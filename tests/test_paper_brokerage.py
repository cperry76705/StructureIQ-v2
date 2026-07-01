from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.main import app, get_live_market_monitor, get_paper_brokerage
from core.live_market_monitor import LiveMarketMonitor, MonitorConfig
from core.market_data import Candle
from core.paper_brokerage import (
    PaperAccountConfig,
    PaperBrokerageEngine,
    PaperBrokerageError,
    PaperOpenRequest,
)


def _request(**overrides):
    values = dict(
        symbol="BTC-USD", timeframe="5m", higher_timeframe="1h",
        action="buy", setup="liquidity_sweep_reversal_long",
        strategy="liquidity_sweep_reversal", entry_price=100.0,
        stop_loss=98.0, target=106.0,
    )
    values.update(overrides)
    return PaperOpenRequest(**values)


def test_account_initializes_and_resets() -> None:
    broker = PaperBrokerageEngine()
    assert broker.account().balance == 10_000
    assert broker.account().equity == 10_000
    broker.open_position(_request())
    assert broker.reset().open_positions_count == 0


def test_valid_buy_position_size_and_winning_close() -> None:
    broker = PaperBrokerageEngine()
    trade = broker.open_position(_request())
    assert trade.risk_amount == 100
    assert trade.position_size == 50
    assert trade.target_r == 3
    closed = broker.close_position(trade.trade_id, 106)
    assert closed.realized_r == 3
    assert closed.realized_pl == 300
    assert broker.account().balance == 10_300
    assert broker.performance().total_r == 3


def test_valid_sell_and_losing_close() -> None:
    broker = PaperBrokerageEngine()
    trade = broker.open_position(_request(
        symbol="EUR-USD", action="sell", setup="bearish_bos_retest",
        entry_price=1.1, stop_loss=1.102, target=1.096,
    ))
    assert trade.position_size == pytest.approx(50_000)
    closed = broker.close_position(trade.trade_id, 1.102)
    assert closed.realized_r == pytest.approx(-1)
    assert closed.realized_pl == pytest.approx(-100)
    assert broker.account().balance == pytest.approx(9_900)


@pytest.mark.parametrize("trade_request", [
    _request(stop_loss=101),
    _request(action="sell", stop_loss=99, target=101),
])
def test_invalid_stop_geometry_is_rejected(trade_request) -> None:
    with pytest.raises(PaperBrokerageError):
        PaperBrokerageEngine().open_position(trade_request)


def test_duplicate_and_max_position_rules() -> None:
    broker = PaperBrokerageEngine(PaperAccountConfig(max_open_positions=2))
    broker.open_position(_request())
    with pytest.raises(PaperBrokerageError, match="duplicate"):
        broker.open_position(_request(setup="bullish_bos_retest"))
    broker.open_position(_request(symbol="ETH-USD"))
    with pytest.raises(PaperBrokerageError, match="maximum"):
        broker.open_position(_request(symbol="EUR-USD", entry_price=1.1, stop_loss=1.09, target=1.12))


def test_risk_percent_maximum_is_enforced() -> None:
    broker = PaperBrokerageEngine()
    with pytest.raises(PaperBrokerageError, match="exceeds"):
        broker.open_position(_request(risk_per_trade_percent=2.1))


def test_daily_loss_and_profit_locks_block_new_trades() -> None:
    loss_broker = PaperBrokerageEngine(PaperAccountConfig(max_daily_loss_percent=1))
    loss = loss_broker.open_position(_request())
    loss_broker.close_position(loss.trade_id, 98)
    with pytest.raises(PaperBrokerageError, match="daily_loss_limit"):
        loss_broker.open_position(_request(symbol="ETH-USD"))

    profit_broker = PaperBrokerageEngine(PaperAccountConfig(max_daily_profit_lock_percent=1))
    winner = profit_broker.open_position(_request())
    profit_broker.close_position(winner.trade_id, 102)
    with pytest.raises(PaperBrokerageError, match="daily_profit_lock"):
        profit_broker.open_position(_request(symbol="ETH-USD"))


def test_mark_to_market_updates_equity() -> None:
    broker = PaperBrokerageEngine()
    broker.open_position(_request())
    account = broker.account({"BTC-USD": 101})
    assert account.unrealized_pl == 50
    assert account.equity == 10_050
    assert broker.open_positions()[0].unrealized_r == 0.5


class _Provider:
    def get_candles(self, symbol, timeframe, lookback):
        return [Candle(i, 100, 101, 99, 100, 1000) for i in range(lookback)]


class _Analysis:
    def analyze(self, request):
        return SimpleNamespace(
            symbol=request.symbol, action="buy", setup="liquidity_sweep_reversal_long",
            confidence=7.8, entry_zone="100-100", stop_loss="98", target="106",
            reasons=["Synthetic candidate."],
            setup_plan=SimpleNamespace(setup_status="confirmed"),
            trader_analysis=SimpleNamespace(trade_plan=SimpleNamespace(status="actionable")),
            strategy=SimpleNamespace(preferred_strategy="liquidity_sweep_reversal"),
            setup_quality={"score": 88}, score_summary={"trade_quality_score": 82},
            execution_intelligence={"execution_grade": "B"},
        )


def _monitor(tmp_path: Path):
    return LiveMarketMonitor(
        _Provider(),
        MonitorConfig(symbols=["BTC-USD"], timeframes=["5m"], lookback=50, write_events=False),
        analysis_engine_factory=lambda provider: _Analysis(),
    )


def test_open_from_monitor_event_marks_candidate(tmp_path) -> None:
    broker = PaperBrokerageEngine()
    monitor = _monitor(tmp_path)
    event = monitor.run_once().events[0]
    trade = broker.open_monitor_event(event)
    monitor.mark_paper_trade_created(event.event_id)
    assert trade.source_event_id == event.event_id
    assert monitor.find_event(event.event_id).paper_trade_created is True


def test_paper_api_open_close_monitor_and_dashboard(tmp_path) -> None:
    broker = PaperBrokerageEngine()
    monitor = _monitor(tmp_path)
    event = monitor.run_once().events[0]
    app.dependency_overrides[get_paper_brokerage] = lambda: broker
    app.dependency_overrides[get_live_market_monitor] = lambda: monitor
    try:
        client = TestClient(app)
        paths = client.get("/openapi.json").json()["paths"]
        for path in ("/paper/account", "/paper/reset", "/paper/open", "/paper/close", "/paper/open-positions", "/paper/closed-trades", "/paper/performance"):
            assert path in paths
            assert "paper" in next(iter(paths[path].values()))["tags"]
        opened = client.post("/paper/open", json={"event_id": event.event_id}).json()
        assert opened["status"] == "open"
        assert monitor.find_event(event.event_id).paper_trade_created is True
        account = client.get("/paper/account").json()
        assert account["open_positions_count"] == 1
        closed = client.post("/paper/close", json={"trade_id": opened["trade_id"], "exit_price": 106}).json()
        assert closed["realized_r"] == 3
        assert client.get("/paper/performance").json()["total_r"] == 3
    finally:
        app.dependency_overrides.clear()


def test_dashboard_includes_paper_account_fields(monkeypatch) -> None:
    import core.paper_brokerage as paper_module

    broker = PaperBrokerageEngine()
    broker.open_position(_request())
    monkeypatch.setattr(paper_module, "_GLOBAL_PAPER_BROKER", broker)
    try:
        overview = TestClient(app).get("/dashboard/overview").json()
        readiness = TestClient(app).get("/dashboard/readiness").json()
        assert overview["paper_account_balance"] == 10_000
        assert overview["paper_open_positions_count"] == 1
        assert overview["paper_trading_enabled"] is False
        assert readiness["paper_brokerage_status"] == "available_advisory"
    finally:
        paper_module.reset_global_paper_brokerage()
