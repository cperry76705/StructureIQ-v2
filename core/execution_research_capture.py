"""Durable prospective market-data capture for approved paper orders."""

from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from core.market_session_engine import classify_symbol


@dataclass(frozen=True)
class ExecutionResearchConfig:
    enabled: bool = True
    horizon_hours: float = 24.0
    max_candles_per_order: int = 500
    root: str = "research/execution_research"


@dataclass(frozen=True)
class ResearchOrderSnapshot:
    research_id: str
    campaign_id: str | None
    source_event_id: str | None
    candidate_id: str | None
    order_id: str
    symbol: str
    asset_class: str
    timeframe: str
    higher_timeframe: str
    strategy: str
    setup: str
    direction: str
    approval_timestamp: str
    order_created_at: str
    intended_entry: float
    stop_loss: float
    target: float
    target_r: float | None
    risk_per_trade_percent: float | None
    position_size_reference: float | None
    market_price_at_approval: float | None
    market_price_at_order_creation: float | None
    bid: float | None
    ask: float | None
    spread: float | None
    volatility_context: Any | None
    market_regime: Any | None
    trend_direction: Any | None
    confidence: float | None
    setup_quality: Any | None
    overall_score: Any | None
    execution_cost_grade: Any | None
    order_type: str
    expiration_policy: str
    expires_after_candles: int
    execution_intelligence: Any | None
    candidate_metadata: dict[str, Any]
    capture_origin: str = "PROSPECTIVE_CAPTURE"


@dataclass
class ResearchOrderState:
    snapshot: ResearchOrderSnapshot
    status: str = "CAPTURING"
    candles: list[dict[str, Any]] = field(default_factory=list)
    actual_order_status: str = "pending"
    actual_trade_id: str | None = None
    last_retrieved_at: str | None = None
    provider: str | None = None
    provider_symbol: str | None = None
    error: str | None = None
    updated_at: str | None = None


class ExecutionResearchCapture:
    """Persist immutable approval snapshots and de-duplicated post-order candles."""

    def __init__(self, *, lifecycle: Any, provider: Any, config: ExecutionResearchConfig | None = None, campaign_resolver=None) -> None:
        self.lifecycle = lifecycle
        self.provider = provider
        self.config = config or ExecutionResearchConfig()
        self.root = Path(self.config.root)
        self.campaign_resolver = campaign_resolver or _current_campaign_id
        self._lock = threading.RLock()
        self._states: dict[str, ResearchOrderState] = {}
        self._worker: threading.Thread | None = None
        self._load()
        if hasattr(lifecycle, "add_listener"):
            lifecycle.add_listener(self.on_lifecycle_event)

    def on_lifecycle_event(self, event: Any) -> None:
        """Best-effort listener; research failure never escapes into lifecycle."""
        try:
            event_type = str(getattr(event, "type", ""))
            order_id = (getattr(event, "metadata", None) or {}).get("order_id")
            if event_type == "order_created" and order_id:
                order = next((item for item in self.lifecycle.orders() if item.order_id == order_id), None)
                if order is not None:
                    self.capture_order(order, approval_timestamp=getattr(event, "timestamp", None))
                    self.schedule_collection()
            elif order_id:
                self.update_actual_state(order_id, str(getattr(event, "state_after", "unknown")), getattr(event, "trade_id", None))
        except Exception:
            return

    def capture_order(self, order: Any, *, approval_timestamp: str | None = None, campaign_id: str | None = None, capture_origin: str = "PROSPECTIVE_CAPTURE") -> ResearchOrderState:
        research_id = hashlib.sha256(f"execution-research:{order.order_id}".encode()).hexdigest()[:24]
        with self._lock:
            if research_id in self._states:
                return self._states[research_id]
            metadata = dict(getattr(order, "metadata", None) or {})
            created = str(getattr(order, "created_at", None) or _now())
            resolved_campaign = campaign_id or metadata.get("campaign_id") or self.campaign_resolver()
            snapshot = ResearchOrderSnapshot(
                research_id=research_id, campaign_id=resolved_campaign,
                source_event_id=getattr(order, "source_event_id", None), candidate_id=getattr(order, "source_event_id", None),
                order_id=str(order.order_id), symbol=str(order.symbol), asset_class=classify_symbol(order.symbol).value,
                timeframe=str(order.timeframe), higher_timeframe=str(getattr(order, "higher_timeframe", "")),
                strategy=str(getattr(order, "strategy", "")), setup=str(getattr(order, "setup", "")),
                direction=str(getattr(order, "action", "")), approval_timestamp=approval_timestamp or created,
                order_created_at=created, intended_entry=float(order.entry_price), stop_loss=float(order.stop_loss),
                target=float(order.target), target_r=_target_r(order), risk_per_trade_percent=_float(getattr(order, "risk_per_trade_percent", None)),
                position_size_reference=_float(metadata.get("position_size_reference")), market_price_at_approval=_float(metadata.get("market_price_at_approval")),
                market_price_at_order_creation=_float(metadata.get("market_price_at_order_creation")), bid=_float(metadata.get("bid")),
                ask=_float(metadata.get("ask")), spread=_float(metadata.get("spread")), volatility_context=metadata.get("volatility_context"),
                market_regime=metadata.get("market_regime"), trend_direction=metadata.get("trend_direction"),
                confidence=_float(metadata.get("confidence")), setup_quality=metadata.get("setup_quality"), overall_score=metadata.get("score_summary"),
                execution_cost_grade=_nested(metadata.get("execution_intelligence"), "execution_grade"), order_type=str(order.order_type),
                expiration_policy="candles_evaluated", expires_after_candles=int(order.expires_after_candles),
                execution_intelligence=metadata.get("execution_intelligence"), candidate_metadata=metadata, capture_origin=capture_origin,
            )
            state = ResearchOrderState(snapshot=snapshot, actual_order_status=str(getattr(order, "status", "pending")), updated_at=_now())
            self._states[research_id] = state
            self._persist(state)
            return state

    def capture_candles(self, research_id: str, candles: list[Any] | tuple[Any, ...], *, provider: str | None = None, provider_symbol: str | None = None) -> ResearchOrderState:
        with self._lock:
            state = self._states[research_id]
            existing = {str(item["candle_timestamp"]) for item in state.candles}
            for candle in candles:
                row = _candle_row(candle, provider or getattr(self.provider, "provider_name", type(self.provider).__name__), provider_symbol or state.snapshot.symbol)
                if row is None or str(row["candle_timestamp"]) in existing:
                    continue
                state.candles.append(row); existing.add(str(row["candle_timestamp"]))
            state.candles.sort(key=lambda item: _timestamp_sort(item["candle_timestamp"]))
            state.candles = state.candles[-self.config.max_candles_per_order:]
            state.provider = provider or getattr(self.provider, "provider_name", type(self.provider).__name__)
            state.provider_symbol = provider_symbol or state.snapshot.symbol
            state.last_retrieved_at = _now(); state.error = None; state.updated_at = _now()
            state.status = self._coverage_status(state)
            self._persist(state)
            return state

    def collect(self, research_id: str) -> ResearchOrderState:
        state = self._states[research_id]
        try:
            candles = self.provider.get_candles(state.snapshot.symbol, state.snapshot.timeframe, self.config.max_candles_per_order)
            return self.capture_candles(research_id, tuple(candles or ()))
        except Exception as exc:
            with self._lock:
                state.error = str(exc); state.status = "ERROR"; state.updated_at = _now(); self._persist(state)
            return state

    def collect_all(self) -> tuple[ResearchOrderState, ...]:
        if not self.config.enabled:
            return self.orders()
        for state in self.orders():
            if state.status in {"CAPTURING", "PARTIAL", "INSUFFICIENT_DATA", "ERROR"}:
                self.collect(state.snapshot.research_id)
        return self.orders()

    def schedule_collection(self) -> bool:
        """Start at most one daemon collection pass; never block the trading cycle."""
        with self._lock:
            if self._worker is not None and self._worker.is_alive():
                return False
            self._worker = threading.Thread(target=self.collect_all, name="execution-research", daemon=True)
            self._worker.start()
            return True

    def update_actual_state(self, order_id: str, status: str, trade_id: str | None = None) -> None:
        with self._lock:
            state = next((x for x in self._states.values() if x.snapshot.order_id == order_id), None)
            if state is None: return
            state.actual_order_status=status; state.actual_trade_id=trade_id or state.actual_trade_id; state.updated_at=_now(); self._persist(state)

    def orders(self, *, campaign_id: str | None = None) -> tuple[ResearchOrderState, ...]:
        with self._lock:
            values = tuple(self._states.values())
        return tuple(x for x in values if campaign_id is None or x.snapshot.campaign_id == campaign_id)

    def get(self, research_id: str) -> ResearchOrderState | None:
        return self._states.get(research_id)

    def summary(self, *, campaign_id: str | None = None) -> dict[str, Any]:
        orders = self.orders(campaign_id=campaign_id); total = len(orders)
        complete = sum(x.status == "COMPLETE" for x in orders); partial = sum(x.status in {"CAPTURING", "PARTIAL"} and bool(x.candles) for x in orders)
        none = sum(not x.candles for x in orders)
        return {"approved_orders": total, "research_orders_created": total,
            "orders_with_market_snapshot": sum(x.snapshot.market_price_at_order_creation is not None for x in orders),
            "orders_with_complete_candle_horizon": complete, "orders_with_partial_candle_horizon": partial,
            "orders_with_no_candles": none, "research_coverage_percent": round((total-none)/total*100,6) if total else None,
            "shadow_evaluable_orders": sum(bool(x.candles) for x in orders), "capturing": sum(x.status == "CAPTURING" for x in orders),
            "errors": sum(x.status == "ERROR" for x in orders), "queue_backlog": sum(x.status not in {"COMPLETE"} for x in orders),
            "read_only_actual_execution": True}

    def writable(self) -> bool:
        try:
            self.root.mkdir(parents=True, exist_ok=True); probe=self.root/".probe"; probe.write_text("ok",encoding="utf-8"); probe.unlink(); return True
        except OSError: return False

    def _coverage_status(self, state: ResearchOrderState) -> str:
        if not state.candles: return "INSUFFICIENT_DATA"
        horizon = _dt(state.snapshot.order_created_at) + timedelta(hours=self.config.horizon_hours)
        latest = max((_candle_dt(x["candle_timestamp"]) for x in state.candles), default=None)
        return "COMPLETE" if latest and latest >= horizon else "PARTIAL"

    def _persist(self, state: ResearchOrderState) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / f"{state.snapshot.research_id}.json"; temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(asdict(state), separators=(",", ":"), default=str), encoding="utf-8"); temp.replace(path)

    def _load(self) -> None:
        if not self.root.exists(): return
        for path in self.root.glob("*.json"):
            try:
                raw=json.loads(path.read_text(encoding="utf-8")); raw["snapshot"]=ResearchOrderSnapshot(**raw["snapshot"])
                state=ResearchOrderState(**raw); self._states[state.snapshot.research_id]=state
            except (OSError,TypeError,ValueError,KeyError,json.JSONDecodeError): continue


def _candle_row(candle: Any, provider: str, provider_symbol: str) -> dict[str, Any] | None:
    timestamp=getattr(candle,"timestamp",None)
    if timestamp is None: return None
    return {"provider":provider,"provider_symbol":provider_symbol,"timeframe":None,"retrieved_at":_now(),"candle_timestamp":timestamp,
        "open":float(candle.open),"high":float(candle.high),"low":float(candle.low),"close":float(candle.close),"volume":_float(getattr(candle,"volume",None))}
def _target_r(order):
    risk=abs(float(order.entry_price)-float(order.stop_loss)); return abs(float(order.target)-float(order.entry_price))/risk if risk else None
def _float(value):
    try:return float(value) if value is not None else None
    except (TypeError,ValueError):return None
def _nested(value,key): return value.get(key) if isinstance(value,dict) else None
def _now(): return datetime.now(timezone.utc).isoformat()
def _dt(value):
    result=datetime.fromisoformat(str(value).replace("Z","+00:00")); return result if result.tzinfo else result.replace(tzinfo=timezone.utc)
def _candle_dt(value):
    if isinstance(value,(int,float)): return datetime.fromtimestamp(value/1000 if value>10_000_000_000 else value,tz=timezone.utc)
    try:return _dt(value)
    except ValueError:return None
def _timestamp_sort(value):
    parsed=_candle_dt(value); return parsed.timestamp() if parsed else 0
def _current_campaign_id():
    try:
        from core.validation_campaigns import get_global_validation_campaign_manager
        campaign=get_global_validation_campaign_manager().current(); return campaign.campaign_id if campaign else None
    except Exception:return None
