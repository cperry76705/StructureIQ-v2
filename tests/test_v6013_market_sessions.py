from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

import start
from app.main import app, get_live_market_monitor, get_market_session_engine
from core.candidate_pipeline_diagnostics import CandidatePipelineDiagnosticsEngine
from core.live_market_monitor import LiveMarketMonitor, MonitorConfig
from core.market_data import Candle
from core.market_session_engine import AssetClass, MarketSessionEngine, MarketSessionStatus, classify_symbol
from core.paper_trading_orchestrator import PaperTradingOrchestrator, PaperTradingOrchestratorConfig
from core.paper_brokerage import PaperBrokerageEngine
from core.paper_trade_journal import PaperTradeJournal
from core.trade_lifecycle_manager import TradeLifecycleManager
from core.daily_report_engine import DailyReportEngine
from core.validation_campaigns import ValidationCampaignManager


class _Provider:
    def __init__(self):
        self.calls: list[str] = []

    def get_candles(self, symbol, timeframe, lookback):
        self.calls.append(symbol)
        return [Candle(i, 100, 101, 99, 100, 1000) for i in range(lookback)]


class _Analysis:
    def analyze(self, request):
        return SimpleNamespace(
            symbol=request.symbol,
            action="wait",
            setup="none",
            confidence=0,
            trader_analysis=SimpleNamespace(trade_plan=SimpleNamespace(status="waiting")),
            setup_plan=SimpleNamespace(setup_status="developing"),
        )


def _dt(year, month, day, hour):
    return datetime(year, month, day, hour, 0, tzinfo=timezone.utc)


def test_symbol_classification_and_forex_sessions():
    assert classify_symbol("BTC-USD") is AssetClass.CRYPTO
    assert classify_symbol("ETH-USD") is AssetClass.CRYPTO
    assert classify_symbol("EUR-USD") is AssetClass.FOREX
    assert classify_symbol("GBP-USD") is AssetClass.FOREX

    weekend = MarketSessionEngine(clock=lambda: _dt(2026, 8, 8, 18))
    weekday = MarketSessionEngine(clock=lambda: _dt(2026, 8, 10, 15))
    friday_closed = MarketSessionEngine(clock=lambda: _dt(2026, 8, 7, 22))
    sunday_open = MarketSessionEngine(clock=lambda: _dt(2026, 8, 9, 23))

    assert weekend.session_for_asset_class(AssetClass.CRYPTO).status is MarketSessionStatus.OPEN
    assert weekend.session_for_asset_class(AssetClass.FOREX).status is MarketSessionStatus.CLOSED
    assert weekday.session_for_asset_class(AssetClass.FOREX).status is MarketSessionStatus.OPEN
    assert friday_closed.session_for_asset_class(AssetClass.FOREX).status is MarketSessionStatus.CLOSED
    assert sunday_open.session_for_asset_class(AssetClass.FOREX).status is MarketSessionStatus.OPEN


def test_weekend_watchlist_filters_forex_and_ignore_restores_old_behavior():
    engine = MarketSessionEngine(clock=lambda: _dt(2026, 8, 8, 18))
    watchlist = engine.active_watchlist(["BTC-USD", "ETH-USD", "EUR-USD", "GBP-USD"])

    assert watchlist.active_symbols == ("BTC-USD", "ETH-USD")
    assert watchlist.skipped_symbols == ("EUR-USD", "GBP-USD")
    assert watchlist.reasons["EUR-USD"] == "Forex Market Closed"

    ignored = engine.active_watchlist(["BTC-USD", "EUR-USD"], ignore_market_sessions=True)
    assert ignored.active_symbols == ("BTC-USD", "EUR-USD")
    assert ignored.skipped_symbols == ()


def test_monitor_skips_closed_markets_before_provider_and_analysis(tmp_path: Path):
    provider = _Provider()
    engine = MarketSessionEngine(clock=lambda: _dt(2026, 8, 8, 18))
    monitor = LiveMarketMonitor(
        provider,
        MonitorConfig(symbols=["BTC-USD", "ETH-USD", "EUR-USD", "GBP-USD"], timeframes=["5m"], lookback=50, write_events=False),
        analysis_engine_factory=lambda source: _Analysis(),
        market_sessions=engine,
    )

    result = monitor.run_once()

    assert result.analyzed == 2
    assert result.markets_configured == 4
    assert result.markets_open == 2
    assert result.markets_skipped == 2
    assert result.skipped_symbols == ("EUR-USD", "GBP-USD")
    assert provider.calls == ["BTC-USD", "ETH-USD"]


def test_candidate_pipeline_records_skips_without_rejections(tmp_path: Path):
    provider = _Provider()
    engine = MarketSessionEngine(clock=lambda: _dt(2026, 8, 8, 18))
    monitor = LiveMarketMonitor(
        provider,
        MonitorConfig(symbols=["BTC-USD", "EUR-USD"], timeframes=["5m"], lookback=50, write_events=False),
        analysis_engine_factory=lambda source: _Analysis(),
        market_sessions=engine,
    )
    result = monitor.run_once()
    pipeline = CandidatePipelineDiagnosticsEngine(tmp_path / "cycles.jsonl", campaigns_root=tmp_path / "campaigns")

    cycle = pipeline.record_cycle(
        cycle_id="cycle-1",
        campaign_id="campaign-1",
        started_at="2026-08-08T18:00:00+00:00",
        completed_at=result.completed_at,
        monitor_result=result,
        orders_created=0,
        trades_opened=0,
        cycle_status="completed",
        configured_symbols=tuple(monitor.config.symbols),
        configured_timeframes=tuple(monitor.config.timeframes),
        recent_market_diagnostics=(),
    )

    skipped = [item for item in cycle.symbol_diagnostics if item.skipped]
    assert cycle.symbols_scanned == 1
    assert cycle.symbols_skipped == 1
    assert cycle.candidates_rejected == 1  # only the analyzed BTC no-candidate path
    assert skipped[0].symbol == "EUR-USD"
    assert skipped[0].skipped_reason == "Forex Market Closed"
    assert skipped[0].rejection_stage is None
    assert pipeline.summary(campaign_id="campaign-1").symbols_skipped_market_closed == 1


def test_market_session_api_dashboard_cli_and_campaign_summary(tmp_path: Path, capsys, monkeypatch):
    import core.research_dashboard as dashboard_module
    import core.candidate_pipeline_diagnostics as pipeline_module

    engine = MarketSessionEngine(clock=lambda: _dt(2026, 8, 8, 18))
    monkeypatch.setattr(dashboard_module, "get_global_market_session_engine", lambda: engine)
    provider = _Provider()
    monitor = LiveMarketMonitor(
        provider,
        MonitorConfig(symbols=["BTC-USD", "ETH-USD", "EUR-USD", "GBP-USD"], timeframes=["5m"], lookback=50, write_events=False),
        analysis_engine_factory=lambda source: _Analysis(),
        market_sessions=engine,
    )
    app.dependency_overrides[get_market_session_engine] = lambda: engine
    app.dependency_overrides[get_live_market_monitor] = lambda: monitor
    try:
        client = TestClient(app)
        sessions = client.get("/market-sessions").json()
        watchlist = client.get("/watchlist/active").json()
        dashboard = client.get("/dashboard/overview").json()
    finally:
        app.dependency_overrides.clear()

    assert sessions["crypto"]["status"] == "OPEN"
    assert sessions["forex"]["status"] == "CLOSED"
    assert watchlist["active_symbols"] == ["BTC-USD", "ETH-USD"]
    assert watchlist["skipped_symbols"] == ["EUR-USD", "GBP-USD"]
    assert dashboard["market_session_crypto_status"] == "OPEN"

    start.print_market_sessions(["BTC-USD", "EUR-USD"])
    output = capsys.readouterr().out
    assert "Market Sessions" in output
    assert "Active Watchlist" in output

    broker = PaperBrokerageEngine()
    lifecycle = TradeLifecycleManager(provider, monitor, broker)
    journal = PaperTradeJournal(broker, lifecycle, tmp_path / "journal.jsonl")
    reports = DailyReportEngine(journal, lifecycle, broker, monitor, reports_dir=tmp_path / "daily")
    orchestrator = PaperTradingOrchestrator(monitor, lifecycle, broker, journal, reports, PaperTradingOrchestratorConfig(generate_daily_report_after_cycle=False))
    campaign_manager = ValidationCampaignManager(tmp_path / "campaigns", journal)
    campaign = campaign_manager.start("Session Test")
    cycle = orchestrator.run_cycle()
    pipeline = CandidatePipelineDiagnosticsEngine(tmp_path / "pipeline.jsonl", campaigns_root=tmp_path / "campaigns")
    pipeline.record_cycle(
        cycle_id=cycle.cycle_id,
        campaign_id=campaign.campaign_id,
        started_at=cycle.started_at,
        completed_at=cycle.completed_at,
        monitor_result=cycle.monitor_result,
        orders_created=0,
        trades_opened=0,
        cycle_status=cycle.status,
        configured_symbols=tuple(monitor.config.symbols),
        configured_timeframes=tuple(monitor.config.timeframes),
        recent_market_diagnostics=(),
    )
    monkeypatch.setattr(pipeline_module, "current_candidate_pipeline_diagnostics", lambda: pipeline)
    summary = campaign_manager.summary(campaign.campaign_id)
    assert summary.markets_configured == 4
    assert summary.markets_analyzed == 2
    assert summary.markets_skipped == 2
    assert summary.skipped_by_market_closed == 2
