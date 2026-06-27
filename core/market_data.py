"""Provider-agnostic market data types and contracts."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Candle:
    """Standard OHLCV shape consumed by every analysis module."""

    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float


class MarketDataError(RuntimeError):
    """A provider could not return usable market data."""


class MarketDataProvider(Protocol):
    """Contract implemented by interchangeable market data sources."""

    def get_candles(self, symbol: str, timeframe: str, lookback: int) -> list[Candle]:
        """Return chronological candles in StructureIQ's standard format."""
        ...
