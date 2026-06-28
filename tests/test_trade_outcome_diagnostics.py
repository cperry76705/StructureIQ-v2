"""Deterministic path and excursion diagnostics for executed trades."""

from core.backtesting import (
    LossReason,
    diagnose_trade_outcome,
    simulate_trade_outcome,
)
from core.journal import TradeOutcome
from core.market_data import Candle


def _diagnose(action: str, candles: list[Candle]):
    entry, stop, target = (
        (100.0, 98.0, 104.0)
        if action == "buy"
        else (100.0, 102.0, 96.0)
    )
    outcome, realized_r, _ = simulate_trade_outcome(
        action=action,
        entry=entry,
        stop_loss=stop,
        target=target,
        future_candles=candles,
        estimated_risk_reward=2.0,
    )
    return diagnose_trade_outcome(
        action=action,
        entry=entry,
        stop_loss=stop,
        target=target,
        future_candles=candles,
        outcome=outcome,
        realized_r=realized_r,
    )


def test_winning_trade_reports_target_first_touch() -> None:
    result = _diagnose("buy", [Candle(1, 100, 104, 99, 103, 100)])

    assert result.outcome is TradeOutcome.WIN
    assert result.first_touch == "target"
    assert result.bars_to_outcome == 1


def test_losing_trade_reports_stop_first_touch_and_immediate_loss() -> None:
    result = _diagnose("buy", [Candle(1, 100, 101, 98, 98.5, 100)])

    assert result.outcome is TradeOutcome.LOSS
    assert result.first_touch == "stop"
    assert result.loss_reason is LossReason.STOPPED_IMMEDIATELY


def test_same_candle_stop_and_target_remains_conservative_and_ambiguous() -> None:
    result = _diagnose("buy", [Candle(1, 100, 104, 98, 101, 100)])

    assert result.outcome is TradeOutcome.LOSS
    assert result.first_touch == "both_same_candle"
    assert result.loss_reason is LossReason.SAME_CANDLE_AMBIGUOUS


def test_bullish_mfe_and_mae_are_measured_in_r() -> None:
    result = _diagnose(
        "buy",
        [
            Candle(1, 100, 102, 99, 101, 100),
            Candle(2, 101, 104, 100, 103, 100),
        ],
    )

    assert result.max_favorable_excursion_r == 2.0
    assert result.max_adverse_excursion_r == 0.5


def test_bearish_mfe_and_mae_are_measured_in_r() -> None:
    result = _diagnose(
        "sell",
        [
            Candle(1, 100, 101, 98, 99, 100),
            Candle(2, 99, 100, 96, 97, 100),
        ],
    )

    assert result.max_favorable_excursion_r == 2.0
    assert result.max_adverse_excursion_r == 0.5


def test_loss_without_half_r_follow_through_is_classified() -> None:
    result = _diagnose(
        "buy",
        [
            Candle(1, 100, 100.6, 99, 100.1, 100),
            Candle(2, 100.1, 100.4, 98, 98.5, 100),
        ],
    )

    assert result.direction_was_correct_initially is False
    assert result.loss_reason is LossReason.NO_FOLLOW_THROUGH


def test_diagnostics_do_not_change_existing_simulation_result() -> None:
    candles = [Candle(1, 100, 104, 98, 101, 100)]
    outcome, realized_r, _ = simulate_trade_outcome(
        action="buy",
        entry=100,
        stop_loss=98,
        target=104,
        future_candles=candles,
        estimated_risk_reward=2,
    )
    diagnostics = diagnose_trade_outcome(
        action="buy",
        entry=100,
        stop_loss=98,
        target=104,
        future_candles=candles,
        outcome=outcome,
        realized_r=realized_r,
    )

    assert outcome is TradeOutcome.LOSS
    assert realized_r == -1.0
    assert diagnostics.outcome is outcome
    assert diagnostics.realized_r == realized_r
