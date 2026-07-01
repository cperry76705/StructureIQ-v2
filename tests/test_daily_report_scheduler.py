from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app, get_daily_report_scheduler
from core.daily_report_engine import DailyReportEngine
from core.daily_report_scheduler import (
    DailyReportScheduler,
    DailyReportSchedulerConfig,
)
from core.live_market_monitor import LiveMarketMonitor, MonitorConfig
from core.market_data import Candle
from core.paper_brokerage import PaperBrokerageEngine
from core.paper_trade_journal import PaperTradeJournal
from core.trade_lifecycle_manager import TradeLifecycleManager


class _Provider:
    def get_candles(self, symbol, timeframe, lookback):
        return [Candle(i, 100, 101, 99, 100, 1000) for i in range(lookback)]


def _scheduler(tmp_path: Path, **overrides):
    provider = _Provider()
    monitor = LiveMarketMonitor(provider, MonitorConfig(symbols=["BTC-USD"], timeframes=["5m"], lookback=50, write_events=False))
    broker = PaperBrokerageEngine()
    lifecycle = TradeLifecycleManager(provider, monitor, broker)
    journal = PaperTradeJournal(broker, lifecycle, tmp_path / "journal.jsonl")
    reports = DailyReportEngine(journal, lifecycle, broker, monitor, reports_dir=tmp_path / "daily")
    config = DailyReportSchedulerConfig(history_path=str(tmp_path / "history.jsonl"), **overrides)
    return DailyReportScheduler(reports, config), reports


def test_scheduler_initializes_stopped(tmp_path) -> None:
    scheduler, _ = _scheduler(tmp_path)
    status = scheduler.status()
    assert status.running is False
    assert status.enabled is False
    assert status.paused is False
    assert status.next_run_at is None


def test_run_now_generates_previous_day_report(tmp_path) -> None:
    scheduler, reports = _scheduler(tmp_path)
    result = scheduler.run_now()
    expected = scheduler._default_report_date().isoformat()
    assert result.report_date == expected
    assert result.status == "completed"
    assert result.report_status == "NO_TRADES"
    assert reports.get(expected) is not None


def test_run_now_accepts_explicit_date(tmp_path) -> None:
    scheduler, _ = _scheduler(tmp_path)
    result = scheduler.run_now(date(2026, 7, 1))
    assert result.report_date == "2026-07-01"
    assert result.report_path.endswith("2026-07-01.json")


def test_existing_report_is_not_overwritten_without_permission(tmp_path) -> None:
    scheduler, reports = _scheduler(tmp_path)
    first = scheduler.run_now(date(2026, 7, 1))
    path = Path(first.report_path)
    original = path.read_text(encoding="utf-8")
    skipped = scheduler.run_now(date(2026, 7, 1))
    assert skipped.status == "skipped_existing"
    assert path.read_text(encoding="utf-8") == original
    overwritten = scheduler.run_now(date(2026, 7, 1), overwrite=True)
    assert overwritten.status == "completed"
    assert reports.get("2026-07-01") is not None


def test_start_stop_are_idempotent_and_next_run_is_calculated(tmp_path) -> None:
    scheduler, _ = _scheduler(tmp_path)
    fixed = datetime(2026, 7, 1, 10, 30, tzinfo=timezone.utc)
    assert scheduler.next_run_time(fixed).isoformat().startswith("2026-07-01T06:00")
    assert scheduler.start().running is True
    assert scheduler.start().running is True
    assert scheduler.status().next_run_at is not None
    assert scheduler.stop().running is False
    assert scheduler.stop().running is False


def test_scheduler_records_append_only_history(tmp_path) -> None:
    scheduler, _ = _scheduler(tmp_path)
    scheduler.run_now(date(2026, 7, 1))
    scheduler.run_now(date(2026, 7, 2))
    assert len(scheduler.history()) == 2
    lines = (tmp_path / "history.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2


def test_scheduler_captures_errors_without_crashing(tmp_path) -> None:
    class _FailingReports:
        reports_dir = tmp_path / "daily"
        def get(self, report_date): return None
        def generate(self, report_date, overwrite=False): raise RuntimeError("synthetic report failure")

    scheduler = DailyReportScheduler(
        _FailingReports(),
        DailyReportSchedulerConfig(max_errors_before_pause=1, history_path=str(tmp_path / "history.jsonl")),
    )
    result = scheduler.run_now(date(2026, 7, 1))
    assert result.status == "failed"
    assert "synthetic" in result.error
    assert scheduler.status().paused is True
    assert scheduler.status().error_count == 1


def test_scheduler_api_openapi_and_dashboard(tmp_path, monkeypatch) -> None:
    import core.daily_report_scheduler as module

    scheduler, _ = _scheduler(tmp_path)
    monkeypatch.setattr(module, "_GLOBAL_SCHEDULER", scheduler)
    app.dependency_overrides[get_daily_report_scheduler] = lambda: scheduler
    try:
        client = TestClient(app)
        paths = client.get("/openapi.json").json()["paths"]
        for path in (
            "/reports/scheduler/status", "/reports/scheduler/start",
            "/reports/scheduler/stop", "/reports/scheduler/run-now",
            "/reports/scheduler/history",
        ):
            assert path in paths
            assert "reports" in next(iter(paths[path].values()))["tags"]
        run = client.post("/reports/scheduler/run-now", json={"report_date": "2026-07-01"}).json()
        assert run["status"] == "completed"
        assert client.get("/reports/scheduler/history").json()
        assert client.post("/reports/scheduler/start").json()["running"] is True
        overview = client.get("/dashboard/overview").json()
        assert overview["daily_report_scheduler_running"] is True
        assert overview["scheduled_reporting_ready"] is True
        assert client.post("/reports/scheduler/stop").json()["running"] is False
    finally:
        scheduler.stop()
        app.dependency_overrides.clear()
        module.reset_global_daily_report_scheduler()
