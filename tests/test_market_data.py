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


@pytest.mark.parametrize(
    ("timeframe", "lookback", "expected_range"),
    [
        ("1m", 10_000, "7d"),
        ("5m", 10_000, "1mo"),
        ("15m", 5_000, "1mo"),
        ("30m", 2_000, "1mo"),
        ("1h", 20_000, "2y"),
    ],
)
def test_yahoo_caps_intraday_ranges(
    timeframe: str,
    lookback: int,
    expected_range: str,
) -> None:
    requested_ranges: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_ranges.append(request.url.params["range"])
        return httpx.Response(200, json=_payload())

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        YahooFinanceMarketDataProvider(client=client).get_candles(
            "BTC-USD", timeframe, lookback
        )

    assert requested_ranges == [expected_range]


def test_yahoo_daily_range_selection_remains_uncapped() -> None:
    requested_ranges: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_ranges.append(request.url.params["range"])
        return httpx.Response(200, json=_payload())

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        YahooFinanceMarketDataProvider(client=client).get_candles(
            "BTC-USD", "1d", 100
        )

    assert requested_ranges == ["6mo"]


def test_yahoo_error_includes_range_and_normalization_context() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(422))
    with httpx.Client(transport=transport) as client:
        with pytest.raises(MarketDataError) as captured:
            YahooFinanceMarketDataProvider(client=client).get_candles(
                "EUR-USD", "15m", 5_000
            )

    message = str(captured.value)
    assert "normalized_symbol=EURUSD=X" in message
    assert "selected_range=3mo" in message
    assert "capped_range=1mo" in message
