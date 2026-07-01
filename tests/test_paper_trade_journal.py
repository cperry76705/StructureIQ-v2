import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app, get_paper_brokerage, get_paper_trade_journal
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
    journal = PaperTradeJournal(broker, lifecycle, tmp_path / "paper.jsonl")
    return broker, lifecycle, journal


def _request(**overrides):
    values = dict(
        symbol="BTC-USD", timeframe="5m", higher_timeframe="1h",
        action="buy", setup="liquidity_sweep_reversal_long",
        strategy="liquidity_sweep_reversal", entry_price=100,
        stop_loss=98, target=106,
        metadata={
            "setup_quality": {"score": 88},
            "score_summary": {"trade_quality_score": 82},
            "execution_intelligence": {"execution_grade": "B"},
            "confidence_calibration": {"calibrated_confidence": 72},
            "symbol_profile": {"market_character": "trending"},
            "adaptive_strategy_router": {"routing_alignment": "aligned"},
            "strategy_rating": {"grade": "B"}, "setup_rating": {"grade": "B+"},
        },
    )
    values.update(overrides)
    return PaperOpenRequest(**values)


def test_journal_initializes_empty(tmp_path) -> None:
    _, _, journal = _services(tmp_path)
    assert journal.entries() == ()
    assert journal.summary().total_journaled_trades == 0


def test_open_and_close_are_automatically_journaled(tmp_path) -> None:
    broker, _, journal = _services(tmp_path)
    trade = broker.open_position(_request())
    opened = journal.get_trade(trade.trade_id)
    assert opened.status == "open"
    assert opened.account_balance_at_open == 10_000
    assert opened.setup_quality["score"] == 88
    broker.close_position(trade.trade_id, 106)
    closed = journal.get_trade(trade.trade_id)
    assert closed.status == "closed"
    assert closed.realized_r == 3
    assert closed.realized_pl == 300
    assert closed.account_balance_at_close == 10_300


def test_summary_calculates_performance_and_groups(tmp_path) -> None:
    broker, _, journal = _services(tmp_path)
    winner = broker.open_position(_request())
    broker.close_position(winner.trade_id, 104)
    loser = broker.open_position(_request(symbol="ETH-USD", setup="bullish_bos_retest", strategy="trend_continuation"))
    broker.close_position(loser.trade_id, 98)
    summary = journal.summary()
    assert summary.closed_trades == 2
    assert summary.win_rate == 50
    assert summary.total_r == 1
    assert summary.realized_pl == 98
    assert summary.best_setup == "liquidity_sweep_reversal_long"
    assert summary.worst_setup == "bullish_bos_retest"
    assert summary.average_setup_quality == 88


def test_jsonl_is_append_only_and_reload_reconstructs_latest(tmp_path) -> None:
    path = tmp_path / "paper.jsonl"
    broker, lifecycle, journal = _services(tmp_path)
    trade = broker.open_position(_request())
    broker.close_position(trade.trade_id, 106)
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert [row["event_type"] for row in rows] == ["paper_trade_opened", "paper_trade_closed"]
    reloaded = PaperTradeJournal(broker, lifecycle, path)
    assert reloaded.get_trade(trade.trade_id).realized_r == 3


def test_rebuild_from_paper_state_preserves_latest_view(tmp_path) -> None:
    broker, _, journal = _services(tmp_path)
    trade = broker.open_position(_request())
    summary = journal.rebuild_from_paper_state()
    assert summary.total_journaled_trades == 1
    assert journal.get_trade(trade.trade_id).status == "open"


def test_export_is_compact_and_daily_report_ready(tmp_path) -> None:
    broker, _, journal = _services(tmp_path)
    trade = broker.open_position(_request())
    broker.close_position(trade.trade_id, 104)
    exported = journal.export()
    assert exported.daily_report_ready is True
    assert exported.trades[0]["trade_id"] == trade.trade_id
    assert "metadata" not in exported.trades[0]


def test_paper_journal_api_and_trade_lookup(tmp_path) -> None:
    broker, _, journal = _services(tmp_path)
    app.dependency_overrides[get_paper_brokerage] = lambda: broker
    app.dependency_overrides[get_paper_trade_journal] = lambda: journal
    try:
        client = TestClient(app)
        paths = client.get("/openapi.json").json()["paths"]
        for path in (
            "/paper-journal/entries", "/paper-journal/summary",
            "/paper-journal/trade/{trade_id}",
            "/paper-journal/rebuild-from-paper-state", "/paper-journal/export",
        ):
            assert path in paths
            assert "paper-journal" in next(iter(paths[path].values()))["tags"]
        opened = client.post("/paper/open", json=_request().model_dump()).json()
        trade_id = opened["trade_id"]
        assert client.get(f"/paper-journal/trade/{trade_id}").status_code == 200
        assert client.get("/paper-journal/summary").json()["open_trades"] == 1
        assert client.post("/paper-journal/export").json()["daily_report_ready"] is True
        assert client.post("/paper-journal/rebuild-from-paper-state").status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_dashboard_includes_journal_fields(tmp_path, monkeypatch) -> None:
    import core.paper_trade_journal as journal_module

    broker, _, journal = _services(tmp_path)
    trade = broker.open_position(_request())
    monkeypatch.setattr(journal_module, "_GLOBAL_JOURNAL", journal)
    try:
        overview = TestClient(app).get("/dashboard/overview").json()
        risks = TestClient(app).get("/dashboard/risks").json()
        assert overview["journal_status"] == "available"
        assert overview["journaled_trade_count"] == 1
        assert overview["latest_journaled_trade"] == trade.trade_id
        assert overview["journal_ready_for_daily_reports"] is True
        assert risks["journal_status"] == "available"
    finally:
        journal_module.reset_global_paper_trade_journal()
