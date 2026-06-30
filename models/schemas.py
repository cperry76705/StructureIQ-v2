"""Validated request and response shapes exposed by the API."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.config import DEFAULT_LOOKBACK, MAX_LOOKBACK, MIN_LOOKBACK, SUPPORTED_TIMEFRAMES
from core.decision_engine import DecisionResult
from core.explanation_engine import TraderAnalysis
from core.multi_timeframe import MultiTimeframeResult
from core.regime import RegimeResult
from core.regime_tuning import RegimeTuningEvidence
from core.setup_engine import SetupResult
from core.strategy_engine import StrategyResult
from core.score_engine import ScoreSummary
from core.execution_intelligence import ExecutionIntelligence
from core.confidence_calibration_engine import ConfidenceCalibration


Bias = Literal["bullish", "bearish", "ranging"]
Action = Literal["buy", "sell", "wait", "no_trade"]


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "symbol": "EUR-USD",
                    "timeframe": "5m",
                    "higher_timeframe": "1h",
                    "lookback": 200,
                }
            ]
        }
    )

    symbol: str = Field(default="BTC-USD", min_length=3, max_length=20)
    timeframe: str = "5m"
    higher_timeframe: str = "1h"
    lookback: int = Field(default=DEFAULT_LOOKBACK, ge=MIN_LOOKBACK, le=MAX_LOOKBACK)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("timeframe", "higher_timeframe")
    @classmethod
    def validate_timeframe(cls, value: str) -> str:
        if value not in SUPPORTED_TIMEFRAMES:
            raise ValueError(f"timeframe must be one of {sorted(SUPPORTED_TIMEFRAMES)}")
        return value


class AnalysisResponse(BaseModel):
    symbol: str
    timeframe: str
    higher_timeframe_bias: Bias
    current_structure: str
    action: Action
    setup: str
    confidence: float = Field(ge=0, le=10)
    entry_zone: str
    stop_loss: str
    target: str
    reasons: list[str]
    multi_timeframe: MultiTimeframeResult
    decision: DecisionResult
    setup_plan: SetupResult
    strategy: StrategyResult
    trader_analysis: TraderAnalysis
    market_regime: RegimeResult
    score_summary: ScoreSummary | None = None
    execution_intelligence: ExecutionIntelligence | None = None
    confidence_calibration: ConfidenceCalibration | None = None
    tuned_market_regime: Annotated[RegimeResult | None, Field(exclude=True)] = None
    # Research metadata is carried into historical calibration but deliberately
    # excluded from the public /analysis response contract.
    regime_tuning_evidence: Annotated[
        RegimeTuningEvidence | None, Field(exclude=True)
    ] = None


class HealthResponse(BaseModel):
    status: Literal["ok"]
    app: str
