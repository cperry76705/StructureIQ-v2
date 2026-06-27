"""Weighted, explainable trade-decision engine for StructureIQ v0.4."""

from dataclasses import dataclass
from enum import Enum
from typing import Literal

from core.market_structure import MarketStructureResult
from core.multi_timeframe import MultiTimeframeResult, TimeframeAlignment


EvidenceCategory = Literal[
    "market_structure",
    "multi_timeframe",
    "support_resistance_liquidity",
    "indicators",
    "risk_reward_volatility",
]
TradeDirection = Literal["bullish", "bearish"]


class DecisionAction(str, Enum):
    BUY = "buy"
    SELL = "sell"
    WAIT = "wait"
    AVOID = "avoid"


@dataclass(frozen=True)
class EvidenceItem:
    """One traceable observation and its directional score impact."""

    category: EvidenceCategory
    message: str
    impact: float


@dataclass(frozen=True)
class ScoreBreakdown:
    """Weighted category contributions on a 0–100 confidence scale."""

    market_structure: float
    multi_timeframe: float
    support_resistance_liquidity: float
    indicators: float
    risk_reward_volatility: float
    total: float

    @classmethod
    def build(
        cls,
        *,
        market_structure: float,
        multi_timeframe: float,
        support_resistance_liquidity: float,
        indicators: float,
        risk_reward_volatility: float,
    ) -> "ScoreBreakdown":
        values = tuple(
            round(value, 1)
            for value in (
                market_structure,
                multi_timeframe,
                support_resistance_liquidity,
                indicators,
                risk_reward_volatility,
            )
        )
        return cls(*values, total=round(sum(values), 1))


@dataclass(frozen=True)
class DecisionResult:
    """Complete decision, score, evidence, and risk explanation."""

    action: DecisionAction
    confidence: float
    score_breakdown: ScoreBreakdown
    positive_evidence: tuple[EvidenceItem, ...]
    negative_evidence: tuple[EvidenceItem, ...]
    neutral_evidence: tuple[EvidenceItem, ...]
    risk_notes: tuple[str, ...]
    invalidation_notes: tuple[str, ...]
    human_readable_summary: str


class DecisionEngine:
    """Convert analytical evidence into a weighted, guarded decision."""

    def analyze(
        self,
        *,
        market_structure: MarketStructureResult,
        multi_timeframe: MultiTimeframeResult,
        price_near_level: bool,
        indicator_supportive: bool | None,
        current_timeframe_confirmed: bool,
        risk_reward_ratio: float | None,
        volatility_adequate: bool | None = None,
    ) -> DecisionResult:
        direction = _thesis_direction(market_structure, multi_timeframe)
        positive: list[EvidenceItem] = []
        negative: list[EvidenceItem] = []
        neutral: list[EvidenceItem] = []

        structure_points = _score_market_structure(
            market_structure, direction, positive, negative, neutral
        )
        timeframe_points = _score_multi_timeframe(
            multi_timeframe, positive, negative, neutral
        )
        context_points = _score_price_context(
            market_structure,
            direction,
            price_near_level,
            positive,
            negative,
            neutral,
        )
        indicator_points = _score_indicators(
            indicator_supportive, positive, negative, neutral
        )
        risk_points, risk_notes = _score_risk(
            risk_reward_ratio,
            volatility_adequate,
            positive,
            negative,
            neutral,
        )
        breakdown = ScoreBreakdown.build(
            market_structure=structure_points,
            multi_timeframe=timeframe_points,
            support_resistance_liquidity=context_points,
            indicators=indicator_points,
            risk_reward_volatility=risk_points,
        )

        action = _select_action(
            confidence=breakdown.total,
            direction=direction,
            market_structure=market_structure,
            multi_timeframe=multi_timeframe,
            current_timeframe_confirmed=current_timeframe_confirmed,
            risk_reward_ratio=risk_reward_ratio,
        )
        invalidation_notes = _build_invalidation_notes(
            direction, market_structure
        )

        return DecisionResult(
            action=action,
            confidence=breakdown.total,
            score_breakdown=breakdown,
            positive_evidence=tuple(positive),
            negative_evidence=tuple(negative),
            neutral_evidence=tuple(neutral),
            risk_notes=tuple(risk_notes),
            invalidation_notes=tuple(invalidation_notes),
            human_readable_summary=_build_summary(
                action,
                breakdown.total,
                direction,
                multi_timeframe,
                current_timeframe_confirmed,
            ),
        )


def _thesis_direction(
    structure: MarketStructureResult, multi_timeframe: MultiTimeframeResult
) -> TradeDirection | None:
    if multi_timeframe.directional_bias in {"bullish", "bearish"}:
        return multi_timeframe.directional_bias
    if multi_timeframe.higher_timeframe_trend in {"bullish", "bearish"}:
        return multi_timeframe.higher_timeframe_trend
    if structure.trend in {"bullish", "bearish"}:
        return structure.trend
    return None


def _score_market_structure(
    structure: MarketStructureResult,
    direction: TradeDirection | None,
    positive: list[EvidenceItem],
    negative: list[EvidenceItem],
    neutral: list[EvidenceItem],
) -> float:
    category: EvidenceCategory = "market_structure"
    if direction is None or structure.trend == "unclear":
        neutral.append(
            EvidenceItem(category, "Market structure is unclear.", 0.0)
        )
        return 35.0 * 0.15

    if structure.trend == direction:
        quality = 0.8 if structure.phase == "impulse" else 0.65
        expected_bos = f"{direction}_bos"
        opposing_choch = "bearish_choch" if direction == "bullish" else "bullish_choch"
        if expected_bos in structure.structure_events:
            quality += 0.2
            positive.append(
                EvidenceItem(
                    category,
                    f"Execution structure confirmed a {direction} break of structure.",
                    7.0,
                )
            )
        if opposing_choch in structure.structure_events:
            quality -= 0.25
            negative.append(
                EvidenceItem(
                    category,
                    "Execution structure shows a change of character against the thesis.",
                    -8.8,
                )
            )
        positive.append(
            EvidenceItem(
                category,
                f"Execution-timeframe structure is {structure.trend}.",
                round(35.0 * max(0.0, min(quality, 1.0)), 1),
            )
        )
        return 35.0 * max(0.0, min(quality, 1.0))

    if structure.trend == "ranging":
        neutral.append(
            EvidenceItem(
                category,
                "Execution-timeframe structure is ranging and lacks directional confirmation.",
                0.0,
            )
        )
        return 35.0 * 0.35

    negative.append(
        EvidenceItem(
            category,
            f"Execution-timeframe structure is {structure.trend}, against the {direction} thesis.",
            -31.5,
        )
    )
    return 35.0 * 0.1


def _score_multi_timeframe(
    result: MultiTimeframeResult,
    positive: list[EvidenceItem],
    negative: list[EvidenceItem],
    neutral: list[EvidenceItem],
) -> float:
    category: EvidenceCategory = "multi_timeframe"
    points = 25.0 * max(0.0, min(result.alignment_score, 100.0)) / 100.0
    if result.alignment in {
        TimeframeAlignment.ALIGNED_BULLISH,
        TimeframeAlignment.ALIGNED_BEARISH,
    }:
        positive.append(
            EvidenceItem(
                category,
                "Higher and current timeframe structures agree directionally.",
                round(points, 1),
            )
        )
    elif result.alignment is TimeframeAlignment.CONFLICTING:
        negative.append(
            EvidenceItem(
                category,
                "Higher and current timeframe structures conflict.",
                round(-(25.0 - points), 1),
            )
        )
    elif result.alignment is TimeframeAlignment.MIXED:
        neutral.append(
            EvidenceItem(
                category,
                result.reasons[-1],
                0.0,
            )
        )
    else:
        negative.append(
            EvidenceItem(
                category,
                "Timeframe alignment is unclear.",
                round(-(25.0 - points), 1),
            )
        )
    return points


def _score_price_context(
    structure: MarketStructureResult,
    direction: TradeDirection | None,
    price_near_level: bool,
    positive: list[EvidenceItem],
    negative: list[EvidenceItem],
    neutral: list[EvidenceItem],
) -> float:
    category: EvidenceCategory = "support_resistance_liquidity"
    quality = 0.65 if price_near_level else 0.25
    if price_near_level:
        positive.append(
            EvidenceItem(category, "Price is testing a relevant structural zone.", 9.8)
        )
    else:
        neutral.append(
            EvidenceItem(category, "Price is not near the relevant structural zone.", 0.0)
        )

    favorable_sweep = (
        "liquidity_sweep_low"
        if direction == "bullish"
        else "liquidity_sweep_high" if direction == "bearish" else None
    )
    adverse_sweep = (
        "liquidity_sweep_high"
        if direction == "bullish"
        else "liquidity_sweep_low" if direction == "bearish" else None
    )
    if favorable_sweep and favorable_sweep in structure.structure_events:
        quality += 0.35
        positive.append(
            EvidenceItem(
                category,
                "A liquidity sweep supports reversal in the thesis direction.",
                5.2,
            )
        )
    if adverse_sweep and adverse_sweep in structure.structure_events:
        quality -= 0.35
        negative.append(
            EvidenceItem(
                category,
                "A liquidity sweep warns against the thesis direction.",
                -5.2,
            )
        )
    return 15.0 * max(0.0, min(quality, 1.0))


def _score_indicators(
    supportive: bool | None,
    positive: list[EvidenceItem],
    negative: list[EvidenceItem],
    neutral: list[EvidenceItem],
) -> float:
    category: EvidenceCategory = "indicators"
    if supportive is True:
        positive.append(
            EvidenceItem(
                category,
                "Available indicator context supports the structural thesis.",
                12.0,
            )
        )
        return 15.0 * 0.8
    if supportive is False:
        negative.append(
            EvidenceItem(
                category,
                "Available indicator context does not support the structural thesis.",
                -11.2,
            )
        )
        return 15.0 * 0.25
    neutral.append(
        EvidenceItem(category, "Indicator confirmation is unavailable.", 0.0)
    )
    return 15.0 * 0.3


def _score_risk(
    risk_reward_ratio: float | None,
    volatility_adequate: bool | None,
    positive: list[EvidenceItem],
    negative: list[EvidenceItem],
    neutral: list[EvidenceItem],
) -> tuple[float, list[str]]:
    category: EvidenceCategory = "risk_reward_volatility"
    notes: list[str] = []
    if risk_reward_ratio is None:
        reward_quality = 0.1
        negative.append(
            EvidenceItem(category, "Risk/reward could not be established.", -7.2)
        )
        notes.append("Wait for valid entry, invalidation, and target levels before taking risk.")
    elif risk_reward_ratio >= 2.0:
        reward_quality = 1.0
        positive.append(
            EvidenceItem(
                category,
                f"Estimated risk/reward is favorable at {risk_reward_ratio:.2f}:1.",
                8.0,
            )
        )
    elif risk_reward_ratio >= 1.5:
        reward_quality = 0.8
        positive.append(
            EvidenceItem(
                category,
                f"Estimated risk/reward is acceptable at {risk_reward_ratio:.2f}:1.",
                6.4,
            )
        )
    elif risk_reward_ratio >= 1.0:
        reward_quality = 0.55
        neutral.append(
            EvidenceItem(
                category,
                f"Estimated risk/reward is marginal at {risk_reward_ratio:.2f}:1.",
                0.0,
            )
        )
        notes.append("Risk/reward is marginal; require stronger confirmation.")
    else:
        reward_quality = 0.2
        negative.append(
            EvidenceItem(
                category,
                f"Estimated risk/reward is poor at {risk_reward_ratio:.2f}:1.",
                -6.4,
            )
        )
        notes.append("Avoid entry while expected reward is smaller than defined risk.")

    volatility_quality = 0.2 if volatility_adequate is True else 0.0
    if volatility_adequate is False:
        negative.append(
            EvidenceItem(category, "Volatility conditions are unsuitable.", -2.0)
        )
        notes.append("Current volatility conditions weaken trade quality.")
    elif volatility_adequate is None:
        volatility_quality = 0.05
        neutral.append(
            EvidenceItem(category, "Volatility quality is not yet available.", 0.0)
        )
        notes.append("ATR-based volatility context is not yet available in v0.4.")

    return 10.0 * min(reward_quality * 0.8 + volatility_quality, 1.0), notes


def _select_action(
    *,
    confidence: float,
    direction: TradeDirection | None,
    market_structure: MarketStructureResult,
    multi_timeframe: MultiTimeframeResult,
    current_timeframe_confirmed: bool,
    risk_reward_ratio: float | None,
) -> DecisionAction:
    if confidence < 50.0:
        return DecisionAction.AVOID
    if confidence < 70.0:
        return DecisionAction.WAIT
    if direction is None:
        return DecisionAction.WAIT
    if multi_timeframe.alignment in {
        TimeframeAlignment.CONFLICTING,
        TimeframeAlignment.UNCLEAR,
    }:
        return DecisionAction.WAIT
    if market_structure.trend != direction:
        return DecisionAction.WAIT

    aligned = multi_timeframe.alignment is (
        TimeframeAlignment.ALIGNED_BULLISH
        if direction == "bullish"
        else TimeframeAlignment.ALIGNED_BEARISH
    )
    mixed_confirmed = (
        multi_timeframe.alignment is TimeframeAlignment.MIXED
        and market_structure.trend == direction
        and current_timeframe_confirmed
    )
    if not aligned and not mixed_confirmed:
        return DecisionAction.WAIT
    if risk_reward_ratio is None or risk_reward_ratio < 1.0:
        return DecisionAction.WAIT
    return DecisionAction.BUY if direction == "bullish" else DecisionAction.SELL


def _build_invalidation_notes(
    direction: TradeDirection | None, structure: MarketStructureResult
) -> list[str]:
    if direction == "bullish" and structure.latest_swing_low is not None:
        return [
            "Bullish thesis weakens if price closes below the latest confirmed "
            f"swing low at {structure.latest_swing_low.price:.2f}."
        ]
    if direction == "bearish" and structure.latest_swing_high is not None:
        return [
            "Bearish thesis weakens if price closes above the latest confirmed "
            f"swing high at {structure.latest_swing_high.price:.2f}."
        ]
    return ["No confirmed structural invalidation level is currently available."]


def _build_summary(
    action: DecisionAction,
    confidence: float,
    direction: TradeDirection | None,
    multi_timeframe: MultiTimeframeResult,
    current_timeframe_confirmed: bool,
) -> str:
    if action is DecisionAction.AVOID:
        return (
            f"StructureIQ recommends avoiding a trade because confidence is {confidence:.1f}/100 "
            "and the available evidence is insufficient or materially weak."
        )
    if action is DecisionAction.WAIT:
        if multi_timeframe.alignment is TimeframeAlignment.CONFLICTING:
            reason = "the higher and current timeframes conflict"
        elif (
            multi_timeframe.alignment is TimeframeAlignment.MIXED
            and not current_timeframe_confirmed
        ):
            reason = "the current timeframe has not confirmed the mixed higher-timeframe context"
        else:
            reason = "the evidence has not cleared every direction and risk gate"
        return (
            f"StructureIQ recommends waiting because {reason}; confidence is "
            f"{confidence:.1f}/100."
        )
    strength = "high-confidence " if confidence >= 85.0 else ""
    return (
        f"StructureIQ favors a {strength}{action.value} decision because {direction} "
        f"structure and timeframe context agree; confidence is {confidence:.1f}/100."
    )
