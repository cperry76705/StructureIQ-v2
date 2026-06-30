from math import sin

from fastapi.testclient import TestClient

from app.main import app, get_market_data_provider
from core.market_data import Candle, MarketDataError


class FailingProvider:
    def get_candles(self, symbol: str, timeframe: str, lookback: int) -> list[Candle]:
        del symbol, timeframe, lookback
        raise MarketDataError("test provider is offline")


class SyntheticProvider:
    def get_candles(self, symbol: str, timeframe: str, lookback: int) -> list[Candle]:
        del symbol, timeframe, lookback
        candles: list[Candle] = []
        for index in range(60):
            close = 100 + index * 0.4 + sin(index * 0.8) * 3
            candles.append(Candle(index, close - 0.2, close + 1, close - 1, close, 100))
        return candles


def test_analysis_contract_keeps_legacy_fields_and_adds_engine_results() -> None:
    app.dependency_overrides[get_market_data_provider] = lambda: SyntheticProvider()
    try:
        response = TestClient(app).post(
            "/analysis",
            json={
                "symbol": "BTC-USD",
                "timeframe": "5m",
                "higher_timeframe": "1h",
                "lookback": 200,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    legacy_fields = {
        "symbol",
        "timeframe",
        "higher_timeframe_bias",
        "current_structure",
        "action",
        "setup",
        "confidence",
        "entry_zone",
        "stop_loss",
        "target",
        "reasons",
    }
    assert legacy_fields < set(payload)
    assert set(payload) - legacy_fields == {
        "multi_timeframe",
        "decision",
        "setup_plan",
        "strategy",
        "trader_analysis",
        "market_regime",
        "score_summary",
    }
    assert set(payload["market_regime"]) == {
        "market_regime",
        "regime_confidence",
        "regime_reasons",
        "human_readable_summary",
    }
    assert set(payload["multi_timeframe"]) == {
        "higher_timeframe",
        "current_timeframe",
        "higher_timeframe_trend",
        "current_timeframe_trend",
        "higher_timeframe_phase",
        "current_timeframe_phase",
        "alignment",
        "alignment_score",
        "directional_bias",
        "reasons",
        "human_readable_summary",
    }
    assert payload["multi_timeframe"]["higher_timeframe"] == "1h"
    assert payload["multi_timeframe"]["current_timeframe"] == "5m"
    assert set(payload["decision"]) == {
        "action",
        "confidence",
        "score_breakdown",
        "positive_evidence",
        "negative_evidence",
        "neutral_evidence",
        "risk_notes",
        "invalidation_notes",
        "human_readable_summary",
        "decision_diagnostics",
    }
    assert set(payload["decision"]["decision_diagnostics"]) == {
        "raw_score",
        "final_confidence",
        "intended_direction",
        "confidence_band",
        "blocked_by",
        "gate_results",
        "human_readable_summary",
    }
    assert payload["decision"]["decision_diagnostics"]["gate_results"]
    decision = payload["decision"]
    expected_legacy_action = (
        "no_trade" if decision["action"] == "avoid" else decision["action"]
    )
    assert payload["action"] == expected_legacy_action
    assert payload["confidence"] == round(decision["confidence"] / 10, 1)
    assert set(payload["setup_plan"]) == {
        "setup_type",
        "setup_status",
        "direction",
        "setup_quality_score",
        "entry_zone",
        "stop_loss",
        "target",
        "estimated_risk_reward",
        "entry_conditions",
        "invalidation_rules",
        "supporting_evidence",
        "warning_notes",
        "human_readable_summary",
            "setup_level_diagnostics",
            "setup_candidate_diagnostics",
        }
    assert set(payload["setup_plan"]["setup_level_diagnostics"]) == {
        "setup_type",
        "setup_status",
        "entry_zone_source",
        "stop_loss_source",
        "target_source",
        "latest_swing_high",
        "latest_swing_low",
        "nearest_support",
        "nearest_resistance",
        "level_quality",
        "human_readable_summary",
    }
    assert payload["setup"] == payload["setup_plan"]["setup_type"]
    assert set(payload["strategy"]) == {
        "preferred_strategy",
        "candidates",
        "strategy_alignment",
        "human_readable_summary",
    }
    assert payload["strategy"]["candidates"]
    assert set(payload["strategy"]["candidates"][0]) == {
        "strategy_type",
        "status",
        "direction",
        "score",
        "score_breakdown",
        "supporting_evidence",
        "opposing_evidence",
        "required_conditions",
        "invalidation",
        "notes",
    }
    assert set(payload["trader_analysis"]) == {
        "headline",
        "summary",
        "recommendation",
        "market_narrative",
        "why",
        "trade_plan",
        "key_risks",
        "confidence_interpretation",
        "next_best_action",
    }
    assert set(payload["trader_analysis"]["trade_plan"]) == {
        "status",
        "setup_type",
        "direction",
        "entry_zone",
        "stop_loss",
        "target",
        "estimated_risk_reward",
        "wait_for",
        "invalidation",
        "notes",
    }


def test_analysis_returns_informative_503_when_provider_fails() -> None:
    app.dependency_overrides[get_market_data_provider] = lambda: FailingProvider()
    try:
        response = TestClient(app).post(
            "/analysis",
            json={
                "symbol": "BTC-USD",
                "timeframe": "5m",
                "higher_timeframe": "1h",
                "lookback": 200,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Market data unavailable: test provider is offline"
    }


def test_calibration_returns_controlled_result_when_all_provider_runs_fail() -> None:
    app.dependency_overrides[get_market_data_provider] = lambda: FailingProvider()
    try:
        response = TestClient(app).post(
            "/calibrate",
            json={
                "symbols": ["BTC-USD"],
                "timeframes": ["15m"],
                "higher_timeframes": ["1h"],
                "lookback": 300,
                "max_trades_per_run": 50,
                "risk_per_trade_percent": 1,
                "starting_balance": 10000,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["aggregate_metrics"]["total_runs"] == 0
    assert payload["aggregate_metrics"]["total_trades"] == 0
    assert payload["failed_runs"] == 1
    assert payload["provider_failures"][0]["symbol"] == "BTC-USD"
    assert payload["data_availability_summary"]["all_runs_failed"] is True
