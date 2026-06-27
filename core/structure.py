"""Swing discovery primitives shared by StructureIQ structure analyzers."""

from dataclasses import dataclass
from typing import Literal

from core.market_data import Candle


SwingKind = Literal["high", "low"]
SwingLabel = Literal["higher_high", "higher_low", "lower_high", "lower_low"]


@dataclass(frozen=True)
class SwingPoint:
    """A confirmed fractal swing and its relationship to the prior same-kind swing.

    ``kind``, ``label``, and ``confirmed_index`` are optional to preserve the small
    two-argument construction used by older callers. Points returned by
    :func:`find_swings` always populate ``kind`` and ``confirmed_index``.
    """

    index: int
    price: float
    kind: SwingKind | None = None
    label: SwingLabel | None = None
    confirmed_index: int | None = None


def find_swings(candles: list[Candle], window: int = 2) -> tuple[list[SwingPoint], list[SwingPoint]]:
    """Return strictly confirmed fractal highs and lows in chronological order."""

    if window < 1:
        raise ValueError("window must be at least 1")

    highs: list[SwingPoint] = []
    lows: list[SwingPoint] = []
    for index in range(window, len(candles) - window):
        neighbors = candles[index - window : index] + candles[index + 1 : index + window + 1]
        if candles[index].high > max(candle.high for candle in neighbors):
            previous = highs[-1] if highs else None
            label: SwingLabel | None = None
            if previous is not None and candles[index].high != previous.price:
                label = (
                    "higher_high"
                    if candles[index].high > previous.price
                    else "lower_high"
                )
            highs.append(
                SwingPoint(
                    index=index,
                    price=candles[index].high,
                    kind="high",
                    label=label,
                    confirmed_index=index + window,
                )
            )
        if candles[index].low < min(candle.low for candle in neighbors):
            previous = lows[-1] if lows else None
            label = None
            if previous is not None and candles[index].low != previous.price:
                label = (
                    "higher_low"
                    if candles[index].low > previous.price
                    else "lower_low"
                )
            lows.append(
                SwingPoint(
                    index=index,
                    price=candles[index].low,
                    kind="low",
                    label=label,
                    confirmed_index=index + window,
                )
            )
    return highs, lows


def determine_bias(highs: list[SwingPoint], lows: list[SwingPoint]) -> str:
    if len(highs) < 2 or len(lows) < 2:
        return "ranging"
    rising = highs[-1].price > highs[-2].price and lows[-1].price > lows[-2].price
    falling = highs[-1].price < highs[-2].price and lows[-1].price < lows[-2].price
    return "bullish" if rising else "bearish" if falling else "ranging"


def classify_current_structure(candles: list[Candle], bias: str) -> str:
    if len(candles) < 4:
        return "unclear"
    recent_move = candles[-1].close - candles[-4].close
    if bias == "bullish":
        return "continuation" if recent_move > 0 else "pullback"
    if bias == "bearish":
        return "continuation" if recent_move < 0 else "pullback"
    return "range"
