from typing import cast

from core.decision_engine import DecisionAction, DecisionResult, ScoreBreakdown
from core.market_structure import MarketStructureResult, Phase, Trend
from core.multi_timeframe import (
    DirectionalBias,
    MultiTimeframeResult,
    TimeframeAlignment,
)
from core.setup_engine import (
    EntryCondition,
    InvalidationRule,
    SetupResult,
    SetupDirection,
    SetupStatus,
    SetupType,
)
from core.strategy_engine import StrategyEngine, StrategyStatus, StrategyType


ENGINE = StrategyEngine()


def _decision(action: DecisionAction) -> DecisionResult:
    return DecisionResult(
        action=action,
        confidence=85.0 if action in {DecisionAction.BUY, DecisionAction.SELL} else 65.0,
        score_breakdown=ScoreBreakdown(0, 0, 0, 0, 0, 85),
        positive_evidence=(),
        negative_evidence=(),
        neutral_evidence=(),
        risk_notes=(),
        invalidation_notes=(),
        human_readable_summary="Synthetic decision.",
    )


def _structure(
    trend: Trend,
    phase: Phase,
    events: list[str] | None = None,
) -> MarketStructureResult:
    return MarketStructureResult(
        trend=trend,
        phase=phase,
        latest_swing_high=None,
        latest_swing_low=None,
        structure_events=events or [],
        liquidity_sweep_detected=any(
            event.startswith("liquidity_sweep_") for event in events or []
        ),
        confidence_modifier=0.0,
        human_readable_summary="Synthetic structure.",
    )


def _multi(
    direction: str,
    alignment: TimeframeAlignment | None = None,
) -> MultiTimeframeResult:
    if direction == "bullish":
        trend: Trend = "bullish"
        resolved_alignment = alignment or TimeframeAlignment.ALIGNED_BULLISH
        bias = "bullish"
    elif direction == "bearish":
        trend = "bearish"
        resolved_alignment = alignment or TimeframeAlignment.ALIGNED_BEARISH
        bias = "bearish"
    else:
        trend = "ranging"
        resolved_alignment = alignment or TimeframeAlignment.MIXED
        bias = "neutral"
    return MultiTimeframeResult(
        higher_timeframe="1h",
        current_timeframe="5m",
        higher_timeframe_trend=trend,
        current_timeframe_trend=trend,
        higher_timeframe_phase="range" if trend == "ranging" else "impulse",
        current_timeframe_phase="range" if trend == "ranging" else "impulse",
        alignment=resolved_alignment,
        alignment_score=95 if "aligned" in resolved_alignment.value else 65,
        directional_bias=cast(DirectionalBias, bias),
        reasons=("Higher.", "Current.", "Context."),
        human_readable_summary="Synthetic multi-timeframe result.",
    )


def _setup(
    setup_type: SetupType,
    direction: str,
    status: SetupStatus = SetupStatus.CONFIRMED,
    risk_reward: float | None = 2.0,
) -> SetupResult:
    return SetupResult(
        setup_type=setup_type,
        setup_status=status,
        direction=cast(SetupDirection, direction),
        setup_quality_score=85.0,
        entry_zone="94-96",
        stop_loss="90",
        target="105",
        estimated_risk_reward=risk_reward,
        entry_conditions=(
            EntryCondition(
                "Current timeframe confirms the setup.",
                status is SetupStatus.CONFIRMED,
                "required",
            ),
        ),
        invalidation_rules=(
            InvalidationRule("Structure invalidates beyond the protected swing.", "90", "hard"),
        ),
        supporting_evidence=(),
        warning_notes=(),
        human_readable_summary="Synthetic setup.",
    )


def _analyze(
    action: DecisionAction,
    structure: MarketStructureResult,
    multi: MultiTimeframeResult,
    setup: SetupResult,
    *,
    near_support: bool = True,
    near_resistance: bool = False,
):
    return ENGINE.analyze(
        decision=_decision(action),
        market_structure=structure,
        multi_timeframe=multi,
        setup_plan=setup,
        price_near_support=near_support,
        price_near_resistance=near_resistance,
        indicator_supportive=True,
    )


def test_trend_continuation_preferred_when_structure_and_timeframes_align() -> None:
    result = _analyze(
        DecisionAction.BUY,
        _structure("bullish", "impulse"),
        _multi("bullish"),
        _setup(SetupType.BULLISH_PULLBACK_CONTINUATION, "bullish"),
    )

    assert result.preferred_strategy is StrategyType.TREND_CONTINUATION


def test_pullback_continuation_preferred_during_directional_pullback() -> None:
    result = _analyze(
        DecisionAction.WAIT,
        _structure("bullish", "pullback"),
        _multi("bullish", TimeframeAlignment.MIXED),
        _setup(
            SetupType.BULLISH_PULLBACK_CONTINUATION,
            "bullish",
            SetupStatus.WAITING_FOR_CONFIRMATION,
        ),
    )

    assert result.preferred_strategy is StrategyType.PULLBACK_CONTINUATION


def test_breakout_continuation_scores_when_bos_aligns() -> None:
    result = _analyze(
        DecisionAction.BUY,
        _structure("bullish", "impulse", ["bullish_bos"]),
        _multi("bullish"),
        _setup(SetupType.BULLISH_BOS_RETEST, "bullish"),
    )
    candidate = next(
        item for item in result.candidates
        if item.strategy_type is StrategyType.BREAKOUT_CONTINUATION
    )

    assert candidate.score >= 70
    assert any("BOS" in evidence for evidence in candidate.supporting_evidence)


def test_range_reversal_preferred_near_range_support() -> None:
    result = _analyze(
        DecisionAction.WAIT,
        _structure("ranging", "range"),
        _multi("neutral"),
        _setup(
            SetupType.RANGE_REVERSAL_LONG,
            "bullish",
            SetupStatus.WAITING_FOR_CONFIRMATION,
        ),
        near_support=True,
    )

    assert result.preferred_strategy is StrategyType.RANGE_REVERSAL


def test_liquidity_sweep_reversal_preferred_after_sweep() -> None:
    result = _analyze(
        DecisionAction.WAIT,
        _structure("ranging", "range", ["liquidity_sweep_low"]),
        _multi("bullish", TimeframeAlignment.MIXED),
        _setup(
            SetupType.LIQUIDITY_SWEEP_REVERSAL_LONG,
            "bullish",
            SetupStatus.WAITING_FOR_CONFIRMATION,
        ),
    )

    assert result.preferred_strategy is StrategyType.LIQUIDITY_SWEEP_REVERSAL


def test_compression_breakout_is_developing_until_confirmed() -> None:
    result = _analyze(
        DecisionAction.WAIT,
        _structure("unclear", "unclear"),
        _multi("bullish", TimeframeAlignment.MIXED),
        _setup(
            SetupType.COMPRESSION_BREAKOUT_LONG,
            "bullish",
            SetupStatus.DEVELOPING,
        ),
    )
    candidate = next(
        item for item in result.candidates
        if item.strategy_type is StrategyType.COMPRESSION_BREAKOUT
    )

    assert candidate.status is StrategyStatus.DEVELOPING


def test_avoid_decision_returns_no_strategy() -> None:
    result = _analyze(
        DecisionAction.AVOID,
        _structure("bullish", "impulse"),
        _multi("bullish"),
        _setup(SetupType.BULLISH_PULLBACK_CONTINUATION, "bullish"),
    )

    assert result.preferred_strategy is StrategyType.NO_STRATEGY
    assert all(candidate.status is StrategyStatus.REJECTED for candidate in result.candidates)


def test_wait_decision_keeps_strategy_developing_or_viable() -> None:
    result = _analyze(
        DecisionAction.WAIT,
        _structure("bullish", "pullback"),
        _multi("bullish", TimeframeAlignment.MIXED),
        _setup(
            SetupType.BULLISH_PULLBACK_CONTINUATION,
            "bullish",
            SetupStatus.WAITING_FOR_CONFIRMATION,
        ),
    )
    candidate = next(
        item for item in result.candidates
        if item.strategy_type is result.preferred_strategy
    )

    assert candidate.status in {StrategyStatus.DEVELOPING, StrategyStatus.VIABLE}
    assert candidate.status is not StrategyStatus.PREFERRED


def test_preferred_strategy_is_highest_scoring_aligned_candidate() -> None:
    result = _analyze(
        DecisionAction.BUY,
        _structure("bullish", "pullback"),
        _multi("bullish", TimeframeAlignment.MIXED),
        _setup(SetupType.BULLISH_PULLBACK_CONTINUATION, "bullish"),
    )
    preferred = next(
        candidate for candidate in result.candidates
        if candidate.strategy_type is result.preferred_strategy
    )
    aligned_scores = [
        candidate.score
        for candidate in result.candidates
        if candidate.direction == "bullish"
        and candidate.status not in {StrategyStatus.REJECTED, StrategyStatus.NOT_APPLICABLE}
    ]

    assert preferred.score == max(aligned_scores)


def test_strategy_alignment_reflects_decision_and_setup_consistency() -> None:
    aligned = _analyze(
        DecisionAction.BUY,
        _structure("bullish", "pullback"),
        _multi("bullish"),
        _setup(SetupType.BULLISH_PULLBACK_CONTINUATION, "bullish"),
    )
    partial = _analyze(
        DecisionAction.WAIT,
        _structure("bullish", "pullback"),
        _multi("bullish", TimeframeAlignment.MIXED),
        _setup(
            SetupType.BULLISH_PULLBACK_CONTINUATION,
            "bullish",
            SetupStatus.WAITING_FOR_CONFIRMATION,
        ),
    )

    assert aligned.strategy_alignment == "aligned_with_decision"
    assert partial.strategy_alignment == "partially_aligned"


def test_candidates_include_score_breakdown() -> None:
    result = _analyze(
        DecisionAction.BUY,
        _structure("bullish", "impulse"),
        _multi("bullish"),
        _setup(SetupType.BULLISH_PULLBACK_CONTINUATION, "bullish"),
    )
    breakdown = result.candidates[0].score_breakdown

    assert breakdown.total == round(
        breakdown.structure_fit
        + breakdown.timeframe_fit
        + breakdown.setup_fit
        + breakdown.risk_fit
        + breakdown.indicator_confirmation,
        1,
    )


def test_candidates_include_supporting_and_opposing_evidence() -> None:
    result = _analyze(
        DecisionAction.BUY,
        _structure("bullish", "impulse"),
        _multi("bullish"),
        _setup(SetupType.BULLISH_PULLBACK_CONTINUATION, "bullish"),
    )

    assert any(candidate.supporting_evidence for candidate in result.candidates)
    assert any(candidate.opposing_evidence for candidate in result.candidates)


def test_no_strategy_when_no_setup_meaningfully_applies() -> None:
    result = _analyze(
        DecisionAction.WAIT,
        _structure("unclear", "unclear"),
        _multi("neutral", TimeframeAlignment.UNCLEAR),
        _setup(SetupType.NO_VALID_SETUP, "neutral", SetupStatus.NO_SETUP, None),
        near_support=False,
    )

    assert result.preferred_strategy is StrategyType.NO_STRATEGY
    assert result.strategy_alignment == "no_clear_strategy"
