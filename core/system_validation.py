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
from core.candidate_pipeline_diagnostics import (
    CandidatePipelineCycleDiagnostic,
    CandidateSymbolPipelineDiagnostic,
    get_global_candidate_pipeline_diagnostics,
)
from core.calibration_analytics import CalibrationAnalyticsEngine, get_global_calibration_analytics
from core.daily_report_engine import DailyReportEngine
from core.live_market_monitor import LiveMarketMonitor, MonitorConfig
from core.market_data import Candle
from core.market_session_engine import AssetClass, MarketSessionEngine, MarketSessionStatus, classify_symbol
from core.opportunity_coverage import OpportunityCoverageEngine
from core.journal_integrity import JournalIntegrityAuditor
from core.paper_brokerage import PaperBrokerageEngine
from core.paper_trade_journal import PaperTradeJournal
from core.paper_state_reconciliation import PaperStateReconciliationEngine
from core.paper_trading_orchestrator import PaperTradingOrchestrator, PaperTradingOrchestratorConfig
from core.recovery_test_harness import RecoveryTestHarness
from core.trade_lifecycle_manager import TradeLifecycleManager
from core.symbol_registry import DEFAULT_SYMBOL_UNIVERSE, get_symbol_registry
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
        "/market-sessions", "/watchlist/active",
        "/monitor/status", "/paper/account", "/lifecycle/status",
        "/paper-journal/summary", "/reports/daily",
        "/reports/scheduler/status", "/paper-trading/status",
        "/dashboard/overview", "/system/validation/run",
        "/continuous-paper/status",
        "/candidate-diagnostics/summary",
        "/candidate-diagnostics/rejections",
        "/calibration-analytics/summary",
        "/opportunity-coverage/summary",
        "/opportunity-coverage/funnel",
        "/opportunity-coverage/by-symbol",
        "/opportunity-coverage/by-asset-class",
        "/opportunity-coverage/terminal-reasons",
        "/validation-readiness/7-day",
        "/symbols/provider-validation",
        "/paper-reconciliation/status",
        "/paper-reconciliation/summary",
        "/paper-recovery/status",
        "/paper-integrity/summary",
        "/paper-integrity/enhanced-summary",
        "/paper-integrity/quarantine",
        "/paper-integrity/duplicates",
        "/paper-integrity/duplicates/analysis",
        "/paper-integrity/incomplete",
        "/paper-integrity/lifecycle",
        "/paper-integrity/timestamps",
        "/paper-integrity/campaign",
        "/paper-integrity/remediation/preview",
        "/paper-integrity/remediation/apply",
        "/paper-integrity/remediation/history",
        "/paper-integrity/rebuild-derived-state",
        "/paper-integrity/campaign/rebuild",
        "/paper-integrity/baselines",
        "/paper-integrity/baseline",
        "/paper-integrity/create-baseline",
        "/paper-integrity/clear-safe-mode",
        "/paper-integrity/recovery",
        "/campaigns",
        "/campaigns/legacy_campaign/audit",
        "/recovery-test/status",
        "/recovery-test/runs/create",
        "/recovery-test/runs",
        "/recovery-test/runs/current",
        "/recovery-test/runs/incomplete",
        "/recovery-test/runs/{run_id}",
        "/recovery-test/runs/{run_id}/snapshot",
        "/recovery-test/runs/{run_id}/verify",
        "/recovery-test/runs/{run_id}/cleanup",
        "/recovery-test/create-pending-order",
        "/recovery-test/create-open-trade",
        "/recovery-test/snapshot",
        "/recovery-test/verify-after-restart",
        "/recovery-test/cleanup",
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
        reconciliation: Any | None = None,
        recovery: Any | None = None,
        campaigns: Any | None = None,
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
        self.reconciliation = reconciliation
        self.recovery = recovery
        self.campaigns = campaigns
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
            ("Market Session Engine", self._market_sessions),
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
            ("Paper State Reconciliation", self._paper_reconciliation),
            ("Paper Runtime Recovery", self._paper_recovery),
            ("Paper Journal Integrity", self._journal_integrity),
            ("Validation Campaigns", self._campaigns),
            ("Recovery Test Harness", self._recovery_test_harness),
            ("Symbol Registry", self._symbol_registry),
            ("Opportunity Coverage", self._opportunity_coverage),
            ("7-Day Validation Readiness", self._seven_day_readiness),
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

    def _market_sessions(self):
        engine = MarketSessionEngine(clock=lambda: datetime(2026, 8, 8, 18, 0, tzinfo=timezone.utc))
        fx = ("EUR-USD", "GBP-USD", "USD-JPY", "USD-CHF", "USD-CAD", "AUD-USD", "NZD-USD")
        if classify_symbol("BTC-USD") is not AssetClass.CRYPTO or any(classify_symbol(item) is not AssetClass.FOREX for item in fx):
            return _fail("Market Session Engine symbol classification failed.")
        watchlist = engine.active_watchlist(DEFAULT_SYMBOL_UNIVERSE)
        if watchlist.active_symbols != ("BTC-USD", "ETH-USD"):
            return _fail("Market Session Engine did not filter weekend Forex symbols correctly.")
        weekday = engine.active_watchlist(DEFAULT_SYMBOL_UNIVERSE, as_of=datetime(2026, 8, 10, 18, 0, tzinfo=timezone.utc))
        if weekday.active_symbols != DEFAULT_SYMBOL_UNIVERSE:
            return _fail("Market Session Engine did not activate all default symbols while Forex is open.")
        if engine.session_for_asset_class(AssetClass.CRYPTO).status is not MarketSessionStatus.OPEN:
            return _fail("Market Session Engine did not mark crypto as open.")
        bypass = engine.active_watchlist(("BTC-USD", "EUR-USD"), ignore_market_sessions=True)
        if bypass.active_symbols != ("BTC-USD", "EUR-USD"):
            return _fail("Market Session Engine ignore mode did not preserve configured symbols.")
        return _pass("Market Session Engine classifies symbols and filters closed markets before analysis.")

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
        pipeline = get_global_candidate_pipeline_diagnostics()
        if not engine.writable():
            return _fail("Candidate Diagnostics persistence is not writable.")
        if not pipeline.writable():
            return _fail("Candidate Pipeline Diagnostics persistence is not writable.")
        summary = engine.summary()
        if summary.markets_analyzed < 0 or summary.candidates_created < 0:
            return _fail("Candidate Diagnostics statistics are invalid.")
        pipeline.summary()
        return _pass("Candidate Diagnostics and cycle pipeline diagnostics are available, writable, and statistically operational.")

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

    def _paper_reconciliation(self):
        engine = self.reconciliation or PaperStateReconciliationEngine(
            broker=self.broker, lifecycle=self.lifecycle, journal=self.journal,
            reports=self.reports, orchestrator=self.orchestrator,
        )
        if not engine.writable():
            return _fail("Paper State Reconciliation history path is not writable.")
        before = (
            len(self.broker.open_positions()),
            len(self.broker.closed_trades()),
            len(self.lifecycle.pending_orders()),
            len(self.lifecycle.events()),
            len(self.journal.entries()),
            len(self.orchestrator.recent_actions()),
        )
        result = engine.run(persist=False)
        after = (
            len(self.broker.open_positions()),
            len(self.broker.closed_trades()),
            len(self.lifecycle.pending_orders()),
            len(self.lifecycle.events()),
            len(self.journal.entries()),
            len(self.orchestrator.recent_actions()),
        )
        if before != after:
            return _fail("Paper State Reconciliation mutated paper trading state.")
        if result.status == "FAIL":
            return _fail("Paper State Reconciliation detected critical discrepancies.", tuple(item.message for item in result.discrepancies if item.severity == "critical"))
        if result.status == "WATCHLIST":
            return _watch(tuple(item.message for item in result.discrepancies if item.severity == "warning"), result.human_readable_summary)
        return _pass("Paper State Reconciliation is available, writable, and read-only.")

    def _paper_recovery(self):
        if self.recovery is None:
            from core.paper_recovery import PaperRecoveryEngine
            engine = self.reconciliation or PaperStateReconciliationEngine(
                broker=self.broker, lifecycle=self.lifecycle, journal=self.journal,
                reports=self.reports, orchestrator=self.orchestrator,
            )
            self.recovery = PaperRecoveryEngine(
                broker=self.broker, lifecycle=self.lifecycle, journal=self.journal,
                reconciliation=engine,
            )
        if not self.recovery.writable():
            return _fail("Paper Runtime Recovery orphan path is not writable.")
        before = (
            len(self.broker.open_positions()),
            len(self.broker.closed_trades()),
            len(self.lifecycle.pending_orders()),
            len(self.lifecycle.events()),
            len(self.journal.entries()),
        )
        result = self.recovery.run(persist_reconciliation=False)
        after = (
            len(self.broker.open_positions()),
            len(self.broker.closed_trades()),
            len(self.lifecycle.pending_orders()),
            len(self.lifecycle.events()),
            len(self.journal.entries()),
        )
        if before != after:
            return _fail("Paper Runtime Recovery mutated paper trading state during validation.")
        if result.summary.status == "FAIL":
            return _fail("Paper Runtime Recovery reports critical reconciliation issues.")
        if result.summary.status == "WATCHLIST":
            if result.summary.runtime_recovery_status == "PASS" and result.summary.active_campaign_recovery_status == "PASS":
                return _watch(result.warnings, "Paper Runtime Recovery is healthy for current runtime; legacy recovery drift remains visible.")
            return _watch(result.warnings, result.human_readable_summary)
        return _pass("Paper Runtime Recovery can run safely and preserves restored state.")

    def _journal_integrity(self):
        auditor = JournalIntegrityAuditor(
            journal=self.journal,
            broker=self.broker,
            lifecycle=self.lifecycle,
            campaigns=self.campaigns,
        )
        summary = auditor.summary()
        if summary.unresolved_critical_records:
            return _fail("Paper Journal Integrity requires SAFE MODE before automation.", tuple(issue.root_cause for issue in summary.issues if issue.severity == "critical"))
        if summary.total_records and summary.safe_mode_status != "CLEARED":
            return _watch(("SAFE MODE is not cleared through a clean validation baseline.",), summary.human_readable_summary)
        if summary.status == "WATCHLIST":
            return _watch(tuple(issue.root_cause for issue in summary.issues), summary.human_readable_summary)
        if auditor.root_cause("47cbfd066469d49904e4dc23").found:
            return _watch(("Named v6.0.15 target trade is present and should be reviewed.",), "Root-cause target trade is present.")
        return _pass("Paper Journal Integrity, lifecycle, duplicate, timestamp, and quarantine checks are safe.")

    def _campaigns(self):
        if self.campaigns is None:
            from core.validation_campaigns import ValidationCampaignManager
            self.campaigns = ValidationCampaignManager(journal=self.journal)
        if not self.campaigns.writable():
            return _fail("Validation Campaign storage is not writable.")
        self.campaigns.list_campaigns()
        try:
            if self.campaigns.get("legacy_campaign") is not None:
                self.campaigns.legacy_audit()
        except Exception as exc:
            return _watch((f"Legacy campaign audit is unavailable: {exc}",), "Validation Campaign storage is available but legacy audit needs review.")
        return _pass("Validation Campaign storage is available and readable.")

    def _recovery_test_harness(self):
        from core.paper_recovery import PaperRecoveryEngine
        campaigns = self.campaigns
        reconciliation = self.reconciliation or PaperStateReconciliationEngine(
            broker=self.broker, lifecycle=self.lifecycle, journal=self.journal,
            reports=self.reports, orchestrator=self.orchestrator, campaigns=campaigns,
        )
        recovery = self.recovery or PaperRecoveryEngine(
            broker=self.broker, lifecycle=self.lifecycle, journal=self.journal,
            reconciliation=reconciliation,
        )
        harness = RecoveryTestHarness(
            broker=self.broker,
            lifecycle=self.lifecycle,
            campaigns=campaigns,
            reconciliation=reconciliation,
            recovery=recovery,
            reports_dir=Path(tempfile.gettempdir()) / "structureiq-validation-recovery-test",
        )
        if not harness.writable():
            return _fail("Recovery Test Harness storage is not writable.")
        account = self.broker.account()
        if getattr(account, "paper_trading_enabled", False) or not getattr(account, "advisory_only", True):
            return _fail("Recovery Test Harness safety check failed; fixture creation would not be paper-only.")
        blocked = harness.verify_after_restart()
        if blocked.status not in {"NOT_READY", "AMBIGUOUS"}:
            return _fail("Recovery Test Harness did not fail closed when no run-bound snapshot was available.")
        if not getattr(blocked, "harness_precondition_failure", False):
            return _fail("Recovery Test Harness did not distinguish harness preconditions from recovery failure.")
        return _pass("Recovery Test Harness run identity, stale-snapshot guard, paper-only storage, and fail-closed verification are available; validation did not create fixtures.")

    def _symbol_registry(self):
        registry = get_symbol_registry()
        if registry.default_symbols() != DEFAULT_SYMBOL_UNIVERSE or len(DEFAULT_SYMBOL_UNIVERSE) != 9:
            return _fail("Symbol Registry default universe is invalid.")
        validations = registry.validate_provider_symbols()
        if sum(item.supported for item in validations) != 9:
            return _fail("Symbol Registry provider mapping is incomplete.")
        if registry.validate_provider_symbol("UNKNOWN", "yahoo").supported:
            return _fail("Symbol Registry incorrectly supports an unknown symbol.")
        return _pass("Symbol Registry contains 9 defaults and deterministic provider mappings.")

    def _opportunity_coverage(self):
        with tempfile.TemporaryDirectory() as temp:
            engine = OpportunityCoverageEngine(_EmptyPipeline(), None, campaigns_root=Path(temp))
            if engine.summary().markets_analyzed != 0:
                return _fail("Opportunity Coverage empty state is invalid.")
            if not engine.funnel().reconciles:
                return _fail("Opportunity Coverage empty funnel did not reconcile.")
            populated = _PopulatedPipeline()
            report = OpportunityCoverageEngine(populated, None, campaigns_root=Path(temp)).report(campaign_id="campaign_validation")
            path = Path(temp) / "campaign_validation" / "opportunity_coverage.json"
            if report.summary.markets_analyzed != 2 or report.summary.candidates_created != 1:
                return _fail("Opportunity Coverage populated-state aggregation is invalid.")
            if not path.exists():
                return _fail("Opportunity Coverage campaign isolation file was not written.")
        return _pass("Opportunity Coverage handles empty/populated states, by-symbol and by-asset aggregation, and campaign isolation safely.")

    def _seven_day_readiness(self):
        registry = get_symbol_registry()
        if len(registry.default_symbols()) != 9:
            return _fail("7-day readiness cannot pass without the 9-symbol default universe.")
        if not all(item.supported for item in registry.validate_provider_symbols()):
            return _fail("7-day readiness cannot pass without provider mappings.")
        return _pass("7-day readiness capability checks can pass without requiring Forex to be open.")

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


class _EmptyPipeline:
    def recent(self, limit: int = 100, *, campaign_id: str | None = None):
        del limit, campaign_id
        return ()


class _PopulatedPipeline:
    def recent(self, limit: int = 100, *, campaign_id: str | None = None):
        del limit
        cycle = CandidatePipelineCycleDiagnostic(
            cycle_id="validation_cycle",
            campaign_id=campaign_id,
            started_at=_now(),
            completed_at=_now(),
            symbols_requested=2,
            symbols_scanned=2,
            symbols_with_market_data=2,
            symbols_without_market_data=0,
            symbols_skipped=0,
            symbols_skipped_market_closed=0,
            candidates_created=1,
            candidates_rejected=1,
            orders_created=0,
            trades_opened=0,
            cycle_status="completed",
            cycle_duration_ms=1.0,
            symbol_diagnostics=(
                CandidateSymbolPipelineDiagnostic(
                    symbol="BTC-USD",
                    market_data_status="available",
                    candles_received=100,
                    timeframes_received=1,
                    structure_status="completed",
                    bias_status="bullish",
                    setup_status="pullback",
                    confidence_score=8.0,
                    setup_quality_score=80.0,
                    risk_status="available",
                    candidate_status="created",
                    final_outcome="candidate_created",
                    rejection_stage=None,
                    rejection_reason=None,
                    exception_type=None,
                    exception_message=None,
                ),
                CandidateSymbolPipelineDiagnostic(
                    symbol="ETH-USD",
                    market_data_status="available",
                    candles_received=100,
                    timeframes_received=1,
                    structure_status="completed",
                    bias_status="bullish",
                    setup_status="pullback",
                    confidence_score=4.0,
                    setup_quality_score=70.0,
                    risk_status="available",
                    candidate_status="rejected",
                    final_outcome="candidate_rejected",
                    rejection_stage="CONFIDENCE",
                    rejection_reason="directional_confidence",
                    exception_type=None,
                    exception_message=None,
                ),
            ),
            persistence_errors=(),
            zero_candidate_explanation=None,
        )
        return (cycle,) if campaign_id in {None, "campaign_validation"} else ()


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
