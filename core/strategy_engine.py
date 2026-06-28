"""Rank broader playbooks without changing decision or setup output."""

from dataclasses import dataclass, replace
from enum import Enum
from typing import Literal

from core.decision_engine import DecisionAction, DecisionResult
from core.market_structure import MarketStructureResult
from core.multi_timeframe import MultiTimeframeResult, TimeframeAlignment
from core.setup_engine import SetupResult, SetupStatus, SetupType


StrategyDirection = Literal["bullish", "bearish", "neutral"]
StrategyAlignment = Literal[
    "aligned_with_decision",
    "partially_aligned",
    "conflicts_with_decision",
    "no_clear_strategy",
]


class StrategyType(str, Enum):
    TREND_CONTINUATION = "trend_continuation"
    PULLBACK_CONTINUATION = "pullback_continuation"
    BREAKOUT_CONTINUATION = "breakout_continuation"
    RANGE_REVERSAL = "range_reversal"
    LIQUIDITY_SWEEP_REVERSAL = "liquidity_sweep_reversal"
    COMPRESSION_BREAKOUT = "compression_breakout"
    NO_STRATEGY = "no_strategy"


class StrategyStatus(str, Enum):
    PREFERRED = "preferred"
    VIABLE = "viable"
    DEVELOPING = "developing"
    NOT_APPLICABLE = "not_applicable"
    REJECTED = "rejected"


@dataclass(frozen=True)
class StrategyScoreBreakdown:
    structure_fit: float
    timeframe_fit: float
    setup_fit: float
    risk_fit: float
    indicator_confirmation: float
    total: float

    @classmethod
    def build(
        cls,
        *,
        structure_fit: float,
        timeframe_fit: float,
        setup_fit: float,
        risk_fit: float,
        indicator_confirmation: float,
    ) -> "StrategyScoreBreakdown":
        values = tuple(
            round(value, 1)
            for value in (
                structure_fit,
                timeframe_fit,
                setup_fit,
                risk_fit,
                indicator_confirmation,
            )
        )
        return cls(*values, total=round(sum(values), 1))


@dataclass(frozen=True)
class StrategyCandidate:
    strategy_type: StrategyType
    status: StrategyStatus
    direction: StrategyDirection
    score: float
    score_breakdown: StrategyScoreBreakdown
    supporting_evidence: tuple[str, ...]
    opposing_evidence: tuple[str, ...]
    required_conditions: tuple[str, ...]
    invalidation: tuple[str, ...]
    notes: tuple[str, ...]


@dataclass(frozen=True)
class StrategyResult:
    preferred_strategy: StrategyType
    candidates: tuple[StrategyCandidate, ...]
    strategy_alignment: StrategyAlignment
    human_readable_summary: str


class StrategyEngine:
    """Score all supported playbooks and select the strongest aligned candidate."""

    def analyze(
        self,
        *,
        decision: DecisionResult,
        market_structure: MarketStructureResult,
        multi_timeframe: MultiTimeframeResult,
        setup_plan: SetupResult,
        price_near_support: bool,
        price_near_resistance: bool,
        indicator_supportive: bool | None,
    ) -> StrategyResult:
        direction = _context_direction(decision, multi_timeframe, setup_plan)
        candidates = [
            _build_candidate(
                strategy_type=strategy_type,
                direction=_candidate_direction(strategy_type, direction, setup_plan),
                decision=decision,
                structure=market_structure,
                multi=multi_timeframe,
                setup=setup_plan,
                price_near_support=price_near_support,
                price_near_resistance=price_near_resistance,
                indicator_supportive=indicator_supportive,
            )
            for strategy_type in StrategyType
            if strategy_type is not StrategyType.NO_STRATEGY
        ]
        candidates.sort(key=lambda candidate: candidate.score, reverse=True)

        alignment = _strategy_alignment(decision, setup_plan, direction)
        if decision.action is DecisionAction.AVOID:
            rejected = tuple(
                replace(candidate, status=StrategyStatus.REJECTED)
                for candidate in candidates
            )
            return StrategyResult(
                preferred_strategy=StrategyType.NO_STRATEGY,
                candidates=rejected,
                strategy_alignment="no_clear_strategy",
                human_readable_summary=(
                    "No strategy is preferred because the Decision Engine returned avoid."
                ),
            )

        if alignment == "conflicts_with_decision" or setup_plan.setup_status in {
            SetupStatus.INVALID,
            SetupStatus.NO_SETUP,
        }:
            result_alignment: StrategyAlignment = (
                alignment
                if alignment == "conflicts_with_decision"
                else "no_clear_strategy"
            )
            return StrategyResult(
                preferred_strategy=StrategyType.NO_STRATEGY,
                candidates=tuple(candidates),
                strategy_alignment=result_alignment,
                human_readable_summary=(
                    "No strategy is preferred because decision and setup context do not "
                    "support the same playbook."
                ),
            )

        eligible = [
            candidate
            for candidate in candidates
            if candidate.score >= 50.0
            and candidate.status
            not in {StrategyStatus.REJECTED, StrategyStatus.NOT_APPLICABLE}
            and _direction_matches(candidate.direction, direction)
        ]
        if not eligible:
            return StrategyResult(
                preferred_strategy=StrategyType.NO_STRATEGY,
                candidates=tuple(candidates),
                strategy_alignment="no_clear_strategy",
                human_readable_summary=(
                    "No strategy candidate has enough aligned evidence to be preferred."
                ),
            )

        preferred = eligible[0]
        if (
            decision.action in {DecisionAction.BUY, DecisionAction.SELL}
            and setup_plan.setup_status is SetupStatus.CONFIRMED
        ):
            candidates = [
                replace(candidate, status=StrategyStatus.PREFERRED)
                if candidate.strategy_type is preferred.strategy_type
                else candidate
                for candidate in candidates
            ]

        summary_status = (
            "preferred"
            if decision.action in {DecisionAction.BUY, DecisionAction.SELL}
            else "most relevant but still developing"
        )
        return StrategyResult(
            preferred_strategy=preferred.strategy_type,
            candidates=tuple(candidates),
            strategy_alignment=alignment,
            human_readable_summary=(
                f"{_strategy_name(preferred.strategy_type)} is {summary_status} for the "
                "current decision and setup context."
            ),
        )


def _build_candidate(
    *,
    strategy_type: StrategyType,
    direction: StrategyDirection,
    decision: DecisionResult,
    structure: MarketStructureResult,
    multi: MultiTimeframeResult,
    setup: SetupResult,
    price_near_support: bool,
    price_near_resistance: bool,
    indicator_supportive: bool | None,
) -> StrategyCandidate:
    supporting: list[str] = []
    opposing: list[str] = []

    structure_fit = _structure_fit(
        strategy_type,
        direction,
        structure,
        setup,
        price_near_support,
        price_near_resistance,
        supporting,
        opposing,
    )
    timeframe_fit = _timeframe_fit(
        strategy_type, direction, multi, supporting, opposing
    )
    setup_fit = _setup_fit(strategy_type, direction, setup, supporting, opposing)
    risk_fit = _risk_fit(setup.estimated_risk_reward, supporting, opposing)
    indicator_fit = _indicator_fit(indicator_supportive, supporting, opposing)
    breakdown = StrategyScoreBreakdown.build(
        structure_fit=structure_fit,
        timeframe_fit=timeframe_fit,
        setup_fit=setup_fit,
        risk_fit=risk_fit,
        indicator_confirmation=indicator_fit,
    )
    status = _candidate_status(
        strategy_type, direction, breakdown.total, decision, setup, structure_fit
    )
    setup_strategy = _strategy_for_setup(setup.setup_type)
    required = _required_conditions(strategy_type, setup, setup_strategy)
    invalidation = (
        tuple(rule.rule for rule in setup.invalidation_rules)
        if direction == setup.direction
        else ()
    )
    notes = list(setup.warning_notes if setup_strategy is strategy_type else ())
    if setup_strategy is not strategy_type:
        notes.append("This playbook is broader than the currently selected setup plan.")

    return StrategyCandidate(
        strategy_type=strategy_type,
        status=status,
        direction=direction,
        score=breakdown.total,
        score_breakdown=breakdown,
        supporting_evidence=tuple(dict.fromkeys(supporting)),
        opposing_evidence=tuple(dict.fromkeys(opposing)),
        required_conditions=required,
        invalidation=invalidation,
        notes=tuple(dict.fromkeys(notes)),
    )


def _structure_fit(
    strategy: StrategyType,
    direction: StrategyDirection,
    structure: MarketStructureResult,
    setup: SetupResult,
    near_support: bool,
    near_resistance: bool,
    supporting: list[str],
    opposing: list[str],
) -> float:
    directional_trend = direction in {"bullish", "bearish"} and structure.trend == direction
    expected_bos = f"{direction}_bos"
    expected_sweep = (
        "liquidity_sweep_low"
        if direction == "bullish"
        else "liquidity_sweep_high"
    )

    if strategy is StrategyType.TREND_CONTINUATION:
        if directional_trend:
            supporting.append(f"Market structure is {direction}.")
            return 25.0 if structure.phase == "impulse" else 22.0
        opposing.append("Market structure does not support directional continuation.")
        return 0.0
    if strategy is StrategyType.PULLBACK_CONTINUATION:
        if directional_trend and structure.phase == "pullback":
            supporting.append("Directional structure is in a pullback phase.")
            return 25.0
        if directional_trend:
            supporting.append("Directional structure exists, but no pullback is active.")
            return 8.0
        opposing.append("A directional pullback is not present.")
        return 0.0
    if strategy is StrategyType.BREAKOUT_CONTINUATION:
        if direction != "neutral" and expected_bos in structure.structure_events:
            supporting.append(f"A recent {direction} BOS supports breakout continuation.")
            return 25.0
        if directional_trend:
            opposing.append("Directional trend exists, but a confirming BOS is absent.")
            return 6.0
        return 0.0
    if strategy is StrategyType.RANGE_REVERSAL:
        near_boundary = near_support if direction == "bullish" else near_resistance
        if structure.trend == "ranging" and near_boundary:
            supporting.append("Ranging structure is testing the relevant range boundary.")
            return 25.0
        if structure.trend == "ranging":
            opposing.append("Price is not near the relevant range boundary.")
            return 12.0
        return 0.0
    if strategy is StrategyType.LIQUIDITY_SWEEP_REVERSAL:
        if direction != "neutral" and expected_sweep in structure.structure_events:
            supporting.append("A liquidity sweep supports reversal in this direction.")
            return 25.0
        opposing.append("No directionally relevant liquidity sweep is confirmed.")
        return 0.0
    if strategy is StrategyType.COMPRESSION_BREAKOUT:
        if setup.setup_type in {
            SetupType.COMPRESSION_BREAKOUT_LONG,
            SetupType.COMPRESSION_BREAKOUT_SHORT,
        }:
            supporting.append("The Setup Engine identified a compression breakout candidate.")
            return 22.0 if setup.setup_status is SetupStatus.CONFIRMED else 18.0
        return 0.0
    return 0.0


def _timeframe_fit(
    strategy: StrategyType,
    direction: StrategyDirection,
    multi: MultiTimeframeResult,
    supporting: list[str],
    opposing: list[str],
) -> float:
    expected_alignment = (
        TimeframeAlignment.ALIGNED_BULLISH
        if direction == "bullish"
        else TimeframeAlignment.ALIGNED_BEARISH
        if direction == "bearish"
        else None
    )
    if multi.alignment is expected_alignment:
        supporting.append("Higher and current timeframes align with the playbook direction.")
        return 25.0
    if strategy is StrategyType.RANGE_REVERSAL and (
        multi.higher_timeframe_trend == "ranging"
        or multi.current_timeframe_trend == "ranging"
    ):
        supporting.append("Timeframe context supports range behavior.")
        return 22.0
    if multi.alignment is TimeframeAlignment.MIXED and multi.directional_bias == direction:
        supporting.append("Mixed alignment still preserves the playbook direction.")
        return 18.0
    if multi.alignment is TimeframeAlignment.CONFLICTING:
        opposing.append("Timeframe structures conflict with one another.")
        return 0.0
    if multi.alignment is TimeframeAlignment.UNCLEAR:
        opposing.append("Timeframe alignment is unclear.")
        return 4.0
    return 8.0


def _setup_fit(
    strategy: StrategyType,
    direction: StrategyDirection,
    setup: SetupResult,
    supporting: list[str],
    opposing: list[str],
) -> float:
    setup_strategy = _strategy_for_setup(setup.setup_type)
    if setup_strategy is strategy and setup.direction == direction:
        supporting.append("The selected setup directly matches this playbook.")
        if setup.setup_status is SetupStatus.CONFIRMED:
            return 25.0
        if setup.setup_status in {
            SetupStatus.DEVELOPING,
            SetupStatus.WAITING_FOR_CONFIRMATION,
        }:
            return 20.0
        return 5.0
    if setup.direction == direction and setup.setup_type is not SetupType.NO_VALID_SETUP:
        supporting.append("The setup direction is compatible with this broader playbook.")
        return 12.0
    opposing.append("The selected setup does not directly support this playbook.")
    return 0.0


def _risk_fit(
    risk_reward: float | None,
    supporting: list[str],
    opposing: list[str],
) -> float:
    if risk_reward is None:
        opposing.append("Risk/reward is unavailable.")
        return 3.0
    if risk_reward >= 2.0:
        supporting.append(f"Risk/reward is favorable at {risk_reward:.2f}R.")
        return 15.0
    if risk_reward >= 1.5:
        supporting.append(f"Risk/reward meets the setup threshold at {risk_reward:.2f}R.")
        return 12.0
    if risk_reward >= 1.0:
        opposing.append(f"Risk/reward is marginal at {risk_reward:.2f}R.")
        return 7.0
    opposing.append(f"Risk/reward is poor at {risk_reward:.2f}R.")
    return 2.0


def _indicator_fit(
    supportive: bool | None,
    supporting: list[str],
    opposing: list[str],
) -> float:
    if supportive is True:
        supporting.append("Available indicator context confirms the structural thesis.")
        return 10.0
    if supportive is False:
        opposing.append("Available indicator context does not confirm the structural thesis.")
        return 3.0
    return 5.0


def _candidate_status(
    strategy: StrategyType,
    direction: StrategyDirection,
    score: float,
    decision: DecisionResult,
    setup: SetupResult,
    structure_fit: float,
) -> StrategyStatus:
    expected_direction = _decision_action_direction(decision.action)
    if decision.action is DecisionAction.AVOID:
        return StrategyStatus.REJECTED
    if expected_direction and direction != expected_direction:
        return StrategyStatus.REJECTED
    if setup.direction != "neutral" and direction != setup.direction:
        return StrategyStatus.REJECTED
    if structure_fit <= 0.0 or score < 40.0:
        return StrategyStatus.NOT_APPLICABLE
    if decision.action is DecisionAction.WAIT:
        return StrategyStatus.DEVELOPING
    if (
        _strategy_for_setup(setup.setup_type) is strategy
        and setup.setup_status is SetupStatus.CONFIRMED
        and score >= 65.0
    ):
        return StrategyStatus.VIABLE
    return StrategyStatus.VIABLE if score >= 55.0 else StrategyStatus.DEVELOPING


def _required_conditions(
    strategy: StrategyType,
    setup: SetupResult,
    setup_strategy: StrategyType,
) -> tuple[str, ...]:
    if setup_strategy is strategy:
        unmet = tuple(
            condition.condition
            for condition in setup.entry_conditions
            if not condition.is_met and condition.importance == "required"
        )
        if unmet:
            return unmet
    defaults = {
        StrategyType.TREND_CONTINUATION: "Directional structure remains intact.",
        StrategyType.PULLBACK_CONTINUATION: "The pullback confirms continuation.",
        StrategyType.BREAKOUT_CONTINUATION: "Price confirms and holds beyond broken structure.",
        StrategyType.RANGE_REVERSAL: "The relevant range boundary rejects price.",
        StrategyType.LIQUIDITY_SWEEP_REVERSAL: "Price confirms rejection after the sweep.",
        StrategyType.COMPRESSION_BREAKOUT: "Price closes beyond the compression boundary.",
    }
    return (defaults[strategy],)


def _context_direction(
    decision: DecisionResult,
    multi: MultiTimeframeResult,
    setup: SetupResult,
) -> StrategyDirection:
    action_direction = _decision_action_direction(decision.action)
    if action_direction:
        return action_direction
    if setup.direction in {"bullish", "bearish"}:
        return setup.direction
    if multi.directional_bias in {"bullish", "bearish"}:
        return multi.directional_bias
    return "neutral"


def _candidate_direction(
    strategy: StrategyType,
    context_direction: StrategyDirection,
    setup: SetupResult,
) -> StrategyDirection:
    setup_strategy = _strategy_for_setup(setup.setup_type)
    if setup_strategy is strategy and setup.direction in {"bullish", "bearish"}:
        return setup.direction
    return context_direction


def _strategy_for_setup(setup_type: SetupType) -> StrategyType:
    mapping = {
        SetupType.BULLISH_BOS_RETEST: StrategyType.BREAKOUT_CONTINUATION,
        SetupType.BEARISH_BOS_RETEST: StrategyType.BREAKOUT_CONTINUATION,
        SetupType.BULLISH_PULLBACK_CONTINUATION: StrategyType.PULLBACK_CONTINUATION,
        SetupType.BEARISH_PULLBACK_CONTINUATION: StrategyType.PULLBACK_CONTINUATION,
        SetupType.RANGE_REVERSAL_LONG: StrategyType.RANGE_REVERSAL,
        SetupType.RANGE_REVERSAL_SHORT: StrategyType.RANGE_REVERSAL,
        SetupType.LIQUIDITY_SWEEP_REVERSAL_LONG: StrategyType.LIQUIDITY_SWEEP_REVERSAL,
        SetupType.LIQUIDITY_SWEEP_REVERSAL_SHORT: StrategyType.LIQUIDITY_SWEEP_REVERSAL,
        SetupType.COMPRESSION_BREAKOUT_LONG: StrategyType.COMPRESSION_BREAKOUT,
        SetupType.COMPRESSION_BREAKOUT_SHORT: StrategyType.COMPRESSION_BREAKOUT,
        SetupType.NO_VALID_SETUP: StrategyType.NO_STRATEGY,
    }
    return mapping[setup_type]


def _strategy_alignment(
    decision: DecisionResult,
    setup: SetupResult,
    direction: StrategyDirection,
) -> StrategyAlignment:
    action_direction = _decision_action_direction(decision.action)
    if action_direction and setup.direction not in {"neutral", action_direction}:
        return "conflicts_with_decision"
    if action_direction and direction == action_direction:
        return "aligned_with_decision"
    if decision.action is DecisionAction.WAIT and direction in {"bullish", "bearish"}:
        return "partially_aligned"
    return "no_clear_strategy"


def _decision_action_direction(
    action: DecisionAction,
) -> Literal["bullish", "bearish"] | None:
    if action is DecisionAction.BUY:
        return "bullish"
    if action is DecisionAction.SELL:
        return "bearish"
    return None


def _direction_matches(
    candidate: StrategyDirection, context: StrategyDirection
) -> bool:
    return context == "neutral" or candidate == context


def _strategy_name(strategy: StrategyType) -> str:
    return strategy.value.replace("_", " ").capitalize()
