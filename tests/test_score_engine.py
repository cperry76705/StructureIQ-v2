from math import sin
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app, get_market_data_provider
from core.market_data import Candle
from core.score_engine import ScoreEngine


def _strong_inputs():
    structure = SimpleNamespace(trend="bullish", phase="impulse")
    timeframe = SimpleNamespace(alignment="aligned_bullish", alignment_score=95)
    regime = SimpleNamespace(
        market_regime="strong_bull_trend", regime_confidence=92
    )
    decision = SimpleNamespace(action="buy", confidence=90)
    conditions = (
        SimpleNamespace(importance="required", is_met=True),
        SimpleNamespace(importance="required", is_met=True),
    )
    setup = SimpleNamespace(
        setup_status="confirmed",
        setup_quality_score=95,
        entry_zone="100-101",
        stop_loss="98",
        target="106",
        entry_conditions=conditions,
    )
    candidate = SimpleNamespace(strategy_type="trend_continuation", score=90)
    strategy = SimpleNamespace(
        preferred_strategy="trend_continuation",
        strategy_alignment="aligned_with_decision",
        candidates=(candidate,),
    )
    return structure, timeframe, regime, decision, setup, strategy


def test_strong_evidence_produces_a_grade_without_research() -> None:
    structure, timeframe, regime, decision, setup, strategy = _strong_inputs()
    result = ScoreEngine().score(
        market_structure=structure,
        multi_timeframe=timeframe,
        market_regime=regime,
        decision=decision,
        setup_plan=setup,
        strategy=strategy,
        risk_reward_ratio=2.5,
    )

    assert result.score_grade.value in {"A", "A+"}
    assert result.trade_quality_score >= 80
    assert result.positive_score_contributors
    assert set(result.unavailable_research_inputs) == {
        "historical_edge",
        "statistical_reliability",
        "monte_carlo_risk",
    }
    assert "Research inputs unavailable" in result.human_readable_summary


def test_weak_no_trade_evidence_produces_d_or_f() -> None:
    result = ScoreEngine().score(
        market_structure=SimpleNamespace(trend="unclear", phase="unclear"),
        multi_timeframe=SimpleNamespace(alignment="conflicting", alignment_score=10),
        market_regime=SimpleNamespace(
            market_regime="unknown", regime_confidence=10
        ),
        decision=SimpleNamespace(action="avoid", confidence=20),
        setup_plan=SimpleNamespace(
            setup_status="no_setup",
            setup_quality_score=10,
            entry_zone=None,
            stop_loss=None,
            target=None,
            entry_conditions=(),
        ),
        strategy=SimpleNamespace(
            preferred_strategy="no_strategy",
            strategy_alignment="no_clear_strategy",
            candidates=(),
        ),
        risk_reward_ratio=0.5,
    )

    assert result.score_grade.value in {"D", "F"}
    assert result.negative_score_contributors


def test_mixed_evidence_produces_b_or_c() -> None:
    conditions = (
        SimpleNamespace(importance="required", is_met=True),
        SimpleNamespace(importance="required", is_met=False),
    )
    setup = SimpleNamespace(
        setup_status="developing",
        setup_quality_score=68,
        entry_zone="100-101",
        stop_loss="98",
        target="104",
        entry_conditions=conditions,
    )
    strategy = SimpleNamespace(
        preferred_strategy="range_reversal",
        strategy_alignment="partially_aligned",
        candidates=(SimpleNamespace(strategy_type="range_reversal", score=70),),
    )
    result = ScoreEngine().score(
        market_structure=SimpleNamespace(trend="ranging", phase="range"),
        multi_timeframe=SimpleNamespace(alignment="mixed", alignment_score=65),
        market_regime=SimpleNamespace(market_regime="range", regime_confidence=70),
        decision=SimpleNamespace(action="wait", confidence=65),
        setup_plan=setup,
        strategy=strategy,
        risk_reward_ratio=1.8,
    )

    assert result.score_grade.value in {"B", "C"}
    assert result.neutral_score_contributors


class _Provider:
    def get_candles(self, symbol: str, timeframe: str, lookback: int) -> list[Candle]:
        del symbol, timeframe
        candles = []
        for index in range(320):
            close = 100 + index * 0.08 + sin(index * 0.7) * 2
            candles.append(
                Candle(index, close - 0.2, close + 0.8, close - 0.8, close, 100)
            )
        return candles[-lookback:]


def test_analysis_includes_score_without_changing_action() -> None:
    app.dependency_overrides[get_market_data_provider] = lambda: _Provider()
    request = {
        "symbol": "BTC-USD",
        "timeframe": "5m",
        "higher_timeframe": "1h",
        "lookback": 200,
    }
    try:
        client = TestClient(app)
        first = client.post("/analysis", json=request)
        second = client.post("/analysis", json=request)
    finally:
        app.dependency_overrides.clear()

    assert first.status_code == second.status_code == 200
    assert first.json()["score_summary"] is not None
    assert first.json()["score_summary"]["human_readable_summary"]
    assert first.json()["action"] == second.json()["action"]
    assert first.json()["decision"] == second.json()["decision"]


def test_calibration_includes_aggregate_score_without_changing_metrics() -> None:
    app.dependency_overrides[get_market_data_provider] = lambda: _Provider()
    request = {
        "symbols": ["BTC-USD"],
        "timeframes": ["5m"],
        "higher_timeframes": ["1h"],
        "lookback": 100,
        "max_trades_per_run": 5,
    }
    try:
        client = TestClient(app)
        first = client.post("/calibrate", json=request)
        second = client.post("/calibrate", json=request)
    finally:
        app.dependency_overrides.clear()

    assert first.status_code == second.status_code == 200
    assert first.json()["aggregate_score_summary"] is not None
    assert first.json()["aggregate_score_summary"]["evidence_score_breakdown"]
    assert first.json()["aggregate_metrics"] == second.json()["aggregate_metrics"]

