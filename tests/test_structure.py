import pytest

from core.market_data import Candle
from core.structure import SwingPoint, determine_bias, find_swings


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


def test_find_swings_rejects_invalid_confirmation_window() -> None:
    candles = [Candle(0, 10, 11, 9, 10, 100)]

    with pytest.raises(ValueError, match="window must be at least 1"):
        find_swings(candles, window=0)
