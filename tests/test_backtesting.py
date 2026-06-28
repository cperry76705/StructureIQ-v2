from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from core.backtesting import (
    BacktestRequest,
    BacktestTrade,
    BacktestingEngine,
    calculate_backtest_metrics,
    simulate_trade_outcome,
)
from core.decision_engine import DecisionAction
from core.journal import TradeOutcome
from core.market_data import Candle
from core.setup_engine import SetupType
from core.strategy_engine import StrategyType


def _candles(count: int = 60) -> list[Candle]:
    return [
        Candle(index, 100.0, 101.0, 99.0, 100.0, 100.0)
        for index in range(count)
    ]


def _analysis(*, actionable: bool):
    plan = SimpleNamespace(
        status="actionable" if actionable else "waiting",
        entry_zone="100-101" if actionable else None,
        stop_loss="98" if actionable else None,
        target="105" if actionable else None,
        estimated_risk_reward=2.0 if actionable else None,
    )
    return SimpleNamespace(
        trader_analysis=SimpleNamespace(trade_plan=plan),
        decision=SimpleNamespace(
            action=DecisionAction.BUY if actionable else DecisionAction.WAIT
        ),
        setup_plan=SimpleNamespace(
            setup_type=SetupType.BULLISH_PULLBACK_CONTINUATION
        ),
        strategy=SimpleNamespace(
            preferred_strategy=StrategyType.PULLBACK_CONTINUATION
        ),
    )


class _Provider:
    def __init__(self, candles: list[Candle]) -> None:
        self.candles = candles

    def get_candles(self, symbol: str, timeframe: str, lookback: int) -> list[Candle]:
        del symbol, timeframe
        return self.candles[-lookback:]


class _StaticRunner:
    def __init__(self, analysis) -> None:
        self.analysis = analysis

    def analyze(self, request):
        del request
        return self.analysis


def _trade(
    outcome: TradeOutcome,
    realized_r: float | None,
) -> BacktestTrade:
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
        reason="Synthetic trade.",
    )


def test_backtest_request_validates() -> None:
    with pytest.raises(ValidationError):
        BacktestRequest(
            symbol="",
            timeframe="5m",
            higher_timeframe="1h",
            lookback=10,
            starting_balance=0,
            risk_per_trade_percent=0,
            max_trades=0,
        )


def test_non_actionable_setups_are_skipped() -> None:
    engine = BacktestingEngine(
        _Provider(_candles()),
        analysis_engine_factory=lambda provider: _StaticRunner(
            _analysis(actionable=False)
        ),
    )
    result = engine.run(
        BacktestRequest(
            symbol="BTC-USD",
            timeframe="5m",
            higher_timeframe="1h",
            lookback=60,
            max_trades=1,
        )
    )

    assert result.trades[0].outcome is TradeOutcome.SKIPPED


def test_trade_outcome_is_win_when_target_hits_first() -> None:
    outcome, realized_r, _ = simulate_trade_outcome(
        action="buy",
        entry=100.0,
        stop_loss=98.0,
        target=104.0,
        future_candles=[Candle(1, 100, 104, 99, 103, 100)],
        estimated_risk_reward=2.0,
    )

    assert outcome is TradeOutcome.WIN
    assert realized_r == 2.0


def test_trade_outcome_is_loss_when_stop_hits_first() -> None:
    outcome, realized_r, _ = simulate_trade_outcome(
        action="sell",
        entry=100.0,
        stop_loss=102.0,
        target=96.0,
        future_candles=[Candle(1, 100, 103, 97, 102, 100)],
    )

    assert outcome is TradeOutcome.LOSS
    assert realized_r == -1.0


def test_metrics_calculate_win_rate() -> None:
    metrics = calculate_backtest_metrics(
        [_trade(TradeOutcome.WIN, 2.0), _trade(TradeOutcome.LOSS, -1.0)]
    )

    assert metrics.win_rate == 50.0


def test_metrics_calculate_average_r() -> None:
    metrics = calculate_backtest_metrics(
        [_trade(TradeOutcome.WIN, 2.0), _trade(TradeOutcome.LOSS, -1.0)]
    )

    assert metrics.average_r == 0.5


def test_metrics_calculate_total_r() -> None:
    metrics = calculate_backtest_metrics(
        [_trade(TradeOutcome.WIN, 2.0), _trade(TradeOutcome.LOSS, -1.0)]
    )

    assert metrics.total_r == 1.0


def test_max_trades_cap_is_respected() -> None:
    engine = BacktestingEngine(
        _Provider(_candles()),
        analysis_engine_factory=lambda provider: _StaticRunner(
            _analysis(actionable=False)
        ),
    )
    result = engine.run(
        BacktestRequest(
            symbol="BTC-USD",
            timeframe="5m",
            higher_timeframe="1h",
            lookback=60,
            max_trades=2,
        )
    )

    assert len(result.trades) == 2


def test_backtest_returns_limitations() -> None:
    engine = BacktestingEngine(
        _Provider(_candles()),
        analysis_engine_factory=lambda provider: _StaticRunner(
            _analysis(actionable=False)
        ),
    )
    result = engine.run(
        BacktestRequest(
            symbol="BTC-USD",
            timeframe="5m",
            higher_timeframe="1h",
            lookback=60,
            max_trades=1,
        )
    )

    assert result.limitations
    assert any("simplified" in limitation for limitation in result.limitations)
