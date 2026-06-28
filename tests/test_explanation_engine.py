import pytest

from core.decision_engine import (
    DecisionAction,
    DecisionResult,
    EvidenceItem,
    ScoreBreakdown,
)
from core.explanation_engine import ExplanationEngine, interpret_confidence
from core.market_structure import MarketStructureResult, Phase, Trend
from core.multi_timeframe import MultiTimeframeResult, TimeframeAlignment
from core.setup_engine import (
    EntryCondition,
    InvalidationRule,
    SetupResult,
    SetupStatus,
    SetupType,
)


ENGINE = ExplanationEngine()


def _decision(action: DecisionAction, confidence: float = 80.0) -> DecisionResult:
    negative = (
        EvidenceItem(
            "multi_timeframe",
            "Execution timeframe has not confirmed continuation.",
            -8.0,
        ),
    ) if action in {DecisionAction.WAIT, DecisionAction.AVOID} else ()
    return DecisionResult(
        action=action,
        confidence=confidence,
        score_breakdown=ScoreBreakdown(0, 0, 0, 0, 0, confidence),
        positive_evidence=(),
        negative_evidence=negative,
        neutral_evidence=(),
        risk_notes=("Risk should be defined only after setup confirmation.",),
        invalidation_notes=(),
        human_readable_summary="Synthetic decision.",
    )


def _structure(trend: Trend, phase: Phase) -> MarketStructureResult:
    return MarketStructureResult(
        trend=trend,
        phase=phase,
        latest_swing_high=None,
        latest_swing_low=None,
        structure_events=[],
        liquidity_sweep_detected=False,
        confidence_modifier=0.0,
        human_readable_summary="Synthetic structure.",
    )


def _multi(direction: str) -> MultiTimeframeResult:
    bullish = direction == "bullish"
    trend: Trend = "bullish" if bullish else "bearish"
    return MultiTimeframeResult(
        higher_timeframe="1h",
        current_timeframe="5m",
        higher_timeframe_trend=trend,
        current_timeframe_trend=trend,
        higher_timeframe_phase="impulse",
        current_timeframe_phase="pullback",
        alignment=(
            TimeframeAlignment.ALIGNED_BULLISH
            if bullish
            else TimeframeAlignment.ALIGNED_BEARISH
        ),
        alignment_score=95,
        directional_bias=trend,
        reasons=("Higher.", "Current.", "Context."),
        human_readable_summary="Synthetic alignment.",
    )


def _setup(
    direction: str,
    status: SetupStatus,
    *,
    unmet_condition: bool = False,
    missing_optional_fields: bool = False,
) -> SetupResult:
    bullish = direction == "bullish"
    setup_type = (
        SetupType.BULLISH_PULLBACK_CONTINUATION
        if bullish
        else SetupType.BEARISH_PULLBACK_CONTINUATION
    )
    conditions = (
        EntryCondition(
            f"{direction.title()} confirmation candle forms near the setup level.",
            not unmet_condition,
            "required",
        ),
    )
    invalidations = () if missing_optional_fields else (
        InvalidationRule(
            f"{direction.title()} thesis invalidates beyond the latest swing.",
            "90.00" if bullish else "110.00",
            "hard",
        ),
    )
    return SetupResult(
        setup_type=setup_type,
        setup_status=status,
        direction="bullish" if bullish else "bearish",
        setup_quality_score=85.0,
        entry_zone=None if missing_optional_fields else "94-96",
        stop_loss=None if missing_optional_fields else "90",
        target=None if missing_optional_fields else "105",
        estimated_risk_reward=None if missing_optional_fields else 1.8,
        entry_conditions=conditions,
        invalidation_rules=invalidations,
        supporting_evidence=(),
        warning_notes=(),
        human_readable_summary=(
            f"A {setup_type.value.replace('_', ' ')} setup is {status.value}."
        ),
    )


def _analyze(
    action: DecisionAction,
    setup: SetupResult,
    *,
    confidence: float = 80.0,
):
    direction = setup.direction if setup.direction != "neutral" else "bullish"
    return ENGINE.analyze(
        symbol="EUR/USD",
        market_structure=_structure(direction, "pullback"),
        multi_timeframe=_multi(direction),
        decision=_decision(action, confidence),
        setup_plan=setup,
    )


def test_buy_with_confirmed_setup_is_actionable() -> None:
    result = _analyze(
        DecisionAction.BUY,
        _setup("bullish", SetupStatus.CONFIRMED),
    )

    assert result.trade_plan.status == "actionable"
    assert "actionable" in result.recommendation.lower()
    assert "EUR/USD" in result.headline


def test_sell_with_confirmed_setup_is_actionable() -> None:
    result = _analyze(
        DecisionAction.SELL,
        _setup("bearish", SetupStatus.CONFIRMED),
    )

    assert result.trade_plan.status == "actionable"
    assert result.trade_plan.direction == "bearish"


def test_wait_decision_creates_waiting_or_developing_plan() -> None:
    result = _analyze(
        DecisionAction.WAIT,
        _setup("bullish", SetupStatus.WAITING_FOR_CONFIRMATION, unmet_condition=True),
        confidence=65.0,
    )

    assert result.trade_plan.status in {"waiting", "developing"}
    assert result.recommendation.startswith("Wait")


def test_avoid_decision_creates_avoid_explanation() -> None:
    result = _analyze(
        DecisionAction.AVOID,
        _setup("bullish", SetupStatus.NO_SETUP, missing_optional_fields=True),
        confidence=35.0,
    )

    assert result.trade_plan.status in {"avoid", "no_trade"}
    assert "Avoid" in result.recommendation
    assert result.key_risks


def test_unmet_required_conditions_become_wait_for_items() -> None:
    result = _analyze(
        DecisionAction.WAIT,
        _setup("bullish", SetupStatus.WAITING_FOR_CONFIRMATION, unmet_condition=True),
    )

    assert len(result.trade_plan.wait_for) == 1
    assert result.trade_plan.wait_for[0].importance == "required"
    assert result.trade_plan.wait_for[0].source == "setup_engine"


def test_invalidation_rules_become_plain_english_notes() -> None:
    result = _analyze(
        DecisionAction.BUY,
        _setup("bullish", SetupStatus.CONFIRMED),
    )

    assert result.trade_plan.invalidation
    assert "trigger level is 90.00" in result.trade_plan.invalidation[0]


@pytest.mark.parametrize(
    ("confidence", "expected"),
    [
        (49.0, "Weak or no edge"),
        (60.0, "Moderate but incomplete"),
        (75.0, "Strong evidence"),
        (90.0, "High-conviction"),
    ],
)
def test_confidence_interpretation_ranges(
    confidence: float, expected: str
) -> None:
    assert expected in interpret_confidence(confidence)


def test_fallback_explanation_handles_missing_optional_fields() -> None:
    result = _analyze(
        DecisionAction.WAIT,
        _setup(
            "bullish",
            SetupStatus.WAITING_FOR_CONFIRMATION,
            unmet_condition=True,
            missing_optional_fields=True,
        ),
    )

    assert result.trade_plan.entry_zone is None
    assert result.trade_plan.stop_loss is None
    assert result.trade_plan.estimated_risk_reward is None
    assert result.headline
    assert result.summary
    assert result.next_best_action
