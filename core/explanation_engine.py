"""Trader-facing explanations built only from existing engine output."""

from dataclasses import dataclass
from typing import Literal

from core.decision_engine import DecisionAction, DecisionResult
from core.market_structure import MarketStructureResult
from core.multi_timeframe import MultiTimeframeResult, TimeframeAlignment
from core.setup_engine import SetupResult, SetupStatus, SetupType
from core.strategy_engine import StrategyResult, StrategyType


TradePlanStatus = Literal["actionable", "developing", "waiting", "avoid", "no_trade"]
ExplanationSource = Literal[
    "market_structure",
    "multi_timeframe",
    "decision_engine",
    "setup_engine",
    "indicators",
    "risk",
]
ExplanationSectionSource = ExplanationSource | Literal["strategy_engine"]
RiskSeverity = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class ExplanationSection:
    """Traceable plain-language section used to compose the public explanation."""

    title: str
    message: str
    source: ExplanationSectionSource


@dataclass(frozen=True)
class WaitForCondition:
    condition: str
    importance: Literal["required", "recommended", "optional"]
    source: ExplanationSource


@dataclass(frozen=True)
class KeyRisk:
    risk: str
    severity: RiskSeverity
    reason: str


@dataclass(frozen=True)
class MarketNarrative:
    bias: Literal["bullish", "bearish", "neutral", "unclear"]
    phase: str
    context: str


@dataclass(frozen=True)
class TradePlan:
    status: TradePlanStatus
    setup_type: str
    direction: Literal["bullish", "bearish", "neutral"]
    entry_zone: str | None
    stop_loss: str | None
    target: str | None
    estimated_risk_reward: float | None
    wait_for: tuple[WaitForCondition, ...]
    invalidation: tuple[str, ...]
    notes: tuple[str, ...]


@dataclass(frozen=True)
class TraderAnalysis:
    headline: str
    summary: str
    recommendation: str
    market_narrative: MarketNarrative
    why: tuple[str, ...]
    trade_plan: TradePlan
    key_risks: tuple[KeyRisk, ...]
    confidence_interpretation: str
    next_best_action: str


class ExplanationEngine:
    """Explain Decision and Setup results without changing either result."""

    def analyze(
        self,
        *,
        symbol: str,
        market_structure: MarketStructureResult,
        multi_timeframe: MultiTimeframeResult,
        decision: DecisionResult,
        setup_plan: SetupResult,
        strategy: StrategyResult | None = None,
    ) -> TraderAnalysis:
        narrative = _market_narrative(market_structure, multi_timeframe)
        plan_status = _trade_plan_status(decision, setup_plan)
        wait_for = _wait_conditions(setup_plan)
        invalidation = _invalidation_notes(setup_plan)
        notes = _plan_notes(decision, setup_plan, plan_status, strategy)
        trade_plan = TradePlan(
            status=plan_status,
            setup_type=setup_plan.setup_type.value,
            direction=setup_plan.direction,
            entry_zone=setup_plan.entry_zone,
            stop_loss=setup_plan.stop_loss,
            target=setup_plan.target,
            estimated_risk_reward=setup_plan.estimated_risk_reward,
            wait_for=wait_for,
            invalidation=invalidation,
            notes=notes,
        )
        sections = _why_sections(
            market_structure, multi_timeframe, decision, setup_plan, strategy
        )

        return TraderAnalysis(
            headline=_headline(symbol, decision, setup_plan, plan_status, narrative),
            summary=_summary(narrative, decision, setup_plan),
            recommendation=_recommendation(decision, setup_plan, plan_status),
            market_narrative=narrative,
            why=tuple(section.message for section in sections),
            trade_plan=trade_plan,
            key_risks=_key_risks(decision, setup_plan),
            confidence_interpretation=interpret_confidence(decision.confidence),
            next_best_action=_next_best_action(plan_status, wait_for),
        )


def interpret_confidence(confidence: float) -> str:
    """Translate Decision Engine confidence without changing its value."""

    bounded = max(0.0, min(confidence, 100.0))
    if bounded < 50.0:
        return "Weak or no edge. The available evidence does not support a trade."
    if bounded < 70.0:
        return "Moderate but incomplete edge. More confirmation is required."
    if bounded < 85.0:
        return "Strong evidence, but execution discipline and invalidation still matter."
    return "High-conviction evidence, but the outcome is not guaranteed."


def _trade_plan_status(
    decision: DecisionResult, setup: SetupResult
) -> TradePlanStatus:
    if decision.action is DecisionAction.AVOID:
        return "avoid"
    if decision.action is DecisionAction.WAIT:
        return "developing" if setup.setup_status is SetupStatus.DEVELOPING else "waiting"
    if (
        decision.action in {DecisionAction.BUY, DecisionAction.SELL}
        and setup.setup_status is SetupStatus.CONFIRMED
    ):
        return "actionable"
    if setup.setup_status in {SetupStatus.INVALID, SetupStatus.NO_SETUP}:
        return "no_trade"
    if setup.setup_status is SetupStatus.DEVELOPING:
        return "developing"
    return "waiting"


def _market_narrative(
    structure: MarketStructureResult, multi: MultiTimeframeResult
) -> MarketNarrative:
    bias = multi.directional_bias
    phase = structure.phase.replace("_", " ")
    if multi.alignment in {
        TimeframeAlignment.ALIGNED_BULLISH,
        TimeframeAlignment.ALIGNED_BEARISH,
    }:
        context = (
            f"The {multi.higher_timeframe} and {multi.current_timeframe} structures "
            f"both support a {bias} context while the current market is in a {phase} phase."
        )
    elif multi.alignment is TimeframeAlignment.MIXED:
        context = (
            f"The {multi.higher_timeframe} context remains {multi.higher_timeframe_trend}, "
            f"while {multi.current_timeframe} execution structure is "
            f"{multi.current_timeframe_trend} in a {phase} phase."
        )
    elif multi.alignment is TimeframeAlignment.CONFLICTING:
        context = (
            f"The {multi.higher_timeframe} and {multi.current_timeframe} structures point "
            "in opposing directions, so execution context is conflicted."
        )
    else:
        context = (
            "The available timeframe structure is not clear enough to establish reliable "
            "directional context."
        )
    return MarketNarrative(bias=bias, phase=phase, context=context)


def _headline(
    symbol: str,
    decision: DecisionResult,
    setup: SetupResult,
    status: TradePlanStatus,
    narrative: MarketNarrative,
) -> str:
    market = symbol.strip().upper() or "This market"
    if status == "actionable":
        return (
            f"{market} has a confirmed {setup.direction} "
            f"{_setup_name(setup.setup_type)} setup."
        )
    if status in {"waiting", "developing"}:
        if narrative.bias in {"bullish", "bearish"}:
            return f"{market} is {narrative.bias}, but the entry is not confirmed yet."
        return f"{market} needs more confirmation before a trade plan is actionable."
    if decision.action is DecisionAction.AVOID:
        return f"{market} does not currently offer a reliable trade edge."
    return f"{market} has no valid trade setup at the current price."


def _summary(
    narrative: MarketNarrative,
    decision: DecisionResult,
    setup: SetupResult,
) -> str:
    setup_text = (
        "No setup currently qualifies."
        if setup.setup_type is SetupType.NO_VALID_SETUP
        else (
            f"The {_setup_name(setup.setup_type)} setup is "
            f"{setup.setup_status.value.replace('_', ' ')}."
        )
    )
    return (
        f"{narrative.context} The Decision Engine remains {decision.action.value} at "
        f"{decision.confidence:.1f}/100 confidence. {setup_text}"
    )


def _recommendation(
    decision: DecisionResult,
    setup: SetupResult,
    status: TradePlanStatus,
) -> str:
    if status == "actionable":
        return (
            f"The {setup.direction} setup is actionable under the current rules; "
            "respect the defined entry and invalidation conditions."
        )
    if status in {"waiting", "developing"}:
        return "Wait for the missing setup conditions before considering entry."
    if decision.action is DecisionAction.AVOID:
        return "Avoid this market until structure, alignment, and trade quality improve."
    return "No trade is recommended because no valid setup is currently available."


def _why_sections(
    structure: MarketStructureResult,
    multi: MultiTimeframeResult,
    decision: DecisionResult,
    setup: SetupResult,
    strategy: StrategyResult | None,
) -> tuple[ExplanationSection, ...]:
    setup_message = (
        setup.human_readable_summary
        or "The Setup Engine did not provide additional setup context."
    )
    sections = [
        ExplanationSection(
            "Market context",
            _market_narrative(structure, multi).context,
            "multi_timeframe",
        ),
        ExplanationSection(
            "Decision",
            f"Weighted evidence produced {decision.action.value} with "
            f"{decision.confidence:.1f}/100 confidence.",
            "decision_engine",
        ),
        ExplanationSection("Setup", setup_message, "setup_engine"),
    ]
    if strategy and strategy.preferred_strategy is not StrategyType.NO_STRATEGY:
        sections.append(
            ExplanationSection(
                "Strategy",
                f"The Strategy Engine ranks "
                f"{strategy.preferred_strategy.value.replace('_', ' ')} highest.",
                "strategy_engine",
            )
        )
    return tuple(sections)


def _wait_conditions(setup: SetupResult) -> tuple[WaitForCondition, ...]:
    return tuple(
        WaitForCondition(
            condition=condition.condition,
            importance=condition.importance,
            source=_condition_source(condition.condition),
        )
        for condition in setup.entry_conditions
        if not condition.is_met and condition.importance == "required"
    )


def _condition_source(condition: str) -> ExplanationSource:
    normalized = condition.lower()
    if "decision engine" in normalized:
        return "decision_engine"
    if "timeframe" in normalized:
        return "multi_timeframe"
    if "risk/reward" in normalized or "risk" in normalized:
        return "risk"
    if "indicator" in normalized:
        return "indicators"
    if "structure" in normalized or "swing" in normalized:
        return "market_structure"
    return "setup_engine"


def _invalidation_notes(setup: SetupResult) -> tuple[str, ...]:
    notes: list[str] = []
    for invalidation in setup.invalidation_rules:
        rule = invalidation.rule.strip()
        if invalidation.trigger_level and invalidation.trigger_level not in rule:
            rule = f"{rule} The trigger level is {invalidation.trigger_level}."
        notes.append(rule)
    return tuple(notes)


def _plan_notes(
    decision: DecisionResult,
    setup: SetupResult,
    status: TradePlanStatus,
    strategy: StrategyResult | None,
) -> tuple[str, ...]:
    notes = [*setup.warning_notes, *decision.risk_notes]
    if status == "actionable":
        notes.append("A confirmed setup is not a guaranteed outcome.")
    if strategy and strategy.preferred_strategy is not StrategyType.NO_STRATEGY:
        notes.append(
            "Preferred broader playbook: "
            f"{strategy.preferred_strategy.value.replace('_', ' ')}."
        )
    if not notes and status in {"waiting", "developing"}:
        notes.append("Do not treat a developing setup as confirmed.")
    return tuple(dict.fromkeys(note for note in notes if note.strip()))


def _key_risks(
    decision: DecisionResult, setup: SetupResult
) -> tuple[KeyRisk, ...]:
    risks: list[KeyRisk] = []
    for evidence in decision.negative_evidence:
        severity: RiskSeverity = (
            "high" if evidence.impact <= -15 else "medium" if evidence.impact <= -5 else "low"
        )
        risks.append(
            KeyRisk(
                risk=evidence.message,
                severity=severity,
                reason="This evidence reduced the Decision Engine's confidence.",
            )
        )
    for warning in setup.warning_notes:
        severity = "high" if "conflict" in warning.lower() else "medium"
        risks.append(
            KeyRisk(
                risk=warning,
                severity=severity,
                reason="The Setup Engine identified this as a qualification warning.",
            )
        )
    for note in decision.risk_notes:
        risks.append(
            KeyRisk(
                risk=note,
                severity="medium",
                reason="Risk context remains relevant before any entry is considered.",
            )
        )
    unique: dict[str, KeyRisk] = {}
    for risk in risks:
        unique.setdefault(risk.risk, risk)
    return tuple(unique.values())


def _next_best_action(
    status: TradePlanStatus, wait_for: tuple[WaitForCondition, ...]
) -> str:
    if status == "actionable":
        return "Review the entry, invalidation, and risk checklist before acting."
    if status in {"waiting", "developing"} and wait_for:
        return f"Wait for this required condition: {wait_for[0].condition}"
    if status in {"waiting", "developing"}:
        return "Continue monitoring until the setup becomes confirmed or invalid."
    if status == "avoid":
        return "Stand aside until the Decision Engine no longer returns avoid."
    return "Wait for a valid setup to develop before planning an entry."


def _setup_name(setup_type: SetupType) -> str:
    return setup_type.value.replace("_", " ")
