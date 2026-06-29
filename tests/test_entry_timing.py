from dataclasses import replace
from types import SimpleNamespace

from core.backtesting import (
    BacktestRequest,
    BacktestResult,
    BacktestTrade,
    build_backtest_trade,
    calculate_backtest_metrics,
)
from core.calibration import CalibrationEngine, CalibrationRequest
from core.decision_engine import DecisionAction
from core.entry_timing import EntryModel, EntryTimingProfile
from core.entry_timing_lab import (
    build_entry_timing_summary,
    ensure_immediate_baseline,
)
from core.journal import TradeOutcome
from core.market_data import Candle
from core.setup_engine import SetupStatus, SetupType
from core.strategy_engine import StrategyType


def _analysis():
    plan = SimpleNamespace(
        status="actionable",
        entry_zone="100",
        stop_loss="90",
        target="120",
        estimated_risk_reward=2.0,
    )
    setup = SimpleNamespace(
        setup_type=SetupType.BULLISH_BOS_RETEST,
        setup_status=SetupStatus.CONFIRMED,
        direction="bullish",
        entry_zone="100",
        stop_loss="90",
        target="120",
        estimated_risk_reward=2.0,
        entry_conditions=(),
        setup_level_diagnostics=SimpleNamespace(
            nearest_support=97.0,
            nearest_resistance=120.0,
        ),
    )
    return SimpleNamespace(
        trader_analysis=SimpleNamespace(trade_plan=plan),
        decision=SimpleNamespace(action=DecisionAction.BUY),
        setup_plan=setup,
        strategy=SimpleNamespace(
            preferred_strategy=StrategyType.BREAKOUT_CONTINUATION,
            strategy_alignment="aligned_with_decision",
            candidates=(),
        ),
    )


def _profile(
    name: str,
    model: EntryModel,
    *,
    touch: bool = False,
    allow_missed: bool = True,
    wait: int = 3,
) -> EntryTimingProfile:
    return EntryTimingProfile(
        name=name,
        description=f"Synthetic {name} timing.",
        entry_model=model,
        require_touch=touch,
        allow_missed_entries=allow_missed,
        max_wait_bars=wait,
    )


def _trade(profile: EntryTimingProfile, candles: list[Candle]) -> BacktestTrade:
    return build_backtest_trade(
        analysis=_analysis(),
        timestamp=1,
        symbol="BTC-USD",
        future_candles=candles,
        entry_timing_profile=profile,
        signal_close=101.0,
    )


def test_immediate_profile_matches_production_outcome() -> None:
    trade = _trade(
        _profile("immediate", EntryModel.IMMEDIATE, allow_missed=False),
        [Candle(2, 100, 121, 99, 120, 1)],
    )

    assert trade.outcome is TradeOutcome.WIN
    assert trade.realized_r == 2.0
    assert trade.entry == 100.0


def test_next_bar_open_can_reduce_expectancy() -> None:
    trade = _trade(
        _profile("next_bar", EntryModel.NEXT_BAR_OPEN, allow_missed=False),
        [Candle(2, 105, 121, 99, 120, 1)],
    )

    assert trade.entry == 105.0
    assert trade.realized_r == 1.0
    assert trade.entry_timing_diagnostics.delay_bars == 1


def test_conservative_pullback_improves_r_when_filled() -> None:
    trade = _trade(
        _profile("pullback", EntryModel.QUARTER_PULLBACK_STOP, touch=True),
        [Candle(2, 100, 121, 97, 120, 1)],
    )

    assert trade.entry == 97.5
    assert trade.realized_r == 3.0
    assert trade.entry_timing_diagnostics.entry_improvement_r == 0.25


def test_conservative_pullback_can_miss_winning_opportunity() -> None:
    trade = _trade(
        _profile("pullback", EntryModel.QUARTER_PULLBACK_STOP, touch=True, wait=2),
        [
            Candle(2, 100, 121, 99, 120, 1),
            Candle(3, 120, 122, 119, 121, 1),
        ],
    )

    assert trade.outcome is TradeOutcome.SKIPPED
    assert trade.entry_timing_diagnostics.missed is True
    assert trade.entry_timing_diagnostics.missed_opportunity_r == 2.0


def test_disallowed_miss_falls_back_deterministically() -> None:
    profile = _profile(
        "pullback_fallback",
        EntryModel.QUARTER_PULLBACK_STOP,
        touch=True,
        allow_missed=False,
        wait=1,
    )
    first = _trade(profile, [Candle(2, 100, 121, 99, 120, 1)])
    second = _trade(profile, [Candle(2, 100, 121, 99, 120, 1)])

    assert first.entry == second.entry == 100.0
    assert first.realized_r == second.realized_r == 2.0
    assert first.entry_timing_diagnostics.fallback_used is True


def test_touch_delay_and_summary_aggregates_are_calculated() -> None:
    immediate = _profile("immediate-copy", EntryModel.IMMEDIATE, allow_missed=False)
    pullback = _profile("delayed_pullback", EntryModel.QUARTER_PULLBACK_STOP, touch=True)
    immediate_trade = _trade(immediate, [Candle(2, 100, 121, 99, 120, 1)])
    pullback_trade = _trade(
        pullback,
        [
            Candle(2, 100, 105, 99, 102, 1),
            Candle(3, 102, 121, 97, 120, 1),
        ],
    )
    canonical = ensure_immediate_baseline([])[0]
    canonical_trade = _trade(canonical, [Candle(2, 100, 121, 99, 120, 1)])
    summary = build_entry_timing_summary([
        (canonical, [canonical_trade]),
        (immediate, [immediate_trade]),
        (pullback, [pullback_trade]),
    ])

    result = next(item for item in summary.profiles if item.profile_name == "delayed_pullback")
    assert result.average_entry_delay_bars == 2.0
    assert result.average_entry_improvement_r == 0.25
    assert result.filled_trades == 1
    assert summary.best_expectancy_profile == "delayed_pullback"


class _LabRunner:
    def run(self, request: BacktestRequest) -> BacktestResult:
        profile = request.entry_timing_profile or _profile(
            "production", EntryModel.IMMEDIATE, allow_missed=False
        )
        next_open = 105.0 if profile.entry_model is EntryModel.NEXT_BAR_OPEN else 100.0
        trade = _trade(profile, [Candle(2, next_open, 121, 99, 120, 1)])
        trade = replace(trade, setup_level_diagnostics=None)
        return BacktestResult(
            request=request,
            trades=(trade,),
            metrics=calculate_backtest_metrics([trade]),
            human_readable_summary="Synthetic timing calibration.",
            limitations=("Synthetic.",),
        )


class _UnusedProvider:
    def get_candles(self, symbol: str, timeframe: str, lookback: int) -> list[Candle]:
        del symbol, timeframe, lookback
        return []


def test_timing_profiles_do_not_mutate_production_calibration_metrics() -> None:
    runner = _LabRunner()
    result = CalibrationEngine(
        _UnusedProvider(), backtesting_engine_factory=lambda provider: runner
    ).run(
        CalibrationRequest(
            symbols=["BTC-USD"],
            timeframes=["5m"],
            higher_timeframes=["1h"],
            lookback=100,
            max_trades_per_run=1,
            risk_per_trade_percent=1.0,
            starting_balance=10_000,
            entry_timing_profiles=[
                _profile("next_bar", EntryModel.NEXT_BAR_OPEN, allow_missed=False)
            ],
        )
    )

    assert result.aggregate_metrics.average_r == 2.0
    assert result.entry_timing_summary is not None
    timing = {item.profile_name: item for item in result.entry_timing_summary.profiles}
    assert timing["immediate"].average_r == 2.0
    assert timing["next_bar"].average_r == 1.0
