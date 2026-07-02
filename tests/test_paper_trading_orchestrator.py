from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app, get_paper_trading_orchestrator
from core.daily_report_engine import DailyReportEngine
from core.live_market_monitor import LiveMarketMonitor, MonitorConfig
from core.market_data import Candle, MarketDataError
from core.paper_brokerage import PaperAccountConfig, PaperBrokerageEngine, PaperOpenRequest
from core.paper_trade_journal import PaperTradeJournal
from core.paper_trading_orchestrator import (
    PaperTradingOrchestrator,
    PaperTradingOrchestratorConfig,
)
from core.trade_lifecycle_manager import TradeLifecycleManager


class _Provider:
    def __init__(self, fail=False):
        self.fail = fail
        self.candle = Candle(100, 100, 101, 99, 100.5, 1000)

    def get_candles(self, symbol, timeframe, lookback):
        if self.fail:
            raise MarketDataError("synthetic provider failure")
        return [self.candle for _ in range(lookback)]


class _Analysis:
    def __init__(self, *, action="buy", grade="B", include_quality=True, blockers=()):
        self.action, self.grade, self.include_quality, self.blockers = action, grade, include_quality, blockers

    def analyze(self, request):
        return SimpleNamespace(
            symbol=request.symbol, action=self.action,
            setup="liquidity_sweep_reversal_long", confidence=7.8,
            entry_zone="100", stop_loss="98", target="106",
            reasons=["Synthetic orchestrator candidate."],
            setup_plan=SimpleNamespace(setup_status="confirmed"),
            trader_analysis=SimpleNamespace(trade_plan=SimpleNamespace(status="actionable")),
            strategy=SimpleNamespace(preferred_strategy="liquidity_sweep_reversal"),
            setup_quality=({"score": 82, "grade": self.grade} if self.include_quality else None),
            score_summary={"trade_quality_score": 80},
            execution_intelligence={"execution_blockers": list(self.blockers)},
        )


def _services(tmp_path: Path, *, symbols=None, analysis=None, provider=None, config=None, broker_config=None):
    provider = provider or _Provider()
    analysis = analysis or _Analysis()
    monitor = LiveMarketMonitor(
        provider,
        MonitorConfig(symbols=symbols or ["BTC-USD"], timeframes=["5m"], lookback=50, write_events=False),
        analysis_engine_factory=lambda source: analysis,
    )
    broker = PaperBrokerageEngine(broker_config)
    lifecycle = TradeLifecycleManager(provider, monitor, broker)
    journal = PaperTradeJournal(broker, lifecycle, tmp_path / "journal.jsonl")
    reports = DailyReportEngine(journal, lifecycle, broker, monitor, reports_dir=tmp_path / "daily")
    orchestrator = PaperTradingOrchestrator(monitor, lifecycle, broker, journal, reports, config)
    return orchestrator, monitor, lifecycle, broker, journal, reports


def _auto(**overrides):
    values = dict(
        auto_approve_candidates=True, require_manual_approval=False,
        generate_daily_report_after_cycle=False,
    )
    values.update(overrides)
    return PaperTradingOrchestratorConfig(**values)


def test_orchestrator_initializes_disabled() -> None:
    orchestrator, *_ = _services(Path("unused"), config=PaperTradingOrchestratorConfig(generate_daily_report_after_cycle=False))
    status = orchestrator.status()
    assert status.enabled is False
    assert status.running is False
    assert status.paper_only is True


def test_run_cycle_with_no_candidates(tmp_path) -> None:
    orchestrator, *_ = _services(tmp_path, analysis=_Analysis(action="wait"), config=PaperTradingOrchestratorConfig(generate_daily_report_after_cycle=False))
    result = orchestrator.run_cycle()
    assert result.candidates_seen == 0
    assert result.trades_opened == 0
    assert result.status == "completed"


def test_default_cycle_observes_without_approval(tmp_path) -> None:
    orchestrator, _, lifecycle, broker, _, _ = _services(tmp_path, config=PaperTradingOrchestratorConfig(generate_daily_report_after_cycle=False))
    result = orchestrator.run_cycle()
    assert result.candidates_seen == 1
    assert result.candidates_approved == 0
    assert len(lifecycle.pending_orders()) == 0
    assert len(broker.open_positions()) == 0
    assert "manual" in " ".join(result.blocked_reasons).lower()


def test_auto_approval_opens_only_safe_candidate(tmp_path) -> None:
    orchestrator, _, _, broker, journal, _ = _services(tmp_path, config=_auto())
    result = orchestrator.run_cycle()
    assert result.candidates_approved == 1
    assert result.orders_created == 1
    assert result.orders_filled == 1
    assert result.trades_opened == 1
    assert len(broker.open_positions()) == 1
    assert len(journal.entries()) == 1


def test_low_or_missing_quality_is_blocked(tmp_path) -> None:
    low, *_ = _services(tmp_path / "low", analysis=_Analysis(grade="F"), config=_auto())
    low_result = low.run_cycle()
    assert low_result.candidates_approved == 0
    assert "grade F" in " ".join(low_result.blocked_reasons)

    missing, *_ = _services(tmp_path / "missing", analysis=_Analysis(include_quality=False), config=_auto())
    missing_result = missing.run_cycle()
    assert missing_result.candidates_approved == 0
    assert "quality is missing" in " ".join(missing_result.blocked_reasons)


def test_paper_risk_limit_blocks_auto_approval(tmp_path) -> None:
    orchestrator, _, _, broker, _, _ = _services(
        tmp_path, config=_auto(),
        broker_config=PaperAccountConfig(max_daily_loss_percent=1),
    )
    trade = broker.open_position(PaperOpenRequest(
        symbol="ETH-USD", timeframe="5m", higher_timeframe="1h", action="buy",
        setup="test", strategy="test", entry_price=100, stop_loss=98, target=104,
    ))
    broker.close_position(trade.trade_id, 98)
    result = orchestrator.run_cycle()
    assert result.candidates_approved == 0
    assert "daily_loss_limit" in " ".join(result.blocked_reasons)


def test_max_new_trades_and_duplicate_cycles_are_enforced(tmp_path) -> None:
    orchestrator, _, _, broker, _, _ = _services(
        tmp_path, symbols=["BTC-USD", "ETH-USD", "EUR-USD"],
        config=_auto(max_candidates_per_cycle=3, max_new_trades_per_cycle=1),
        broker_config=PaperAccountConfig(allow_duplicate_symbol_positions=True, allow_duplicate_setup_positions=True),
    )
    first = orchestrator.run_cycle()
    assert first.candidates_seen == 3
    assert first.candidates_approved == 1
    assert len(broker.open_positions()) == 1
    second = orchestrator.run_cycle()
    assert second.candidates_seen == 0
    assert second.candidates_approved == 0


def test_daily_report_generation_and_error_pause(tmp_path) -> None:
    orchestrator, *_, reports = _services(tmp_path / "report", analysis=_Analysis(action="wait"))
    result = orchestrator.run_cycle()
    assert result.daily_report_generated is True
    assert reports.latest() is not None

    guarded, *_, guarded_reports = _services(
        tmp_path / "guarded", analysis=_Analysis(action="wait"),
        config=PaperTradingOrchestratorConfig(report_overwrite=False),
    )
    first = guarded.run_cycle(); second = guarded.run_cycle()
    assert first.daily_report_status == "generated"
    assert second.daily_report_status == "skipped_existing"
    assert "daily_report_skipped_existing" in second.blocked_reasons
    assert second.errors == ()
    assert len(guarded_reports.list_reports()) == 1

    failing, *_ = _services(
        tmp_path / "fail", provider=_Provider(fail=True),
        config=PaperTradingOrchestratorConfig(generate_daily_report_after_cycle=False, max_errors_before_pause=1),
    )
    failed = failing.run_cycle()
    assert failed.errors
    assert failing.status().paused is True


def test_start_stop_are_idempotent(tmp_path) -> None:
    orchestrator, *_ = _services(tmp_path, analysis=_Analysis(action="wait"), config=PaperTradingOrchestratorConfig(generate_daily_report_after_cycle=False))
    assert orchestrator.start().running is True
    assert orchestrator.start().running is True
    assert orchestrator.stop().running is False
    assert orchestrator.stop().running is False


def test_api_openapi_and_dashboard(tmp_path, monkeypatch) -> None:
    import core.paper_trading_orchestrator as module

    orchestrator, *_ = _services(tmp_path, config=PaperTradingOrchestratorConfig(generate_daily_report_after_cycle=False))
    monkeypatch.setattr(module, "_GLOBAL_ORCHESTRATOR", orchestrator)
    app.dependency_overrides[get_paper_trading_orchestrator] = lambda: orchestrator
    try:
        client = TestClient(app)
        paths = client.get("/openapi.json").json()["paths"]
        for path in (
            "/paper-trading/status", "/paper-trading/run-cycle", "/paper-trading/start",
            "/paper-trading/stop", "/paper-trading/cycles", "/paper-trading/recent-actions",
        ):
            assert path in paths
            assert "paper-trading" in next(iter(paths[path].values()))["tags"]
        cycle = client.post("/paper-trading/run-cycle").json()
        assert cycle["candidates_seen"] == 1
        assert client.get("/paper-trading/cycles").json()
        overview = client.get("/dashboard/overview").json()
        assert overview["paper_trading_orchestrator_status"] == "stopped_advisory"
        assert overview["total_cycles"] == 1
    finally:
        orchestrator.stop()
        app.dependency_overrides.clear()
        module.reset_global_paper_trading_orchestrator()
