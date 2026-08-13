from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app, get_execution_capture_engine
from core.execution_capture import ExecutionCaptureEngine
from core.market_data import Candle


CAMPAIGN = "campaign-active"


def _ts(minutes: int) -> int:
    return int(datetime(2026, 8, 13, 12, minutes, tzinfo=timezone.utc).timestamp())


def _iso(minutes: int) -> str:
    return datetime(2026, 8, 13, 12, minutes, tzinfo=timezone.utc).isoformat()


def _event(kind: str, minute: int, state: str):
    return {"type": kind, "timestamp": _iso(minute), "state_after": state}


def _order(order_id="o1", source="s1", symbol="BTC-USD", status="expired", trade_id=None, strategy="breakout", setup="bos"):
    return SimpleNamespace(order_id=order_id, source_event_id=source, trade_id=trade_id, symbol=symbol,
        timeframe="5m", strategy=strategy, setup=setup, action="buy", order_type="limit_retest",
        entry_price=100.0, stop_loss=99.0, target=103.0, created_at=_iso(0), status=status)


def _journal(source="s1", trade_id="lifecycle:s1", campaign=CAMPAIGN, status="expired", events=None, **extra):
    values = dict(source_event_id=source, trade_id=trade_id, campaign_id=campaign, symbol="BTC-USD", status=status,
        opened_at=None, closed_at=None, actual_entry=None, exit_price=None, realized_r=None, realized_pl=None,
        stop_loss=99.0, target=103.0, lifecycle_events=events or (_event("order_created", 0, "pending"), _event("order_expired", 10, "expired")),
        test_fixture=False, synthetic_recovery_test=False, exclude_from_performance=False,
        exclude_from_campaign_metrics=False, exclude_from_research=False)
    values.update(extra)
    return SimpleNamespace(**values)


class _Lifecycle:
    def __init__(self, orders): self._orders = tuple(orders)
    def orders(self): return self._orders


class _Journal:
    def __init__(self, entries): self._entries = tuple(entries)
    def entries(self): return self._entries


class _Provider:
    def __init__(self, candles): self.candles = candles
    def get_candles(self, symbol, timeframe, lookback): return list(self.candles.get(symbol, ()))


class _Opportunity:
    def report(self, campaign_id=None):
        symbol = SimpleNamespace(symbol="BTC-USD", raw_setups=10, qualified_setups=5, candidates_created=4)
        return SimpleNamespace(summary=SimpleNamespace(raw_setups=10, qualified_setups=5, candidates_created=4, approved_candidates=2), by_symbol=(symbol,))


class _Reconciliation:
    def run(self, **kwargs):
        discrepancy = SimpleNamespace(trade_id="t1", message="Closed trade missing from durable brokerage state.")
        return SimpleNamespace(discrepancies=(discrepancy,))


def _engine(orders, entries, candles=()):
    return ExecutionCaptureEngine(lifecycle=_Lifecycle(orders), journal=_Journal(entries), opportunity=_Opportunity(),
        reconciliation=_Reconciliation(), provider=_Provider({"BTC-USD": candles, "EUR-USD": candles}))


def test_filled_and_expired_orders_and_zero_safe_rates():
    filled_events = (_event("order_created", 0, "pending"), _event("order_filled", 2, "filled"), _event("position_opened", 2, "open"))
    filled = _journal(trade_id="t1", status="open", events=filled_events, opened_at=_iso(2), actual_entry=100.0)
    report = _engine((_order(status="open", trade_id="t1"), _order("o2", "s2")), (filled, _journal("s2", "lifecycle:s2"))).report(campaign_id=CAMPAIGN)
    assert report["summary"]["orders_filled"] == 1
    assert report["summary"]["orders_unfilled"] == 1
    assert report["summary"]["order_fill_rate"] == 50.0
    empty = _engine((), ()).report(campaign_id=CAMPAIGN)
    assert empty["summary"]["order_fill_rate"] is None


def test_entry_never_reached_touched_before_and_only_after_expiration():
    never = [Candle(_ts(i), 105, 106, 104, 105, 1) for i in (0, 5, 10, 15)]
    assert _engine((_order(),), (_journal(),), never).records(campaign_id=CAMPAIGN)[0].terminal_reason == "ENTRY_NOT_REACHED"
    before = [Candle(_ts(0), 101, 102, 100, 101, 1), Candle(_ts(5), 100, 101, 99.5, 100, 1)]
    assert _engine((_order(),), (_journal(),), before).records(campaign_id=CAMPAIGN)[0].entry_touched is True
    after = [Candle(_ts(0), 102, 103, 101, 102, 1), Candle(_ts(15), 100, 101, 99, 100, 1)]
    row = _engine((_order(),), (_journal(),), after).records(campaign_id=CAMPAIGN)[0]
    assert row.entry_touched is False and row.entry_touched_after_expiration is True


def test_target_stop_and_ambiguous_post_order_analysis():
    target = [Candle(_ts(0), 100, 100.5, 99.5, 100, 1), Candle(_ts(5), 102, 103.2, 101, 103, 1)]
    assert _engine((_order(),), (_journal(),), target).records(campaign_id=CAMPAIGN)[0].first_exit_event == "TARGET"
    stop = [Candle(_ts(0), 100, 100.5, 99.5, 100, 1), Candle(_ts(5), 99, 99.5, 98.8, 99, 1)]
    assert _engine((_order(),), (_journal(),), stop).records(campaign_id=CAMPAIGN)[0].first_exit_event == "STOP"
    both = [Candle(_ts(0), 100, 103.5, 98.5, 100, 1)]
    assert _engine((_order(),), (_journal(),), both).records(campaign_id=CAMPAIGN)[0].first_exit_event == "AMBIGUOUS_INTRABAR"


def test_counterfactuals_are_read_only_and_missing_data_is_explicit():
    journal = _journal()
    before = deepcopy(journal.__dict__)
    report = _engine((_order(),), (journal,), ()).report(campaign_id=CAMPAIGN)
    assert all(row["status"] == "INSUFFICIENT_DATA" for row in report["counterfactuals"])
    assert journal.__dict__ == before


def test_campaign_fixture_legacy_and_research_exclusions():
    entries = (_journal(), _journal("s2", campaign="other"), _journal("s3", campaign=None),
        _journal("s4", test_fixture=True), _journal("s5", exclude_from_research=True))
    orders = tuple(_order(f"o{i}", f"s{i}") for i in range(1, 6))
    records = _engine(orders, entries).records(campaign_id=CAMPAIGN)
    assert [row.source_event_id for row in records] == ["s1"]


def test_quarantined_trade_is_excluded():
    engine = ExecutionCaptureEngine(lifecycle=_Lifecycle((_order(),)), journal=_Journal((_journal(),)),
        opportunity=_Opportunity(), provider=_Provider({}), excluded_trade_ids={"lifecycle:s1"})
    assert engine.records(campaign_id=CAMPAIGN) == ()


def test_crypto_forex_symbol_strategy_and_setup_aggregation():
    orders = (_order(), _order("o2", "s2", symbol="EUR-USD", strategy="reversal", setup="sweep"))
    entries = (_journal(), _journal("s2", "lifecycle:s2", symbol="EUR-USD"))
    report = _engine(orders, entries).report(campaign_id=CAMPAIGN)
    assert {r["asset_class"] for r in report["by_asset_class"]} == {"CRYPTO", "FOREX"}
    assert {r["symbol"] for r in report["by_symbol"]} == {"BTC-USD", "EUR-USD"}
    assert {r["strategy"] for r in report["by_strategy"]} == {"breakout", "reversal"}
    assert {r["setup"] for r in report["by_setup"]} == {"bos", "sweep"}


def test_executed_trade_linkage_and_discrepancy_are_preserved():
    events = (_event("order_created", 0, "pending"), _event("order_filled", 1, "filled"), _event("position_opened", 1, "open"), _event("position_closed", 5, "closed"))
    trade = _journal(trade_id="t1", status="closed", events=events, opened_at=_iso(1), closed_at=_iso(5),
        actual_entry=100.0, exit_price=103.0, realized_r=3.0, realized_pl=300.0)
    audit = _engine((_order(status="closed", trade_id="t1"),), (trade,)).report(campaign_id=CAMPAIGN)["trades"][0]
    assert audit["linkage_complete"] is True
    assert audit["realized_r"] == 3.0
    assert audit["reconciliation_discrepancies"]


def test_api_surface_uses_read_only_engine():
    engine = _engine((_order(),), (_journal(),))
    app.dependency_overrides[get_execution_capture_engine] = lambda: engine
    try:
        client = TestClient(app)
        assert client.get("/execution-capture/summary", params={"campaign_id": CAMPAIGN}).status_code == 200
        paths = client.get("/openapi.json").json()["paths"]
        for path in ("/execution-capture/unfilled", "/execution-capture/counterfactuals", "/execution-capture/trades"):
            assert path in paths
    finally:
        app.dependency_overrides.clear()
