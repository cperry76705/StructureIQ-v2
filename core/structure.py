"""Swing discovery and rule-based market structure classification."""

from dataclasses import dataclass

from core.market_data import Candle


@dataclass(frozen=True)
class SwingPoint:
    index: int
    price: float


def find_swings(candles: list[Candle], window: int = 2) -> tuple[list[SwingPoint], list[SwingPoint]]:
    highs: list[SwingPoint] = []
    lows: list[SwingPoint] = []
    for index in range(window, len(candles) - window):
        neighbors = candles[index - window : index] + candles[index + 1 : index + window + 1]
        if candles[index].high > max(candle.high for candle in neighbors):
            highs.append(SwingPoint(index, candles[index].high))
        if candles[index].low < min(candle.low for candle in neighbors):
            lows.append(SwingPoint(index, candles[index].low))
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
