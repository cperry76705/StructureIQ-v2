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


def get_research_dashboard_service(
    symbol_profiles: SymbolProfileEngine = Depends(get_symbol_profile_engine),
    research_engine: ResearchEngine = Depends(get_research_engine),
) -> ResearchDashboardService:
    """Return the compact read-only dashboard summarizer."""

    return ResearchDashboardService(
        symbol_profiles=symbol_profiles,
        research_engine=research_engine,
    )


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
