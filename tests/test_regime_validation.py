from core.backtesting import BacktestTrade
from core.journal import TradeOutcome
from core.market_data import Candle
from core.regime import MarketRegime, RegimeResult
from core.regime_validation import (
    RegimeForwardObservation,
    build_forward_observation,
    build_regime_validation_summary,
)


def _forward(kind: str) -> RegimeForwardObservation:
    candles: list[Candle] = []
    for index in range(1, 21):
        if kind == "bullish":
            close = 100.0 + index * 0.2
            width = 0.2
        elif kind == "bearish":
            close = 100.0 - index * 0.2
            width = 0.2
        elif kind == "range":
            close = 100.0 + (0.02 if index % 2 else -0.02)
            width = 0.2
        elif kind == "expansion":
            close = 100.0
            width = 0.2 if index <= 10 else 1.0
        else:
            close = 100.0
            width = 1.0 if index <= 10 else 0.2
        candles.append(Candle(index, close, close + width / 2, close - width / 2, close, 1))
    observation = build_forward_observation(start_price=100.0, future_candles=candles)
    assert observation is not None
    return observation


def _record(
    regime: MarketRegime,
    timestamp: int,
    *,
    forward: RegimeForwardObservation | None = None,
    confidence: float = 80.0,
    outcome: TradeOutcome = TradeOutcome.SKIPPED,
) -> BacktestTrade:
    return BacktestTrade(
        timestamp=timestamp,
        symbol="BTC-USD",
        timeframe="5m",
        action="wait",
        setup_type="no_valid_setup",
        strategy_type="no_strategy",
        entry=None,
        stop_loss=None,
        target=None,
        estimated_risk_reward=None,
        outcome=outcome,
        realized_r=None,
        reason="Synthetic validation record.",
        market_regime=RegimeResult(
            market_regime=regime,
            regime_confidence=confidence,
            regime_reasons=("Synthetic classification.",),
            human_readable_summary="Synthetic classification.",
        ),
        regime_forward_observation=forward,
    )


def test_distribution_and_transition_dominance() -> None:
    records = [
        *[_record(MarketRegime.TRANSITION, index) for index in range(7)],
        *[_record(MarketRegime.RANGE, index + 7) for index in range(3)],
    ]
    summary = build_regime_validation_summary(records)
    transition = next(
        item for item in summary.classification_distribution
        if item.market_regime is MarketRegime.TRANSITION
    )

    assert transition.records == 7
    assert transition.percentage_of_total == 70.0
    assert summary.transition_dominance_ratio == 0.7
    assert summary.transition_is_overused is True
    assert "transition_overuse" in summary.dominant_failure_modes


def test_persistence_and_transition_exit_analysis() -> None:
    records = [
        _record(MarketRegime.TRANSITION, 1),
        _record(MarketRegime.TRANSITION, 2),
        _record(MarketRegime.STRONG_BULL_TREND, 3),
        _record(MarketRegime.TRANSITION, 4),
    ]
    summary = build_regime_validation_summary(records)
    persistence = next(
        item for item in summary.persistence_by_regime
        if item.market_regime is MarketRegime.TRANSITION
    )

    assert persistence.occurrences == 2
    assert persistence.average_duration_bars == 1.5
    assert persistence.max_duration_bars == 2
    assert persistence.median_duration_bars == 1.5
    assert summary.transition_exit_analysis.transition_records == 3
    assert summary.transition_exit_analysis.transitions_to_bullish == 2
    assert summary.transition_exit_analysis.remained_transition == 1
    assert summary.transition_exit_analysis.average_bars_to_exit_transition == 1.5


def test_forward_bullish_bearish_and_range_behavior() -> None:
    records = [
        _record(MarketRegime.STRONG_BULL_TREND, 1, forward=_forward("bullish")),
        _record(MarketRegime.STRONG_BEAR_TREND, 2, forward=_forward("bearish")),
        _record(MarketRegime.RANGE, 3, forward=_forward("range")),
    ]
    summary = build_regime_validation_summary(records)
    by_regime = {item.market_regime: item for item in summary.forward_behavior_by_regime}

    bull5 = by_regime[MarketRegime.STRONG_BULL_TREND].horizons[0]
    bear10 = by_regime[MarketRegime.STRONG_BEAR_TREND].horizons[1]
    range20 = by_regime[MarketRegime.RANGE].horizons[2]
    assert bull5.bullish_follow_through_rate == 100.0
    assert bear10.bearish_follow_through_rate == 100.0
    assert range20.range_behavior_rate == 100.0


def test_confusion_proxy_and_insufficient_forward_data_are_safe() -> None:
    records = [
        _record(MarketRegime.WEAK_BULL_TREND, 1, forward=_forward("bearish")),
        _record(MarketRegime.UNKNOWN, 2, forward=None),
    ]
    summary = build_regime_validation_summary(records)
    matrix = summary.regime_confusion_proxy.predicted_vs_actual

    assert matrix["weak_bull_trend"]["actual_bearish"] == 1
    assert summary.regime_confusion_proxy.total_compared == 1
    assert summary.regime_confusion_proxy.insufficient_forward_records == 1
    assert "insufficient_samples" in summary.dominant_failure_modes
