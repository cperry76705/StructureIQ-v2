"""Research-only robustness and promotion-readiness analysis over OOS folds."""

from dataclasses import dataclass, replace
from enum import Enum
from statistics import pstdev

from core.out_of_sample import (
    GeneralizationSummary,
    OutOfSampleSummary,
    OverfittingSummary,
    StabilitySummary,
    ValidationCategoryPerformance,
    ValidationFoldResult,
)
from core.monte_carlo import MonteCarloRiskSummary
from core.monte_carlo_reporting import (
    MonteCarloReportingResult,
    monte_carlo_blocks_readiness,
)


class PromotionReadiness(str, Enum):
    NOT_READY = "NOT_READY"
    NEEDS_MORE_DATA = "NEEDS_MORE_DATA"
    WATCHLIST = "WATCHLIST"
    READY_FOR_PAPER_TRADING = "READY_FOR_PAPER_TRADING"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"


@dataclass(frozen=True)
class RobustnessRanking:
    dimension: str
    combination: str
    training_trades: int
    validation_trades: int
    training_expectancy: float
    validation_expectancy: float
    expectancy_decay_percent: float
    validation_win_rate: float
    validation_profit_factor: float | None
    max_validation_drawdown: float
    fold_consistency_score: float
    robustness_score: float
    sample_quality: str
    promotion_readiness: PromotionReadiness
    human_readable_summary: str


@dataclass(frozen=True)
class WalkForwardIntelligenceSummary:
    folds_analyzed: int
    training_trades: int
    validation_trades: int
    validation_expectancy: float
    expectancy_decay_percent: float
    fold_stability_score: float
    fold_variance: float
    symbol_dependency: bool
    timeframe_dependency: bool
    setup_dependency: bool
    strategy_dependency: bool
    regime_dependency: bool
    drawdown_stability_score: float
    trade_frequency_stability_score: float
    confidence_drift: float
    highest_robustness_combination: str | None
    human_readable_summary: str


@dataclass(frozen=True)
class PromotionReadinessSummary:
    overall_status: PromotionReadiness
    acceptable_validation_trades: int
    strong_validation_trades: int
    excellent_validation_trades: int
    not_ready_count: int
    needs_more_data_count: int
    watchlist_count: int
    ready_for_paper_trading_count: int
    ready_for_review_count: int
    executive_statement: str
    reasons: tuple[str, ...]
    monte_carlo_risk_level: str | None
    monte_carlo_readiness_blocked: bool
    monte_carlo_report_status: str | None
    monte_carlo_failure_reasons: tuple[str, ...]


@dataclass(frozen=True)
class WalkForwardIntelligenceResult:
    summary: WalkForwardIntelligenceSummary
    rankings: tuple[RobustnessRanking, ...]
    promotion_readiness: PromotionReadinessSummary
    action_items: tuple[str, ...]


def build_walk_forward_intelligence(
    out_of_sample: OutOfSampleSummary,
    folds: tuple[ValidationFoldResult, ...],
    generalization: GeneralizationSummary,
    overfitting: OverfittingSummary,
    stability: StabilitySummary,
    monte_carlo_risk_summary: MonteCarloRiskSummary | None = None,
    monte_carlo_reporting: MonteCarloReportingResult | None = None,
) -> WalkForwardIntelligenceResult:
    """Evaluate immutable training/validation results without changing trades."""

    rankings = _apply_monte_carlo_risk(
        _build_rankings(folds, overfitting),
        monte_carlo_risk_summary,
        monte_carlo_reporting,
    )
    ordered = tuple(
        sorted(
            rankings,
            key=lambda item: (
                item.robustness_score,
                item.validation_expectancy,
                item.validation_trades,
            ),
            reverse=True,
        )
    )
    best = ordered[0] if ordered else None
    summary = WalkForwardIntelligenceSummary(
        folds_analyzed=len(folds),
        training_trades=out_of_sample.training.trades,
        validation_trades=out_of_sample.validation.trades,
        validation_expectancy=out_of_sample.validation.expectancy,
        expectancy_decay_percent=generalization.expectancy_decay_percent,
        fold_stability_score=stability.fold_stability_score,
        fold_variance=stability.variance_across_folds,
        symbol_dependency=overfitting.large_dependence_on_one_symbol,
        timeframe_dependency=overfitting.large_dependence_on_one_timeframe,
        setup_dependency=overfitting.setup_instability,
        strategy_dependency=overfitting.strategy_instability,
        regime_dependency=overfitting.regime_instability,
        drawdown_stability_score=_drawdown_stability(folds),
        trade_frequency_stability_score=max(
            0.0, round(100.0 - generalization.trade_frequency_drift, 3)
        ),
        confidence_drift=generalization.confidence_drift,
        highest_robustness_combination=best.combination if best else None,
        human_readable_summary=(
            f"Walk-forward research evaluated {len(folds)} folds and "
            f"{out_of_sample.validation.trades} validation trades. "
            f"Validation expectancy was {out_of_sample.validation.expectancy:.3f}R "
            f"with {stability.fold_stability_score:.1f}/100 fold stability."
        ),
    )
    promotion = _promotion_summary(
        ordered,
        out_of_sample,
        overfitting,
        monte_carlo_risk_summary,
        monte_carlo_reporting,
    )
    return WalkForwardIntelligenceResult(
        summary=summary,
        rankings=ordered,
        promotion_readiness=promotion,
        action_items=_action_items(ordered, promotion, overfitting),
    )


def _build_rankings(
    folds: tuple[ValidationFoldResult, ...],
    overfitting: OverfittingSummary,
) -> list[RobustnessRanking]:
    rows: list[RobustnessRanking] = []
    rows.extend(_fold_dimension(folds, "symbol", lambda fold: fold.symbol, overfitting))
    rows.extend(
        _fold_dimension(folds, "timeframe", lambda fold: fold.timeframe, overfitting)
    )
    for dimension, training_name, validation_name in (
        ("setup", "training_setup_performance", "validation_setup_performance"),
        (
            "strategy",
            "training_strategy_performance",
            "validation_strategy_performance",
        ),
        ("regime", "training_regime_performance", "validation_regime_performance"),
    ):
        categories: set[str] = set()
        for fold in folds:
            categories.update((getattr(fold, training_name) or {}).keys())
            categories.update((getattr(fold, validation_name) or {}).keys())
        for category in sorted(categories):
            rows.append(
                _category_row(
                    dimension,
                    category,
                    [
                        (getattr(fold, training_name) or {}).get(category)
                        for fold in folds
                    ],
                    [
                        (getattr(fold, validation_name) or {}).get(category)
                        for fold in folds
                    ],
                    overfitting,
                )
            )
    rows.extend(
        _cross_category_rows(
            folds,
            "symbol_timeframe_setup",
            "training_setup_performance",
            "validation_setup_performance",
            overfitting,
        )
    )
    rows.extend(
        _cross_category_rows(
            folds,
            "symbol_timeframe_strategy",
            "training_strategy_performance",
            "validation_strategy_performance",
            overfitting,
        )
    )
    return rows


def _fold_dimension(folds, dimension, key, overfitting):
    groups: dict[str, list[ValidationFoldResult]] = {}
    for fold in folds:
        groups.setdefault(key(fold), []).append(fold)
    return [
        _category_row(
            dimension,
            category,
            [_compact(fold.training) for fold in group],
            [_compact(fold.validation) for fold in group],
            overfitting,
        )
        for category, group in sorted(groups.items())
    ]


def _cross_category_rows(
    folds,
    dimension,
    training_name,
    validation_name,
    overfitting,
):
    groups: dict[
        str,
        tuple[
            list[ValidationCategoryPerformance | None],
            list[ValidationCategoryPerformance | None],
        ],
    ] = {}
    for fold in folds:
        training = getattr(fold, training_name) or {}
        validation = getattr(fold, validation_name) or {}
        for category in sorted(set(training) | set(validation)):
            name = f"{fold.symbol} {fold.timeframe} | {category}"
            pair = groups.setdefault(name, ([], []))
            pair[0].append(training.get(category))
            pair[1].append(validation.get(category))
    return [
        _category_row(dimension, category, pair[0], pair[1], overfitting)
        for category, pair in sorted(groups.items())
    ]


def _compact(measurement) -> ValidationCategoryPerformance:
    return ValidationCategoryPerformance(
        trades=measurement.trades,
        win_rate=measurement.win_rate,
        expectancy=measurement.expectancy,
        profit_factor=measurement.profit_factor,
        maximum_drawdown=measurement.maximum_drawdown,
    )


def _category_row(
    dimension: str,
    category: str,
    training: list[ValidationCategoryPerformance | None],
    validation: list[ValidationCategoryPerformance | None],
    overfitting: OverfittingSummary,
) -> RobustnessRanking:
    train = [item for item in training if item is not None]
    validate = [item for item in validation if item is not None]
    training_trades = sum(item.trades for item in train)
    validation_trades = sum(item.trades for item in validate)
    training_expectancy = _weighted(train, "expectancy")
    validation_expectancy = _weighted(validate, "expectancy")
    decay = _decay(training_expectancy, validation_expectancy)
    consistency = _fold_consistency(validate)
    max_drawdown = max((item.maximum_drawdown for item in validate), default=0.0)
    robustness = _robustness(
        validation_trades,
        validation_expectancy,
        decay,
        max_drawdown,
        consistency,
        overfitting,
        dimension,
    )
    readiness = _readiness(
        validation_trades,
        validation_expectancy,
        max_drawdown,
        consistency,
        robustness,
        overfitting,
    )
    if validation_trades < 100 and validation_expectancy > 0:
        conclusion = (
            f"{category.replace('_', ' ').title()} is promising but under-tested: "
            f"validation expectancy is {validation_expectancy:.3f}R, but sample "
            f"size is below the 100-trade minimum."
        )
    else:
        conclusion = (
            f"{category.replace('_', ' ').title()} has {validation_trades} validation "
            f"trades, {validation_expectancy:.3f}R expectancy, and "
            f"{robustness:.1f}/100 robustness; readiness is {readiness.value}."
        )
    return RobustnessRanking(
        dimension=dimension,
        combination=category,
        training_trades=training_trades,
        validation_trades=validation_trades,
        training_expectancy=round(training_expectancy, 6),
        validation_expectancy=round(validation_expectancy, 6),
        expectancy_decay_percent=round(decay, 3),
        validation_win_rate=round(_weighted(validate, "win_rate"), 3),
        validation_profit_factor=_weighted_optional(validate, "profit_factor"),
        max_validation_drawdown=round(max_drawdown, 6),
        fold_consistency_score=round(consistency, 3),
        robustness_score=round(robustness, 3),
        sample_quality=_sample_quality(validation_trades),
        promotion_readiness=readiness,
        human_readable_summary=conclusion,
    )


def _weighted(items, attribute: str) -> float:
    total = sum(item.trades for item in items)
    return (
        sum(getattr(item, attribute) * item.trades for item in items) / total
        if total else 0.0
    )


def _weighted_optional(items, attribute: str) -> float | None:
    available = [item for item in items if getattr(item, attribute) is not None]
    return round(_weighted(available, attribute), 6) if available else None


def _decay(training: float, validation: float) -> float:
    if training == 0:
        return 0.0 if validation >= 0 else 100.0
    return (training - validation) / abs(training) * 100.0


def _fold_consistency(items: list[ValidationCategoryPerformance]) -> float:
    values = [item.expectancy for item in items if item.trades]
    if not values:
        return 0.0
    positive_rate = sum(value > 0 for value in values) / len(values) * 100.0
    variance_score = max(0.0, 100.0 - pstdev(values) * 30.0)
    return (positive_rate + variance_score) / 2.0


def _robustness(
    trades,
    expectancy,
    decay,
    drawdown,
    consistency,
    overfitting,
    dimension,
) -> float:
    sample = min(100.0, trades / 3.0)
    edge = max(0.0, min(100.0, 50.0 + expectancy * 20.0))
    decay_score = max(0.0, min(100.0, 100.0 - max(0.0, decay)))
    drawdown_score = max(0.0, 100.0 - drawdown * 10.0)
    score = (
        sample * 0.25
        + edge * 0.25
        + consistency * 0.25
        + decay_score * 0.15
        + drawdown_score * 0.10
    )
    risk_penalty = {"LOW": 0.0, "MEDIUM": 10.0, "HIGH": 25.0, "OVERFIT_RISK": 40.0}.get(
        overfitting.risk_level.upper(), 15.0
    )
    dependency = (
        (dimension == "symbol" and overfitting.large_dependence_on_one_symbol)
        or (dimension == "timeframe" and overfitting.large_dependence_on_one_timeframe)
        or (dimension == "setup" and overfitting.setup_instability)
        or (dimension == "strategy" and overfitting.strategy_instability)
        or (dimension == "regime" and overfitting.regime_instability)
    )
    return max(0.0, min(100.0, score - risk_penalty - (10.0 if dependency else 0.0)))


def _readiness(trades, expectancy, drawdown, consistency, robustness, overfitting):
    if trades < 100:
        return PromotionReadiness.NEEDS_MORE_DATA if expectancy > 0 else PromotionReadiness.NOT_READY
    if overfitting.risk_level.upper() in {"HIGH", "OVERFIT_RISK"}:
        return PromotionReadiness.NOT_READY
    if expectancy <= 0 or robustness < 45 or consistency < 50:
        return PromotionReadiness.NOT_READY
    if robustness >= 75 and consistency >= 70 and drawdown <= 10:
        return PromotionReadiness.READY_FOR_PAPER_TRADING
    if robustness >= 60:
        return PromotionReadiness.READY_FOR_REVIEW
    return PromotionReadiness.WATCHLIST


def _sample_quality(trades: int) -> str:
    if trades < 100:
        return "insufficient"
    if trades < 300:
        return "acceptable"
    if trades < 500:
        return "strong"
    return "excellent"


def _drawdown_stability(folds) -> float:
    values = [fold.validation.maximum_drawdown for fold in folds]
    return max(0.0, 100.0 - (pstdev(values) * 20.0 if len(values) > 1 else 0.0))


def _promotion_summary(
    rankings, oos, overfitting, monte_carlo_risk, monte_carlo_reporting
):
    counts = {status: 0 for status in PromotionReadiness}
    for row in rankings:
        counts[row.promotion_readiness] += 1
    monte_carlo_blocked = _monte_carlo_blocks_readiness(
        monte_carlo_risk, monte_carlo_reporting
    )
    if counts[PromotionReadiness.READY_FOR_PAPER_TRADING] and not monte_carlo_blocked:
        overall = PromotionReadiness.READY_FOR_PAPER_TRADING
    elif oos.validation.trades < 100:
        overall = PromotionReadiness.NEEDS_MORE_DATA
    elif overfitting.risk_level.upper() in {"HIGH", "OVERFIT_RISK"}:
        overall = PromotionReadiness.NOT_READY
    elif counts[PromotionReadiness.READY_FOR_REVIEW]:
        overall = PromotionReadiness.READY_FOR_REVIEW
    else:
        overall = PromotionReadiness.WATCHLIST
    if overall is PromotionReadiness.READY_FOR_PAPER_TRADING:
        statement = (
            "StructureIQ has at least one research combination ready for controlled "
            "paper-trading review; no production change is authorized."
        )
    else:
        statement = (
            "StructureIQ is currently research-ready, but not paper-trading-ready "
            "because validation evidence or stability remains insufficient."
        )
    reasons = []
    if oos.validation.trades < 100:
        reasons.append("Fewer than 100 aggregate validation trades are available.")
    if overfitting.risk_level.upper() != "LOW":
        reasons.append(f"Out-of-sample overfitting risk is {overfitting.risk_level}.")
    if monte_carlo_blocked:
        reasons.append(
            "Monte Carlo sequence risk exceeds the paper-trading readiness limit."
        )
    return PromotionReadinessSummary(
        overall_status=overall,
        acceptable_validation_trades=100,
        strong_validation_trades=300,
        excellent_validation_trades=500,
        not_ready_count=counts[PromotionReadiness.NOT_READY],
        needs_more_data_count=counts[PromotionReadiness.NEEDS_MORE_DATA],
        watchlist_count=counts[PromotionReadiness.WATCHLIST],
        ready_for_paper_trading_count=counts[PromotionReadiness.READY_FOR_PAPER_TRADING],
        ready_for_review_count=counts[PromotionReadiness.READY_FOR_REVIEW],
        executive_statement=statement,
        reasons=tuple(reasons),
        monte_carlo_risk_level=(
            monte_carlo_risk.risk_level if monte_carlo_risk else None
        ),
        monte_carlo_readiness_blocked=monte_carlo_blocked,
        monte_carlo_report_status=(
            monte_carlo_reporting.report.overall_status
            if monte_carlo_reporting else None
        ),
        monte_carlo_failure_reasons=(
            monte_carlo_reporting.failure_reasons
            if monte_carlo_reporting else ()
        ),
    )


def _apply_monte_carlo_risk(rankings, risk, reporting):
    if not _monte_carlo_blocks_readiness(risk, reporting):
        return rankings
    return [
        replace(
            row,
            robustness_score=max(0.0, round(row.robustness_score - 25.0, 3)),
            promotion_readiness=(
                PromotionReadiness.NOT_READY
                if row.promotion_readiness
                in {
                    PromotionReadiness.READY_FOR_PAPER_TRADING,
                    PromotionReadiness.READY_FOR_REVIEW,
                }
                else row.promotion_readiness
            ),
            human_readable_summary=(
                row.human_readable_summary.replace(
                    f"readiness is {row.promotion_readiness.value}.",
                    "readiness is NOT_READY because Monte Carlo tail risk "
                    "blocks promotion.",
                )
            ),
        )
        for row in rankings
    ]


def _monte_carlo_blocks_readiness(risk, reporting=None):
    if reporting is not None:
        return monte_carlo_blocks_readiness(reporting)
    return bool(
        risk is not None
        and (
            risk.risk_of_ruin >= 5.0
            or risk.probability_of_drawdown_over_20_percent >= 25.0
            or risk.risk_level == "high"
        )
    )


def _action_items(rankings, promotion, overfitting):
    items: list[str] = []
    under_tested = [
        row for row in rankings
        if row.validation_expectancy > 0 and row.validation_trades < 100
    ]
    if under_tested:
        best = max(under_tested, key=lambda item: item.validation_expectancy)
        items.append(
            f"Collect at least {100 - best.validation_trades} additional validation "
            f"trades for {best.combination} before considering paper trading."
        )
    if overfitting.detected_risks:
        items.append(
            "Investigate OOS risk flags before promotion: "
            + ", ".join(overfitting.detected_risks)
            + "."
        )
    if promotion.monte_carlo_readiness_blocked:
        items.append(
            "Reduce uncertainty in Monte Carlo ruin and 20% drawdown risk through "
            "additional OOS evidence before any paper-trading review."
        )
    if promotion.overall_status is PromotionReadiness.READY_FOR_PAPER_TRADING:
        items.append(
            "Submit the qualifying research combination for human review and a "
            "separately authorized paper-trading design."
        )
    if not items:
        items.append("Continue walk-forward collection without changing production rules.")
    return tuple(items)
