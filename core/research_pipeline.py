"""Unified, downstream-only research intelligence over calibration and OOS output."""

from dataclasses import dataclass

from core.out_of_sample import (
    GeneralizationSummary,
    OutOfSampleSummary,
    OverfittingSummary,
    SegmentValidationSummary,
    StabilitySummary,
    ValidationFoldResult,
)
from core.monte_carlo import MonteCarloRiskSummary
from core.research_lab import PerformanceMatrices, ResearchLabSummary, ResearchRankings
from core.walk_forward_intelligence import (
    PromotionReadinessSummary,
    RobustnessRanking,
    WalkForwardIntelligenceSummary,
    build_walk_forward_intelligence,
)


@dataclass(frozen=True)
class ResearchPipelineSummary:
    status: str
    calibration_runs: int
    calibration_trades: int
    validation_folds: int
    validation_trades: int
    generalization_score: float
    overfitting_risk: str
    calibration_stability_score: float
    fold_stability_score: float
    strongest_historical_combination: str | None
    weakest_historical_combination: str | None
    symbols_evaluated: int
    timeframes_evaluated: int
    matrices_available: int
    monte_carlo_risk_level: str | None
    monte_carlo_readiness_blocked: bool
    human_readable_summary: str


@dataclass(frozen=True)
class ResearchPipelineResult:
    research_pipeline_summary: ResearchPipelineSummary
    walk_forward_intelligence_summary: WalkForwardIntelligenceSummary
    strategy_robustness_rankings: tuple[RobustnessRanking, ...]
    promotion_readiness_summary: PromotionReadinessSummary
    research_action_items: tuple[str, ...]


def build_research_pipeline(
    *,
    aggregate_metrics,
    research_lab_summary: ResearchLabSummary,
    research_rankings: ResearchRankings,
    performance_matrices: PerformanceMatrices,
    out_of_sample_summary: OutOfSampleSummary,
    validation_fold_results: tuple[ValidationFoldResult, ...],
    generalization_summary: GeneralizationSummary,
    overfitting_summary: OverfittingSummary,
    stability_summary: StabilitySummary,
    symbol_validation_summary: tuple[SegmentValidationSummary, ...],
    timeframe_validation_summary: tuple[SegmentValidationSummary, ...],
    monte_carlo_risk_summary: MonteCarloRiskSummary | None = None,
) -> ResearchPipelineResult:
    """Combine finalized research artifacts without feeding findings upstream."""

    intelligence = build_walk_forward_intelligence(
        out_of_sample_summary,
        validation_fold_results,
        generalization_summary,
        overfitting_summary,
        stability_summary,
        monte_carlo_risk_summary,
    )
    strongest = research_rankings.highest_expectancy
    weakest = (
        research_rankings.top_10_weakest_combinations[0]
        if research_rankings.top_10_weakest_combinations else None
    )
    matrices_available = sum(
        bool(rows)
        for rows in (
            performance_matrices.regime_strategy,
            performance_matrices.setup_regime,
            performance_matrices.symbol_setup,
            performance_matrices.timeframe_setup,
        )
    )
    promotion = intelligence.promotion_readiness
    pipeline = ResearchPipelineSummary(
        status="available",
        calibration_runs=aggregate_metrics.total_runs,
        calibration_trades=aggregate_metrics.total_trades,
        validation_folds=len(validation_fold_results),
        validation_trades=out_of_sample_summary.validation.trades,
        generalization_score=generalization_summary.generalization_score,
        overfitting_risk=overfitting_summary.risk_level,
        calibration_stability_score=stability_summary.calibration_stability_score,
        fold_stability_score=stability_summary.fold_stability_score,
        strongest_historical_combination=strongest.name if strongest else None,
        weakest_historical_combination=weakest.name if weakest else None,
        symbols_evaluated=len(symbol_validation_summary),
        timeframes_evaluated=len(timeframe_validation_summary),
        matrices_available=matrices_available,
        monte_carlo_risk_level=(
            monte_carlo_risk_summary.risk_level
            if monte_carlo_risk_summary else None
        ),
        monte_carlo_readiness_blocked=(
            promotion.monte_carlo_readiness_blocked
        ),
        human_readable_summary=(
            f"The unified research pipeline combined {aggregate_metrics.total_runs} "
            f"calibration runs, {len(validation_fold_results)} independent folds, "
            f"and {out_of_sample_summary.validation.trades} validation trades. "
            f"Generalization scored {generalization_summary.generalization_score:.1f}/100; "
            f"promotion status is {promotion.overall_status.value}."
        ),
    )
    action_items = tuple(
        dict.fromkeys(
            (
                *intelligence.action_items,
                research_lab_summary.where_additional_testing_is_needed,
                "Do not change production behavior from this research report alone.",
            )
        )
    )
    return ResearchPipelineResult(
        research_pipeline_summary=pipeline,
        walk_forward_intelligence_summary=intelligence.summary,
        strategy_robustness_rankings=intelligence.rankings,
        promotion_readiness_summary=promotion,
        research_action_items=action_items,
    )
