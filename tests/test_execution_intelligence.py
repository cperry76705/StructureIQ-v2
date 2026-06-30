from math import sin
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app, get_market_data_provider
from core.execution_intelligence import ExecutionIntelligenceEngine, ExecutionStyle
from core.market_data import Candle


def _setup(
    *,
    setup_type="bullish_bos_retest",
    status="confirmed",
    ratio=2.0,
    confirmed=True,
    levels=True,
):
    return SimpleNamespace(
        setup_type=setup_type,
        setup_status=status,
        direction="bullish",
        setup_quality_score=88,
        entry_zone="100-101" if levels else None,
        stop_loss="98" if levels else None,
        target="106" if levels else None,
        estimated_risk_reward=ratio,
        entry_conditions=(
            SimpleNamespace(
                importance="required",
                is_met=confirmed,
            ),
        ),
    )


def _strategy(alignment="aligned_with_decision"):
    return SimpleNamespace(
        preferred_strategy="breakout_continuation",
        strategy_alignment=alignment,
    )


def test_no_trade_uses_avoid_execution() -> None:
    result = ExecutionIntelligenceEngine().analyze(
        action="no_trade",
        setup_plan=_setup(setup_type="no_valid_setup", status="no_setup", levels=False),
        strategy=_strategy("no_clear_strategy"),
    )

    assert result.preferred_execution_style is ExecutionStyle.AVOID_EXECUTION
    assert result.execution_blockers
    assert "Do not execute" in result.entry_timing_guidance


def test_valid_retest_setup_produces_limit_execution_guidance() -> None:
    result = ExecutionIntelligenceEngine().analyze(
        action="buy",
        setup_plan=_setup(ratio=2.5),
        strategy=_strategy(),
    )

    assert result.preferred_execution_style is ExecutionStyle.LIMIT_RETEST
    assert result.execution_quality_score >= 70
    assert result.risk_reward_assessment.status == "strong"
    assert "2.50R" in result.risk_reward_assessment.explanation
    assert result.human_readable_summary


def test_weak_confirmation_prefers_wait_guidance() -> None:
    result = ExecutionIntelligenceEngine().analyze(
        action="wait",
        setup_plan=_setup(
            setup_type="bullish_pullback_continuation",
            status="developing",
            confirmed=False,
        ),
        strategy=_strategy("partially_aligned"),
    )

    assert result.preferred_execution_style is ExecutionStyle.WAIT_FOR_PULLBACK
    assert "confirmation" in " ".join(result.execution_warnings).lower()
    assert "Wait for price" in result.entry_timing_guidance


def test_level_diagnostics_and_management_research_add_advisory_warnings() -> None:
    management = SimpleNamespace(
        improved_vs_baseline=True,
        total_r=5.0,
        rule="trail_after_1r",
    )
    result = ExecutionIntelligenceEngine().analyze(
        action="buy",
        setup_plan=_setup(),
        strategy=_strategy(),
        risk_reward_diagnostics=SimpleNamespace(failure_reason="stop_too_wide"),
        trade_management_sensitivity=(management,),
    )

    assert result.stop_quality_assessment.status == "too_wide"
    assert "trade_management" in result.research_inputs_available
    assert any("trail after 1r" in item for item in result.trade_management_guidance)


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


def test_analysis_includes_execution_intelligence_without_changing_action() -> None:
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
    intelligence = first.json()["execution_intelligence"]
    assert intelligence is not None
    assert intelligence["human_readable_summary"]
    assert first.json()["action"] == second.json()["action"]
    assert first.json()["entry_zone"] == second.json()["entry_zone"]


def test_calibration_aggregates_execution_intelligence_without_metric_changes() -> None:
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
    summary = first.json()["aggregate_execution_intelligence_summary"]
    assert summary is not None
    assert summary["human_readable_summary"]
    assert first.json()["aggregate_metrics"] == second.json()["aggregate_metrics"]

