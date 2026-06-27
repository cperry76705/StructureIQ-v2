"""Two-timeframe market-structure alignment for StructureIQ v0.3."""

from dataclasses import dataclass
from enum import Enum
from typing import Literal

from core.market_structure import MarketStructureResult, Phase, Trend


DirectionalBias = Literal["bullish", "bearish", "neutral", "unclear"]


class TimeframeAlignment(str, Enum):
    """Relationship between higher-timeframe context and current structure."""

    ALIGNED_BULLISH = "aligned_bullish"
    ALIGNED_BEARISH = "aligned_bearish"
    MIXED = "mixed"
    CONFLICTING = "conflicting"
    UNCLEAR = "unclear"


@dataclass(frozen=True)
class TimeframeAnalysis:
    """Structure evidence for one named timeframe."""

    timeframe: str
    trend: Trend
    phase: Phase
    structure_events: tuple[str, ...]
    human_readable_summary: str

    @classmethod
    def from_structure(
        cls, timeframe: str, structure: MarketStructureResult
    ) -> "TimeframeAnalysis":
        return cls(
            timeframe=timeframe,
            trend=structure.trend,
            phase=structure.phase,
            structure_events=tuple(structure.structure_events),
            human_readable_summary=structure.human_readable_summary,
        )


@dataclass(frozen=True)
class MultiTimeframeResult:
    """Unified higher/current-timeframe context returned by the v0.3 engine."""

    higher_timeframe: str
    current_timeframe: str
    higher_timeframe_trend: Trend
    current_timeframe_trend: Trend
    higher_timeframe_phase: Phase
    current_timeframe_phase: Phase
    alignment: TimeframeAlignment
    alignment_score: int
    directional_bias: DirectionalBias
    reasons: tuple[str, ...]
    human_readable_summary: str


class MultiTimeframeEngine:
    """Evaluate directional context across exactly two structure results."""

    def analyze(
        self,
        higher_timeframe: str,
        current_timeframe: str,
        higher_structure: MarketStructureResult,
        current_structure: MarketStructureResult,
    ) -> MultiTimeframeResult:
        higher = TimeframeAnalysis.from_structure(
            higher_timeframe, higher_structure
        )
        current = TimeframeAnalysis.from_structure(
            current_timeframe, current_structure
        )
        alignment, score, bias, context_reason = _classify_alignment(higher, current)

        reasons = (
            f"Higher timeframe {higher.timeframe} is {higher.trend} "
            f"in {_phase_with_article(higher.phase)} phase.",
            f"Current timeframe {current.timeframe} is {current.trend} "
            f"in {_phase_with_article(current.phase)} phase.",
            context_reason,
        )
        summary = _build_summary(higher, current, alignment, score, bias)

        return MultiTimeframeResult(
            higher_timeframe=higher.timeframe,
            current_timeframe=current.timeframe,
            higher_timeframe_trend=higher.trend,
            current_timeframe_trend=current.trend,
            higher_timeframe_phase=higher.phase,
            current_timeframe_phase=current.phase,
            alignment=alignment,
            alignment_score=score,
            directional_bias=bias,
            reasons=reasons,
            human_readable_summary=summary,
        )


def _phase_with_article(phase: Phase) -> str:
    article = "an" if phase in {"impulse", "unclear"} else "a"
    return f"{article} {phase.replace('_', ' ')}"


def _classify_alignment(
    higher: TimeframeAnalysis, current: TimeframeAnalysis
) -> tuple[TimeframeAlignment, int, DirectionalBias, str]:
    if higher.trend == "unclear":
        return (
            TimeframeAlignment.UNCLEAR,
            15,
            "unclear",
            "Higher-timeframe structure is unclear, so no directional bias is assigned.",
        )
    if current.trend == "unclear":
        bias: DirectionalBias = (
            higher.trend if higher.trend in {"bullish", "bearish"} else "unclear"
        )
        return (
            TimeframeAlignment.UNCLEAR,
            30,
            bias,
            "Current-timeframe structure is unclear, reducing execution confidence.",
        )

    if higher.trend in {"bullish", "bearish"}:
        higher_bias: DirectionalBias = higher.trend
        opposite = "bearish" if higher.trend == "bullish" else "bullish"
        if current.trend == opposite:
            return (
                TimeframeAlignment.CONFLICTING,
                20,
                "neutral",
                "Current structure directly opposes the higher-timeframe direction.",
            )
        if current.trend == "ranging":
            return (
                TimeframeAlignment.MIXED,
                60,
                higher_bias,
                "Current structure is ranging inside the directional higher-timeframe context.",
            )
        if current.phase == "pullback":
            return (
                TimeframeAlignment.MIXED,
                70,
                higher_bias,
                "Current structure is pulling back within the higher-timeframe direction.",
            )
        if current.phase == "reversal_attempt":
            return (
                TimeframeAlignment.MIXED,
                50,
                higher_bias,
                "Current structure shows a reversal attempt against otherwise aligned trends.",
            )

        alignment = (
            TimeframeAlignment.ALIGNED_BULLISH
            if higher.trend == "bullish"
            else TimeframeAlignment.ALIGNED_BEARISH
        )
        return (
            alignment,
            95,
            higher_bias,
            "Both timeframes confirm the same directional structure.",
        )

    if higher.trend == "ranging":
        reason = (
            "Both timeframes are ranging, so there is no directional edge."
            if current.trend == "ranging"
            else "The higher timeframe is ranging despite directional current structure."
        )
        return TimeframeAlignment.MIXED, 45, "neutral", reason

    return (
        TimeframeAlignment.UNCLEAR,
        0,
        "unclear",
        "The available structure cannot be classified across timeframes.",
    )


def _build_summary(
    higher: TimeframeAnalysis,
    current: TimeframeAnalysis,
    alignment: TimeframeAlignment,
    score: int,
    bias: DirectionalBias,
) -> str:
    bias_text = (
        f"Directional bias is {bias}."
        if bias != "unclear"
        else "Directional bias remains unclear."
    )
    return (
        f"{higher.timeframe} {higher.trend} context and {current.timeframe} "
        f"{current.trend} execution structure are {alignment.value.replace('_', ' ')} "
        f"({score}/100). {bias_text}"
    )
