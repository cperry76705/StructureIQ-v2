from fastapi.testclient import TestClient

from app.main import app, get_market_data_provider, get_symbol_profile_engine
from core.market_data import Candle
from core.symbol_profile_engine import SymbolProfileEngine


class _ResearchProvider:
    def get_candles(self, symbol: str, timeframe: str, lookback: int) -> list[Candle]:
        del symbol, timeframe, lookback
        candles: list[Candle] = []
        price = 100.0
        for index in range(100):
            drift = 0.6 if (index // 12) % 2 == 0 else -0.45
            close = price + drift
            candles.append(
                Candle(index, price, max(price, close) + 0.3, min(price, close) - 0.3, close, 1000.0)
            )
            price = close
        return candles


REQUIRED_PAYLOAD = {
    "symbols": ["BTC-USD"],
    "timeframes": ["5m"],
    "higher_timeframes": ["1h"],
    "lookback": 5000,
    "max_trades_per_run": 400,
    "risk_per_trade_percent": 1,
    "starting_balance": 10000,
    "out_of_sample_validation": True,
    "validation_method": "walk_forward",
    "training_percent": 70,
    "validation_percent": 30,
    "validation_folds": 5,
    "monte_carlo_analysis": True,
    "monte_carlo_simulations": 1000,
    "monte_carlo_random_seed": 42,
    "statistical_validation_analysis": True,
    "regime_classifier_mode": "compare",
    "forward_validation": True,
    "regime_confidence_analysis": True,
}


REQUIRED_NON_NULL_FIELDS = (
    "out_of_sample_summary",
    "validation_fold_results",
    "generalization_summary",
    "overfitting_summary",
    "stability_summary",
    "symbol_validation_summary",
    "timeframe_validation_summary",
    "research_pipeline_summary",
    "walk_forward_intelligence_summary",
    "strategy_robustness_rankings",
    "promotion_readiness_summary",
    "monte_carlo_summary",
    "monte_carlo_report",
    "monte_carlo_risk_summary",
    "statistical_validation_summary",
    "edge_decay_summary",
    "weakness_detection_summary",
    "legacy_market_regime_summary",
    "tuned_market_regime_summary",
    "regime_classifier_comparison",
    "legacy_forward_validation",
    "tuned_forward_validation",
    "forward_validation_comparison",
    "regime_confidence_summary",
    "symbol_profile_summary",
    "aggregate_adaptive_strategy_router_summary",
    "research_lab_summary",
    "research_rankings",
    "performance_matrices",
    "research_statistics",
    "aggregate_score_summary",
    "aggregate_execution_intelligence_summary",
    "aggregate_confidence_calibration_summary",
    "strategy_rating_summary",
    "setup_rating_summary",
)


def _post(payload: dict) -> dict:
    profiles = SymbolProfileEngine(path=None)
    app.dependency_overrides[get_market_data_provider] = lambda: _ResearchProvider()
    app.dependency_overrides[get_symbol_profile_engine] = lambda: profiles
    try:
        response = TestClient(app).post("/calibrate", json=payload)
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200, response.text
    return response.json()


def test_required_research_payload_populates_enabled_and_always_on_fields() -> None:
    payload = _post(REQUIRED_PAYLOAD)
    missing = [name for name in REQUIRED_NON_NULL_FIELDS if payload[name] is None]
    assert missing == []
    # Empty research samples are explicit rather than silently omitted.
    assert "available" in payload["monte_carlo_summary"]
    assert "available" in payload["statistical_validation_summary"]


def test_disabled_optional_research_fields_remain_null() -> None:
    payload = _post(
        {
            "symbols": ["BTC-USD"],
            "timeframes": ["5m"],
            "higher_timeframes": ["1h"],
            "lookback": 100,
            "max_trades_per_run": 5,
            "risk_per_trade_percent": 1,
            "starting_balance": 10000,
        }
    )
    assert payload["out_of_sample_summary"] is None
    assert payload["monte_carlo_summary"] is None
    assert payload["statistical_validation_summary"] is None
    assert payload["regime_confidence_summary"] is None
    assert payload["execution_sensitivity_summary"] is None
    assert payload["entry_timing_summary"] is None
    assert payload["market_regime_summary"] is None
    assert payload["symbol_profile_summary"] is not None
    assert payload["aggregate_adaptive_strategy_router_summary"] is not None


def test_analytics_do_not_change_production_calibration_metrics() -> None:
    baseline_request = {
        "symbols": ["BTC-USD"],
        "timeframes": ["5m"],
        "higher_timeframes": ["1h"],
        "lookback": 100,
        "max_trades_per_run": 20,
        "risk_per_trade_percent": 1,
        "starting_balance": 10000,
    }
    baseline = _post(baseline_request)
    researched = _post({**baseline_request, **{
        key: value
        for key, value in REQUIRED_PAYLOAD.items()
        if key not in {"lookback", "max_trades_per_run"}
    }})
    assert researched["aggregate_metrics"] == baseline["aggregate_metrics"]


def test_openapi_exposes_all_research_flags() -> None:
    schemas = TestClient(app).get("/openapi.json").json()["components"]["schemas"]
    request_fields = schemas["CalibrationRequest"]["properties"]
    for field in (
        "out_of_sample_validation",
        "validation_method",
        "training_percent",
        "validation_percent",
        "validation_folds",
        "monte_carlo_analysis",
        "monte_carlo_simulations",
        "monte_carlo_random_seed",
        "statistical_validation_analysis",
        "regime_classifier_mode",
        "forward_validation",
        "regime_confidence_analysis",
    ):
        assert field in request_fields
