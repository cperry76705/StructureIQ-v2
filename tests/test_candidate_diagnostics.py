from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app, get_candidate_diagnostics_engine
from core.candidate_diagnostics import CandidateDiagnosticsEngine
from core.live_market_monitor import LiveMarketMonitor, MonitorConfig
from core.market_data import Candle


def _analysis(confidence=66, quality=82, score=68, *, action="wait", setup_status="waiting_for_confirmation"):
    gate = SimpleNamespace(gate_name="directional_confidence", required=True, passed=False,
                           blocking_reason="Confidence is below threshold.")
    condition = SimpleNamespace(condition="Confirmation candle must close.", importance="required", is_met=False)
    return SimpleNamespace(
        symbol="EUR-USD", action=action, setup="bullish_bos_retest", confidence=confidence / 10,
        decision=SimpleNamespace(confidence=confidence, decision_diagnostics=SimpleNamespace(gate_results=(gate,))),
        setup_plan=SimpleNamespace(setup_status=setup_status, setup_type="bullish_bos_retest",
                                   setup_quality_score=quality, estimated_risk_reward=1.4,
                                   entry_conditions=(condition,), warning_notes=("Confirmation remains incomplete.",)),
        setup_quality=SimpleNamespace(score=quality),
        score_summary=SimpleNamespace(trade_quality_score=score),
        strategy=SimpleNamespace(preferred_strategy="breakout_continuation"),
        market_regime=SimpleNamespace(market_regime="weak_bull_trend"),
        multi_timeframe=SimpleNamespace(alignment="conflicting", directional_bias="bullish"),
        execution_intelligence=SimpleNamespace(execution_grade="C", execution_blockers=("Execution plan is not actionable.",), execution_warnings=()),
        trader_analysis=SimpleNamespace(trade_plan=SimpleNamespace(status="waiting")),
    )


def test_statistics_reasons_and_near_miss_calculation(tmp_path: Path) -> None:
    engine = CandidateDiagnosticsEngine(tmp_path / "diagnostics.jsonl")
    rejected = engine.record_analysis(_analysis(), timeframe="5m", higher_timeframe="1h", candidate_created=False)
    engine.record_analysis(_analysis(88, 92, 90, action="buy", setup_status="confirmed"), timeframe="5m", higher_timeframe="1h", candidate_created=True)
    summary = engine.summary()
    assert summary.markets_analyzed == 2 and summary.candidates_created == 1
    assert summary.candidate_rate_percent == 50
    assert summary.highest_confidence_rejected == 66
    assert rejected.distance_to_candidate[0].distance == -4
    assert rejected.blocked_reasons[0] == "directional_confidence"
    assert "execution_intelligence" in rejected.blocked_reasons
    assert engine.near_misses(1)[0].symbol == "EUR-USD"


def test_rejection_reason_ordering_and_duplicate_priority(tmp_path: Path) -> None:
    engine = CandidateDiagnosticsEngine(tmp_path / "diagnostics.jsonl")
    record = engine.record_analysis(_analysis(), timeframe="5m", higher_timeframe="1h", candidate_created=False, duplicate=True)
    assert record.blocked_reasons[0] == "duplicate_candidate"
    frequencies = engine.reasons()
    assert frequencies["duplicate_candidate"] == 1
    assert frequencies["directional_confidence"] == 1


def test_persistence_is_append_only_and_reloads(tmp_path: Path) -> None:
    path = tmp_path / "diagnostics.jsonl"
    engine = CandidateDiagnosticsEngine(path)
    engine.record_analysis(_analysis(), timeframe="5m", higher_timeframe="1h", candidate_created=False)
    engine.record_failure(symbol="BTC-USD", timeframe="5m", higher_timeframe="1h", error="provider unavailable")
    assert len(path.read_text(encoding="utf-8").splitlines()) == 2
    restored = CandidateDiagnosticsEngine(path)
    assert len(restored.recent()) == 2
    assert restored.summary().markets_analyzed == 1
    assert restored.writable()


class _Provider:
    def get_candles(self, symbol, timeframe, lookback):
        return [Candle(i, 100, 101, 99, 100, 1000) for i in range(lookback)]


class _Analysis:
    def analyze(self, request): return _analysis()


def test_monitor_records_rejected_market_without_changing_candidate_behavior(tmp_path: Path) -> None:
    diagnostics = CandidateDiagnosticsEngine(tmp_path / "diagnostics.jsonl")
    monitor = LiveMarketMonitor(
        _Provider(), MonitorConfig(symbols=["EUR-USD"], timeframes=["5m"], lookback=50, write_events=False),
        analysis_engine_factory=lambda provider: _Analysis(), candidate_diagnostics=diagnostics,
    )
    result = monitor.run_once()
    assert result.analyzed == 1 and result.candidates_created == 0
    assert diagnostics.summary().markets_analyzed == 1


def test_api_dashboard_and_openapi_integration(tmp_path: Path, monkeypatch) -> None:
    import core.candidate_diagnostics as module
    engine = CandidateDiagnosticsEngine(tmp_path / "diagnostics.jsonl")
    engine.record_analysis(_analysis(), timeframe="5m", higher_timeframe="1h", candidate_created=False)
    monkeypatch.setattr(module, "_GLOBAL_ENGINE", engine)
    app.dependency_overrides[get_candidate_diagnostics_engine] = lambda: engine
    try:
        client = TestClient(app)
        paths = client.get("/openapi.json").json()["paths"]
        for path in ("/candidate-diagnostics/summary", "/candidate-diagnostics/recent", "/candidate-diagnostics/reasons", "/candidate-diagnostics/near-misses"):
            assert path in paths
        assert client.get("/candidate-diagnostics/summary").json()["markets_analyzed"] == 1
        assert len(client.get("/candidate-diagnostics/recent?limit=1").json()) == 1
        assert client.get("/candidate-diagnostics/reasons").json()["directional_confidence"] == 1
        assert len(client.get("/candidate-diagnostics/near-misses").json()) == 1
        overview = client.get("/dashboard/overview").json()
        assert overview["candidate_markets_analyzed"] == 1
        assert overview["candidate_top_rejection_reason"] == "directional_confidence"
    finally:
        app.dependency_overrides.clear()
