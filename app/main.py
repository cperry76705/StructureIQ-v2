"""FastAPI entrypoint for the StructureIQ service."""

from functools import lru_cache
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, status

from app.config import APP_DESCRIPTION, APP_NAME, APP_VERSION
from core.analysis_engine import AnalysisEngine
from core.backtesting import BacktestRequest, BacktestResult, BacktestingEngine
from core.calibration import CalibrationEngine, CalibrationRequest, CalibrationResult
from core.journal import JournalEntry, JournalStore, JournalSummary, TradeOutcome
from core.market_data import MarketDataError, MarketDataProvider
from core.live_market_monitor import (
    LiveMarketMonitor,
    MonitorConfig,
    MonitorCycleResult,
    MonitorEvent,
    MonitorStatus,
    get_global_live_market_monitor,
)
from core.paper_brokerage import (
    PaperAccount,
    PaperAccountConfig,
    PaperBrokerageEngine,
    PaperBrokerageError,
    PaperCloseRequest,
    PaperOpenRequest,
    PaperPerformance,
    PaperTrade,
    get_global_paper_brokerage,
)
from core.trade_lifecycle_manager import (
    ApproveCandidateRequest,
    CancelOrderRequest,
    LifecycleCycleResult,
    LifecycleError,
    LifecycleEvent,
    LifecycleStatus,
    PendingPaperOrder,
    RejectCandidateRequest,
    TradeLifecycleManager,
    get_global_trade_lifecycle_manager,
)
from core.paper_trade_journal import (
    PaperJournalExport,
    PaperTradeJournal,
    PaperTradeJournalEntry,
    PaperTradeJournalSummary,
    get_global_paper_trade_journal,
)
from core.daily_report_engine import (
    DailyPaperTradingReport,
    DailyReportEngine,
    DailyReportError,
    DailyReportGenerateRequest,
    DailyReportGPTPayload,
    DailyReportGPTRequest,
    DailyReportListItem,
    get_global_daily_report_engine,
)
from core.paper_trading_orchestrator import (
    OrchestratorAction,
    PaperTradingCycleResult,
    PaperTradingOrchestrator,
    PaperTradingOrchestratorConfig,
    PaperTradingOrchestratorStatus,
    get_global_paper_trading_orchestrator,
)
from core.daily_report_scheduler import (
    DailyReportScheduler,
    DailyReportSchedulerConfig,
    DailyReportSchedulerStatus,
    SchedulerHistoryItem,
    SchedulerRunNowRequest,
    get_global_daily_report_scheduler,
)
from core.system_health import (
    HealthDimension,
    SystemErrors,
    SystemHealthEngine,
    SystemHealthReport,
    SystemReadiness,
)
from core.system_validation import (
    SystemValidationHarness,
    SystemValidationResult,
)
from core.continuous_paper_trading import (
    ContinuousPaperCycleResult,
    ContinuousPaperEvent,
    ContinuousPaperSession,
    ContinuousPaperStatus,
    ContinuousPaperTradingConfig,
    ContinuousPaperTradingRuntime,
    get_global_continuous_paper_trading,
)
from core.candidate_diagnostics import (
    CandidateDiagnostic,
    CandidateDiagnosticsEngine,
    CandidateDiagnosticsSummary,
    get_global_candidate_diagnostics,
)
from core.providers.yahoo import YahooFinanceMarketDataProvider
from core.research_engine import (
    ContinuousResearchRankings,
    ContinuousResearchStatus,
    ResearchCombination,
    ResearchEngine,
    ResearchRefreshRequest,
    ResearchWindow,
    get_global_research_engine,
)
from core.research_dashboard import (
    DashboardOverview,
    DashboardReadiness,
    DashboardRecommendations,
    DashboardRisks,
    DashboardSetups,
    DashboardStrategies,
    DashboardSymbols,
    ResearchDashboardService,
    latest_calibration,
    store_latest_calibration,
)
from core.symbol_profile_engine import (
    SymbolProfileEngine,
    get_global_symbol_profile_engine,
)
from models.schemas import AnalysisRequest, AnalysisResponse, HealthResponse

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description=APP_DESCRIPTION,
)


@lru_cache
def get_market_data_provider() -> MarketDataProvider:
    """Dependency-injection seam for selecting a market data adapter."""
    return YahooFinanceMarketDataProvider()


def get_symbol_profile_engine() -> SymbolProfileEngine:
    """Return the durable research-only symbol profile store."""

    return get_global_symbol_profile_engine()


def get_candidate_diagnostics_engine() -> CandidateDiagnosticsEngine:
    return get_global_candidate_diagnostics()


def get_analysis_engine(
    provider: MarketDataProvider = Depends(get_market_data_provider),
    symbol_profiles: SymbolProfileEngine = Depends(get_symbol_profile_engine),
) -> AnalysisEngine:
    """Build the engine from the selected provider through FastAPI DI."""
    return AnalysisEngine(provider, symbol_profile_engine=symbol_profiles)


@lru_cache
def get_journal_store() -> JournalStore:
    """Return the local append-only journal store."""

    return JournalStore()


def get_research_engine() -> ResearchEngine:
    """Return the process-local, read-only continuous research store."""

    return get_global_research_engine()


def get_live_market_monitor(
    provider: MarketDataProvider = Depends(get_market_data_provider),
) -> LiveMarketMonitor:
    """Return the explicitly controlled process-local market monitor."""

    return get_global_live_market_monitor(provider)


def get_paper_brokerage() -> PaperBrokerageEngine:
    """Return the process-local advisory paper account."""

    return get_global_paper_brokerage()


def get_trade_lifecycle_manager(
    provider: MarketDataProvider = Depends(get_market_data_provider),
    monitor: LiveMarketMonitor = Depends(get_live_market_monitor),
    broker: PaperBrokerageEngine = Depends(get_paper_brokerage),
) -> TradeLifecycleManager:
    return get_global_trade_lifecycle_manager(provider, monitor, broker)


def get_paper_trade_journal(
    broker: PaperBrokerageEngine = Depends(get_paper_brokerage),
    lifecycle: TradeLifecycleManager = Depends(get_trade_lifecycle_manager),
) -> PaperTradeJournal:
    return get_global_paper_trade_journal(broker, lifecycle)


def get_research_dashboard_service(
    symbol_profiles: SymbolProfileEngine = Depends(get_symbol_profile_engine),
    research_engine: ResearchEngine = Depends(get_research_engine),
) -> ResearchDashboardService:
    """Return the compact read-only dashboard summarizer."""

    return ResearchDashboardService(
        symbol_profiles=symbol_profiles,
        research_engine=research_engine,
    )


def get_daily_report_engine(
    journal: PaperTradeJournal = Depends(get_paper_trade_journal),
    lifecycle: TradeLifecycleManager = Depends(get_trade_lifecycle_manager),
    broker: PaperBrokerageEngine = Depends(get_paper_brokerage),
    monitor: LiveMarketMonitor = Depends(get_live_market_monitor),
    dashboard: ResearchDashboardService = Depends(get_research_dashboard_service),
) -> DailyReportEngine:
    return get_global_daily_report_engine(
        journal, lifecycle, broker, monitor,
        calibration_result=latest_calibration(),
        readiness_context=dashboard.readiness(),
        risk_context=dashboard.risks(),
    )


def get_paper_trading_orchestrator(
    monitor: LiveMarketMonitor = Depends(get_live_market_monitor),
    lifecycle: TradeLifecycleManager = Depends(get_trade_lifecycle_manager),
    broker: PaperBrokerageEngine = Depends(get_paper_brokerage),
    journal: PaperTradeJournal = Depends(get_paper_trade_journal),
    daily_reports: DailyReportEngine = Depends(get_daily_report_engine),
) -> PaperTradingOrchestrator:
    return get_global_paper_trading_orchestrator(
        monitor, lifecycle, broker, journal, daily_reports
    )


def get_daily_report_scheduler(
    reports: DailyReportEngine = Depends(get_daily_report_engine),
) -> DailyReportScheduler:
    return get_global_daily_report_scheduler(reports)


def get_system_health_engine(
    provider: MarketDataProvider = Depends(get_market_data_provider),
    monitor: LiveMarketMonitor = Depends(get_live_market_monitor),
    broker: PaperBrokerageEngine = Depends(get_paper_brokerage),
    lifecycle: TradeLifecycleManager = Depends(get_trade_lifecycle_manager),
    journal: PaperTradeJournal = Depends(get_paper_trade_journal),
    reports: DailyReportEngine = Depends(get_daily_report_engine),
    scheduler: DailyReportScheduler = Depends(get_daily_report_scheduler),
    orchestrator: PaperTradingOrchestrator = Depends(get_paper_trading_orchestrator),
) -> SystemHealthEngine:
    return SystemHealthEngine(
        market_data_provider=provider, live_monitor=monitor,
        paper_brokerage=broker, trade_lifecycle_manager=lifecycle,
        paper_trade_journal=journal, daily_report_engine=reports,
        daily_report_scheduler=scheduler,
        paper_trading_orchestrator=orchestrator,
    )


def get_system_validation_harness(
    health: SystemHealthEngine = Depends(get_system_health_engine),
    provider: MarketDataProvider = Depends(get_market_data_provider),
    monitor: LiveMarketMonitor = Depends(get_live_market_monitor),
    broker: PaperBrokerageEngine = Depends(get_paper_brokerage),
    lifecycle: TradeLifecycleManager = Depends(get_trade_lifecycle_manager),
    journal: PaperTradeJournal = Depends(get_paper_trade_journal),
    reports: DailyReportEngine = Depends(get_daily_report_engine),
    scheduler: DailyReportScheduler = Depends(get_daily_report_scheduler),
    orchestrator: PaperTradingOrchestrator = Depends(get_paper_trading_orchestrator),
    dashboard: ResearchDashboardService = Depends(get_research_dashboard_service),
) -> SystemValidationHarness:
    return SystemValidationHarness(
        health_engine=health, market_data_provider=provider,
        monitor=monitor, broker=broker, lifecycle=lifecycle,
        journal=journal, reports=reports, scheduler=scheduler,
        orchestrator=orchestrator, dashboard=dashboard,
        api_paths_provider=lambda: set(app.openapi()["paths"]),
    )


def get_continuous_paper_trading(
    orchestrator: PaperTradingOrchestrator = Depends(get_paper_trading_orchestrator),
    health: SystemHealthEngine = Depends(get_system_health_engine),
    validation: SystemValidationHarness = Depends(get_system_validation_harness),
    broker: PaperBrokerageEngine = Depends(get_paper_brokerage),
    scheduler: DailyReportScheduler = Depends(get_daily_report_scheduler),
) -> ContinuousPaperTradingRuntime:
    return get_global_continuous_paper_trading(orchestrator, health, validation, broker, scheduler)


def _research_snapshot(
    engine: ResearchEngine,
    window: ResearchWindow,
    custom_lookback: int | None,
):
    """Resolve a rolling research snapshot with useful query validation."""

    try:
        return engine.snapshot(window, custom_lookback)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["service"],
    summary="Check service health",
)
def health() -> HealthResponse:
    """Return a lightweight liveness response."""

    return HealthResponse(status="ok", app=APP_NAME)


@app.post(
    "/analysis",
    response_model=AnalysisResponse,
    tags=["analysis"],
    summary="Analyze current market structure",
)
def analysis(
    request: AnalysisRequest,
    engine: AnalysisEngine = Depends(get_analysis_engine),
) -> AnalysisResponse:
    """Run the complete StructureIQ decision-support pipeline."""

    try:
        return engine.analyze(request)
    except MarketDataError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Market data unavailable: {exc}",
        ) from exc


@app.post(
    "/journal",
    response_model=JournalEntry,
    tags=["journal"],
    summary="Append a journal entry",
)
def append_journal_entry(
    payload: dict[str, Any],
    store: JournalStore = Depends(get_journal_store),
) -> JournalEntry:
    """Persist a journal entry or compatible analysis snapshot."""

    entry = JournalEntry.from_payload(payload)
    return store.append_entry(entry)


@app.get(
    "/journal",
    response_model=list[JournalEntry],
    tags=["journal"],
    summary="List journal entries",
)
def list_journal_entries(
    symbol: str | None = None,
    timeframe: str | None = None,
    outcome: TradeOutcome | None = None,
    store: JournalStore = Depends(get_journal_store),
) -> list[JournalEntry]:
    """Return journal entries, optionally filtered by public fields."""

    return store.list_entries(
        symbol=symbol,
        timeframe=timeframe,
        outcome=outcome,
    )


@app.get(
    "/journal/summary",
    response_model=JournalSummary,
    tags=["journal"],
    summary="Summarize journal outcomes",
)
def journal_summary(
    store: JournalStore = Depends(get_journal_store),
) -> JournalSummary:
    """Aggregate journal counts and realized R performance."""

    return store.summarize_entries()


@app.post(
    "/backtest",
    response_model=BacktestResult,
    tags=["research"],
    summary="Run a deterministic historical backtest",
)
def backtest(
    request: BacktestRequest,
    provider: MarketDataProvider = Depends(get_market_data_provider),
) -> BacktestResult:
    """Evaluate the existing analysis pipeline over historical windows."""

    try:
        return BacktestingEngine(provider).run(request)
    except MarketDataError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Market data unavailable: {exc}",
        ) from exc


@app.post(
    "/calibrate",
    response_model=CalibrationResult,
    tags=["research"],
    summary="Evaluate behavior across backtest combinations",
)
def calibrate(
    request: CalibrationRequest,
    provider: MarketDataProvider = Depends(get_market_data_provider),
    symbol_profiles: SymbolProfileEngine = Depends(get_symbol_profile_engine),
) -> CalibrationResult:
    """Aggregate backtests and return observational recommendations."""

    try:
        result = CalibrationEngine(
            provider,
            symbol_profile_engine=symbol_profiles,
        ).run(request)
        store_latest_calibration(result)
        return result
    except MarketDataError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Market data unavailable: {exc}",
        ) from exc


@app.get(
    "/dashboard/overview",
    response_model=DashboardOverview,
    tags=["dashboard"],
    summary="Read a compact research dashboard overview",
)
def dashboard_overview(
    service: ResearchDashboardService = Depends(get_research_dashboard_service),
) -> DashboardOverview:
    """Summarize the latest available research state without recalibration."""

    return service.overview()


@app.get(
    "/dashboard/symbols",
    response_model=DashboardSymbols,
    tags=["dashboard"],
    summary="Rank persisted symbol research profiles",
)
def dashboard_symbols(
    service: ResearchDashboardService = Depends(get_research_dashboard_service),
) -> DashboardSymbols:
    """Return compact symbol profile rows."""

    return service.symbols()


@app.get(
    "/dashboard/strategies",
    response_model=DashboardStrategies,
    tags=["dashboard"],
    summary="Rank historical strategy ratings",
)
def dashboard_strategies(
    service: ResearchDashboardService = Depends(get_research_dashboard_service),
) -> DashboardStrategies:
    """Return compact strategy rating rows."""

    return service.strategies()


@app.get(
    "/dashboard/setups",
    response_model=DashboardSetups,
    tags=["dashboard"],
    summary="Rank historical setup ratings",
)
def dashboard_setups(
    service: ResearchDashboardService = Depends(get_research_dashboard_service),
) -> DashboardSetups:
    """Return compact setup rating rows."""

    return service.setups()


@app.get(
    "/dashboard/readiness",
    response_model=DashboardReadiness,
    tags=["dashboard"],
    summary="Summarize paper-trading readiness research",
)
def dashboard_readiness(
    service: ResearchDashboardService = Depends(get_research_dashboard_service),
) -> DashboardReadiness:
    """Return conservative paper-trading readiness from existing evidence."""

    return service.readiness()


@app.get(
    "/dashboard/risks",
    response_model=DashboardRisks,
    tags=["dashboard"],
    summary="Summarize research risk warnings",
)
def dashboard_risks(
    service: ResearchDashboardService = Depends(get_research_dashboard_service),
) -> DashboardRisks:
    """Return compact risk warnings and data availability state."""

    return service.risks()


@app.get(
    "/dashboard/recommendations",
    response_model=DashboardRecommendations,
    tags=["dashboard"],
    summary="Return prioritized dashboard recommendations",
)
def dashboard_recommendations(
    service: ResearchDashboardService = Depends(get_research_dashboard_service),
) -> DashboardRecommendations:
    """Return prioritized advisory action items from existing research."""

    return service.recommendations()


@app.get(
    "/monitor/status",
    response_model=MonitorStatus,
    tags=["monitor"],
    summary="Read advisory live-monitor status",
)
def monitor_status(
    monitor: LiveMarketMonitor = Depends(get_live_market_monitor),
) -> MonitorStatus:
    return monitor.status()


@app.post(
    "/monitor/run-once",
    response_model=MonitorCycleResult,
    tags=["monitor"],
    summary="Run one synchronous monitoring cycle",
)
def monitor_run_once(
    config: MonitorConfig | None = None,
    monitor: LiveMarketMonitor = Depends(get_live_market_monitor),
) -> MonitorCycleResult:
    try:
        return monitor.run_once(config)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post(
    "/monitor/start",
    response_model=MonitorStatus,
    tags=["monitor"],
    summary="Start the advisory background monitor",
)
def monitor_start(
    config: MonitorConfig | None = None,
    monitor: LiveMarketMonitor = Depends(get_live_market_monitor),
) -> MonitorStatus:
    try:
        return monitor.start(config)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post(
    "/monitor/stop",
    response_model=MonitorStatus,
    tags=["monitor"],
    summary="Stop the advisory background monitor",
)
def monitor_stop(
    monitor: LiveMarketMonitor = Depends(get_live_market_monitor),
) -> MonitorStatus:
    return monitor.stop()


@app.get(
    "/monitor/events",
    response_model=list[MonitorEvent],
    tags=["monitor"],
    summary="List recent candidate monitor events",
)
def monitor_events(
    limit: int | None = None,
    monitor: LiveMarketMonitor = Depends(get_live_market_monitor),
) -> list[MonitorEvent]:
    if limit is not None and not 1 <= limit <= 10_000:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 10000")
    return list(monitor.events(limit))


@app.get(
    "/paper/account",
    response_model=PaperAccount,
    tags=["paper"],
    summary="Read the simulated paper account",
)
def paper_account(
    latest_prices: str | None = None,
    broker: PaperBrokerageEngine = Depends(get_paper_brokerage),
) -> PaperAccount:
    return broker.account(_parse_latest_prices(latest_prices))


@app.post(
    "/paper/reset",
    response_model=PaperAccount,
    tags=["paper"],
    summary="Reset the simulated paper account",
)
def paper_reset(
    config: PaperAccountConfig | None = None,
    broker: PaperBrokerageEngine = Depends(get_paper_brokerage),
) -> PaperAccount:
    return broker.reset(config)


@app.post(
    "/paper/open",
    response_model=PaperTrade,
    tags=["paper"],
    summary="Explicitly open a simulated paper position",
)
def paper_open(
    request: PaperOpenRequest,
    broker: PaperBrokerageEngine = Depends(get_paper_brokerage),
    monitor: LiveMarketMonitor = Depends(get_live_market_monitor),
    journal: PaperTradeJournal = Depends(get_paper_trade_journal),
) -> PaperTrade:
    del journal
    try:
        if request.event_id:
            event = monitor.find_event(request.event_id)
            if event is None:
                raise HTTPException(status_code=404, detail="monitor candidate was not found")
            if event.paper_trade_created:
                raise HTTPException(status_code=409, detail="monitor candidate already created a paper trade")
            trade = broker.open_monitor_event(
                event,
                risk_per_trade_percent=request.risk_per_trade_percent,
                allow_duplicate=request.allow_duplicate,
            )
            monitor.mark_paper_trade_created(event.event_id)
            return trade
        return broker.open_position(request)
    except PaperBrokerageError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post(
    "/paper/close",
    response_model=PaperTrade,
    tags=["paper"],
    summary="Close a simulated paper position",
)
def paper_close(
    request: PaperCloseRequest,
    broker: PaperBrokerageEngine = Depends(get_paper_brokerage),
    journal: PaperTradeJournal = Depends(get_paper_trade_journal),
) -> PaperTrade:
    del journal
    try:
        return broker.close_position(request.trade_id, request.exit_price)
    except PaperBrokerageError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get(
    "/paper/open-positions",
    response_model=list[PaperTrade],
    tags=["paper"],
    summary="List simulated open positions",
)
def paper_open_positions(
    latest_prices: str | None = None,
    broker: PaperBrokerageEngine = Depends(get_paper_brokerage),
) -> list[PaperTrade]:
    return list(broker.open_positions(_parse_latest_prices(latest_prices)))


@app.get(
    "/paper/closed-trades",
    response_model=list[PaperTrade],
    tags=["paper"],
    summary="List closed simulated trades",
)
def paper_closed_trades(
    broker: PaperBrokerageEngine = Depends(get_paper_brokerage),
) -> list[PaperTrade]:
    return list(broker.closed_trades())


@app.get(
    "/paper/performance",
    response_model=PaperPerformance,
    tags=["paper"],
    summary="Summarize simulated paper performance",
)
def paper_performance(
    broker: PaperBrokerageEngine = Depends(get_paper_brokerage),
) -> PaperPerformance:
    return broker.performance()


@app.get("/lifecycle/status", response_model=LifecycleStatus, tags=["lifecycle"])
def lifecycle_status(manager: TradeLifecycleManager = Depends(get_trade_lifecycle_manager)) -> LifecycleStatus:
    return manager.status()


@app.post("/lifecycle/run-once", response_model=LifecycleCycleResult, tags=["lifecycle"])
def lifecycle_run_once(manager: TradeLifecycleManager = Depends(get_trade_lifecycle_manager), journal: PaperTradeJournal = Depends(get_paper_trade_journal)) -> LifecycleCycleResult:
    del journal
    return manager.run_once()


@app.post("/lifecycle/approve-candidate", response_model=PendingPaperOrder, tags=["lifecycle"])
def lifecycle_approve_candidate(request: ApproveCandidateRequest, manager: TradeLifecycleManager = Depends(get_trade_lifecycle_manager), journal: PaperTradeJournal = Depends(get_paper_trade_journal)) -> PendingPaperOrder:
    del journal
    try:
        return manager.approve_candidate(request)
    except LifecycleError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/lifecycle/reject-candidate", response_model=LifecycleEvent, tags=["lifecycle"])
def lifecycle_reject_candidate(request: RejectCandidateRequest, manager: TradeLifecycleManager = Depends(get_trade_lifecycle_manager), journal: PaperTradeJournal = Depends(get_paper_trade_journal)) -> LifecycleEvent:
    del journal
    try:
        return manager.reject_candidate(request)
    except LifecycleError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/lifecycle/cancel-order", response_model=LifecycleEvent, tags=["lifecycle"])
def lifecycle_cancel_order(request: CancelOrderRequest, manager: TradeLifecycleManager = Depends(get_trade_lifecycle_manager), journal: PaperTradeJournal = Depends(get_paper_trade_journal)) -> LifecycleEvent:
    del journal
    try:
        return manager.cancel_order(request)
    except LifecycleError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/lifecycle/events", response_model=list[LifecycleEvent], tags=["lifecycle"])
def lifecycle_events(limit: int | None = None, manager: TradeLifecycleManager = Depends(get_trade_lifecycle_manager)) -> list[LifecycleEvent]:
    if limit is not None and not 1 <= limit <= 100_000:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 100000")
    return list(manager.events(limit))


@app.get("/lifecycle/pending-orders", response_model=list[PendingPaperOrder], tags=["lifecycle"])
def lifecycle_pending_orders(manager: TradeLifecycleManager = Depends(get_trade_lifecycle_manager)) -> list[PendingPaperOrder]:
    return list(manager.pending_orders())


@app.get("/lifecycle/open-trades", response_model=list[PaperTrade], tags=["lifecycle"])
def lifecycle_open_trades(manager: TradeLifecycleManager = Depends(get_trade_lifecycle_manager)) -> list[PaperTrade]:
    return list(manager.open_trades())


@app.get("/lifecycle/closed-trades", response_model=list[PaperTrade], tags=["lifecycle"])
def lifecycle_closed_trades(manager: TradeLifecycleManager = Depends(get_trade_lifecycle_manager)) -> list[PaperTrade]:
    return list(manager.closed_trades())


@app.get("/paper-journal/entries", response_model=list[PaperTradeJournalEntry], tags=["paper-journal"])
def paper_journal_entries(journal: PaperTradeJournal = Depends(get_paper_trade_journal)) -> list[PaperTradeJournalEntry]:
    return list(journal.entries())


@app.get("/paper-journal/summary", response_model=PaperTradeJournalSummary, tags=["paper-journal"])
def paper_journal_summary(journal: PaperTradeJournal = Depends(get_paper_trade_journal)) -> PaperTradeJournalSummary:
    return journal.summary()


@app.get("/paper-journal/trade/{trade_id}", response_model=PaperTradeJournalEntry, tags=["paper-journal"])
def paper_journal_trade(trade_id: str, journal: PaperTradeJournal = Depends(get_paper_trade_journal)) -> PaperTradeJournalEntry:
    entry = journal.get_trade(trade_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="paper journal trade was not found")
    return entry


@app.post("/paper-journal/rebuild-from-paper-state", response_model=PaperTradeJournalSummary, tags=["paper-journal"])
def paper_journal_rebuild(journal: PaperTradeJournal = Depends(get_paper_trade_journal)) -> PaperTradeJournalSummary:
    return journal.rebuild_from_paper_state()


@app.post("/paper-journal/export", response_model=PaperJournalExport, tags=["paper-journal"])
def paper_journal_export(journal: PaperTradeJournal = Depends(get_paper_trade_journal)) -> PaperJournalExport:
    return journal.export()


@app.get("/reports/daily", response_model=list[DailyReportListItem], tags=["reports"])
def daily_reports(engine: DailyReportEngine = Depends(get_daily_report_engine)) -> list[DailyReportListItem]:
    return list(engine.list_reports())


@app.post("/reports/daily/generate", response_model=DailyPaperTradingReport, tags=["reports"])
def daily_report_generate(request: DailyReportGenerateRequest, engine: DailyReportEngine = Depends(get_daily_report_engine)) -> DailyPaperTradingReport:
    try:
        return engine.generate(request.report_date, overwrite=request.overwrite)
    except DailyReportError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/reports/daily/export-gpt-payload", response_model=DailyReportGPTPayload, tags=["reports"])
def daily_report_gpt_payload(request: DailyReportGPTRequest, engine: DailyReportEngine = Depends(get_daily_report_engine)) -> DailyReportGPTPayload:
    try:
        return engine.export_gpt_payload(request.report_date, generate_if_missing=request.generate_if_missing)
    except DailyReportError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/reports/daily/{report_date}", response_model=DailyPaperTradingReport, tags=["reports"])
def daily_report_by_date(report_date: str, engine: DailyReportEngine = Depends(get_daily_report_engine)) -> DailyPaperTradingReport:
    try:
        report = engine.get(report_date)
    except DailyReportError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if report is None:
        raise HTTPException(status_code=404, detail="daily report was not found")
    return report


@app.get("/paper-trading/status", response_model=PaperTradingOrchestratorStatus, tags=["paper-trading"])
def paper_trading_status(orchestrator: PaperTradingOrchestrator = Depends(get_paper_trading_orchestrator)) -> PaperTradingOrchestratorStatus:
    return orchestrator.status()


@app.post("/paper-trading/run-cycle", response_model=PaperTradingCycleResult, tags=["paper-trading"])
def paper_trading_run_cycle(config: PaperTradingOrchestratorConfig | None = None, orchestrator: PaperTradingOrchestrator = Depends(get_paper_trading_orchestrator)) -> PaperTradingCycleResult:
    try:
        return orchestrator.run_cycle(config)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/paper-trading/start", response_model=PaperTradingOrchestratorStatus, tags=["paper-trading"])
def paper_trading_start(config: PaperTradingOrchestratorConfig | None = None, orchestrator: PaperTradingOrchestrator = Depends(get_paper_trading_orchestrator)) -> PaperTradingOrchestratorStatus:
    try:
        return orchestrator.start(config)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/paper-trading/stop", response_model=PaperTradingOrchestratorStatus, tags=["paper-trading"])
def paper_trading_stop(orchestrator: PaperTradingOrchestrator = Depends(get_paper_trading_orchestrator)) -> PaperTradingOrchestratorStatus:
    return orchestrator.stop()


@app.get("/paper-trading/cycles", response_model=list[PaperTradingCycleResult], tags=["paper-trading"])
def paper_trading_cycles(limit: int | None = None, orchestrator: PaperTradingOrchestrator = Depends(get_paper_trading_orchestrator)) -> list[PaperTradingCycleResult]:
    if limit is not None and not 1 <= limit <= 10_000:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 10000")
    return list(orchestrator.cycles(limit))


@app.get("/paper-trading/recent-actions", response_model=list[OrchestratorAction], tags=["paper-trading"])
def paper_trading_recent_actions(limit: int | None = None, orchestrator: PaperTradingOrchestrator = Depends(get_paper_trading_orchestrator)) -> list[OrchestratorAction]:
    if limit is not None and not 1 <= limit <= 10_000:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 10000")
    return list(orchestrator.recent_actions(limit))


@app.get("/reports/scheduler/status", response_model=DailyReportSchedulerStatus, tags=["reports"])
def report_scheduler_status(scheduler: DailyReportScheduler = Depends(get_daily_report_scheduler)) -> DailyReportSchedulerStatus:
    return scheduler.status()


@app.post("/reports/scheduler/start", response_model=DailyReportSchedulerStatus, tags=["reports"])
def report_scheduler_start(config: DailyReportSchedulerConfig | None = None, scheduler: DailyReportScheduler = Depends(get_daily_report_scheduler)) -> DailyReportSchedulerStatus:
    try:
        return scheduler.start(config)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/reports/scheduler/stop", response_model=DailyReportSchedulerStatus, tags=["reports"])
def report_scheduler_stop(scheduler: DailyReportScheduler = Depends(get_daily_report_scheduler)) -> DailyReportSchedulerStatus:
    return scheduler.stop()


@app.post("/reports/scheduler/run-now", response_model=SchedulerHistoryItem, tags=["reports"])
def report_scheduler_run_now(request: SchedulerRunNowRequest, scheduler: DailyReportScheduler = Depends(get_daily_report_scheduler)) -> SchedulerHistoryItem:
    return scheduler.run_now(request.report_date, request.overwrite)


@app.get("/reports/scheduler/history", response_model=list[SchedulerHistoryItem], tags=["reports"])
def report_scheduler_history(limit: int | None = None, scheduler: DailyReportScheduler = Depends(get_daily_report_scheduler)) -> list[SchedulerHistoryItem]:
    if limit is not None and not 1 <= limit <= 10_000:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 10000")
    return list(scheduler.history(limit))


@app.get("/system/health", response_model=SystemHealthReport, tags=["system"])
def system_health(engine: SystemHealthEngine = Depends(get_system_health_engine)) -> SystemHealthReport:
    return engine.check()


@app.get("/system/readiness", response_model=SystemReadiness, tags=["system"])
def system_readiness(engine: SystemHealthEngine = Depends(get_system_health_engine)) -> SystemReadiness:
    return engine.readiness()


@app.get("/system/errors", response_model=SystemErrors, tags=["system"])
def system_errors(engine: SystemHealthEngine = Depends(get_system_health_engine)) -> SystemErrors:
    return engine.errors()


@app.get("/system/storage", response_model=HealthDimension, tags=["system"])
def system_storage(engine: SystemHealthEngine = Depends(get_system_health_engine)) -> HealthDimension:
    return engine.storage()


@app.get("/system/components", response_model=list[HealthDimension], tags=["system"])
def system_components(engine: SystemHealthEngine = Depends(get_system_health_engine)) -> list[HealthDimension]:
    return list(engine.components())


@app.get("/system/validation", response_model=SystemValidationResult | None, tags=["system"])
def system_validation_latest(harness: SystemValidationHarness = Depends(get_system_validation_harness)) -> SystemValidationResult | None:
    return harness.latest()


@app.post("/system/validation/run", response_model=SystemValidationResult, tags=["system"])
def system_validation_run(harness: SystemValidationHarness = Depends(get_system_validation_harness)) -> SystemValidationResult:
    return harness.run()


@app.get("/system/validation/history", response_model=list[SystemValidationResult], tags=["system"])
def system_validation_history(limit: int | None = None, harness: SystemValidationHarness = Depends(get_system_validation_harness)) -> list[SystemValidationResult]:
    if limit is not None and not 1 <= limit <= 10_000:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 10000")
    return list(harness.history(limit))


@app.post("/system/validation/reset-history", response_model=dict[str, int], tags=["system"])
def system_validation_reset(harness: SystemValidationHarness = Depends(get_system_validation_harness)) -> dict[str, int]:
    return {"cleared_runs": harness.reset_history()}


@app.get("/continuous-paper/status", response_model=ContinuousPaperStatus, tags=["continuous-paper"])
def continuous_paper_status(runtime: ContinuousPaperTradingRuntime = Depends(get_continuous_paper_trading)) -> ContinuousPaperStatus:
    return runtime.status()


@app.post("/continuous-paper/start", response_model=ContinuousPaperStatus, tags=["continuous-paper"])
def continuous_paper_start(config: ContinuousPaperTradingConfig | None = None, runtime: ContinuousPaperTradingRuntime = Depends(get_continuous_paper_trading)) -> ContinuousPaperStatus:
    return runtime.start(config)


@app.post("/continuous-paper/stop", response_model=ContinuousPaperStatus, tags=["continuous-paper"])
def continuous_paper_stop(runtime: ContinuousPaperTradingRuntime = Depends(get_continuous_paper_trading)) -> ContinuousPaperStatus:
    return runtime.stop()


@app.post("/continuous-paper/pause", response_model=ContinuousPaperStatus, tags=["continuous-paper"])
def continuous_paper_pause(runtime: ContinuousPaperTradingRuntime = Depends(get_continuous_paper_trading)) -> ContinuousPaperStatus:
    return runtime.pause()


@app.post("/continuous-paper/resume", response_model=ContinuousPaperStatus, tags=["continuous-paper"])
def continuous_paper_resume(runtime: ContinuousPaperTradingRuntime = Depends(get_continuous_paper_trading)) -> ContinuousPaperStatus:
    try:
        return runtime.resume()
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/continuous-paper/run-once", response_model=ContinuousPaperCycleResult, tags=["continuous-paper"])
def continuous_paper_run_once(runtime: ContinuousPaperTradingRuntime = Depends(get_continuous_paper_trading)) -> ContinuousPaperCycleResult:
    return runtime.run_once()


@app.get("/continuous-paper/events", response_model=list[ContinuousPaperEvent], tags=["continuous-paper"])
def continuous_paper_events(limit: int | None = None, runtime: ContinuousPaperTradingRuntime = Depends(get_continuous_paper_trading)) -> list[ContinuousPaperEvent]:
    if limit is not None and not 1 <= limit <= 10_000:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 10000")
    return list(runtime.events(limit))


@app.get("/continuous-paper/sessions", response_model=list[ContinuousPaperSession], tags=["continuous-paper"])
def continuous_paper_sessions(limit: int | None = None, runtime: ContinuousPaperTradingRuntime = Depends(get_continuous_paper_trading)) -> list[ContinuousPaperSession]:
    if limit is not None and not 1 <= limit <= 10_000:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 10000")
    return list(runtime.sessions(limit))


@app.get("/candidate-diagnostics/summary", response_model=CandidateDiagnosticsSummary, tags=["candidate-diagnostics"])
def candidate_diagnostics_summary(engine: CandidateDiagnosticsEngine = Depends(get_candidate_diagnostics_engine)) -> CandidateDiagnosticsSummary:
    return engine.summary()


@app.get("/candidate-diagnostics/recent", response_model=list[CandidateDiagnostic], tags=["candidate-diagnostics"])
def candidate_diagnostics_recent(limit: int = 100, engine: CandidateDiagnosticsEngine = Depends(get_candidate_diagnostics_engine)) -> list[CandidateDiagnostic]:
    if not 1 <= limit <= 10_000: raise HTTPException(status_code=422, detail="limit must be between 1 and 10000")
    return list(engine.recent(limit))


@app.get("/candidate-diagnostics/reasons", response_model=dict[str, int], tags=["candidate-diagnostics"])
def candidate_diagnostics_reasons(engine: CandidateDiagnosticsEngine = Depends(get_candidate_diagnostics_engine)) -> dict[str, int]:
    return engine.reasons()


@app.get("/candidate-diagnostics/near-misses", response_model=list[CandidateDiagnostic], tags=["candidate-diagnostics"])
def candidate_diagnostics_near_misses(limit: int = 100, engine: CandidateDiagnosticsEngine = Depends(get_candidate_diagnostics_engine)) -> list[CandidateDiagnostic]:
    if not 1 <= limit <= 10_000: raise HTTPException(status_code=422, detail="limit must be between 1 and 10000")
    return list(engine.near_misses(limit))


def _parse_latest_prices(value: str | None) -> dict[str, float]:
    if value is None:
        return {}
    import json

    try:
        payload = json.loads(value)
        if not isinstance(payload, dict):
            raise ValueError
        return {str(symbol).upper(): float(price) for symbol, price in payload.items()}
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail="latest_prices must be a JSON object of symbol-to-price values") from exc


@app.get(
    "/research/status",
    response_model=ContinuousResearchStatus,
    tags=["research"],
    summary="Read the latest continuous research status",
)
def research_status(
    window: ResearchWindow = ResearchWindow.ALL_TIME,
    custom_lookback: int | None = None,
    engine: ResearchEngine = Depends(get_research_engine),
) -> ContinuousResearchStatus:
    """Return a human-readable snapshot of current historical findings."""

    return _research_snapshot(engine, window, custom_lookback).status


@app.get(
    "/research/rankings",
    response_model=ContinuousResearchRankings,
    tags=["research"],
    summary="Rank continuous research dimensions",
)
def research_rankings(
    window: ResearchWindow = ResearchWindow.ALL_TIME,
    custom_lookback: int | None = None,
    engine: ResearchEngine = Depends(get_research_engine),
) -> ContinuousResearchRankings:
    """Rank symbols, timeframes, setups, strategies, regimes, and timing."""

    return _research_snapshot(engine, window, custom_lookback).rankings


@app.get(
    "/research/best-combinations",
    response_model=list[ResearchCombination],
    tags=["research"],
    summary="List the strongest historical combinations",
)
def research_best_combinations(
    window: ResearchWindow = ResearchWindow.ALL_TIME,
    custom_lookback: int | None = None,
    engine: ResearchEngine = Depends(get_research_engine),
) -> list[ResearchCombination]:
    """Return up to ten highest-expectancy completed-trade combinations."""

    return list(
        _research_snapshot(engine, window, custom_lookback).best_combinations
    )


@app.get(
    "/research/weakest-combinations",
    response_model=list[ResearchCombination],
    tags=["research"],
    summary="List the weakest historical combinations",
)
def research_weakest_combinations(
    window: ResearchWindow = ResearchWindow.ALL_TIME,
    custom_lookback: int | None = None,
    engine: ResearchEngine = Depends(get_research_engine),
) -> list[ResearchCombination]:
    """Return up to ten lowest-expectancy completed-trade combinations."""

    return list(
        _research_snapshot(engine, window, custom_lookback).weakest_combinations
    )


@app.post(
    "/research/refresh",
    response_model=ContinuousResearchStatus,
    tags=["research"],
    summary="Refresh a continuous research snapshot",
)
def refresh_research(
    request: ResearchRefreshRequest,
    engine: ResearchEngine = Depends(get_research_engine),
) -> ContinuousResearchStatus:
    """Recalculate research statistics without changing any trading behavior."""

    return engine.refresh(request.window, request.custom_lookback)
