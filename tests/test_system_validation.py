from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

import start
from app.main import app, get_system_validation_harness
from core.daily_report_engine import DailyReportEngine
from core.daily_report_scheduler import DailyReportScheduler, DailyReportSchedulerConfig
from core.live_market_monitor import LiveMarketMonitor, MonitorConfig
from core.market_data import Candle
from core.paper_brokerage import PaperBrokerageEngine
from core.paper_trade_journal import PaperTradeJournal
from core.paper_trading_orchestrator import PaperTradingOrchestrator, PaperTradingOrchestratorConfig
from core.system_health import SystemHealthEngine
from core.system_validation import SystemValidationHarness
from core.trade_lifecycle_manager import TradeLifecycleManager


class _Provider:
    provider_name = "validation-test"
    def get_candles(self, symbol, timeframe, lookback):
        raise AssertionError("configured provider must not be called by validation")


class _Dashboard:
    def overview(self): return SimpleNamespace(status="available")
    def readiness(self): return SimpleNamespace(status="available")
    def risks(self): return SimpleNamespace(status="available")
    def recommendations(self): return SimpleNamespace(status="available")


def _harness(tmp_path: Path, *, stopped_watch=True, api_paths=None, dashboard=None):
    root = Path(__file__).resolve().parents[1]
    provider = _Provider()
    monitor = LiveMarketMonitor(provider, MonitorConfig(symbols=["BTC-USD"], timeframes=["5m"], lookback=50, write_events=False))
    broker = PaperBrokerageEngine()
    lifecycle = TradeLifecycleManager(provider, monitor, broker)
    journal = PaperTradeJournal(broker, lifecycle, tmp_path / "journal.jsonl")
    reports = DailyReportEngine(journal, lifecycle, broker, monitor, reports_dir=tmp_path / "daily")
    scheduler = DailyReportScheduler(reports, DailyReportSchedulerConfig(history_path=str(tmp_path / "scheduler.jsonl")))
    orchestrator = PaperTradingOrchestrator(monitor, lifecycle, broker, journal, reports, PaperTradingOrchestratorConfig(generate_daily_report_after_cycle=False))
    health = SystemHealthEngine(
        project_root=root, market_data_provider=provider, live_monitor=monitor,
        paper_brokerage=broker, trade_lifecycle_manager=lifecycle,
        paper_trade_journal=journal, daily_report_engine=reports,
        daily_report_scheduler=scheduler, paper_trading_orchestrator=orchestrator,
        log_path=tmp_path / "health.jsonl",
    )
    paths = api_paths if api_paths is not None else SystemValidationHarness.REQUIRED_API_PATHS
    return SystemValidationHarness(
        health_engine=health, market_data_provider=provider, monitor=monitor,
        broker=broker, lifecycle=lifecycle, journal=journal, reports=reports,
        scheduler=scheduler, orchestrator=orchestrator,
        dashboard=dashboard or _Dashboard(), api_paths_provider=lambda: set(paths),
        history_path=tmp_path / "validation.jsonl",
        stopped_components_watchlist=stopped_watch,
    )


def test_overall_pass_and_every_component_is_timed(tmp_path) -> None:
    harness = _harness(tmp_path, stopped_watch=False)
    result = harness.run()
    assert result.validation_status == "PASS"
    assert result.overall_score >= 90
    assert result.paper_trading_ready is True
    assert result.continuous_runtime_ready is True
    assert result.components_checked == 21
    assert all(item.duration_ms >= 0 for item in result.component_results)
    names = {item.component for item in result.component_results}
    assert {"Storage", "Live Monitor", "Paper Brokerage", "Trade Lifecycle Manager", "Paper Journal", "Daily Reports", "Daily Scheduler", "Continuous Paper Trading", "Candidate Diagnostics", "Calibration Analytics", "Dashboard", "Observability"} <= names


def test_stopped_monitor_and_scheduler_produce_watchlist(tmp_path) -> None:
    result = _harness(tmp_path, stopped_watch=True).run()
    assert result.validation_status == "WATCHLIST"
    assert result.watchlist >= 2
    assert any("stopped" in warning.lower() for warning in result.warnings)
    assert result.continuous_runtime_ready is False


def test_missing_required_api_produces_fail_but_remaining_steps_run(tmp_path) -> None:
    result = _harness(tmp_path, stopped_watch=False, api_paths=set()).run()
    assert result.validation_status == "FAIL"
    assert result.failed == 1
    api = next(item for item in result.component_results if item.component == "API Registration")
    startup = next(item for item in result.component_results if item.component == "Startup Launcher")
    assert api.status == "FAIL"
    assert startup.status == "PASS"
    assert result.blocking_issues


def test_independent_dashboard_failure_does_not_stop_observability(tmp_path) -> None:
    class _BrokenDashboard(_Dashboard):
        def overview(self): raise RuntimeError("synthetic dashboard failure")

    result = _harness(tmp_path, stopped_watch=False, dashboard=_BrokenDashboard()).run()
    dashboard = next(item for item in result.component_results if item.component == "Dashboard")
    observability = next(item for item in result.component_results if item.component == "Observability")
    assert dashboard.status == "FAIL"
    assert observability.status == "PASS"


def test_history_persistence_retrieval_and_reset(tmp_path) -> None:
    harness = _harness(tmp_path, stopped_watch=False)
    harness.run(); harness.run()
    assert len(harness.history()) == 2
    assert len((tmp_path / "validation.jsonl").read_text(encoding="utf-8").splitlines()) == 2
    reloaded = _harness(tmp_path, stopped_watch=False)
    assert len(reloaded.history()) == 2
    assert reloaded.reset_history() == 2
    assert not (tmp_path / "validation.jsonl").exists()


def test_validation_api_openapi_and_dashboard(tmp_path) -> None:
    harness = _harness(tmp_path, stopped_watch=False, api_paths=set(app.openapi()["paths"]))
    app.dependency_overrides[get_system_validation_harness] = lambda: harness
    try:
        client = TestClient(app)
        paths = client.get("/openapi.json").json()["paths"]
        for path in (
            "/system/validation", "/system/validation/run",
            "/system/validation/history", "/system/validation/reset-history",
        ):
            assert path in paths
            assert "system" in next(iter(paths[path].values()))["tags"]
        result = client.post("/system/validation/run").json()
        assert result["validation_status"] == "PASS"
        assert client.get("/system/validation").json()["run_id"] == result["run_id"]
        assert client.get("/system/validation/history").json()
        overview = client.get("/dashboard/overview").json()
        assert overview["latest_validation_status"] == "PASS"
        assert overview["continuous_runtime_ready"] is True
        reset = client.post("/system/validation/reset-history").json()
        assert reset["cleared_runs"] == 1
    finally:
        app.dependency_overrides.clear()


def test_launcher_validate_exit_codes(monkeypatch) -> None:
    monkeypatch.setattr(start, "write_startup_log", lambda **kwargs: None)
    monkeypatch.setattr(start, "run_system_validation", lambda: 0)
    assert start.main(["--validate"]) == 0
    monkeypatch.setattr(start, "run_system_validation", lambda: 1)
    assert start.main(["--validate"]) == 1
    monkeypatch.setattr(start, "run_system_validation", lambda: 2)
    assert start.main(["--validate"]) == 2
