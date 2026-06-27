"""Reserved OANDA adapter; implementation will be added in a future phase."""

from core.market_data import Candle, MarketDataError


class OandaMarketDataProvider:
    def get_candles(self, symbol: str, timeframe: str, lookback: int) -> list[Candle]:
        del symbol, timeframe, lookback
        raise MarketDataError("The OANDA provider is not configured yet.")
