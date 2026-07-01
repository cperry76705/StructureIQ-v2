from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.main import app, get_trade_lifecycle_manager
from core.live_market_monitor import LiveMarketMonitor, MonitorConfig
from core.market_data import Candle
from core.paper_brokerage import PaperBrokerageEngine
from core.trade_lifecycle_manager import (
    ApproveCandidateRequest,
    LifecycleConfig,
    LifecycleError,
    OrderType,
    RejectCandidateRequest,
    TradeLifecycleManager,
)


class _Provider:
    def __init__(self):
        self.candle = Candle(100, 99, 99.5, 98.5, 99, 1000)

    def get_candles(self, symbol, timeframe, lookback):
        del symbol, timeframe
        return [self.candle for _ in range(lookback)]


class _Analysis:
    def __init__(self, action="buy", entry="100", stop="98", target="106"):
        self.action, self.entry, self.stop, self.target = action, entry, stop, target

    def analyze(self, request):
        return SimpleNamespace(
            symbol=request.symbol, action=self.action,
            setup="liquidity_sweep_reversal_long" if self.action == "buy" else "liquidity_sweep_reversal_short",
            confidence=7.8, entry_zone=self.entry, stop_loss=self.stop,
            target=self.target, reasons=["Synthetic lifecycle candidate."],
            setup_plan=SimpleNamespace(setup_status="confirmed"),
            trader_analysis=SimpleNamespace(trade_plan=SimpleNamespace(status="actionable")),
            strategy=SimpleNamespace(preferred_strategy="liquidity_sweep_reversal"),
            setup_quality={"score": 88}, score_summary={"trade_quality_score": 82},
            execution_intelligence={"execution_grade": "B"},
        )


def _manager(*, action="buy", entry="100", stop="98", target="106", config=None):
    provider = _Provider()
    monitor = LiveMarketMonitor(
        provider, MonitorConfig(symbols=["BTC-USD"], timeframes=["5m"], lookback=50, write_events=False),
        analysis_engine_factory=lambda source: _Analysis(action, entry, stop, target),
    )
    event = monitor.run_once().events[0]
    broker = PaperBrokerageEngine()
    manager = TradeLifecycleManager(provider, monitor, broker, config)
    return manager, provider, monitor, broker, event


def test_candidate_approval_creates_pending_order_and_event() -> None:
    manager, _, _, _, event = _manager()
    order = manager.approve_candidate(ApproveCandidateRequest(event_id=event.event_id))
    assert order.status == "pending"
    assert manager.status().pending_orders_count == 1
    assert manager.events()[0].state_before == "candidate"
    assert manager.events()[0].state_after == "pending"


def test_candidate_rejection_records_rejected_state() -> None:
    manager, _, _, _, event = _manager()
    lifecycle_event = manager.reject_candidate(RejectCandidateRequest(event_id=event.event_id))
    assert lifecycle_event.state_after == "rejected"
    assert manager.status().rejected_candidates_count == 1


def test_invalid_candidate_is_rejected_and_recorded() -> None:
    manager, _, _, _, event = _manager(stop="101")
    with pytest.raises(LifecycleError, match="invalid"):
        manager.approve_candidate(ApproveCandidateRequest(event_id=event.event_id))
    assert manager.status().rejected_candidates_count == 1
    assert manager.events()[-1].state_after == "rejected"


def test_market_approval_opens_paper_trade_and_blocks_duplicate() -> None:
    manager, _, monitor, _, event = _manager()
    order = manager.approve_candidate(ApproveCandidateRequest(event_id=event.event_id, order_type=OrderType.MARKET))
    assert order.status == "open"
    assert order.trade_id is not None
    assert manager.status().lifecycle_open_trades_count == 1
    assert monitor.find_event(event.event_id).paper_trade_created is True
    with pytest.raises(LifecycleError, match="already"):
        manager.approve_candidate(ApproveCandidateRequest(event_id=event.event_id))


def test_limit_order_waits_then_fills_when_entry_touched() -> None:
    manager, provider, _, _, event = _manager()
    manager.approve_candidate(ApproveCandidateRequest(event_id=event.event_id))
    first = manager.run_once()
    assert first.orders_filled == 0
    assert manager.status().pending_orders_count == 1
    provider.candle = Candle(101, 99, 101, 99, 100.5, 1000)
    second = manager.run_once()
    assert second.orders_filled == 1
    assert manager.status().lifecycle_open_trades_count == 1


def test_pending_order_expires_after_configured_candles() -> None:
    manager, _, _, _, event = _manager(config=LifecycleConfig(pending_order_expiration_candles=2))
    manager.approve_candidate(ApproveCandidateRequest(event_id=event.event_id))
    assert manager.run_once().orders_expired == 0
    assert manager.run_once().orders_expired == 1
    assert manager.status().expired_orders_count == 1


def test_buy_target_and_stop_closure() -> None:
    target_manager, provider, _, broker, event = _manager()
    target_manager.approve_candidate(ApproveCandidateRequest(event_id=event.event_id, order_type="market"))
    provider.candle = Candle(101, 101, 106, 100, 105, 1000)
    assert target_manager.run_once().trades_closed == 1
    assert broker.closed_trades()[0].realized_r == 3

    stop_manager, provider2, _, broker2, event2 = _manager()
    stop_manager.approve_candidate(ApproveCandidateRequest(event_id=event2.event_id, order_type="market"))
    provider2.candle = Candle(102, 100, 101, 98, 99, 1000)
    assert stop_manager.run_once().trades_closed == 1
    assert broker2.closed_trades()[0].realized_r == -1


def test_sell_target_and_stop_closure() -> None:
    manager, provider, _, broker, event = _manager(action="sell", entry="100", stop="102", target="94")
    manager.approve_candidate(ApproveCandidateRequest(event_id=event.event_id, order_type="market"))
    provider.candle = Candle(103, 99, 100, 94, 95, 1000)
    assert manager.run_once().trades_closed == 1
    assert broker.closed_trades()[0].realized_r == 3


def test_same_candle_ambiguity_uses_conservative_stop_first() -> None:
    manager, provider, _, broker, event = _manager()
    manager.approve_candidate(ApproveCandidateRequest(event_id=event.event_id, order_type="market"))
    provider.candle = Candle(104, 100, 106, 98, 103, 1000)
    result = manager.run_once()
    assert result.ambiguous_exits == 1
    assert broker.closed_trades()[0].realized_r == -1
    assert manager.status().ambiguous_exit_count == 1
    assert any(item.metadata.get("same_candle_ambiguous") for item in manager.events())


def test_lifecycle_api_openapi_and_dashboard(monkeypatch) -> None:
    import core.trade_lifecycle_manager as lifecycle_module

    manager, _, _, _, event = _manager()
    monkeypatch.setattr(lifecycle_module, "_GLOBAL_MANAGER", manager)
    app.dependency_overrides[get_trade_lifecycle_manager] = lambda: manager
    try:
        client = TestClient(app)
        paths = client.get("/openapi.json").json()["paths"]
        lifecycle_paths = (
            "/lifecycle/status", "/lifecycle/run-once", "/lifecycle/approve-candidate",
            "/lifecycle/reject-candidate", "/lifecycle/cancel-order", "/lifecycle/events",
            "/lifecycle/pending-orders", "/lifecycle/open-trades", "/lifecycle/closed-trades",
        )
        for path in lifecycle_paths:
            assert path in paths
            assert "lifecycle" in next(iter(paths[path].values()))["tags"]
        approved = client.post("/lifecycle/approve-candidate", json={"event_id": event.event_id}).json()
        assert approved["status"] == "pending"
        assert client.get("/lifecycle/status").json()["pending_orders_count"] == 1
        overview = client.get("/dashboard/overview").json()
        assert overview["pending_orders_count"] == 1
        assert overview["lifecycle_status"] == "disabled_advisory"
    finally:
        app.dependency_overrides.clear()
        lifecycle_module.reset_global_trade_lifecycle_manager()
