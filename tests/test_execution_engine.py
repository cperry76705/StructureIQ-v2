import pytest

from core.backtesting import BacktestRequest, simulate_execution_adjusted_outcome
from core.execution import (
    ExecutionProfile,
    FillModel,
    SlippageType,
    calculate_execution_summary,
)
from core.journal import TradeOutcome
from core.market_data import Candle


def _winning_candles(action: str, *, next_open: float = 100.0) -> list[Candle]:
    if action == "buy":
        return [Candle(2, next_open, 121.0, 99.0, 120.0, 1.0)]
    return [Candle(2, next_open, 101.0, 79.0, 80.0, 1.0)]


def _run(action: str, profile: ExecutionProfile, *, timestamp: int = 1):
    return simulate_execution_adjusted_outcome(
        action=action,
        entry=100.0,
        stop_loss=90.0 if action == "buy" else 110.0,
        target=120.0 if action == "buy" else 80.0,
        future_candles=_winning_candles(action),
        estimated_risk_reward=2.0,
        execution_profile=profile,
        symbol="BTC-USD",
        timestamp=timestamp,
        starting_balance=10_000.0,
        risk_per_trade_percent=1.0,
    )


def test_spread_reduces_bullish_r_correctly() -> None:
    outcome, realized, _, diagnostics, actual, _ = _run(
        "buy", ExecutionProfile(spread=1.0)
    )

    assert outcome is TradeOutcome.WIN
    assert actual == 101.0
    assert realized == 1.9
    assert diagnostics.execution_degradation_r == pytest.approx(0.1)


def test_spread_reduces_bearish_r_correctly() -> None:
    outcome, realized, _, diagnostics, actual, _ = _run(
        "sell", ExecutionProfile(spread=1.0)
    )

    assert outcome is TradeOutcome.WIN
    assert actual == 99.0
    assert realized == 1.9
    assert diagnostics.spread_cost == 1.0


def test_fixed_slippage_is_applied_adversely() -> None:
    _, realized, _, diagnostics, actual, _ = _run(
        "buy",
        ExecutionProfile(slippage=0.5),
    )

    assert actual == 100.5
    assert realized == 1.95
    assert diagnostics.slippage_cost == 0.5


def test_random_slippage_is_seeded_and_deterministic() -> None:
    profile = ExecutionProfile(
        slippage=0.75,
        slippage_type=SlippageType.RANDOM,
        random_seed=42,
    )

    first = _run("buy", profile, timestamp=99)
    second = _run("buy", profile, timestamp=99)

    assert first[4] == second[4]
    assert first[3].slippage_cost == second[3].slippage_cost


def test_fixed_commission_reduces_profit_in_r() -> None:
    outcome, realized, _, diagnostics, _, _ = _run(
        "buy",
        ExecutionProfile(commission_per_trade=10.0),
    )

    assert outcome is TradeOutcome.WIN
    assert realized == 1.9
    assert diagnostics.commission_cost == 0.1


def test_next_bar_fill_uses_next_open() -> None:
    profile = ExecutionProfile(fill_model=FillModel.NEXT_BAR)
    result = simulate_execution_adjusted_outcome(
        action="buy",
        entry=100.0,
        stop_loss=90.0,
        target=120.0,
        future_candles=_winning_candles("buy", next_open=102.0),
        estimated_risk_reward=2.0,
        execution_profile=profile,
        symbol="BTC-USD",
        timestamp=1,
        starting_balance=10_000.0,
        risk_per_trade_percent=1.0,
    )

    assert result[4] == 102.0
    assert result[1] == 1.8
    assert result[3].fill_model_used == "next_bar"


def test_touch_fill_waits_for_requested_price() -> None:
    result = simulate_execution_adjusted_outcome(
        action="buy",
        entry=100.0,
        stop_loss=90.0,
        target=120.0,
        future_candles=[
            Candle(2, 98.0, 99.0, 97.0, 98.0, 1.0),
            Candle(3, 100.0, 121.0, 99.0, 120.0, 1.0),
        ],
        estimated_risk_reward=2.0,
        execution_profile=ExecutionProfile(fill_model=FillModel.TOUCH),
        symbol="BTC-USD",
        timestamp=1,
        starting_balance=10_000.0,
        risk_per_trade_percent=1.0,
    )

    assert result[0] is TradeOutcome.WIN
    assert result[4] == 100.0
    assert len(result[5]) == 1


def test_partial_fill_scales_realized_r_deterministically() -> None:
    _, realized, _, diagnostics, _, _ = _run(
        "buy",
        ExecutionProfile(
            allow_partial_fill=True,
            partial_fill_probability=1.0,
            random_seed=7,
        ),
    )

    assert realized == 1.0
    assert diagnostics.execution_quality == "partial"


def test_perfect_execution_profile_preserves_existing_result() -> None:
    outcome, realized, _, diagnostics, actual, _ = simulate_execution_adjusted_outcome(
        action="buy",
        entry=100.0,
        stop_loss=90.0,
        target=120.0,
        future_candles=_winning_candles("buy"),
        estimated_risk_reward=2.123,
        execution_profile=ExecutionProfile(),
        symbol="BTC-USD",
        timestamp=1,
        starting_balance=10_000.0,
        risk_per_trade_percent=1.0,
    )

    assert outcome is TradeOutcome.WIN
    assert realized == 2.123
    assert actual == 100.0
    assert diagnostics.execution_quality == "perfect"
    assert diagnostics.requested_entry == diagnostics.actual_entry


def test_execution_diagnostics_roll_up_expectancy_degradation() -> None:
    realistic = _run("buy", ExecutionProfile(spread=1.0))[3]
    summary = calculate_execution_summary([realistic])

    assert summary.modeled_trades == 1
    assert summary.baseline_expectancy == 2.0
    assert summary.realistic_expectancy == 1.9
    assert summary.expectancy_reduction == pytest.approx(0.1)


def test_backtest_request_accepts_optional_execution_profile() -> None:
    request = BacktestRequest(
        symbol="BTC-USD",
        timeframe="5m",
        higher_timeframe="1h",
        lookback=100,
        execution_profile={
            "spread": 0.5,
            "slippage": 0.25,
            "slippage_type": "fixed",
            "commission_per_trade": 2.0,
            "commission_type": "fixed",
            "fill_model": "next_bar",
        },
    )

    assert request.execution_profile is not None
    assert request.execution_profile.fill_model is FillModel.NEXT_BAR
