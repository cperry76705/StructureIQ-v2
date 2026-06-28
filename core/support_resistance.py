"""Build simple zones around the latest relevant swing prices."""

from core.market_data import Candle
from core.instruments import format_price, instrument_zone_width
from core.structure import SwingPoint


def detect_zones(
    candles: list[Candle],
    highs: list[SwingPoint],
    lows: list[SwingPoint],
    symbol: str = "",
) -> tuple[tuple[float, float], tuple[float, float]]:
    current = candles[-1].close
    support_price = next((s.price for s in reversed(lows) if s.price <= current), min(c.low for c in candles[-20:]))
    resistance_price = next((s.price for s in reversed(highs) if s.price >= current), max(c.high for c in candles[-20:]))
    width = instrument_zone_width(symbol, current, candles)
    return (support_price - width, support_price + width), (resistance_price - width, resistance_price + width)


def format_zone(zone: tuple[float, float], symbol: str = "") -> str:
    return f"{format_price(zone[0], symbol)}-{format_price(zone[1], symbol)}"
