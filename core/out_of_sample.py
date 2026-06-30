"""Deterministic out-of-sample validation over isolated chronological folds."""

from collections import Counter, defaultdict
from dataclasses import dataclass
from enum import Enum
from statistics import mean, pvariance, pstdev
from typing import Callable, Protocol

from core.backtesting import (
    BacktestRequest,
    BacktestResult,
    BacktestTrade,
    BacktestingEngine,
    calculate_backtest_metrics,
    calculate_trade_management_sensitivity,
)
from core.journal import TradeOutcome
from core.market_data import Candle, MarketDataError, MarketDataProvider


class ValidationMethod(str, Enum):
    CHRONOLOGICAL = "chronological"
    ROLLING_WINDOW = "rolling_window"
    WALK_FORWARD = "walk_forward"
    EXPANDING_WINDOW = "expanding_window"
    ANCHORED = "anchored"


class _BacktestRunner(Protocol):
    def run(self, request: BacktestRequest) -> BacktestResult:
        ...


BacktesterFactory = Callable[[MarketDataProvider], _BacktestRunner]


@dataclass(frozen=True)
class ValidationSplit:
    fold: int
    training_start: int
    training_end: int
    validation_start: int
    validation_end: int


@dataclass(frozen=True)
class ValidationMeasurements:
    records: int
    trades: int
    win_rate: float
    average_r: float
    total_r: float
    profit_factor: float | None
    maximum_drawdown: float
    expectancy: float
    average_mfe: float
    average_mae: float
    average_trade_duration: float
    skipped_records: int
    confidence_distribution: dict[str, int]
    average_confidence: float
    setup_distribution: dict[str, int]
    strategy_distribution: dict[str, int]
    regime_distribution: dict[str, int]
    execution_degradation: float
    trade_management_sensitivity: dict[str, float]


@dataclass(frozen=True)
class ValidationFoldResult:
    fold: int
    symbol: str
    timeframe: str
    higher_timeframe: str
    training_start_index: int
    training_end_index: int
    validation_start_index: int
    validation_end_index: int
    training: ValidationMeasurements
    validation: ValidationMeasurements
    human_readable_summary: str


@dataclass(frozen=True)
class GeneralizationSummary:
    generalization_score: float
    performance_decay_percent: float
    win_rate_decay_percent: float
    expectancy_decay_percent: float
    drawdown_change: float
    profit_factor_change: float
    confidence_drift: float
    strategy_drift: float
    setup_drift: float
    regime_drift: float
    execution_drift: float
    trade_frequency_drift: float
    calibration_stability_score: float
    fold_stability_score: float
    variance_across_folds: float
    coefficient_of_variation: float
    human_readable_summary: str


@dataclass(frozen=True)
class StabilitySummary:
    calibration_stability_score: float
    fold_stability_score: float
    variance_across_folds: float
    standard_deviation_across_folds: float
    coefficient_of_variation: float
    fold_count: int
    human_readable_summary: str


@dataclass(frozen=True)
class OverfittingSummary:
    risk_level: str
    detected_risks: tuple[str, ...]
    performance_collapse: bool
    confidence_collapse: bool
    setup_instability: bool
    strategy_instability: bool
    regime_instability: bool
    execution_instability: bool
    risk_instability: bool
    large_variance_between_folds: bool
    large_dependence_on_one_market: bool
    large_dependence_on_one_timeframe: bool
    large_dependence_on_one_symbol: bool
    human_readable_summary: str


@dataclass(frozen=True)
class SegmentValidationSummary:
    name: str
    training: ValidationMeasurements
    validation: ValidationMeasurements
    generalization_score: float
    validation_fold_count: int
    human_readable_summary: str


@dataclass(frozen=True)
class OutOfSampleSummary:
    validation_method: ValidationMethod
    requested_folds: int
    completed_folds: int
    training: ValidationMeasurements
    validation: ValidationMeasurements
    entire_sample: ValidationMeasurements
    human_readable_summary: str
    limitations: tuple[str, ...]


@dataclass(frozen=True)
class OutOfSampleValidationBundle:
    out_of_sample_summary: OutOfSampleSummary
    validation_fold_results: tuple[ValidationFoldResult, ...]
    generalization_summary: GeneralizationSummary
    overfitting_summary: OverfittingSummary
    stability_summary: StabilitySummary
    symbol_validation_summary: tuple[SegmentValidationSummary, ...]
    timeframe_validation_summary: tuple[SegmentValidationSummary, ...]
    research_recommendations: tuple[str, ...]


@dataclass(frozen=True)
class OutOfSampleRequest:
    symbols: tuple[str, ...]
    timeframes: tuple[str, ...]
    higher_timeframes: tuple[str, ...]
    lookback: int
    starting_balance: float
    risk_per_trade_percent: float
    max_trades: int
    method: ValidationMethod
    training_percent: float
    validation_percent: float
    folds: int
    execution_profile: object | None = None


def build_validation_splits(
    total_records: int,
    *,
    method: ValidationMethod,
    training_percent: float,
    validation_percent: float,
    folds: int,
) -> tuple[ValidationSplit, ...]:
    """Build chronological index ranges without shuffling or overlap leakage."""

    if total_records < 2:
        return ()
    training_size = max(1, int(total_records * training_percent / 100.0))
    validation_total = max(1, int(total_records * validation_percent / 100.0))
    training_size = min(training_size, total_records - 1)
    if method is ValidationMethod.CHRONOLOGICAL:
        validation_end = min(total_records, training_size + validation_total)
        return (
            ValidationSplit(1, 0, training_size, training_size, validation_end),
        )

    fold_count = max(1, folds)
    validation_size = max(1, validation_total // fold_count)
    splits: list[ValidationSplit] = []
    for index in range(fold_count):
        offset = index * validation_size
        if method in {ValidationMethod.WALK_FORWARD, ValidationMethod.EXPANDING_WINDOW}:
            training_start = 0
            training_end = min(total_records - 1, training_size + offset)
        elif method is ValidationMethod.ANCHORED:
            training_start = 0
            training_end = training_size
        else:
            training_start = offset
            training_end = min(total_records - 1, training_start + training_size)
        validation_start = (
            training_end
            if method is not ValidationMethod.ANCHORED
            else training_size + offset
        )
        validation_end = min(total_records, validation_start + validation_size)
        if validation_start >= total_records or validation_end <= validation_start:
            break
        splits.append(
            ValidationSplit(
                fold=index + 1,
                training_start=training_start,
                training_end=training_end,
                validation_start=validation_start,
                validation_end=validation_end,
            )
        )
    return tuple(splits)


class OutOfSampleValidationEngine:
    """Run fresh production backtests over bounded training and validation data."""

    def __init__(
        self,
        market_data: MarketDataProvider,
        backtester_factory: BacktesterFactory | None = None,
    ) -> None:
        self._market_data = market_data
        self._factory = backtester_factory or BacktestingEngine

    def run(
        self,
        request: OutOfSampleRequest,
        *,
        entire_sample_trades: list[BacktestTrade],
    ) -> OutOfSampleValidationBundle:
        folds: list[ValidationFoldResult] = []
        training_trades: list[BacktestTrade] = []
        validation_trades: list[BacktestTrade] = []
        symbol_groups: dict[str, tuple[list[BacktestTrade], list[BacktestTrade]]] = {}
        timeframe_groups: dict[str, tuple[list[BacktestTrade], list[BacktestTrade]]] = {}
        symbol_fold_counts: Counter[str] = Counter()
        timeframe_fold_counts: Counter[str] = Counter()

        for symbol in request.symbols:
            symbol_groups.setdefault(symbol, ([], []))
            for timeframe in request.timeframes:
                timeframe_groups.setdefault(timeframe, ([], []))
                for higher_timeframe in request.higher_timeframes:
                    try:
                        current = self._market_data.get_candles(
                            symbol, timeframe, request.lookback
                        )
                        higher = (
                            current
                            if higher_timeframe == timeframe
                            else self._market_data.get_candles(
                                symbol, higher_timeframe, request.lookback
                            )
                        )
                    except MarketDataError:
                        # Calibration owns availability reporting. OOS research
                        # skips the same unavailable combination instead of
                        # turning a partial calibration into a service failure.
                        continue
                    total = min(len(current), len(higher))
                    splits = build_validation_splits(
                        total,
                        method=request.method,
                        training_percent=request.training_percent,
                        validation_percent=request.validation_percent,
                        folds=request.folds,
                    )
                    for split in splits:
                        training_result = self._run_slice(
                            request,
                            symbol=symbol,
                            timeframe=timeframe,
                            higher_timeframe=higher_timeframe,
                            current=current[split.training_start : split.training_end],
                            higher=higher[split.training_start : split.training_end],
                        )
                        context_start = max(0, split.validation_start - 49)
                        validation_result = self._run_slice(
                            request,
                            symbol=symbol,
                            timeframe=timeframe,
                            higher_timeframe=higher_timeframe,
                            current=current[context_start : split.validation_end],
                            higher=higher[context_start : split.validation_end],
                        )
                        train = list(training_result.trades)
                        validate = list(validation_result.trades)
                        training_trades.extend(train)
                        validation_trades.extend(validate)
                        symbol_groups[symbol][0].extend(train)
                        symbol_groups[symbol][1].extend(validate)
                        timeframe_groups[timeframe][0].extend(train)
                        timeframe_groups[timeframe][1].extend(validate)
                        symbol_fold_counts[symbol] += 1
                        timeframe_fold_counts[timeframe] += 1
                        folds.append(
                            ValidationFoldResult(
                                fold=split.fold,
                                symbol=symbol,
                                timeframe=timeframe,
                                higher_timeframe=higher_timeframe,
                                training_start_index=split.training_start,
                                training_end_index=split.training_end,
                                validation_start_index=split.validation_start,
                                validation_end_index=split.validation_end,
                                training=measure_trades(train),
                                validation=measure_trades(validate),
                                human_readable_summary=(
                                    f"Fold {split.fold} trained on indices "
                                    f"[{split.training_start}, {split.training_end}) and "
                                    f"validated on [{split.validation_start}, "
                                    f"{split.validation_end}) without reused decisions."
                                ),
                            )
                        )

        training_measurements = measure_trades(training_trades)
        validation_measurements = measure_trades(validation_trades)
        entire_measurements = measure_trades(entire_sample_trades)
        generalization = build_generalization_summary(
            training_measurements,
            validation_measurements,
            [item.validation.average_r for item in folds],
        )
        fold_standard_deviation = (
            pstdev([item.validation.average_r for item in folds])
            if len(folds) > 1 else 0.0
        )
        stability = StabilitySummary(
            calibration_stability_score=generalization.calibration_stability_score,
            fold_stability_score=generalization.fold_stability_score,
            variance_across_folds=generalization.variance_across_folds,
            standard_deviation_across_folds=round(fold_standard_deviation, 6),
            coefficient_of_variation=generalization.coefficient_of_variation,
            fold_count=len(folds),
            human_readable_summary=(
                f"{len(folds)} validation folds produced a "
                f"{generalization.fold_stability_score:.1f}/100 stability score."
            ),
        )
        symbol_summaries = _segment_summaries(symbol_groups, symbol_fold_counts)
        timeframe_summaries = _segment_summaries(
            timeframe_groups, timeframe_fold_counts
        )
        overfitting = build_overfitting_summary(
            generalization,
            symbol_summaries=symbol_summaries,
            timeframe_summaries=timeframe_summaries,
        )
        recommendations = _research_recommendations(generalization, overfitting)
        return OutOfSampleValidationBundle(
            out_of_sample_summary=OutOfSampleSummary(
                validation_method=request.method,
                requested_folds=(1 if request.method is ValidationMethod.CHRONOLOGICAL else request.folds),
                completed_folds=len(folds),
                training=training_measurements,
                validation=validation_measurements,
                entire_sample=entire_measurements,
                human_readable_summary=(
                    f"Out-of-sample validation completed {len(folds)} independent "
                    f"folds with {validation_measurements.trades} closed validation trades."
                ),
                limitations=(
                    "Historical folds are deterministic simulations, not live execution.",
                    "Validation uses raw pre-split candles as warm-up context but "
                    "never reuses training decisions.",
                    "Small trade counts and overlapping expanding folds can "
                    "reduce statistical independence.",
                ),
            ),
            validation_fold_results=tuple(folds),
            generalization_summary=generalization,
            overfitting_summary=overfitting,
            stability_summary=stability,
            symbol_validation_summary=symbol_summaries,
            timeframe_validation_summary=timeframe_summaries,
            research_recommendations=recommendations,
        )

    def _run_slice(
        self,
        request: OutOfSampleRequest,
        *,
        symbol: str,
        timeframe: str,
        higher_timeframe: str,
        current: list[Candle],
        higher: list[Candle],
    ) -> BacktestResult:
        provider = _SliceProvider(
            symbol,
            {timeframe: current, higher_timeframe: higher},
        )
        runner = self._factory(provider)
        return runner.run(
            BacktestRequest(
                symbol=symbol,
                timeframe=timeframe,
                higher_timeframe=higher_timeframe,
                lookback=max(50, len(current)),
                starting_balance=request.starting_balance,
                risk_per_trade_percent=request.risk_per_trade_percent,
                max_trades=request.max_trades,
                execution_profile=request.execution_profile,
            )
        )


class _SliceProvider:
    def __init__(
        self, symbol: str, candles_by_timeframe: dict[str, list[Candle]]
    ) -> None:
        self._symbol = symbol
        self._candles = candles_by_timeframe

    def get_candles(
        self, symbol: str, timeframe: str, lookback: int
    ) -> list[Candle]:
        del lookback
        if symbol != self._symbol or timeframe not in self._candles:
            return []
        return list(self._candles[timeframe])


def measure_trades(trades: list[BacktestTrade]) -> ValidationMeasurements:
    metrics = calculate_backtest_metrics(trades)
    outcomes = [item.outcome_diagnostics for item in trades if item.outcome_diagnostics]
    durations = [item.bars_to_outcome for item in outcomes if item.bars_to_outcome is not None]
    confidence_values = [
        item.decision_diagnostics.final_confidence
        for item in trades
        if item.decision_diagnostics is not None
    ]
    execution_values = [
        item.execution_diagnostics.execution_degradation
        for item in trades
        if item.execution_diagnostics is not None
    ]
    management = calculate_trade_management_sensitivity(trades)
    return ValidationMeasurements(
        records=len(trades),
        trades=metrics.total_trades,
        win_rate=metrics.win_rate,
        average_r=metrics.average_r,
        total_r=metrics.total_r,
        profit_factor=metrics.profit_factor,
        maximum_drawdown=metrics.max_drawdown_r,
        expectancy=metrics.average_r,
        average_mfe=(
            round(mean(item.max_favorable_excursion_r for item in outcomes), 6)
            if outcomes else 0.0
        ),
        average_mae=(
            round(mean(item.max_adverse_excursion_r for item in outcomes), 6)
            if outcomes else 0.0
        ),
        average_trade_duration=round(mean(durations), 3) if durations else 0.0,
        skipped_records=sum(item.outcome is TradeOutcome.SKIPPED for item in trades),
        confidence_distribution=_confidence_histogram(confidence_values),
        average_confidence=round(mean(confidence_values), 3) if confidence_values else 0.0,
        setup_distribution=dict(sorted(Counter(item.setup_type for item in trades).items())),
        strategy_distribution=dict(
            sorted(Counter(item.strategy_type for item in trades).items())
        ),
        regime_distribution=dict(
            sorted(
                Counter(
                    item.market_regime.market_regime.value
                    for item in trades
                    if item.market_regime is not None
                ).items()
            )
        ),
        execution_degradation=round(mean(execution_values), 6) if execution_values else 0.0,
        trade_management_sensitivity={
            item.rule.value: item.total_r for item in management
        },
    )


def build_generalization_summary(
    training: ValidationMeasurements,
    validation: ValidationMeasurements,
    fold_expectancies: list[float],
) -> GeneralizationSummary:
    performance_decay = _relative_decay(training.average_r, validation.average_r)
    win_decay = _relative_decay(training.win_rate, validation.win_rate)
    expectancy_decay = _relative_decay(training.expectancy, validation.expectancy)
    confidence_drift = abs(training.average_confidence - validation.average_confidence)
    strategy_drift = _distribution_drift(
        training.strategy_distribution, validation.strategy_distribution
    )
    setup_drift = _distribution_drift(
        training.setup_distribution, validation.setup_distribution
    )
    regime_drift = _distribution_drift(
        training.regime_distribution, validation.regime_distribution
    )
    execution_drift = abs(
        training.execution_degradation - validation.execution_degradation
    )
    training_frequency = training.trades / training.records if training.records else 0.0
    validation_frequency = (
        validation.trades / validation.records if validation.records else 0.0
    )
    frequency_drift = abs(training_frequency - validation_frequency) * 100.0
    variance = pvariance(fold_expectancies) if len(fold_expectancies) > 1 else 0.0
    deviation = pstdev(fold_expectancies) if len(fold_expectancies) > 1 else 0.0
    average_fold = mean(fold_expectancies) if fold_expectancies else 0.0
    coefficient = deviation / abs(average_fold) if average_fold else (1.0 if deviation else 0.0)
    calibration_stability = max(0.0, 100.0 - confidence_drift * 4.0)
    fold_stability = max(0.0, 100.0 - min(100.0, coefficient * 50.0))
    penalties = (
        max(0.0, performance_decay) * 0.35
        + max(0.0, win_decay) * 0.10
        + min(100.0, setup_drift) * 0.10
        + min(100.0, strategy_drift) * 0.10
        + min(100.0, regime_drift) * 0.10
        + min(100.0, confidence_drift * 4.0) * 0.10
        + (100.0 - fold_stability) * 0.15
    )
    score = max(0.0, min(100.0, 100.0 - penalties))
    return GeneralizationSummary(
        generalization_score=round(score, 3),
        performance_decay_percent=round(performance_decay, 3),
        win_rate_decay_percent=round(win_decay, 3),
        expectancy_decay_percent=round(expectancy_decay, 3),
        drawdown_change=round(
            validation.maximum_drawdown - training.maximum_drawdown, 6
        ),
        profit_factor_change=round(
            _numeric_profit_factor(validation.profit_factor)
            - _numeric_profit_factor(training.profit_factor),
            6,
        ),
        confidence_drift=round(confidence_drift, 3),
        strategy_drift=round(strategy_drift, 3),
        setup_drift=round(setup_drift, 3),
        regime_drift=round(regime_drift, 3),
        execution_drift=round(execution_drift, 6),
        trade_frequency_drift=round(frequency_drift, 3),
        calibration_stability_score=round(calibration_stability, 3),
        fold_stability_score=round(fold_stability, 3),
        variance_across_folds=round(variance, 6),
        coefficient_of_variation=round(coefficient, 6),
        human_readable_summary=(
            f"Validation retained a {score:.1f}/100 generalization score with "
            f"{performance_decay:.1f}% expectancy decay and "
            f"{coefficient:.2f} coefficient of variation across folds."
        ),
    )


def build_overfitting_summary(
    generalization: GeneralizationSummary,
    *,
    symbol_summaries: tuple[SegmentValidationSummary, ...],
    timeframe_summaries: tuple[SegmentValidationSummary, ...],
) -> OverfittingSummary:
    flags: list[str] = []
    performance = generalization.performance_decay_percent > 50.0
    confidence = generalization.confidence_drift > 15.0
    setup = generalization.setup_drift > 30.0
    strategy = generalization.strategy_drift > 30.0
    regime = generalization.regime_drift > 30.0
    execution = generalization.execution_drift > 0.5
    risk = generalization.drawdown_change > 2.0
    variance = generalization.coefficient_of_variation > 1.0
    symbol_dependence = _segment_dependence(symbol_summaries)
    timeframe_dependence = _segment_dependence(timeframe_summaries)
    checks = (
        (performance, "PERFORMANCE_COLLAPSE"),
        (confidence, "CONFIDENCE_COLLAPSE"),
        (setup, "SETUP_INSTABILITY"),
        (strategy, "STRATEGY_INSTABILITY"),
        (regime, "REGIME_INSTABILITY"),
        (execution, "EXECUTION_INSTABILITY"),
        (risk, "RISK_INSTABILITY"),
        (variance, "LARGE_VARIANCE_BETWEEN_FOLDS"),
        (symbol_dependence, "LARGE_DEPENDENCE_ON_ONE_MARKET"),
        (symbol_dependence, "LARGE_DEPENDENCE_ON_ONE_SYMBOL"),
        (timeframe_dependence, "LARGE_DEPENDENCE_ON_ONE_TIMEFRAME"),
    )
    flags.extend(name for active, name in checks if active)
    severity = sum((2 if name in {"PERFORMANCE_COLLAPSE", "RISK_INSTABILITY"} else 1) for name in flags)
    risk_level = (
        "OVERFIT_RISK" if severity >= 6
        else "HIGH" if severity >= 4
        else "MEDIUM" if severity >= 2
        else "LOW"
    )
    return OverfittingSummary(
        risk_level=risk_level,
        detected_risks=tuple(flags),
        performance_collapse=performance,
        confidence_collapse=confidence,
        setup_instability=setup,
        strategy_instability=strategy,
        regime_instability=regime,
        execution_instability=execution,
        risk_instability=risk,
        large_variance_between_folds=variance,
        large_dependence_on_one_market=symbol_dependence,
        large_dependence_on_one_timeframe=timeframe_dependence,
        large_dependence_on_one_symbol=symbol_dependence,
        human_readable_summary=(
            f"Out-of-sample overfit risk is {risk_level}; "
            f"{len(flags)} diagnostic conditions were detected."
        ),
    )


def _segment_summaries(
    groups: dict[str, tuple[list[BacktestTrade], list[BacktestTrade]]],
    fold_counts: Counter[str],
) -> tuple[SegmentValidationSummary, ...]:
    rows: list[SegmentValidationSummary] = []
    for name, (training_trades, validation_trades) in sorted(groups.items()):
        training = measure_trades(training_trades)
        validation = measure_trades(validation_trades)
        generalization = build_generalization_summary(training, validation, [])
        rows.append(
            SegmentValidationSummary(
                name=name,
                training=training,
                validation=validation,
                generalization_score=generalization.generalization_score,
                validation_fold_count=fold_counts[name],
                human_readable_summary=(
                    f"{name} validation produced {validation.trades} closed trades "
                    f"and a {generalization.generalization_score:.1f}/100 score."
                ),
            )
        )
    return tuple(rows)


def _relative_decay(training: float, validation: float) -> float:
    if training == 0:
        return 0.0 if validation == 0 else -100.0 if validation > 0 else 100.0
    return (training - validation) / abs(training) * 100.0


def _distribution_drift(left: dict[str, int], right: dict[str, int]) -> float:
    left_total = sum(left.values())
    right_total = sum(right.values())
    names = set(left) | set(right)
    if not names or not left_total or not right_total:
        return 0.0 if left_total == right_total else 100.0
    distance = sum(
        abs(left.get(name, 0) / left_total - right.get(name, 0) / right_total)
        for name in names
    )
    return 50.0 * distance


def _confidence_histogram(values: list[float]) -> dict[str, int]:
    bands = ((0, 49), (50, 59), (60, 69), (70, 79), (80, 89), (90, 100))
    return {
        f"{lower}-{upper}": sum(lower <= value <= upper for value in values)
        for lower, upper in bands
    }


def _numeric_profit_factor(value: float | None) -> float:
    return value if value is not None else 0.0


def _segment_dependence(rows: tuple[SegmentValidationSummary, ...]) -> bool:
    if len(rows) < 2:
        return False
    values = [abs(item.validation.total_r) for item in rows]
    total = sum(values)
    return bool(total and max(values) / total >= 0.70)


def _research_recommendations(
    generalization: GeneralizationSummary,
    overfitting: OverfittingSummary,
) -> tuple[str, ...]:
    messages = [
        "Out-of-sample results are research evidence and must not alter production rules automatically."
    ]
    if overfitting.performance_collapse:
        messages.append(
            "Validation expectancy decayed by more than 50%; inspect "
            "training-specific setup or market dependence."
        )
    if overfitting.large_variance_between_folds:
        messages.append(
            "Fold variance is high; collect more non-overlapping history before drawing conclusions."
        )
    if generalization.trade_frequency_drift > 10.0:
        messages.append(
            "Trade frequency shifted materially between training and validation periods."
        )
    if len(messages) == 1:
        messages.append(
            "No major overfit threshold fired, but independent market periods remain necessary."
        )
    return tuple(messages)
