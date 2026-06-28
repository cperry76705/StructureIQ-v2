"""FastAPI entrypoint for StructureIQ v2."""

from functools import lru_cache
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, status

from app.config import APP_NAME
from core.analysis_engine import AnalysisEngine
from core.backtesting import BacktestRequest, BacktestResult, BacktestingEngine
from core.journal import JournalEntry, JournalStore, JournalSummary, TradeOutcome
from core.market_data import MarketDataError, MarketDataProvider
from core.providers.yahoo import YahooFinanceMarketDataProvider
from models.schemas import AnalysisRequest, AnalysisResponse, HealthResponse

app = FastAPI(title=APP_NAME, version="2.0.0")


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


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", app=APP_NAME)


@app.post("/analysis", response_model=AnalysisResponse)
def analysis(
    request: AnalysisRequest,
    engine: AnalysisEngine = Depends(get_analysis_engine),
) -> AnalysisResponse:
    try:
        return engine.analyze(request)
    except MarketDataError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Market data unavailable: {exc}",
        ) from exc


@app.post("/journal", response_model=JournalEntry)
def append_journal_entry(
    payload: dict[str, Any],
    store: JournalStore = Depends(get_journal_store),
) -> JournalEntry:
    entry = JournalEntry.from_payload(payload)
    return store.append_entry(entry)


@app.get("/journal", response_model=list[JournalEntry])
def list_journal_entries(
    symbol: str | None = None,
    timeframe: str | None = None,
    outcome: TradeOutcome | None = None,
    store: JournalStore = Depends(get_journal_store),
) -> list[JournalEntry]:
    return store.list_entries(
        symbol=symbol,
        timeframe=timeframe,
        outcome=outcome,
    )


@app.get("/journal/summary", response_model=JournalSummary)
def journal_summary(
    store: JournalStore = Depends(get_journal_store),
) -> JournalSummary:
    return store.summarize_entries()


@app.post("/backtest", response_model=BacktestResult)
def backtest(
    request: BacktestRequest,
    provider: MarketDataProvider = Depends(get_market_data_provider),
) -> BacktestResult:
    try:
        return BacktestingEngine(provider).run(request)
    except MarketDataError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Market data unavailable: {exc}",
        ) from exc
