from core.out_of_sample import (
    GeneralizationSummary,
    OutOfSampleSummary,
    OverfittingSummary,
    StabilitySummary,
    ValidationCategoryPerformance,
    ValidationFoldResult,
    ValidationMeasurements,
    ValidationMethod,
)
from core.walk_forward_intelligence import (
    PromotionReadiness,
    build_walk_forward_intelligence,
)
from core.monte_carlo import MonteCarloRiskSummary
from core.monte_carlo_reporting import build_monte_carlo_report
from core.monte_carlo import run_monte_carlo
from core.statistical_validation import build_statistical_validation


def _measurement(trades: int, expectancy: float, drawdown: float = 1.0):
    return ValidationMeasurements(
        records=trades * 2,
        trades=trades,
        win_rate=60.0 if expectancy > 0 else 35.0,
        average_r=expectancy,
        total_r=expectancy * trades,
        profit_factor=2.0 if expectancy > 0 else 0.6,
        maximum_drawdown=drawdown,
        expectancy=expectancy,
        average_mfe=1.5,
        average_mae=0.7,
        average_trade_duration=4.0,
        skipped_records=trades,
        confidence_distribution={"70-79": trades},
        average_confidence=75.0,
        setup_distribution={"bearish_bos_retest": trades},
        strategy_distribution={"breakout_continuation": trades},
        regime_distribution={"strong_bear_trend": trades},
        execution_degradation=0.1,
        trade_management_sensitivity={"none": expectancy * trades},
    )


def _category(trades: int, expectancy: float, drawdown: float = 1.0):
    return ValidationCategoryPerformance(
        trades=trades,
        win_rate=60.0 if expectancy > 0 else 35.0,
        expectancy=expectancy,
        profit_factor=2.0 if expectancy > 0 else 0.6,
        maximum_drawdown=drawdown,
    )


def _fold(number: int, trades: int, expectancy: float) -> ValidationFoldResult:
    category = {"bearish_bos_retest": _category(trades, expectancy)}
    strategy = {"breakout_continuation": _category(trades, expectancy)}
    regime = {"strong_bear_trend": _category(trades, expectancy)}
    return ValidationFoldResult(
        fold=number,
        symbol="EUR-USD",
        timeframe="5m",
        higher_timeframe="1h",
        training_start_index=0,
        training_end_index=100,
        validation_start_index=100,
        validation_end_index=150,
        training=_measurement(trades, 1.0),
        validation=_measurement(trades, expectancy),
        human_readable_summary="Synthetic fold.",
        training_setup_performance=category,
        validation_setup_performance=category,
        training_strategy_performance=strategy,
        validation_strategy_performance=strategy,
        training_regime_performance=regime,
        validation_regime_performance=regime,
    )


def _generalization(variance: float = 0.01):
    return GeneralizationSummary(
        generalization_score=90.0,
        performance_decay_percent=10.0,
        win_rate_decay_percent=5.0,
        expectancy_decay_percent=10.0,
        drawdown_change=0.2,
        profit_factor_change=-0.1,
        confidence_drift=2.0,
        strategy_drift=2.0,
        setup_drift=2.0,
        regime_drift=2.0,
        execution_drift=0.1,
        trade_frequency_drift=3.0,
        calibration_stability_score=92.0,
        fold_stability_score=90.0,
        variance_across_folds=variance,
        coefficient_of_variation=0.1,
        human_readable_summary="Stable synthetic generalization.",
    )


def _overfit(risk: str = "LOW"):
    flagged = risk != "LOW"
    return OverfittingSummary(
        risk_level=risk,
        detected_risks=("large variance",) if flagged else (),
        performance_collapse=False,
        confidence_collapse=False,
        setup_instability=flagged,
        strategy_instability=flagged,
        regime_instability=False,
        execution_instability=False,
        risk_instability=False,
        large_variance_between_folds=flagged,
        large_dependence_on_one_market=False,
        large_dependence_on_one_timeframe=False,
        large_dependence_on_one_symbol=False,
        human_readable_summary="Synthetic overfit report.",
    )


def _build(
    folds,
    risk="LOW",
    monte_carlo_risk=None,
    monte_carlo_reporting=None,
    statistical_validation=None,
):
    validation_trades = sum(fold.validation.trades for fold in folds)
    oos = OutOfSampleSummary(
        validation_method=ValidationMethod.WALK_FORWARD,
        requested_folds=len(folds),
        completed_folds=len(folds),
        training=_measurement(validation_trades, 1.0),
        validation=_measurement(
            validation_trades,
            sum(fold.validation.expectancy for fold in folds) / len(folds),
        ),
        entire_sample=_measurement(validation_trades * 2, 0.9),
        human_readable_summary="Synthetic OOS.",
        limitations=(),
    )
    stability = StabilitySummary(
        calibration_stability_score=92.0,
        fold_stability_score=90.0,
        variance_across_folds=0.01,
        standard_deviation_across_folds=0.1,
        coefficient_of_variation=0.1,
        fold_count=len(folds),
        human_readable_summary="Stable folds.",
    )
    return build_walk_forward_intelligence(
        oos,
        tuple(folds),
        _generalization(),
        _overfit(risk),
        stability,
        monte_carlo_risk,
        monte_carlo_reporting,
        statistical_validation,
    )


def test_small_high_performing_sample_needs_more_data() -> None:
    result = _build([_fold(1, 20, 1.5), _fold(2, 20, 1.2)])
    setup = next(row for row in result.rankings if row.dimension == "setup")

    assert setup.promotion_readiness is PromotionReadiness.NEEDS_MORE_DATA
    assert "promising but under-tested" in setup.human_readable_summary
    assert "100-trade minimum" in setup.human_readable_summary
    assert any(
        row.dimension == "symbol_timeframe_setup"
        and "EUR-USD 5m" in row.combination
        for row in result.rankings
    )


def test_high_fold_variance_reduces_robustness() -> None:
    stable = _build([_fold(1, 120, 1.0), _fold(2, 120, 1.0), _fold(3, 120, 1.0)])
    volatile = _build([_fold(1, 120, 2.5), _fold(2, 120, -1.0), _fold(3, 120, 1.5)])
    stable_setup = next(row for row in stable.rankings if row.dimension == "setup")
    volatile_setup = next(row for row in volatile.rankings if row.dimension == "setup")

    assert volatile_setup.fold_consistency_score < stable_setup.fold_consistency_score
    assert volatile_setup.robustness_score < stable_setup.robustness_score


def test_overfitting_risk_lowers_readiness() -> None:
    folds = [_fold(1, 120, 1.0), _fold(2, 120, 1.0), _fold(3, 120, 1.0)]
    low_risk = _build(folds)
    high_risk = _build(folds, "HIGH")
    low_setup = next(row for row in low_risk.rankings if row.dimension == "setup")
    high_setup = next(row for row in high_risk.rankings if row.dimension == "setup")

    assert low_setup.robustness_score > high_setup.robustness_score
    assert high_setup.promotion_readiness is PromotionReadiness.NOT_READY


def test_stable_large_validation_sample_can_reach_paper_trading_readiness() -> None:
    result = _build([_fold(1, 120, 1.0), _fold(2, 120, 1.0), _fold(3, 120, 1.0)])
    setup = next(row for row in result.rankings if row.dimension == "setup")

    assert setup.validation_trades == 360
    assert setup.sample_quality == "strong"
    assert setup.promotion_readiness is PromotionReadiness.READY_FOR_PAPER_TRADING
    assert result.promotion_readiness.ready_for_paper_trading_count > 0


def test_high_monte_carlo_drawdown_blocks_paper_trading_readiness() -> None:
    folds = [_fold(1, 120, 1.0), _fold(2, 120, 1.0), _fold(3, 120, 1.0)]
    monte_carlo_risk = MonteCarloRiskSummary(
        risk_of_ruin=1.0,
        probability_of_finishing_profitable=80.0,
        probability_of_drawdown_over_5_percent=80.0,
        probability_of_drawdown_over_10_percent=55.0,
        probability_of_drawdown_over_20_percent=40.0,
        expectancy_mean=1.0,
        expectancy_standard_deviation=0.2,
        risk_level="high",
        human_readable_summary="Synthetic high drawdown risk.",
    )
    result = _build(folds, monte_carlo_risk=monte_carlo_risk)
    setup = next(row for row in result.rankings if row.dimension == "setup")

    assert setup.promotion_readiness is not PromotionReadiness.READY_FOR_PAPER_TRADING
    assert result.promotion_readiness.monte_carlo_readiness_blocked is True
    assert "Monte Carlo" in " ".join(result.promotion_readiness.reasons)


def test_expectancy_confidence_crossing_zero_blocks_readiness() -> None:
    folds = [_fold(1, 120, 1.0), _fold(2, 120, 1.0), _fold(3, 120, 1.0)]
    returns = [1.0, -1.0] * 60
    monte_carlo = run_monte_carlo(returns, simulations=100, random_seed=42)
    reporting = build_monte_carlo_report(monte_carlo, returns)
    result = _build(
        folds,
        monte_carlo_risk=monte_carlo.risk_summary,
        monte_carlo_reporting=reporting,
    )

    assert reporting.expectancy_confidence.lower_bound_positive is False
    assert result.promotion_readiness.monte_carlo_readiness_blocked is True
    assert result.promotion_readiness.ready_for_paper_trading_count == 0
    assert "expectancy_confidence_crosses_zero" in (
        result.promotion_readiness.monte_carlo_failure_reasons
    )


def test_negative_recent_expectancy_blocks_readiness() -> None:
    folds = [_fold(1, 120, 1.0), _fold(2, 120, 1.0), _fold(3, 120, 1.0)]
    validation = build_statistical_validation(
        [1.0] * 40 + [0.5] * 40 + [-0.2] * 40,
        fold_expectancies=[1.0, 1.0, 1.0],
    )
    result = _build(folds, statistical_validation=validation)

    assert result.promotion_readiness.statistical_validation_readiness_blocked is True
    assert result.promotion_readiness.ready_for_paper_trading_count == 0
    assert "NEGATIVE_RECENT_EXPECTANCY" in (
        result.promotion_readiness.statistical_weakness_flags
    )
