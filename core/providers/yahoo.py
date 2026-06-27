"""Yahoo Finance chart API adapter (the default Phase 2 provider)."""

from collections.abc import Sequence
from typing import Any

import httpx

from core.market_data import Candle, MarketDataError


_INTERVALS = {
    "1m": ("1m", 1, 1),
    "5m": ("5m", 1, 5),
    "15m": ("15m", 1, 15),
    "30m": ("30m", 1, 30),
    "1h": ("1h", 1, 60),
    # Yahoo has no native 4h interval, so hourly candles are aggregated below.
    "4h": ("1h", 4, 60),
    "1d": ("1d", 1, 1_440),
}

_RANGES = (
    (1, "1d"),
    (5, "5d"),
    (30, "1mo"),
    (90, "3mo"),
    (180, "6mo"),
    (365, "1y"),
    (730, "2y"),
    (1_825, "5y"),
    (3_650, "10y"),
)


class YahooFinanceMarketDataProvider:
    base_url = "https://query1.finance.yahoo.com/v8/finance/chart"

    def __init__(self, client: httpx.Client | None = None, timeout: float = 10.0) -> None:
        self._client = client
        self._timeout = timeout

    def get_candles(self, symbol: str, timeframe: str, lookback: int) -> list[Candle]:
        if timeframe not in _INTERVALS:
            raise MarketDataError(f"Yahoo Finance does not support timeframe '{timeframe}'.")

        interval, aggregation, source_minutes = _INTERVALS[timeframe]
        range_value = self._select_range(lookback * aggregation, source_minutes)
        try:
            payload = self._fetch(symbol, interval, range_value)
            candles = self._parse(payload)
        except MarketDataError:
            raise
        except httpx.HTTPStatusError as exc:
            raise MarketDataError(
                f"Yahoo Finance returned HTTP {exc.response.status_code} for {symbol} "
                f"({timeframe}); try again later."
            ) from exc
        except (httpx.HTTPError, KeyError, TypeError, ValueError, IndexError) as exc:
            raise MarketDataError(
                f"Yahoo Finance could not provide data for {symbol} ({timeframe})."
            ) from exc

        if aggregation > 1:
            candles = self._aggregate(candles, aggregation)
        candles = candles[-lookback:]
        if len(candles) < min(lookback, 20):
            raise MarketDataError(
                f"Yahoo Finance returned only {len(candles)} usable candles for {symbol}; "
                f"at least {min(lookback, 20)} are required."
            )
        return candles

    @staticmethod
    def _select_range(source_candles: int, minutes_per_candle: int) -> str:
        # The buffer accommodates weekends, market closures, and an incomplete candle.
        required_days = source_candles * minutes_per_candle / 1_440 * 1.5
        for maximum_days, range_value in _RANGES:
            if required_days <= maximum_days:
                return range_value
        return "max"

    def _fetch(self, symbol: str, interval: str, range_value: str) -> dict[str, Any]:
        url = f"{self.base_url}/{symbol}"
        params = {"interval": interval, "range": range_value, "events": "history"}
        if self._client is not None:
            response = self._client.get(url, params=params, timeout=self._timeout)
        else:
            headers = {
                "Accept": "application/json",
                "User-Agent": "StructureIQ/2.0 market-analysis client",
            }
            with httpx.Client(follow_redirects=True, headers=headers) as client:
                response = client.get(url, params=params, timeout=self._timeout)
        response.raise_for_status()
        payload = response.json()
        chart = payload.get("chart", {})
        if chart.get("error"):
            description = chart["error"].get("description", "unknown provider error")
            raise MarketDataError(f"Yahoo Finance rejected {symbol}: {description}.")
        return payload

    @staticmethod
    def _parse(payload: dict[str, Any]) -> list[Candle]:
        result = payload["chart"]["result"][0]
        timestamps: Sequence[int | None] = result["timestamp"]
        quote = result["indicators"]["quote"][0]
        candles: list[Candle] = []
        for timestamp, open_, high, low, close, volume in zip(
            timestamps,
            quote["open"],
            quote["high"],
            quote["low"],
            quote["close"],
            quote["volume"],
        ):
            if None in (timestamp, open_, high, low, close):
                continue
            candles.append(
                Candle(
                    timestamp=int(timestamp),
                    open=float(open_),
                    high=float(high),
                    low=float(low),
                    close=float(close),
                    volume=float(volume or 0),
                )
            )
        if not candles:
            raise MarketDataError("Yahoo Finance returned no usable candles.")
        return candles

    @staticmethod
    def _aggregate(candles: list[Candle], size: int) -> list[Candle]:
        aggregated: list[Candle] = []
        # Discard an incomplete leading group so every output candle has equal duration.
        start = len(candles) % size
        for index in range(start, len(candles), size):
            group = candles[index : index + size]
            if len(group) != size:
                continue
            aggregated.append(
                Candle(
                    timestamp=group[0].timestamp,
                    open=group[0].open,
                    high=max(candle.high for candle in group),
                    low=min(candle.low for candle in group),
                    close=group[-1].close,
                    volume=sum(candle.volume for candle in group),
                )
            )
        return aggregated
