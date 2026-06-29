from fastapi.testclient import TestClient

from app.main import app, get_market_data_provider
from core.backtesting import BacktestTrade
from core.journal import TradeOutcome
from core.market_data import Candle
from core.regime import MarketRegime, RegimeResult
from core.regime_forward_validation import (
    build_classifier_forward_validation,
    build_forward_validation_comparison,
    build_forward_validation_observation,
)


def _forward(kind: str) -> list[Candle]:
    candles: list[Candle] = []
    for index in range(1, 21):
        if kind == "bullish":
            close = 100.0 + index * 0.25
        elif kind == "bearish":
            close = 100.0 - index * 0.25
        else:
            close = 100.0 + (0.02 if index % 2 else -0.02)
        candles.append(
            Candle(index, close, close + 0.1, close - 0.1, close, 100)
        )
    return candles


def _result(regime: MarketRegime, confidence: float = 82.0) -> RegimeResult:
    return RegimeResult(
        market_regime=regime,
        regime_confidence=confidence,
        regime_reasons=("Synthetic prediction.",),
        human_readable_summary="Synthetic prediction.",
    )


def _record(
    legacy: MarketRegime,
    tuned: MarketRegime,
    behavior: str,
    *,
    timestamp: int = 1,
) -> BacktestTrade:
    observation = build_forward_validation_observation(
        start_price=100.0,
        future_candles=_forward(behavior),
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
        reason="Synthetic validation record.",
        market_regime=_result(legacy),
        tuned_market_regime=_result(tuned, confidence=76.0),
        regime_forward_validation_observation=observation,
    )


def test_legacy_and_tuned_validate_the_exact_same_records() -> None:
    records = [
        _record(MarketRegime.TRANSITION, MarketRegime.STRONG_BULL_TREND, "bullish"),
        _record(
            MarketRegime.TRANSITION,
            MarketRegime.STRONG_BEAR_TREND,
            "bearish",
            timestamp=2,
        ),
    ]

    legacy = build_classifier_forward_validation(records, classifier="legacy")
    tuned = build_classifier_forward_validation(records, classifier="tuned")

    assert legacy.statistical_summary.record_count == 2
    assert tuned.statistical_summary.record_count == 2
    assert legacy.statistical_summary.evaluated_predictions == 6
    assert tuned.statistical_summary.evaluated_predictions == 6
    assert tuned.overall_accuracy.value > legacy.overall_accuracy.value


def test_confusion_reliability_persistence_and_forward_statistics_are_generated() -> None:
    records = [
        _record(
            MarketRegime.STRONG_BULL_TREND,
            MarketRegime.STRONG_BULL_TREND,
            "bullish",
        ),
        _record(MarketRegime.RANGE, MarketRegime.RANGE, "range", timestamp=2),
    ]

    result = build_classifier_forward_validation(records, classifier="legacy")

    assert result.confusion_matrix["strong_bull_trend"]["strong_bull_trend"] == 3
    assert len(result.confidence_reliability_curve) == 6
    assert sum(point.sample_size for point in result.confidence_reliability_curve) == 6
    assert len(result.regime_persistence_validation) == len(MarketRegime)
    assert result.overall_accuracy.sample_size == 6
    assert result.overall_accuracy.confidence_interval_high >= result.overall_accuracy.value
    horizon = result.statistical_summary.horizons[0]
    assert horizon.sample_size == 2
    assert horizon.average_maximum_favorable_excursion > 0
    assert horizon.average_maximum_adverse_excursion >= 0


def test_comparison_metrics_and_low_sample_flags() -> None:
    records = [
        _record(MarketRegime.TRANSITION, MarketRegime.STRONG_BULL_TREND, "bullish")
    ]
    legacy = build_classifier_forward_validation(records, classifier="legacy")
    tuned = build_classifier_forward_validation(records, classifier="tuned")

    comparison = build_forward_validation_comparison(legacy, tuned)

    assert comparison.shared_record_count == 1
    assert comparison.shared_evaluation_count == 3
    assert comparison.overall_accuracy_delta > 0
    assert comparison.best_classifier == "tuned"
    assert "LOW_SAMPLE" in legacy.statistical_summary.flags
    assert "HIGH_CONFIDENCE" in legacy.statistical_summary.flags
    assert any("LOW_SAMPLE" in item for item in comparison.recommendations)


class _Provider:
    def get_candles(self, symbol: str, timeframe: str, lookback: int) -> list[Candle]:
        del symbol, timeframe
        candles = [
            Candle(index, 100 + index * 0.1, 100.2 + index * 0.1, 99.8 + index * 0.1, 100 + index * 0.1, 100)
            for index in range(80)
        ]
        return candles[-lookback:]


def _payload(*, mode: str, forward_validation: bool) -> dict[str, object]:
    return {
        "symbols": ["BTC-USD"],
        "timeframes": ["5m"],
        "higher_timeframes": ["1h"],
        "lookback": 70,
        "max_trades_per_run": 5,
        "regime_classifier_mode": mode,
        "forward_validation": forward_validation,
    }


def test_forward_validation_runs_only_in_compare_mode() -> None:
    app.dependency_overrides[get_market_data_provider] = lambda: _Provider()
    try:
        client = TestClient(app)
        legacy = client.post(
            "/calibrate", json=_payload(mode="legacy", forward_validation=True)
        )
        compare = client.post(
            "/calibrate", json=_payload(mode="compare", forward_validation=True)
        )
    finally:
        app.dependency_overrides.clear()

    assert legacy.status_code == 200
    assert legacy.json()["legacy_forward_validation"] is None
    assert compare.status_code == 200
    assert compare.json()["legacy_forward_validation"] is not None
    assert compare.json()["tuned_forward_validation"] is not None
    assert compare.json()["forward_validation_comparison"] is not None


def test_omitted_validation_and_enabled_validation_preserve_trade_metrics() -> None:
    app.dependency_overrides[get_market_data_provider] = lambda: _Provider()
    try:
        client = TestClient(app)
        ordinary = client.post(
            "/calibrate", json=_payload(mode="compare", forward_validation=False)
        )
        validated = client.post(
            "/calibrate", json=_payload(mode="compare", forward_validation=True)
        )
    finally:
        app.dependency_overrides.clear()

    assert ordinary.status_code == 200
    assert ordinary.json()["legacy_forward_validation"] is None
    assert ordinary.json()["tuned_forward_validation"] is None
    assert ordinary.json()["forward_validation_comparison"] is None
    assert validated.status_code == 200
    assert ordinary.json()["aggregate_metrics"] == validated.json()["aggregate_metrics"]
    assert ordinary.json()["aggregate_skip_diagnostics"] == validated.json()["aggregate_skip_diagnostics"]
