"""Hermetic end-to-end validation harness for the StructureIQ paper platform."""

from __future__ import annotations

import hashlib
import importlib
import json
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

from fastapi.encoders import jsonable_encoder

from app.config import APP_VERSION
from core.analysis_engine import AnalysisEngine
from core.candidate_diagnostics import get_global_candidate_diagnostics
from core.calibration_analytics import CalibrationAnalyticsEngine, get_global_calibration_analytics
from core.daily_report_engine import DailyReportEngine
from core.live_market_monitor import LiveMarketMonitor, MonitorConfig
from core.market_data import Candle
from core.paper_brokerage import PaperBrokerageEngine
from core.paper_trade_journal import PaperTradeJournal
from core.paper_trading_orchestrator import PaperTradingOrchestrator, PaperTradingOrchestratorConfig
from core.trade_lifecycle_manager import TradeLifecycleManager
from models.schemas import AnalysisRequest


@dataclass(frozen=True)
class ComponentValidationResult:
    component: str
    status: str
    duration_ms: float
    warnings: tuple[str, ...]
    blocking_issues: tuple[str, ...]
    recommendations: tuple[str, ...]
    human_readable_summary: str


@dataclass(frozen=True)
class SystemValidationResult:
    run_id: str
    validation_status: str
    overall_score: float
    components_checked: int
    passed: int
    watchlist: int
    failed: int
    started_at: str
    completed_at: str
    duration_ms: float
    app_version: str
    paper_trading_ready: bool
    continuous_runtime_ready: bool
    component_results: tuple[ComponentValidationResult, ...]
    blocking_issues: tuple[str, ...]
    warnings: tuple[str, ...]
    recommendations: tuple[str, ...]
    human_readable_summary: str


class SystemValidationHarness:
    """Validate every subsystem independently without external network access."""

    REQUIRED_API_PATHS = {
        "/health", "/analysis", "/calibrate", "/system/health",
        "/monitor/status", "/paper/account", "/lifecycle/status",
        "/paper-journal/summary", "/reports/daily",
        "/reports/scheduler/status", "/paper-trading/status",
        "/dashboard/overview", "/system/validation/run",
        "/continuous-paper/status",
        "/candidate-diagnostics/summary",
        "/calibration-analytics/summary",
    }

    def __init__(
        self,
        *,
        health_engine: Any,
        market_data_provider: Any,
        monitor: Any,
        broker: Any,
        lifecycle: Any,
        journal: Any,
        reports: Any,
        scheduler: Any,
        orchestrator: Any,
        dashboard: Any,
        api_paths_provider: Callable[[], set[str]] | None = None,
        history_path: str | Path = "reports/system_validation_history.jsonl",
        stopped_components_watchlist: bool = True,
    ) -> None:
        self.health_engine = health_engine
        self.provider = market_data_provider
        self.monitor = monitor
        self.broker = broker
        self.lifecycle = lifecycle
        self.journal = journal
        self.reports = reports
        self.scheduler = scheduler
        self.orchestrator = orchestrator
        self.dashboard = dashboard
        self.api_paths_provider = api_paths_provider or (lambda: set())
        self.history_path = Path(history_path)
        self.stopped_components_watchlist = stopped_components_watchlist
        self._history: list[SystemValidationResult] = []
        self._load_history()

    def run(self) -> SystemValidationResult:
        started_clock = time.perf_counter()
        started = _now()
        steps = (
            ("Application", self._application),
            ("Configuration", self._configuration),
            ("Storage", self._storage),
            ("Research Files", self._research_files),
            ("Market Data Provider", self._provider),
            ("Analysis Engine", self._analysis),
            ("Live Monitor", self._monitor),
            ("Paper Brokerage", self._brokerage),
            ("Trade Lifecycle Manager", self._lifecycle),
            ("Paper Journal", self._journal),
            ("Daily Reports", self._reports),
            ("Daily Scheduler", self._scheduler),
            ("Paper Trading Orchestrator", self._orchestrator),
            ("Continuous Paper Trading", self._continuous_paper),
            ("Candidate Diagnostics", self._candidate_diagnostics),
            ("Calibration Analytics", self._calibration_analytics),
            ("Dashboard", self._dashboard),
            ("Observability", self._observability),
            ("API Registration", self._api_registration),
            ("Startup Launcher", self._startup_launcher),
        )
        results = tuple(self._run_component(name, check) for name, check in steps)
        passed = sum(item.status == "PASS" for item in results)
        watchlist = sum(item.status == "WATCHLIST" for item in results)
        failed = sum(item.status == "FAIL" for item in results)
        warnings = tuple(dict.fromkeys(w for item in results for w in item.warnings))
        blockers = tuple(dict.fromkeys(b for item in results for b in item.blocking_issues))
        recommendations = tuple(dict.fromkeys(r for item in results for r in item.recommendations))
        score = round(sum(_score(item.status) for item in results) / len(results), 2)
        health = self.health_engine.check(write_log=False)
        paper_ready = health.paper_trading_operational_readiness == "READY" and not blockers
        continuous_ready = paper_ready and not failed and not watchlist
        status = "FAIL" if failed or blockers else "PASS" if score >= 90 and paper_ready and not warnings else "WATCHLIST"
        completed = _now()
        result = SystemValidationResult(
            run_id=hashlib.sha256(f"validation:{started}".encode()).hexdigest()[:24],
            validation_status=status, overall_score=score,
            components_checked=len(results), passed=passed, watchlist=watchlist,
            failed=failed, started_at=started, completed_at=completed,
            duration_ms=round((time.perf_counter() - started_clock) * 1000, 3),
            app_version=APP_VERSION, paper_trading_ready=paper_ready,
            continuous_runtime_ready=continuous_ready,
            component_results=results, blocking_issues=blockers,
            warnings=warnings, recommendations=recommendations,
            human_readable_summary=(
                "StructureIQ successfully passed full system validation."
                if status == "PASS" else
                f"StructureIQ validation is {status} with {failed} failed and {watchlist} watchlist components."
            ),
        )
        self._history.append(result)
        self._persist(result)
        _set_latest(result)
        return result

    def history(self, limit: int | None = None) -> tuple[SystemValidationResult, ...]:
        values = tuple(self._history)
        return values[-limit:] if limit is not None else values

    def latest(self) -> SystemValidationResult | None:
        return self._history[-1] if self._history else None

    def reset_history(self) -> int:
        count = len(self._history)
        self._history.clear()
        if self.history_path.exists():
            self.history_path.unlink()
        _set_latest(None)
        return count

    def _run_component(self, name: str, check: Callable[[], tuple[str, tuple[str, ...], tuple[str, ...], tuple[str, ...], str]]) -> ComponentValidationResult:
        started = time.perf_counter()
        try:
            status, warnings, blockers, recommendations, summary = check()
        except Exception as exc:
            status, warnings = "FAIL", ()
            blockers = (f"{name} validation failed: {exc}",)
            recommendations = (f"Inspect and repair {name} before continuous paper trading.",)
            summary = f"{name} validation failed safely; remaining checks continued."
        return ComponentValidationResult(name, status, round((time.perf_counter() - started) * 1000, 3), warnings, blockers, recommendations, summary)

    def _application(self):
        return _pass("Application runtime and version identity are available.")

    def _configuration(self):
        importlib.import_module("app.config")
        return _pass(f"Configuration loaded for StructureIQ {APP_VERSION}.")

    def _storage(self):
        result = self.health_engine.storage()
        return _from_health(result)

    def _research_files(self):
        dimension = next(item for item in self.health_engine.check(write_log=False).dimensions if item.name == "research_files")
        return _from_health(dimension)

    def _provider(self):
        if self.provider is None:
            return _fail("Market data provider is unavailable.")
        return _pass("Market data provider is configured; validation made no external request.")

    def _analysis(self):
        provider = _SyntheticProvider()
        response = AnalysisEngine(provider).analyze(AnalysisRequest(symbol="BTC-USD", timeframe="5m", higher_timeframe="1h", lookback=80))
        if response.action not in {"buy", "sell", "wait", "no_trade"}:
            return _fail("Analysis Engine returned an invalid action.")
        return _pass("Analysis Engine completed against deterministic in-process candles.")

    def _monitor(self):
        if self.monitor is None:
            return _fail("Live Monitor is unavailable.")
        state = self.monitor.status()
        if state.last_error:
            return _watch((f"Live Monitor reports {state.last_error}",), "Live Monitor is available with errors.")
        if self.stopped_components_watchlist and not state.running:
            return _watch(("Live Monitor is stopped.",), "Live Monitor is available and stopped.")
        return _pass("Live Monitor is operational.")

    def _brokerage(self):
        account = self.broker.account()
        if account.balance < 0:
            return _fail("Paper Brokerage balance is invalid.")
        return _pass("Paper Brokerage initialized successfully.")

    def _lifecycle(self):
        self.lifecycle.status()
        return _pass("Trade Lifecycle Manager state is available.")

    def _journal(self):
        self.journal.summary()
        if not _parent_writable(self.journal.path):
            return _fail("Paper Journal path is not writable.")
        return _pass("Paper Journal is readable and writable.")

    def _reports(self):
        self.reports.reports_dir.mkdir(parents=True, exist_ok=True)
        if not _parent_writable(self.reports.reports_dir / "probe.json"):
            return _fail("Daily report path is not writable.")
        return _pass("Daily Report Engine storage is operational.")

    def _scheduler(self):
        state = self.scheduler.status()
        self.scheduler.next_run_time()
        if state.paused:
            return _fail("Daily Report Scheduler is paused.")
        if self.stopped_components_watchlist and not state.running:
            return _watch(("Daily Report Scheduler is stopped.",), "Daily Report Scheduler is available and stopped.")
        return _pass("Daily Report Scheduler is operational.")

    def _orchestrator(self):
        state = self.orchestrator.status()
        if state.paused:
            return _fail("Paper Trading Orchestrator is paused.")
        # Exercise the real orchestration class with isolated, no-network dependencies.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            provider = _SyntheticProvider()
            monitor = LiveMarketMonitor(provider, MonitorConfig(symbols=["BTC-USD"], timeframes=["5m"], lookback=50, write_events=False), analysis_engine_factory=lambda source: _NoCandidateAnalysis())
            broker = PaperBrokerageEngine()
            lifecycle = TradeLifecycleManager(provider, monitor, broker)
            journal = PaperTradeJournal(broker, lifecycle, root / "journal.jsonl")
            reports = DailyReportEngine(journal, lifecycle, broker, monitor, reports_dir=root / "daily")
            orchestrator = PaperTradingOrchestrator(monitor, lifecycle, broker, journal, reports, PaperTradingOrchestratorConfig(generate_daily_report_after_cycle=True))
            cycle = orchestrator.run_cycle()
            if cycle.status != "completed":
                return _fail("Isolated Paper Trading Orchestrator cycle did not complete cleanly.")
        return _pass("Paper Trading Orchestrator completed a hermetic no-candidate cycle.")

    def _dashboard(self):
        for method in (self.dashboard.overview, self.dashboard.readiness, self.dashboard.risks, self.dashboard.recommendations):
            method()
        return _pass("Dashboard summaries are operational.")

    def _continuous_paper(self):
        module = importlib.import_module("core.continuous_paper_trading")
        runtime = module.current_continuous_paper_trading()
        if runtime is None:
            return _pass("Continuous Paper Trading is available and not auto-started.")
        state = runtime.status()
        if state.paused:
            return _watch(state.pause_reasons, "Continuous Paper Trading is available but paused safely.")
        return _pass("Continuous Paper Trading runtime state is operational and paper-only.")

    def _candidate_diagnostics(self):
        engine = get_global_candidate_diagnostics()
        if not engine.writable():
            return _fail("Candidate Diagnostics persistence is not writable.")
        summary = engine.summary()
        if summary.markets_analyzed < 0 or summary.candidates_created < 0:
            return _fail("Candidate Diagnostics statistics are invalid.")
        return _pass("Candidate Diagnostics is available, writable, and statistically operational.")

    def _calibration_analytics(self):
        engine = get_global_calibration_analytics()
        if not engine.readable(): return _fail("Candidate diagnostics history is not readable for calibration analytics.")
        engine.summary()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); empty = CalibrationAnalyticsEngine(root / "empty.jsonl", lambda: 0)
            if empty.summary().markets_analyzed != 0: return _fail("Calibration Analytics empty-state calculation is invalid.")
            populated_path = root / "populated.jsonl"
            populated_path.write_text(json.dumps({
                "analysis_completed": True, "candidate_created": False, "symbol": "TEST",
                "best_strategy": "no_strategy", "market_regime": "unknown",
                "highest_confidence": 50, "highest_setup_quality": 50, "overall_score": 50,
                "blocked_reasons": ["directional_confidence"], "distance_to_candidate": [],
            }) + "\n", encoding="utf-8")
            if CalibrationAnalyticsEngine(populated_path, lambda: 0).summary().markets_analyzed != 1:
                return _fail("Calibration Analytics populated-state calculation is invalid.")
        return _pass("Calibration Analytics is available, read-only, and handles empty and populated diagnostics safely.")

    def _observability(self):
        report = self.health_engine.check(write_log=False)
        if report.status == "FAIL":
            return _fail("System Health reports blocking issues.", report.blocking_issues)
        if report.status == "WATCHLIST":
            return _watch(report.warnings, "System Health is operational with warnings.")
        return _pass("System Health and Observability is operational.")

    def _api_registration(self):
        missing = self.REQUIRED_API_PATHS - set(self.api_paths_provider())
        if missing:
            return _fail("Required API paths are missing.", tuple(f"Missing API path: {path}" for path in sorted(missing)))
        return _pass("Required API endpoints are registered.")

    def _startup_launcher(self):
        launcher = importlib.import_module("start")
        health = launcher.run_startup_checks(self.health_engine.root)
        if not health.passed:
            return _fail("Startup Launcher validation failed.", tuple(item.message for item in health.checks if not item.passed))
        return _pass("Startup Launcher validation passed.")

    def _persist(self, result: SystemValidationResult) -> None:
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        with self.history_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(jsonable_encoder(result), separators=(",", ":")) + "\n")

    def _load_history(self) -> None:
        if not self.history_path.exists(): return
        for line in self.history_path.read_text(encoding="utf-8").splitlines():
            try:
                raw = json.loads(line)
                components = tuple(ComponentValidationResult(**item) for item in raw.pop("component_results"))
                for key in ("blocking_issues", "warnings", "recommendations"):
                    raw[key] = tuple(raw.get(key, ()))
                self._history.append(SystemValidationResult(component_results=components, **raw))
            except (ValueError, TypeError, KeyError, json.JSONDecodeError):
                continue


class _SyntheticProvider:
    provider_name = "validation-synthetic"
    def get_candles(self, symbol, timeframe, lookback):
        del symbol, timeframe
        candles = []
        for index in range(max(lookback, 80)):
            close = 100 + index * 0.1 + ((index % 8) - 4) * 0.2
            candles.append(Candle(index, close - 0.1, close + 0.8, close - 0.8, close, 1000))
        return candles[-lookback:]


class _NoCandidateAnalysis:
    def analyze(self, request):
        return SimpleNamespace(
            symbol=request.symbol, action="wait", setup="no_valid_setup",
            setup_plan=SimpleNamespace(setup_status="developing"),
            trader_analysis=SimpleNamespace(trade_plan=SimpleNamespace(status="waiting")),
        )


def _pass(summary): return "PASS", (), (), (), summary
def _watch(warnings, summary): return "WATCHLIST", tuple(warnings), (), ("Review advisory stopped or warning state before continuous runtime.",), summary
def _fail(summary, blockers=()): return "FAIL", (), tuple(blockers) or (summary,), ("Resolve the blocking subsystem issue.",), summary
def _from_health(item):
    if item.status == "FAIL": return _fail(item.human_readable_summary, item.blocking_issues)
    if item.status == "WATCHLIST": return _watch(item.warnings, item.human_readable_summary)
    return _pass(item.human_readable_summary)
def _score(status): return {"PASS": 100.0, "WATCHLIST": 75.0, "FAIL": 0.0}[status]
def _parent_writable(path: Path) -> bool:
    try:
        target = path if path.suffix == "" else path.parent
        target.mkdir(parents=True, exist_ok=True)
        probe = target / ".validation-probe"; probe.write_text("ok", encoding="utf-8"); probe.unlink()
        return True
    except OSError: return False
def _now(): return datetime.now(timezone.utc).isoformat()


_LATEST_VALIDATION: SystemValidationResult | None = None
def _set_latest(value):
    global _LATEST_VALIDATION; _LATEST_VALIDATION = value
def latest_system_validation(): return _LATEST_VALIDATION
