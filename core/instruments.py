"""Instrument metadata and scale-aware price formatting helpers."""

from dataclasses import dataclass
from typing import Literal

from core.market_data import Candle


AssetClass = Literal["forex", "crypto", "equity", "unknown"]
_CRYPTO_BASES = {"BTC", "ETH", "SOL", "XRP", "ADA", "DOGE", "LTC", "BCH"}
_FOREX_CURRENCIES = {"USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD"}


@dataclass(frozen=True)
class InstrumentMetadata:
    asset_class: AssetClass
    decimal_precision: int
    tick_size: float
    pip_size: float | None
    minimum_zone_width: float


def infer_asset_class(symbol: str) -> AssetClass:
    normalized = symbol.strip().upper()
    base, quote = _symbol_parts(normalized)
    if base in _CRYPTO_BASES and quote == "USD":
        return "crypto"
    if base in _FOREX_CURRENCIES and quote in _FOREX_CURRENCIES and base != quote:
        return "forex"
    if normalized:
        return "equity"
    return "unknown"


def instrument_metadata(symbol: str) -> InstrumentMetadata:
    normalized = symbol.strip().upper()
    asset_class = infer_asset_class(normalized)
    base, quote = _symbol_parts(normalized)
    if asset_class == "forex":
        jpy_pair = quote == "JPY"
        precision = 3 if jpy_pair else 5
        tick = 0.001 if jpy_pair else 0.00001
        pip = 0.01 if jpy_pair else 0.0001
        return InstrumentMetadata(asset_class, precision, tick, pip, pip)
    if asset_class == "crypto":
        return InstrumentMetadata(asset_class, 2, 0.01, None, 0.05)
    return InstrumentMetadata(asset_class, 2, 0.01, None, 0.01)


def decimal_precision(symbol: str) -> int:
    return instrument_metadata(symbol).decimal_precision


def tick_size(symbol: str) -> float:
    return instrument_metadata(symbol).tick_size


def pip_size(symbol: str) -> float | None:
    return instrument_metadata(symbol).pip_size


def minimum_zone_width(symbol: str) -> float:
    return instrument_metadata(symbol).minimum_zone_width


def average_true_range(candles: list[Candle], period: int = 14) -> float | None:
    if len(candles) < 2:
        return None
    sample = candles[-(period + 1) :]
    ranges: list[float] = []
    for previous, current in zip(sample, sample[1:]):
        ranges.append(
            max(
                current.high - current.low,
                abs(current.high - previous.close),
                abs(current.low - previous.close),
            )
        )
    return sum(ranges) / len(ranges) if ranges else None


def instrument_zone_width(
    symbol: str,
    current_price: float,
    candles: list[Candle] | None = None,
) -> float:
    """Return a half-zone width bounded by price scale, ATR, and instrument tick."""

    floor = minimum_zone_width(symbol)
    percentage_width = abs(current_price) * 0.0005
    atr = average_true_range(candles or [])
    adaptive_width = min(percentage_width, atr * 0.25) if atr and atr > 0 else percentage_width
    return max(floor, adaptive_width)


def format_price(value: float, symbol: str) -> str:
    return f"{value:.{decimal_precision(symbol)}f}"


def _symbol_parts(symbol: str) -> tuple[str, str]:
    cleaned = symbol.removesuffix("=X")
    if "-" in cleaned:
        parts = cleaned.split("-", 1)
        return parts[0], parts[1]
    if len(cleaned) == 6:
        return cleaned[:3], cleaned[3:]
    return cleaned, ""
