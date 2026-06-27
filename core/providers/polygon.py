"""Reserved Polygon.io adapter; implementation will be added in a future phase."""

from core.market_data import Candle, MarketDataError


class PolygonMarketDataProvider:
    def get_candles(self, symbol: str, timeframe: str, lookback: int) -> list[Candle]:
        del symbol, timeframe, lookback
        raise MarketDataError("The Polygon.io provider is not configured yet.")
