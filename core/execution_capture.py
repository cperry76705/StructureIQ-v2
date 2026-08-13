"""Read-only execution opportunity capture and missed-order research diagnostics."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from statistics import mean, median
from typing import Any, Iterable

from core.lifecycle_record_classification import LifecycleRecordClassification, classify_lifecycle_record
from core.market_session_engine import classify_symbol


SCENARIOS = (
    "LIMIT_RETEST_CURRENT", "LIMIT_TOLERANCE_0_10_PERCENT", "LIMIT_TOLERANCE_0_25_PERCENT",
    "LIMIT_TOLERANCE_0_50_PERCENT", "EXTENDED_ORDER_LIFETIME_2X", "EXTENDED_ORDER_LIFETIME_4X",
    "APPROVAL_PRICE_ENTRY", "CONFIRMATION_MARKET_ENTRY",
)


@dataclass(frozen=True)
class ExecutionCaptureRecord:
    order_id: str
    source_event_id: str | None
    trade_id: str | None
    campaign_id: str | None
    symbol: str
    asset_class: str
    strategy: str
    setup: str
    direction: str
    order_type: str
    candidate_created_at: str | None
    order_created_at: str | None
    order_expired_at: str | None
    intended_entry: float | None
    stop_loss: float | None
    target: float | None
    target_r: float | None
    market_price_at_order_creation: float | None
    distance_to_entry: float | None
    distance_to_entry_percent: float | None
    order_lifetime_seconds: float | None
    classification: str
    terminal_state: str
    terminal_reason: str
    minimum_distance_to_entry: float | None
    entry_touched: bool | None
    entry_touched_after_expiration: bool | None
    maximum_favorable_excursion: float | None
    maximum_adverse_excursion: float | None
    target_reached: bool | None
    stop_reached: bool | None
    first_exit_event: str | None
    seconds_to_closest_approach: float | None
    seconds_to_target: float | None
    seconds_to_stop: float | None
    data_status: str


class ExecutionCaptureEngine:
    """Join retained orders, lifecycle evidence, journal trades, and optional candles."""

    def __init__(self, *, lifecycle: Any, journal: Any, opportunity: Any, reconciliation: Any | None = None, provider: Any | None = None, excluded_trade_ids: Iterable[str] = ()) -> None:
        self.lifecycle = lifecycle
        self.journal = journal
        self.opportunity = opportunity
        self.reconciliation = reconciliation
        self.provider = provider or getattr(lifecycle, "provider", None)
        self.excluded_trade_ids = {str(item) for item in excluded_trade_ids}

    def report(self, *, campaign_id: str | None = None) -> dict[str, Any]:
        records = self.records(campaign_id=campaign_id)
        opportunity = self.opportunity.report(campaign_id=campaign_id)
        summary = self._summary(records, opportunity)
        return {
            "campaign_id": campaign_id,
            "summary": summary,
            "funnel": self._funnel(summary),
            "unfilled": [asdict(item) for item in records if item.classification != "OPEN_TRADE" and item.classification != "CLOSED_TRADE"],
            "by_symbol": self._aggregate(records, "symbol", opportunity),
            "by_asset_class": self._aggregate(records, "asset_class", opportunity),
            "by_strategy": self._aggregate(records, "strategy", opportunity),
            "by_setup": self._aggregate(records, "setup", opportunity),
            "counterfactuals": self._counterfactuals(records),
            "prop_readiness": self._prop_readiness(records, summary, campaign_id),
            "trades": self._trade_audit(campaign_id),
            "capture_metric_definitions": {
                "SETUP_CAPTURE_RATE": "qualified setups divided by raw setups",
                "CANDIDATE_CAPTURE_RATE": "candidates created divided by qualified setups",
                "APPROVED_ORDER_FILL_RATE": "filled approved orders divided by approved orders created",
                "APPROVED_TRADE_CAPTURE_RATE": "trades opened divided by approved candidates",
                "MISSED_FAVORABLE_MOVE_RATE": "analyzable unfilled orders whose original target was subsequently reached divided by analyzable unfilled orders",
            },
            "read_only": True,
            "human_readable_summary": (
                f"Observed {summary['orders_created']} approved orders and {summary['orders_filled']} fills; "
                f"order fill rate is {_display(summary['order_fill_rate'])}. Counterfactual results are research-only."
            ),
        }

    def records(self, *, campaign_id: str | None = None) -> tuple[ExecutionCaptureRecord, ...]:
        entries = [item for item in self.journal.entries() if self._eligible(item, campaign_id)]
        by_source = {str(item.source_event_id): item for item in entries if getattr(item, "source_event_id", None)}
        by_trade = {str(item.trade_id): item for item in entries if getattr(item, "trade_id", None)}
        orders = tuple(self.lifecycle.orders()) if hasattr(self.lifecycle, "orders") else tuple(self.lifecycle.pending_orders())
        results = []
        for order in orders:
            journal = by_trade.get(str(getattr(order, "trade_id", None))) or by_source.get(str(getattr(order, "source_event_id", None)))
            if journal is None or not self._eligible(journal, campaign_id):
                continue
            events = tuple(getattr(journal, "lifecycle_events", ()) or ())
            classification = classify_lifecycle_record(journal, events=events)
            created = _event_time(events, {"order_created"}) or getattr(order, "created_at", None)
            expired = _event_time(events, {"order_expired", "order_cancelled", "order_rejected"})
            candles = self._candles(order, created)
            analysis = _analyze_candles(order, candles, created, expired)
            state = str(getattr(order, "status", "unknown"))
            reason = _terminal_reason(state, events, analysis)
            entry = _float(getattr(order, "entry_price", None))
            market_price = analysis.pop("market_price_at_order_creation")
            distance = abs(market_price - entry) if market_price is not None and entry is not None else None
            results.append(ExecutionCaptureRecord(
                order_id=str(order.order_id), source_event_id=getattr(order, "source_event_id", None),
                trade_id=getattr(order, "trade_id", None), campaign_id=getattr(journal, "campaign_id", None),
                symbol=str(order.symbol), asset_class=classify_symbol(order.symbol).value,
                strategy=str(getattr(order, "strategy", "") or "UNKNOWN"), setup=str(getattr(order, "setup", "") or "UNKNOWN"),
                direction=str(getattr(order, "action", "") or "UNKNOWN"), order_type=str(getattr(order, "order_type", "") or "UNKNOWN"),
                candidate_created_at=_event_time(events, {"candidate_created"}), order_created_at=created,
                order_expired_at=expired, intended_entry=entry, stop_loss=_float(getattr(order, "stop_loss", None)),
                target=_float(getattr(order, "target", None)), target_r=_target_r(order),
                market_price_at_order_creation=market_price, distance_to_entry=distance,
                distance_to_entry_percent=(distance / market_price * 100 if distance is not None and market_price else None),
                order_lifetime_seconds=_seconds(created, expired), classification=classification.value,
                terminal_state=state.upper(), terminal_reason=reason, **analysis,
            ))
        return tuple(results)

    def _candles(self, order: Any, created: str | None) -> tuple[Any, ...]:
        if self.provider is None or not hasattr(self.provider, "get_candles"):
            return ()
        try:
            return tuple(self.provider.get_candles(order.symbol, order.timeframe, 5000) or ())
        except Exception:
            return ()

    def _summary(self, records: tuple[ExecutionCaptureRecord, ...], opportunity: Any) -> dict[str, Any]:
        base = opportunity.summary
        filled = [r for r in records if r.classification in {"OPEN_TRADE", "CLOSED_TRADE"}]
        unfilled = [r for r in records if r not in filled]
        analyzable = [r for r in unfilled if r.data_status == "PASS"]
        return {
            "raw_setups": base.raw_setups, "qualified_setups": base.qualified_setups,
            "candidates_created": base.candidates_created, "approved_candidates": base.approved_candidates,
            "orders_created": len(records), "orders_filled": len(filled), "orders_unfilled": len(unfilled),
            "orders_expired": sum(r.terminal_state == "EXPIRED" for r in records),
            "orders_cancelled": sum(r.terminal_reason == "ORDER_CANCELLED" for r in records),
            "orders_rejected": sum(r.terminal_reason == "ORDER_REJECTED" for r in records),
            "trades_opened": sum(r.classification in {"OPEN_TRADE", "CLOSED_TRADE"} for r in records),
            "trades_closed": sum(r.classification == "CLOSED_TRADE" for r in records),
            "candidate_to_approval_rate": _rate(base.approved_candidates, base.candidates_created),
            "approval_to_order_rate": _rate(len(records), base.approved_candidates),
            "order_fill_rate": _rate(len(filled), len(records)),
            "approval_to_trade_rate": _rate(len(filled), base.approved_candidates),
            "trade_close_rate": _rate(sum(r.classification == "CLOSED_TRADE" for r in records), len(filled)),
            "setup_capture_rate": _rate(base.qualified_setups, base.raw_setups),
            "candidate_capture_rate": _rate(base.candidates_created, base.qualified_setups),
            "missed_favorable_move_rate": _rate(sum(r.target_reached is True for r in analyzable), len(analyzable)),
            "never_reached_entry": sum(r.entry_touched is False for r in analyzable),
            "reached_entry_before_expiration": sum(r.entry_touched is True for r in analyzable),
            "reached_entry_after_expiration": sum(r.entry_touched_after_expiration is True for r in analyzable),
            "subsequently_reached_target": sum(r.target_reached is True for r in analyzable),
            "subsequently_reached_stop": sum(r.stop_reached is True for r in analyzable),
            "ambiguous": sum(r.first_exit_event == "AMBIGUOUS_INTRABAR" for r in analyzable),
            "insufficient_market_data": sum(r.data_status != "PASS" for r in unfilled),
            "average_distance_to_entry": _average(r.distance_to_entry for r in records),
            "median_distance_to_entry": _median(r.distance_to_entry for r in records),
            "average_order_lifetime_seconds": _average(r.order_lifetime_seconds for r in records),
            "median_order_lifetime_seconds": _median(r.order_lifetime_seconds for r in records),
        }

    def _funnel(self, summary: dict[str, Any]) -> dict[str, int]:
        return {key: summary[key] for key in ("raw_setups", "qualified_setups", "candidates_created", "approved_candidates", "orders_created", "orders_filled", "orders_unfilled", "trades_opened", "trades_closed")}

    def _aggregate(self, records: tuple[ExecutionCaptureRecord, ...], field: str, opportunity: Any) -> list[dict[str, Any]]:
        groups = defaultdict(list)
        for record in records: groups[getattr(record, field) or "UNKNOWN"].append(record)
        opportunity_symbols = {item.symbol: item for item in getattr(opportunity, "by_symbol", ())}
        rows = []
        for name, items in sorted(groups.items()):
            fills = [i for i in items if i.classification in {"OPEN_TRADE", "CLOSED_TRADE"}]
            base = opportunity_symbols.get(name) if field == "symbol" else None
            rows.append({field: name, "raw_setups": getattr(base, "raw_setups", None), "qualified_setups": getattr(base, "qualified_setups", None),
                "candidates": getattr(base, "candidates_created", None), "approved_candidates": len(items), "orders_created": len(items),
                "orders_filled": len(fills), "trades": len(fills), "fill_rate": _rate(len(fills), len(items)),
                "orders_expired": sum(i.terminal_state == "EXPIRED" for i in items),
                "average_entry_distance": _average(i.distance_to_entry for i in items),
                "average_order_lifetime": _average(i.order_lifetime_seconds for i in items),
                "average_mfe": _average(i.maximum_favorable_excursion for i in items if i.classification not in {"OPEN_TRADE", "CLOSED_TRADE"}),
                "average_mae": _average(i.maximum_adverse_excursion for i in items if i.classification not in {"OPEN_TRADE", "CLOSED_TRADE"}),
                "missed_target_count": sum(i.target_reached is True and i.classification not in {"OPEN_TRADE", "CLOSED_TRADE"} for i in items),
                "missed_stop_count": sum(i.stop_reached is True and i.classification not in {"OPEN_TRADE", "CLOSED_TRADE"} for i in items)})
        return rows

    def _counterfactuals(self, records: tuple[ExecutionCaptureRecord, ...]) -> list[dict[str, Any]]:
        results = []
        for scenario in SCENARIOS:
            modeled = [_model_scenario(r, scenario) for r in records]
            available = [item for item in modeled if item is not None]
            fills = [item for item in available if item[0]]
            returns = [item[1] for item in fills if item[1] is not None]
            results.append({"scenario": scenario, "status": "PASS" if available else "INSUFFICIENT_DATA",
                "hypothetical_fills": len(fills), "fill_rate": _rate(len(fills), len(available)),
                "wins": sum(r > 0 for r in returns), "losses": sum(r < 0 for r in returns), "breakeven": sum(r == 0 for r in returns),
                "total_r": round(sum(returns), 6), "average_r": _average(returns), "expectancy_r": _average(returns),
                "win_rate": _rate(sum(r > 0 for r in returns), len(returns)), "max_drawdown_r": _max_drawdown(returns),
                "average_entry_slippage": None, "average_adverse_excursion": None, "average_favorable_excursion": None,
                "research_only": True})
        return results

    def _prop_readiness(self, records: tuple[ExecutionCaptureRecord, ...], summary: dict[str, Any], campaign_id: str | None) -> dict[str, Any]:
        filled_ids = {r.trade_id for r in records if r.trade_id and r.classification in {"OPEN_TRADE", "CLOSED_TRADE"}}
        trades = [e for e in self.journal.entries() if self._eligible(e, campaign_id) and e.trade_id in filled_ids]
        duration = _duration_days([getattr(x, "opened_at", None) for x in trades] + [r.order_created_at for r in records])
        returns = [float(e.realized_r) for e in trades if getattr(e, "realized_r", None) is not None]
        return {"campaign_days": duration, "executed_trades_per_day": len(trades) / duration if duration else None,
            "approved_opportunities_per_day": len(records) / duration if duration else None, "fill_rate": summary["order_fill_rate"],
            "realized_r_per_day": sum(returns) / duration if duration else None, "average_r_per_trade": _average(returns),
            "win_rate": _rate(sum(r > 0 for r in returns), len(returns)), "maximum_drawdown_r": _max_drawdown(returns),
            "opportunity_capture_rate": summary["approval_to_trade_rate"], "read_only": True}

    def _trade_audit(self, campaign_id: str | None) -> list[dict[str, Any]]:
        discrepancies = ()
        if self.reconciliation is not None:
            try: discrepancies = self.reconciliation.run(persist=False, scope="campaign", campaign_id=campaign_id).discrepancies if campaign_id else self.reconciliation.run(persist=False).discrepancies
            except Exception: discrepancies = ()
        by_trade = defaultdict(list)
        for item in discrepancies:
            if getattr(item, "trade_id", None): by_trade[item.trade_id].append(item.message)
        rows = []
        for entry in self.journal.entries():
            if not self._eligible(entry, campaign_id) or classify_lifecycle_record(entry).value not in {"OPEN_TRADE", "CLOSED_TRADE"}: continue
            rows.append({"trade_id": entry.trade_id, "source_event_id": entry.source_event_id, "campaign_id": entry.campaign_id,
                "symbol": entry.symbol, "status": entry.status, "entry": entry.actual_entry, "stop": entry.stop_loss,
                "target": entry.target, "exit": entry.exit_price, "realized_r": entry.realized_r, "realized_pl": entry.realized_pl,
                "lifecycle_events": list(entry.lifecycle_events), "reconciliation_discrepancies": by_trade.get(entry.trade_id, []),
                "linkage_complete": bool(entry.source_event_id and entry.lifecycle_events and entry.opened_at)})
        return rows

    def _eligible(self, entry: Any, campaign_id: str | None) -> bool:
        return str(getattr(entry, "trade_id", "")) not in self.excluded_trade_ids and _eligible(entry, campaign_id)


def _eligible(entry: Any, campaign_id: str | None) -> bool:
    if campaign_id is not None and getattr(entry, "campaign_id", None) != campaign_id: return False
    if campaign_id is None and getattr(entry, "campaign_id", None) in {None, "legacy_campaign"}: return False
    return not any(bool(getattr(entry, flag, False)) for flag in ("test_fixture", "synthetic_recovery_test", "exclude_from_performance", "exclude_from_campaign_metrics", "exclude_from_research"))


def _analyze_candles(order: Any, candles: tuple[Any, ...], created: str | None, expired: str | None) -> dict[str, Any]:
    empty = {"minimum_distance_to_entry": None, "entry_touched": None, "entry_touched_after_expiration": None,
        "maximum_favorable_excursion": None, "maximum_adverse_excursion": None, "target_reached": None, "stop_reached": None,
        "first_exit_event": None, "seconds_to_closest_approach": None, "seconds_to_target": None, "seconds_to_stop": None,
        "data_status": "INSUFFICIENT_DATA", "market_price_at_order_creation": None}
    start = _dt(created); end = _dt(expired); entry = _float(getattr(order, "entry_price", None)); target = _float(getattr(order, "target", None)); stop = _float(getattr(order, "stop_loss", None))
    parsed = sorted(((_candle_dt(c), c) for c in candles if _candle_dt(c) is not None), key=lambda x: x[0])
    if not parsed or start is None or entry is None: return empty
    after = [(t, c) for t, c in parsed if t >= start]
    if not after: return empty
    active = [(t, c) for t, c in after if end is None or t <= end]
    post = [(t, c) for t, c in after if end is not None and t > end]
    distances = [(min(abs(float(c.low)-entry), abs(float(c.high)-entry), 0.0 if float(c.low) <= entry <= float(c.high) else float("inf")), t) for t,c in active]
    distances = [(d,t) for d,t in distances if d != float("inf")]
    touched = any(float(c.low) <= entry <= float(c.high) for _,c in active)
    touched_after = any(float(c.low) <= entry <= float(c.high) for _,c in post) if end else None
    direction = str(getattr(order, "action", "buy"))
    mfe = max(((float(c.high)-entry) if direction == "buy" else (entry-float(c.low))) for _,c in after)
    mae = max(((entry-float(c.low)) if direction == "buy" else (float(c.high)-entry)) for _,c in after)
    target_hits = [(t,c) for t,c in after if target is not None and float(c.low) <= target <= float(c.high)]
    stop_hits = [(t,c) for t,c in after if stop is not None and float(c.low) <= stop <= float(c.high)]
    first = None
    if target_hits and stop_hits:
        first = "AMBIGUOUS_INTRABAR" if target_hits[0][0] == stop_hits[0][0] else ("TARGET" if target_hits[0][0] < stop_hits[0][0] else "STOP")
    elif target_hits: first = "TARGET"
    elif stop_hits: first = "STOP"
    closest = min(distances, default=(None,None), key=lambda x:x[0])
    return {"minimum_distance_to_entry": closest[0], "entry_touched": touched, "entry_touched_after_expiration": touched_after,
        "maximum_favorable_excursion": mfe, "maximum_adverse_excursion": mae, "target_reached": bool(target_hits), "stop_reached": bool(stop_hits),
        "first_exit_event": first, "seconds_to_closest_approach": (closest[1]-start).total_seconds() if closest[1] else None,
        "seconds_to_target": (target_hits[0][0]-start).total_seconds() if target_hits else None,
        "seconds_to_stop": (stop_hits[0][0]-start).total_seconds() if stop_hits else None,
        "data_status": "PASS", "market_price_at_order_creation": float(after[0][1].close)}


def _terminal_reason(state: str, events: tuple[Any,...], analysis: dict[str,Any]) -> str:
    types = {_event_value(e,"type") for e in events}
    if "order_cancelled" in types: return "ORDER_CANCELLED"
    if "order_rejected" in types: return "ORDER_REJECTED"
    if state == "expired" and analysis["entry_touched"] is False: return "ENTRY_NOT_REACHED"
    if state == "expired": return "ORDER_EXPIRED"
    if state == "rejected": return "ORDER_REJECTED"
    if state == "pending": return "UNKNOWN"
    return "FILLED"


def _model_scenario(record: ExecutionCaptureRecord, scenario: str):
    if scenario in {"APPROVAL_PRICE_ENTRY", "CONFIRMATION_MARKET_ENTRY"}: return None
    if record.data_status != "PASS": return None
    tolerance = {"LIMIT_RETEST_CURRENT":0, "LIMIT_TOLERANCE_0_10_PERCENT":.001, "LIMIT_TOLERANCE_0_25_PERCENT":.0025, "LIMIT_TOLERANCE_0_50_PERCENT":.005}.get(scenario)
    filled = record.entry_touched
    if tolerance is not None and record.minimum_distance_to_entry is not None and record.intended_entry:
        filled = record.minimum_distance_to_entry <= abs(record.intended_entry)*tolerance
    if scenario.startswith("EXTENDED_ORDER_LIFETIME"): filled = bool(record.entry_touched or record.entry_touched_after_expiration)
    outcome = None
    fill_time = record.seconds_to_closest_approach
    target_after_fill = record.seconds_to_target is not None and (fill_time is None or record.seconds_to_target >= fill_time)
    stop_after_fill = record.seconds_to_stop is not None and (fill_time is None or record.seconds_to_stop >= fill_time)
    if filled and record.first_exit_event == "TARGET" and target_after_fill: outcome = record.target_r
    elif filled and record.first_exit_event == "STOP" and stop_after_fill: outcome = -1.0
    elif filled and record.first_exit_event == "AMBIGUOUS_INTRABAR": outcome = None
    return bool(filled), outcome


def _event_time(events, types):
    for e in events:
        if _event_value(e,"type") in types: return (e.get("timestamp") if isinstance(e,dict) else getattr(e,"timestamp",None))
    return None
def _event_value(e, field): return str((e.get(field) if isinstance(e,dict) else getattr(e,field,None)) or "").lower()
def _dt(value):
    if not value: return None
    try:
        result=datetime.fromisoformat(str(value).replace("Z","+00:00")); return result if result.tzinfo else result.replace(tzinfo=timezone.utc)
    except ValueError: return None
def _candle_dt(c):
    value=getattr(c,"timestamp",None)
    if isinstance(value,(int,float)): return datetime.fromtimestamp(value/1000 if value>10_000_000_000 else value,tz=timezone.utc)
    return _dt(str(value))
def _seconds(a,b):
    x,y=_dt(a),_dt(b); return (y-x).total_seconds() if x and y else None
def _float(v):
    try: return float(v) if v is not None else None
    except (TypeError,ValueError): return None
def _target_r(o):
    e,s,t=map(_float,(getattr(o,"entry_price",None),getattr(o,"stop_loss",None),getattr(o,"target",None)))
    return abs(t-e)/abs(e-s) if None not in (e,s,t) and e!=s else None
def _rate(n,d): return round(n/d*100,6) if d else None
def _average(values):
    x=[float(v) for v in values if v is not None]; return round(mean(x),6) if x else None
def _median(values):
    x=[float(v) for v in values if v is not None]; return round(median(x),6) if x else None
def _max_drawdown(values):
    peak=equity=draw=0.0
    for v in values: equity+=v; peak=max(peak,equity); draw=max(draw,peak-equity)
    return round(draw,6)
def _duration_days(values):
    dates=[_dt(v) for v in values]; dates=[d for d in dates if d]
    return max(1.0,(max(dates)-min(dates)).total_seconds()/86400) if dates else None
def _display(value): return "unavailable" if value is None else f"{value:.2f}%"
