from datetime import datetime,timezone
from types import SimpleNamespace
from pathlib import Path
from fastapi.testclient import TestClient
from core.market_data import Candle
from core.execution_research_capture import ExecutionResearchCapture,ExecutionResearchConfig
from core.shadow_execution_lab import ShadowExecutionLab
from app.main import app,get_execution_research_capture,get_shadow_execution_lab

def ts(m): return int(datetime(2026,8,13,12,tzinfo=timezone.utc).timestamp()) + m*60
def order(**kw):
 d=dict(order_id="o1",source_event_id="s1",symbol="BTC-USD",timeframe="5m",higher_timeframe="1h",strategy="breakout_continuation",setup="bearish_bos_retest",action="buy",entry_price=100.,stop_loss=99.,target=103.,created_at=datetime(2026,8,13,12,tzinfo=timezone.utc).isoformat(),risk_per_trade_percent=1.,order_type="limit_retest",expires_after_candles=1,status="pending",metadata={"campaign_id":"c1","market_price_at_approval":101.})
 d.update(kw); return SimpleNamespace(**d)
class Life:
 def __init__(self): self.listeners=[]; self._orders=[]
 def add_listener(self,x): self.listeners.append(x)
 def orders(self): return tuple(self._orders)
class Provider:
 provider_name="test"
 def __init__(self,c=()): self.c=list(c)
 def get_candles(self,*a): return self.c
def capture(tmp,candles=()): return ExecutionResearchCapture(lifecycle=Life(),provider=Provider(candles),config=ExecutionResearchConfig(root=str(tmp/"research"),horizon_hours=1,max_candles_per_order=50),campaign_resolver=lambda:"c1")

def test_snapshot_identifiers_persistence_dedup_and_restart(tmp_path):
 e=capture(tmp_path); s=e.capture_order(order()); assert s.snapshot.order_id=="o1" and s.snapshot.campaign_id=="c1"
 c=Candle(ts(0),101,102,100,101,1); e.capture_candles(s.snapshot.research_id,[c,c]); assert len(e.get(s.snapshot.research_id).candles)==1
 restored=capture(tmp_path); assert restored.get(s.snapshot.research_id) is not None

def test_partial_none_and_complete_horizon(tmp_path):
 e=capture(tmp_path); s=e.capture_order(order()); assert e.collect(s.snapshot.research_id).status=="INSUFFICIENT_DATA"
 e.capture_candles(s.snapshot.research_id,[Candle(ts(5),100,101,99,100,1)]); assert e.get(s.snapshot.research_id).status=="PARTIAL"
 e.capture_candles(s.snapshot.research_id,[Candle(ts(60),100,101,99,100,1)]); assert e.get(s.snapshot.research_id).status=="COMPLETE"

def test_shadow_scenarios_touch_timing_outcomes_mfe_mae(tmp_path):
 candles=[Candle(ts(0),101,101.2,100.05,101,1),Candle(ts(5),100,100.5,99.5,100,1),Candle(ts(10),102,103.2,98.8,102,1)]
 e=capture(tmp_path); s=e.capture_order(order()); e.capture_candles(s.snapshot.research_id,candles); lab=ShadowExecutionLab(e)
 current=lab.evaluate(s,"LIMIT_RETEST_CURRENT"); assert current.fill_status=="FILLED" and current.exit_status=="AMBIGUOUS_INTRABAR" and current.mfe>=3 and current.mae>=1
 assert lab.evaluate(s,"LIMIT_TOLERANCE_0_10_PERCENT").fill_status=="FILLED"
 assert lab.evaluate(s,"LIMIT_TOLERANCE_0_25_PERCENT").fill_status=="FILLED"
 assert lab.evaluate(s,"LIMIT_TOLERANCE_0_50_PERCENT").fill_status=="FILLED"
 assert lab.evaluate(s,"EXTENDED_LIFETIME_2X").fill_status=="FILLED"
 assert lab.evaluate(s,"EXTENDED_LIFETIME_4X").fill_status=="FILLED"
 assert lab.evaluate(s,"APPROVAL_PRICE_ENTRY").fill_status=="FILLED"
 assert lab.evaluate(s,"CONFIRMATION_MARKET_ENTRY").fill_status=="INSUFFICIENT_DATA"

def test_entry_before_after_never_and_aggregations(tmp_path):
 e=capture(tmp_path); a=e.capture_order(order()); e.capture_candles(a.snapshot.research_id,[Candle(ts(0),101,101.2,100,101,1)])
 b=e.capture_order(order(order_id="o2",source_event_id="s2",symbol="EUR-USD",strategy="liquidity_sweep_reversal",setup="liquidity_sweep_reversal_short")); e.capture_candles(b.snapshot.research_id,[Candle(ts(10),100,101,99,100,1)])
 report=ShadowExecutionLab(e).report(campaign_id="c1"); assert {x["asset_class"] for x in report["by_asset_class"]}=={"CRYPTO","FOREX"}; assert len(report["by_strategy"])==2 and len(report["by_setup"])==2

def test_actual_shadow_isolation_and_failure_safety(tmp_path):
 e=capture(tmp_path); s=e.capture_order(order()); before=s.actual_trade_id; report=ShadowExecutionLab(e).report(campaign_id="c1")
 assert report["actual"]["realized_r"]==0 and e.get(s.snapshot.research_id).actual_trade_id==before
 e.provider=SimpleNamespace(get_candles=lambda *a: (_ for _ in ()).throw(RuntimeError("offline"))); assert e.collect(s.snapshot.research_id).status=="ERROR"

def test_campaign_isolation_and_api(tmp_path):
 e=capture(tmp_path); e.capture_order(order(),campaign_id="c1"); e.capture_order(order(order_id="o2",source_event_id="s2"),campaign_id="c2"); lab=ShadowExecutionLab(e)
 assert len(e.orders(campaign_id="c1"))==1
 app.dependency_overrides[get_execution_research_capture]=lambda:e; app.dependency_overrides[get_shadow_execution_lab]=lambda:lab
 try:
  client=TestClient(app); assert client.get('/execution-research/summary').status_code==200; assert client.get('/shadow-execution/scenarios').status_code==200
 finally: app.dependency_overrides.clear()
