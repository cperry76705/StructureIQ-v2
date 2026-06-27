from core.market_structure import MarketStructureResult, Phase, Trend
from core.multi_timeframe import MultiTimeframeEngine, TimeframeAlignment


ENGINE = MultiTimeframeEngine()


def _structure(trend: Trend, phase: Phase) -> MarketStructureResult:
    return MarketStructureResult(
        trend=trend,
        phase=phase,
        latest_swing_high=None,
        latest_swing_low=None,
        structure_events=[],
        liquidity_sweep_detected=False,
        confidence_modifier=0.0,
        human_readable_summary=f"Structure is {trend} in a {phase} phase.",
    )


def _analyze(
    higher_trend: Trend,
    higher_phase: Phase,
    current_trend: Trend,
    current_phase: Phase,
):
    return ENGINE.analyze(
        "1h",
        "5m",
        _structure(higher_trend, higher_phase),
        _structure(current_trend, current_phase),
    )


def test_aligned_bullish_timeframes() -> None:
    result = _analyze("bullish", "impulse", "bullish", "impulse")

    assert result.alignment is TimeframeAlignment.ALIGNED_BULLISH
    assert result.alignment_score == 95
    assert result.directional_bias == "bullish"


def test_aligned_bearish_timeframes() -> None:
    result = _analyze("bearish", "impulse", "bearish", "impulse")

    assert result.alignment is TimeframeAlignment.ALIGNED_BEARISH
    assert result.alignment_score == 95
    assert result.directional_bias == "bearish"


def test_mixed_bullish_pullback_keeps_bullish_context() -> None:
    result = _analyze("bullish", "impulse", "bullish", "pullback")

    assert result.alignment is TimeframeAlignment.MIXED
    assert result.alignment_score == 70
    assert result.directional_bias == "bullish"
    assert "pulling back" in result.reasons[-1]


def test_mixed_bearish_pullback_keeps_bearish_context() -> None:
    result = _analyze("bearish", "impulse", "bearish", "pullback")

    assert result.alignment is TimeframeAlignment.MIXED
    assert result.alignment_score == 70
    assert result.directional_bias == "bearish"


def test_bullish_higher_and_bearish_current_are_conflicting() -> None:
    result = _analyze("bullish", "impulse", "bearish", "impulse")

    assert result.alignment is TimeframeAlignment.CONFLICTING
    assert result.alignment_score == 20
    assert result.directional_bias == "neutral"


def test_bearish_higher_and_bullish_current_are_conflicting() -> None:
    result = _analyze("bearish", "impulse", "bullish", "impulse")

    assert result.alignment is TimeframeAlignment.CONFLICTING
    assert result.alignment_score == 20
    assert result.directional_bias == "neutral"


def test_unclear_higher_timeframe_lowers_score_and_bias() -> None:
    result = _analyze("unclear", "unclear", "bullish", "impulse")

    assert result.alignment is TimeframeAlignment.UNCLEAR
    assert result.alignment_score == 15
    assert result.directional_bias == "unclear"


def test_ranging_current_timeframe_is_mixed_directional_context() -> None:
    result = _analyze("bullish", "impulse", "ranging", "range")

    assert result.alignment is TimeframeAlignment.MIXED
    assert result.alignment_score == 60
    assert result.directional_bias == "bullish"
    assert "mixed" in result.human_readable_summary
