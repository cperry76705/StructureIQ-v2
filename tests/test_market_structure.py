from core.market_data import Candle
from core.market_structure import MarketStructureEngine, StructureEvent


def _candles(closes: list[float]) -> list[Candle]:
    return [
        Candle(index, close, close + 1, close - 1, close, 100)
        for index, close in enumerate(closes)
    ]


def _with_last_wick(
    closes: list[float], *, high: float | None = None, low: float | None = None
) -> list[Candle]:
    candles = _candles(closes)
    last = candles[-1]
    candles[-1] = Candle(
        last.timestamp,
        last.open,
        high if high is not None else last.high,
        low if low is not None else last.low,
        last.close,
        last.volume,
    )
    return candles


ENGINE = MarketStructureEngine(swing_window=1)


def test_bullish_trend() -> None:
    result = ENGINE.analyze(_candles([9, 12, 10, 14, 11, 16, 14]))
    assert result.trend == "bullish"
    assert "higher_high" in result.structure_events
    assert "higher_low" in result.structure_events
    assert result.latest_swing_high is not None
    assert result.latest_swing_high.price == 17
    assert result.latest_swing_low is not None
    assert result.latest_swing_low.price == 10
    assert result.confidence_modifier > 0
    assert "bullish" in result.human_readable_summary


def test_bearish_trend() -> None:
    result = ENGINE.analyze(_candles([16, 13, 15, 11, 14, 9, 11]))
    assert result.trend == "bearish"
    assert "lower_high" in result.structure_events
    assert "lower_low" in result.structure_events


def test_ranging_market() -> None:
    result = ENGINE.analyze(_candles([10, 12, 10, 12, 10, 12, 10]))
    assert result.trend == "ranging"
    assert result.phase == "range"


def test_bullish_break_of_structure() -> None:
    result = ENGINE.analyze(_candles([10, 12, 10, 11, 14]))
    assert "bullish_bos" in result.structure_events


def test_bearish_break_of_structure() -> None:
    result = ENGINE.analyze(_candles([14, 12, 14, 13, 10]))
    assert "bearish_bos" in result.structure_events


def test_bullish_change_of_character() -> None:
    result = ENGINE.analyze(_candles([18, 14, 17, 12, 16, 10, 15, 18]))
    assert "bullish_choch" in result.structure_events
    assert result.phase == "reversal_attempt"


def test_bearish_change_of_character() -> None:
    result = ENGINE.analyze(_candles([10, 14, 11, 16, 12, 18, 13, 10]))
    assert "bearish_choch" in result.structure_events
    assert result.phase == "reversal_attempt"


def test_liquidity_sweep_high() -> None:
    result = ENGINE.analyze(_with_last_wick([10, 12, 10, 12], high=14))
    assert "liquidity_sweep_high" in result.structure_events
    assert result.liquidity_sweep_detected is True


def test_liquidity_sweep_low() -> None:
    result = ENGINE.analyze(_with_last_wick([12, 10, 12, 10], low=8))
    assert "liquidity_sweep_low" in result.structure_events
    assert result.liquidity_sweep_detected is True


def test_bullish_pullback_phase() -> None:
    result = ENGINE.analyze(_candles([9, 12, 10, 14, 11, 16, 15, 14]))
    assert result.trend == "bullish"
    assert result.phase == "pullback"
    assert "pullback" in result.structure_events


def test_result_exposes_confirmed_swing_metadata() -> None:
    result = ENGINE.analyze(_candles([9, 12, 10, 14, 11, 16, 14]))

    assert [point.label for point in result.swing_highs] == [None, "higher_high", "higher_high"]
    assert [point.label for point in result.swing_lows] == [None, "higher_low"]
    assert all(point.kind == "high" for point in result.swing_highs)
    assert all(point.kind == "low" for point in result.swing_lows)
    assert all(point.confirmed_index == point.index + 1 for point in result.swing_highs)


def test_break_event_retains_reference_level_and_explanation() -> None:
    result = ENGINE.analyze(_candles([10, 12, 10, 11, 14]))
    event = next(event for event in result.events if event.type == "bullish_bos")

    assert isinstance(event, StructureEvent)
    assert event.reference_swing is not None
    assert event.reference_swing.price == 13
    assert event.price == 14
    assert "closed above" in event.description


def test_wick_through_level_is_sweep_not_break() -> None:
    result = ENGINE.analyze(_with_last_wick([10, 12, 10, 12], high=14))

    assert "liquidity_sweep_high" in result.structure_events
    assert "bullish_bos" not in result.structure_events


def test_insufficient_candles_return_explicit_unclear_result() -> None:
    result = MarketStructureEngine(swing_window=2).analyze(_candles([10, 11, 12, 13]))

    assert result.trend == "unclear"
    assert result.phase == "unclear"
    assert result.events == ()
    assert "not enough confirmed candles" in result.human_readable_summary


def test_summary_explains_directional_swing_sequence() -> None:
    result = ENGINE.analyze(_candles([9, 12, 10, 14, 11, 16, 14]))

    assert "higher high" in result.human_readable_summary
    assert "higher low" in result.human_readable_summary
