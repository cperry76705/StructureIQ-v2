"""Paper-only lifecycle orchestration over monitor candidates and paper brokerage."""

from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from core.backtesting import parse_price_level
from core.live_market_monitor import LiveMarketMonitor, MonitorEvent
from core.market_data import MarketDataProvider
from core.paper_brokerage import PaperBrokerageEngine, PaperBrokerageError, PaperTrade


class LifecycleError(ValueError):
    """A lifecycle transition was invalid or could not be completed safely."""


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT_RETEST = "limit_retest"
    CONFIRMATION_CLOSE = "confirmation_close"


LifecycleState = Literal[
    "candidate", "pending", "filled", "open", "breakeven_eligible",
    "trailing", "target_hit", "stop_hit", "closed", "rejected", "expired",
]


class LifecycleConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lifecycle_enabled: bool = False
    auto_open_from_monitor: bool = False
    require_manual_approval: bool = True
    pending_order_expiration_candles: int = Field(default=3, ge=1)
    allow_market_orders: bool = True
    allow_limit_orders: bool = True
    allow_confirmation_close: bool = True
    enable_breakeven_rule: bool = False
    breakeven_trigger_r: float = Field(default=1.0, gt=0)
    enable_trailing_stop_rule: bool = False
    trailing_trigger_r: float = Field(default=1.5, gt=0)
    max_lifecycle_events_in_memory: int = Field(default=1000, ge=1, le=100_000)
    durable_state: bool = False
    persistence_path: str = "research/lifecycle_state.json"


class ApproveCandidateRequest(BaseModel):
    event_id: str
    order_type: OrderType = OrderType.LIMIT_RETEST
    risk_per_trade_percent: float | None = Field(default=None, gt=0)


class RejectCandidateRequest(BaseModel):
    event_id: str
    reason: str = "Candidate rejected manually."


class CancelOrderRequest(BaseModel):
    order_id: str
    reason: str = "Pending paper order cancelled manually."


@dataclass(frozen=True)
class PendingPaperOrder:
    order_id: str
    source_event_id: str
    symbol: str
    timeframe: str
    higher_timeframe: str
    action: str
    setup: str
    strategy: str
    order_type: str
    entry_price: float
    stop_loss: float
    target: float
    created_at: str
    expires_after_candles: int
    candles_evaluated: int
    status: str
    trade_id: str | None
    risk_per_trade_percent: float | None
    metadata: dict[str, Any]


@dataclass(frozen=True)
class LifecycleEvent:
    event_id: str
    timestamp: str
    type: str
    symbol: str
    timeframe: str
    source_event_id: str | None
    trade_id: str | None
    state_before: LifecycleState
    state_after: LifecycleState
    message: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class LifecycleCycleResult:
    pending_evaluated: int
    orders_filled: int
    trades_closed: int
    orders_expired: int
    ambiguous_exits: int
    errors: tuple[str, ...]
    events: tuple[LifecycleEvent, ...]
    completed_at: str
    human_readable_summary: str


@dataclass(frozen=True)
class LifecycleStatus:
    lifecycle_enabled: bool
    auto_open_from_monitor: bool
    require_manual_approval: bool
    pending_orders_count: int
    lifecycle_open_trades_count: int
    lifecycle_closed_trades_count: int
    expired_orders_count: int
    rejected_candidates_count: int
    ambiguous_exit_count: int
    lifecycle_event_count: int
    last_cycle_time: str | None
    last_error: str | None
    lifecycle_status: str
    paper_only: bool
    human_readable_summary: str


class TradeLifecycleManager:
    """Manage paper candidate/order transitions while brokerage owns all P/L state."""

    def __init__(self, provider: MarketDataProvider, monitor: LiveMarketMonitor, broker: PaperBrokerageEngine, config: LifecycleConfig | None = None) -> None:
        self.provider = provider
        self.monitor = monitor
        self.broker = broker
        self.config = config or LifecycleConfig()
        self._lock = threading.RLock()
        self._orders: dict[str, PendingPaperOrder] = {}
        self._events: list[LifecycleEvent] = []
        self._processed_candidates: set[str] = set()
        self._managed_trade_ids: set[str] = set()
        self._trade_states: dict[str, LifecycleState] = {}
        self._expired = 0
        self._rejected = 0
        self._ambiguous = 0
        self._last_cycle_time: str | None = None
        self._last_error: str | None = None
        self._listeners: list[Any] = []
        if self.config.durable_state:
            self._load_state()

    def add_listener(self, listener: Any) -> None:
        with self._lock:
            if listener not in self._listeners:
                self._listeners.append(listener)

    def approve_candidate(self, request: ApproveCandidateRequest) -> PendingPaperOrder:
        with self._lock:
            if request.event_id in self._processed_candidates:
                raise LifecycleError("candidate already has a lifecycle decision")
            candidate = self.monitor.find_event(request.event_id)
            if candidate is None:
                raise LifecycleError("monitor candidate was not found")
            try:
                entry, stop, target = _candidate_levels(candidate)
                _validate_geometry(candidate.action, entry, stop, target)
                self._validate_order_type(request.order_type)
            except (LifecycleError, ValueError) as exc:
                self._processed_candidates.add(request.event_id)
                self._rejected += 1
                self._emit(candidate, "candidate_rejected", "candidate", "rejected", str(exc))
                raise LifecycleError(str(exc)) from exc

            now = _now()
            order_id = hashlib.sha256(f"{candidate.event_id}:{request.order_type.value}".encode()).hexdigest()[:24]
            order = PendingPaperOrder(
                order_id=order_id, source_event_id=candidate.event_id,
                symbol=candidate.symbol, timeframe=candidate.timeframe,
                higher_timeframe=candidate.higher_timeframe, action=candidate.action,
                setup=candidate.setup, strategy=candidate.strategy,
                order_type=request.order_type.value, entry_price=entry,
                stop_loss=stop, target=target, created_at=now,
                expires_after_candles=self.config.pending_order_expiration_candles,
                candles_evaluated=0, status="pending", trade_id=None,
                risk_per_trade_percent=request.risk_per_trade_percent,
                metadata=_candidate_metadata(candidate),
            )
            self._processed_candidates.add(candidate.event_id)
            self._orders[order.order_id] = order
            self._emit(candidate, "order_created", "candidate", "pending", f"Candidate approved and pending {order.order_type} order created.", order_id=order.order_id)
            if request.order_type is OrderType.MARKET:
                order = self._fill_order(order, candidate)
            self._persist_state()
            return order

    def reject_candidate(self, request: RejectCandidateRequest) -> LifecycleEvent:
        with self._lock:
            if request.event_id in self._processed_candidates:
                raise LifecycleError("candidate already has a lifecycle decision")
            candidate = self.monitor.find_event(request.event_id)
            if candidate is None:
                raise LifecycleError("monitor candidate was not found")
            self._processed_candidates.add(request.event_id)
            self._rejected += 1
            event = self._emit(candidate, "candidate_rejected", "candidate", "rejected", request.reason)
            self._persist_state()
            return event

    def cancel_order(self, request: CancelOrderRequest) -> LifecycleEvent:
        with self._lock:
            order = self._orders.get(request.order_id)
            if order is None or order.status != "pending":
                raise LifecycleError("pending lifecycle order was not found")
            self._orders[order.order_id] = replace(order, status="expired")
            self._expired += 1
            event = self._emit_order(order, "order_cancelled", "pending", "expired", request.reason)
            self._persist_state()
            return event

    def run_once(self) -> LifecycleCycleResult:
        new_events_before = len(self._events)
        errors: list[str] = []
        filled = closed = expired = ambiguous = pending_evaluated = 0
        if self.config.lifecycle_enabled and self.config.auto_open_from_monitor and not self.config.require_manual_approval:
            for candidate in self.monitor.events():
                if candidate.event_id not in self._processed_candidates:
                    try:
                        self.approve_candidate(ApproveCandidateRequest(event_id=candidate.event_id))
                    except LifecycleError as exc:
                        errors.append(str(exc))

        for order in tuple(self.pending_orders()):
            pending_evaluated += 1
            try:
                candles = self.provider.get_candles(order.symbol, order.timeframe, 2)
                if not candles:
                    raise LifecycleError("provider returned no candles")
                candle = candles[-1]
                evaluated = order.candles_evaluated + 1
                candidate = self.monitor.find_event(order.source_event_id)
                if candidate is None:
                    raise LifecycleError("source monitor candidate is unavailable")
                if _order_fills(order, candle):
                    self._orders[order.order_id] = replace(order, candles_evaluated=evaluated)
                    self._fill_order(self._orders[order.order_id], candidate)
                    filled += 1
                elif evaluated >= order.expires_after_candles:
                    self._orders[order.order_id] = replace(order, candles_evaluated=evaluated, status="expired")
                    self._expired += 1; expired += 1
                    self._emit_order(order, "order_expired", "pending", "expired", "Pending order expired before entry conditions were met.")
                else:
                    self._orders[order.order_id] = replace(order, candles_evaluated=evaluated)
            except Exception as exc:
                errors.append(f"{order.symbol} {order.timeframe}: {exc}")

        open_by_id = {item.trade_id: item for item in self.broker.open_positions() if item.trade_id in self._managed_trade_ids}
        for trade_id, trade in open_by_id.items():
            try:
                candles = self.provider.get_candles(trade.symbol, trade.timeframe, 2)
                if not candles:
                    raise LifecycleError("provider returned no candles")
                candle = candles[-1]
                stop_hit, target_hit = _exit_touches(trade, candle)
                if stop_hit and target_hit:
                    self._ambiguous += 1; ambiguous += 1
                    self._close_trade(trade, trade.stop_loss, "stop_hit", ambiguous=True)
                    closed += 1
                elif stop_hit:
                    self._close_trade(trade, trade.stop_loss, "stop_hit")
                    closed += 1
                elif target_hit:
                    self._close_trade(trade, trade.target, "target_hit")
                    closed += 1
                else:
                    self._advisory_management(trade, candle)
            except Exception as exc:
                errors.append(f"{trade.symbol} {trade.timeframe}: {exc}")

        completed = _now()
        with self._lock:
            self._last_cycle_time = completed
            if errors:
                self._last_error = errors[-1]
            emitted = tuple(self._events[new_events_before:])
            self._persist_state()
        return LifecycleCycleResult(
            pending_evaluated=pending_evaluated, orders_filled=filled,
            trades_closed=closed, orders_expired=expired,
            ambiguous_exits=ambiguous, errors=tuple(errors), events=emitted,
            completed_at=completed,
            human_readable_summary=f"Lifecycle evaluated {pending_evaluated} pending orders, filled {filled}, closed {closed}, and expired {expired}.",
        )

    def status(self) -> LifecycleStatus:
        with self._lock:
            return LifecycleStatus(
                lifecycle_enabled=self.config.lifecycle_enabled,
                auto_open_from_monitor=self.config.auto_open_from_monitor,
                require_manual_approval=self.config.require_manual_approval,
                pending_orders_count=len(self.pending_orders()),
                lifecycle_open_trades_count=len(self.open_trades()),
                lifecycle_closed_trades_count=len(self.closed_trades()),
                expired_orders_count=self._expired,
                rejected_candidates_count=self._rejected,
                ambiguous_exit_count=self._ambiguous,
                lifecycle_event_count=len(self._events),
                last_cycle_time=self._last_cycle_time, last_error=self._last_error,
                lifecycle_status="enabled_advisory" if self.config.lifecycle_enabled else "disabled_advisory",
                paper_only=True,
                human_readable_summary="Trade Lifecycle Manager is paper-only and never submits live orders.",
            )

    def events(self, limit: int | None = None) -> tuple[LifecycleEvent, ...]:
        with self._lock:
            values = tuple(self._events)
        return values[-limit:] if limit is not None else values

    def pending_orders(self) -> tuple[PendingPaperOrder, ...]:
        return tuple(item for item in self._orders.values() if item.status == "pending")

    def open_trades(self) -> tuple[PaperTrade, ...]:
        return tuple(item for item in self.broker.open_positions() if item.trade_id in self._managed_trade_ids)

    def closed_trades(self) -> tuple[PaperTrade, ...]:
        return tuple(item for item in self.broker.closed_trades() if item.trade_id in self._managed_trade_ids)

    def _fill_order(self, order: PendingPaperOrder, candidate: MonitorEvent) -> PendingPaperOrder:
        try:
            trade = self.broker.open_monitor_event(candidate, risk_per_trade_percent=order.risk_per_trade_percent)
        except PaperBrokerageError as exc:
            self._orders[order.order_id] = replace(order, status="rejected")
            self._rejected += 1
            self._emit_order(order, "order_rejected", "pending", "rejected", str(exc))
            raise LifecycleError(str(exc)) from exc
        self.monitor.mark_paper_trade_created(candidate.event_id)
        updated = replace(order, status="open", trade_id=trade.trade_id)
        self._orders[order.order_id] = updated
        self._managed_trade_ids.add(trade.trade_id)
        self._trade_states[trade.trade_id] = "open"
        self._emit_order(updated, "order_filled", "pending", "filled", "Pending paper order filled.", trade_id=trade.trade_id)
        self._emit_order(updated, "position_opened", "filled", "open", "Paper brokerage position opened.", trade_id=trade.trade_id)
        self._persist_state()
        return updated

    def _close_trade(self, trade: PaperTrade, exit_price: float, outcome: str, ambiguous: bool = False) -> None:
        state: LifecycleState = "stop_hit" if outcome == "stop_hit" else "target_hit"
        message = "Stop and target touched in the same candle; conservative stop-first handling applied." if ambiguous else f"Paper position {outcome.replace('_', ' ')}."
        self._emit_trade(trade, outcome, self._trade_states.get(trade.trade_id, "open"), state, message, {"same_candle_ambiguous": ambiguous})
        closed = self.broker.close_position(trade.trade_id, exit_price)
        self._trade_states[trade.trade_id] = "closed"
        self._emit_trade(closed, "position_closed", state, "closed", f"Paper position closed at {exit_price}.", {"realized_r": closed.realized_r})
        self._persist_state()

    def _advisory_management(self, trade: PaperTrade, candle: Any) -> None:
        risk = abs(trade.entry_price - trade.stop_loss)
        favorable = (candle.high - trade.entry_price) if trade.action == "buy" else (trade.entry_price - candle.low)
        favorable_r = favorable / risk if risk else 0.0
        state = self._trade_states.get(trade.trade_id, "open")
        if self.config.enable_trailing_stop_rule and favorable_r >= self.config.trailing_trigger_r and state != "trailing":
            self._trade_states[trade.trade_id] = "trailing"
            self._emit_trade(trade, "trailing_eligible", state, "trailing", "Trade reached the advisory trailing-stop trigger; brokerage levels remain unchanged.", {"favorable_r": favorable_r})
            self._persist_state()
        elif self.config.enable_breakeven_rule and favorable_r >= self.config.breakeven_trigger_r and state == "open":
            self._trade_states[trade.trade_id] = "breakeven_eligible"
            self._emit_trade(trade, "breakeven_eligible", "open", "breakeven_eligible", "Trade reached the advisory break-even trigger; brokerage stop remains unchanged.", {"favorable_r": favorable_r})
            self._persist_state()

    def _validate_order_type(self, order_type: OrderType) -> None:
        allowed = {
            OrderType.MARKET: self.config.allow_market_orders,
            OrderType.LIMIT_RETEST: self.config.allow_limit_orders,
            OrderType.CONFIRMATION_CLOSE: self.config.allow_confirmation_close,
        }
        if not allowed[order_type]:
            raise LifecycleError(f"{order_type.value} orders are disabled")

    def _emit(self, candidate: MonitorEvent, event_type: str, before: LifecycleState, after: LifecycleState, message: str, *, order_id: str | None = None) -> LifecycleEvent:
        return self._append_event(event_type, candidate.symbol, candidate.timeframe, candidate.event_id, None, before, after, message, {"order_id": order_id} if order_id else {})

    def _emit_order(self, order: PendingPaperOrder, event_type: str, before: LifecycleState, after: LifecycleState, message: str, *, trade_id: str | None = None) -> LifecycleEvent:
        return self._append_event(event_type, order.symbol, order.timeframe, order.source_event_id, trade_id or order.trade_id, before, after, message, {"order_id": order.order_id})

    def _emit_trade(self, trade: PaperTrade, event_type: str, before: LifecycleState, after: LifecycleState, message: str, metadata: dict[str, Any]) -> LifecycleEvent:
        return self._append_event(event_type, trade.symbol, trade.timeframe, trade.source_event_id, trade.trade_id, before, after, message, metadata)

    def _append_event(self, event_type, symbol, timeframe, source_event_id, trade_id, before, after, message, metadata) -> LifecycleEvent:
        now = _now()
        event = LifecycleEvent(
            event_id=hashlib.sha256(f"{event_type}:{symbol}:{timeframe}:{now}:{len(self._events)}".encode()).hexdigest()[:24],
            timestamp=now, type=event_type, symbol=symbol, timeframe=timeframe,
            source_event_id=source_event_id, trade_id=trade_id,
            state_before=before, state_after=after, message=message, metadata=metadata,
        )
        self._events.append(event)
        excess = len(self._events) - self.config.max_lifecycle_events_in_memory
        if excess > 0:
            del self._events[:excess]
        for listener in tuple(self._listeners):
            try:
                listener(event)
            except Exception:
                continue
        return event

    def recover_from_storage(self) -> LifecycleStatus:
        with self._lock:
            if self.config.durable_state:
                self._load_state()
            return self.status()

    def _persist_state(self) -> None:
        if not self.config.durable_state:
            return
        path = Path(self.config.persistence_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "pending_orders": [asdict(item) for item in self._orders.values()],
            "trade_event_history": [asdict(item) for item in self._events],
            "processed_candidates": sorted(self._processed_candidates),
            "managed_trade_ids": sorted(self._managed_trade_ids),
            "trade_states": dict(self._trade_states),
            "expired_trades": self._expired,
            "rejected_candidates": self._rejected,
            "ambiguous_exit_count": self._ambiguous,
            "last_cycle_time": self._last_cycle_time,
            "last_error": self._last_error,
            "state_machine_status": self.status().lifecycle_status,
            "updated_at": _now(),
        }
        path.write_text(json.dumps(payload, separators=(",", ":"), default=str), encoding="utf-8")

    def _load_state(self) -> None:
        path = Path(self.config.persistence_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            self._persist_state()
            return
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            self._orders = {
                item["order_id"]: PendingPaperOrder(**item)
                for item in raw.get("pending_orders", ())
                if isinstance(item, dict) and item.get("order_id")
            }
            seen_events: set[str] = set()
            events: list[LifecycleEvent] = []
            for item in raw.get("trade_event_history", ()):
                if not isinstance(item, dict) or not item.get("event_id") or item["event_id"] in seen_events:
                    continue
                seen_events.add(item["event_id"])
                events.append(LifecycleEvent(**item))
            self._events = events[-self.config.max_lifecycle_events_in_memory:]
            self._processed_candidates = set(raw.get("processed_candidates", ()))
            self._managed_trade_ids = set(raw.get("managed_trade_ids", ()))
            self._trade_states = dict(raw.get("trade_states", {}))
            self._expired = int(raw.get("expired_trades", 0) or 0)
            self._rejected = int(raw.get("rejected_candidates", 0) or 0)
            self._ambiguous = int(raw.get("ambiguous_exit_count", 0) or 0)
            self._last_cycle_time = raw.get("last_cycle_time")
            self._last_error = raw.get("last_error")
        except (OSError, TypeError, ValueError, KeyError, json.JSONDecodeError):
            self._orders = {}
            self._events = []
            self._processed_candidates = set()
            self._managed_trade_ids = set()
            self._trade_states = {}
            self._expired = self._rejected = self._ambiguous = 0
            self._last_cycle_time = self._last_error = None
            self._persist_state()


def _candidate_levels(candidate: MonitorEvent) -> tuple[float, float, float]:
    entry = parse_price_level(candidate.entry_zone, midpoint=True)
    stop = parse_price_level(candidate.stop_loss)
    target = parse_price_level(candidate.target)
    if entry is None or stop is None or target is None:
        raise LifecycleError("candidate entry, stop, or target is unavailable")
    return entry, stop, target


def _validate_geometry(action: str, entry: float, stop: float, target: float) -> None:
    if action == "buy" and stop < entry < target:
        return
    if action == "sell" and target < entry < stop:
        return
    raise LifecycleError("candidate has invalid directional price geometry")


def _candidate_metadata(candidate: MonitorEvent) -> dict[str, Any]:
    return {
        "confidence": candidate.confidence,
        "setup_quality": candidate.setup_quality,
        "score_summary": candidate.score_summary,
        "execution_intelligence": candidate.execution_intelligence,
        "confidence_calibration": candidate.confidence_calibration,
        "symbol_profile": candidate.symbol_profile,
        "adaptive_strategy_router": candidate.adaptive_strategy_router,
        "strategy_rating": candidate.strategy_rating,
        "setup_rating": candidate.setup_rating,
    }


def _order_fills(order: PendingPaperOrder, candle: Any) -> bool:
    if order.order_type == OrderType.LIMIT_RETEST.value:
        return candle.low <= order.entry_price <= candle.high
    if order.order_type == OrderType.CONFIRMATION_CLOSE.value:
        return candle.close >= order.entry_price if order.action == "buy" else candle.close <= order.entry_price
    return True


def _exit_touches(trade: PaperTrade, candle: Any) -> tuple[bool, bool]:
    if trade.action == "buy":
        return candle.low <= trade.stop_loss, candle.high >= trade.target
    return candle.high >= trade.stop_loss, candle.low <= trade.target


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


_GLOBAL_MANAGER: TradeLifecycleManager | None = None
_GLOBAL_LOCK = threading.RLock()


def get_global_trade_lifecycle_manager(provider: MarketDataProvider, monitor: LiveMarketMonitor, broker: PaperBrokerageEngine) -> TradeLifecycleManager:
    global _GLOBAL_MANAGER
    with _GLOBAL_LOCK:
        if _GLOBAL_MANAGER is None or _GLOBAL_MANAGER.provider is not provider or _GLOBAL_MANAGER.monitor is not monitor or _GLOBAL_MANAGER.broker is not broker:
            _GLOBAL_MANAGER = TradeLifecycleManager(provider, monitor, broker, LifecycleConfig(durable_state=True))
        return _GLOBAL_MANAGER


def current_trade_lifecycle_manager() -> TradeLifecycleManager | None:
    with _GLOBAL_LOCK:
        return _GLOBAL_MANAGER


def reset_global_trade_lifecycle_manager() -> None:
    global _GLOBAL_MANAGER
    with _GLOBAL_LOCK:
        _GLOBAL_MANAGER = None
