from math import sin

from fastapi.testclient import TestClient

from app.main import app, get_market_data_provider
from core.market_data import Candle


class _Provider:
    def get_candles(self, symbol: str, timeframe: str, lookback: int) -> list[Candle]:
        del symbol, timeframe
        candles = []
        for index in range(320):
            close = 100 + index * 0.08 + sin(index * 0.7) * 2
            candles.append(
                Candle(index, close - 0.2, close + 0.8, close - 0.8, close, 100)
            )
        return candles[-lookback:]


def _request(enabled: bool) -> dict:
    return {
        "symbols": ["BTC-USD"],
        "timeframes": ["5m"],
        "higher_timeframes": ["1h"],
        "lookback": 300,
        "max_trades_per_run": 50,
        "risk_per_trade_percent": 1,
        "starting_balance": 10000,
        "out_of_sample_validation": enabled,
        "validation_method": "walk_forward",
        "training_percent": 70,
        "validation_percent": 30,
        "validation_folds": 3,
    }


def test_pipeline_fields_require_oos_and_do_not_change_production_metrics() -> None:
    app.dependency_overrides[get_market_data_provider] = lambda: _Provider()
    try:
        client = TestClient(app)
        baseline = client.post("/calibrate", json=_request(False))
        researched = client.post("/calibrate", json=_request(True))
    finally:
        app.dependency_overrides.clear()

    assert baseline.status_code == researched.status_code == 200
    baseline_payload = baseline.json()
    research_payload = researched.json()
    fields = (
        "research_pipeline_summary",
        "walk_forward_intelligence_summary",
        "strategy_robustness_rankings",
        "promotion_readiness_summary",
        "research_action_items",
    )
    assert all(baseline_payload[field] is None for field in fields)
    assert all(research_payload[field] is not None for field in fields)
    assert research_payload["research_action_items"]
    assert all(isinstance(item, str) for item in research_payload["research_action_items"])
    assert (
        research_payload["aggregate_metrics"]
        == baseline_payload["aggregate_metrics"]
    )
    assert "unified research pipeline" in (
        research_payload["research_pipeline_summary"]["human_readable_summary"].lower()
    )

