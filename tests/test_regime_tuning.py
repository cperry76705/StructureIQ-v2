from fastapi.testclient import TestClient

from app.main import app, get_market_data_provider
from core.backtesting import BacktestTrade
from core.journal import TradeOutcome
from core.market_data import Candle
from core.market_structure import MarketStructureResult, StructureEvent
from core.multi_timeframe import MultiTimeframeResult, TimeframeAlignment
from core.regime import MarketRegime, RegimeResult
from core.regime_tuning import (
    RegimeEvidenceScores,
    RegimeTuningEvidence,
    build_regime_tuning_evidence,
    build_regime_tuning_summary,
)
from core.regime_validation import build_forward_observation


def _evidence(
    regime: MarketRegime = MarketRegime.TRANSITION,
    *,
    trend: str = "bearish",
    confidence: float = 88.0,
    transition_score: float = 68.0,
    trend_score: float = 64.0,
    recent_bos: bool = False,
    recent_choch: bool = False,
) -> RegimeTuningEvidence:
    return RegimeTuningEvidence(
        production_regime=regime,
        confidence=confidence,
        trend=trend,
        phase="reversal_attempt" if regime is MarketRegime.TRANSITION else "impulse",
        alignment="aligned_bearish" if trend == "bearish" else "aligned_bullish",
        alignment_score=85,
        has_bos=True,
        recent_bos=recent_bos,
        has_choch=True,
        recent_choch=recent_choch,
        conflict=False,
        directional_swing_structure=trend in {"bullish", "bearish"},
        scores=RegimeEvidenceScores(
            trend_score=trend_score,
            range_score=10.0,
            transition_score=transition_score,
            compression_score=12.0,
            expansion_score=5.0,
        ),
        transition_reasons=("recent_choch" if recent_choch else "stale_choch",),
    )


def _record(index: int, evidence: RegimeTuningEvidence) -> BacktestTrade:
    future = [
        Candle(bar, 100 + bar * 0.1, 100.2 + bar * 0.1, 99.8 + bar * 0.1, 100 + bar * 0.1, 1)
        for bar in range(1, 21)
    ]
    return BacktestTrade(
        timestamp=index,
        symbol="EUR-USD",
        action="wait",
        setup_type="no_valid_setup",
        strategy_type="no_strategy",
        entry=None,
        stop_loss=None,
        target=None,
        estimated_risk_reward=None,
        outcome=TradeOutcome.SKIPPED,
        realized_r=None,
        reason="Synthetic tuning record.",
        market_regime=RegimeResult(
            evidence.production_regime,
            evidence.confidence,
            ("Synthetic classification.",),
            "Synthetic classification.",
        ),
        regime_forward_observation=build_forward_observation(
            start_price=100.0, future_candles=future
        ),
        regime_tuning_evidence=evidence,
    )


def test_tuning_evidence_identifies_stale_transition_with_trend_structure() -> None:
    candles = [Candle(i, 100, 101, 99, 100, 1) for i in range(20)]
    structure = MarketStructureResult(
        trend="bearish",
        phase="reversal_attempt",
        latest_swing_high=None,
        latest_swing_low=None,
        structure_events=["bearish_bos", "bearish_choch"],
        liquidity_sweep_detected=False,
        confidence_modifier=0.0,
        human_readable_summary="Synthetic bearish transition.",
        events=(
            StructureEvent(3, 3, "bearish_bos", 99, "Old BOS."),
            StructureEvent(4, 4, "bearish_choch", 100, "Old CHOCH."),
        ),
    )
    multi = MultiTimeframeResult(
        higher_timeframe="1h",
        current_timeframe="5m",
        higher_timeframe_trend="bearish",
        current_timeframe_trend="bearish",
        higher_timeframe_phase="impulse",
        current_timeframe_phase="reversal_attempt",
        alignment=TimeframeAlignment.ALIGNED_BEARISH,
        alignment_score=90,
        directional_bias="bearish",
        reasons=(),
        human_readable_summary="Aligned bearish.",
    )
    regime = RegimeResult(
        MarketRegime.TRANSITION, 88, ("CHOCH exists.",), "Transition."
    )

    evidence = build_regime_tuning_evidence(
        candles=candles,
        market_structure=structure,
        multi_timeframe=multi,
        production_regime=regime,
    )

    assert evidence.has_bos and evidence.has_choch
    assert not evidence.recent_bos and not evidence.recent_choch
    assert evidence.directional_swing_structure is True
    assert "stale_choch" in evidence.transition_reasons


def test_summary_reports_dominance_margins_and_counterfactuals() -> None:
    records = [
        *[_record(index, _evidence()) for index in range(8)],
        _record(8, _evidence(MarketRegime.STRONG_BEAR_TREND, transition_score=20)),
        _record(9, _evidence(MarketRegime.RANGE, trend="ranging", transition_score=15, trend_score=10)),
    ]

    summary = build_regime_tuning_summary(records)

    assert summary.current_regime_distribution["transition"] == 8
    assert summary.current_regime_distribution["strong_bull_trend"] == 0
    assert summary.transition_dominance_ratio == 0.8
    assert summary.transition_overuse_score == 0.5
    assert summary.transition_without_recent_bos == 8
    assert summary.transition_without_recent_choch == 8
    assert summary.transition_with_trend_structure == 8
    assert summary.second_best_regime == "weak_bear_trend"
    assert summary.score_margin_between_winner_and_runner_up == 7.9
    assert [item.threshold for item in summary.transition_threshold_simulation] == [60, 65, 70, 75, 80]
    assert {item.simulation_name for item in summary.trend_evidence_simulation} == {
        "stronger_bos_weight",
        "stronger_choch_weight",
        "stronger_swing_structure_weight",
        "stronger_higher_timeframe_alignment_weight",
    }
    assert [item.horizon for item in summary.forward_stability] == [5, 10, 20]
    assert sum(summary.confidence_histogram.values()) == 10


def test_threshold_and_trend_simulations_do_not_mutate_production_labels() -> None:
    evidence = _evidence(transition_score=68, trend_score=64)
    records = [_record(index, evidence) for index in range(4)]
    before = [record.market_regime.market_regime for record in records]

    summary = build_regime_tuning_summary(records)

    assert summary.transition_threshold_simulation[0].transition_records == 4
    assert summary.transition_threshold_simulation[-1].transition_records == 0
    swing = next(
        item for item in summary.trend_evidence_simulation
        if item.simulation_name == "stronger_swing_structure_weight"
    )
    assert swing.expected_trend_classifications == 4
    assert [record.market_regime.market_regime for record in records] == before


class _Provider:
    def get_candles(self, symbol: str, timeframe: str, lookback: int) -> list[Candle]:
        del symbol, timeframe
        return [Candle(i, 100, 101, 99, 100, 1) for i in range(60)][-lookback:]


def test_calibration_flag_returns_tuning_summary_and_analysis_stays_clean() -> None:
    app.dependency_overrides[get_market_data_provider] = lambda: _Provider()
    try:
        client = TestClient(app)
        calibration = client.post(
            "/calibrate",
            json={
                "symbols": ["EUR-USD"],
                "timeframes": ["5m"],
                "higher_timeframes": ["1h"],
                "lookback": 60,
                "max_trades_per_run": 2,
                "regime_tuning_analysis": True,
            },
        )
        analysis = client.post(
            "/analysis",
            json={
                "symbol": "EUR-USD",
                "timeframe": "5m",
                "higher_timeframe": "1h",
                "lookback": 60,
            },
        )
        backtest = client.post(
            "/backtest",
            json={
                "symbol": "EUR-USD",
                "timeframe": "5m",
                "higher_timeframe": "1h",
                "lookback": 60,
                "max_trades": 1,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert calibration.status_code == 200
    tuning = calibration.json()["regime_tuning_summary"]
    assert tuning["total_records"] == 2
    assert len(tuning["transition_threshold_simulation"]) == 5
    assert analysis.status_code == 200
    assert "regime_tuning_evidence" not in analysis.json()
    assert backtest.status_code == 200
    assert "regime_tuning_evidence" not in backtest.json()["trades"][0]


def test_calibration_does_not_run_tuning_when_not_requested() -> None:
    app.dependency_overrides[get_market_data_provider] = lambda: _Provider()
    try:
        response = TestClient(app).post(
            "/calibrate",
            json={
                "symbols": ["EUR-USD"],
                "timeframes": ["5m"],
                "higher_timeframes": ["1h"],
                "lookback": 60,
                "max_trades_per_run": 1,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["regime_tuning_summary"] is None
