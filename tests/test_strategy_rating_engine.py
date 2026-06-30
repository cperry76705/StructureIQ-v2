from math import sin
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app, get_market_data_provider
from core.market_data import Candle
from core.research_lab import ResearchConfidenceInterval
from core.strategy_rating_engine import RatingGrade, StrategyRatingEngine


def _row(
    category: str,
    *,
    sample: int,
    expectancy: float,
    profit_factor: float | None = 2.0,
    drawdown: float = 2.0,
):
    return SimpleNamespace(
        category=category,
        records_seen=sample,
        executed_trades=sample,
        wins=round(sample * 0.65),
        losses=sample - round(sample * 0.65),
        breakeven=0,
        win_rate=65.0,
        average_r=expectancy,
        total_r=expectancy * sample,
        expectancy=expectancy,
        profit_factor=profit_factor,
        max_drawdown=drawdown,
        average_mfe=1.5,
        average_mae=0.7,
        average_trade_duration=4.0,
        average_confidence=78.0,
        confidence_interval=ResearchConfidenceInterval(
            expectancy - 0.1, expectancy + 0.1, 0.95, sample
        ),
        statistical_significance_score=95.0,
        sample_quality=(
            "high" if sample >= 50 else "moderate" if sample >= 20
            else "low" if sample >= 5 else "insufficient"
        ),
        recommendation="Synthetic recommendation.",
    )


def _rate(row, *, folds=()):
    summary = SimpleNamespace(
        strategy_performance=(row,),
        setup_performance=(row,),
    )
    return StrategyRatingEngine().rate(
        research_lab_summary=summary,
        validation_fold_results=folds,
        overfitting_summary=SimpleNamespace(risk_level="LOW"),
        statistical_validation_summary=SimpleNamespace(overall_status="PASS"),
        confidence_bucket_calibration=(),
    )


def _fold(category: str):
    performance = SimpleNamespace(trades=20, expectancy=0.8)
    return SimpleNamespace(
        validation_strategy_performance={category: performance},
        validation_setup_performance={category: performance},
    )


def test_strong_sufficient_strategy_produces_a_grade() -> None:
    row = _row("trend_continuation", sample=100, expectancy=0.8)
    result = _rate(row, folds=tuple(_fold(row.category) for _ in range(5)))
    grade = result.strategy_grades[0]

    assert grade.grade in {RatingGrade.A, RatingGrade.A_PLUS}
    assert grade.sample_size == 100
    assert grade.out_of_sample_consistency == 100.0
    assert result.strongest_strategy == "trend_continuation"


def test_positive_low_sample_strategy_is_capped_at_b() -> None:
    grade = _rate(_row("breakout_continuation", sample=10, expectancy=1.2)).strategy_grades[0]

    assert grade.grade is RatingGrade.B
    assert "Fewer than 20" in grade.human_readable_summary


def test_fewer_than_five_trades_is_capped_at_d() -> None:
    grade = _rate(_row("range_reversal", sample=4, expectancy=2.0)).strategy_grades[0]

    assert grade.grade is RatingGrade.D
    assert grade.sample_quality == "insufficient"
    assert "do not change production" in grade.human_readable_summary


def test_negative_expectancy_is_f() -> None:
    grade = _rate(
        _row("weak_strategy", sample=100, expectancy=-0.1, profit_factor=0.8)
    ).strategy_grades[0]

    assert grade.grade is RatingGrade.F
    assert "negative-expectancy" in grade.recommendation


def test_missing_oos_and_statistical_inputs_do_not_crash() -> None:
    summary = SimpleNamespace(
        strategy_performance=(_row("trend_continuation", sample=25, expectancy=0.3),),
        setup_performance=(_row("bullish_bos_retest", sample=25, expectancy=0.3),),
    )
    result = StrategyRatingEngine().rate(research_lab_summary=summary)

    assert result.strategy_grades[0].out_of_sample_consistency is None
    assert "unavailable" in result.strategy_grades[0].human_readable_summary.lower()


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


def test_analysis_returns_unavailable_ratings_without_changing_action() -> None:
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
    assert first.json()["current_strategy_rating"]["available"] is False
    assert first.json()["current_setup_rating"]["available"] is False
    assert first.json()["current_strategy_rating"]["warning"]
    assert first.json()["action"] == second.json()["action"]


def test_calibration_returns_rating_summaries_without_metric_changes() -> None:
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
    assert first.json()["strategy_rating_summary"] is not None
    assert first.json()["setup_rating_summary"] is not None
    assert first.json()["aggregate_metrics"] == second.json()["aggregate_metrics"]

