from fastapi.testclient import TestClient

from app.main import app, get_market_data_provider
from core.backtesting import BacktestTrade
from core.calibration import CalibrationRequest
from core.journal import TradeOutcome
from core.market_data import Candle
from core.market_structure import MarketStructureResult, StructureEvent
from core.multi_timeframe import MultiTimeframeResult, TimeframeAlignment
from core.regime import (
    MarketRegime,
    MarketRegimeEngine,
    RegimeClassifierMode,
    RegimeResult,
    TunedMarketRegimeEngine,
)
from core.regime_lab import build_regime_classifier_comparison


def _candles(direction: int = 1, count: int = 20) -> list[Candle]:
    candles: list[Candle] = []
    close = 100.0
    for index in range(count):
        close += direction * 0.15
        candles.append(Candle(index, close, close + 0.3, close - 0.3, close, 100))
    return candles


def _structure(
    trend: str,
    *,
    phase: str = "unclear",
    event_type: str | None = None,
    event_index: int = 2,
) -> MarketStructureResult:
    event = (
        StructureEvent(
            index=event_index,
            timestamp=event_index,
            type=event_type,
            price=100.0,
            description="Synthetic event.",
        )
        if event_type else None
    )
    return MarketStructureResult(
        trend=trend,
        phase=phase,
        latest_swing_high=None,
        latest_swing_low=None,
        structure_events=[event_type] if event_type else [],
        liquidity_sweep_detected=False,
        confidence_modifier=0.0,
        human_readable_summary="Synthetic directional structure.",
        events=(event,) if event else (),
    )


def _multi(
    trend: str,
    alignment: TimeframeAlignment = TimeframeAlignment.UNCLEAR,
) -> MultiTimeframeResult:
    return MultiTimeframeResult(
        higher_timeframe="1h",
        current_timeframe="5m",
        higher_timeframe_trend=trend,
        current_timeframe_trend=trend,
        higher_timeframe_phase="impulse",
        current_timeframe_phase="unclear",
        alignment=alignment,
        alignment_score=95 if alignment.value.startswith("aligned") else 30,
        directional_bias=trend if trend in {"bullish", "bearish"} else "unclear",
        reasons=(),
        human_readable_summary="Synthetic alignment.",
    )


def test_default_classifier_mode_remains_legacy() -> None:
    request = CalibrationRequest(
        symbols=["BTC-USD"],
        timeframes=["5m"],
        higher_timeframes=["1h"],
    )

    assert request.regime_classifier_mode is RegimeClassifierMode.LEGACY


def test_tuned_mode_reduces_transition_for_directional_stale_choch() -> None:
    candles = _candles(direction=-1)
    structure = _structure(
        "bearish", phase="reversal_attempt", event_type="bearish_choch", event_index=2
    )
    multi = _multi("bearish", TimeframeAlignment.ALIGNED_BEARISH)

    legacy = MarketRegimeEngine().classify(
        candles=candles, market_structure=structure, multi_timeframe=multi
    )
    tuned = TunedMarketRegimeEngine().classify(
        candles=candles, market_structure=structure, multi_timeframe=multi
    )

    assert legacy.market_regime is MarketRegime.TRANSITION
    assert tuned.market_regime is MarketRegime.STRONG_BEAR_TREND
    assert any("No recent CHOCH" in reason for reason in tuned.regime_reasons)


def test_recent_bos_strengthens_tuned_trend_classification() -> None:
    candles = _candles(direction=0)
    without_bos = TunedMarketRegimeEngine().classify(
        candles=candles,
        market_structure=_structure("bullish"),
        multi_timeframe=_multi("bullish"),
    )
    with_bos = TunedMarketRegimeEngine().classify(
        candles=candles,
        market_structure=_structure(
            "bullish", event_type="bullish_bos", event_index=19
        ),
        multi_timeframe=_multi("bullish"),
    )

    assert without_bos.market_regime is MarketRegime.WEAK_BULL_TREND
    assert with_bos.market_regime is MarketRegime.STRONG_BULL_TREND
    assert with_bos.regime_confidence > without_bos.regime_confidence


def test_higher_timeframe_alignment_supports_tuned_trend() -> None:
    candles = _candles(direction=0)
    unclear = TunedMarketRegimeEngine().classify(
        candles=candles,
        market_structure=_structure("bearish"),
        multi_timeframe=_multi("bearish"),
    )
    aligned = TunedMarketRegimeEngine().classify(
        candles=candles,
        market_structure=_structure("bearish"),
        multi_timeframe=_multi("bearish", TimeframeAlignment.ALIGNED_BEARISH),
    )

    assert unclear.market_regime is MarketRegime.WEAK_BEAR_TREND
    assert aligned.market_regime is MarketRegime.STRONG_BEAR_TREND
    assert aligned.regime_confidence > unclear.regime_confidence


def test_tuned_classifier_preserves_range_compression_expansion_and_recent_transition() -> None:
    def variable_ranges(recent_width: float) -> list[Candle]:
        return [
            Candle(
                index,
                100.0,
                100.0 + (recent_width if index >= 16 else 1.0) / 2,
                100.0 - (recent_width if index >= 16 else 1.0) / 2,
                100.0,
                100,
            )
            for index in range(20)
        ]

    engine = TunedMarketRegimeEngine()
    ranging = engine.classify(
        candles=_candles(direction=0),
        market_structure=_structure("ranging", phase="range"),
        multi_timeframe=_multi("ranging", TimeframeAlignment.MIXED),
    )
    compression = engine.classify(
        candles=variable_ranges(0.2),
        market_structure=_structure("ranging", phase="range"),
        multi_timeframe=_multi("ranging", TimeframeAlignment.MIXED),
    )
    expansion = engine.classify(
        candles=variable_ranges(2.0),
        market_structure=_structure("bullish", phase="impulse"),
        multi_timeframe=_multi("bullish", TimeframeAlignment.ALIGNED_BULLISH),
    )
    transition = engine.classify(
        candles=_candles(direction=0),
        market_structure=_structure(
            "bullish",
            phase="reversal_attempt",
            event_type="bearish_choch",
            event_index=19,
        ),
        multi_timeframe=_multi("bullish"),
    )

    assert ranging.market_regime is MarketRegime.RANGE
    assert compression.market_regime is MarketRegime.COMPRESSION
    assert expansion.market_regime is MarketRegime.EXPANSION
    assert transition.market_regime is MarketRegime.TRANSITION


class _Provider:
    def get_candles(self, symbol: str, timeframe: str, lookback: int) -> list[Candle]:
        del symbol, timeframe
        return _candles(count=60)[-lookback:]


def _calibration_payload(mode: str) -> dict[str, object]:
    return {
        "symbols": ["BTC-USD"],
        "timeframes": ["5m"],
        "higher_timeframes": ["1h"],
        "lookback": 50,
        "max_trades_per_run": 5,
        "regime_classifier_mode": mode,
    }


def test_compare_mode_returns_both_summaries_and_comparison() -> None:
    app.dependency_overrides[get_market_data_provider] = lambda: _Provider()
    try:
        response = TestClient(app).post(
            "/calibrate", json=_calibration_payload("compare")
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["legacy_market_regime_summary"] is not None
    assert payload["tuned_market_regime_summary"] is not None
    comparison = payload["regime_classifier_comparison"]
    assert comparison is not None
    assert comparison["legacy_transition_ratio"] >= comparison["tuned_transition_ratio"]
    assert "Trade outcomes" in comparison["human_readable_summary"]


def test_trade_metrics_are_identical_between_legacy_and_tuned_modes() -> None:
    app.dependency_overrides[get_market_data_provider] = lambda: _Provider()
    try:
        client = TestClient(app)
        legacy = client.post("/calibrate", json=_calibration_payload("legacy"))
        tuned = client.post("/calibrate", json=_calibration_payload("tuned"))
    finally:
        app.dependency_overrides.clear()

    assert legacy.status_code == 200
    assert tuned.status_code == 200
    assert legacy.json()["aggregate_metrics"] == tuned.json()["aggregate_metrics"]
    assert legacy.json()["aggregate_skip_diagnostics"] == tuned.json()["aggregate_skip_diagnostics"]


def test_comparison_counts_transition_to_trend_without_changing_trade_result() -> None:
    legacy = RegimeResult(
        MarketRegime.TRANSITION, 88.0, ("Legacy transition.",), "Legacy transition."
    )
    tuned = RegimeResult(
        MarketRegime.STRONG_BEAR_TREND,
        82.0,
        ("Tuned bearish trend.",),
        "Tuned bearish trend.",
    )
    trade = BacktestTrade(
        timestamp=1,
        symbol="BTC-USD",
        action="sell",
        setup_type="bearish_bos_retest",
        strategy_type="trend_continuation",
        entry=100.0,
        stop_loss=101.0,
        target=98.0,
        estimated_risk_reward=2.0,
        outcome=TradeOutcome.WIN,
        realized_r=2.0,
        reason="Synthetic closed trade.",
        market_regime=legacy,
        tuned_market_regime=tuned,
    )

    legacy_summary, tuned_summary, comparison = build_regime_classifier_comparison(
        [trade]
    )

    assert comparison.legacy_transition_ratio == 1.0
    assert comparison.tuned_transition_ratio == 0.0
    assert comparison.changed_from_transition_to_trend == 1
    assert comparison.trend_count_increase == 1
    legacy_row = next(
        row for row in legacy_summary.regimes
        if row.market_regime is MarketRegime.TRANSITION
    )
    assert legacy_row.total_r == 2.0
    tuned_row = next(
        row for row in tuned_summary.regimes
        if row.market_regime is MarketRegime.STRONG_BEAR_TREND
    )
    assert tuned_row.total_r == 2.0
    assert trade.market_regime is legacy
