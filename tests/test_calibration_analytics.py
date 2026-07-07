import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app, get_calibration_analytics_engine
from core.calibration_analytics import CalibrationAnalyticsEngine


def _record(symbol, confidence, quality, score, *, candidate=False, strategy="trend_continuation", regime="range", reasons=()):
    return {
        "timestamp": "2026-07-06T12:00:00+00:00", "symbol": symbol,
        "timeframe": "5m", "higher_timeframe": "1h", "analysis_completed": True,
        "candidate_created": candidate, "highest_confidence": confidence,
        "highest_setup_quality": quality, "overall_score": score,
        "best_strategy": strategy, "best_setup_name": "bullish_bos_retest",
        "market_regime": regime, "blocked_reasons": list(reasons),
        "distance_to_candidate": [
            {"metric": "directional_confidence", "required": 70, "actual": confidence, "distance": confidence - 70},
            {"metric": "setup_quality_reference", "required": 85, "actual": quality, "distance": quality - 85},
            {"metric": "overall_score_reference", "required": 70, "actual": score, "distance": score - 70},
        ] if not candidate else [],
    }


def _engine(tmp_path: Path):
    path = tmp_path / "candidate_diagnostics.jsonl"
    records = [
        _record("EUR-USD", 66, 82, 82, reasons=("directional_confidence", "higher_timeframe_alignment")),
        _record("EUR-USD", 75, 90, 85, candidate=True, regime="weak_bull_trend"),
        _record("BTC-USD", 95, 88, 92, candidate=True, strategy="liquidity_sweep_reversal", regime="expansion"),
        _record("GBP-USD", 40, 30, 20, reasons=("risk_filter", "score_threshold")),
        {"analysis_completed": False, "candidate_created": False, "symbol": "ETH-USD", "blocked_reasons": ["unknown"]},
    ]
    path.write_text("\n".join(json.dumps(item) for item in records) + "\n", encoding="utf-8")
    return CalibrationAnalyticsEngine(path, lambda: 3), path


def test_empty_diagnostics_are_safe(tmp_path):
    engine = CalibrationAnalyticsEngine(tmp_path / "missing.jsonl", lambda: 0)
    assert engine.summary().markets_analyzed == 0
    assert engine.confidence_distribution().total_records == 0
    assert engine.conversion_funnel().candidate_created == 0


def test_distributions_use_ten_fixed_buckets(tmp_path):
    engine, _ = _engine(tmp_path)
    confidence = engine.confidence_distribution()
    quality = engine.setup_quality_distribution()
    score = engine.score_distribution()
    assert len(confidence.buckets) == len(quality.buckets) == len(score.buckets) == 10
    assert confidence.buckets[4].count == 1  # confidence 40
    assert confidence.buckets[9].count == 1  # confidence 95
    assert quality.buckets[8].count == 2
    assert score.buckets[2].count == 1
    assert sum(item.percent for item in confidence.buckets) == 100


def test_funnel_waterfall_and_near_miss_summary(tmp_path):
    engine, _ = _engine(tmp_path)
    funnel = engine.conversion_funnel()
    assert funnel.markets_analyzed == 5 and funnel.analysis_completed == 4
    assert funnel.candidate_created == 2 and funnel.blocked_by_confidence == 1
    assert funnel.blocked_by_risk == 1 and funnel.paper_trades_opened == 3
    waterfall = engine.rejection_waterfall()
    assert waterfall.rejected_markets == 2
    assert {item.reason for item in waterfall.reasons} >= {"directional_confidence", "risk_filter"}
    near = engine.near_miss_summary()
    assert near.near_miss_count == 1
    assert near.closest_missed_candidate["symbol"] == "EUR-USD"
    assert near.average_distance_to_confidence_threshold == -4


def test_symbol_strategy_and_regime_analytics(tmp_path):
    engine, _ = _engine(tmp_path)
    symbols = engine.by_symbol().groups
    eur = next(item for item in symbols if item.symbol == "EUR-USD")
    assert eur.markets_analyzed == 2 and eur.candidates_created == 1
    assert eur.candidate_rate_percent == 50
    strategies = engine.by_strategy().groups
    assert any(item.name == "liquidity_sweep_reversal" and item.candidate_count == 1 for item in strategies)
    regimes = engine.by_regime().groups
    assert any(item.name == "range" and item.rejected_count == 2 for item in regimes)


def test_summary_and_computation_do_not_mutate_history(tmp_path):
    engine, path = _engine(tmp_path); before = path.read_bytes()
    summary = engine.summary()
    engine.confidence_distribution(); engine.conversion_funnel(); engine.by_symbol()
    assert path.read_bytes() == before
    assert summary.candidate_conversion_rate == 50
    assert summary.best_symbol_by_candidate_rate == "BTC-USD"
    assert summary.weakest_symbol_by_average_score == "GBP-USD"


def test_api_openapi_and_dashboard_integration(tmp_path, monkeypatch):
    import core.calibration_analytics as module
    engine, _ = _engine(tmp_path)
    monkeypatch.setattr(module, "_GLOBAL_ENGINE", engine)
    app.dependency_overrides[get_calibration_analytics_engine] = lambda: engine
    try:
        client = TestClient(app)
        paths = client.get("/openapi.json").json()["paths"]
        expected = (
            "/calibration-analytics/summary", "/calibration-analytics/confidence-distribution",
            "/calibration-analytics/setup-quality-distribution", "/calibration-analytics/score-distribution",
            "/calibration-analytics/rejection-waterfall", "/calibration-analytics/conversion-funnel",
            "/calibration-analytics/by-symbol", "/calibration-analytics/by-strategy", "/calibration-analytics/by-regime",
        )
        assert all(path in paths for path in expected)
        assert client.get("/calibration-analytics/summary").json()["markets_analyzed"] == 4
        assert len(client.get("/calibration-analytics/by-symbol").json()["groups"]) == 3
        overview = client.get("/dashboard/overview").json()
        assert overview["calibration_candidate_conversion_rate"] == 50
        assert overview["calibration_weakest_symbol_by_average_score"] == "GBP-USD"
    finally:
        app.dependency_overrides.clear()
