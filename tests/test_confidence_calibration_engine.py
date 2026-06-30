from math import sin

from fastapi.testclient import TestClient

from app.main import app, get_market_data_provider
from core.confidence_calibration_engine import (
    ConfidenceCalibrationEngine,
    ConfidenceReliability,
)
from core.market_data import Candle


def test_missing_history_uses_identity_with_insufficient_reliability() -> None:
    result = ConfidenceCalibrationEngine().calibrate(74.0)

    assert result.raw_score == result.calibrated_confidence == 74.0
    assert result.historical_win_probability is None
    assert result.confidence_reliability is ConfidenceReliability.INSUFFICIENT
    assert result.calibration_method == "identity"
    assert result.calibration_warning
    assert result.human_readable_summary


def test_low_sample_bucket_is_flagged_and_keeps_identity_mapping() -> None:
    engine = ConfidenceCalibrationEngine()
    buckets = engine.build_buckets([(75.0, "win")] * 7 + [(75.0, "loss")] * 3)
    result = engine.calibrate(76.0, buckets)

    assert result.sample_size == 10
    assert result.historical_win_probability == 70.0
    assert result.calibrated_confidence == 76.0
    assert result.confidence_reliability is ConfidenceReliability.LOW
    assert result.calibration_method == "identity"


def test_strong_sample_uses_empirical_win_probability() -> None:
    engine = ConfidenceCalibrationEngine()
    observations = [(82.0, "win")] * 70 + [(84.0, "loss")] * 30
    buckets = engine.build_buckets(observations)
    result = engine.calibrate(83.0, buckets)
    summary = engine.summarize(buckets)

    assert result.sample_size == 100
    assert result.calibrated_confidence == 70.0
    assert result.historical_win_probability == 70.0
    assert result.confidence_reliability is ConfidenceReliability.HIGH
    assert result.calibration_method == "bucketed_empirical"
    assert summary.total_samples == 100
    assert summary.overall_reliability is ConfidenceReliability.HIGH


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


def test_analysis_returns_identity_calibration_without_changing_action() -> None:
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
    calibration = first.json()["confidence_calibration"]
    assert calibration["calibration_method"] == "identity"
    assert calibration["confidence_reliability"] == "insufficient"
    assert calibration["raw_score"] == first.json()["decision"]["confidence"]
    assert first.json()["action"] == second.json()["action"]


def test_calibration_returns_buckets_without_changing_metrics() -> None:
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
    payload = first.json()
    assert payload["aggregate_confidence_calibration_summary"] is not None
    assert len(payload["confidence_bucket_calibration"]) == 5
    assert {
        item["calibration_bucket"] for item in payload["confidence_bucket_calibration"]
    } == {"50-59", "60-69", "70-79", "80-89", "90-100"}
    assert payload["aggregate_metrics"] == second.json()["aggregate_metrics"]

