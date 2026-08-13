"""Canonical semantic classification for persisted order and trade records."""

from __future__ import annotations

from enum import Enum
from typing import Any, Iterable


class LifecycleRecordClassification(str, Enum):
    PENDING_ORDER = "PENDING_ORDER"
    EXPIRED_ORDER = "EXPIRED_ORDER"
    OPEN_TRADE = "OPEN_TRADE"
    CLOSED_TRADE = "CLOSED_TRADE"


_FILL_EVENTS = {"order_filled", "position_opened", "paper_trade_opened"}
_CLOSE_EVENTS = {"position_closed", "paper_trade_closed"}
_UNFILLED_TERMINAL_STATES = {"expired", "cancelled", "canceled", "rejected"}


def classify_lifecycle_record(
    record: Any,
    *,
    events: Iterable[Any] | None = None,
    in_brokerage_open: bool = False,
    in_brokerage_closed: bool = False,
    in_lifecycle_open: bool = False,
    in_lifecycle_closed: bool = False,
) -> LifecycleRecordClassification:
    """Classify from execution evidence; identifiers never provide trade evidence."""

    history = tuple(events if events is not None else getattr(record, "lifecycle_events", ()) or ())
    event_types = {_event_value(item, "type") for item in history}
    event_states = {_event_value(item, "state_after") for item in history}
    status = str(getattr(record, "status", "") or "").lower()

    executed = any((
        in_brokerage_open,
        in_brokerage_closed,
        in_lifecycle_open,
        in_lifecycle_closed,
        bool(getattr(record, "opened_at", None)),
        getattr(record, "actual_entry", None) is not None,
        bool(event_types & _FILL_EVENTS),
        bool(event_states & {"filled", "open", "closed"}),
    ))
    closed = any((
        in_brokerage_closed,
        in_lifecycle_closed,
        bool(getattr(record, "closed_at", None)),
        getattr(record, "exit_price", None) is not None,
        getattr(record, "realized_r", None) is not None,
        getattr(record, "realized_pl", None) is not None,
        status == "closed",
        bool(event_types & _CLOSE_EVENTS),
        "closed" in event_states,
    ))
    if executed:
        return LifecycleRecordClassification.CLOSED_TRADE if closed else LifecycleRecordClassification.OPEN_TRADE
    if status in _UNFILLED_TERMINAL_STATES or event_states & _UNFILLED_TERMINAL_STATES:
        return LifecycleRecordClassification.EXPIRED_ORDER
    return LifecycleRecordClassification.PENDING_ORDER


def has_execution_evidence(record: Any, **kwargs: Any) -> bool:
    return classify_lifecycle_record(record, **kwargs) in {
        LifecycleRecordClassification.OPEN_TRADE,
        LifecycleRecordClassification.CLOSED_TRADE,
    }


def _event_value(event: Any, field: str) -> str:
    value = event.get(field) if isinstance(event, dict) else getattr(event, field, None)
    return str(value or "").lower()
