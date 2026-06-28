"""Counterfactual confidence-threshold study over immutable snapshots."""

from core.backtesting import BacktestTrade, ExecutionReadinessSnapshot
from core.calibration import (
    ThresholdSensitivityResult,
    _threshold_sensitivity_recommendation,
    calculate_threshold_sensitivity,
)
from core.decision_engine import DecisionDiagnostics, GateResult
from core.journal import TradeOutcome


def _diagnostics(score: float) -> DecisionDiagnostics:
    return DecisionDiagnostics(
        raw_score=score,
        final_confidence=round(score, 1),
        intended_direction="bullish",
        confidence_band="wait" if score < 70 else "tradable",
        blocked_by=("directional_confidence",) if score < 70 else (),
        gate_results=(
            GateResult(
                "directional_confidence",
                score >= 70,
                True,
                score,
                ">= 70.0",
                min(0.0, score - 70),
                None if score >= 70 else "Below production threshold.",
            ),
            GateResult(
                "structure_alignment", True, True, "bullish", "bullish", 0.0, None
            ),
            GateResult(
                "multi_timeframe_alignment",
                True,
                True,
                "aligned_bullish",
                "aligned_bullish",
                0.0,
                None,
            ),
        ),
        human_readable_summary="Synthetic diagnostics.",
    )


def _snapshot(
    *,
    setup_status: str = "confirmed",
    plan_status: str = "actionable",
    entry_zone: str | None = "100-101",
    stop_loss: str | None = "98",
    target: str | None = "105",
    risk_reward: float | None = 2.0,
    strategy: str = "pullback_continuation",
    alignment: str = "aligned_with_decision",
) -> ExecutionReadinessSnapshot:
    return ExecutionReadinessSnapshot(
        setup_status=setup_status,
        plan_status=plan_status,
        entry_zone=entry_zone,
        stop_loss=stop_loss,
        target=target,
        estimated_risk_reward=risk_reward,
        preferred_strategy=strategy,
        strategy_alignment=alignment,
    )


def _record(score: float, snapshot: ExecutionReadinessSnapshot) -> BacktestTrade:
    return BacktestTrade(
        timestamp=1,
        symbol="BTC-USD",
        action="wait",
        setup_type="bullish_pullback_continuation",
        strategy_type=snapshot.preferred_strategy,
        entry=None,
        stop_loss=None,
        target=None,
        estimated_risk_reward=snapshot.estimated_risk_reward,
        outcome=TradeOutcome.SKIPPED,
        realized_r=None,
        reason="Synthetic sensitivity record.",
        decision_diagnostics=_diagnostics(score),
        execution_readiness=snapshot,
    )


def test_threshold_fifty_is_more_directionally_eligible_than_seventy() -> None:
    records = [_record(52, _snapshot()), _record(72, _snapshot())]

    results = calculate_threshold_sensitivity(records)
    threshold_50 = next(result for result in results if result.threshold == 50)
    threshold_70 = next(result for result in results if result.threshold == 70)

    assert threshold_50.directionally_eligible == 2
    assert threshold_70.directionally_eligible == 1


def test_sensitivity_does_not_change_production_decision_action() -> None:
    record = _record(60, _snapshot())

    calculate_threshold_sensitivity([record])

    assert record.action == "wait"
    assert record.outcome is TradeOutcome.SKIPPED


def test_execution_readiness_requires_setup_levels_risk_and_strategy() -> None:
    records = [
        _record(60, _snapshot()),
        _record(60, _snapshot(setup_status="no_setup")),
        _record(60, _snapshot(target=None)),
        _record(60, _snapshot(risk_reward=1.4)),
        _record(60, _snapshot(setup_status="developing", plan_status="waiting")),
        _record(60, _snapshot(strategy="no_strategy", alignment="no_clear_strategy")),
    ]

    result = next(
        item for item in calculate_threshold_sensitivity(records)
        if item.threshold == 50
    )

    assert result.directionally_eligible == 6
    assert result.execution_ready == 1
    assert result.estimated_trade_candidates == 1
    assert result.missing_setup == 1
    assert result.missing_levels == 1
    assert result.risk_reward_failed == 1
    assert result.setup_not_confirmed == 1
    assert result.strategy_not_aligned == 1


def test_recommendation_warns_when_lower_threshold_adds_no_executable_trades() -> None:
    sensitivity = (
        ThresholdSensitivityResult(50, 20, 0, 0, 12, 8, 0, 0, 0, 0, "Low."),
        ThresholdSensitivityResult(70, 2, 0, 0, 2, 0, 0, 0, 18, 0, "Production."),
    )

    recommendation = _threshold_sensitivity_recommendation(sensitivity)

    assert recommendation is not None
    assert "no executable trade candidates" in recommendation.message
    assert "does not justify lowering" in recommendation.suggested_action
