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
    DecisionDiagnosticsSummary,
    ExecutionReadinessSnapshot,
    RiskRewardSummary,
    SetupCoverageSummary,
    SetupLevelSummary,
    TradeOutcomeDiagnosticsSummary,
    TradeManagementSensitivityResult,
    SkipDiagnostics,
    calculate_backtest_metrics,
    calculate_decision_diagnostics_summary,
    calculate_risk_reward_summary,
    calculate_setup_coverage_summary,
    calculate_setup_level_summary,
    calculate_outcome_diagnostics_summary,
    calculate_trade_management_sensitivity,
    calculate_skip_diagnostics,
    parse_price_level,
)
from core.journal import TradeOutcome
from core.execution import (
    ExecutionProfile,
    ExecutionSummary,
    FillModel,
    calculate_execution_summary,
)
from core.entry_timing import EntryTimingProfile
from core.execution_intelligence import (
    ExecutionIntelligence,
    ExecutionIntelligenceEngine,
)
from core.entry_timing_lab import (
    EntryTimingSummary,
    build_entry_timing_summary,
    ensure_immediate_baseline,
)
from core.execution_sensitivity import (
    ExecutionSensitivityProfile,
    ExecutionSensitivitySummary,
    build_execution_sensitivity_summary,
    ensure_perfect_baseline,
)
from core.market_data import Candle, MarketDataError, MarketDataProvider
from core.monte_carlo import (
    MonteCarloDistribution,
    MonteCarloRiskSummary,
    MonteCarloSummary,
    run_monte_carlo,
)
from core.monte_carlo_reporting import (
    MonteCarloExpectancyConfidence,
    MonteCarloKellySummary,
    MonteCarloReport,
    MonteCarloRiskHeatmap,
    MonteCarloTargetProbabilities,
    build_monte_carlo_report,
)
from core.out_of_sample import (
    GeneralizationSummary,
    OutOfSampleRequest,
    OutOfSampleSummary,
    OutOfSampleValidationEngine,
    OverfittingSummary,
    SegmentValidationSummary,
    StabilitySummary,
    ValidationFoldResult,
    ValidationMethod,
)
from core.regime_lab import (
    MarketRegimeSummary,
    RegimeClassifierComparison,
    SetupRegimeMatrix,
    StrategyRegimeMatrix,
    build_regime_classifier_comparison,
    build_market_regime_analysis,
    tuned_regime_view,
)
from core.regime import RegimeClassifierMode
from core.regime_confidence import (
    RegimeConfidenceSummary,
    build_regime_confidence_summary,
)
from core.regime_forward_validation import (
    ForwardValidationComparison,
    RegimeForwardValidationResult,
    build_matched_forward_validation,
)
from core.regime_validation import (
    RegimeValidationSummary,
    build_regime_validation_summary,
)
from core.regime_tuning import RegimeTuningSummary, build_regime_tuning_summary
from core.research_lab import (
    PerformanceMatrices,
    ResearchLabSummary,
    ResearchRankings,
    ResearchStatistics,
    build_research_lab,
)
from core.research_pipeline import ResearchPipelineSummary, build_research_pipeline
from core.setup_engine import MINIMUM_ACCEPTABLE_RISK_REWARD
from core.score_engine import ScoreEngine, ScoreSummary
from core.statistical_validation import (
    EdgeDecaySummary,
    LosingStreakSummary,
    StatisticalFoldStabilitySummary,
    StatisticalValidationSummary,
    StatisticalValidationResult,
    TradeDistributionSummary,
    WeaknessDetectionSummary,
    build_statistical_validation,
)
from core.symbols import normalize_yahoo_symbol
from core.walk_forward_intelligence import (
    PromotionReadinessSummary,
    RobustnessRanking,
    WalkForwardIntelligenceSummary,
)


RecommendationCategory = Literal[
    "decision_threshold",
    "setup_quality",
    "strategy_selection",
    "risk_reward",
    "market_structure",
    "data_quality",
]
RecommendationSeverity = Literal["low", "medium", "high"]
SENSITIVITY_THRESHOLDS = (50.0, 55.0, 60.0, 65.0, 70.0)


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
                },
                {
                    "symbols": ["BTC-USD"],
                    "timeframes": ["5m"],
                    "higher_timeframes": ["1h"],
                    "lookback": 300,
                    "max_trades_per_run": 50,
                    "risk_per_trade_percent": 1.0,
                    "starting_balance": 10_000,
                    "out_of_sample_validation": True,
                    "validation_method": "walk_forward",
                    "training_percent": 70,
                    "validation_percent": 30,
                    "validation_folds": 3,
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
    execution_profile: ExecutionProfile | None = None
    execution_sensitivity_profiles: list[ExecutionSensitivityProfile] | None = Field(
        default=None, max_length=20
    )
    entry_timing_profiles: list[EntryTimingProfile] | None = Field(
        default=None, max_length=20
    )
    market_regime_analysis: bool = False
    regime_validation_analysis: bool = False
    regime_tuning_analysis: bool = False
    regime_classifier_mode: RegimeClassifierMode = RegimeClassifierMode.LEGACY
    forward_validation: bool = False
    regime_confidence_analysis: bool = False
    out_of_sample_validation: bool = False
    validation_method: ValidationMethod = ValidationMethod.CHRONOLOGICAL
    training_percent: float = Field(default=70.0, gt=0, lt=100)
    validation_percent: float = Field(default=30.0, gt=0, lt=100)
    validation_folds: int = Field(default=5, ge=1, le=20)
    monte_carlo_analysis: bool = False
    monte_carlo_simulations: int = Field(default=1_000, ge=1, le=10_000)
    monte_carlo_random_seed: int = 42
    statistical_validation_analysis: bool = False

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
        if self.training_percent + self.validation_percent > 100:
            raise ValueError(
                "training_percent plus validation_percent cannot exceed 100"
            )
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
class ThresholdSensitivityResult:
    threshold: float
    directionally_eligible: int
    execution_ready: int
    missing_setup: int
    missing_levels: int
    risk_reward_failed: int
    setup_not_confirmed: int
    strategy_not_aligned: int
    still_blocked: int
    estimated_trade_candidates: int
    human_readable_summary: str


@dataclass(frozen=True)
class ProviderFailure:
    symbol: str
    normalized_symbol: str
    timeframe: str
    higher_timeframe: str
    provider: str
    error_message: str
    failure_type: str
    skipped: bool = True


@dataclass(frozen=True)
class DataAvailabilitySummary:
    requested_runs: int
    completed_runs: int
    failed_runs: int
    completion_rate: float
    all_runs_failed: bool
    human_readable_summary: str


@dataclass(frozen=True)
class CalibrationResult:
    runs: tuple[CalibrationRun, ...]
    aggregate_metrics: CalibrationMetrics
    aggregate_skip_diagnostics: SkipDiagnostics
    aggregate_decision_diagnostics: DecisionDiagnosticsSummary
    threshold_sensitivity: tuple[ThresholdSensitivityResult, ...]
    aggregate_risk_reward_summary: RiskRewardSummary
    aggregate_setup_level_summary: SetupLevelSummary
    aggregate_outcome_diagnostics: TradeOutcomeDiagnosticsSummary
    aggregate_trade_management_sensitivity: tuple[
        TradeManagementSensitivityResult, ...
    ]
    aggregate_setup_coverage_summary: SetupCoverageSummary
    aggregate_execution_summary: ExecutionSummary
    setup_performance: tuple[SetupPerformance, ...]
    strategy_performance: tuple[StrategyPerformance, ...]
    recommendations: tuple[CalibrationRecommendation, ...]
    human_readable_summary: str
    limitations: tuple[str, ...]
    execution_sensitivity_summary: ExecutionSensitivitySummary | None = None
    entry_timing_summary: EntryTimingSummary | None = None
    market_regime_summary: MarketRegimeSummary | None = None
    strategy_regime_matrix: tuple[StrategyRegimeMatrix, ...] | None = None
    setup_regime_matrix: tuple[SetupRegimeMatrix, ...] | None = None
    regime_validation_summary: RegimeValidationSummary | None = None
    regime_tuning_summary: RegimeTuningSummary | None = None
    legacy_market_regime_summary: MarketRegimeSummary | None = None
    tuned_market_regime_summary: MarketRegimeSummary | None = None
    regime_classifier_comparison: RegimeClassifierComparison | None = None
    legacy_forward_validation: RegimeForwardValidationResult | None = None
    tuned_forward_validation: RegimeForwardValidationResult | None = None
    forward_validation_comparison: ForwardValidationComparison | None = None
    regime_confidence_summary: RegimeConfidenceSummary | None = None
    out_of_sample_summary: OutOfSampleSummary | None = None
    validation_fold_results: tuple[ValidationFoldResult, ...] | None = None
    generalization_summary: GeneralizationSummary | None = None
    overfitting_summary: OverfittingSummary | None = None
    stability_summary: StabilitySummary | None = None
    symbol_validation_summary: tuple[SegmentValidationSummary, ...] | None = None
    timeframe_validation_summary: tuple[SegmentValidationSummary, ...] | None = None
    research_recommendations: tuple[str, ...] | None = None
    research_lab_summary: ResearchLabSummary | None = None
    research_rankings: ResearchRankings | None = None
    performance_matrices: PerformanceMatrices | None = None
    research_statistics: ResearchStatistics | None = None
    provider_failures: tuple[ProviderFailure, ...] = ()
    failed_runs: int = 0
    data_availability_summary: DataAvailabilitySummary | None = None
    research_pipeline_summary: ResearchPipelineSummary | None = None
    walk_forward_intelligence_summary: WalkForwardIntelligenceSummary | None = None
    strategy_robustness_rankings: tuple[RobustnessRanking, ...] | None = None
    promotion_readiness_summary: PromotionReadinessSummary | None = None
    research_action_items: tuple[str, ...] | None = None
    monte_carlo_summary: MonteCarloSummary | None = None
    monte_carlo_distribution: MonteCarloDistribution | None = None
    monte_carlo_risk_summary: MonteCarloRiskSummary | None = None
    monte_carlo_recommendations: tuple[str, ...] | None = None
    monte_carlo_report: MonteCarloReport | None = None
    monte_carlo_risk_heatmap: MonteCarloRiskHeatmap | None = None
    monte_carlo_target_probabilities: MonteCarloTargetProbabilities | None = None
    monte_carlo_expectancy_confidence: MonteCarloExpectancyConfidence | None = None
    monte_carlo_kelly_summary: MonteCarloKellySummary | None = None
    monte_carlo_failure_reasons: tuple[str, ...] | None = None
    statistical_validation_summary: StatisticalValidationSummary | None = None
    losing_streak_summary: LosingStreakSummary | None = None
    trade_distribution_summary: TradeDistributionSummary | None = None
    edge_decay_summary: EdgeDecaySummary | None = None
    fold_stability_summary: StatisticalFoldStabilitySummary | None = None
    weakness_detection_summary: WeaknessDetectionSummary | None = None
    aggregate_score_summary: ScoreSummary | None = None
    aggregate_execution_intelligence_summary: ExecutionIntelligence | None = None


class _BacktestRunner(Protocol):
    def run(self, request: BacktestRequest) -> BacktestResult:
        ...


BacktestingEngineFactory = Callable[[MarketDataProvider], _BacktestRunner]


class _CalibrationDataCache:
    """Freeze provider candles so every sensitivity profile sees identical data."""

    def __init__(self, source: MarketDataProvider) -> None:
        self._source = source
        self._cache: dict[tuple[str, str, int], tuple[Candle, ...]] = {}

    @property
    def provider_name(self) -> str:
        name = type(self._source).__name__
        if name == "YahooFinanceMarketDataProvider":
            return "Yahoo Finance"
        return name.removeprefix("_") or "unknown"

    def get_candles(
        self, symbol: str, timeframe: str, lookback: int
    ) -> list[Candle]:
        key = (symbol, timeframe, lookback)
        if key not in self._cache:
            self._cache[key] = tuple(
                self._source.get_candles(symbol, timeframe, lookback)
            )
        return list(self._cache[key])


class CalibrationEngine:
    """Aggregate backtests and recommend areas for human inspection."""

    def __init__(
        self,
        market_data: MarketDataProvider,
        backtesting_engine_factory: BacktestingEngineFactory | None = None,
    ) -> None:
        factory = backtesting_engine_factory or BacktestingEngine
        self._market_data = _CalibrationDataCache(market_data)
        self._backtester_factory = factory
        self._backtester = factory(self._market_data)

    def run(self, request: CalibrationRequest) -> CalibrationResult:
        runs: list[CalibrationRun] = []
        all_trades: list[BacktestTrade] = []
        provider_failures: list[ProviderFailure] = []

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
                        execution_profile=request.execution_profile,
                    )
                    try:
                        result = self._backtester.run(backtest_request)
                    except MarketDataError as exc:
                        provider_failures.append(
                            ProviderFailure(
                                symbol=symbol,
                                normalized_symbol=normalize_yahoo_symbol(symbol),
                                timeframe=timeframe,
                                higher_timeframe=higher_timeframe,
                                provider=self._market_data.provider_name,
                                error_message=str(exc),
                                failure_type="market_data_error",
                            )
                        )
                        continue
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
        aggregate_skip_diagnostics = calculate_skip_diagnostics(all_trades)
        aggregate_decision_diagnostics = calculate_decision_diagnostics_summary(
            all_trades
        )
        threshold_sensitivity = calculate_threshold_sensitivity(all_trades)
        aggregate_risk_reward_summary = calculate_risk_reward_summary(all_trades)
        aggregate_setup_level_summary = calculate_setup_level_summary(all_trades)
        aggregate_outcome_diagnostics = calculate_outcome_diagnostics_summary(
            all_trades
        )
        aggregate_trade_management_sensitivity = (
            calculate_trade_management_sensitivity(all_trades)
        )
        aggregate_setup_coverage_summary = calculate_setup_coverage_summary(all_trades)
        aggregate_execution_summary = calculate_execution_summary(
            [trade.execution_diagnostics for trade in all_trades if trade.execution_diagnostics]
        )
        execution_sensitivity_summary = (
            _run_execution_sensitivity(self._backtester, request)
            if request.execution_sensitivity_profiles
            else None
        )
        entry_timing_summary = (
            _run_entry_timing_lab(self._backtester, request)
            if request.entry_timing_profiles
            else None
        )
        legacy_market_regime_summary = None
        tuned_market_regime_summary = None
        regime_classifier_comparison = None
        if request.regime_classifier_mode is RegimeClassifierMode.COMPARE:
            (
                legacy_market_regime_summary,
                tuned_market_regime_summary,
                regime_classifier_comparison,
            ) = build_regime_classifier_comparison(all_trades)
            if request.market_regime_analysis:
                (
                    market_regime_summary,
                    strategy_regime_matrix,
                    setup_regime_matrix,
                ) = build_market_regime_analysis(all_trades)
            else:
                market_regime_summary = None
                strategy_regime_matrix = None
                setup_regime_matrix = None
        elif request.regime_classifier_mode is RegimeClassifierMode.TUNED:
            (
                market_regime_summary,
                strategy_regime_matrix,
                setup_regime_matrix,
            ) = build_market_regime_analysis(tuned_regime_view(all_trades))
            tuned_market_regime_summary = market_regime_summary
        elif request.market_regime_analysis:
            (
                market_regime_summary,
                strategy_regime_matrix,
                setup_regime_matrix,
            ) = build_market_regime_analysis(all_trades)
        else:
            market_regime_summary = None
            strategy_regime_matrix = None
            setup_regime_matrix = None
        regime_validation_summary = (
            build_regime_validation_summary(all_trades)
            if request.regime_validation_analysis
            else None
        )
        regime_tuning_summary = (
            build_regime_tuning_summary(all_trades)
            if request.regime_tuning_analysis
            else None
        )
        if (
            request.regime_classifier_mode is RegimeClassifierMode.COMPARE
            and request.forward_validation
        ):
            (
                legacy_forward_validation,
                tuned_forward_validation,
                forward_validation_comparison,
            ) = build_matched_forward_validation(all_trades)
        else:
            legacy_forward_validation = None
            tuned_forward_validation = None
            forward_validation_comparison = None
        regime_confidence_summary = (
            build_regime_confidence_summary(all_trades)
            if request.regime_confidence_analysis
            and request.regime_classifier_mode is RegimeClassifierMode.COMPARE
            and request.forward_validation
            and legacy_forward_validation is not None
            and tuned_forward_validation is not None
            and legacy_forward_validation.statistical_summary.evaluated_predictions > 0
            and tuned_forward_validation.statistical_summary.evaluated_predictions > 0
            else None
        )
        if request.out_of_sample_validation:
            out_of_sample = OutOfSampleValidationEngine(
                self._market_data,
                self._backtester_factory,
            ).run(
                OutOfSampleRequest(
                    symbols=tuple(request.symbols),
                    timeframes=tuple(request.timeframes),
                    higher_timeframes=tuple(request.higher_timeframes),
                    lookback=request.lookback,
                    starting_balance=request.starting_balance,
                    risk_per_trade_percent=request.risk_per_trade_percent,
                    max_trades=request.max_trades_per_run,
                    method=request.validation_method,
                    training_percent=request.training_percent,
                    validation_percent=request.validation_percent,
                    folds=request.validation_folds,
                    execution_profile=request.execution_profile,
                ),
                entire_sample_trades=all_trades,
            )
            out_of_sample_summary = out_of_sample.out_of_sample_summary
            validation_fold_results = out_of_sample.validation_fold_results
            generalization_summary = out_of_sample.generalization_summary
            overfitting_summary = out_of_sample.overfitting_summary
            stability_summary = out_of_sample.stability_summary
            symbol_validation_summary = out_of_sample.symbol_validation_summary
            timeframe_validation_summary = out_of_sample.timeframe_validation_summary
            oos_research_recommendations = out_of_sample.research_recommendations
            oos_trade_returns = out_of_sample.validation_trade_returns
            oos_execution_degradations = (
                out_of_sample.validation_execution_degradations
            )
        else:
            out_of_sample_summary = None
            validation_fold_results = None
            generalization_summary = None
            overfitting_summary = None
            stability_summary = None
            symbol_validation_summary = None
            timeframe_validation_summary = None
            oos_research_recommendations = ()
            oos_trade_returns = ()
            oos_execution_degradations = ()
        setup_performance = _setup_performance(all_trades)
        strategy_performance = _strategy_performance(all_trades)
        recommendations = _recommendations(
            aggregate,
            all_trades,
            setup_performance,
            strategy_performance,
            aggregate_skip_diagnostics,
            aggregate_decision_diagnostics,
            threshold_sensitivity,
            aggregate_risk_reward_summary,
            aggregate_setup_level_summary,
            aggregate_outcome_diagnostics,
            aggregate_trade_management_sensitivity,
            aggregate_setup_coverage_summary,
        )
        requested_runs = (
            len(request.symbols)
            * len(request.timeframes)
            * len(request.higher_timeframes)
        )
        failed_run_count = len(provider_failures)
        completion_rate = round(
            len(runs) / requested_runs * 100.0 if requested_runs else 0.0,
            2,
        )
        all_runs_failed = bool(requested_runs and not runs)
        availability_summary = DataAvailabilitySummary(
            requested_runs=requested_runs,
            completed_runs=len(runs),
            failed_runs=failed_run_count,
            completion_rate=completion_rate,
            all_runs_failed=all_runs_failed,
            human_readable_summary=(
                f"Completed {len(runs)} of {requested_runs} requested calibration "
                f"runs; {failed_run_count} failed because market data was unavailable."
                if not all_runs_failed
                else (
                    f"No calibration runs completed: market data was unavailable "
                    f"for all {requested_runs} requested runs."
                )
            ),
        )
        summary = (
            f"Calibration completed {aggregate.total_runs} of {requested_runs} runs "
            f"with {aggregate.total_trades} closed trades, "
            f"{aggregate.total_skipped} skipped records, "
            f"{failed_run_count} provider failures, and "
            f"{aggregate.total_r:.2f}R aggregate performance."
        )
        research_lab = build_research_lab(
            all_trades,
            management_results=aggregate_trade_management_sensitivity,
            entry_timing_summary=entry_timing_summary,
            execution_sensitivity_summary=execution_sensitivity_summary,
        )
        closed_trades = [
            trade for trade in all_trades
            if trade.realized_r is not None
            and trade.outcome in {
                TradeOutcome.WIN,
                TradeOutcome.LOSS,
                TradeOutcome.BREAKEVEN,
            }
        ]
        research_trade_returns = (
            oos_trade_returns
            if request.out_of_sample_validation
            else tuple(float(trade.realized_r) for trade in closed_trades)
        )
        if request.monte_carlo_analysis:
            monte_carlo = run_monte_carlo(
                research_trade_returns,
                simulations=request.monte_carlo_simulations,
                random_seed=request.monte_carlo_random_seed,
                starting_balance=request.starting_balance,
                risk_per_trade_percent=request.risk_per_trade_percent,
                execution_degradations=(
                    oos_execution_degradations
                    if request.out_of_sample_validation
                    else tuple(
                        float(trade.execution_diagnostics.execution_degradation_r)
                        for trade in closed_trades
                        if trade.execution_diagnostics is not None
                        and trade.execution_diagnostics.execution_degradation_r
                        is not None
                    )
                ),
            )
            monte_carlo_reporting = build_monte_carlo_report(
                monte_carlo, research_trade_returns
            )
        else:
            monte_carlo = None
            monte_carlo_reporting = None
        statistical_validation: StatisticalValidationResult | None = (
            build_statistical_validation(
                research_trade_returns,
                fold_expectancies=(
                    tuple(
                        fold.validation.expectancy
                        for fold in validation_fold_results
                    )
                    if validation_fold_results else ()
                ),
            )
            if request.statistical_validation_analysis else None
        )
        if (
            request.out_of_sample_validation
            and out_of_sample_summary is not None
            and validation_fold_results is not None
            and generalization_summary is not None
            and overfitting_summary is not None
            and stability_summary is not None
            and symbol_validation_summary is not None
            and timeframe_validation_summary is not None
        ):
            research_pipeline = build_research_pipeline(
                aggregate_metrics=aggregate,
                research_lab_summary=research_lab.research_lab_summary,
                research_rankings=research_lab.research_rankings,
                performance_matrices=research_lab.performance_matrices,
                out_of_sample_summary=out_of_sample_summary,
                validation_fold_results=validation_fold_results,
                generalization_summary=generalization_summary,
                overfitting_summary=overfitting_summary,
                stability_summary=stability_summary,
                symbol_validation_summary=symbol_validation_summary,
                timeframe_validation_summary=timeframe_validation_summary,
                monte_carlo_risk_summary=(
                    monte_carlo.risk_summary if monte_carlo else None
                ),
                monte_carlo_reporting=monte_carlo_reporting,
                statistical_validation=statistical_validation,
            )
        else:
            research_pipeline = None
        aggregate_score_summary = ScoreEngine().aggregate(
            tuple(
                trade.score_summary
                for trade in all_trades
                if trade.score_summary is not None
            ),
            research_pipeline_summary=(
                research_pipeline.research_pipeline_summary
                if research_pipeline else None
            ),
            statistical_validation_summary=(
                statistical_validation.statistical_validation_summary
                if statistical_validation else None
            ),
            monte_carlo_report=(
                monte_carlo_reporting.report if monte_carlo_reporting else None
            ),
        )
        aggregate_execution_intelligence_summary = (
            ExecutionIntelligenceEngine().aggregate(
                tuple(
                    trade.execution_intelligence
                    for trade in all_trades
                    if trade.execution_intelligence is not None
                ),
                outcome_diagnostics=aggregate_outcome_diagnostics,
                entry_timing_summary=entry_timing_summary,
                trade_management_sensitivity=(
                    aggregate_trade_management_sensitivity
                ),
                monte_carlo_report=(
                    monte_carlo_reporting.report
                    if monte_carlo_reporting else None
                ),
                statistical_validation_summary=(
                    statistical_validation.statistical_validation_summary
                    if statistical_validation else None
                ),
            )
        )
        research_recommendations = tuple(
            dict.fromkeys(
                (
                    *research_lab.research_recommendations,
                    *oos_research_recommendations,
                )
            )
        )
        result = CalibrationResult(
            runs=tuple(runs),
            aggregate_metrics=aggregate,
            aggregate_skip_diagnostics=aggregate_skip_diagnostics,
            aggregate_decision_diagnostics=aggregate_decision_diagnostics,
            threshold_sensitivity=threshold_sensitivity,
            aggregate_risk_reward_summary=aggregate_risk_reward_summary,
            aggregate_setup_level_summary=aggregate_setup_level_summary,
            aggregate_outcome_diagnostics=aggregate_outcome_diagnostics,
            aggregate_trade_management_sensitivity=(
                aggregate_trade_management_sensitivity
            ),
            aggregate_setup_coverage_summary=aggregate_setup_coverage_summary,
            aggregate_execution_summary=aggregate_execution_summary,
            setup_performance=setup_performance,
            strategy_performance=strategy_performance,
            recommendations=recommendations,
            human_readable_summary=summary,
            limitations=calibration_limitations(),
            execution_sensitivity_summary=execution_sensitivity_summary,
            entry_timing_summary=entry_timing_summary,
            market_regime_summary=market_regime_summary,
            strategy_regime_matrix=strategy_regime_matrix,
            setup_regime_matrix=setup_regime_matrix,
            regime_validation_summary=regime_validation_summary,
            regime_tuning_summary=regime_tuning_summary,
            legacy_market_regime_summary=legacy_market_regime_summary,
            tuned_market_regime_summary=tuned_market_regime_summary,
            regime_classifier_comparison=regime_classifier_comparison,
            legacy_forward_validation=legacy_forward_validation,
            tuned_forward_validation=tuned_forward_validation,
            forward_validation_comparison=forward_validation_comparison,
            regime_confidence_summary=regime_confidence_summary,
            out_of_sample_summary=out_of_sample_summary,
            validation_fold_results=validation_fold_results,
            generalization_summary=generalization_summary,
            overfitting_summary=overfitting_summary,
            stability_summary=stability_summary,
            symbol_validation_summary=symbol_validation_summary,
            timeframe_validation_summary=timeframe_validation_summary,
            research_recommendations=research_recommendations,
            research_lab_summary=research_lab.research_lab_summary,
            research_rankings=research_lab.research_rankings,
            performance_matrices=research_lab.performance_matrices,
            research_statistics=research_lab.research_statistics,
            provider_failures=tuple(provider_failures),
            failed_runs=failed_run_count,
            data_availability_summary=availability_summary,
            research_pipeline_summary=(
                research_pipeline.research_pipeline_summary
                if research_pipeline else None
            ),
            walk_forward_intelligence_summary=(
                research_pipeline.walk_forward_intelligence_summary
                if research_pipeline else None
            ),
            strategy_robustness_rankings=(
                research_pipeline.strategy_robustness_rankings
                if research_pipeline else None
            ),
            promotion_readiness_summary=(
                research_pipeline.promotion_readiness_summary
                if research_pipeline else None
            ),
            research_action_items=(
                research_pipeline.research_action_items
                if research_pipeline else None
            ),
            monte_carlo_summary=monte_carlo.summary if monte_carlo else None,
            monte_carlo_distribution=(
                monte_carlo.distribution if monte_carlo else None
            ),
            monte_carlo_risk_summary=(
                monte_carlo.risk_summary if monte_carlo else None
            ),
            monte_carlo_recommendations=(
                monte_carlo.recommendations if monte_carlo else None
            ),
            monte_carlo_report=(
                monte_carlo_reporting.report if monte_carlo_reporting else None
            ),
            monte_carlo_risk_heatmap=(
                monte_carlo_reporting.risk_heatmap
                if monte_carlo_reporting else None
            ),
            monte_carlo_target_probabilities=(
                monte_carlo_reporting.target_probabilities
                if monte_carlo_reporting else None
            ),
            monte_carlo_expectancy_confidence=(
                monte_carlo_reporting.expectancy_confidence
                if monte_carlo_reporting else None
            ),
            monte_carlo_kelly_summary=(
                monte_carlo_reporting.kelly_summary
                if monte_carlo_reporting else None
            ),
            monte_carlo_failure_reasons=(
                monte_carlo_reporting.failure_reasons
                if monte_carlo_reporting else None
            ),
            statistical_validation_summary=(
                statistical_validation.statistical_validation_summary
                if statistical_validation else None
            ),
            losing_streak_summary=(
                statistical_validation.losing_streak_summary
                if statistical_validation else None
            ),
            trade_distribution_summary=(
                statistical_validation.trade_distribution_summary
                if statistical_validation else None
            ),
            edge_decay_summary=(
                statistical_validation.edge_decay_summary
                if statistical_validation else None
            ),
            fold_stability_summary=(
                statistical_validation.fold_stability_summary
                if statistical_validation else None
            ),
            weakness_detection_summary=(
                statistical_validation.weakness_detection_summary
                if statistical_validation else None
            ),
            aggregate_score_summary=aggregate_score_summary,
            aggregate_execution_intelligence_summary=(
                aggregate_execution_intelligence_summary
            ),
        )
        _assert_out_of_sample_result(request, result)
        # Continuous research observes the completed calibration output only.
        # It deliberately runs after every production metric has been finalized
        # so reporting can never influence trade selection or calibration.
        from core.research_engine import get_global_research_engine

        get_global_research_engine().ingest(all_trades)
        return result


def _assert_out_of_sample_result(
    request: CalibrationRequest,
    result: CalibrationResult,
) -> None:
    """Prevent enabled OOS validation from silently returning an empty contract."""

    if not request.out_of_sample_validation:
        return
    required = (
        "out_of_sample_summary",
        "validation_fold_results",
        "generalization_summary",
        "overfitting_summary",
        "stability_summary",
        "symbol_validation_summary",
        "timeframe_validation_summary",
        "research_recommendations",
        "research_pipeline_summary",
        "walk_forward_intelligence_summary",
        "strategy_robustness_rankings",
        "promotion_readiness_summary",
        "research_action_items",
    )
    missing = [name for name in required if getattr(result, name) is None]
    if missing:
        raise RuntimeError(
            "Out-of-sample validation was enabled but failed to populate: "
            + ", ".join(missing)
        )


def _run_execution_sensitivity(
    backtester: _BacktestRunner,
    request: CalibrationRequest,
) -> ExecutionSensitivitySummary:
    profiles = ensure_perfect_baseline(request.execution_sensitivity_profiles or [])
    profile_runs: list[tuple[ExecutionSensitivityProfile, list[BacktestTrade]]] = []
    for profile in profiles:
        trades: list[BacktestTrade] = []
        for symbol in request.symbols:
            for timeframe in request.timeframes:
                for higher_timeframe in request.higher_timeframes:
                    try:
                        result = backtester.run(
                            BacktestRequest(
                                symbol=symbol,
                                timeframe=timeframe,
                                higher_timeframe=higher_timeframe,
                                lookback=request.lookback,
                                starting_balance=request.starting_balance,
                                risk_per_trade_percent=request.risk_per_trade_percent,
                                max_trades=request.max_trades_per_run,
                                execution_profile=profile.execution_profile,
                            )
                        )
                    except MarketDataError:
                        continue
                    trades.extend(result.trades)
        profile_runs.append((profile, trades))
    return build_execution_sensitivity_summary(profile_runs)


def _run_entry_timing_lab(
    backtester: _BacktestRunner,
    request: CalibrationRequest,
) -> EntryTimingSummary:
    profiles = ensure_immediate_baseline(request.entry_timing_profiles or [])
    execution_profile = request.execution_profile
    if execution_profile is not None:
        execution_profile = execution_profile.model_copy(
            update={"fill_model": FillModel.IMMEDIATE}
        )
    profile_runs: list[tuple[EntryTimingProfile, list[BacktestTrade]]] = []
    for profile in profiles:
        trades: list[BacktestTrade] = []
        for symbol in request.symbols:
            for timeframe in request.timeframes:
                for higher_timeframe in request.higher_timeframes:
                    try:
                        result = backtester.run(
                            BacktestRequest(
                                symbol=symbol,
                                timeframe=timeframe,
                                higher_timeframe=higher_timeframe,
                                lookback=request.lookback,
                                starting_balance=request.starting_balance,
                                risk_per_trade_percent=request.risk_per_trade_percent,
                                max_trades=request.max_trades_per_run,
                                execution_profile=execution_profile,
                                entry_timing_profile=profile,
                            )
                        )
                    except MarketDataError:
                        continue
                    trades.extend(result.trades)
        profile_runs.append((profile, trades))
    return build_entry_timing_summary(profile_runs)


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


def calculate_threshold_sensitivity(
    records: list[BacktestTrade],
    thresholds: tuple[float, ...] = SENSITIVITY_THRESHOLDS,
) -> tuple[ThresholdSensitivityResult, ...]:
    """Evaluate confidence alternatives without changing stored decisions or trades."""

    execution_ready_records = {
        index
        for index, record in enumerate(records)
        if _execution_blocker(record.execution_readiness) is None
    }
    results: list[ThresholdSensitivityResult] = []
    for threshold in thresholds:
        eligible = {
            index
            for index, record in enumerate(records)
            if _directionally_eligible(record, threshold)
        }
        blockers: defaultdict[str, int] = defaultdict(int)
        for index in eligible:
            blocker = _execution_blocker(records[index].execution_readiness)
            if blocker is not None:
                blockers[blocker] += 1
        candidates = eligible & execution_ready_records
        results.append(
            ThresholdSensitivityResult(
                threshold=threshold,
                directionally_eligible=len(eligible),
                execution_ready=len(execution_ready_records),
                missing_setup=blockers["missing_setup"],
                missing_levels=blockers["missing_levels"],
                risk_reward_failed=blockers["risk_reward_failed"],
                setup_not_confirmed=blockers["setup_not_confirmed"],
                strategy_not_aligned=blockers["strategy_not_aligned"],
                still_blocked=len(records) - len(eligible),
                estimated_trade_candidates=len(candidates),
                human_readable_summary=(
                    f"At {threshold:.0f} confidence, {len(eligible)} records are "
                    f"directionally eligible, {len(execution_ready_records)} have "
                    f"execution-ready snapshots, and {len(candidates)} pass both."
                ),
            )
        )
    return tuple(results)


def _directionally_eligible(record: BacktestTrade, threshold: float) -> bool:
    diagnostics = record.decision_diagnostics
    if diagnostics is None or not diagnostics.gate_results:
        return False
    if diagnostics.intended_direction not in {"bullish", "bearish"}:
        return False
    gates = {gate.gate_name: gate for gate in diagnostics.gate_results}
    if not gates.get("structure_alignment") or not gates["structure_alignment"].passed:
        return False
    if (
        not gates.get("multi_timeframe_alignment")
        or not gates["multi_timeframe_alignment"].passed
    ):
        return False
    return diagnostics.raw_score >= threshold


def _execution_blocker(
    snapshot: ExecutionReadinessSnapshot | None,
) -> str | None:
    if snapshot is None or snapshot.setup_status in {"no_setup", "invalid", "unknown"}:
        return "missing_setup"
    levels = (
        parse_price_level(snapshot.entry_zone, midpoint=True),
        parse_price_level(snapshot.stop_loss),
        parse_price_level(snapshot.target),
    )
    if any(level is None for level in levels):
        return "missing_levels"
    if (
        snapshot.estimated_risk_reward is None
        or snapshot.estimated_risk_reward < MINIMUM_ACCEPTABLE_RISK_REWARD
    ):
        return "risk_reward_failed"
    if snapshot.setup_status != "confirmed" or snapshot.plan_status != "actionable":
        return "setup_not_confirmed"
    if snapshot.preferred_strategy == "no_strategy" or snapshot.strategy_alignment in {
        "conflicts_with_decision",
        "no_clear_strategy",
    }:
        return "strategy_not_aligned"
    return None


def _recommendations(
    metrics: CalibrationMetrics,
    records: list[BacktestTrade],
    setups: tuple[SetupPerformance, ...],
    strategies: tuple[StrategyPerformance, ...],
    skip_diagnostics: SkipDiagnostics,
    decision_diagnostics: DecisionDiagnosticsSummary,
    threshold_sensitivity: tuple[ThresholdSensitivityResult, ...],
    risk_reward_summary: RiskRewardSummary,
    setup_level_summary: SetupLevelSummary,
    outcome_diagnostics: TradeOutcomeDiagnosticsSummary,
    management_sensitivity: tuple[TradeManagementSensitivityResult, ...],
    setup_coverage: SetupCoverageSummary,
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

    diagnostic_recommendation = _skip_diagnostic_recommendation(skip_diagnostics)
    if diagnostic_recommendation is not None:
        recommendations.append(diagnostic_recommendation)

    decision_recommendation = _decision_diagnostic_recommendation(
        decision_diagnostics
    )
    if decision_recommendation is not None:
        recommendations.append(decision_recommendation)

    sensitivity_recommendation = _threshold_sensitivity_recommendation(
        threshold_sensitivity
    )
    if sensitivity_recommendation is not None:
        recommendations.append(sensitivity_recommendation)

    recommendations.extend(
        _risk_and_level_recommendations(
            risk_reward_summary,
            setup_level_summary,
        )
    )
    outcome_recommendation = _outcome_diagnostic_recommendation(
        outcome_diagnostics
    )
    if outcome_recommendation is not None:
        recommendations.append(outcome_recommendation)
    management_recommendation = _trade_management_recommendation(
        management_sensitivity
    )
    if management_recommendation is not None:
        recommendations.append(management_recommendation)
    coverage_recommendation = _setup_coverage_recommendation(setup_coverage)
    if coverage_recommendation is not None:
        recommendations.append(coverage_recommendation)
    recommendations.append(_bearish_bos_contribution_recommendation(setups, setup_coverage))

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


def _skip_diagnostic_recommendation(
    diagnostics: SkipDiagnostics,
) -> CalibrationRecommendation | None:
    """Translate the dominant skip cause into a specific inspection target."""

    reason = diagnostics.most_common_reason
    if reason is None:
        return None
    count = diagnostics.by_reason_code.get(reason, 0)
    recommendations: dict[
        str, tuple[RecommendationCategory, RecommendationSeverity, str]
    ] = {
        "decision_not_actionable": (
            "decision_threshold",
            "high",
            "Inspect the Decision Engine confidence distribution and the evidence "
            "gates that most often produce wait or avoid; do not lower them until "
            "their contribution is measured.",
        ),
        "setup_not_confirmed": (
            "setup_quality",
            "high",
            "Measure which required Setup Engine confirmation conditions remain "
            "unmet most often before considering gate changes.",
        ),
        "setup_missing_levels": (
            "setup_quality",
            "high",
            "Inspect setup entry, stop, and target derivation for the affected "
            "market regimes and data windows.",
        ),
        "risk_reward_missing": (
            "risk_reward",
            "high",
            "Inspect why entry and invalidation context cannot produce a risk/reward "
            "estimate before reviewing the minimum threshold.",
        ),
        "risk_reward_too_low": (
            "risk_reward",
            "medium",
            "Review the distribution around the existing minimum risk/reward gate; "
            "do not change the gate until outcome sensitivity is measured.",
        ),
        "trader_plan_not_actionable": (
            "setup_quality",
            "medium",
            "Inspect how confirmed decision and setup states propagate into the "
            "trader-facing plan status.",
        ),
        "strategy_not_aligned": (
            "strategy_selection",
            "medium",
            "Inspect strategy alignment and candidate eligibility by market regime.",
        ),
        "no_strategy": (
            "strategy_selection",
            "medium",
            "Inspect which strategy fit components prevent any playbook from reaching "
            "eligibility.",
        ),
        "no_valid_setup": (
            "setup_quality",
            "high",
            "Inspect why the Setup Engine rejects all candidates, grouped by setup "
            "type and missing required condition.",
        ),
        "unknown": (
            "data_quality",
            "high",
            "Inspect raw analysis snapshots for an unclassified backtesting gate and "
            "add a diagnostic code before tuning.",
        ),
    }
    category, severity, action = recommendations[reason]
    return CalibrationRecommendation(
        category=category,
        message=(
            f"The dominant skip reason was {reason.replace('_', ' ')} "
            f"({count} records)."
        ),
        severity=severity,
        suggested_action=action,
    )


def _setup_coverage_recommendation(
    coverage: SetupCoverageSummary,
) -> CalibrationRecommendation | None:
    if not coverage.by_setup_type:
        return None
    ranked = sorted(
        coverage.by_setup_type,
        key=lambda item: (
            -item.missed_executable_count,
            -item.average_quality_score,
            -item.candidates_seen,
            item.setup_type,
        ),
    )
    candidate = ranked[0]
    executable_families = [
        name for name, count in coverage.executable_candidate_counts.items() if count
    ]
    only_family = (
        f" Only {executable_families[0].replace('_', ' ')} currently produces "
        "executable candidates."
        if len(executable_families) == 1
        else ""
    )
    blocker = candidate.most_common_blocking_reason or "insufficient candidate quality"
    return CalibrationRecommendation(
        "setup_quality",
        (
            f"Setup coverage found {coverage.missed_executable_candidate_count} "
            f"non-selected executable candidates.{only_family}"
        ),
        "medium" if coverage.missed_executable_candidate_count else "low",
        (
            f"Inspect {candidate.setup_type.replace('_', ' ')} first; it appeared "
            f"{candidate.candidates_seen} times and its dominant blocker was "
            f"{blocker.replace('_', ' ')}. Preserve selection and execution gates "
            "until this coverage evidence is reviewed."
        ),
    )


def _bearish_bos_contribution_recommendation(
    setups: tuple[SetupPerformance, ...],
    coverage: SetupCoverageSummary,
) -> CalibrationRecommendation:
    performance = next(
        (item for item in setups if item.setup_type == "bearish_bos_retest"),
        None,
    )
    family = next(
        (item for item in coverage.by_setup_type if item.setup_type == "bearish_bos_retest"),
        None,
    )
    trades = performance.total_trades if performance is not None else 0
    executable = family.executable_count if family is not None else 0
    if trades:
        return CalibrationRecommendation(
            "setup_quality",
            f"Bearish BOS retest contributed {trades} closed production trades.",
            "low",
            "Compare its outcomes, selection count, and missed candidates with liquidity-sweep reversals before further expansion.",
        )
    if executable:
        return CalibrationRecommendation(
            "setup_quality",
            f"Bearish BOS retest produced {executable} executable candidates but no closed production trades.",
            "medium",
            "Inspect selection attribution and available future-candle outcomes before changing any gate.",
        )
    return CalibrationRecommendation(
        "setup_quality",
        "Bearish BOS retest did not produce executable or closed production trades.",
        "medium",
        "Inspect bearish BOS recency, retest location, alignment, and level geometry while preserving current gates.",
    )
def _decision_diagnostic_recommendation(
    diagnostics: DecisionDiagnosticsSummary,
) -> CalibrationRecommendation | None:
    """Recommend inspection of the dominant existing Decision Engine gate."""

    gate = diagnostics.most_common_blocked_gate
    if gate is None:
        return None
    count = diagnostics.by_blocked_gate.get(gate, 0)
    recommendations: dict[
        str, tuple[RecommendationCategory, RecommendationSeverity, str]
    ] = {
        "directional_confidence": (
            "decision_threshold",
            "high",
            "Inspect the raw-score and confidence-band distribution, especially the "
            "distance below 70, before testing any confidence threshold change.",
        ),
        # Compatibility for diagnostic snapshots recorded before v1.3.
        "confidence_threshold": (
            "decision_threshold",
            "high",
            "Inspect the raw-score and confidence-band distribution, especially the "
            "distance below 70, before testing any confidence threshold change.",
        ),
        "structure_alignment": (
            "market_structure",
            "high",
            "Group failures by structure trend and intended direction to determine "
            "whether unclear or opposing structure dominates.",
        ),
        "multi_timeframe_alignment": (
            "market_structure",
            "high",
            "Break alignment failures into mixed, conflicting, and unclear states and "
            "measure whether current-timeframe confirmation changes outcomes.",
        ),
        "risk_plan_available": (
            "risk_reward",
            "high",
            "Inspect support, resistance, entry, and invalidation derivation when "
            "risk/reward cannot be calculated.",
        ),
        "risk_plan_quality": (
            "risk_reward",
            "medium",
            "Measure the risk/reward distribution around the existing 1.5 Setup "
            "Engine minimum before running a sensitivity experiment.",
        ),
    }
    if gate not in recommendations:
        return CalibrationRecommendation(
            "data_quality",
            f"Decision gate {gate.replace('_', ' ')} blocked {count} records.",
            "medium",
            "Inspect the underlying gate results before changing decision policy.",
        )
    category, severity, action = recommendations[gate]
    return CalibrationRecommendation(
        category,
        f"Decision gate {gate.replace('_', ' ')} blocked {count} records.",
        severity,
        action,
    )


def _threshold_sensitivity_recommendation(
    sensitivity: tuple[ThresholdSensitivityResult, ...],
) -> CalibrationRecommendation | None:
    if not sensitivity:
        return None
    lowest = min(sensitivity, key=lambda result: result.threshold)
    production = max(sensitivity, key=lambda result: result.threshold)
    gained = lowest.directionally_eligible - production.directionally_eligible

    if gained > 0 and lowest.estimated_trade_candidates == 0:
        execution_counts = {
            "missing setup": lowest.missing_setup,
            "missing levels": lowest.missing_levels,
            "risk/reward": lowest.risk_reward_failed,
            "setup confirmation": lowest.setup_not_confirmed,
            "strategy alignment": lowest.strategy_not_aligned,
        }
        dominant = max(execution_counts, key=execution_counts.get)
        return CalibrationRecommendation(
            "setup_quality" if dominant != "risk/reward" else "risk_reward",
            (
                f"Lowering the studied confidence threshold from "
                f"{production.threshold:.0f} to {lowest.threshold:.0f} adds {gained} "
                "directionally eligible records but produces no executable trade candidates."
            ),
            "high",
            (
                f"Inspect {dominant} before considering a production confidence "
                "change; the sensitivity study does not justify lowering the threshold."
            ),
        )
    if lowest.estimated_trade_candidates > production.estimated_trade_candidates:
        increase = (
            lowest.estimated_trade_candidates
            - production.estimated_trade_candidates
        )
        return CalibrationRecommendation(
            "decision_threshold",
            (
                f"The {lowest.threshold:.0f} sensitivity threshold produces {increase} "
                "additional estimated trade candidates versus the production threshold."
            ),
            "medium",
            "Validate those candidates out of sample before considering any threshold change.",
        )
    if lowest.directionally_eligible == 0:
        return CalibrationRecommendation(
            "market_structure",
            "No records are directionally eligible at any studied threshold.",
            "high",
            "Inspect structure and timeframe alignment rather than confidence thresholds.",
        )
    return CalibrationRecommendation(
        "decision_threshold",
        "Studied threshold changes do not increase estimated executable candidates.",
        "low",
        "Keep the production threshold unchanged and inspect downstream execution blockers.",
    )


def _risk_and_level_recommendations(
    risk: RiskRewardSummary,
    levels: SetupLevelSummary,
) -> tuple[CalibrationRecommendation, ...]:
    recommendations: list[CalibrationRecommendation] = []
    if levels.total_records:
        incomplete = levels.partial_level_records + levels.missing_level_records
        if incomplete >= 3 and incomplete / levels.total_records >= 0.2:
            recommendations.append(
                CalibrationRecommendation(
                    "setup_quality",
                    f"{incomplete} setup records have partial or missing generated levels.",
                    "high",
                    "Review setup-level generation and its support/resistance inputs before changing confirmation rules.",
                )
            )
        if levels.invalid_level_records >= 3:
            recommendations.append(
                CalibrationRecommendation(
                    "market_structure",
                    f"{levels.invalid_level_records} setup records have invalid level geometry.",
                    "high",
                    "Review support/resistance selection and directional level ordering.",
                )
            )

    target_close = risk.by_failure_reason.get("target_too_close", 0)
    stop_wide = risk.by_failure_reason.get("stop_too_wide", 0)
    if target_close >= 3:
        recommendations.append(
            CalibrationRecommendation(
                "risk_reward",
                f"Target distance is too close in {target_close} records.",
                "high" if target_close >= stop_wide else "medium",
                "Review target selection against the next valid resistance or support objective.",
            )
        )
    if stop_wide >= 3:
        recommendations.append(
            CalibrationRecommendation(
                "risk_reward",
                f"Stop distance is too wide in {stop_wide} records.",
                "high" if stop_wide > target_close else "medium",
                "Review structural stop placement and invalidation distance without tightening stops arbitrarily.",
            )
        )
    near = risk.records_near_threshold_1_2_to_1_5
    if (
        near >= 3
        and risk.complete_level_records
        and near / risk.complete_level_records >= 0.2
    ):
        recommendations.append(
            CalibrationRecommendation(
                "risk_reward",
                f"{near} complete records cluster between 1.2R and 1.5R.",
                "medium",
                "Run a controlled 1.2R–1.5R outcome sensitivity study before considering any minimum-R change.",
            )
        )
    return tuple(recommendations)


def _outcome_diagnostic_recommendation(
    summary: TradeOutcomeDiagnosticsSummary,
) -> CalibrationRecommendation | None:
    if not summary.by_loss_reason:
        return None
    reason = sorted(
        summary.by_loss_reason,
        key=lambda key: (-summary.by_loss_reason[key], key),
    )[0]
    count = summary.by_loss_reason[reason]
    recommendations: dict[str, tuple[RecommendationCategory, str]] = {
        "same_candle_ambiguous": (
            "data_quality",
            "Use finer-grained data to resolve intrabar stop/target ordering before changing rules.",
        ),
        "stopped_immediately": (
            "setup_quality",
            "Inspect entry timing and confirmation strength; do not widen stops automatically.",
        ),
        "no_follow_through": (
            "setup_quality",
            "Inspect confirmation quality and whether entries occur before directional follow-through.",
        ),
        "wrong_direction": (
            "market_structure",
            "Inspect structure direction and multi-timeframe alignment on losing entries.",
        ),
        "stop_too_tight": (
            "risk_reward",
            "Compare structural invalidation with MFE before considering any stop-placement change.",
        ),
        "target_too_far": (
            "risk_reward",
            "Review target distance against observed MFE without lowering the current R:R gate.",
        ),
        "weak_confirmation": (
            "setup_quality",
            "Inspect the confirmation conditions present at entry before changing setup rules.",
        ),
        "adverse_move_before_follow_through": (
            "setup_quality",
            "Inspect whether entries need stronger follow-through before execution.",
        ),
        "unclear": (
            "data_quality",
            "Inspect individual candle paths before changing strategy or risk rules.",
        ),
    }
    category, action = recommendations[reason]
    return CalibrationRecommendation(
        category,
        f"The dominant executed-trade loss reason was {reason.replace('_', ' ')} ({count} trades).",
        "high" if count == summary.losses else "medium",
        action,
    )


def _trade_management_recommendation(
    sensitivity: tuple[TradeManagementSensitivityResult, ...],
) -> CalibrationRecommendation | None:
    if not sensitivity:
        return None
    baseline = next(
        (item for item in sensitivity if item.rule.value == "none"),
        None,
    )
    alternatives = [
        item for item in sensitivity
        if item.rule.value != "none" and item.improved_vs_baseline
    ]
    if baseline is None or not alternatives:
        return None
    strongest = max(alternatives, key=lambda item: (item.total_r, -item.max_drawdown_r))
    return CalibrationRecommendation(
        "risk_reward",
        (
            f"The strongest management sensitivity rule is "
            f"{strongest.rule.value.replace('_', ' ')}, improving simulated total R "
            f"from {baseline.total_r:.2f}R to {strongest.total_r:.2f}R."
        ),
        "medium",
        (
            "Validate this approximation on a larger out-of-sample trade set; do not "
            "change production stop or target behavior automatically."
        ),
    )


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
