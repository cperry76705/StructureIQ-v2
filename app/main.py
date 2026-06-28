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


def get_analysis_engine(
    provider: MarketDataProvider = Depends(get_market_data_provider),
) -> AnalysisEngine:
    """Build the engine from the selected provider through FastAPI DI."""
    return AnalysisEngine(provider)


@lru_cache
def get_journal_store() -> JournalStore:
    """Return the local append-only journal store."""

    return JournalStore()


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
) -> CalibrationResult:
    """Aggregate backtests and return observational recommendations."""

    try:
        return CalibrationEngine(provider).run(request)
    except MarketDataError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Market data unavailable: {exc}",
        ) from exc
