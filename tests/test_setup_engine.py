from typing import cast

from core.decision_engine import (
    DecisionAction,
    DecisionResult,
    ScoreBreakdown,
)
from core.market_structure import MarketStructureResult, Phase, Trend
from core.multi_timeframe import (
    DirectionalBias,
    MultiTimeframeResult,
    TimeframeAlignment,
)
from core.setup_engine import (
    CompressionDirection,
    SetupEngine,
    SetupStatus,
    SetupType,
)
from core.structure import SwingPoint


ENGINE = SetupEngine()


def _decision(action: DecisionAction) -> DecisionResult:
    confidence = 82.0 if action in {DecisionAction.BUY, DecisionAction.SELL} else 62.0
    return DecisionResult(
        action=action,
        confidence=confidence,
        score_breakdown=ScoreBreakdown(0, 0, 0, 0, 0, confidence),
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
        latest_swing_high=SwingPoint(5, 110.0, "high"),
        latest_swing_low=SwingPoint(4, 90.0, "low"),
        structure_events=events or [],
        liquidity_sweep_detected=any(
            event.startswith("liquidity_sweep_") for event in events or []
        ),
        confidence_modifier=0.0,
        human_readable_summary="Synthetic structure.",
    )


def _multi(direction: str) -> MultiTimeframeResult:
    trend = cast(
        Trend, direction if direction in {"bullish", "bearish"} else "ranging"
    )
    alignment = (
        TimeframeAlignment.ALIGNED_BULLISH
        if direction == "bullish"
        else TimeframeAlignment.ALIGNED_BEARISH
        if direction == "bearish"
        else TimeframeAlignment.MIXED
    )
    return MultiTimeframeResult(
        higher_timeframe="1h",
        current_timeframe="5m",
        higher_timeframe_trend=trend,
        current_timeframe_trend=trend,
        higher_timeframe_phase="impulse" if trend != "ranging" else "range",
        current_timeframe_phase="impulse" if trend != "ranging" else "range",
        alignment=alignment,
        alignment_score=95 if trend != "ranging" else 45,
        directional_bias=cast(
            DirectionalBias,
            direction if direction in {"bullish", "bearish"} else "neutral",
        ),
        reasons=("Higher.", "Current.", "Context."),
        human_readable_summary="Synthetic alignment.",
    )


def _analyze(
    decision: DecisionAction,
    structure: MarketStructureResult,
    *,
    direction: str,
    price: float,
    confirmed: bool = True,
    risk_reward: float | None = 2.0,
    entry_zone: str | None = "94-96",
    stop_loss: str | None = "90",
    target: str | None = "105",
    compression: bool = False,
    breakout_direction: str | None = None,
):
    return ENGINE.analyze(
        decision=_decision(decision),
        market_structure=structure,
        multi_timeframe=_multi(direction),
        current_price=price,
        support_zone=(94.0, 96.0),
        resistance_zone=(104.0, 106.0),
        current_timeframe_confirmed=confirmed,
        estimated_risk_reward=risk_reward,
        entry_zone=entry_zone,
        stop_loss=stop_loss,
        target=target,
        compression_detected=compression,
        compression_breakout_direction=cast(
            CompressionDirection | None, breakout_direction
        ),
    )


def test_bullish_bos_retest_setup() -> None:
    result = _analyze(
        DecisionAction.BUY,
        _structure("bullish", "impulse", ["bullish_bos"]),
        direction="bullish",
        price=95.0,
    )

    assert result.setup_type is SetupType.BULLISH_BOS_RETEST
    assert result.setup_status is SetupStatus.CONFIRMED
    assert result.setup_level_diagnostics.level_quality == "complete"
    assert result.setup_level_diagnostics.entry_zone_source == "support_zone"
    assert result.setup_level_diagnostics.latest_swing_low == 90.0
    selected = next(item for item in result.setup_candidate_diagnostics if item.was_selected)
    assert selected.candidate_setup_type == SetupType.BULLISH_BOS_RETEST.value
    assert result.setup_type is SetupType.BULLISH_BOS_RETEST


def test_missing_risk_levels_cannot_confirm_setup() -> None:
    result = _analyze(
        DecisionAction.BUY,
        _structure("bullish", "impulse", ["bullish_bos"]),
        direction="bullish",
        price=95.0,
        target=None,
    )

    assert result.setup_status is SetupStatus.WAITING_FOR_CONFIRMATION
    assert result.setup_level_diagnostics.level_quality == "partial"
    assert result.setup_level_diagnostics.target_source == "unavailable"
    level_condition = next(
        condition for condition in result.entry_conditions
        if condition.condition == "Entry, stop loss, and target levels are available."
    )
    assert level_condition.is_met is False


def test_bearish_bos_retest_setup() -> None:
    result = _analyze(
        DecisionAction.SELL,
        _structure("bearish", "impulse", ["bearish_bos"]),
        direction="bearish",
        price=105.0,
    )

    assert result.setup_type is SetupType.BEARISH_BOS_RETEST
    assert result.setup_status is SetupStatus.CONFIRMED


def test_bullish_pullback_continuation() -> None:
    result = _analyze(
        DecisionAction.BUY,
        _structure("bullish", "pullback"),
        direction="bullish",
        price=95.0,
    )

    assert result.setup_type is SetupType.BULLISH_PULLBACK_CONTINUATION


def test_bearish_pullback_continuation() -> None:
    result = _analyze(
        DecisionAction.SELL,
        _structure("bearish", "pullback"),
        direction="bearish",
        price=105.0,
    )

    assert result.setup_type is SetupType.BEARISH_PULLBACK_CONTINUATION


def test_range_reversal_long_near_support() -> None:
    result = _analyze(
        DecisionAction.WAIT,
        _structure("ranging", "range"),
        direction="neutral",
        price=95.0,
    )

    assert result.setup_type is SetupType.RANGE_REVERSAL_LONG


def test_range_reversal_short_near_resistance() -> None:
    result = _analyze(
        DecisionAction.WAIT,
        _structure("ranging", "range"),
        direction="neutral",
        price=105.0,
    )

    assert result.setup_type is SetupType.RANGE_REVERSAL_SHORT


def test_no_setup_in_middle_of_range() -> None:
    result = _analyze(
        DecisionAction.WAIT,
        _structure("ranging", "range"),
        direction="neutral",
        price=100.0,
    )

    assert result.setup_type is SetupType.NO_VALID_SETUP
    assert result.setup_status is SetupStatus.NO_SETUP


def test_liquidity_sweep_reversal_long() -> None:
    result = _analyze(
        DecisionAction.WAIT,
        _structure("ranging", "range", ["liquidity_sweep_low"]),
        direction="neutral",
        price=95.0,
    )

    assert result.setup_type is SetupType.LIQUIDITY_SWEEP_REVERSAL_LONG


def test_liquidity_sweep_reversal_short() -> None:
    result = _analyze(
        DecisionAction.WAIT,
        _structure("ranging", "range", ["liquidity_sweep_high"]),
        direction="neutral",
        price=105.0,
    )

    assert result.setup_type is SetupType.LIQUIDITY_SWEEP_REVERSAL_SHORT


def test_decision_avoid_returns_no_valid_setup() -> None:
    result = _analyze(
        DecisionAction.AVOID,
        _structure("bullish", "pullback"),
        direction="bullish",
        price=95.0,
    )

    assert result.setup_type is SetupType.NO_VALID_SETUP
    assert result.setup_status is SetupStatus.NO_SETUP


def test_wait_decision_cannot_force_confirmed_setup() -> None:
    result = _analyze(
        DecisionAction.WAIT,
        _structure("bullish", "pullback"),
        direction="bullish",
        price=95.0,
        confirmed=False,
    )

    assert result.setup_status in {
        SetupStatus.DEVELOPING,
        SetupStatus.WAITING_FOR_CONFIRMATION,
    }
    assert result.setup_status is not SetupStatus.CONFIRMED


def test_setup_returns_checklist_invalidation_and_risk_reward() -> None:
    result = _analyze(
        DecisionAction.BUY,
        _structure("bullish", "pullback"),
        direction="bullish",
        price=95.0,
        risk_reward=1.8,
    )

    assert result.entry_conditions
    assert any(condition.importance == "required" for condition in result.entry_conditions)
    assert result.invalidation_rules
    assert result.invalidation_rules[0].trigger_level == "90.00"
    assert result.estimated_risk_reward == 1.8


def test_compression_without_breakout_is_developing() -> None:
    result = _analyze(
        DecisionAction.WAIT,
        _structure("unclear", "unclear"),
        direction="bullish",
        price=100.0,
        compression=True,
    )

    assert result.setup_type is SetupType.COMPRESSION_BREAKOUT_LONG
    assert result.setup_status in {
        SetupStatus.DEVELOPING,
        SetupStatus.WAITING_FOR_CONFIRMATION,
    }
