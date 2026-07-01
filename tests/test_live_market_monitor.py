import json
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app, get_live_market_monitor
from core.live_market_monitor import (
    LiveMarketMonitor,
    MonitorConfig,
    reset_global_live_market_monitor,
)
from core.market_data import Candle, MarketDataError


class _Provider:
    provider_name = "monitor-test"

    def __init__(self, failing_symbol: str | None = None):
        self.failing_symbol = failing_symbol
        self.calls = []

    def get_candles(self, symbol, timeframe, lookback):
        self.calls.append((symbol, timeframe, lookback))
        if symbol == self.failing_symbol:
            raise MarketDataError("synthetic provider failure")
        return [Candle(i, 100, 101, 99, 100, 1000) for i in range(1, lookback + 1)]


def _analysis(symbol="BTC-USD", action="buy", setup_status="confirmed", plan_status="actionable"):
    return SimpleNamespace(
        symbol=symbol,
        action=action,
        setup="liquidity_sweep_reversal_long",
        confidence=7.8,
        entry_zone="100.00-100.20",
        stop_loss="99.00",
        target="102.50",
        reasons=["Synthetic actionable evidence."],
        setup_plan=SimpleNamespace(setup_status=setup_status),
        trader_analysis=SimpleNamespace(trade_plan=SimpleNamespace(status=plan_status)),
        strategy=SimpleNamespace(preferred_strategy="liquidity_sweep_reversal"),
        setup_quality=SimpleNamespace(score=88, grade="B+"),
        score_summary=SimpleNamespace(trade_quality_score=82),
        execution_intelligence=SimpleNamespace(execution_grade="B"),
    )


class _AnalysisEngine:
    def __init__(self, provider, resolver):
        self.provider = provider
        self.resolver = resolver

    def analyze(self, request):
        return self.resolver(request)


def _monitor(tmp_path: Path, *, provider=None, resolver=None, write=False):
    provider = provider or _Provider()
    resolver = resolver or (lambda request: _analysis(request.symbol))
    config = MonitorConfig(
        symbols=["BTC-USD", "EUR-USD"], timeframes=["5m"],
        higher_timeframe="1h", lookback=50, poll_seconds=60,
        write_events=write, events_path=str(tmp_path / "events.jsonl"),
    )
    return LiveMarketMonitor(
        provider, config,
        analysis_engine_factory=lambda source: _AnalysisEngine(source, resolver),
    )


def test_run_once_analyzes_configured_symbols_and_emits_candidates(tmp_path) -> None:
    monitor = _monitor(tmp_path)
    result = monitor.run_once()
    assert result.analyzed == 2
    assert result.candidates_created == 2
    assert {event.symbol for event in result.events} == {"BTC-USD", "EUR-USD"}
    assert all(event.status == "candidate" and not event.paper_trade_created for event in result.events)


def test_wait_and_no_trade_do_not_emit_events(tmp_path) -> None:
    monitor = _monitor(tmp_path, resolver=lambda request: _analysis(request.symbol, action="wait", setup_status="developing", plan_status="waiting"))
    result = monitor.run_once()
    assert result.candidates_created == 0
    assert monitor.events() == ()


def test_duplicate_candle_signal_is_not_emitted_twice(tmp_path) -> None:
    monitor = _monitor(tmp_path)
    assert monitor.run_once().candidates_created == 2
    second = monitor.run_once()
    assert second.candidates_created == 0
    assert second.duplicates_skipped == 2
    assert len(monitor.events()) == 2


def test_provider_failure_is_captured_and_other_symbols_continue(tmp_path) -> None:
    monitor = _monitor(tmp_path, provider=_Provider(failing_symbol="BTC-USD"))
    result = monitor.run_once()
    assert result.analyzed == 1
    assert result.candidates_created == 1
    assert len(result.errors) == 1
    assert monitor.status().error_count == 1
    assert "BTC-USD" in monitor.status().last_error


def test_jsonl_appends_candidate_events(tmp_path) -> None:
    monitor = _monitor(tmp_path, write=True)
    monitor.run_once()
    path = tmp_path / "events.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2
    assert rows[0]["paper_trade_created"] is False
    assert rows[0]["setup_quality"]["score"] == 88


def test_start_stop_are_safe_and_idempotent(tmp_path) -> None:
    monitor = _monitor(tmp_path)
    assert monitor.start().running is True
    assert monitor.start().running is True
    assert monitor.stop().running is False
    assert monitor.stop().running is False


def test_monitor_api_and_openapi_contract(tmp_path) -> None:
    monitor = _monitor(tmp_path)
    app.dependency_overrides[get_live_market_monitor] = lambda: monitor
    try:
        client = TestClient(app)
        paths = client.get("/openapi.json").json()["paths"]
        for path in ("/monitor/status", "/monitor/run-once", "/monitor/start", "/monitor/stop", "/monitor/events"):
            assert path in paths
            assert "monitor" in next(iter(paths[path].values()))["tags"]
        assert client.get("/monitor/status").json()["running"] is False
        cycle = client.post("/monitor/run-once").json()
        assert cycle["candidates_created"] == 2
        events = client.get("/monitor/events").json()
        assert len(events) == 2
        assert client.post("/monitor/start").json()["running"] is True
        assert client.post("/monitor/stop").json()["running"] is False
    finally:
        monitor.stop()
        app.dependency_overrides.clear()


def test_dashboard_surfaces_monitor_state_without_enabling_paper_trading(tmp_path, monkeypatch) -> None:
    import core.live_market_monitor as live_module

    monitor = _monitor(tmp_path)
    monitor.run_once()
    monkeypatch.setattr(live_module, "_GLOBAL_MONITOR", monitor)
    try:
        client = TestClient(app)
        overview = client.get("/dashboard/overview").json()
        readiness = client.get("/dashboard/readiness").json()
        assert overview["recent_monitor_signal_count"] == 2
        assert overview["monitor_ready_for_paper_trading"] is False
        assert readiness["monitor_ready_for_paper_trading"] is False
    finally:
        reset_global_live_market_monitor()
