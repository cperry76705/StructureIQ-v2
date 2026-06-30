from math import sin

from fastapi.testclient import TestClient

from app.main import app, get_market_data_provider
from core.market_data import Candle
from core.monte_carlo import run_monte_carlo
from core.monte_carlo_reporting import build_monte_carlo_report


def _report(returns, *, risk=1.0, simulations=200):
    monte_carlo = run_monte_carlo(
        returns,
        simulations=simulations,
        random_seed=42,
        risk_per_trade_percent=risk,
    )
    return build_monte_carlo_report(monte_carlo, returns)


def test_small_sample_is_insufficient_and_has_human_readable_output() -> None:
    result = _report([2.0, -1.0, 1.5, -0.5] * 5)

    assert result.report.overall_status == "INSUFFICIENT_DATA"
    assert "insufficient_trade_sample" in result.failure_reasons
    assert result.expectancy_confidence.sample_warning is not None
    assert result.report.human_readable_summary
    assert result.risk_heatmap.tail_risk.explanation


def test_high_drawdown_sample_fails_reporting() -> None:
    result = _report([-1.0] * 120, risk=5.0)

    assert result.report.overall_status == "FAIL"
    assert result.report.probability_of_drawdown_over_20_percent >= 25.0
    assert "drawdown_probability_too_high" in result.failure_reasons
    assert result.risk_heatmap.drawdown_risk.status == "HIGH"


def test_stable_positive_sample_passes_and_reports_targets() -> None:
    result = _report([1.0] * 120)

    assert result.report.overall_status == "PASS"
    assert result.report.probability_of_profit > 95.0
    assert result.expectancy_confidence.lower_bound_positive is True
    assert result.target_probabilities.probability_reaching_50r > 0
    assert result.target_probabilities.probability_growth_10_percent > 0
    assert result.risk_heatmap.ruin_risk.status == "LOW"


def test_kelly_and_confidence_calculations_are_deterministic() -> None:
    returns = [2.0, -1.0] * 60
    first = _report(returns)
    second = _report(returns)

    assert first.kelly_summary == second.kelly_summary
    assert first.expectancy_confidence == second.expectancy_confidence
    assert first.kelly_summary.average_win_r == 2.0
    assert first.kelly_summary.average_loss_r == 1.0
    assert first.kelly_summary.full_kelly_fraction == 0.25


def test_expectancy_interval_crossing_zero_is_a_failure_reason() -> None:
    result = _report([1.0, -1.0] * 60)

    assert result.expectancy_confidence.lower_bound_positive is False
    assert "expectancy_confidence_crosses_zero" in result.failure_reasons
    assert result.report.overall_status == "FAIL"


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


def test_reporting_api_fields_are_additive_and_metrics_stay_unchanged() -> None:
    app.dependency_overrides[get_market_data_provider] = lambda: _Provider()
    try:
        client = TestClient(app)
        baseline = client.post("/calibrate", json=_request(False))
        reported = client.post("/calibrate", json=_request(True))
    finally:
        app.dependency_overrides.clear()

    assert baseline.status_code == reported.status_code == 200
    baseline_payload = baseline.json()
    reported_payload = reported.json()
    fields = (
        "monte_carlo_report",
        "monte_carlo_risk_heatmap",
        "monte_carlo_target_probabilities",
        "monte_carlo_expectancy_confidence",
        "monte_carlo_kelly_summary",
        "monte_carlo_failure_reasons",
    )
    assert all(baseline_payload[field] is None for field in fields)
    assert all(reported_payload[field] is not None for field in fields)
    assert baseline_payload["aggregate_metrics"] == reported_payload["aggregate_metrics"]

