"""Simplified deterministic historical evaluation for StructureIQ analyses."""

import re
from dataclasses import dataclass
from typing import Callable, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.config import SUPPORTED_TIMEFRAMES
from core.analysis_engine import AnalysisEngine
from core.journal import TradeOutcome
from core.market_data import Candle, MarketDataProvider
from models.schemas import AnalysisRequest, AnalysisResponse


class BacktestRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "symbol": "BTC-USD",
                    "timeframe": "5m",
                    "higher_timeframe": "1h",
                    "lookback": 300,
                    "starting_balance": 10_000,
                    "risk_per_trade_percent": 1.0,
                    "max_trades": 25,
                }
            ]
        }
    )

    symbol: str = Field(min_length=1, max_length=20)
    timeframe: str = Field(min_length=1)
    higher_timeframe: str = Field(min_length=1)
    lookback: int = Field(default=200, ge=50, le=5000)
    starting_balance: float = Field(default=10_000.0, gt=0)
    risk_per_trade_percent: float = Field(default=1.0, gt=0, le=100)
    max_trades: int = Field(default=100, ge=1, le=1000)

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


@dataclass(frozen=True)
class BacktestTrade:
    timestamp: int
    symbol: str
    action: str
    setup_type: str
    strategy_type: str
    entry: float | None
    stop_loss: float | None
    target: float | None
    estimated_risk_reward: float | None
    outcome: TradeOutcome
    realized_r: float | None
    reason: str


@dataclass(frozen=True)
class BacktestMetrics:
    total_trades: int
    wins: int
    losses: int
    breakeven: int
    win_rate: float
    average_r: float
    total_r: float
    profit_factor: float | None
    max_drawdown_r: float


@dataclass(frozen=True)
class BacktestResult:
    request: BacktestRequest
    trades: tuple[BacktestTrade, ...]
    metrics: BacktestMetrics
    human_readable_summary: str
    limitations: tuple[str, ...]


class _AnalysisRunner(Protocol):
    def analyze(self, request: AnalysisRequest) -> AnalysisResponse:
        ...


AnalysisEngineFactory = Callable[[MarketDataProvider], _AnalysisRunner]


class BacktestingEngine:
    """Replay the current analysis pipeline over chronological candle windows."""

    def __init__(
        self,
        market_data: MarketDataProvider,
        analysis_engine_factory: AnalysisEngineFactory | None = None,
    ) -> None:
        self._market_data = market_data
        self._analysis_engine_factory = analysis_engine_factory or AnalysisEngine

    def run(self, request: BacktestRequest) -> BacktestResult:
        candles = self._market_data.get_candles(
            request.symbol, request.timeframe, request.lookback
        )
        if request.higher_timeframe == request.timeframe:
            higher_candles = candles
        else:
            higher_candles = self._market_data.get_candles(
                request.symbol, request.higher_timeframe, request.lookback
            )

        trades: list[BacktestTrade] = []
        minimum_window = 50
        for index in range(minimum_window - 1, len(candles) - 1):
            if len(trades) >= request.max_trades:
                break
            higher_index = _aligned_index(index, len(candles), len(higher_candles))
            window_provider = _WindowProvider(
                {
                    request.timeframe: candles[: index + 1],
                    request.higher_timeframe: higher_candles[: higher_index + 1],
                }
            )
            analysis_request = AnalysisRequest(
                symbol=request.symbol,
                timeframe=request.timeframe,
                higher_timeframe=request.higher_timeframe,
                lookback=min(1000, max(50, index + 1)),
            )
            analysis = self._analysis_engine_factory(window_provider).analyze(
                analysis_request
            )
            trades.append(
                build_backtest_trade(
                    analysis=analysis,
                    timestamp=candles[index].timestamp,
                    symbol=request.symbol,
                    future_candles=candles[index + 1 :],
                )
            )

        metrics = calculate_backtest_metrics(trades)
        limitations = backtest_limitations()
        summary = (
            f"Backtest evaluated {len(trades)} analysis windows and produced "
            f"{metrics.total_trades} closed simulated trades with "
            f"{metrics.total_r:.2f}R total performance."
        )
        return BacktestResult(
            request=request,
            trades=tuple(trades),
            metrics=metrics,
            human_readable_summary=summary,
            limitations=limitations,
        )


def build_backtest_trade(
    *,
    analysis: AnalysisResponse,
    timestamp: int,
    symbol: str,
    future_candles: list[Candle],
) -> BacktestTrade:
    """Convert one analysis snapshot into a skipped or simulated trade record."""

    plan = analysis.trader_analysis.trade_plan
    action = analysis.decision.action.value
    setup_type = analysis.setup_plan.setup_type.value
    strategy_type = analysis.strategy.preferred_strategy.value
    if plan.status != "actionable" or action not in {"buy", "sell"}:
        return BacktestTrade(
            timestamp=timestamp,
            symbol=symbol,
            action=action,
            setup_type=setup_type,
            strategy_type=strategy_type,
            entry=None,
            stop_loss=None,
            target=None,
            estimated_risk_reward=plan.estimated_risk_reward,
            outcome=TradeOutcome.SKIPPED,
            realized_r=None,
            reason="Trade skipped because the trader-facing plan was not actionable.",
        )

    entry = parse_price_level(plan.entry_zone, midpoint=True)
    stop = parse_price_level(plan.stop_loss)
    target = parse_price_level(plan.target)
    if entry is None or stop is None or target is None:
        return BacktestTrade(
            timestamp=timestamp,
            symbol=symbol,
            action=action,
            setup_type=setup_type,
            strategy_type=strategy_type,
            entry=entry,
            stop_loss=stop,
            target=target,
            estimated_risk_reward=plan.estimated_risk_reward,
            outcome=TradeOutcome.SKIPPED,
            realized_r=None,
            reason="Trade skipped because entry, stop, or target was unavailable.",
        )

    outcome, realized_r, reason = simulate_trade_outcome(
        action=action,
        entry=entry,
        stop_loss=stop,
        target=target,
        future_candles=future_candles,
        estimated_risk_reward=plan.estimated_risk_reward,
    )
    return BacktestTrade(
        timestamp=timestamp,
        symbol=symbol,
        action=action,
        setup_type=setup_type,
        strategy_type=strategy_type,
        entry=entry,
        stop_loss=stop,
        target=target,
        estimated_risk_reward=plan.estimated_risk_reward,
        outcome=outcome,
        realized_r=realized_r,
        reason=reason,
    )


def simulate_trade_outcome(
    *,
    action: str,
    entry: float,
    stop_loss: float,
    target: float,
    future_candles: list[Candle],
    estimated_risk_reward: float | None = None,
) -> tuple[TradeOutcome, float | None, str]:
    """Resolve the first stop or target touch using conservative OHLC ordering."""

    risk = abs(entry - stop_loss)
    reward = abs(target - entry)
    reward_r = estimated_risk_reward
    if reward_r is None and risk > 0:
        reward_r = reward / risk

    for candle in future_candles:
        if action == "buy":
            stop_hit = candle.low <= stop_loss
            target_hit = candle.high >= target
        else:
            stop_hit = candle.high >= stop_loss
            target_hit = candle.low <= target
        if stop_hit and target_hit:
            return (
                TradeOutcome.LOSS,
                -1.0,
                "Stop and target were touched in one candle; conservative ordering "
                "records a loss.",
            )
        if stop_hit:
            return TradeOutcome.LOSS, -1.0, "Stop loss was reached before the target."
        if target_hit:
            return (
                TradeOutcome.WIN,
                round(reward_r or 0.0, 3),
                "Target was reached before the stop loss.",
            )
    return TradeOutcome.OPEN, None, "Neither stop nor target was reached in the available data."


def calculate_backtest_metrics(trades: list[BacktestTrade]) -> BacktestMetrics:
    closed = [
        trade
        for trade in trades
        if trade.outcome
        in {TradeOutcome.WIN, TradeOutcome.LOSS, TradeOutcome.BREAKEVEN}
    ]
    wins = sum(trade.outcome is TradeOutcome.WIN for trade in closed)
    losses = sum(trade.outcome is TradeOutcome.LOSS for trade in closed)
    breakeven = sum(trade.outcome is TradeOutcome.BREAKEVEN for trade in closed)
    realized = [trade.realized_r or 0.0 for trade in closed]
    total_r = sum(realized)
    gross_wins = sum(value for value in realized if value > 0)
    gross_losses = abs(sum(value for value in realized if value < 0))

    peak = 0.0
    cumulative = 0.0
    max_drawdown = 0.0
    for value in realized:
        cumulative += value
        peak = max(peak, cumulative)
        max_drawdown = max(max_drawdown, peak - cumulative)

    return BacktestMetrics(
        total_trades=len(closed),
        wins=wins,
        losses=losses,
        breakeven=breakeven,
        win_rate=round(100.0 * wins / len(closed), 2) if closed else 0.0,
        average_r=round(total_r / len(closed), 3) if closed else 0.0,
        total_r=round(total_r, 3),
        profit_factor=round(gross_wins / gross_losses, 3)
        if gross_losses
        else None,
        max_drawdown_r=round(max_drawdown, 3),
    )


def parse_price_level(value: str | None, *, midpoint: bool = False) -> float | None:
    if value is None:
        return None
    text = value.strip().replace(",", "")
    range_match = re.fullmatch(
        r"\s*(-?\d+(?:\.\d+)?)\s*-\s*(-?\d+(?:\.\d+)?)\s*", text
    )
    if range_match:
        first, second = (float(number) for number in range_match.groups())
        return (first + second) / 2 if midpoint else first
    try:
        return float(text)
    except ValueError:
        return None


def backtest_limitations() -> tuple[str, ...]:
    return (
        "This is a simplified deterministic backtest, not a production execution simulator.",
        "OHLC candles do not reveal intrabar order; same-candle stop and target "
        "touches are treated as losses.",
        "Fees, spread, slippage, latency, partial fills, and market impact are not modeled.",
        "Entry, stop, and target levels inherit the current engines' approximate "
        "structural levels.",
        "Starting balance and risk percentage are recorded but position sizing is "
        "not yet simulated.",
        "Results measure historical directional usefulness and do not guarantee profitability.",
    )


def _aligned_index(
    current_index: int, current_length: int, higher_length: int
) -> int:
    if higher_length <= 1 or current_length <= 1:
        return max(0, higher_length - 1)
    ratio = current_index / (current_length - 1)
    return min(higher_length - 1, max(0, round(ratio * (higher_length - 1))))


class _WindowProvider:
    def __init__(self, candles_by_timeframe: dict[str, list[Candle]]) -> None:
        self._candles = candles_by_timeframe

    def get_candles(
        self, symbol: str, timeframe: str, lookback: int
    ) -> list[Candle]:
        del symbol
        candles = self._candles.get(timeframe, [])
        return candles[-lookback:]
