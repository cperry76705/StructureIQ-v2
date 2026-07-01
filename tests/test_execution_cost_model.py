from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from core.backtesting import BacktestRequest, BacktestResult, BacktestTrade, calculate_backtest_metrics
from core.calibration import CalibrationEngine, CalibrationRequest
from core.execution_cost_model import ExecutionCostModel, infer_asset_class, resolve_assumptions
from core.journal import TradeOutcome
from core.research_dashboard import clear_dashboard_state, store_latest_calibration


def _trade(symbol="EUR-USD", realized_r=2.0, *, strategy="trend_continuation", setup="bearish_bos_retest"):
    return BacktestTrade(
        timestamp=1, symbol=symbol, action="sell", setup_type=setup,
        strategy_type=strategy, entry=1.10000 if "USD" in symbol and symbol.startswith("EUR") else 100.0,
        stop_loss=1.10200 if symbol.startswith("EUR") else 98.0,
        target=1.09600 if symbol.startswith("EUR") else 104.0,
        estimated_risk_reward=2.0,
        outcome=TradeOutcome.WIN if realized_r > 0 else TradeOutcome.LOSS,
        realized_r=realized_r, reason="Synthetic completed trade.",
    )


def test_disabled_mode_preserves_baseline_exactly() -> None:
    result = ExecutionCostModel().model([_trade()], enabled=False)
    assert result == (None, None, (), ())


def test_enabled_costs_reduce_realistic_r_deterministically() -> None:
    kwargs = dict(enabled=True, spread_bps=2, slippage_bps=1, commission_per_trade=2, stop_slippage_bps=3, latency_ms=100, starting_balance=10_000, risk_per_trade_percent=1)
    first = ExecutionCostModel().model([_trade()], **kwargs)
    second = ExecutionCostModel().model([_trade()], **kwargs)
    assert first == second
    summary, metrics, _, trades = first
    assert trades[0].realistic_r < trades[0].baseline_r
    assert summary.realistic_total_r <= summary.baseline_total_r
    assert metrics.total_r <= summary.baseline_total_r


def test_spread_slippage_stop_and_commission_are_calculated() -> None:
    _, _, _, records = ExecutionCostModel().model(
        [_trade(realized_r=-1.0)], enabled=True, spread_bps=2,
        slippage_bps=3, stop_slippage_bps=4, commission_per_trade=5,
        starting_balance=10_000, risk_per_trade_percent=1,
    )
    item = records[0]
    assert item.spread_cost_r > 0
    assert item.slippage_cost_r > 0
    assert item.stop_slippage_cost_r > 0
    assert item.commission_cost_r == 0.05
    assert item.total_cost_r == round(item.spread_cost_r + item.slippage_cost_r + item.stop_slippage_cost_r + item.commission_cost_r + item.latency_cost_r, 6)


def test_asset_defaults_are_conservative_and_instrument_aware() -> None:
    assert infer_asset_class("BTC-USD") == "crypto"
    assert infer_asset_class("EUR-USD") == "forex"
    assert infer_asset_class("SPY") == "stocks_etfs"
    crypto = resolve_assumptions("crypto")
    forex = resolve_assumptions("forex")
    stocks = resolve_assumptions("stocks_etfs")
    assert crypto.spread_bps > stocks.spread_bps > forex.spread_bps


class _Runner:
    def run(self, request: BacktestRequest) -> BacktestResult:
        trades = (_trade(request.symbol, 2.0), _trade(request.symbol, -1.0))
        return BacktestResult(request=request, trades=trades, metrics=calculate_backtest_metrics(trades), human_readable_summary="Synthetic.", limitations=())


class _Provider:
    provider_name = "unused"
    def get_candles(self, symbol, timeframe, lookback):
        return []


def test_calibration_aggregates_costs_without_changing_baseline_metrics() -> None:
    engine = CalibrationEngine(_Provider(), backtesting_engine_factory=lambda provider: _Runner())
    base = dict(symbols=["EUR-USD"], timeframes=["5m"], higher_timeframes=["1h"], lookback=100, max_trades_per_run=10, risk_per_trade_percent=1, starting_balance=10_000)
    disabled = engine.run(CalibrationRequest(**base))
    enabled = engine.run(CalibrationRequest(**base, execution_cost_modeling=True, spread_bps=2, slippage_bps=1, commission_per_trade=2))
    assert disabled.aggregate_metrics == enabled.aggregate_metrics
    assert disabled.aggregate_execution_cost_summary is None
    assert enabled.aggregate_execution_cost_summary is not None
    assert enabled.aggregate_execution_cost_summary.realistic_total_r < enabled.aggregate_execution_cost_summary.baseline_total_r
    assert enabled.aggregate_execution_cost_summary.symbols_most_affected[0].name == "EUR-USD"


def test_dashboard_reports_execution_cost_risk_and_recommendation() -> None:
    model = ExecutionCostModel()
    summary, _, recommendations, records = model.model([_trade()], enabled=True, spread_bps=20, slippage_bps=10)
    aggregate = model.aggregate(records, summary)
    store_latest_calibration(SimpleNamespace(
        aggregate_execution_cost_summary=aggregate,
        aggregate_metrics=SimpleNamespace(win_rate=100, average_r=2, total_r=2, profit_factor=None, max_drawdown_r=0),
        setup_quality_summary=None, strategy_rating_summary=None, setup_rating_summary=None,
        recommendations=(), provider_failures=(), research_recommendations=(), research_action_items=(),
    ))
    try:
        client = TestClient(app)
        overview = client.get("/dashboard/overview").json()
        risks = client.get("/dashboard/risks").json()
        recs = client.get("/dashboard/recommendations").json()
    finally:
        clear_dashboard_state()
    assert overview["execution_cost_status"] == "enabled"
    assert overview["realistic_total_r"] <= overview["baseline_total_r_after_cost_model"]
    assert risks["execution_cost_status"] == "enabled"
    assert any(item["category"] == "execution_cost" for item in recs["recommendations"])


def test_openapi_exposes_new_request_and_response_fields() -> None:
    schema = TestClient(app).get("/openapi.json").json()["components"]["schemas"]
    for request_name in ("BacktestRequest-Input", "CalibrationRequest"):
        properties = schema[request_name]["properties"]
        for field in ("execution_cost_modeling", "spread_bps", "slippage_bps", "commission_per_trade", "stop_slippage_bps", "latency_ms"):
            assert field in properties
    assert "execution_cost_summary" in schema["BacktestResult"]["properties"]
    assert "aggregate_execution_cost_summary" in schema["CalibrationResult"]["properties"]
