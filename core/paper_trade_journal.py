"""Append-only paper-trade journal with reconstructed latest trade views."""

from __future__ import annotations

import hashlib
import json
import threading
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from statistics import mean
from typing import Any

from fastapi.encoders import jsonable_encoder

from core.paper_brokerage import PaperAccount, PaperBrokerageEngine, PaperTrade
from core.trade_lifecycle_manager import LifecycleEvent, TradeLifecycleManager


@dataclass(frozen=True)
class PaperTradeJournalEntry:
    journal_id: str
    trade_id: str
    source_event_id: str | None
    symbol: str
    timeframe: str
    higher_timeframe: str
    action: str
    setup: str
    strategy: str
    status: str
    opened_at: str | None
    closed_at: str | None
    planned_entry: float | None
    actual_entry: float | None
    stop_loss: float | None
    target: float | None
    planned_r: float | None
    risk_amount: float | None
    position_size: float | None
    exit_price: float | None
    realized_r: float | None
    realized_pl: float | None
    close_reason: str | None
    account_balance_at_open: float | None
    account_balance_at_close: float | None
    setup_quality: dict[str, Any] | None
    score_summary: dict[str, Any] | None
    execution_intelligence: dict[str, Any] | None
    confidence_calibration: dict[str, Any] | None
    symbol_profile: dict[str, Any] | None
    adaptive_strategy_router: dict[str, Any] | None
    strategy_rating: dict[str, Any] | None
    setup_rating: dict[str, Any] | None
    lifecycle_events: tuple[dict[str, Any], ...]
    warnings: tuple[str, ...]
    rule_violations: tuple[str, ...]
    human_readable_summary: str
    campaign_id: str | None = None


@dataclass(frozen=True)
class PaperTradeJournalSummary:
    total_journaled_trades: int
    open_trades: int
    closed_trades: int
    wins: int
    losses: int
    breakeven: int
    win_rate: float
    total_r: float
    average_r: float
    realized_pl: float
    best_trade: str | None
    worst_trade: str | None
    best_setup: str | None
    worst_setup: str | None
    best_strategy: str | None
    worst_strategy: str | None
    average_setup_quality: float | None
    most_common_warning: str | None
    rule_violation_count: int
    human_readable_summary: str


@dataclass(frozen=True)
class PaperJournalExport:
    generated_at: str
    summary: PaperTradeJournalSummary
    trades: tuple[dict[str, Any], ...]
    daily_report_ready: bool
    human_readable_summary: str


class PaperTradeJournal:
    """Observe paper/lifecycle events and append immutable latest snapshots."""

    def __init__(self, broker: PaperBrokerageEngine, lifecycle: TradeLifecycleManager, path: str | Path = "research/paper_trade_journal.jsonl") -> None:
        self.broker = broker
        self.lifecycle = lifecycle
        self.path = Path(path)
        self._lock = threading.RLock()
        self._entries: dict[str, PaperTradeJournalEntry] = {}
        self._source_index: dict[str, str] = {}
        self._load()
        broker.add_listener(self._on_brokerage_event)
        lifecycle.add_listener(self._on_lifecycle_event)

    def entries(self) -> tuple[PaperTradeJournalEntry, ...]:
        with self._lock:
            return tuple(sorted(self._entries.values(), key=lambda item: (item.opened_at or "", item.journal_id)))

    def get_trade(self, trade_id: str) -> PaperTradeJournalEntry | None:
        with self._lock:
            return self._entries.get(trade_id)

    def summary(self) -> PaperTradeJournalSummary:
        records = self.entries()
        closed = [item for item in records if item.status == "closed" and item.realized_r is not None]
        returns = [float(item.realized_r) for item in closed]
        wins = sum(value > 0 for value in returns); losses = sum(value < 0 for value in returns)
        breakeven = len(returns) - wins - losses
        qualities = [float(item.setup_quality["score"]) for item in records if item.setup_quality and isinstance(item.setup_quality.get("score"), (int, float))]
        warnings = [warning for item in records for warning in item.warnings]
        return PaperTradeJournalSummary(
            total_journaled_trades=len(records),
            open_trades=sum(item.status == "open" for item in records),
            closed_trades=len(closed), wins=wins, losses=losses, breakeven=breakeven,
            win_rate=round(wins / len(closed) * 100, 6) if closed else 0.0,
            total_r=round(sum(returns), 6),
            average_r=round(mean(returns), 6) if returns else 0.0,
            realized_pl=round(sum(float(item.realized_pl or 0) for item in closed), 6),
            best_trade=max(closed, key=lambda item: item.realized_r).trade_id if closed else None,
            worst_trade=min(closed, key=lambda item: item.realized_r).trade_id if closed else None,
            best_setup=_best_group(closed, "setup", True), worst_setup=_best_group(closed, "setup", False),
            best_strategy=_best_group(closed, "strategy", True), worst_strategy=_best_group(closed, "strategy", False),
            average_setup_quality=round(mean(qualities), 3) if qualities else None,
            most_common_warning=Counter(warnings).most_common(1)[0][0] if warnings else None,
            rule_violation_count=sum(len(item.rule_violations) for item in records),
            human_readable_summary=f"Paper journal contains {len(records)} trades, {len(closed)} closed, with {sum(returns):.2f}R total performance.",
        )

    def rebuild_from_paper_state(self) -> PaperTradeJournalSummary:
        for trade in (*self.broker.open_positions(), *self.broker.closed_trades()):
            account = self.broker.account()
            self._on_brokerage_event(
                "paper_trade_closed" if trade.status == "closed" else "paper_trade_opened",
                trade,
                account,
            )
        for event in self.lifecycle.events():
            self._on_lifecycle_event(event)
        return self.summary()

    def export(self) -> PaperJournalExport:
        summary = self.summary()
        compact = tuple(
            {
                "trade_id": item.trade_id, "symbol": item.symbol,
                "timeframe": item.timeframe, "setup": item.setup,
                "strategy": item.strategy, "status": item.status,
                "realized_r": item.realized_r, "realized_pl": item.realized_pl,
                "opened_at": item.opened_at, "closed_at": item.closed_at,
                "warnings": list(item.warnings),
            }
            for item in self.entries()
        )
        return PaperJournalExport(
            generated_at=_now(), summary=summary, trades=compact,
            daily_report_ready=summary.total_journaled_trades > 0,
            human_readable_summary="Compact paper-journal export is ready for future daily reporting." if compact else "No paper trades are available to export.",
        )

    def _on_brokerage_event(self, event_type: str, trade: PaperTrade, account: PaperAccount) -> None:
        with self._lock:
            existing_key = self._source_index.get(trade.source_event_id or "")
            existing = self._entries.get(trade.trade_id) or (self._entries.get(existing_key) if existing_key else None)
            lifecycle_history = existing.lifecycle_events if existing else ()
            warnings = existing.warnings if existing else ()
            violations = existing.rule_violations if existing else ()
            metadata = trade.metadata or {}
            if event_type == "paper_trade_opened":
                campaign_id = _current_campaign_id()
                entry = PaperTradeJournalEntry(
                    journal_id=_journal_id(trade.trade_id), trade_id=trade.trade_id,
                    source_event_id=trade.source_event_id, symbol=trade.symbol,
                    timeframe=trade.timeframe, higher_timeframe=trade.higher_timeframe,
                    action=trade.action, setup=trade.setup, strategy=trade.strategy,
                    status="open", opened_at=trade.opened_at, closed_at=None,
                    planned_entry=trade.entry_price, actual_entry=trade.entry_price,
                    stop_loss=trade.stop_loss, target=trade.target, planned_r=trade.target_r,
                    risk_amount=trade.risk_amount, position_size=trade.position_size,
                    exit_price=None, realized_r=None, realized_pl=None, close_reason=None,
                    account_balance_at_open=account.balance, account_balance_at_close=None,
                    setup_quality=_dict(metadata.get("setup_quality")), score_summary=_dict(metadata.get("score_summary")),
                    execution_intelligence=_dict(metadata.get("execution_intelligence")), confidence_calibration=_dict(metadata.get("confidence_calibration")),
                    symbol_profile=_dict(metadata.get("symbol_profile")), adaptive_strategy_router=_dict(metadata.get("adaptive_strategy_router")),
                    strategy_rating=_dict(metadata.get("strategy_rating")), setup_rating=_dict(metadata.get("setup_rating")),
                    lifecycle_events=lifecycle_history, warnings=warnings, rule_violations=violations,
                    human_readable_summary=f"Paper trade opened from {trade.symbol} {trade.timeframe} {trade.setup} setup.",
                    campaign_id=campaign_id,
                )
                if existing_key and existing_key != trade.trade_id:
                    self._entries.pop(existing_key, None)
            else:
                if existing is None:
                    self._on_brokerage_event("paper_trade_opened", replace(trade, status="open", closed_at=None, exit_price=None, realized_r=None, realized_pl=None), account)
                    existing = self._entries[trade.trade_id]
                reason = _close_reason(existing.lifecycle_events)
                entry = replace(
                    existing, status="closed", closed_at=trade.closed_at,
                    exit_price=trade.exit_price, realized_r=trade.realized_r,
                    realized_pl=trade.realized_pl, close_reason=reason,
                    account_balance_at_close=account.balance,
                    human_readable_summary=f"Paper trade closed at {trade.exit_price} for {trade.realized_r:.2f}R and {trade.realized_pl:.2f} P/L.",
                )
            self._entries[trade.trade_id] = entry
            if trade.source_event_id:
                self._source_index[trade.source_event_id] = trade.trade_id
            self._append(event_type, entry)

    def _on_lifecycle_event(self, event: LifecycleEvent) -> None:
        with self._lock:
            key = event.trade_id or self._source_index.get(event.source_event_id or "") or f"lifecycle:{event.source_event_id}"
            existing = self._entries.get(key)
            event_payload = jsonable_encoder(event)
            if existing is None:
                existing = PaperTradeJournalEntry(
                    journal_id=_journal_id(key), trade_id=key,
                    source_event_id=event.source_event_id, symbol=event.symbol,
                    timeframe=event.timeframe, higher_timeframe="", action="",
                    setup="", strategy="", status=event.state_after,
                    opened_at=None, closed_at=None, planned_entry=None,
                    actual_entry=None, stop_loss=None, target=None, planned_r=None,
                    risk_amount=None, position_size=None, exit_price=None,
                    realized_r=None, realized_pl=None, close_reason=None,
                    account_balance_at_open=None, account_balance_at_close=None,
                    setup_quality=None, score_summary=None, execution_intelligence=None,
                    confidence_calibration=None, symbol_profile=None,
                    adaptive_strategy_router=None, strategy_rating=None, setup_rating=None,
                    lifecycle_events=(), warnings=(), rule_violations=(),
                    human_readable_summary=f"Lifecycle record is {event.state_after}: {event.message}",
                    campaign_id=_current_campaign_id(),
                )
                if event.source_event_id:
                    self._source_index[event.source_event_id] = key
            warnings = list(existing.warnings); violations = list(existing.rule_violations)
            if event.metadata.get("same_candle_ambiguous"):
                warnings.append("Stop and target were touched in the same candle; stop-first handling was used.")
            if event.state_after in {"rejected", "expired"}:
                warnings.append(event.message)
            if event.state_after == "rejected":
                violations.append(event.message)
            updated = replace(
                existing, status=event.state_after if event.state_after in {"rejected", "expired", "closed"} else existing.status,
                lifecycle_events=(*existing.lifecycle_events, event_payload),
                warnings=tuple(dict.fromkeys(warnings)),
                rule_violations=tuple(dict.fromkeys(violations)),
            )
            self._entries[key] = updated
            self._append("lifecycle_event", updated)

    def _append(self, event_type: str, entry: PaperTradeJournalEntry) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"event_type": event_type, "recorded_at": _now(), "entry": jsonable_encoder(entry)}
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(payload, separators=(",", ":")))
            stream.write("\n")

    def _load(self) -> None:
        if not self.path.exists():
            return
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                payload = json.loads(line)
                raw = payload["entry"]
                raw["lifecycle_events"] = tuple(raw.get("lifecycle_events", ()))
                raw["warnings"] = tuple(raw.get("warnings", ()))
                raw["rule_violations"] = tuple(raw.get("rule_violations", ()))
                raw.setdefault("campaign_id", None)
                entry = PaperTradeJournalEntry(**raw)
                self._entries[entry.trade_id] = entry
                if entry.source_event_id:
                    self._source_index[entry.source_event_id] = entry.trade_id
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                continue


def _best_group(records, field: str, best: bool) -> str | None:
    grouped: dict[str, list[float]] = defaultdict(list)
    for item in records:
        grouped[getattr(item, field)].append(float(item.realized_r))
    if not grouped:
        return None
    averages = {name: mean(values) for name, values in grouped.items()}
    return (max if best else min)(averages, key=averages.get)


def _dict(value: Any) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None


def _close_reason(events: tuple[dict[str, Any], ...]) -> str:
    types = [item.get("type") for item in events]
    if "target_hit" in types:
        return "target_hit"
    if "stop_hit" in types:
        return "stop_hit"
    return "manual_close"


def _journal_id(trade_id: str) -> str:
    return hashlib.sha256(f"journal:{trade_id}".encode()).hexdigest()[:24]


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _current_campaign_id() -> str | None:
    try:
        from core.validation_campaigns import get_global_validation_campaign_manager
        campaign = get_global_validation_campaign_manager().current()
        return campaign.campaign_id if campaign else None
    except Exception:
        return None


_GLOBAL_JOURNAL: PaperTradeJournal | None = None
_GLOBAL_LOCK = threading.RLock()


def get_global_paper_trade_journal(broker: PaperBrokerageEngine, lifecycle: TradeLifecycleManager) -> PaperTradeJournal:
    global _GLOBAL_JOURNAL
    with _GLOBAL_LOCK:
        if _GLOBAL_JOURNAL is None or _GLOBAL_JOURNAL.broker is not broker or _GLOBAL_JOURNAL.lifecycle is not lifecycle:
            _GLOBAL_JOURNAL = PaperTradeJournal(broker, lifecycle)
        return _GLOBAL_JOURNAL


def current_paper_trade_journal() -> PaperTradeJournal | None:
    with _GLOBAL_LOCK:
        return _GLOBAL_JOURNAL


def reset_global_paper_trade_journal() -> None:
    global _GLOBAL_JOURNAL
    with _GLOBAL_LOCK:
        _GLOBAL_JOURNAL = None
