"""Advisory execution guidance over immutable analysis and research output."""

from collections import Counter
from dataclasses import dataclass
from enum import Enum
from statistics import mean


class ExecutionStyle(str, Enum):
    MARKET_ENTRY = "market_entry"
    LIMIT_RETEST = "limit_retest"
    CONFIRMATION_CLOSE = "confirmation_close"
    WAIT_FOR_PULLBACK = "wait_for_pullback"
    AVOID_EXECUTION = "avoid_execution"


@dataclass(frozen=True)
class ExecutionAssessment:
    status: str
    score: float
    explanation: str


@dataclass(frozen=True)
class ExecutionIntelligence:
    execution_quality_score: float
    execution_grade: str
    preferred_execution_style: ExecutionStyle
    entry_timing_guidance: str
    stop_quality_assessment: ExecutionAssessment
    target_quality_assessment: ExecutionAssessment
    risk_reward_assessment: ExecutionAssessment
    trade_management_guidance: tuple[str, ...]
    execution_warnings: tuple[str, ...]
    execution_blockers: tuple[str, ...]
    research_inputs_available: tuple[str, ...]
    human_readable_summary: str


class ExecutionIntelligenceEngine:
    """Explain execution quality without modifying levels or trade eligibility."""

    def analyze(
        self,
        *,
        action: str,
        setup_plan,
        strategy,
        risk_reward_diagnostics=None,
        outcome_diagnostics=None,
        entry_timing_summary=None,
        trade_management_sensitivity=(),
        monte_carlo_report=None,
        statistical_validation_summary=None,
    ) -> ExecutionIntelligence:
        setup_type = _value(getattr(setup_plan, "setup_type", "no_valid_setup"))
        setup_status = _value(getattr(setup_plan, "setup_status", "no_setup"))
        direction = _value(getattr(setup_plan, "direction", "neutral"))
        ratio = getattr(setup_plan, "estimated_risk_reward", None)
        conditions = tuple(getattr(setup_plan, "entry_conditions", ()))
        required = [item for item in conditions if getattr(item, "importance", "") == "required"]
        unmet = [item for item in required if not getattr(item, "is_met", False)]
        levels_complete = all(
            getattr(setup_plan, name, None)
            for name in ("entry_zone", "stop_loss", "target")
        )
        strategy_type = _value(
            getattr(strategy, "preferred_strategy", "no_strategy")
        )
        strategy_alignment = _value(
            getattr(strategy, "strategy_alignment", "no_clear_strategy")
        )
        no_trade = action in {"no_trade", "avoid"} or setup_type == "no_valid_setup"
        blockers: list[str] = []
        warnings: list[str] = []
        if no_trade:
            blockers.append("The authoritative analysis does not permit execution.")
        if not levels_complete:
            blockers.append("Entry, stop, and target levels are not all available.")
        if unmet:
            warnings.append(f"{len(unmet)} required confirmation conditions remain unmet.")

        style = _execution_style(
            no_trade,
            setup_type,
            setup_status,
            bool(unmet),
            ratio,
            levels_complete,
        )
        stop = _stop_assessment(risk_reward_diagnostics, levels_complete)
        target = _target_assessment(risk_reward_diagnostics, ratio, levels_complete)
        rr = _risk_reward_assessment(ratio)
        if stop.status in {"too_tight", "too_wide", "invalid"}:
            warnings.append(stop.explanation)
        if target.status in {"too_close", "invalid"}:
            warnings.append(target.explanation)
        if ratio is not None and ratio < 1.5:
            blockers.append("Estimated risk/reward remains below the 1.5R execution minimum.")
        if strategy_alignment == "conflicts_with_decision":
            blockers.append("The preferred strategy conflicts with the Decision Engine.")

        research_available: list[str] = []
        management = [
            "Keep production trade management unchanged; no research sensitivity is available."
        ]
        if entry_timing_summary is not None:
            research_available.append("entry_timing")
            management.append(
                f"Entry Timing Laboratory favored {entry_timing_summary.best_expectancy_profile}; "
                "treat this as counterfactual guidance only."
            )
        improved = [
            item for item in trade_management_sensitivity
            if getattr(item, "improved_vs_baseline", False)
        ]
        if improved:
            research_available.append("trade_management")
            best = max(improved, key=lambda item: getattr(item, "total_r", 0.0))
            rule = _value(getattr(best, "rule", "unknown"))
            if rule in {"trail_after_1r", "trail_after_1_5r"}:
                management.append(
                    f"Research sensitivity favored {rule.replace('_', ' ')}; do not "
                    "apply it without a separately authorized experiment."
                )
        if outcome_diagnostics is not None:
            research_available.append("mfe_mae")
            mfe = float(getattr(outcome_diagnostics, "average_mfe_r", 0.0))
            mae = float(getattr(outcome_diagnostics, "average_mae_r", 0.0))
            management.append(
                f"Historical executed trades averaged {mfe:.2f}R MFE and {mae:.2f}R MAE."
            )
            if mae > mfe:
                warnings.append("Historical adverse excursion exceeded favorable excursion.")
            loss_reasons = getattr(outcome_diagnostics, "by_loss_reason", {})
            if loss_reasons.get("stop_too_tight", 0):
                stop = ExecutionAssessment(
                    "too_tight",
                    30,
                    "Executed-trade diagnostics identify stop too tight as a loss cause.",
                )
                warnings.append(stop.explanation)
            if loss_reasons.get("stop_too_wide", 0):
                stop = ExecutionAssessment(
                    "too_wide",
                    30,
                    "Executed-trade diagnostics identify stop too wide as a loss cause.",
                )
                warnings.append(stop.explanation)
        if monte_carlo_report is not None:
            research_available.append("monte_carlo")
            if getattr(monte_carlo_report, "overall_status", "") == "FAIL":
                warnings.append("Monte Carlo reporting indicates failed sequence-risk quality.")
        if statistical_validation_summary is not None:
            research_available.append("statistical_validation")
            if getattr(statistical_validation_summary, "overall_status", "") == "FAIL":
                warnings.append("Advanced statistical validation detected hidden weakness.")

        quality = _quality_score(
            setup_plan,
            ratio,
            required,
            unmet,
            levels_complete,
            strategy_alignment,
            blockers,
            warnings,
        )
        grade = _grade(quality)
        timing = _timing_guidance(style, setup_type, direction, ratio)
        return ExecutionIntelligence(
            execution_quality_score=quality,
            execution_grade=grade,
            preferred_execution_style=style,
            entry_timing_guidance=timing,
            stop_quality_assessment=stop,
            target_quality_assessment=target,
            risk_reward_assessment=rr,
            trade_management_guidance=tuple(dict.fromkeys(management)),
            execution_warnings=tuple(dict.fromkeys(warnings)),
            execution_blockers=tuple(dict.fromkeys(blockers)),
            research_inputs_available=tuple(research_available),
            human_readable_summary=(
                f"Execution quality is {grade} ({quality:.1f}/100). Preferred style is "
                f"{style.value.replace('_', ' ')} for the {setup_type.replace('_', ' ')} "
                f"setup using the existing, unchanged levels."
            ),
        )

    def aggregate(
        self,
        records: list[ExecutionIntelligence] | tuple[ExecutionIntelligence, ...],
        **research,
    ) -> ExecutionIntelligence:
        if not records:
            unavailable = self.analyze(
                action="no_trade",
                setup_plan=None,
                strategy=None,
            )
            return ExecutionIntelligence(
                execution_quality_score=0.0,
                execution_grade="F",
                preferred_execution_style=ExecutionStyle.AVOID_EXECUTION,
                entry_timing_guidance=unavailable.entry_timing_guidance,
                stop_quality_assessment=unavailable.stop_quality_assessment,
                target_quality_assessment=unavailable.target_quality_assessment,
                risk_reward_assessment=unavailable.risk_reward_assessment,
                trade_management_guidance=unavailable.trade_management_guidance,
                execution_warnings=("No calibration execution observations are available.",),
                execution_blockers=unavailable.execution_blockers,
                research_inputs_available=(),
                human_readable_summary=(
                    "Aggregate execution intelligence is unavailable because no "
                    "calibration execution observations were produced."
                ),
            )
        style = Counter(item.preferred_execution_style for item in records).most_common(1)[0][0]
        average_quality = mean(item.execution_quality_score for item in records)
        warnings = tuple(dict.fromkeys(message for item in records for message in item.execution_warnings))
        blockers = tuple(dict.fromkeys(message for item in records for message in item.execution_blockers))
        enriched = self.analyze(
            action="wait",
            setup_plan=_AggregateSetup(records, average_quality),
            strategy=_AggregateStrategy(),
            outcome_diagnostics=research.get("outcome_diagnostics"),
            entry_timing_summary=research.get("entry_timing_summary"),
            trade_management_sensitivity=research.get("trade_management_sensitivity", ()),
            monte_carlo_report=research.get("monte_carlo_report"),
            statistical_validation_summary=research.get("statistical_validation_summary"),
        )
        return ExecutionIntelligence(
            execution_quality_score=round(average_quality, 3),
            execution_grade=_grade(average_quality),
            preferred_execution_style=style,
            entry_timing_guidance=(
                f"The most common advisory style across {len(records)} records was "
                f"{style.value.replace('_', ' ')}."
            ),
            stop_quality_assessment=enriched.stop_quality_assessment,
            target_quality_assessment=enriched.target_quality_assessment,
            risk_reward_assessment=enriched.risk_reward_assessment,
            trade_management_guidance=enriched.trade_management_guidance,
            execution_warnings=tuple(dict.fromkeys((*warnings, *enriched.execution_warnings))),
            execution_blockers=tuple(dict.fromkeys((*blockers, *enriched.execution_blockers))),
            research_inputs_available=enriched.research_inputs_available,
            human_readable_summary=(
                f"Aggregate execution quality is {_grade(average_quality)} "
                f"({average_quality:.1f}/100) across {len(records)} immutable analysis records."
            ),
        )


@dataclass(frozen=True)
class _AggregateSetup:
    records: tuple[ExecutionIntelligence, ...] | list[ExecutionIntelligence]
    setup_quality_score: float
    setup_type: str = "aggregate_setup"
    setup_status: str = "developing"
    direction: str = "neutral"
    entry_zone: str = "aggregate"
    stop_loss: str = "aggregate"
    target: str = "aggregate"
    estimated_risk_reward: float | None = None
    entry_conditions: tuple = ()


@dataclass(frozen=True)
class _AggregateStrategy:
    preferred_strategy: str = "aggregate_strategy"
    strategy_alignment: str = "partially_aligned"


def _execution_style(no_trade, setup_type, status, weak, ratio, levels):
    if no_trade:
        return ExecutionStyle.AVOID_EXECUTION
    if weak or status in {"developing", "waiting_for_confirmation"}:
        return (
            ExecutionStyle.WAIT_FOR_PULLBACK
            if "pullback" in setup_type else ExecutionStyle.CONFIRMATION_CLOSE
        )
    if not levels:
        return ExecutionStyle.AVOID_EXECUTION
    if any(name in setup_type for name in ("retest", "pullback", "liquidity_sweep")):
        return ExecutionStyle.LIMIT_RETEST
    if "breakout" in setup_type:
        return ExecutionStyle.CONFIRMATION_CLOSE
    return ExecutionStyle.MARKET_ENTRY if ratio is not None and ratio >= 2 else ExecutionStyle.LIMIT_RETEST


def _stop_assessment(diagnostics, levels):
    failure = _value(getattr(diagnostics, "failure_reason", "")) if diagnostics else ""
    if failure == "stop_too_wide":
        return ExecutionAssessment("too_wide", 30, "Stop distance appears too wide relative to reward.")
    if failure == "stop_too_tight":
        return ExecutionAssessment("too_tight", 30, "Stop distance appears too tight for observed movement.")
    if failure == "invalid_price_geometry":
        return ExecutionAssessment("invalid", 10, "Stop geometry is invalid for the setup direction.")
    return ExecutionAssessment("acceptable" if levels else "unavailable", 80 if levels else 30, "Stop is defined from existing setup levels." if levels else "Stop level is unavailable.")


def _target_assessment(diagnostics, ratio, levels):
    failure = _value(getattr(diagnostics, "failure_reason", "")) if diagnostics else ""
    if failure in {"target_too_close", "below_minimum_r"} or (ratio is not None and ratio < 1.5):
        return ExecutionAssessment("too_close", 35, "Target is too close to satisfy the current 1.5R requirement.")
    if failure == "invalid_price_geometry":
        return ExecutionAssessment("invalid", 10, "Target geometry is invalid for the setup direction.")
    return ExecutionAssessment("acceptable" if levels else "unavailable", 85 if levels else 30, "Target is defined with the existing setup geometry." if levels else "Target level is unavailable.")


def _risk_reward_assessment(ratio):
    if ratio is None:
        return ExecutionAssessment("unavailable", 35, "Risk/reward is unavailable; execution should wait.")
    score = 95 if ratio >= 3 else 88 if ratio >= 2 else 75 if ratio >= 1.5 else 35
    status = "strong" if ratio >= 2 else "acceptable" if ratio >= 1.5 else "insufficient"
    return ExecutionAssessment(status, score, f"Estimated reward-to-risk is {ratio:.2f}R ({status}).")


def _quality_score(setup, ratio, required, unmet, levels, alignment, blockers, warnings):
    setup_quality = float(getattr(setup, "setup_quality_score", 0.0))
    rr = _risk_reward_assessment(ratio).score
    confirmation = 100.0 * (len(required) - len(unmet)) / len(required) if required else 50.0
    level_score = 90.0 if levels else 20.0
    strategy_score = {"aligned_with_decision": 90, "partially_aligned": 65, "conflicts_with_decision": 20, "no_clear_strategy": 35}.get(alignment, 40)
    score = setup_quality * 0.30 + rr * 0.25 + confirmation * 0.20 + level_score * 0.15 + strategy_score * 0.10
    score -= min(40, len(blockers) * 20) + min(15, len(warnings) * 5)
    return round(max(0.0, min(100.0, score)), 3)


def _timing_guidance(style, setup_type, direction, ratio):
    descriptions = {
        ExecutionStyle.AVOID_EXECUTION: "Do not execute; retain the current wait/no-trade decision.",
        ExecutionStyle.CONFIRMATION_CLOSE: "Wait for the required confirmation candle to close before considering execution.",
        ExecutionStyle.WAIT_FOR_PULLBACK: "Wait for price to complete the pullback and satisfy required confirmation.",
        ExecutionStyle.LIMIT_RETEST: "A retest-style entry is more coherent than chasing price; keep the existing entry zone unchanged.",
        ExecutionStyle.MARKET_ENTRY: "Evidence supports immediate-style execution only after all existing conditions are confirmed.",
    }
    return descriptions[style] + f" Context: {direction} {setup_type.replace('_', ' ')}, {ratio if ratio is not None else 'unknown'}R."


def _grade(score):
    return "A+" if score >= 90 else "A" if score >= 80 else "B" if score >= 70 else "C" if score >= 60 else "D" if score >= 45 else "F"


def _value(value):
    return str(getattr(value, "value", value))
