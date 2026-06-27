from core.structure import SwingPoint, determine_bias


def test_rising_highs_and_lows_are_bullish() -> None:
    highs = [SwingPoint(1, 100), SwingPoint(3, 110)]
    lows = [SwingPoint(2, 90), SwingPoint(4, 95)]
    assert determine_bias(highs, lows) == "bullish"


def test_falling_highs_and_lows_are_bearish() -> None:
    highs = [SwingPoint(1, 110), SwingPoint(3, 100)]
    lows = [SwingPoint(2, 95), SwingPoint(4, 90)]
    assert determine_bias(highs, lows) == "bearish"


def test_mixed_structure_is_ranging() -> None:
    highs = [SwingPoint(1, 100), SwingPoint(3, 110)]
    lows = [SwingPoint(2, 95), SwingPoint(4, 90)]
    assert determine_bias(highs, lows) == "ranging"
