from core.backtesting import BacktestTrade, TradeOutcomeDiagnostics
from core.journal import TradeOutcome
from core.market_data import Candle
from core.market_structure import MarketStructureResult
from core.multi_timeframe import MultiTimeframeResult, TimeframeAlignment
from core.regime import MarketRegime, MarketRegimeEngine, RegimeResult
from core.regime_lab import build_market_regime_analysis
from core.structure import SwingPoint


def _candles(
    *,
    direction: int = 1,
    baseline_range: float = 0.4,
    recent_range: float | None = None,
) -> list[Candle]:
    candles: list[Candle] = []
    close = 100.0
    for index in range(20):
        close += direction * 0.2
        width = recent_range if recent_range is not None and index >= 16 else baseline_range
        candles.append(
            Candle(index, close - direction * 0.05, close + width / 2, close - width / 2, close, 100)
        )
    return candles


def _structure(trend: str, phase: str, events: list[str] | None = None):
    return MarketStructureResult(
        trend=trend,
        phase=phase,
        latest_swing_high=SwingPoint(10, 105.0, "high"),
        latest_swing_low=SwingPoint(9, 95.0, "low"),
        structure_events=events or [],
        liquidity_sweep_detected=False,
        confidence_modifier=1.0,
        human_readable_summary="Synthetic structure.",
    )


def _multi(trend: str, alignment: TimeframeAlignment):
    return MultiTimeframeResult(
        higher_timeframe="1h",
        current_timeframe="5m",
        higher_timeframe_trend=trend,
        current_timeframe_trend=trend,
        higher_timeframe_phase="impulse",
        current_timeframe_phase="impulse",
        alignment=alignment,
        alignment_score=95 if alignment.value.startswith("aligned") else 50,
        directional_bias=trend if trend in {"bullish", "bearish"} else "neutral",
        reasons=("Synthetic.",),
        human_readable_summary="Synthetic multi-timeframe context.",
    )


def test_strong_bull_and_bear_classification() -> None:
    engine = MarketRegimeEngine()
    bull = engine.classify(
        candles=_candles(direction=1),
        market_structure=_structure("bullish", "impulse", ["bullish_bos"]),
        multi_timeframe=_multi("bullish", TimeframeAlignment.ALIGNED_BULLISH),
    )
    bear = engine.classify(
        candles=_candles(direction=-1),
        market_structure=_structure("bearish", "impulse", ["bearish_bos"]),
        multi_timeframe=_multi("bearish", TimeframeAlignment.ALIGNED_BEARISH),
    )

    assert bull.market_regime is MarketRegime.STRONG_BULL_TREND
    assert bear.market_regime is MarketRegime.STRONG_BEAR_TREND
    assert bull.regime_confidence >= 80
    assert bull.regime_reasons


def test_range_compression_and_expansion_classification() -> None:
    engine = MarketRegimeEngine()
    ranging = engine.classify(
        candles=_candles(direction=0),
        market_structure=_structure("ranging", "range"),
        multi_timeframe=_multi("ranging", TimeframeAlignment.MIXED),
    )
    compression = engine.classify(
        candles=_candles(direction=0, baseline_range=2.0, recent_range=0.3),
        market_structure=_structure("ranging", "range"),
        multi_timeframe=_multi("ranging", TimeframeAlignment.MIXED),
    )
    expansion = engine.classify(
        candles=_candles(direction=1, baseline_range=0.4, recent_range=1.2),
        market_structure=_structure("bullish", "impulse"),
        multi_timeframe=_multi("bullish", TimeframeAlignment.ALIGNED_BULLISH),
    )

    assert ranging.market_regime is MarketRegime.RANGE
    assert compression.market_regime is MarketRegime.COMPRESSION
    assert expansion.market_regime is MarketRegime.EXPANSION


def test_choch_and_conflict_classify_transition() -> None:
    result = MarketRegimeEngine().classify(
        candles=_candles(),
        market_structure=_structure("bullish", "reversal_attempt", ["bearish_choch"]),
        multi_timeframe=_multi("bullish", TimeframeAlignment.CONFLICTING),
    )

    assert result.market_regime is MarketRegime.TRANSITION
    assert result.regime_confidence == 88.0
    assert "transition" in result.human_readable_summary


def _diagnostics(outcome: TradeOutcome, realized: float) -> TradeOutcomeDiagnostics:
    return TradeOutcomeDiagnostics(
        outcome=outcome,
        realized_r=realized,
        entry_price=100.0,
        stop_loss=98.0,
        target=104.0,
        first_touch="target" if outcome is TradeOutcome.WIN else "stop",
        bars_to_outcome=3,
        max_favorable_excursion_r=2.0 if outcome is TradeOutcome.WIN else 0.4,
        max_adverse_excursion_r=0.3 if outcome is TradeOutcome.WIN else 1.0,
        direction_was_correct_initially=outcome is TradeOutcome.WIN,
        loss_reason=None,
        human_readable_summary="Synthetic outcome.",
    )


def _trade(
    regime: MarketRegime,
    outcome: TradeOutcome,
    realized: float,
    *,
    strategy: str,
    setup: str,
) -> BacktestTrade:
    return BacktestTrade(
        timestamp=1,
        symbol="BTC-USD",
        action="sell",
        setup_type=setup,
        strategy_type=strategy,
        entry=100.0,
        stop_loss=102.0,
        target=96.0,
        estimated_risk_reward=2.0,
        outcome=outcome,
        realized_r=realized,
        reason="Synthetic regime trade.",
        outcome_diagnostics=_diagnostics(outcome, realized),
        market_regime=RegimeResult(
            market_regime=regime,
            regime_confidence=80.0,
            regime_reasons=("Synthetic regime.",),
            human_readable_summary="Synthetic regime.",
        ),
    )


def test_regime_summary_and_strategy_setup_matrices() -> None:
    trades = [
        _trade(MarketRegime.RANGE, TradeOutcome.WIN, 2.0, strategy="range_reversal", setup="range_reversal_short"),
        _trade(MarketRegime.RANGE, TradeOutcome.LOSS, -1.0, strategy="range_reversal", setup="range_reversal_short"),
        _trade(MarketRegime.STRONG_BEAR_TREND, TradeOutcome.LOSS, -1.0, strategy="breakout_continuation", setup="bearish_bos_retest"),
        _trade(MarketRegime.STRONG_BEAR_TREND, TradeOutcome.LOSS, -1.0, strategy="breakout_continuation", setup="bearish_bos_retest"),
    ]

    summary, strategy_matrix, setup_matrix = build_market_regime_analysis(trades)
    range_result = next(item for item in summary.regimes if item.market_regime is MarketRegime.RANGE)

    assert len(summary.regimes) == len(MarketRegime)
    assert range_result.records_seen == 2
    assert range_result.executed_trades == 2
    assert range_result.average_r == 0.5
    assert range_result.average_trade_duration == 3.0
    assert range_result.average_mfe == 1.2
    assert summary.highest_expectancy_regime == "range"
    assert summary.worst_regime == "strong_bear_trend"
    assert any(row.strategy_type == "range_reversal" for row in strategy_matrix)
    assert any(row.setup_type == "bearish_bos_retest" for row in setup_matrix)
    assert any("underperforms" in message for message in summary.recommendations)
