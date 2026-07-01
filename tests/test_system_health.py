from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app, get_system_health_engine
from core.daily_report_engine import DailyReportEngine
from core.daily_report_scheduler import DailyReportScheduler, DailyReportSchedulerConfig
from core.live_market_monitor import LiveMarketMonitor, MonitorConfig
from core.market_data import Candle, MarketDataError
from core.paper_brokerage import PaperBrokerageEngine
from core.paper_trade_journal import PaperTradeJournal
from core.paper_trading_orchestrator import PaperTradingOrchestrator, PaperTradingOrchestratorConfig
from core.system_health import SystemHealthEngine, reset_latest_system_health
from core.trade_lifecycle_manager import TradeLifecycleManager


class _Provider:
    provider_name = "health-test"
    def __init__(self, fail=False): self.fail = fail
    def get_candles(self, symbol, timeframe, lookback):
        if self.fail: raise MarketDataError("synthetic health provider failure")
        return [Candle(i, 100, 101, 99, 100, 1000) for i in range(lookback)]


def _engine(tmp_path: Path, *, provider=None):
    provider = provider or _Provider()
    monitor = LiveMarketMonitor(provider, MonitorConfig(symbols=["BTC-USD"], timeframes=["5m"], lookback=50, write_events=False))
    broker = PaperBrokerageEngine()
    lifecycle = TradeLifecycleManager(provider, monitor, broker)
    journal = PaperTradeJournal(broker, lifecycle, tmp_path / "journal.jsonl")
    reports = DailyReportEngine(journal, lifecycle, broker, monitor, reports_dir=tmp_path / "reports/daily")
    scheduler = DailyReportScheduler(reports, DailyReportSchedulerConfig(history_path=str(tmp_path / "reports/history.jsonl")))
    orchestrator = PaperTradingOrchestrator(monitor, lifecycle, broker, journal, reports, PaperTradingOrchestratorConfig(generate_daily_report_after_cycle=False))
    engine = SystemHealthEngine(
        project_root=tmp_path, market_data_provider=provider,
        live_monitor=monitor, paper_brokerage=broker,
        trade_lifecycle_manager=lifecycle, paper_trade_journal=journal,
        daily_report_engine=reports, daily_report_scheduler=scheduler,
        paper_trading_orchestrator=orchestrator,
    )
    return engine, monitor, scheduler, orchestrator


def test_health_engine_clean_state_is_pass(tmp_path) -> None:
    engine, *_ = _engine(tmp_path)
    report = engine.check()
    assert report.status == "PASS"
    assert report.score == 100
    assert report.paper_trading_operational_readiness == "READY"
    assert report.blocking_issues == ()


def test_missing_optional_files_do_not_fail_and_required_folders_are_created(tmp_path) -> None:
    engine, *_ = _engine(tmp_path)
    storage = engine.storage()
    assert storage.status == "PASS"
    for folder in ("logs", "research", "reports", "reports/daily"):
        assert (tmp_path / folder).is_dir()
    assert all(not info["exists"] for info in storage.details["optional_files"].values())


def test_storage_corruption_and_writability_are_reported(tmp_path) -> None:
    engine, *_ = _engine(tmp_path)
    state = tmp_path / "research/paper_account_state.json"
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text("not-json", encoding="utf-8")
    storage = engine.storage()
    assert storage.status == "FAIL"
    assert any("corrupted" in item for item in storage.blocking_issues)


def test_component_status_contains_every_dimension(tmp_path) -> None:
    engine, *_ = _engine(tmp_path)
    names = {item.name for item in engine.components()}
    assert {
        "application", "configuration", "market_data_provider", "live_monitor",
        "paper_brokerage", "trade_lifecycle_manager", "paper_trade_journal",
        "daily_report_engine", "daily_report_scheduler", "paper_trading_orchestrator",
        "dashboard", "storage", "logs", "research_files", "reports",
        "tests_status_placeholder",
    } <= names


def test_paper_readiness_not_ready_when_components_unavailable(tmp_path) -> None:
    engine = SystemHealthEngine(project_root=tmp_path)
    readiness = engine.readiness()
    assert readiness.paper_trading_operational_readiness == "NOT_READY"
    assert readiness.required_components_available is False


def test_errors_aggregate_known_component_errors(tmp_path) -> None:
    engine, monitor, _, _ = _engine(tmp_path, provider=_Provider(fail=True))
    monitor.run_once()
    errors = engine.errors()
    assert errors.total_errors >= 1
    assert any(item["component"] == "live_monitor" for item in errors.errors)


def test_health_logging_is_append_only(tmp_path) -> None:
    engine, *_ = _engine(tmp_path)
    engine.check(); engine.check()
    lines = (tmp_path / "logs/system_health.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2


def test_system_api_and_dashboard(tmp_path) -> None:
    engine, *_ = _engine(tmp_path)
    app.dependency_overrides[get_system_health_engine] = lambda: engine
    try:
        client = TestClient(app)
        paths = client.get("/openapi.json").json()["paths"]
        for path in ("/system/health", "/system/readiness", "/system/errors", "/system/storage", "/system/components"):
            assert path in paths
            assert "system" in next(iter(paths[path].values()))["tags"]
        health = client.get("/system/health").json()
        assert health["status"] == "PASS"
        assert client.get("/system/readiness").json()["paper_trading_operational_readiness"] == "READY"
        assert client.get("/system/storage").json()["status"] == "PASS"
        assert len(client.get("/system/components").json()) >= 16
        overview = client.get("/dashboard/overview").json()
        assert overview["system_health_status"] == "PASS"
        assert overview["paper_trading_operational_readiness"] == "READY"
        assert overview["latest_health_check_at"] is not None
    finally:
        app.dependency_overrides.clear()
        reset_latest_system_health()
