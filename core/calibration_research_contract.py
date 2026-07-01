"""Central population contract for additive calibration research fields."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ResearchFieldRequirement:
    field: str
    request_condition: str
    source_data: str
    enabled: bool


def research_field_requirements(request: Any) -> tuple[ResearchFieldRequirement, ...]:
    """Describe when every optional research family must be populated."""

    compare = str(getattr(request.regime_classifier_mode, "value", request.regime_classifier_mode)) == "compare"
    forward = compare and bool(request.forward_validation)
    oos = bool(request.out_of_sample_validation)
    monte_carlo = bool(request.monte_carlo_analysis)
    statistical = bool(request.statistical_validation_analysis)
    requirements: list[ResearchFieldRequirement] = []

    def add(fields: tuple[str, ...], condition: str, source: str, enabled: bool) -> None:
        requirements.extend(
            ResearchFieldRequirement(field, condition, source, enabled)
            for field in fields
        )

    add(("execution_sensitivity_summary",), "execution_sensitivity_profiles supplied", "replayed backtests", bool(request.execution_sensitivity_profiles))
    add(("entry_timing_summary",), "entry_timing_profiles supplied", "executed trade candidates", bool(request.entry_timing_profiles))
    add(("market_regime_summary", "strategy_regime_matrix", "setup_regime_matrix"), "market_regime_analysis=true or tuned mode", "calibration records with regime metadata", bool(request.market_regime_analysis) or str(getattr(request.regime_classifier_mode, "value", request.regime_classifier_mode)) == "tuned")
    add(("regime_validation_summary",), "regime_validation_analysis=true", "regime observations", bool(request.regime_validation_analysis))
    add(("regime_tuning_summary",), "regime_tuning_analysis=true", "legacy regime evidence", bool(request.regime_tuning_analysis))
    add(("legacy_market_regime_summary", "tuned_market_regime_summary", "regime_classifier_comparison"), "regime_classifier_mode=compare", "matched legacy/tuned classifications", compare)
    add(("legacy_forward_validation", "tuned_forward_validation", "forward_validation_comparison"), "compare mode and forward_validation=true", "matched forward observations", forward)
    add(("regime_confidence_summary",), "compare mode, forward_validation=true, regime_confidence_analysis=true", "forward-validation observations; empty samples produce an unavailable calibration", forward and bool(request.regime_confidence_analysis))
    add(("out_of_sample_summary", "validation_fold_results", "generalization_summary", "overfitting_summary", "stability_summary", "symbol_validation_summary", "timeframe_validation_summary", "research_pipeline_summary", "walk_forward_intelligence_summary", "strategy_robustness_rankings", "promotion_readiness_summary", "research_action_items"), "out_of_sample_validation=true", "chronological validation folds; empty folds produce controlled summaries", oos)
    add(("monte_carlo_summary", "monte_carlo_distribution", "monte_carlo_risk_summary", "monte_carlo_recommendations", "monte_carlo_report", "monte_carlo_risk_heatmap", "monte_carlo_target_probabilities", "monte_carlo_expectancy_confidence", "monte_carlo_kelly_summary", "monte_carlo_failure_reasons"), "monte_carlo_analysis=true", "closed validation trades, or completed trades without OOS; empty samples produce unavailable output", monte_carlo)
    add(("statistical_validation_summary", "losing_streak_summary", "trade_distribution_summary", "edge_decay_summary", "fold_stability_summary", "weakness_detection_summary"), "statistical_validation_analysis=true", "closed research returns; empty samples produce unavailable output", statistical)
    add(("research_lab_summary", "research_rankings", "performance_matrices", "research_statistics", "aggregate_score_summary", "aggregate_execution_intelligence_summary", "aggregate_confidence_calibration_summary", "confidence_bucket_calibration", "strategy_rating_summary", "setup_rating_summary", "symbol_profile_summary", "aggregate_adaptive_strategy_router_summary"), "always", "all completed and skipped calibration records", True)
    return tuple(requirements)


def validate_research_population(request: Any, result: Any) -> None:
    """Fail loudly if an enabled research section was silently dropped."""

    missing = [
        requirement.field
        for requirement in research_field_requirements(request)
        if requirement.enabled and getattr(result, requirement.field, None) is None
    ]
    if missing:
        raise RuntimeError(
            "Enabled calibration research fields were not populated: "
            + ", ".join(sorted(missing))
        )
