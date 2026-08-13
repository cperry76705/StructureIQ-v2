from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app, get_live_market_monitor, get_market_session_engine, get_opportunity_coverage_engine
from core.candidate_pipeline_diagnostics import (
    CandidatePipelineCycleDiagnostic,
    CandidatePipelineDiagnosticsEngine,
    CandidateSymbolPipelineDiagnostic,
)
from core.live_market_monitor import LiveMarketMonitor, MonitorConfig
from core.market_data import Candle
from core.market_session_engine import AssetClass, MarketSessionEngine, classify_symbol
from core.opportunity_coverage import OpportunityCoverageEngine
from core.paper_brokerage import PaperBrokerageEngine
from core.paper_trade_journal import PaperTradeJournal
from core.symbol_registry import DEFAULT_SYMBOL_UNIVERSE, get_symbol_registry
from core.trade_lifecycle_manager import TradeLifecycleManager


class _Provider:
    def get_candles(self, symbol, timeframe, lookback):
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


def _detail(symbol: str, *, created: bool = False, stage: str | None = None, reason: str | None = None):
    return CandidateSymbolPipelineDiagnostic(
        symbol=symbol,
        market_data_status="available",
        candles_received=100,
        timeframes_received=1,
        structure_status="completed",
        bias_status="bullish",
        setup_status="pullback",
        confidence_score=8.0 if created else 4.0,
        setup_quality_score=80.0,
        risk_status="available",
        candidate_status="created" if created else "rejected",
        final_outcome="candidate_created" if created else "candidate_rejected",
        rejection_stage=stage,
        rejection_reason=reason,
        exception_type=None,
        exception_message=None,
    )


def _cycle(campaign_id: str = "campaign-a"):
    return CandidatePipelineCycleDiagnostic(
        cycle_id=f"{campaign_id}-cycle",
        campaign_id=campaign_id,
        started_at="2026-08-10T18:00:00+00:00",
        completed_at="2026-08-10T18:01:00+00:00",
        symbols_requested=3,
        symbols_scanned=3,
        symbols_with_market_data=3,
        symbols_without_market_data=0,
        symbols_skipped=0,
        symbols_skipped_market_closed=0,
        candidates_created=1,
        candidates_rejected=2,
        orders_created=1,
        trades_opened=0,
        cycle_status="completed",
        cycle_duration_ms=10,
        symbol_diagnostics=(
            _detail("BTC-USD", created=True),
            _detail("EUR-USD", stage="CONFIDENCE", reason="directional_confidence"),
            _detail("GBP-USD", stage="RISK", reason="risk_filter"),
        ),
        persistence_errors=(),
        zero_candidate_explanation=None,
    )


def test_default_universe_and_provider_mappings():
    registry = get_symbol_registry()

    assert DEFAULT_SYMBOL_UNIVERSE == (
        "BTC-USD",
        "ETH-USD",
        "EUR-USD",
        "GBP-USD",
        "USD-JPY",
        "USD-CHF",
        "USD-CAD",
        "AUD-USD",
        "NZD-USD",
    )
    assert len(registry.default_symbols()) == 9
    for symbol in DEFAULT_SYMBOL_UNIVERSE[2:]:
        assert classify_symbol(symbol) is AssetClass.FOREX
    assert registry.provider_symbol("USD-JPY") == "USDJPY=X"
    assert registry.validate_provider_symbol("UNKNOWN").validation_status == "UNKNOWN_SYMBOL"


def test_session_aware_default_universe_weekend_and_weekday():
    weekend = MarketSessionEngine(clock=lambda: _dt(2026, 8, 8, 18))
    weekday = MarketSessionEngine(clock=lambda: _dt(2026, 8, 10, 18))

    assert weekend.active_watchlist(DEFAULT_SYMBOL_UNIVERSE).active_symbols == ("BTC-USD", "ETH-USD")
    assert weekday.active_watchlist(DEFAULT_SYMBOL_UNIVERSE).active_symbols == DEFAULT_SYMBOL_UNIVERSE


def test_monitor_defaults_to_nine_symbol_universe():
    assert MonitorConfig().symbols == list(DEFAULT_SYMBOL_UNIVERSE)


def test_opportunity_coverage_empty_populated_and_campaign_isolation(tmp_path: Path):
    pipeline = CandidatePipelineDiagnosticsEngine(tmp_path / "pipeline.jsonl", campaigns_root=tmp_path / "campaigns")
    assert OpportunityCoverageEngine(pipeline, None, campaigns_root=tmp_path / "campaigns").summary().markets_analyzed == 0

    pipeline._cycles.append(_cycle("campaign-a"))
    pipeline._cycles.append(_cycle("campaign-b"))
    engine = OpportunityCoverageEngine(pipeline, None, campaigns_root=tmp_path / "campaigns")

    report = engine.report(campaign_id="campaign-a")

    assert report.summary.markets_analyzed == 3
    assert report.summary.raw_setups == 3
    assert report.summary.candidates_created == 1
    assert report.summary.approved_candidates == 1
    assert report.funnel.reconciles is True
    assert report.terminal_reasons == {"CONFIDENCE": 1, "RISK": 1}
    assert (tmp_path / "campaigns" / "campaign-a" / "opportunity_coverage.json").exists()
    assert engine.summary(campaign_id="campaign-b").markets_analyzed == 3


def test_market_closed_excluded_and_provider_failure_separated(tmp_path: Path):
    pipeline = CandidatePipelineDiagnosticsEngine(tmp_path / "pipeline.jsonl", campaigns_root=tmp_path / "campaigns")
    skipped = CandidateSymbolPipelineDiagnostic(
        symbol="EUR-USD", market_data_status="skipped", candles_received=0, timeframes_received=0,
        structure_status="not_run", bias_status="not_run", setup_status="not_run",
        confidence_score=None, setup_quality_score=None, risk_status="not_run",
        candidate_status="skipped", final_outcome="market_session_skipped",
        rejection_stage=None, rejection_reason=None, exception_type=None, exception_message=None,
        analyzed=False, skipped=True, skipped_reason="Forex Market Closed",
    )
    provider_failure = CandidateSymbolPipelineDiagnostic(
        symbol="BTC-USD", market_data_status="error", candles_received=0, timeframes_received=0,
        structure_status="not_run", bias_status="not_run", setup_status="not_run",
        confidence_score=None, setup_quality_score=None, risk_status="not_run",
        candidate_status="not_created", final_outcome="provider_or_analysis_error",
        rejection_stage="MARKET_DATA", rejection_reason="market data or analysis failed",
        exception_type="MarketDataError", exception_message="provider failed",
    )
    pipeline._cycles.append(CandidatePipelineCycleDiagnostic(
        cycle_id="cycle", campaign_id=None, started_at="2026-08-08T18:00:00+00:00",
        completed_at="2026-08-08T18:01:00+00:00", symbols_requested=2, symbols_scanned=1,
        symbols_with_market_data=0, symbols_without_market_data=1, symbols_skipped=1,
        symbols_skipped_market_closed=1, candidates_created=0, candidates_rejected=1,
        orders_created=0, trades_opened=0, cycle_status="completed", cycle_duration_ms=1,
        symbol_diagnostics=(skipped, provider_failure), persistence_errors=(),
        zero_candidate_explanation=None,
    ))

    report = OpportunityCoverageEngine(pipeline, None).report()

    assert report.summary.markets_analyzed == 0
    assert report.terminal_reasons == {"PROVIDER_FAILURE": 1}


def test_synthetic_fixtures_excluded_from_performance(tmp_path: Path):
    provider = _Provider()
    monitor = LiveMarketMonitor(provider, MonitorConfig(symbols=["BTC-USD"], write_events=False), analysis_engine_factory=lambda _: _Analysis())
    broker = PaperBrokerageEngine()
    lifecycle = TradeLifecycleManager(provider, monitor, broker)
    journal = PaperTradeJournal(broker, lifecycle, tmp_path / "journal.jsonl")
    synthetic = SimpleNamespace(
        trade_id="fixture", source_event_id=None, symbol="BTC-USD", timeframe="5m",
        higher_timeframe="1h", action="buy", setup="fixture", strategy="fixture",
        entry_price=100, stop_loss=99, target=102, target_r=2, risk_amount=100,
        position_size=1, status="closed", opened_at="2026-08-10T00:00:00+00:00",
        closed_at="2026-08-10T01:00:00+00:00", exit_price=99, realized_r=-1,
        realized_pl=-100, metadata={"test_fixture": True, "synthetic_recovery_test": True, "exclude_from_performance": True},
    )
    journal._on_brokerage_event("paper_trade_opened", synthetic, broker.account())
    journal._on_brokerage_event("paper_trade_closed", synthetic, broker.account())

    report = OpportunityCoverageEngine(CandidatePipelineDiagnosticsEngine(tmp_path / "p.jsonl"), journal).report()

    assert report.symbol_performance[0].trades == 0


def test_opportunity_api_dashboard_and_readiness(tmp_path: Path):
    pipeline = CandidatePipelineDiagnosticsEngine(tmp_path / "pipeline.jsonl", campaigns_root=tmp_path / "campaigns")
    pipeline._cycles.append(_cycle("api-campaign"))
    engine = OpportunityCoverageEngine(pipeline, None, campaigns_root=tmp_path / "campaigns")
    sessions = MarketSessionEngine(clock=lambda: _dt(2026, 8, 8, 18))
    monitor = LiveMarketMonitor(
        _Provider(),
        MonitorConfig(symbols=list(DEFAULT_SYMBOL_UNIVERSE), timeframes=["5m"], write_events=False),
        analysis_engine_factory=lambda _: _Analysis(),
        market_sessions=sessions,
    )
    app.dependency_overrides[get_opportunity_coverage_engine] = lambda: engine
    app.dependency_overrides[get_market_session_engine] = lambda: sessions
    app.dependency_overrides[get_live_market_monitor] = lambda: monitor
    try:
        client = TestClient(app)
        summary = client.get("/opportunity-coverage/summary").json()
        by_symbol = client.get("/opportunity-coverage/by-symbol").json()
        readiness = client.get("/validation-readiness/7-day").json()
        dashboard = client.get("/dashboard/overview").json()
        provider_validation = client.get("/symbols/provider-validation").json()
    finally:
        app.dependency_overrides.clear()

    assert summary["markets_analyzed"] == 3
    assert any(row["symbol"] == "EUR-USD" for row in by_symbol)
    # A version bump can intentionally invalidate the persisted clean baseline until
    # operators create and clear a new one; that does not make coverage unavailable.
    assert readiness["status"] in {"READY", "WATCHLIST", "NOT_READY"}
    if readiness["status"] == "NOT_READY":
        assert readiness["opportunity_coverage"] == "PASS"
    assert readiness["configured_symbols"] == 9
    assert dashboard["trading_universe_configured"] == 9
    assert len(provider_validation) == 9
