import httpx
import pytest

from core.providers.yahoo import YahooFinanceMarketDataProvider
from core.symbols import normalize_yahoo_symbol


def _payload() -> dict:
    values = [float(index + 100) for index in range(25)]
    return {
        "chart": {
            "result": [
                {
                    "timestamp": list(range(25)),
                    "indicators": {
                        "quote": [
                            {
                                "open": values,
                                "high": [value + 2 for value in values],
                                "low": [value - 2 for value in values],
                                "close": [value + 1 for value in values],
                                "volume": [10.0] * 25,
                            }
                        ]
                    },
                }
            ],
            "error": None,
        }
    }


def test_btc_usd_remains_unchanged() -> None:
    assert normalize_yahoo_symbol("BTC-USD") == "BTC-USD"


def test_eur_usd_normalizes_for_yahoo() -> None:
    assert normalize_yahoo_symbol("EUR-USD") == "EURUSD=X"


def test_gbp_usd_normalizes_for_yahoo() -> None:
    assert normalize_yahoo_symbol("GBP-USD") == "GBPUSD=X"


@pytest.mark.parametrize("symbol", ["EURUSD=X", "GBPUSD=X", "USDJPY=X"])
def test_already_normalized_forex_symbols_remain_unchanged(symbol: str) -> None:
    assert normalize_yahoo_symbol(symbol) == symbol


def test_unknown_symbol_passes_through_safely() -> None:
    assert normalize_yahoo_symbol("AAPL") == "AAPL"


def test_yahoo_provider_queries_normalized_symbol() -> None:
    requested_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_paths.append(request.url.path)
        return httpx.Response(200, json=_payload())

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        YahooFinanceMarketDataProvider(client=client).get_candles("EUR-USD", "5m", 20)

    assert requested_paths[0].endswith("/EURUSD=X")
