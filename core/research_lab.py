"""Automatic statistical research over immutable completed calibration records."""

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from math import sqrt
from statistics import mean, pstdev

from core.backtesting import (
    BacktestTrade,
    TradeManagementSensitivityResult,
    calculate_backtest_metrics,
)
from core.entry_timing_lab import EntryTimingSummary
from core.execution_sensitivity import ExecutionSensitivitySummary
from core.journal import TradeOutcome


STANDARD_SYMBOLS = ("BTC", "ETH", "EURUSD", "GBPUSD")
STANDARD_TIMEFRAMES = ("1m", "3m", "5m", "15m", "30m", "1h", "4h")
STANDARD_SETUPS = (
    "bullish_bos_retest",
    "bearish_bos_retest",
    "liquidity_sweep_long",
    "liquidity_sweep_short",
    "range_reversal",
    "pullback_continuation",
    "compression_breakout",
)
STANDARD_STRATEGIES = (
    "breakout_continuation",
    "liquidity_sweep_reversal",
    "trend_continuation",
    "mean_reversion",
)
STANDARD_REGIMES = (
    "strong_bull_trend",
    "weak_bull_trend",
    "strong_bear_trend",
    "weak_bear_trend",
    "range",
    "compression",
    "expansion",
    "transition",
)
CONFIDENCE_BUCKETS = ("40-49", "50-59", "60-69", "70-79", "80-89", "90-100")
DAY_NAMES = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)
DURATION_BUCKETS = ("1 candle", "2 candles", "3-5", "6-10", "10+")


@dataclass(frozen=True)
class ResearchConfidenceInterval:
    lower: float
    upper: float
    confidence_level: float
    sample_size: int


@dataclass(frozen=True)
class ResearchPerformance:
    category: str
    records_seen: int
    executed_trades: int
    wins: int
    losses: int
    breakeven: int
    win_rate: float
    average_r: float
    total_r: float
    expectancy: float
    profit_factor: float | None
    max_drawdown: float
    average_mfe: float
    average_mae: float
    average_trade_duration: float
    average_confidence: float
    confidence_interval: ResearchConfidenceInterval
    statistical_significance_score: float
    sample_quality: str
    recommendation: str


@dataclass(frozen=True)
class ConfidenceBucketPerformance:
    confidence_bucket: str
    trades: int
    win_rate: float
    average_r: float
    expectancy: float
    profit_factor: float | None


@dataclass(frozen=True)
class ResearchMatrixRow:
    matrix: str
    left: str
    right: str
    performance: ResearchPerformance


@dataclass(frozen=True)
class PerformanceMatrices:
    regime_strategy: tuple[ResearchMatrixRow, ...]
    setup_regime: tuple[ResearchMatrixRow, ...]
    symbol_setup: tuple[ResearchMatrixRow, ...]
    timeframe_setup: tuple[ResearchMatrixRow, ...]


@dataclass(frozen=True)
class RankedResearchItem:
    name: str
    dimension: str
    expectancy: float
    profit_factor: float | None
    max_drawdown: float
    statistical_significance_score: float
    sample_size: int


@dataclass(frozen=True)
class ResearchRankings:
    top_10_strongest_combinations: tuple[RankedResearchItem, ...]
    top_10_weakest_combinations: tuple[RankedResearchItem, ...]
    highest_expectancy: RankedResearchItem | None
    highest_profit_factor: RankedResearchItem | None
    lowest_drawdown: RankedResearchItem | None
    highest_statistical_confidence: RankedResearchItem | None
    largest_sample_size: RankedResearchItem | None


@dataclass(frozen=True)
class ResearchStatistics:
    total_records: int
    total_executed_trades: int
    dimensions_analyzed: int
    combinations_analyzed: int
    statistically_significant_categories: int
    insufficient_sample_categories: int
    possible_overfitting: tuple[str, ...]
    promising_under_tested: tuple[str, ...]
    statistically_insignificant: tuple[str, ...]
    high_expectancy_low_sample: tuple[str, ...]
    best_trading_hour: str | None
    worst_trading_hour: str | None


@dataclass(frozen=True)
class ResearchLabSummary:
    symbol_performance: tuple[ResearchPerformance, ...]
    timeframe_performance: tuple[ResearchPerformance, ...]
    setup_performance: tuple[ResearchPerformance, ...]
    strategy_performance: tuple[ResearchPerformance, ...]
    regime_performance: tuple[ResearchPerformance, ...]
    confidence_bucket_performance: tuple[ConfidenceBucketPerformance, ...]
    time_of_day_performance: tuple[ResearchPerformance, ...]
    day_of_week_performance: tuple[ResearchPerformance, ...]
    trade_duration_performance: tuple[ResearchPerformance, ...]
    stop_management_performance: tuple[ResearchPerformance, ...]
    entry_model_performance: tuple[ResearchPerformance, ...]
    execution_profile_performance: tuple[ResearchPerformance, ...]
    executive_summary: str
    what_works_best: str
    what_works_worst: str
    where_additional_testing_is_needed: str
    what_should_not_change: str


@dataclass(frozen=True)
class ResearchLabResult:
    research_lab_summary: ResearchLabSummary
    research_rankings: ResearchRankings
    performance_matrices: PerformanceMatrices
    research_statistics: ResearchStatistics
    research_recommendations: tuple[str, ...]


def build_research_lab(
    trades: list[BacktestTrade],
    *,
    management_results: tuple[TradeManagementSensitivityResult, ...],
    entry_timing_summary: EntryTimingSummary | None,
    execution_sensitivity_summary: ExecutionSensitivitySummary | None,
) -> ResearchLabResult:
    """Analyze completed calibration records without feeding results upstream."""

    symbol = _dimension_performance(
        trades, _symbol_name, STANDARD_SYMBOLS
    )
    timeframe = _dimension_performance(
        trades, lambda item: item.timeframe or "unknown", STANDARD_TIMEFRAMES
    )
    setup = _dimension_performance(trades, _setup_family, STANDARD_SETUPS)
    strategy = _dimension_performance(
        trades, lambda item: item.strategy_type, STANDARD_STRATEGIES
    )
    regime = _dimension_performance(trades, _regime_name, STANDARD_REGIMES)
    confidence = _confidence_bucket_performance(trades)
    hourly = _dimension_performance(
        trades, lambda item: f"{_timestamp(item).hour:02d}:00", tuple(f"{hour:02d}:00" for hour in range(24))
    )
    weekday = _dimension_performance(
        trades, lambda item: DAY_NAMES[_timestamp(item).weekday()], DAY_NAMES
    )
    duration = _dimension_performance(
        [item for item in trades if item.outcome_diagnostics is not None],
        _duration_bucket,
        DURATION_BUCKETS,
    )
    management = tuple(_from_management(item) for item in management_results)
    entry_models = _entry_model_performance(entry_timing_summary)
    execution_profiles = _execution_profile_performance(execution_sensitivity_summary)
    matrices = PerformanceMatrices(
        regime_strategy=_matrix(trades, "regime_strategy", _regime_name, lambda item: item.strategy_type),
        setup_regime=_matrix(trades, "setup_regime", _setup_family, _regime_name),
        symbol_setup=_matrix(trades, "symbol_setup", _symbol_name, _setup_family),
        timeframe_setup=_matrix(
            trades,
            "timeframe_setup",
            lambda item: item.timeframe or "unknown",
            _setup_family,
        ),
    )
    dimensions = (
        symbol,
        timeframe,
        setup,
        strategy,
        regime,
        hourly,
        weekday,
        duration,
        management,
        entry_models,
        execution_profiles,
    )
    all_rows = [row for rows in dimensions for row in rows]
    matrix_rows = [
        row.performance
        for rows in (
            matrices.regime_strategy,
            matrices.setup_regime,
            matrices.symbol_setup,
            matrices.timeframe_setup,
        )
        for row in rows
    ]
    rankings = _rankings(matrix_rows or all_rows)
    active_rows = [item for item in all_rows if item.executed_trades]
    best = max(active_rows, key=_strong_sort) if active_rows else None
    worst = min(active_rows, key=_strong_sort) if active_rows else None
    under_tested = [
        item for item in all_rows
        if 0 < item.executed_trades < 20 and item.expectancy > 0
    ]
    insignificant = [
        item for item in all_rows
        if item.executed_trades and item.statistical_significance_score < 40
    ]
    high_low = [
        item for item in all_rows
        if item.executed_trades < 10 and item.expectancy >= 1.0
    ]
    overfit = _possible_overfitting(symbol, timeframe, setup, strategy)
    best_hour, worst_hour = _best_and_worst_hour(hourly)
    statistics = ResearchStatistics(
        total_records=len(trades),
        total_executed_trades=sum(
            item.outcome in {TradeOutcome.WIN, TradeOutcome.LOSS, TradeOutcome.BREAKEVEN}
            for item in trades
        ),
        dimensions_analyzed=len(dimensions),
        combinations_analyzed=len(matrix_rows),
        statistically_significant_categories=sum(
            item.statistical_significance_score >= 70 for item in all_rows
        ),
        insufficient_sample_categories=sum(
            item.sample_quality == "insufficient" for item in all_rows
        ),
        possible_overfitting=overfit,
        promising_under_tested=tuple(_row_name(item) for item in under_tested[:20]),
        statistically_insignificant=tuple(_row_name(item) for item in insignificant[:20]),
        high_expectancy_low_sample=tuple(_row_name(item) for item in high_low[:20]),
        best_trading_hour=best_hour,
        worst_trading_hour=worst_hour,
    )
    recommendations = _research_recommendations(
        best=best,
        worst=worst,
        under_tested=under_tested,
        insignificant=insignificant,
        overfit=overfit,
    )
    best_text = _describe(best, "No category has a closed trade sample yet.")
    worst_text = _describe(worst, "No losing category can be identified yet.")
    summary = ResearchLabSummary(
        symbol_performance=symbol,
        timeframe_performance=timeframe,
        setup_performance=setup,
        strategy_performance=strategy,
        regime_performance=regime,
        confidence_bucket_performance=confidence,
        time_of_day_performance=hourly,
        day_of_week_performance=weekday,
        trade_duration_performance=duration,
        stop_management_performance=management,
        entry_model_performance=entry_models,
        execution_profile_performance=execution_profiles,
        executive_summary=(
            f"The research laboratory analyzed {len(trades)} records and "
            f"{statistics.total_executed_trades} closed trades across "
            f"{len(all_rows)} category rows and {len(matrix_rows)} combinations."
        ),
        what_works_best=best_text,
        what_works_worst=worst_text,
        where_additional_testing_is_needed=(
            f"{len(under_tested)} positive-expectancy categories have fewer than "
            "20 closed trades and require more testing."
        ),
        what_should_not_change=(
            "Do not change production rules from any category marked insufficient, "
            "low quality, statistically insignificant, or high-expectancy/low-sample."
        ),
    )
    return ResearchLabResult(
        research_lab_summary=summary,
        research_rankings=rankings,
        performance_matrices=matrices,
        research_statistics=statistics,
        research_recommendations=recommendations,
    )


def calculate_research_performance(
    category: str, trades: list[BacktestTrade]
) -> ResearchPerformance:
    metrics = calculate_backtest_metrics(trades)
    closed = [
        item.realized_r
        for item in trades
        if item.outcome in {TradeOutcome.WIN, TradeOutcome.LOSS, TradeOutcome.BREAKEVEN}
        and item.realized_r is not None
    ]
    diagnostics = [item.outcome_diagnostics for item in trades if item.outcome_diagnostics]
    durations = [item.bars_to_outcome for item in diagnostics if item.bars_to_outcome is not None]
    confidences = [
        item.decision_diagnostics.final_confidence
        for item in trades
        if item.decision_diagnostics is not None
    ]
    interval = _confidence_interval(closed)
    significance = _significance_score(closed)
    quality = _sample_quality(len(closed))
    return ResearchPerformance(
        category=category,
        records_seen=len(trades),
        executed_trades=metrics.total_trades,
        wins=metrics.wins,
        losses=metrics.losses,
        breakeven=metrics.breakeven,
        win_rate=metrics.win_rate,
        average_r=metrics.average_r,
        total_r=metrics.total_r,
        expectancy=metrics.average_r,
        profit_factor=metrics.profit_factor,
        max_drawdown=metrics.max_drawdown_r,
        average_mfe=(
            round(mean(item.max_favorable_excursion_r for item in diagnostics), 6)
            if diagnostics else 0.0
        ),
        average_mae=(
            round(mean(item.max_adverse_excursion_r for item in diagnostics), 6)
            if diagnostics else 0.0
        ),
        average_trade_duration=round(mean(durations), 3) if durations else 0.0,
        average_confidence=round(mean(confidences), 3) if confidences else 0.0,
        confidence_interval=interval,
        statistical_significance_score=significance,
        sample_quality=quality,
        recommendation=_performance_recommendation(
            category, len(closed), metrics.average_r, significance
        ),
    )


def _dimension_performance(
    trades: list[BacktestTrade],
    key,
    standards: tuple[str, ...],
) -> tuple[ResearchPerformance, ...]:
    groups: dict[str, list[BacktestTrade]] = defaultdict(list)
    for trade in trades:
        groups[key(trade)].append(trade)
    names = list(standards) + sorted(set(groups) - set(standards))
    return tuple(calculate_research_performance(name, groups[name]) for name in names)


def _matrix(trades: list[BacktestTrade], matrix: str, left_key, right_key) -> tuple[ResearchMatrixRow, ...]:
    groups: dict[tuple[str, str], list[BacktestTrade]] = defaultdict(list)
    for trade in trades:
        groups[(left_key(trade), right_key(trade))].append(trade)
    return tuple(
        ResearchMatrixRow(
            matrix=matrix,
            left=left,
            right=right,
            performance=calculate_research_performance(f"{left} + {right}", records),
        )
        for (left, right), records in sorted(groups.items())
    )


def _confidence_bucket_performance(
    trades: list[BacktestTrade],
) -> tuple[ConfidenceBucketPerformance, ...]:
    groups: dict[str, list[BacktestTrade]] = defaultdict(list)
    for trade in trades:
        confidence = (
            trade.decision_diagnostics.final_confidence
            if trade.decision_diagnostics is not None else None
        )
        if confidence is not None:
            bucket = _confidence_bucket(confidence)
            if bucket:
                groups[bucket].append(trade)
    rows: list[ConfidenceBucketPerformance] = []
    for bucket in CONFIDENCE_BUCKETS:
        metrics = calculate_backtest_metrics(groups[bucket])
        rows.append(
            ConfidenceBucketPerformance(
                confidence_bucket=bucket,
                trades=metrics.total_trades,
                win_rate=metrics.win_rate,
                average_r=metrics.average_r,
                expectancy=metrics.average_r,
                profit_factor=metrics.profit_factor,
            )
        )
    return tuple(rows)


def _from_management(item: TradeManagementSensitivityResult) -> ResearchPerformance:
    return _performance_from_aggregate(
        category=item.rule.value,
        records=item.simulated_trades,
        trades=item.simulated_trades,
        wins=item.wins,
        losses=item.losses,
        breakeven=item.breakeven,
        win_rate=(100.0 * item.wins / item.simulated_trades if item.simulated_trades else 0.0),
        average_r=item.average_r,
        total_r=item.total_r,
        profit_factor=item.profit_factor,
        drawdown=item.max_drawdown_r,
    )


def _entry_model_performance(summary: EntryTimingSummary | None) -> tuple[ResearchPerformance, ...]:
    if summary is None:
        return ()
    return tuple(
        _performance_from_aggregate(
            category=item.profile_name,
            records=item.total_candidates,
            trades=item.filled_trades,
            wins=item.wins,
            losses=item.losses,
            breakeven=item.breakeven,
            win_rate=item.win_rate,
            average_r=item.average_r,
            total_r=item.total_r,
            profit_factor=item.profit_factor,
            drawdown=item.max_drawdown_r,
        )
        for item in summary.profiles
    )


def _execution_profile_performance(
    summary: ExecutionSensitivitySummary | None,
) -> tuple[ResearchPerformance, ...]:
    if summary is None:
        return ()
    return tuple(
        _performance_from_aggregate(
            category=item.profile_name,
            records=item.total_trades,
            trades=item.total_trades,
            wins=item.wins,
            losses=item.losses,
            breakeven=item.breakeven,
            win_rate=item.win_rate,
            average_r=item.average_r,
            total_r=item.total_r,
            profit_factor=item.profit_factor,
            drawdown=item.max_drawdown_r,
        )
        for item in summary.profiles
    )


def _performance_from_aggregate(
    *,
    category: str,
    records: int,
    trades: int,
    wins: int,
    losses: int,
    breakeven: int,
    win_rate: float,
    average_r: float,
    total_r: float,
    profit_factor: float | None,
    drawdown: float,
) -> ResearchPerformance:
    quality = _sample_quality(trades)
    significance = _aggregate_significance(trades, average_r)
    return ResearchPerformance(
        category=category,
        records_seen=records,
        executed_trades=trades,
        wins=wins,
        losses=losses,
        breakeven=breakeven,
        win_rate=round(win_rate, 3),
        average_r=average_r,
        total_r=total_r,
        expectancy=average_r,
        profit_factor=profit_factor,
        max_drawdown=drawdown,
        average_mfe=0.0,
        average_mae=0.0,
        average_trade_duration=0.0,
        average_confidence=0.0,
        confidence_interval=ResearchConfidenceInterval(
            average_r, average_r, 95.0, trades
        ),
        statistical_significance_score=significance,
        sample_quality=quality,
        recommendation=_performance_recommendation(
            category, trades, average_r, significance
        ),
    )


def _rankings(rows: list[ResearchPerformance]) -> ResearchRankings:
    active = [item for item in rows if item.executed_trades]
    ranked = sorted(active, key=_strong_sort, reverse=True)
    weak = sorted(active, key=_strong_sort)
    items = [_ranked(item) for item in ranked]
    weak_items = [_ranked(item) for item in weak]
    return ResearchRankings(
        top_10_strongest_combinations=tuple(items[:10]),
        top_10_weakest_combinations=tuple(weak_items[:10]),
        highest_expectancy=_pick_ranked(active, lambda item: item.expectancy, True),
        highest_profit_factor=_pick_ranked(
            [item for item in active if item.profit_factor is not None],
            lambda item: item.profit_factor or 0.0,
            True,
        ),
        lowest_drawdown=_pick_ranked(active, lambda item: item.max_drawdown, False),
        highest_statistical_confidence=_pick_ranked(
            active, lambda item: item.statistical_significance_score, True
        ),
        largest_sample_size=_pick_ranked(
            active, lambda item: item.executed_trades, True
        ),
    )


def _confidence_interval(values: list[float]) -> ResearchConfidenceInterval:
    if not values:
        return ResearchConfidenceInterval(0.0, 0.0, 95.0, 0)
    average = mean(values)
    deviation = pstdev(values)
    margin = 1.96 * deviation / sqrt(len(values)) if len(values) > 1 else 0.0
    return ResearchConfidenceInterval(
        lower=round(average - margin, 6),
        upper=round(average + margin, 6),
        confidence_level=95.0,
        sample_size=len(values),
    )


def _significance_score(values: list[float]) -> float:
    if not values:
        return 0.0
    average = abs(mean(values))
    deviation = pstdev(values)
    signal = min(1.0, average / (deviation / sqrt(len(values)))) if deviation else (1.0 if average else 0.0)
    sample = min(1.0, len(values) / 30.0)
    return round(100.0 * signal * sample, 3)


def _aggregate_significance(trades: int, average_r: float) -> float:
    return round(min(100.0, trades / 30.0 * 100.0) * min(1.0, abs(average_r)), 3)


def _sample_quality(sample: int) -> str:
    if sample < 5:
        return "insufficient"
    if sample < 20:
        return "low"
    if sample < 50:
        return "moderate"
    return "high"


def _performance_recommendation(
    category: str, sample: int, expectancy: float, significance: float
) -> str:
    if sample < 5:
        return (
            f"Do not change production behavior from {category}; fewer than five "
            "closed trades are available."
        )
    if sample < 20:
        return f"{category} is under-tested; collect at least 20 closed trades before interpretation."
    if significance < 40:
        return f"{category} is statistically insignificant in the current sample."
    if expectancy > 0:
        return f"{category} is promising research evidence but still requires out-of-sample confirmation."
    return f"{category} underperformed historically; investigate causes without automatic filtering."


def _possible_overfitting(
    symbols: tuple[ResearchPerformance, ...],
    timeframes: tuple[ResearchPerformance, ...],
    setups: tuple[ResearchPerformance, ...],
    strategies: tuple[ResearchPerformance, ...],
) -> tuple[str, ...]:
    messages: list[str] = []
    for label, rows in (
        ("symbol", symbols),
        ("timeframe", timeframes),
        ("setup", setups),
        ("strategy", strategies),
    ):
        active = [item for item in rows if item.executed_trades]
        total = sum(abs(item.total_r) for item in active)
        if len(active) > 1 and total:
            dominant = max(active, key=lambda item: abs(item.total_r))
            if abs(dominant.total_r) / total >= 0.70:
                messages.append(
                    f"Possible overfitting: {dominant.category} contributes at "
                    f"least 70% of absolute {label} performance."
                )
    return tuple(messages)


def _research_recommendations(
    *,
    best: ResearchPerformance | None,
    worst: ResearchPerformance | None,
    under_tested: list[ResearchPerformance],
    insignificant: list[ResearchPerformance],
    overfit: tuple[str, ...],
) -> tuple[str, ...]:
    messages = [
        "Research rankings are historical diagnostics and must not change production routing automatically."
    ]
    if best:
        messages.append(
            f"{best.category} currently has the strongest sampled expectancy at {best.expectancy:.3f}R."
        )
    if worst:
        messages.append(
            f"{worst.category} currently has the weakest sampled expectancy at {worst.expectancy:.3f}R."
        )
    if under_tested:
        messages.append(
            f"{len(under_tested)} promising categories remain under-tested; "
            "collect more trades before changes."
        )
    if insignificant:
        messages.append(
            f"{len(insignificant)} active categories remain statistically insignificant."
        )
    messages.extend(overfit)
    return tuple(messages)


def _symbol_name(trade: BacktestTrade) -> str:
    compact = trade.symbol.upper().replace("-", "").replace("=X", "")
    return {
        "BTCUSD": "BTC",
        "ETHUSD": "ETH",
        "EURUSD": "EURUSD",
        "GBPUSD": "GBPUSD",
    }.get(compact, trade.symbol.upper())


def _setup_family(trade: BacktestTrade) -> str:
    value = trade.setup_type
    aliases = {
        "liquidity_sweep_reversal_long": "liquidity_sweep_long",
        "liquidity_sweep_reversal_short": "liquidity_sweep_short",
        "range_reversal_long": "range_reversal",
        "range_reversal_short": "range_reversal",
        "bullish_pullback_continuation": "pullback_continuation",
        "bearish_pullback_continuation": "pullback_continuation",
        "compression_breakout_long": "compression_breakout",
        "compression_breakout_short": "compression_breakout",
    }
    return aliases.get(value, value)


def _regime_name(trade: BacktestTrade) -> str:
    return (
        trade.market_regime.market_regime.value
        if trade.market_regime is not None else "unknown"
    )


def _timestamp(trade: BacktestTrade) -> datetime:
    return datetime.fromtimestamp(trade.timestamp, tz=timezone.utc)


def _duration_bucket(trade: BacktestTrade) -> str:
    bars = trade.outcome_diagnostics.bars_to_outcome or 0
    if bars <= 1:
        return "1 candle"
    if bars == 2:
        return "2 candles"
    if bars <= 5:
        return "3-5"
    if bars <= 10:
        return "6-10"
    return "10+"


def _confidence_bucket(confidence: float) -> str | None:
    for lower, upper in ((40, 49), (50, 59), (60, 69), (70, 79), (80, 89), (90, 100)):
        if lower <= confidence <= upper:
            return f"{lower}-{upper}"
    return None


def _best_and_worst_hour(
    rows: tuple[ResearchPerformance, ...]
) -> tuple[str | None, str | None]:
    active = [item for item in rows if item.executed_trades]
    if not active:
        return None, None
    ordered = sorted(active, key=lambda item: (item.expectancy, item.category))
    return ordered[-1].category, ordered[0].category


def _strong_sort(item: ResearchPerformance) -> tuple[float, float, int]:
    return (
        item.expectancy,
        item.statistical_significance_score,
        item.executed_trades,
    )


def _ranked(item: ResearchPerformance) -> RankedResearchItem:
    return RankedResearchItem(
        name=item.category,
        dimension="combination",
        expectancy=item.expectancy,
        profit_factor=item.profit_factor,
        max_drawdown=item.max_drawdown,
        statistical_significance_score=item.statistical_significance_score,
        sample_size=item.executed_trades,
    )


def _pick_ranked(rows: list[ResearchPerformance], key, highest: bool) -> RankedResearchItem | None:
    if not rows:
        return None
    selected = sorted(rows, key=lambda item: (key(item), item.category), reverse=highest)[0]
    return _ranked(selected)


def _row_name(item: ResearchPerformance) -> str:
    return f"{item.category} ({item.executed_trades} trades, {item.expectancy:.3f}R)"


def _describe(item: ResearchPerformance | None, fallback: str) -> str:
    if item is None:
        return fallback
    return (
        f"{item.category} has {item.expectancy:.3f}R expectancy across "
        f"{item.executed_trades} trades with {item.sample_quality} sample quality."
    )
