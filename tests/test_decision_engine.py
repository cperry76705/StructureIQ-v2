from typing import cast

from core.decision_engine import DecisionAction, DecisionEngine
from core.market_structure import MarketStructureResult, Phase, Trend
from core.multi_timeframe import (
    DirectionalBias,
    MultiTimeframeResult,
    TimeframeAlignment,
)
from core.structure import SwingPoint


ENGINE = DecisionEngine()


def _structure(
    trend: Trend,
    phase: Phase,
    events: list[str] | None = None,
) -> MarketStructureResult:
    return MarketStructureResult(
        trend=trend,
        phase=phase,
        latest_swing_high=SwingPoint(5, 120.0, "high"),
        latest_swing_low=SwingPoint(4, 90.0, "low"),
        structure_events=events or [],
        liquidity_sweep_detected=any(
            event.startswith("liquidity_sweep_") for event in events or []
        ),
        confidence_modifier=0.0,
        human_readable_summary=f"Structure is {trend} in a {phase} phase.",
    )


def _multi_timeframe(
    direction: str,
    alignment: TimeframeAlignment,
    score: int,
    *,
    current_trend: Trend | None = None,
    current_phase: Phase = "impulse",
) -> MultiTimeframeResult:
    higher_trend = cast(
        Trend, direction if direction in {"bullish", "bearish"} else "unclear"
    )
    bias = cast(
        DirectionalBias,
        direction if direction in {"bullish", "bearish"} else "neutral",
    )
    return MultiTimeframeResult(
        higher_timeframe="1h",
        current_timeframe="5m",
        higher_timeframe_trend=higher_trend,
        current_timeframe_trend=current_trend or higher_trend,
        higher_timeframe_phase="impulse" if higher_trend != "unclear" else "unclear",
        current_timeframe_phase=current_phase,
        alignment=alignment,
        alignment_score=score,
        directional_bias=bias,
        reasons=("Higher context.", "Current context.", "Alignment context."),
        human_readable_summary="Synthetic multi-timeframe result.",
    )


def _decision(
    structure: MarketStructureResult,
    multi_timeframe: MultiTimeframeResult,
    *,
    confirmed: bool = True,
    risk_reward: float | None = 2.0,
):
    return ENGINE.analyze(
        market_structure=structure,
        multi_timeframe=multi_timeframe,
        price_near_level=True,
        indicator_supportive=True,
        current_timeframe_confirmed=confirmed,
        risk_reward_ratio=risk_reward,
    )


def test_bullish_aligned_structure_returns_buy_at_high_confidence() -> None:
    result = _decision(
        _structure("bullish", "impulse", ["bullish_bos"]),
        _multi_timeframe("bullish", TimeframeAlignment.ALIGNED_BULLISH, 95),
    )

    assert result.action is DecisionAction.BUY
    assert result.confidence >= 85


def test_bearish_aligned_structure_returns_sell_at_high_confidence() -> None:
    result = _decision(
        _structure("bearish", "impulse", ["bearish_bos"]),
        _multi_timeframe("bearish", TimeframeAlignment.ALIGNED_BEARISH, 95),
    )

    assert result.action is DecisionAction.SELL
    assert result.confidence >= 85


def test_mixed_bullish_pullback_returns_wait_without_confirmation() -> None:
    result = _decision(
        _structure("bullish", "pullback"),
        _multi_timeframe(
            "bullish",
            TimeframeAlignment.MIXED,
            70,
            current_phase="pullback",
        ),
        confirmed=False,
    )

    assert result.action is DecisionAction.WAIT
    assert result.confidence >= 70
    assert result.decision_diagnostics.blocked_by
    assert "multi_timeframe_alignment" in result.decision_diagnostics.blocked_by


def test_conflicting_alignment_returns_wait_or_avoid() -> None:
    result = _decision(
        _structure("bearish", "impulse"),
        _multi_timeframe(
            "bullish",
            TimeframeAlignment.CONFLICTING,
            20,
            current_trend="bearish",
        ),
    )

    assert result.action in {DecisionAction.WAIT, DecisionAction.AVOID}
    assert any("conflict" in item.message for item in result.negative_evidence)
    timeframe_gate = next(
        gate for gate in result.decision_diagnostics.gate_results
        if gate.gate_name == "multi_timeframe_alignment"
    )
    assert timeframe_gate.passed is False
    assert timeframe_gate.actual_value == "conflicting"


def test_confidence_below_fifty_returns_avoid() -> None:
    result = ENGINE.analyze(
        market_structure=_structure("unclear", "unclear"),
        multi_timeframe=_multi_timeframe(
            "neutral",
            TimeframeAlignment.UNCLEAR,
            15,
            current_trend="unclear",
            current_phase="unclear",
        ),
        price_near_level=False,
        indicator_supportive=False,
        current_timeframe_confirmed=False,
        risk_reward_ratio=None,
    )

    assert result.confidence < 50
    assert result.action is DecisionAction.AVOID
    diagnostics = result.decision_diagnostics
    assert diagnostics.confidence_band == "avoid"
    assert "confidence_threshold" in diagnostics.blocked_by
    confidence_gate = next(
        gate for gate in diagnostics.gate_results
        if gate.gate_name == "confidence_threshold"
    )
    assert confidence_gate.passed is False
    assert confidence_gate.expected_value == ">= 70.0"


def test_wait_and_avoid_decisions_include_readable_diagnostics() -> None:
    wait_result = _decision(
        _structure("bullish", "pullback"),
        _multi_timeframe("bullish", TimeframeAlignment.MIXED, 70),
        confirmed=False,
    )
    avoid_result = ENGINE.analyze(
        market_structure=_structure("unclear", "unclear"),
        multi_timeframe=_multi_timeframe(
            "neutral",
            TimeframeAlignment.UNCLEAR,
            15,
            current_trend="unclear",
            current_phase="unclear",
        ),
        price_near_level=False,
        indicator_supportive=False,
        current_timeframe_confirmed=False,
        risk_reward_ratio=None,
    )

    assert "wait decision is blocked" in wait_result.decision_diagnostics.human_readable_summary
    assert "avoid decision is blocked" in avoid_result.decision_diagnostics.human_readable_summary


def test_diagnostics_do_not_change_directional_decision() -> None:
    result = _decision(
        _structure("bullish", "impulse", ["bullish_bos"]),
        _multi_timeframe("bullish", TimeframeAlignment.ALIGNED_BULLISH, 95),
    )

    assert result.action is DecisionAction.BUY
    assert result.decision_diagnostics.blocked_by == ()
    assert result.decision_diagnostics.final_confidence == result.confidence
    assert result.decision_diagnostics.confidence_band == "high_conviction"


def test_score_breakdown_total_is_sum_of_weighted_categories() -> None:
    result = _decision(
        _structure("bullish", "impulse", ["bullish_bos"]),
        _multi_timeframe("bullish", TimeframeAlignment.ALIGNED_BULLISH, 95),
    )
    breakdown = result.score_breakdown

    expected = (
        breakdown.market_structure
        + breakdown.multi_timeframe
        + breakdown.support_resistance_liquidity
        + breakdown.indicators
        + breakdown.risk_reward_volatility
    )
    assert breakdown.total == round(expected, 1)
    assert breakdown.total <= 100


def test_positive_and_negative_evidence_are_included() -> None:
    result = _decision(
        _structure(
            "bullish",
            "impulse",
            ["bullish_bos", "liquidity_sweep_high"],
        ),
        _multi_timeframe("bullish", TimeframeAlignment.ALIGNED_BULLISH, 95),
    )

    assert result.positive_evidence
    assert result.negative_evidence
    assert any("liquidity sweep" in item.message.lower() for item in result.negative_evidence)


def test_invalidation_notes_use_latest_structural_level() -> None:
    result = _decision(
        _structure("bullish", "impulse", ["bullish_bos"]),
        _multi_timeframe("bullish", TimeframeAlignment.ALIGNED_BULLISH, 95),
    )

    assert result.invalidation_notes
    assert "90.00" in result.invalidation_notes[0]


def test_risk_notes_are_returned_when_volatility_is_unavailable() -> None:
    result = _decision(
        _structure("bullish", "impulse", ["bullish_bos"]),
        _multi_timeframe("bullish", TimeframeAlignment.ALIGNED_BULLISH, 95),
    )

    assert result.risk_notes
    assert any("volatility" in note for note in result.risk_notes)
