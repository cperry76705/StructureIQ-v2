"""Deterministic observation and calibration across historical backtest runs."""

from collections import defaultdict
from dataclasses import dataclass
from typing import Callable, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.config import SUPPORTED_TIMEFRAMES
from core.backtesting import (
    BacktestMetrics,
    BacktestRequest,
    BacktestResult,
    BacktestTrade,
    BacktestingEngine,
    calculate_backtest_metrics,
)
from core.journal import TradeOutcome
from core.market_data import MarketDataProvider
from core.symbols import normalize_yahoo_symbol


RecommendationCategory = Literal[
    "decision_threshold",
    "setup_quality",
    "strategy_selection",
    "risk_reward",
    "market_structure",
    "data_quality",
]
RecommendationSeverity = Literal["low", "medium", "high"]


class CalibrationRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "symbols": ["BTC-USD", "EUR-USD"],
                    "timeframes": ["5m"],
                    "higher_timeframes": ["1h"],
                    "lookback": 300,
                    "max_trades_per_run": 25,
                    "risk_per_trade_percent": 1.0,
                    "starting_balance": 10_000,
                }
            ]
        }
    )

    symbols: list[str] = Field(min_length=1, max_length=20)
    timeframes: list[str] = Field(min_length=1, max_length=10)
    higher_timeframes: list[str] = Field(min_length=1, max_length=10)
    lookback: int = Field(default=300, ge=50, le=5000)
    max_trades_per_run: int = Field(default=25, ge=1, le=1000)
    risk_per_trade_percent: float = Field(default=1.0, gt=0, le=100)
    starting_balance: float = Field(default=10_000.0, gt=0)

    @field_validator("symbols")
    @classmethod
    def normalize_symbols(cls, values: list[str]) -> list[str]:
        normalized = [value.strip().upper() for value in values]
        if any(not value for value in normalized):
            raise ValueError("symbols cannot contain blank values")
        return normalized

    @field_validator("timeframes", "higher_timeframes")
    @classmethod
    def validate_timeframes(cls, values: list[str]) -> list[str]:
        invalid = [value for value in values if value not in SUPPORTED_TIMEFRAMES]
        if invalid:
            raise ValueError(
                f"timeframes must be selected from {sorted(SUPPORTED_TIMEFRAMES)}"
            )
        return values

    @model_validator(mode="after")
    def validate_combination_count(self) -> "CalibrationRequest":
        combinations = (
            len(self.symbols)
            * len(self.timeframes)
            * len(self.higher_timeframes)
        )
        if combinations > 100:
            raise ValueError("calibration is limited to 100 run combinations")
        return self


@dataclass(frozen=True)
class CalibrationRun:
    symbol: str
    normalized_symbol: str
    timeframe: str
    higher_timeframe: str
    total_records: int
    total_skipped: int
    total_open: int
    metrics: BacktestMetrics
    human_readable_summary: str


@dataclass(frozen=True)
class CalibrationMetrics:
    total_runs: int
    total_trades: int
    total_skipped: int
    wins: int
    losses: int
    breakeven: int
    win_rate: float
    average_r: float
    total_r: float
    profit_factor: float | None
    max_drawdown_r: float


@dataclass(frozen=True)
class SetupPerformance:
    setup_type: str
    total_records: int
    total_trades: int
    skipped: int
    wins: int
    losses: int
    breakeven: int
    win_rate: float
    average_r: float
    total_r: float
    profit_factor: float | None


@dataclass(frozen=True)
class StrategyPerformance:
    strategy_type: str
    total_records: int
    total_trades: int
    skipped: int
    wins: int
    losses: int
    breakeven: int
    win_rate: float
    average_r: float
    total_r: float
    profit_factor: float | None


@dataclass(frozen=True)
class CalibrationRecommendation:
    category: RecommendationCategory
    message: str
    severity: RecommendationSeverity
    suggested_action: str


@dataclass(frozen=True)
class CalibrationResult:
    runs: tuple[CalibrationRun, ...]
    aggregate_metrics: CalibrationMetrics
    setup_performance: tuple[SetupPerformance, ...]
    strategy_performance: tuple[StrategyPerformance, ...]
    recommendations: tuple[CalibrationRecommendation, ...]
    human_readable_summary: str
    limitations: tuple[str, ...]


class _BacktestRunner(Protocol):
    def run(self, request: BacktestRequest) -> BacktestResult:
        ...


BacktestingEngineFactory = Callable[[MarketDataProvider], _BacktestRunner]


class CalibrationEngine:
    """Aggregate backtests and recommend areas for human inspection."""

    def __init__(
        self,
        market_data: MarketDataProvider,
        backtesting_engine_factory: BacktestingEngineFactory | None = None,
    ) -> None:
        factory = backtesting_engine_factory or BacktestingEngine
        self._backtester = factory(market_data)

    def run(self, request: CalibrationRequest) -> CalibrationResult:
        runs: list[CalibrationRun] = []
        all_trades: list[BacktestTrade] = []

        for symbol in request.symbols:
            for timeframe in request.timeframes:
                for higher_timeframe in request.higher_timeframes:
                    backtest_request = BacktestRequest(
                        symbol=symbol,
                        timeframe=timeframe,
                        higher_timeframe=higher_timeframe,
                        lookback=request.lookback,
                        starting_balance=request.starting_balance,
                        risk_per_trade_percent=request.risk_per_trade_percent,
                        max_trades=request.max_trades_per_run,
                    )
                    result = self._backtester.run(backtest_request)
                    all_trades.extend(result.trades)
                    skipped = sum(
                        trade.outcome is TradeOutcome.SKIPPED
                        for trade in result.trades
                    )
                    open_trades = sum(
                        trade.outcome is TradeOutcome.OPEN for trade in result.trades
                    )
                    runs.append(
                        CalibrationRun(
                            symbol=symbol,
                            normalized_symbol=normalize_yahoo_symbol(symbol),
                            timeframe=timeframe,
                            higher_timeframe=higher_timeframe,
                            total_records=len(result.trades),
                            total_skipped=skipped,
                            total_open=open_trades,
                            metrics=result.metrics,
                            human_readable_summary=result.human_readable_summary,
                        )
                    )

        aggregate = _aggregate_metrics(runs, all_trades)
        setup_performance = _setup_performance(all_trades)
        strategy_performance = _strategy_performance(all_trades)
        recommendations = _recommendations(
            aggregate,
            all_trades,
            setup_performance,
            strategy_performance,
        )
        summary = (
            f"Calibration completed {aggregate.total_runs} runs with "
            f"{aggregate.total_trades} closed trades, {aggregate.total_skipped} "
            f"skipped records, and {aggregate.total_r:.2f}R aggregate performance."
        )
        return CalibrationResult(
            runs=tuple(runs),
            aggregate_metrics=aggregate,
            setup_performance=setup_performance,
            strategy_performance=strategy_performance,
            recommendations=recommendations,
            human_readable_summary=summary,
            limitations=calibration_limitations(),
        )


def _aggregate_metrics(
    runs: list[CalibrationRun], trades: list[BacktestTrade]
) -> CalibrationMetrics:
    metrics = calculate_backtest_metrics(trades)
    skipped = sum(trade.outcome is TradeOutcome.SKIPPED for trade in trades)
    return CalibrationMetrics(
        total_runs=len(runs),
        total_trades=metrics.total_trades,
        total_skipped=skipped,
        wins=metrics.wins,
        losses=metrics.losses,
        breakeven=metrics.breakeven,
        win_rate=metrics.win_rate,
        average_r=metrics.average_r,
        total_r=metrics.total_r,
        profit_factor=metrics.profit_factor,
        max_drawdown_r=metrics.max_drawdown_r,
    )


def _setup_performance(
    trades: list[BacktestTrade],
) -> tuple[SetupPerformance, ...]:
    groups: dict[str, list[BacktestTrade]] = defaultdict(list)
    for trade in trades:
        groups[trade.setup_type].append(trade)
    return tuple(
        _performance_record(name, records, SetupPerformance)
        for name, records in sorted(groups.items())
    )


def _strategy_performance(
    trades: list[BacktestTrade],
) -> tuple[StrategyPerformance, ...]:
    groups: dict[str, list[BacktestTrade]] = defaultdict(list)
    for trade in trades:
        groups[trade.strategy_type].append(trade)
    return tuple(
        _performance_record(name, records, StrategyPerformance)
        for name, records in sorted(groups.items())
    )


def _performance_record(name: str, records: list[BacktestTrade], model):
    metrics = calculate_backtest_metrics(records)
    return model(
        **({"setup_type": name} if model is SetupPerformance else {"strategy_type": name}),
        total_records=len(records),
        total_trades=metrics.total_trades,
        skipped=sum(trade.outcome is TradeOutcome.SKIPPED for trade in records),
        wins=metrics.wins,
        losses=metrics.losses,
        breakeven=metrics.breakeven,
        win_rate=metrics.win_rate,
        average_r=metrics.average_r,
        total_r=metrics.total_r,
        profit_factor=metrics.profit_factor,
    )


def _recommendations(
    metrics: CalibrationMetrics,
    records: list[BacktestTrade],
    setups: tuple[SetupPerformance, ...],
    strategies: tuple[StrategyPerformance, ...],
) -> tuple[CalibrationRecommendation, ...]:
    recommendations: list[CalibrationRecommendation] = []
    record_count = len(records)
    skip_rate = metrics.total_skipped / record_count if record_count else 0.0

    if metrics.total_runs >= 2 and metrics.total_trades == 0:
        recommendations.append(
            CalibrationRecommendation(
                "decision_threshold",
                "No actionable closed trades were produced across multiple runs.",
                "high",
                "Inspect decision thresholds and confirmation gates for excessive conservatism.",
            )
        )
    elif skip_rate >= 0.8:
        recommendations.append(
            CalibrationRecommendation(
                "setup_quality",
                f"{skip_rate:.0%} of calibration records were skipped.",
                "medium",
                "Review which required setup conditions most often remain unmet.",
            )
        )

    if metrics.total_trades and metrics.win_rate < 35.0:
        recommendations.append(
            CalibrationRecommendation(
                "decision_threshold",
                f"Closed-trade win rate is low at {metrics.win_rate:.1f}%.",
                "high",
                "Inspect whether actionable decision thresholds are too permissive.",
            )
        )
    if metrics.total_trades and metrics.average_r < 0.0:
        recommendations.append(
            CalibrationRecommendation(
                "risk_reward",
                f"Average realized performance is negative at {metrics.average_r:.2f}R.",
                "high",
                "Review entry quality, invalidation distance, and minimum reward requirements.",
            )
        )
    if metrics.profit_factor is not None and metrics.profit_factor < 1.0:
        recommendations.append(
            CalibrationRecommendation(
                "strategy_selection",
                f"Aggregate profit factor is weak at {metrics.profit_factor:.2f}.",
                "medium",
                "Inspect whether preferred strategies match their intended market regimes.",
            )
        )
    if metrics.max_drawdown_r >= 5.0:
        recommendations.append(
            CalibrationRecommendation(
                "risk_reward",
                f"Aggregate maximum drawdown reached {metrics.max_drawdown_r:.2f}R.",
                "high",
                "Review clustered losses and risk assumptions before changing thresholds.",
            )
        )

    for setup in setups:
        if setup.total_trades and setup.average_r < 0.0:
            recommendations.append(
                CalibrationRecommendation(
                    "setup_quality",
                    f"Setup {setup.setup_type} averaged {setup.average_r:.2f}R.",
                    "medium",
                    "Inspect this setup's qualification and confirmation requirements.",
                )
            )
    for strategy in strategies:
        if strategy.total_trades and strategy.average_r < 0.0:
            recommendations.append(
                CalibrationRecommendation(
                    "strategy_selection",
                    f"Strategy {strategy.strategy_type} averaged {strategy.average_r:.2f}R.",
                    "medium",
                    "Inspect this strategy's ranking inputs and regime fit.",
                )
            )

    if not records:
        recommendations.append(
            CalibrationRecommendation(
                "data_quality",
                "Calibration runs returned no evaluable analysis records.",
                "high",
                "Verify provider coverage, lookback length, and timeframe availability.",
            )
        )
    if not recommendations:
        recommendations.append(
            CalibrationRecommendation(
                "data_quality",
                "No major calibration imbalance was detected in this sample.",
                "low",
                "Continue collecting larger and more diverse historical samples.",
            )
        )
    return tuple(recommendations)


def calibration_limitations() -> tuple[str, ...]:
    return (
        "Calibration inherits every limitation of the simplified backtesting engine.",
        "Recommendations identify historical patterns for inspection; they do not "
        "tune weights automatically.",
        "Small or homogeneous samples can produce unstable metrics and misleading "
        "recommendations.",
        "Provider coverage and symbol normalization may differ across markets and timeframes.",
        "Historical calibration does not prove future profitability.",
    )
