"""Build simple zones around the latest relevant swing prices."""

from core.market_data import Candle
from core.structure import SwingPoint


def detect_zones(
    candles: list[Candle], highs: list[SwingPoint], lows: list[SwingPoint]
) -> tuple[tuple[float, float], tuple[float, float]]:
    current = candles[-1].close
    support_price = next((s.price for s in reversed(lows) if s.price <= current), min(c.low for c in candles[-20:]))
    resistance_price = next((s.price for s in reversed(highs) if s.price >= current), max(c.high for c in candles[-20:]))
    width = max(current * 0.002, 25.0)
    return (support_price - width, support_price + width), (resistance_price - width, resistance_price + width)


def format_zone(zone: tuple[float, float]) -> str:
    return f"{zone[0]:.0f}-{zone[1]:.0f}"
