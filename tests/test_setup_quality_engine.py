from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app, get_market_data_provider
from core.journal import TradeOutcome
from core.market_data import Candle
from core.setup_quality_engine import SetupQualityEngine, grade_for_score


def _evidence(**overrides):
    values = dict(
        market_structure=SimpleNamespace(
            structure_events=("bearish_bos", "liquidity_sweep_high"),
            trend="bearish", phase="impulse", liquidity_sweep_detected=True,
            swing_highs=(1, 2, 3), swing_lows=(1, 2, 3),
        ),
        multi_timeframe=SimpleNamespace(
            alignment="aligned_bearish", alignment_score=90,
            directional_bias="bearish",
        ),
        setup_plan=SimpleNamespace(
            setup_type="liquidity_sweep_reversal_short", setup_status="confirmed",
            direction="bearish", estimated_risk_reward=2.2,
            entry_conditions=(SimpleNamespace(importance="required", is_met=True),),
            setup_level_diagnostics=SimpleNamespace(level_quality="complete"),
        ),
        market_regime=SimpleNamespace(market_regime="strong_bear_trend"),
        decision=SimpleNamespace(confidence=82),
        candles=tuple(Candle(i, 100-i, 101-i, 98-i, 99-i, 1000) for i in range(8)),
    )
    values.update(overrides)
    return values


def test_score_is_bounded_and_strong_evidence_scores_well() -> None:
    result = SetupQualityEngine().score(**_evidence())
    assert 0 <= result.score <= 100
    assert result.grade in {"A+", "A", "B+", "B"}
    assert sum(vars(result.components).values()) == result.score


def test_grade_mapping_boundaries() -> None:
    assert grade_for_score(95) == "A+"
    assert grade_for_score(90) == "A"
    assert grade_for_score(85) == "B+"
    assert grade_for_score(80) == "B"
    assert grade_for_score(75) == "C+"
    assert grade_for_score(70) == "C"
    assert grade_for_score(65) == "D"
    assert grade_for_score(64.99) == "F"


def test_missing_evidence_is_safe() -> None:
    result = SetupQualityEngine().score()
    assert 0 <= result.score <= 100
    assert result.human_readable_summary


def _trade(index: int, score: float, realized_r: float | None):
    quality = SetupQualityEngine().score(**_evidence())
    quality = quality.__class__(score, grade_for_score(score), quality.components, quality.human_readable_summary)
    return SimpleNamespace(
        symbol="EUR-USD", strategy_type="trend_continuation",
        setup_type="bearish_bos_retest",
        market_regime=SimpleNamespace(market_regime="strong_bear_trend"),
        setup_quality=quality, realized_r=realized_r,
        outcome=TradeOutcome.WIN if (realized_r or 0) > 0 else TradeOutcome.LOSS,
        outcome_diagnostics=SimpleNamespace(bars_to_outcome=index + 1),
        decision_diagnostics=SimpleNamespace(final_confidence=65 + index),
        score_summary=SimpleNamespace(trade_quality_score=score - 2),
    )


def test_calibration_summary_and_correlations_populate() -> None:
    trades = tuple(_trade(i, 65 + i * 3, (-1.0 if i % 3 == 0 else 2.0)) for i in range(12))
    summary = SetupQualityEngine().summarize(trades)
    assert summary.total_records == 12
    assert summary.completed_trades == 12
    assert summary.average_quality_by_symbol[0].name == "EUR-USD"
    assert summary.average_quality_by_setup[0].quality_rank == 1
    assert len(summary.correlations) == 7


class _Provider:
    provider_name = "quality-test"

    def get_candles(self, symbol, timeframe, lookback):
        del symbol, timeframe
        return [Candle(i, 100+i*.2, 101+i*.2, 99+i*.2, 100.4+i*.2, 1000) for i in range(max(lookback, 80))]


def test_analysis_and_calibration_include_quality_without_changing_action() -> None:
    app.dependency_overrides[get_market_data_provider] = lambda: _Provider()
    client = TestClient(app)
    request = {"symbol": "BTC-USD", "timeframe": "5m", "higher_timeframe": "1h", "lookback": 80}
    try:
        first = client.post("/analysis", json=request).json()
        second = client.post("/analysis", json=request).json()
        calibration = client.post("/calibrate", json={
            "symbols": ["BTC-USD"], "timeframes": ["5m"],
            "higher_timeframes": ["1h"], "lookback": 80,
            "max_trades_per_run": 10, "risk_per_trade_percent": 1,
            "starting_balance": 10000,
        }).json()
        overview = client.get("/dashboard/overview").json()
        setups = client.get("/dashboard/setups").json()
        recommendations = client.get("/dashboard/recommendations").json()
    finally:
        app.dependency_overrides.clear()

    assert first["action"] == second["action"]
    assert first["setup"] == second["setup"]
    assert first["setup_quality"]["score"] >= 0
    assert calibration["setup_quality_summary"] is not None
    assert overview["average_quality_score"] is not None
    assert "setups" in setups
    assert any(item["category"] == "setup_quality" for item in recommendations["recommendations"])
