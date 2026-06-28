"""Read-only stop-management and profit-protection sensitivity tests."""

from core.backtesting import (
    BacktestTrade,
    LossReason,
    TradeManagementRule,
    TradeOutcomeDiagnostics,
    calculate_backtest_metrics,
    calculate_trade_management_sensitivity,
)
from core.journal import TradeOutcome


def _trade(
    outcome: TradeOutcome,
    realized_r: float,
    *,
    mfe_before_outcome: float,
) -> BacktestTrade:
    diagnostics = TradeOutcomeDiagnostics(
        outcome=outcome,
        realized_r=realized_r,
        entry_price=100.0,
        stop_loss=98.0,
        target=104.0,
        first_touch="target" if outcome is TradeOutcome.WIN else "stop",
        bars_to_outcome=3,
        max_favorable_excursion_r=(2.0 if outcome is TradeOutcome.WIN else mfe_before_outcome),
        max_adverse_excursion_r=(0.5 if outcome is TradeOutcome.WIN else 1.0),
        direction_was_correct_initially=mfe_before_outcome >= 0.5,
        loss_reason=(None if outcome is TradeOutcome.WIN else LossReason.STOP_TOO_TIGHT),
        human_readable_summary="Synthetic path.",
        max_favorable_excursion_before_outcome_r=mfe_before_outcome,
    )
    return BacktestTrade(
        timestamp=1,
        symbol="BTC-USD",
        action="buy",
        setup_type="bullish_pullback_continuation",
        strategy_type="pullback_continuation",
        entry=100.0,
        stop_loss=98.0,
        target=104.0,
        estimated_risk_reward=2.0,
        outcome=outcome,
        realized_r=realized_r,
        reason="Synthetic closed trade.",
        outcome_diagnostics=diagnostics,
    )


def _result(trades: list[BacktestTrade], rule: TradeManagementRule):
    return next(
        item for item in calculate_trade_management_sensitivity(trades)
        if item.rule is rule
    )


def test_breakeven_at_one_r_converts_favorable_loss() -> None:
    result = _result(
        [_trade(TradeOutcome.LOSS, -1.0, mfe_before_outcome=1.2)],
        TradeManagementRule.MOVE_STOP_TO_BREAKEVEN_AT_1R,
    )

    assert result.breakeven == 1
    assert result.total_r == 0.0


def test_breakeven_at_one_point_five_requires_threshold() -> None:
    result = _result(
        [_trade(TradeOutcome.LOSS, -1.0, mfe_before_outcome=1.2)],
        TradeManagementRule.MOVE_STOP_TO_BREAKEVEN_AT_1_5R,
    )

    assert result.losses == 1
    assert result.total_r == -1.0


def test_partial_at_one_r_improves_loss_outcome() -> None:
    result = _result(
        [_trade(TradeOutcome.LOSS, -1.0, mfe_before_outcome=1.2)],
        TradeManagementRule.TAKE_PARTIAL_AT_1R,
    )

    assert result.total_r == 0.0
    assert result.improved_vs_baseline is True


def test_trailing_after_one_r_locks_positive_r() -> None:
    result = _result(
        [_trade(TradeOutcome.LOSS, -1.0, mfe_before_outcome=1.2)],
        TradeManagementRule.TRAIL_AFTER_1R,
    )

    assert result.wins == 1
    assert result.total_r == 0.25


def test_no_management_matches_baseline_and_metrics_remain_unchanged() -> None:
    trades = [
        _trade(TradeOutcome.WIN, 2.0, mfe_before_outcome=0.0),
        _trade(TradeOutcome.LOSS, -1.0, mfe_before_outcome=1.2),
    ]
    production_before = calculate_backtest_metrics(trades)

    baseline = _result(trades, TradeManagementRule.NONE)
    production_after = calculate_backtest_metrics(trades)

    assert baseline.wins == production_before.wins
    assert baseline.losses == production_before.losses
    assert baseline.total_r == production_before.total_r
    assert baseline.average_r == production_before.average_r
    assert production_after == production_before
