from typing import Callable

import pytest
from pydantic import ValidationError

from core.backtesting import (
    BacktestRequest,
    BacktestResult,
    BacktestTrade,
    calculate_backtest_metrics,
)
from core.calibration import CalibrationEngine, CalibrationRequest
from core.decision_engine import DecisionDiagnostics, GateResult
from core.journal import TradeOutcome
from core.market_data import Candle


def _trade(
    outcome: TradeOutcome,
    realized_r: float | None,
    *,
    setup: str = "bullish_pullback_continuation",
    strategy: str = "pullback_continuation",
    skip_reason_code: str | None = None,
    blocking_engine: str | None = None,
    decision_diagnostics: DecisionDiagnostics | None = None,
) -> BacktestTrade:
    return BacktestTrade(
        timestamp=1,
        symbol="BTC-USD",
        action="buy",
        setup_type=setup,
        strategy_type=strategy,
        entry=100.0,
        stop_loss=98.0,
        target=104.0,
        estimated_risk_reward=2.0,
        outcome=outcome,
        realized_r=realized_r,
        reason="Synthetic calibration trade.",
        skip_reason_code=skip_reason_code,
        blocking_engine=blocking_engine,
        actionability_status="waiting"
        if outcome is TradeOutcome.SKIPPED
        else "actionable",
        decision_diagnostics=decision_diagnostics,
    )


def _result(request: BacktestRequest, trades: list[BacktestTrade]) -> BacktestResult:
    return BacktestResult(
        request=request,
        trades=tuple(trades),
        metrics=calculate_backtest_metrics(trades),
        human_readable_summary="Synthetic backtest.",
        limitations=("Synthetic limitation.",),
    )


class _Runner:
    def __init__(
        self,
        resolver: Callable[[BacktestRequest], list[BacktestTrade]],
    ) -> None:
        self.resolver = resolver
        self.requests: list[BacktestRequest] = []

    def run(self, request: BacktestRequest) -> BacktestResult:
        self.requests.append(request)
        return _result(request, self.resolver(request))


class _UnusedProvider:
    def get_candles(
        self, symbol: str, timeframe: str, lookback: int
    ) -> list[Candle]:
        del symbol, timeframe, lookback
        return []


def _engine(runner: _Runner) -> CalibrationEngine:
    return CalibrationEngine(
        market_data=_UnusedProvider(),
        backtesting_engine_factory=lambda provider: runner,
    )


def _request(**overrides) -> CalibrationRequest:
    values = {
        "symbols": ["BTC-USD"],
        "timeframes": ["5m"],
        "higher_timeframes": ["1h"],
        "lookback": 100,
        "max_trades_per_run": 10,
        "risk_per_trade_percent": 1.0,
        "starting_balance": 10000,
    }
    values.update(overrides)
    return CalibrationRequest(**values)


def test_calibration_request_validates() -> None:
    with pytest.raises(ValidationError):
        CalibrationRequest(
            symbols=[],
            timeframes=[],
            higher_timeframes=[],
            lookback=10,
            max_trades_per_run=0,
            risk_per_trade_percent=0,
            starting_balance=0,
        )


def test_calibration_runs_multiple_symbol_timeframe_combinations() -> None:
    runner = _Runner(lambda request: [_trade(TradeOutcome.SKIPPED, None)])
    result = _engine(runner).run(
        _request(
            symbols=["BTC-USD", "EUR-USD"],
            timeframes=["5m", "15m"],
            higher_timeframes=["1h", "4h"],
        )
    )

    assert len(result.runs) == 8
    assert len(runner.requests) == 8
    assert any(run.normalized_symbol == "EURUSD=X" for run in result.runs)


def test_aggregate_metrics_calculate_totals() -> None:
    runner = _Runner(
        lambda request: [
            _trade(TradeOutcome.WIN, 2.0),
            _trade(TradeOutcome.LOSS, -1.0),
            _trade(TradeOutcome.SKIPPED, None),
        ]
    )
    result = _engine(runner).run(_request())

    assert result.aggregate_metrics.total_runs == 1
    assert result.aggregate_metrics.total_trades == 2
    assert result.aggregate_metrics.total_skipped == 1
    assert result.aggregate_metrics.total_r == 1.0


def test_calibration_aggregates_skip_diagnostics_across_runs() -> None:
    runner = _Runner(
        lambda request: [
            _trade(
                TradeOutcome.SKIPPED,
                None,
                skip_reason_code="decision_not_actionable",
                blocking_engine="decision_engine",
            )
        ]
    )
    result = _engine(runner).run(
        _request(symbols=["BTC-USD", "ETH-USD"])
    )

    assert result.aggregate_skip_diagnostics.total_skipped == 2
    assert result.aggregate_skip_diagnostics.by_reason_code == {
        "decision_not_actionable": 2
    }
    assert result.aggregate_skip_diagnostics.by_blocking_engine == {
        "decision_engine": 2
    }
    assert any(
        "dominant skip reason" in recommendation.message.lower()
        for recommendation in result.recommendations
    )


def test_calibration_aggregates_blocked_decision_gates_across_runs() -> None:
    diagnostics = DecisionDiagnostics(
        raw_score=61.0,
        final_confidence=61.0,
        intended_direction="bullish",
        confidence_band="wait",
        blocked_by=("directional_confidence",),
        gate_results=(
            GateResult(
                "directional_confidence",
                False,
                True,
                61.0,
                ">= 70.0",
                -9.0,
                "Confidence is below the threshold.",
            ),
        ),
        human_readable_summary="Synthetic decision diagnostics.",
    )
    runner = _Runner(
        lambda request: [
            _trade(
                TradeOutcome.SKIPPED,
                None,
                skip_reason_code="decision_not_actionable",
                blocking_engine="decision_engine",
                decision_diagnostics=diagnostics,
            )
        ]
    )
    result = _engine(runner).run(
        _request(symbols=["BTC-USD", "ETH-USD"])
    )

    aggregate = result.aggregate_decision_diagnostics
    assert aggregate.by_blocked_gate == {"directional_confidence": 2}
    assert aggregate.most_common_blocked_gate == "directional_confidence"
    assert any(
        "directional confidence" in recommendation.message.lower()
        for recommendation in result.recommendations
    )


def test_skipped_heavy_results_produce_conservative_recommendation() -> None:
    runner = _Runner(lambda request: [_trade(TradeOutcome.SKIPPED, None)] * 5)
    result = _engine(runner).run(_request(symbols=["BTC-USD", "ETH-USD"]))

    assert any(
        recommendation.category in {"decision_threshold", "setup_quality"}
        and recommendation.severity in {"medium", "high"}
        for recommendation in result.recommendations
    )


def test_low_win_rate_produces_aggressive_recommendation() -> None:
    runner = _Runner(
        lambda request: [
            _trade(TradeOutcome.WIN, 1.0),
            *[_trade(TradeOutcome.LOSS, -1.0) for _ in range(4)],
        ]
    )
    result = _engine(runner).run(_request())

    assert any(
        recommendation.category == "decision_threshold"
        and "win rate" in recommendation.message
        for recommendation in result.recommendations
    )


def test_weak_setup_performance_is_reported() -> None:
    runner = _Runner(
        lambda request: [
            _trade(
                TradeOutcome.LOSS,
                -1.0,
                setup="range_reversal_long",
            )
        ]
    )
    result = _engine(runner).run(_request())

    performance = next(
        item for item in result.setup_performance
        if item.setup_type == "range_reversal_long"
    )
    assert performance.average_r == -1.0
    assert any(
        recommendation.category == "setup_quality"
        and "range_reversal_long" in recommendation.message
        for recommendation in result.recommendations
    )


def test_weak_strategy_performance_is_reported() -> None:
    runner = _Runner(
        lambda request: [
            _trade(
                TradeOutcome.LOSS,
                -1.0,
                strategy="range_reversal",
            )
        ]
    )
    result = _engine(runner).run(_request())

    performance = next(
        item for item in result.strategy_performance
        if item.strategy_type == "range_reversal"
    )
    assert performance.average_r == -1.0
    assert any(
        recommendation.category == "strategy_selection"
        and "range_reversal" in recommendation.message
        for recommendation in result.recommendations
    )


def test_recommendations_include_severity_and_suggested_action() -> None:
    runner = _Runner(lambda request: [_trade(TradeOutcome.SKIPPED, None)])
    result = _engine(runner).run(_request())

    assert result.recommendations
    assert all(item.severity in {"low", "medium", "high"} for item in result.recommendations)
    assert all(item.suggested_action for item in result.recommendations)
