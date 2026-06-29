from core.backtesting import (
    BacktestRequest,
    BacktestResult,
    BacktestTrade,
    calculate_backtest_metrics,
    simulate_execution_adjusted_outcome,
)
from core.calibration import CalibrationEngine, CalibrationRequest
from core.execution import ExecutionProfile, FillModel, SlippageType
from core.execution_sensitivity import (
    ExecutionSensitivityProfile,
    build_execution_sensitivity_summary,
    crypto_execution_sensitivity_profiles,
    ensure_perfect_baseline,
    forex_execution_sensitivity_profiles,
)
from core.journal import TradeOutcome
from core.market_data import Candle


def _profile(name: str, **values: object) -> ExecutionSensitivityProfile:
    return ExecutionSensitivityProfile(
        name=name,
        description=f"Synthetic {name} profile.",
        execution_profile=ExecutionProfile(**values),
    )


def _trade(profile: ExecutionProfile, *, next_open: float = 100.0) -> BacktestTrade:
    outcome, realized, reason, diagnostics, actual, _ = simulate_execution_adjusted_outcome(
        action="buy",
        entry=100.0,
        stop_loss=90.0,
        target=120.0,
        future_candles=[Candle(2, next_open, 121.0, 99.0, 120.0, 1.0)],
        estimated_risk_reward=2.0,
        execution_profile=profile,
        symbol="BTC-USD",
        timestamp=1,
        starting_balance=10_000.0,
        risk_per_trade_percent=1.0,
    )
    return BacktestTrade(
        timestamp=1,
        symbol="BTC-USD",
        action="buy",
        setup_type="bullish_bos_retest",
        strategy_type="breakout_continuation",
        entry=actual,
        stop_loss=90.0,
        target=120.0,
        estimated_risk_reward=2.0,
        outcome=outcome,
        realized_r=realized,
        reason=reason,
        execution_diagnostics=diagnostics,
    )


def _summary(*profiles: ExecutionSensitivityProfile):
    all_profiles = ensure_perfect_baseline(list(profiles))
    return build_execution_sensitivity_summary(
        [(profile, [_trade(profile.execution_profile)]) for profile in all_profiles]
    )


def test_perfect_profile_matches_baseline_results() -> None:
    summary = _summary(_profile("spread", spread=1.0))
    perfect = summary.profiles[0]

    assert perfect.profile_name == "perfect"
    assert perfect.average_r == 2.0
    assert perfect.baseline_expectancy == perfect.realistic_expectancy


def test_isolated_cost_profiles_reduce_expectancy() -> None:
    summary = _summary(
        _profile("spread", spread=1.0),
        _profile("slippage", slippage=0.5),
        _profile("commission", commission_per_trade=10.0),
    )
    results = {item.profile_name: item for item in summary.profiles}

    assert results["spread"].expectancy_reduction > 0
    assert results["slippage"].expectancy_reduction > 0
    assert results["commission"].expectancy_reduction > 0
    assert summary.most_sensitive_cost_component == "spread"


def test_next_bar_profile_can_change_expectancy() -> None:
    perfect = _profile("perfect-copy")
    next_bar = _profile("next_bar", fill_model=FillModel.NEXT_BAR)
    summary = build_execution_sensitivity_summary([
        (ensure_perfect_baseline([])[0], [_trade(ExecutionProfile())]),
        (perfect, [_trade(perfect.execution_profile)]),
        (next_bar, [_trade(next_bar.execution_profile, next_open=105.0)]),
    ])

    result = next(item for item in summary.profiles if item.profile_name == "next_bar")
    assert result.average_r == 1.5
    assert result.expectancy_reduction == 0.5


def test_combined_profile_and_largest_drop_are_reported() -> None:
    summary = _summary(
        _profile("spread", spread=1.0),
        _profile(
            "combined",
            spread=2.0,
            slippage=1.0,
            slippage_type=SlippageType.FIXED,
            commission_per_trade=10.0,
        ),
    )
    combined = next(item for item in summary.profiles if item.profile_name == "combined")

    assert combined.average_execution_degradation > 0
    assert summary.largest_expectancy_drop_profile == "combined"
    assert summary.worst_profile == "combined"
    assert summary.most_sensitive_cost_component == "combined_costs"


def test_default_profile_helpers_include_documented_scenarios() -> None:
    forex_names = {item.name for item in forex_execution_sensitivity_profiles()}
    crypto_names = {item.name for item in crypto_execution_sensitivity_profiles()}

    assert len(forex_names) == 8
    assert len(crypto_names) == 8
    assert {"perfect", "forex_harsh_realistic"} <= forex_names
    assert {"perfect", "crypto_harsh_realistic"} <= crypto_names


class _Runner:
    def __init__(self) -> None:
        self.requests: list[BacktestRequest] = []

    def run(self, request: BacktestRequest) -> BacktestResult:
        self.requests.append(request)
        trade = _trade(request.execution_profile or ExecutionProfile())
        return BacktestResult(
            request=request,
            trades=(trade,),
            metrics=calculate_backtest_metrics([trade]),
            human_readable_summary="Synthetic sensitivity run.",
            limitations=("Synthetic.",),
        )


class _UnusedProvider:
    def get_candles(self, symbol: str, timeframe: str, lookback: int) -> list[Candle]:
        del symbol, timeframe, lookback
        return []


def _request(**overrides: object) -> CalibrationRequest:
    values: dict[str, object] = {
        "symbols": ["BTC-USD"],
        "timeframes": ["5m"],
        "higher_timeframes": ["1h"],
        "lookback": 100,
        "max_trades_per_run": 1,
        "risk_per_trade_percent": 1.0,
        "starting_balance": 10_000.0,
    }
    values.update(overrides)
    return CalibrationRequest(**values)


def test_calibration_is_unchanged_without_sensitivity_profiles() -> None:
    runner = _Runner()
    result = CalibrationEngine(
        _UnusedProvider(), backtesting_engine_factory=lambda provider: runner
    ).run(_request())

    assert len(runner.requests) == 1
    assert result.aggregate_metrics.average_r == 2.0
    assert result.execution_sensitivity_summary is None
    assert result.entry_timing_summary is None
    assert result.market_regime_summary is None
    assert result.regime_validation_summary is None


def test_calibration_adds_isolated_sensitivity_without_mutating_metrics() -> None:
    runner = _Runner()
    result = CalibrationEngine(
        _UnusedProvider(), backtesting_engine_factory=lambda provider: runner
    ).run(
        _request(
            execution_sensitivity_profiles=[
                {
                    "name": "spread_only",
                    "description": "Synthetic spread scenario.",
                    "execution_profile": {"spread": 1.0},
                }
            ]
        )
    )

    assert result.aggregate_metrics.average_r == 2.0
    assert result.execution_sensitivity_summary is not None
    assert [item.profile_name for item in result.execution_sensitivity_summary.profiles] == [
        "perfect",
        "spread_only",
    ]
    assert len(runner.requests) == 3  # production + perfect + spread-only
