"""Pure, research-only shadow execution over retained order candles."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from statistics import mean, median
from typing import Any


SCENARIOS = (
    "LIMIT_RETEST_CURRENT", "LIMIT_TOLERANCE_0_10_PERCENT", "LIMIT_TOLERANCE_0_25_PERCENT",
    "LIMIT_TOLERANCE_0_50_PERCENT", "EXTENDED_LIFETIME_2X", "EXTENDED_LIFETIME_4X",
    "APPROVAL_PRICE_ENTRY", "CONFIRMATION_MARKET_ENTRY",
)


@dataclass(frozen=True)
class ShadowExecutionResult:
    research_id: str
    campaign_id: str | None
    order_id: str
    symbol: str
    asset_class: str
    strategy: str
    setup: str
    scenario: str
    fill_status: str
    fill_timestamp: str | int | None
    hypothetical_entry: float | None
    entry_slippage_vs_planned: float | None
    stop_loss: float
    target: float
    target_r: float | None
    exit_status: str
    exit_timestamp: str | int | None
    exit_price: float | None
    realized_r: float | None
    mfe: float | None
    mae: float | None
    holding_time_seconds: float | None
    label: str = "SHADOW_EXECUTION"
    accounting_status: str = "NON_REALIZED"
    research_only: bool = True


class ShadowExecutionLab:
    def __init__(self, capture: Any) -> None:
        self.capture = capture

    def evaluate(self, state: Any, scenario: str) -> ShadowExecutionResult:
        snapshot=state.snapshot; candles=sorted(state.candles,key=lambda x:_time(x["candle_timestamp"]))
        base=dict(research_id=snapshot.research_id,campaign_id=snapshot.campaign_id,order_id=snapshot.order_id,
            symbol=snapshot.symbol,asset_class=snapshot.asset_class,strategy=snapshot.strategy,setup=snapshot.setup,scenario=scenario,
            stop_loss=snapshot.stop_loss,target=snapshot.target,target_r=snapshot.target_r)
        if scenario == "CONFIRMATION_MARKET_ENTRY" or not candles:
            return ShadowExecutionResult(**base,fill_status="INSUFFICIENT_DATA",fill_timestamp=None,hypothetical_entry=None,
                entry_slippage_vs_planned=None,exit_status="INSUFFICIENT_DATA",exit_timestamp=None,exit_price=None,realized_r=None,mfe=None,mae=None,holding_time_seconds=None)
        created=_dt(snapshot.order_created_at); candle_seconds=_timeframe_seconds(snapshot.timeframe)
        actual_lifetime=max(candle_seconds, snapshot.expires_after_candles*candle_seconds)
        multiplier=4 if scenario.endswith("4X") else 2 if scenario.endswith("2X") else 1
        deadline=created+timedelta(seconds=actual_lifetime*multiplier)
        tolerance={"LIMIT_TOLERANCE_0_10_PERCENT":.001,"LIMIT_TOLERANCE_0_25_PERCENT":.0025,"LIMIT_TOLERANCE_0_50_PERCENT":.005}.get(scenario,0)
        planned=snapshot.intended_entry; approval=snapshot.market_price_at_approval or snapshot.market_price_at_order_creation
        fill=None; entry=None
        if scenario == "APPROVAL_PRICE_ENTRY":
            if approval is None:
                return ShadowExecutionResult(**base,fill_status="INSUFFICIENT_DATA",fill_timestamp=None,hypothetical_entry=None,entry_slippage_vs_planned=None,
                    exit_status="INSUFFICIENT_DATA",exit_timestamp=None,exit_price=None,realized_r=None,mfe=None,mae=None,holding_time_seconds=None)
            fill=candles[0]; entry=approval
        else:
            for candle in candles:
                when=_dt_candle(candle["candle_timestamp"])
                if when < created or when > deadline: continue
                distance=0 if candle["low"]<=planned<=candle["high"] else min(abs(candle["low"]-planned),abs(candle["high"]-planned))
                if distance <= abs(planned)*tolerance: fill=candle; entry=planned; break
        if fill is None:
            return ShadowExecutionResult(**base,fill_status="NOT_FILLED",fill_timestamp=None,hypothetical_entry=None,entry_slippage_vs_planned=None,
                exit_status="NOT_FILLED",exit_timestamp=None,exit_price=None,realized_r=None,mfe=None,mae=None,holding_time_seconds=None)
        fill_index=candles.index(fill); after=candles[fill_index:]; direction=snapshot.direction
        mfe=max(((c["high"]-entry) if direction=="buy" else (entry-c["low"])) for c in after)
        mae=max(((entry-c["low"]) if direction=="buy" else (c["high"]-entry)) for c in after)
        exit_status="OPEN_AT_HORIZON"; exit_candle=None; exit_price=None; realized=None
        for candle in after:
            target_hit=candle["low"]<=snapshot.target<=candle["high"]; stop_hit=candle["low"]<=snapshot.stop_loss<=candle["high"]
            if target_hit and stop_hit: exit_status="AMBIGUOUS_INTRABAR"; exit_candle=candle; break
            if target_hit: exit_status="WIN"; exit_candle=candle; exit_price=snapshot.target; realized=snapshot.target_r; break
            if stop_hit: exit_status="LOSS"; exit_candle=candle; exit_price=snapshot.stop_loss; realized=-1.0; break
        return ShadowExecutionResult(**base,fill_status="FILLED",fill_timestamp=fill["candle_timestamp"],hypothetical_entry=entry,
            entry_slippage_vs_planned=entry-planned,exit_status=exit_status,exit_timestamp=exit_candle["candle_timestamp"] if exit_candle else None,
            exit_price=exit_price,realized_r=realized,mfe=mfe,mae=mae,
            holding_time_seconds=(_time(exit_candle["candle_timestamp"])-_time(fill["candle_timestamp"])) if exit_candle else None)

    def report(self, *, campaign_id: str | None = None) -> dict[str, Any]:
        states=self.capture.orders(campaign_id=campaign_id); results=[self.evaluate(s,sn) for s in states for sn in SCENARIOS]
        scenario_rows=[]
        for scenario in SCENARIOS:
            rows=[r for r in results if r.scenario==scenario]; evaluable=[r for r in rows if r.fill_status!="INSUFFICIENT_DATA"]
            returns=[r.realized_r for r in rows if r.realized_r is not None]
            scenario_rows.append({"scenario":scenario,"orders":len(rows),"evaluable":len(evaluable),"hypothetical_fills":sum(r.fill_status=="FILLED" for r in rows),
                "fill_rate":_rate(sum(r.fill_status=="FILLED" for r in evaluable),len(evaluable)),"wins":sum(r.exit_status=="WIN" for r in rows),
                "losses":sum(r.exit_status=="LOSS" for r in rows),"ambiguous":sum(r.exit_status=="AMBIGUOUS_INTRABAR" for r in rows),
                "hypothetical_total_r":round(sum(returns),6),"expectancy_r":round(mean(returns),6) if returns else None,
                "max_drawdown_r":_drawdown(returns),"research_only":True,"accounting_status":"NON_REALIZED"})
        actual={"orders":len(states),"fills":sum(s.actual_trade_id is not None for s in states),"realized_r":0.0,"source":"ACTUAL_EXECUTION"}
        touch=self.entry_touches(campaign_id=campaign_id); lifetime=self.lifetime(campaign_id=campaign_id)
        return {"campaign_id":campaign_id,"actual":actual,"shadow":scenario_rows,"entry_touches":touch,"lifetime":lifetime,
            "by_symbol":self._aggregate(results,"symbol"),"by_asset_class":self._aggregate(results,"asset_class"),
            "by_strategy":self._aggregate(results,"strategy"),"by_setup":self._aggregate(results,"setup"),
            "results":[asdict(r) for r in results],"labels":["RESEARCH_ONLY","SHADOW_EXECUTION","NON_REALIZED"]}

    def entry_touches(self, *, campaign_id=None):
        rows=[]
        for state in self.capture.orders(campaign_id=campaign_id):
            s=state.snapshot; candles=sorted(state.candles,key=lambda x:_time(x["candle_timestamp"])); created=_dt(s.order_created_at)
            deadline=created+timedelta(seconds=_timeframe_seconds(s.timeframe)*s.expires_after_candles)
            touches=[c for c in candles if c["low"]<=s.intended_entry<=c["high"]]
            before=[c for c in touches if _dt_candle(c["candle_timestamp"])<=deadline]; after=[c for c in touches if _dt_candle(c["candle_timestamp"])>deadline]
            closest=min((min(abs(c["low"]-s.intended_entry),abs(c["high"]-s.intended_entry)) for c in candles),default=None)
            classification="REACHED_DURING_REAL_LIFETIME" if before else "REACHED_AFTER_EXPIRATION" if after else "NEVER_REACHED_ENTRY" if candles else "INSUFFICIENT_DATA"
            rows.append({"research_id":s.research_id,"symbol":s.symbol,"classification":classification,"entry_touched_before_actual_expiration":bool(before) if candles else None,
                "entry_touched_after_actual_expiration":bool(after) if candles else None,"closest_price_to_entry":s.intended_entry if touches else None,
                "distance_to_entry_at_closest":closest,"distance_to_entry_percent":closest/abs(s.intended_entry)*100 if closest is not None and s.intended_entry else None,
                "time_to_entry_touch":_time(touches[0]["candle_timestamp"])-created.timestamp() if touches else None,"entry_touch_count":len(touches)})
        return rows

    def lifetime(self, *, campaign_id=None):
        touches=self.entry_touches(campaign_id=campaign_id); states=self.capture.orders(campaign_id=campaign_id)
        lifetimes=[_timeframe_seconds(s.snapshot.timeframe)*s.snapshot.expires_after_candles for s in states]
        times=[r["time_to_entry_touch"] for r in touches if r["time_to_entry_touch"] is not None]
        return {"median_actual_lifetime_seconds":median(lifetimes) if lifetimes else None,"median_time_to_entry_seconds":median(times) if times else None,
            "percent_touched_within_1x":_touch_percent(states,touches,1),"percent_touched_within_2x":_touch_percent(states,touches,2),
            "percent_touched_within_4x":_touch_percent(states,touches,4),"percent_never_touched":_rate(sum(r["classification"]=="NEVER_REACHED_ENTRY" for r in touches),len(touches))}

    def _aggregate(self, results, field):
        groups=defaultdict(list)
        for r in results: groups[getattr(r,field)].append(r)
        output=[]
        for name,rows in sorted(groups.items()):
            scenarios={}
            for scenario in SCENARIOS:
                subset=[r for r in rows if r.scenario==scenario and r.fill_status!="INSUFFICIENT_DATA"]
                returns=[r.realized_r for r in subset if r.realized_r is not None]
                scenarios[scenario]={"fill_rate":_rate(sum(r.fill_status=="FILLED" for r in subset),len(subset)),"total_r":sum(returns),"expectancy":mean(returns) if returns else None}
            output.append({field:name,"approved_orders":len({r.research_id for r in rows}),"scenarios":scenarios})
        return output


def _timeframe_seconds(value):
    value=str(value).lower(); return int(value[:-1])*60 if value.endswith("m") else int(value[:-1])*3600 if value.endswith("h") else 300
def _dt(value):
    r=datetime.fromisoformat(str(value).replace("Z","+00:00")); return r if r.tzinfo else r.replace(tzinfo=timezone.utc)
def _dt_candle(value): return datetime.fromtimestamp(_time(value),tz=timezone.utc)
def _time(value):
    if isinstance(value,(int,float)): return value/1000 if value>10_000_000_000 else value
    return _dt(value).timestamp()
def _rate(n,d): return round(n/d*100,6) if d else None
def _drawdown(values):
    peak=equity=draw=0.0
    for v in values: equity+=v; peak=max(peak,equity); draw=max(draw,peak-equity)
    return round(draw,6)
def _touch_percent(states,touches,multiplier):
    count=0
    for s,r in zip(states,touches):
        limit=_timeframe_seconds(s.snapshot.timeframe)*s.snapshot.expires_after_candles*multiplier
        count+=r["time_to_entry_touch"] is not None and r["time_to_entry_touch"]<=limit
    return _rate(count,len(states))
