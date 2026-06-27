import httpx
import pytest

from core.market_data import MarketDataError
from core.providers.yahoo import YahooFinanceMarketDataProvider


def _payload(count: int = 25) -> dict:
    values = [float(index + 100) for index in range(count)]
    return {
        "chart": {
            "result": [
                {
                    "timestamp": list(range(count)),
                    "indicators": {
                        "quote": [
                            {
                                "open": values,
                                "high": [value + 2 for value in values],
                                "low": [value - 2 for value in values],
                                "close": [value + 1 for value in values],
                                "volume": [10.0] * count,
                            }
                        ]
                    },
                }
            ],
            "error": None,
        }
    }


def test_yahoo_returns_standardized_candles() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=_payload()))
    with httpx.Client(transport=transport) as client:
        candles = YahooFinanceMarketDataProvider(client=client).get_candles("BTC-USD", "5m", 20)
    assert len(candles) == 20
    assert candles[-1].timestamp == 24
    assert candles[-1].close == 125.0


def test_yahoo_failure_becomes_market_data_error() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(503))
    with httpx.Client(transport=transport) as client:
        provider = YahooFinanceMarketDataProvider(client=client)
        with pytest.raises(MarketDataError, match="Yahoo Finance returned HTTP 503"):
            provider.get_candles("BTC-USD", "5m", 20)
