from fastapi.testclient import TestClient

from app.main import app, get_market_data_provider
from core.market_data import Candle


class _Provider:
    def get_candles(self, symbol: str, timeframe: str, lookback: int) -> list[Candle]:
        del symbol, timeframe
        candles = [
            Candle(index, 100.0, 101.0, 99.0, 100.0, 100.0)
            for index in range(60)
        ]
        return candles[-lookback:]


def _override_provider() -> None:
    app.dependency_overrides[get_market_data_provider] = lambda: _Provider()


def test_calibrate_endpoint_works() -> None:
    _override_provider()
    try:
        response = TestClient(app).post(
            "/calibrate",
            json={
                "symbols": ["BTC-USD", "EUR-USD"],
                "timeframes": ["5m"],
                "higher_timeframes": ["1h"],
                "lookback": 60,
                "max_trades_per_run": 1,
                "risk_per_trade_percent": 1,
                "starting_balance": 10000,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["aggregate_metrics"]["total_runs"] == 2
    assert response.json()["aggregate_skip_diagnostics"]["total_skipped"] == 2
    assert response.json()["aggregate_decision_diagnostics"]["by_blocked_gate"]
    assert [
        item["threshold"] for item in response.json()["threshold_sensitivity"]
    ] == [50.0, 55.0, 60.0, 65.0, 70.0]
    assert response.json()["aggregate_risk_reward_summary"]["total_records"] == 2
    assert response.json()["aggregate_setup_level_summary"]["total_records"] == 2
    assert "aggregate_outcome_diagnostics" in response.json()
    assert len(response.json()["aggregate_trade_management_sensitivity"]) == 7
    assert response.json()["aggregate_setup_coverage_summary"]["total_records"] == 2
    assert response.json()["recommendations"]


def test_analysis_endpoint_still_works_after_calibration() -> None:
    _override_provider()
    try:
        response = TestClient(app).post(
            "/analysis",
            json={
                "symbol": "EUR-USD",
                "timeframe": "5m",
                "higher_timeframe": "1h",
                "lookback": 60,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["symbol"] == "EUR-USD"


def test_backtest_endpoint_still_works_after_calibration() -> None:
    _override_provider()
    try:
        response = TestClient(app).post(
            "/backtest",
            json={
                "symbol": "EUR-USD",
                "timeframe": "5m",
                "higher_timeframe": "1h",
                "lookback": 60,
                "starting_balance": 10000,
                "risk_per_trade_percent": 1,
                "max_trades": 1,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["request"]["symbol"] == "EUR-USD"
    assert response.json()["setup_coverage_summary"]["total_records"] == 1
