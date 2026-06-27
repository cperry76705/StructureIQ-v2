"""FastAPI entrypoint for StructureIQ v2."""

from functools import lru_cache

from fastapi import Depends, FastAPI, HTTPException, status

from app.config import APP_NAME
from core.analysis_engine import AnalysisEngine
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
