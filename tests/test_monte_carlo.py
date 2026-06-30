from math import sin

from fastapi.testclient import TestClient

from app.main import app, get_market_data_provider
from core.market_data import Candle
from core.monte_carlo import run_monte_carlo


def test_monte_carlo_is_deterministic_and_supports_both_sampling_methods() -> None:
    first = run_monte_carlo(
        [2.0, -1.0, 1.5, -0.5], simulations=50, random_seed=17
    )
    second = run_monte_carlo(
        [2.0, -1.0, 1.5, -0.5], simulations=50, random_seed=17
    )

    assert first == second
    assert first.summary.methods == (
        "trade_order_reshuffle",
        "sampling_with_replacement",
    )
    assert {item.method for item in first.distribution.simulations} == set(
        first.summary.methods
    )


def test_empty_trade_list_returns_controlled_unavailable_result() -> None:
    result = run_monte_carlo([], simulations=20)

    assert result.summary.available is False
    assert result.summary.source_trades == 0
    assert result.distribution.simulations == ()
    assert result.risk_summary.risk_level == "unavailable"
    assert "no closed trades" in result.summary.human_readable_summary.lower()


def test_profitable_trades_produce_positive_profit_probability() -> None:
    result = run_monte_carlo(
        [2.0, 1.5, -1.0, 2.5, -1.0],
        simulations=200,
        random_seed=42,
    )

    assert result.summary.available is True
    assert result.risk_summary.probability_of_finishing_profitable > 50.0
    assert result.summary.median_ending_balance > result.summary.starting_balance


def test_losing_trades_show_elevated_ruin_and_drawdown_risk() -> None:
    result = run_monte_carlo(
        [-1.0] * 20,
        simulations=100,
        random_seed=42,
        risk_per_trade_percent=10.0,
    )

    assert result.risk_summary.risk_of_ruin > 0
    assert result.risk_summary.probability_of_drawdown_over_20_percent == 100.0
    assert result.risk_summary.risk_level == "high"
    assert result.risk_summary.probability_of_finishing_profitable == 0.0


def test_execution_degradation_stress_reduces_distribution_expectancy() -> None:
    baseline = run_monte_carlo(
        [1.0] * 20, simulations=100, random_seed=4
    )
    stressed = run_monte_carlo(
        [1.0] * 20,
        simulations=100,
        random_seed=4,
        execution_degradations=[0.5],
    )

    assert stressed.risk_summary.expectancy_mean < baseline.risk_summary.expectancy_mean


class _Provider:
    def get_candles(self, symbol: str, timeframe: str, lookback: int) -> list[Candle]:
        del symbol, timeframe
        candles = []
        for index in range(320):
            close = 100 + index * 0.08 + sin(index * 0.7) * 2
            candles.append(
                Candle(index, close - 0.2, close + 0.8, close - 0.8, close, 100)
            )
        return candles[-lookback:]


def _request(enabled: bool) -> dict:
    return {
        "symbols": ["BTC-USD"],
        "timeframes": ["5m"],
        "higher_timeframes": ["1h"],
        "lookback": 300,
        "max_trades_per_run": 50,
        "risk_per_trade_percent": 1,
        "starting_balance": 10000,
        "monte_carlo_analysis": enabled,
        "monte_carlo_simulations": 25,
        "monte_carlo_random_seed": 42,
    }


def test_api_monte_carlo_fields_are_additive_and_metrics_do_not_change() -> None:
    app.dependency_overrides[get_market_data_provider] = lambda: _Provider()
    try:
        client = TestClient(app)
        baseline = client.post("/calibrate", json=_request(False))
        simulated = client.post("/calibrate", json=_request(True))
    finally:
        app.dependency_overrides.clear()

    assert baseline.status_code == simulated.status_code == 200
    baseline_payload = baseline.json()
    simulated_payload = simulated.json()
    fields = (
        "monte_carlo_summary",
        "monte_carlo_distribution",
        "monte_carlo_risk_summary",
        "monte_carlo_recommendations",
    )
    assert all(baseline_payload[field] is None for field in fields)
    assert all(simulated_payload[field] is not None for field in fields)
    assert (
        baseline_payload["aggregate_metrics"]
        == simulated_payload["aggregate_metrics"]
    )
