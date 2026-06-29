from fastapi.testclient import TestClient

from app.main import app, get_market_data_provider
from core.backtesting import BacktestTrade
from core.journal import TradeOutcome
from core.market_data import Candle
from core.regime import MarketRegime, RegimeResult
from core.regime_confidence import (
    build_classifier_confidence_calibration,
    build_regime_confidence_summary,
)
from core.regime_forward_validation import build_forward_validation_observation


def _forward(direction: int) -> list[Candle]:
    return [
        Candle(
            index,
            100 + direction * index * 0.25,
            100.1 + direction * index * 0.25,
            99.9 + direction * index * 0.25,
            100 + direction * index * 0.25,
            100,
        )
        for index in range(1, 21)
    ]


def _record(
    *,
    direction: int,
    legacy_confidence: float,
    tuned_confidence: float,
    timestamp: int,
) -> BacktestTrade:
    observation = build_forward_validation_observation(
        start_price=100.0,
        future_candles=_forward(direction),
    )
    assert observation is not None
    return BacktestTrade(
        timestamp=timestamp,
        symbol="BTC-USD",
        action="wait",
        setup_type="no_valid_setup",
        strategy_type="no_strategy",
        entry=None,
        stop_loss=None,
        target=None,
        estimated_risk_reward=None,
        outcome=TradeOutcome.SKIPPED,
        realized_r=None,
        reason="Synthetic confidence record.",
        market_regime=RegimeResult(
            MarketRegime.STRONG_BULL_TREND,
            legacy_confidence,
            ("Synthetic legacy prediction.",),
            "Synthetic legacy prediction.",
        ),
        tuned_market_regime=RegimeResult(
            MarketRegime.STRONG_BULL_TREND,
            tuned_confidence,
            ("Synthetic tuned prediction.",),
            "Synthetic tuned prediction.",
        ),
        regime_forward_validation_observation=observation,
    )


def _records() -> list[BacktestTrade]:
    return [
        _record(
            direction=1,
            legacy_confidence=80.0,
            tuned_confidence=60.0,
            timestamp=1,
        ),
        _record(
            direction=-1,
            legacy_confidence=90.0,
            tuned_confidence=60.0,
            timestamp=2,
        ),
    ]


def test_reliability_ece_mce_brier_and_distribution() -> None:
    result = build_classifier_confidence_calibration(
        _records(), classifier="legacy"
    )
    bucket_80 = next(
        item for item in result.reliability_buckets
        if item.confidence_band == "80-89"
    )
    bucket_90 = next(
        item for item in result.reliability_buckets
        if item.confidence_band == "90-100"
    )

    assert bucket_80.sample_size == 3
    assert bucket_80.average_confidence == 80.0
    assert bucket_80.observed_accuracy == 100.0
    assert bucket_80.calibration_gap == -20.0
    assert bucket_90.observed_accuracy == 0.0
    assert result.ece == 55.0
    assert result.mce == 90.0
    assert result.brier_score == 0.425
    assert len(result.reliability_curve) == 2
    assert result.confidence_distribution.mean == 85.0
    assert result.confidence_distribution.median == 85.0
    assert result.confidence_distribution.standard_deviation == 5.0
    assert result.confidence_distribution.percentiles["p90"] == 90.0


def test_overconfidence_mapping_simulations_and_recommendation_are_deterministic() -> None:
    first = build_classifier_confidence_calibration(_records(), classifier="legacy")
    second = build_classifier_confidence_calibration(_records(), classifier="legacy")

    assert first == second
    assert first.overconfidence_analysis.systematic_overconfidence is True
    assert first.overconfidence_analysis.well_calibrated is False
    assert {item.mapping for item in first.mapping_simulations} == {
        "identity",
        "linear_compression",
        "temperature_scaling",
        "isotonic_approximation",
        "piecewise_calibration",
    }
    assert all(item.classification_unchanged for item in first.mapping_simulations)
    assert all(item.expected_routing_unchanged for item in first.mapping_simulations)
    assert first.recommended_mapping.best_mapping == "isotonic_approximation"
    assert first.recommended_mapping.expected_ece_reduction > 0
    assert first.recommended_mapping.research_confidence == "low"


def test_legacy_tuned_confidence_comparison_is_returned() -> None:
    summary = build_regime_confidence_summary(_records())

    assert summary.legacy.sample_size == summary.tuned.sample_size == 6
    assert summary.legacy_vs_tuned_confidence.ece_improvement > 0
    assert summary.legacy_vs_tuned_confidence.mce_improvement > 0
    assert summary.legacy_vs_tuned_confidence.brier_improvement > 0
    assert summary.legacy_vs_tuned_confidence.confidence_reduction == 25.0
    assert summary.recommended_mapping == summary.tuned.recommended_mapping


class _Provider:
    def get_candles(self, symbol: str, timeframe: str, lookback: int) -> list[Candle]:
        del symbol, timeframe
        candles = [
            Candle(
                index,
                100 + index * 0.1,
                100.2 + index * 0.1,
                99.8 + index * 0.1,
                100 + index * 0.1,
                100,
            )
            for index in range(80)
        ]
        return candles[-lookback:]


def _payload(*, confidence_analysis: bool, forward_validation: bool = True):
    return {
        "symbols": ["BTC-USD"],
        "timeframes": ["5m"],
        "higher_timeframes": ["1h"],
        "lookback": 70,
        "max_trades_per_run": 5,
        "regime_classifier_mode": "compare",
        "forward_validation": forward_validation,
        "regime_confidence_analysis": confidence_analysis,
    }


def test_confidence_summary_is_gated_by_request_and_forward_data() -> None:
    app.dependency_overrides[get_market_data_provider] = lambda: _Provider()
    try:
        client = TestClient(app)
        omitted = client.post("/calibrate", json=_payload(confidence_analysis=False))
        no_forward = client.post(
            "/calibrate",
            json=_payload(confidence_analysis=True, forward_validation=False),
        )
        enabled = client.post("/calibrate", json=_payload(confidence_analysis=True))
    finally:
        app.dependency_overrides.clear()

    assert omitted.status_code == no_forward.status_code == enabled.status_code == 200
    assert omitted.json()["regime_confidence_summary"] is None
    assert no_forward.json()["regime_confidence_summary"] is None
    assert enabled.json()["regime_confidence_summary"] is not None


def test_confidence_analysis_does_not_change_trade_metrics() -> None:
    app.dependency_overrides[get_market_data_provider] = lambda: _Provider()
    try:
        client = TestClient(app)
        baseline = client.post("/calibrate", json=_payload(confidence_analysis=False))
        analyzed = client.post("/calibrate", json=_payload(confidence_analysis=True))
    finally:
        app.dependency_overrides.clear()

    assert baseline.status_code == analyzed.status_code == 200
    assert baseline.json()["aggregate_metrics"] == analyzed.json()["aggregate_metrics"]
    assert baseline.json()["aggregate_skip_diagnostics"] == analyzed.json()["aggregate_skip_diagnostics"]
