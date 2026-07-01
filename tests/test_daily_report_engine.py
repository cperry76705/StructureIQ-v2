from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app, get_daily_report_engine
from core.daily_report_engine import DailyReportEngine, DailyReportError
from core.live_market_monitor import LiveMarketMonitor, MonitorConfig
from core.market_data import Candle
from core.paper_brokerage import PaperBrokerageEngine, PaperOpenRequest
from core.paper_trade_journal import PaperTradeJournal
from core.trade_lifecycle_manager import TradeLifecycleManager


class _Provider:
    def get_candles(self, symbol, timeframe, lookback):
        return [Candle(i, 100, 101, 99, 100, 1000) for i in range(lookback)]


def _services(tmp_path: Path):
    provider = _Provider()
    monitor = LiveMarketMonitor(provider, MonitorConfig(symbols=["BTC-USD"], timeframes=["5m"], lookback=50, write_events=False))
    broker = PaperBrokerageEngine()
    lifecycle = TradeLifecycleManager(provider, monitor, broker)
    journal = PaperTradeJournal(broker, lifecycle, tmp_path / "journal.jsonl")
    engine = DailyReportEngine(journal, lifecycle, broker, monitor, reports_dir=tmp_path / "reports")
    return engine, journal, broker, lifecycle, monitor


def _trade_request():
    return PaperOpenRequest(
        symbol="BTC-USD", timeframe="5m", higher_timeframe="1h",
        action="buy", setup="liquidity_sweep_reversal_long",
        strategy="liquidity_sweep_reversal", entry_price=100,
        stop_loss=98, target=106,
        metadata={"setup_quality": {"score": 90}, "score_summary": {"trade_quality_score": 86}},
    )


def test_report_engine_initializes_and_no_trades_is_controlled(tmp_path) -> None:
    engine, *_ = _services(tmp_path)
    report = engine.generate(date.today())
    assert report.status == "NO_TRADES"
    assert report.summary.closed_trades == 0
    assert engine.latest().report_id == report.report_id


def test_winning_trade_returns_pass(tmp_path) -> None:
    engine, _, broker, _, _ = _services(tmp_path)
    trade = broker.open_position(_trade_request())
    broker.close_position(trade.trade_id, 106)
    report = engine.generate(date.today())
    assert report.status == "PASS"
    assert report.summary.total_r == 3
    assert report.summary.realized_pl == 300
    assert report.setup_quality_summary is None


def test_open_risk_or_warning_returns_watchlist(tmp_path) -> None:
    engine, journal, broker, _, _ = _services(tmp_path)
    trade = broker.open_position(_trade_request())
    entry = journal.get_trade(trade.trade_id)
    journal._entries[trade.trade_id] = replace(entry, warnings=("Execution review required.",))
    report = engine.generate(date.today())
    assert report.status == "WATCHLIST"
    assert report.summary.open_trades == 1
    assert report.summary.warnings == 1


def test_rule_violation_with_closed_trade_returns_fail(tmp_path) -> None:
    engine, journal, broker, _, _ = _services(tmp_path)
    trade = broker.open_position(_trade_request())
    broker.close_position(trade.trade_id, 104)
    entry = journal.get_trade(trade.trade_id)
    journal._entries[trade.trade_id] = replace(entry, rule_violations=("Risk rule violated.",))
    report = engine.generate(date.today())
    assert report.status == "FAIL"
    assert report.summary.rule_violations == 1


def test_report_persistence_does_not_overwrite_without_permission(tmp_path) -> None:
    engine, *_ = _services(tmp_path)
    first = engine.generate("2026-07-01")
    path = tmp_path / "reports" / "2026-07-01.json"
    original = path.read_text(encoding="utf-8")
    with pytest.raises(DailyReportError, match="already exists"):
        engine.generate("2026-07-01")
    assert path.read_text(encoding="utf-8") == original
    second = engine.generate("2026-07-01", overwrite=True)
    assert second.report_id == first.report_id


def test_gpt_payload_is_compact_and_clean(tmp_path) -> None:
    engine, _, broker, _, _ = _services(tmp_path)
    trade = broker.open_position(_trade_request())
    broker.close_position(trade.trade_id, 104)
    engine.generate(date.today())
    payload = engine.export_gpt_payload(date.today())
    assert payload.status == "PASS"
    assert payload.trades[0]["trade_id"] == trade.trade_id
    assert len(payload.questions_for_review) == 3
    assert "setup_quality" not in payload.trades[0]


def test_daily_report_api_and_openapi(tmp_path) -> None:
    engine, _, _, _, _ = _services(tmp_path)
    app.dependency_overrides[get_daily_report_engine] = lambda: engine
    today = date.today().isoformat()
    try:
        client = TestClient(app)
        paths = client.get("/openapi.json").json()["paths"]
        for path in (
            "/reports/daily", "/reports/daily/generate",
            "/reports/daily/{report_date}", "/reports/daily/export-gpt-payload",
        ):
            assert path in paths
            assert "reports" in next(iter(paths[path].values()))["tags"]
        generated = client.post("/reports/daily/generate", json={"report_date": today}).json()
        assert generated["status"] == "NO_TRADES"
        assert client.get("/reports/daily").json()[0]["report_date"] == today
        assert client.get(f"/reports/daily/{today}").status_code == 200
        payload = client.post("/reports/daily/export-gpt-payload", json={"report_date": today}).json()
        assert payload["report_date"] == today
    finally:
        app.dependency_overrides.clear()


def test_dashboard_includes_latest_daily_report(tmp_path, monkeypatch) -> None:
    import core.daily_report_engine as report_module

    engine, _, broker, _, _ = _services(tmp_path)
    trade = broker.open_position(_trade_request())
    broker.close_position(trade.trade_id, 106)
    report = engine.generate(date.today())
    monkeypatch.setattr(report_module, "_GLOBAL_REPORT_ENGINE", engine)
    try:
        client = TestClient(app)
        overview = client.get("/dashboard/overview").json()
        readiness = client.get("/dashboard/readiness").json()
        risks = client.get("/dashboard/risks").json()
        assert overview["latest_daily_report_date"] == report.report_date
        assert overview["latest_daily_report_status"] == "PASS"
        assert overview["daily_report_total_r"] == 3
        assert readiness["daily_report_ready"] is True
        assert risks["latest_daily_report_status"] == "PASS"
    finally:
        report_module.reset_global_daily_report_engine()
