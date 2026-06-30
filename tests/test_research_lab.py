from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app, get_market_data_provider
from core.backtesting import BacktestTrade, TradeOutcomeDiagnostics
from core.decision_engine import DecisionDiagnostics
from core.journal import TradeOutcome
from core.market_data import Candle
from core.regime import MarketRegime, RegimeResult
from core.research_lab import build_research_lab, calculate_research_performance


def _diagnostics(confidence: float) -> DecisionDiagnostics:
    return DecisionDiagnostics(
        raw_score=confidence,
        final_confidence=confidence,
        intended_direction="bearish",
        confidence_band="tradable",
        blocked_by=(),
        gate_results=(),
        human_readable_summary="Synthetic decision diagnostics.",
    )


def _trade(
    *,
    symbol: str,
    timeframe: str,
    setup: str,
    strategy: str,
    regime: MarketRegime,
    outcome: TradeOutcome,
    realized_r: float,
    confidence: float,
    bars: int,
    hour: int,
) -> BacktestTrade:
    timestamp = int(datetime(2026, 6, 29, hour, tzinfo=timezone.utc).timestamp())
    return BacktestTrade(
        timestamp=timestamp,
        symbol=symbol,
        timeframe=timeframe,
        higher_timeframe="1h",
        action="sell",
        setup_type=setup,
        strategy_type=strategy,
        entry=100.0,
        stop_loss=101.0,
        target=98.0,
        estimated_risk_reward=2.0,
        outcome=outcome,
        realized_r=realized_r,
        reason="Synthetic research trade.",
        decision_diagnostics=_diagnostics(confidence),
        market_regime=RegimeResult(
            regime,
            80.0,
            ("Synthetic regime.",),
            "Synthetic regime.",
        ),
        outcome_diagnostics=TradeOutcomeDiagnostics(
            outcome=outcome,
            realized_r=realized_r,
            entry_price=100.0,
            stop_loss=101.0,
            target=98.0,
            first_touch="target" if outcome is TradeOutcome.WIN else "stop",
            bars_to_outcome=bars,
            max_favorable_excursion_r=2.2 if outcome is TradeOutcome.WIN else 0.4,
            max_adverse_excursion_r=0.3 if outcome is TradeOutcome.WIN else 1.0,
            direction_was_correct_initially=outcome is TradeOutcome.WIN,
            loss_reason=None,
            human_readable_summary="Synthetic outcome.",
        ),
    )


def _trades() -> list[BacktestTrade]:
    return [
        _trade(
            symbol="BTC-USD",
            timeframe="5m",
            setup="liquidity_sweep_reversal_short",
            strategy="liquidity_sweep_reversal",
            regime=MarketRegime.STRONG_BEAR_TREND,
            outcome=TradeOutcome.WIN,
            realized_r=2.0,
            confidence=82.0,
            bars=1,
            hour=14,
        ),
        _trade(
            symbol="BTC-USD",
            timeframe="5m",
            setup="liquidity_sweep_reversal_short",
            strategy="liquidity_sweep_reversal",
            regime=MarketRegime.STRONG_BEAR_TREND,
            outcome=TradeOutcome.WIN,
            realized_r=2.0,
            confidence=84.0,
            bars=4,
            hour=14,
        ),
        _trade(
            symbol="BTC-USD",
            timeframe="5m",
            setup="liquidity_sweep_reversal_short",
            strategy="liquidity_sweep_reversal",
            regime=MarketRegime.STRONG_BEAR_TREND,
            outcome=TradeOutcome.LOSS,
            realized_r=-1.0,
            confidence=80.0,
            bars=8,
            hour=15,
        ),
        _trade(
            symbol="EUR-USD",
            timeframe="15m",
            setup="bearish_bos_retest",
            strategy="breakout_continuation",
            regime=MarketRegime.RANGE,
            outcome=TradeOutcome.LOSS,
            realized_r=-1.0,
            confidence=72.0,
            bars=12,
            hour=10,
        ),
    ]


def test_statistical_performance_calculates_metrics_and_confidence_interval() -> None:
    performance = calculate_research_performance("BTC", _trades()[:3])

    assert performance.records_seen == 3
    assert performance.executed_trades == 3
    assert performance.wins == 2
    assert performance.losses == 1
    assert performance.win_rate == 66.67
    assert performance.average_r == 1.0
    assert performance.total_r == 3.0
    assert performance.expectancy == 1.0
    assert performance.profit_factor == 4.0
    assert performance.average_mfe > performance.average_mae
    assert performance.average_trade_duration == 4.333
    assert performance.average_confidence == 82.0
    assert performance.confidence_interval.sample_size == 3
    assert performance.confidence_interval.lower < performance.average_r
    assert performance.confidence_interval.upper > performance.average_r
    assert performance.sample_quality == "insufficient"


def test_research_lab_builds_dimensions_matrices_rankings_and_summary() -> None:
    result = build_research_lab(
        _trades(),
        management_results=(),
        entry_timing_summary=None,
        execution_sensitivity_summary=None,
    )
    summary = result.research_lab_summary
    btc = next(item for item in summary.symbol_performance if item.category == "BTC")
    eth = next(item for item in summary.symbol_performance if item.category == "ETH")
    bucket = next(
        item for item in summary.confidence_bucket_performance
        if item.confidence_bucket == "80-89"
    )

    assert btc.executed_trades == 3
    assert eth.records_seen == 0
    assert any(item.category == "3m" for item in summary.timeframe_performance)
    assert bucket.trades == 3
    assert bucket.average_r == 1.0
    assert summary.time_of_day_performance[14].executed_trades == 2
    assert summary.day_of_week_performance[0].executed_trades == 4
    assert any(item.category == "3-5" for item in summary.trade_duration_performance)
    assert result.performance_matrices.regime_strategy
    assert result.performance_matrices.setup_regime
    assert result.performance_matrices.symbol_setup
    assert result.performance_matrices.timeframe_setup
    assert result.research_rankings.top_10_strongest_combinations
    assert result.research_rankings.top_10_weakest_combinations
    assert "research laboratory analyzed" in summary.executive_summary.lower()
    assert "Do not change production rules" in summary.what_should_not_change


class _Provider:
    def get_candles(self, symbol: str, timeframe: str, lookback: int) -> list[Candle]:
        del symbol, timeframe
        candles = [
            Candle(index, 100, 101, 99, 100, 100)
            for index in range(70)
        ]
        return candles[-lookback:]


def test_calibration_always_includes_research_lab_without_changing_metrics() -> None:
    request = {
        "symbols": ["BTC-USD"],
        "timeframes": ["5m"],
        "higher_timeframes": ["1h"],
        "lookback": 60,
        "max_trades_per_run": 5,
    }
    app.dependency_overrides[get_market_data_provider] = lambda: _Provider()
    try:
        client = TestClient(app)
        first = client.post("/calibrate", json=request)
        second = client.post("/calibrate", json=request)
    finally:
        app.dependency_overrides.clear()

    assert first.status_code == second.status_code == 200
    payload = first.json()
    assert payload["research_lab_summary"] is not None
    assert payload["research_rankings"] is not None
    assert payload["performance_matrices"] is not None
    assert payload["research_statistics"] is not None
    assert payload["research_recommendations"]
    assert payload["aggregate_metrics"] == second.json()["aggregate_metrics"]
    assert payload["aggregate_skip_diagnostics"] == second.json()["aggregate_skip_diagnostics"]
    assert payload["research_lab_summary"] == second.json()["research_lab_summary"]
