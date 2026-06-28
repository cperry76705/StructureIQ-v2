"""Focused diagnostics for unchanged backtest actionability gates."""

from dataclasses import replace
from types import SimpleNamespace

from core.backtesting import (
    build_backtest_trade,
    calculate_decision_diagnostics_summary,
    calculate_skip_diagnostics,
)
from core.decision_engine import (
    DecisionAction,
    DecisionDiagnostics,
    GateResult,
)
from core.journal import TradeOutcome
from core.market_data import Candle
from core.setup_engine import SetupStatus, SetupType
from core.strategy_engine import StrategyType


def _analysis(
    *,
    decision: DecisionAction = DecisionAction.BUY,
    setup_status: SetupStatus = SetupStatus.CONFIRMED,
    plan_status: str = "waiting",
    entry_zone: str | None = "100-101",
    stop_loss: str | None = "98",
    target: str | None = "105",
    risk_reward: float | None = 2.0,
):
    plan = SimpleNamespace(
        status=plan_status,
        entry_zone=entry_zone,
        stop_loss=stop_loss,
        target=target,
        estimated_risk_reward=risk_reward,
    )
    setup = SimpleNamespace(
        setup_type=SetupType.BULLISH_PULLBACK_CONTINUATION,
        setup_status=setup_status,
        entry_zone=entry_zone,
        stop_loss=stop_loss,
        target=target,
        estimated_risk_reward=risk_reward,
    )
    return SimpleNamespace(
        trader_analysis=SimpleNamespace(trade_plan=plan),
        decision=SimpleNamespace(action=decision),
        setup_plan=setup,
        strategy=SimpleNamespace(
            preferred_strategy=StrategyType.PULLBACK_CONTINUATION,
            strategy_alignment="aligned_with_decision",
        ),
    )


def _trade(analysis):
    return build_backtest_trade(
        analysis=analysis,
        timestamp=1,
        symbol="BTC-USD",
        future_candles=[],
    )


def test_wait_decision_is_attributed_to_decision_engine() -> None:
    trade = _trade(_analysis(decision=DecisionAction.WAIT))

    assert trade.outcome is TradeOutcome.SKIPPED
    assert trade.skip_reason_code == "decision_not_actionable"
    assert trade.blocking_engine == "decision_engine"


def test_developing_setup_is_attributed_to_setup_confirmation() -> None:
    trade = _trade(
        _analysis(
            setup_status=SetupStatus.DEVELOPING,
            plan_status="developing",
        )
    )

    assert trade.skip_reason_code == "setup_not_confirmed"
    assert trade.blocking_engine == "setup_engine"
    assert trade.actionability_status == "developing"


def test_missing_entry_stop_or_target_is_reported() -> None:
    trade = _trade(
        _analysis(
            plan_status="waiting",
            setup_status=SetupStatus.WAITING_FOR_CONFIRMATION,
            target=None,
        )
    )

    assert trade.skip_reason_code == "setup_missing_levels"
    assert trade.blocking_engine == "setup_engine"


def test_missing_risk_reward_is_reported() -> None:
    trade = _trade(
        _analysis(
            setup_status=SetupStatus.WAITING_FOR_CONFIRMATION,
            risk_reward=None,
        )
    )

    assert trade.skip_reason_code == "risk_reward_missing"
    assert trade.blocking_engine == "risk_engine"


def test_low_risk_reward_is_reported_without_changing_threshold() -> None:
    trade = _trade(_analysis(risk_reward=1.4))

    assert trade.skip_reason_code == "risk_reward_too_low"
    assert "1.50R" in (trade.skip_reason_detail or "")


def test_waiting_trader_plan_status_and_explanation_gate_are_captured() -> None:
    trade = _trade(_analysis(plan_status="waiting"))

    assert trade.skip_reason_code == "trader_plan_not_actionable"
    assert trade.blocking_engine == "explanation_engine"
    assert trade.actionability_status == "waiting"


def test_skip_diagnostics_aggregate_reasons_and_blocking_engines() -> None:
    trades = [
        _trade(_analysis(decision=DecisionAction.WAIT)),
        _trade(_analysis(decision=DecisionAction.WAIT)),
        _trade(
            _analysis(
                setup_status=SetupStatus.DEVELOPING,
                plan_status="developing",
            )
        ),
    ]

    diagnostics = calculate_skip_diagnostics(trades)

    assert diagnostics.total_skipped == 3
    assert diagnostics.by_reason_code == {
        "decision_not_actionable": 2,
        "setup_not_confirmed": 1,
    }
    assert diagnostics.by_blocking_engine == {
        "decision_engine": 2,
        "setup_engine": 1,
    }
    assert diagnostics.most_common_reason == "decision_not_actionable"


def test_actionable_trade_simulation_behavior_is_unchanged() -> None:
    trade = build_backtest_trade(
        analysis=_analysis(plan_status="actionable"),
        timestamp=1,
        symbol="BTC-USD",
        future_candles=[Candle(2, 101, 106, 100, 105, 100)],
    )

    assert trade.outcome is TradeOutcome.WIN
    assert trade.realized_r == 2.0
    assert trade.skip_reason_code is None
    assert trade.blocking_engine is None
    assert trade.actionability_status == "actionable"


def test_backtest_aggregates_blocked_decision_gates() -> None:
    snapshot = DecisionDiagnostics(
        raw_score=62.4,
        final_confidence=62.4,
        intended_direction="bullish",
        confidence_band="wait",
        blocked_by=("directional_confidence",),
        gate_results=(
            GateResult(
                "directional_confidence",
                False,
                True,
                62.4,
                ">= 70.0",
                -7.6,
                "Confidence is below the threshold.",
            ),
        ),
        human_readable_summary="Wait because confidence is below threshold.",
    )
    trades = [
        replace(
            _trade(_analysis(decision=DecisionAction.WAIT)),
            decision_diagnostics=snapshot,
        )
        for _ in range(2)
    ]

    summary = calculate_decision_diagnostics_summary(trades)

    assert summary.by_confidence_band == {"wait": 2}
    assert summary.by_blocked_gate == {"directional_confidence": 2}
    assert summary.average_confidence == 62.4
    assert summary.average_raw_score == 62.4
    assert summary.most_common_blocked_gate == "directional_confidence"


def test_actionable_plan_without_risk_reward_is_still_skipped_by_risk_engine() -> None:
    trade = _trade(
        _analysis(
            plan_status="actionable",
            setup_status=SetupStatus.CONFIRMED,
            risk_reward=None,
        )
    )

    assert trade.outcome is TradeOutcome.SKIPPED
    assert trade.skip_reason_code == "risk_reward_missing"
    assert trade.blocking_engine == "risk_engine"


def test_actionable_plan_below_execution_minimum_is_skipped() -> None:
    trade = _trade(
        _analysis(
            plan_status="actionable",
            setup_status=SetupStatus.CONFIRMED,
            risk_reward=1.4,
        )
    )

    assert trade.outcome is TradeOutcome.SKIPPED
    assert trade.skip_reason_code == "risk_reward_too_low"
    assert trade.blocking_engine == "risk_engine"
