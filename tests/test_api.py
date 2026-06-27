from math import sin

from fastapi.testclient import TestClient

from app.main import app, get_market_data_provider
from core.market_data import Candle, MarketDataError


class FailingProvider:
    def get_candles(self, symbol: str, timeframe: str, lookback: int) -> list[Candle]:
        del symbol, timeframe, lookback
        raise MarketDataError("test provider is offline")


class SyntheticProvider:
    def get_candles(self, symbol: str, timeframe: str, lookback: int) -> list[Candle]:
        del symbol, timeframe, lookback
        candles: list[Candle] = []
        for index in range(60):
            close = 100 + index * 0.4 + sin(index * 0.8) * 3
            candles.append(Candle(index, close - 0.2, close + 1, close - 1, close, 100))
        return candles


def test_analysis_contract_is_unchanged_with_structure_engine() -> None:
    app.dependency_overrides[get_market_data_provider] = lambda: SyntheticProvider()
    try:
        response = TestClient(app).post(
            "/analysis",
            json={
                "symbol": "BTC-USD",
                "timeframe": "5m",
                "higher_timeframe": "1h",
                "lookback": 200,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert set(response.json()) == {
        "symbol",
        "timeframe",
        "higher_timeframe_bias",
        "current_structure",
        "action",
        "setup",
        "confidence",
        "entry_zone",
        "stop_loss",
        "target",
        "reasons",
    }


def test_analysis_returns_informative_503_when_provider_fails() -> None:
    app.dependency_overrides[get_market_data_provider] = lambda: FailingProvider()
    try:
        response = TestClient(app).post(
            "/analysis",
            json={
                "symbol": "BTC-USD",
                "timeframe": "5m",
                "higher_timeframe": "1h",
                "lookback": 200,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Market data unavailable: test provider is offline"
    }
