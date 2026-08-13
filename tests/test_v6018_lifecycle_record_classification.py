from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

from core.lifecycle_record_classification import (
    LifecycleRecordClassification as Classification,
    classify_lifecycle_record,
)
from core.paper_recovery import PaperRecoveryEngine
from core.paper_trade_journal import PaperTradeJournalEntry


def _record(**changes):
    values = dict(
        journal_id="journal-order", trade_id="lifecycle:source-1", source_event_id="source-1",
        symbol="BTC-USD", timeframe="5m", higher_timeframe="", action="", setup="", strategy="",
        status="pending", opened_at=None, closed_at=None, planned_entry=None, actual_entry=None,
        stop_loss=None, target=None, planned_r=None, risk_amount=None, position_size=None,
        exit_price=None, realized_r=None, realized_pl=None, close_reason=None,
        account_balance_at_open=None, account_balance_at_close=None, setup_quality=None,
        score_summary=None, execution_intelligence=None, confidence_calibration=None,
        symbol_profile=None, adaptive_strategy_router=None, strategy_rating=None, setup_rating=None,
        lifecycle_events=(), warnings=(), rule_violations=(), human_readable_summary="Lifecycle order.",
        campaign_id="campaign-active",
    )
    values.update(changes)
    return PaperTradeJournalEntry(**values)


def _event(event_type, state_after):
    return {"type": event_type, "state_after": state_after}


def test_expired_unfilled_order_is_not_a_trade():
    record = _record(status="expired", lifecycle_events=(
        _event("order_created", "pending"), _event("order_expired", "expired"),
    ))
    assert classify_lifecycle_record(record) is Classification.EXPIRED_ORDER


def test_pending_unfilled_order_is_not_a_trade():
    assert classify_lifecycle_record(_record()) is Classification.PENDING_ORDER


def test_filled_open_and_closed_positions_require_execution_evidence():
    opened = _record(status="open", actual_entry=100.0, opened_at="2026-08-13T00:00:00+00:00",
                     lifecycle_events=(_event("order_filled", "filled"), _event("position_opened", "open")))
    closed = replace(opened, status="closed", closed_at="2026-08-13T01:00:00+00:00",
                     exit_price=101.0, realized_r=1.0, realized_pl=100.0,
                     lifecycle_events=(*opened.lifecycle_events, _event("position_closed", "closed")))
    assert classify_lifecycle_record(opened) is Classification.OPEN_TRADE
    assert classify_lifecycle_record(closed) is Classification.CLOSED_TRADE


def test_lifecycle_identifier_never_implies_execution():
    assert classify_lifecycle_record(_record(trade_id="lifecycle:anything")) is Classification.PENDING_ORDER


class _Broker:
    def recover_from_storage(self): pass
    def open_positions(self): return ()
    def closed_trades(self): return ()
    def account(self): return SimpleNamespace(balance=10_000.0)
    def performance(self): return SimpleNamespace(total_r=0.0)


class _Lifecycle:
    def __init__(self, events=()): self._events = tuple(events)
    def recover_from_storage(self): pass
    def pending_orders(self): return ()
    def open_trades(self): return ()
    def closed_trades(self): return ()
    def events(self): return self._events


class _Journal:
    def __init__(self, entries): self._entries = tuple(entries)
    def entries(self): return self._entries


class _Reconciliation:
    campaigns = None
    def run(self, persist=True):
        summary = SimpleNamespace(active_campaign_id="campaign-active")
        return SimpleNamespace(status="PASS", summary=summary)


def _recovery(tmp_path, entries, events=()):
    return PaperRecoveryEngine(
        broker=_Broker(), lifecycle=_Lifecycle(events), journal=_Journal(entries),
        reconciliation=_Reconciliation(), orphan_path=tmp_path / "orphans.json",
    ).run(persist_reconciliation=False)


def test_active_campaign_expired_orders_are_excluded_but_genuine_orphan_remains(tmp_path):
    expired = _record(status="expired", lifecycle_events=(_event("order_created", "pending"), _event("order_expired", "expired")))
    result = _recovery(tmp_path, (expired,))
    assert result.summary.expired_orders == 1
    assert result.summary.current_campaign_orphaned_trades == 0
    assert result.summary.active_campaign_recovery_status == "PASS"

    executed = _record(trade_id="executed-orphan", status="open", actual_entry=100.0,
                       opened_at="2026-08-13T00:00:00+00:00")
    result = _recovery(tmp_path, (expired, executed))
    assert result.summary.current_campaign_orphaned_trades == 1
    assert result.orphans[0].trade_id == "executed-orphan"


def test_legacy_orphans_do_not_contaminate_active_campaign(tmp_path):
    legacy = _record(trade_id="legacy-executed", campaign_id=None, status="closed",
                     opened_at="2026-01-01T00:00:00+00:00", closed_at="2026-01-01T01:00:00+00:00",
                     actual_entry=100.0, exit_price=101.0, realized_r=1.0, realized_pl=100.0)
    result = _recovery(tmp_path, (legacy,))
    assert result.summary.legacy_orphaned_trades == 1
    assert result.summary.active_campaign_recovery_status == "PASS"
    assert result.summary.legacy_recovery_status == "WATCHLIST"


def test_classification_survives_persisted_event_hydration():
    hydrated = _record(status="expired", lifecycle_events=(
        {"type": "order_created", "state_after": "pending"},
        {"type": "order_expired", "state_after": "expired"},
    ))
    assert classify_lifecycle_record(hydrated) is Classification.EXPIRED_ORDER


def test_test_fixture_exclusions_remain_intact(tmp_path):
    # Explicit fixture flags continue to prevent synthetic rows from entering recovery.
    fixture = _record(test_fixture=True, synthetic_recovery_test=True, status="open",
                      actual_entry=100.0, opened_at="2026-08-13T00:00:00+00:00")
    result = _recovery(tmp_path, (fixture,))
    assert result.summary.orphaned_trades == 0
    assert result.summary.excluded_test_fixtures >= 1
