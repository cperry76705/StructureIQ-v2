from math import sin

from fastapi.testclient import TestClient

from app.main import app, get_market_data_provider
from core.market_data import Candle
from core.statistical_validation import build_statistical_validation


def test_stable_profitable_sample_has_low_weakness() -> None:
    result = build_statistical_validation(
        [1.0, -0.5] * 60,
        fold_expectancies=[0.25] * 5,
    )

    assert result.statistical_validation_summary.overall_status == "PASS"
    assert result.statistical_validation_summary.profitable is True
    assert result.weakness_detection_summary.weakness_flags == ()
    assert result.weakness_detection_summary.weakness_score < 25
    assert result.fold_stability_summary.fold_stability_score == 100.0


def test_profitable_outlier_dependent_sample_is_flagged() -> None:
    result = build_statistical_validation([-0.1] * 119 + [20.0])

    assert result.statistical_validation_summary.profitable is True
    assert result.trade_distribution_summary.top_10_percent_trade_contribution == 100.0
    assert "HIGH_OUTLIER_DEPENDENCY" in result.weakness_detection_summary.weakness_flags
    assert "PROFIT_CONCENTRATION" in result.weakness_detection_summary.weakness_flags


def test_profitable_decaying_sample_flags_negative_recent_expectancy() -> None:
    result = build_statistical_validation([1.0] * 40 + [0.5] * 40 + [-0.2] * 40)

    assert result.statistical_validation_summary.profitable is True
    assert result.edge_decay_summary.expectancy_final_third < 0
    assert result.edge_decay_summary.edge_decay_score >= 70
    assert "EDGE_DECAY" in result.weakness_detection_summary.weakness_flags
    assert "NEGATIVE_RECENT_EXPECTANCY" in result.weakness_detection_summary.weakness_flags
    assert result.weakness_detection_summary.readiness_blocked is True


def test_high_fold_variance_is_flagged_and_blocks_readiness() -> None:
    result = build_statistical_validation(
        [1.0, -0.5] * 60,
        fold_expectancies=[3.0, -3.0, 3.0, -3.0],
    )

    assert result.fold_stability_summary.fold_stability_score < 50
    assert "FOLD_INSTABILITY" in result.weakness_detection_summary.weakness_flags
    assert result.weakness_detection_summary.readiness_blocked is True


def test_distribution_and_losing_streak_metrics_are_populated() -> None:
    result = build_statistical_validation(
        [-2.0, -1.0, -0.5, 0.0, 0.5, 1.0, 2.0, 3.0, 6.0] * 12
    )
    buckets = result.trade_distribution_summary.r_distribution_buckets

    assert sum(buckets.values()) == 108
    assert buckets["below_-1R"] == 12
    assert buckets["above_5R"] == 12
    assert result.losing_streak_summary.probability_of_3_losses_in_row > 0
    assert result.losing_streak_summary.worst_observed_losing_streak == 3
    assert result.losing_streak_summary.human_readable_summary


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
        "statistical_validation_analysis": enabled,
    }


def test_statistical_api_fields_are_additive_and_metrics_unchanged() -> None:
    app.dependency_overrides[get_market_data_provider] = lambda: _Provider()
    try:
        client = TestClient(app)
        baseline = client.post("/calibrate", json=_request(False))
        validated = client.post("/calibrate", json=_request(True))
    finally:
        app.dependency_overrides.clear()

    assert baseline.status_code == validated.status_code == 200
    baseline_payload = baseline.json()
    validated_payload = validated.json()
    fields = (
        "statistical_validation_summary",
        "losing_streak_summary",
        "trade_distribution_summary",
        "edge_decay_summary",
        "fold_stability_summary",
        "weakness_detection_summary",
    )
    assert all(baseline_payload[field] is None for field in fields)
    assert all(validated_payload[field] is not None for field in fields)
    assert baseline_payload["aggregate_metrics"] == validated_payload["aggregate_metrics"]

