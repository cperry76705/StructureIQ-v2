"""Small, dependency-free technical indicators used by strategies."""

from core.market_data import Candle


def calculate_rsi(candles: list[Candle], period: int = 14) -> float:
    if len(candles) <= period:
        return 50.0

    changes = [candles[i].close - candles[i - 1].close for i in range(1, len(candles))]
    recent = changes[-period:]
    gains = sum(max(change, 0) for change in recent) / period
    losses = sum(max(-change, 0) for change in recent) / period
    if losses == 0:
        return 100.0
    return round(100 - (100 / (1 + gains / losses)), 2)
