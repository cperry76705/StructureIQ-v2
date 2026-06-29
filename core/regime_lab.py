"""Aggregate strategy and setup behavior by deterministic market regime."""

from collections import defaultdict
from dataclasses import dataclass, replace

from core.backtesting import BacktestTrade, calculate_backtest_metrics
from core.journal import TradeOutcome
from core.regime import MarketRegime


@dataclass(frozen=True)
class RegimePerformance:
    market_regime: MarketRegime
    records_seen: int
    executed_trades: int
    wins: int
    losses: int
    breakeven: int
    win_rate: float
    average_r: float
    total_r: float
    profit_factor: float | None
    max_drawdown: float
    average_trade_duration: float
    average_mfe: float
    average_mae: float
    best_strategy: str | None
    worst_strategy: str | None
    best_setup: str | None
    worst_setup: str | None
    human_readable_summary: str


@dataclass(frozen=True)
class RegimeMatrixPerformance:
    market_regime: MarketRegime
    records_seen: int
    executed_trades: int
    wins: int
    losses: int
    breakeven: int
    win_rate: float
    average_r: float
    total_r: float
    profit_factor: float | None
    max_drawdown: float


@dataclass(frozen=True)
class StrategyRegimeMatrix:
    strategy_type: str
    performance_by_regime: tuple[RegimeMatrixPerformance, ...]


@dataclass(frozen=True)
class SetupRegimeMatrix:
    setup_type: str
    performance_by_regime: tuple[RegimeMatrixPerformance, ...]


@dataclass(frozen=True)
class MarketRegimeSummary:
    regimes: tuple[RegimePerformance, ...]
    best_regime: str | None
    worst_regime: str | None
    highest_expectancy_regime: str | None
    highest_winrate_regime: str | None
    lowest_drawdown_regime: str | None
    largest_sample_regime: str | None
    human_readable_summary: str
    recommendations: tuple[str, ...]


@dataclass(frozen=True)
class RegimeClassifierComparison:
    legacy_transition_ratio: float
    tuned_transition_ratio: float
    transition_reduction: float
    legacy_trend_count: int
    tuned_trend_count: int
    trend_count_increase: int
    records_changed: int
    changed_percentage: float
    agreement_rate: float
    changed_from_transition_to_trend: int
    changed_from_transition_to_range: int
    changed_from_transition_to_compression: int
    changed_from_transition_to_expansion: int
    human_readable_summary: str
    recommendations: tuple[str, ...]


def build_regime_classifier_comparison(
    trades: list[BacktestTrade],
) -> tuple[MarketRegimeSummary, MarketRegimeSummary, RegimeClassifierComparison]:
    """Compare immutable legacy and tuned labels over identical trade records."""

    comparable = [
        trade for trade in trades
        if trade.market_regime is not None and trade.tuned_market_regime is not None
    ]
    tuned_view = [
        replace(trade, market_regime=trade.tuned_market_regime)
        for trade in trades
    ]
    legacy_summary = build_market_regime_analysis(trades)[0]
    tuned_summary = build_market_regime_analysis(tuned_view)[0]
    total = len(comparable)
    legacy_transition = sum(
        trade.market_regime.market_regime is MarketRegime.TRANSITION
        for trade in comparable
    )
    tuned_transition = sum(
        trade.tuned_market_regime.market_regime is MarketRegime.TRANSITION
        for trade in comparable
    )
    legacy_trends = sum(
        _is_trend(trade.market_regime.market_regime) for trade in comparable
    )
    tuned_trends = sum(
        _is_trend(trade.tuned_market_regime.market_regime) for trade in comparable
    )
    changed = [
        trade for trade in comparable
        if trade.market_regime.market_regime is not trade.tuned_market_regime.market_regime
    ]
    transition_changes = [
        trade for trade in changed
        if trade.market_regime.market_regime is MarketRegime.TRANSITION
    ]
    legacy_ratio = legacy_transition / total if total else 0.0
    tuned_ratio = tuned_transition / total if total else 0.0
    changed_percentage = 100.0 * len(changed) / total if total else 0.0
    agreement = 100.0 * (total - len(changed)) / total if total else 0.0
    comparison = RegimeClassifierComparison(
        legacy_transition_ratio=round(legacy_ratio, 6),
        tuned_transition_ratio=round(tuned_ratio, 6),
        transition_reduction=round(legacy_ratio - tuned_ratio, 6),
        legacy_trend_count=legacy_trends,
        tuned_trend_count=tuned_trends,
        trend_count_increase=tuned_trends - legacy_trends,
        records_changed=len(changed),
        changed_percentage=round(changed_percentage, 3),
        agreement_rate=round(agreement, 3),
        changed_from_transition_to_trend=sum(
            _is_trend(trade.tuned_market_regime.market_regime)
            for trade in transition_changes
        ),
        changed_from_transition_to_range=_transition_target_count(
            transition_changes, MarketRegime.RANGE
        ),
        changed_from_transition_to_compression=_transition_target_count(
            transition_changes, MarketRegime.COMPRESSION
        ),
        changed_from_transition_to_expansion=_transition_target_count(
            transition_changes, MarketRegime.EXPANSION
        ),
        human_readable_summary=(
            f"Across {total} identical records, tuned classification reduced "
            f"transition from {legacy_ratio:.1%} to {tuned_ratio:.1%} and "
            f"increased trend labels from {legacy_trends} to {tuned_trends}. "
            "Trade outcomes and calibration metrics were not recalculated."
        ),
        recommendations=_comparison_recommendations(
            total=total,
            legacy_ratio=legacy_ratio,
            tuned_ratio=tuned_ratio,
            changed_percentage=changed_percentage,
            tuned_trends=tuned_trends,
        ),
    )
    return legacy_summary, tuned_summary, comparison


def tuned_regime_view(trades: list[BacktestTrade]) -> list[BacktestTrade]:
    """Return research copies grouped by tuned labels, leaving originals untouched."""

    return [
        replace(
            trade,
            market_regime=trade.tuned_market_regime or trade.market_regime,
        )
        for trade in trades
    ]


def _is_trend(regime: MarketRegime) -> bool:
    return regime in {
        MarketRegime.STRONG_BULL_TREND,
        MarketRegime.WEAK_BULL_TREND,
        MarketRegime.STRONG_BEAR_TREND,
        MarketRegime.WEAK_BEAR_TREND,
    }


def _transition_target_count(
    trades: list[BacktestTrade], target: MarketRegime
) -> int:
    return sum(
        trade.tuned_market_regime.market_regime is target for trade in trades
    )


def _comparison_recommendations(
    *,
    total: int,
    legacy_ratio: float,
    tuned_ratio: float,
    changed_percentage: float,
    tuned_trends: int,
) -> tuple[str, ...]:
    messages: list[str] = []
    if not total:
        return (
            "Collect comparable legacy and tuned classifications before interpretation.",
        )
    if tuned_ratio < legacy_ratio:
        messages.append(
            "The tuned classifier reduces transition dominance; validate the new "
            "trend labels against forward behavior before any production adoption."
        )
    if tuned_ratio > 0.60:
        messages.append(
            "Transition remains above 60% under tuned rules; inspect recent-event "
            "and conflict evidence further."
        )
    if changed_percentage > 50.0:
        messages.append(
            "More than half of labels changed; require out-of-sample validation "
            "because this is a material classifier shift."
        )
    if tuned_trends == 0:
        messages.append(
            "Tuned rules still produce no trend labels; inspect swing-structure "
            "inputs and event recency."
        )
    messages.append(
        "Classifier comparison is research-only and must not be used to infer changed trade performance."
    )
    return tuple(messages)


def build_market_regime_analysis(
    trades: list[BacktestTrade],
) -> tuple[
    MarketRegimeSummary,
    tuple[StrategyRegimeMatrix, ...],
    tuple[SetupRegimeMatrix, ...],
]:
    grouped: dict[MarketRegime, list[BacktestTrade]] = defaultdict(list)
    for trade in trades:
        if trade.market_regime is not None:
            grouped[trade.market_regime.market_regime].append(trade)

    performances = tuple(
        _regime_performance(regime, grouped.get(regime, []))
        for regime in MarketRegime
    )
    active = [item for item in performances if item.executed_trades > 0]
    seen = [item for item in performances if item.records_seen > 0]
    best = _pick(active, lambda item: item.total_r, highest=True)
    worst = _pick(active, lambda item: item.total_r, highest=False)
    expectancy = _pick(active, lambda item: item.average_r, highest=True)
    winrate = _pick(active, lambda item: item.win_rate, highest=True)
    drawdown = _pick(active, lambda item: item.max_drawdown, highest=False)
    sample = _pick(seen, lambda item: item.records_seen, highest=True)

    strategies = _strategy_matrix(trades)
    setups = _setup_matrix(trades)
    recommendations = _recommendations(performances, strategies, setups)
    summary = MarketRegimeSummary(
        regimes=performances,
        best_regime=_name(best),
        worst_regime=_name(worst),
        highest_expectancy_regime=_name(expectancy),
        highest_winrate_regime=_name(winrate),
        lowest_drawdown_regime=_name(drawdown),
        largest_sample_regime=_name(sample),
        human_readable_summary=(
            f"Regime analysis classified {sum(item.records_seen for item in performances)} "
            f"records across {len(seen)} observed regimes. "
            + (
                f"{expectancy.market_regime.value.replace('_', ' ')} had the highest "
                f"expectancy at {expectancy.average_r:.3f}R."
                if expectancy else "No closed regime trades were available."
            )
        ),
        recommendations=recommendations,
    )
    return summary, strategies, setups


def _regime_performance(
    regime: MarketRegime, trades: list[BacktestTrade]
) -> RegimePerformance:
    metrics = calculate_backtest_metrics(trades)
    diagnostics = [trade.outcome_diagnostics for trade in trades if trade.outcome_diagnostics]
    durations = [item.bars_to_outcome for item in diagnostics if item.bars_to_outcome is not None]
    best_strategy, worst_strategy = _best_and_worst(trades, "strategy_type")
    best_setup, worst_setup = _best_and_worst(trades, "setup_type")
    return RegimePerformance(
        market_regime=regime,
        records_seen=len(trades),
        executed_trades=metrics.total_trades,
        wins=metrics.wins,
        losses=metrics.losses,
        breakeven=metrics.breakeven,
        win_rate=metrics.win_rate,
        average_r=metrics.average_r,
        total_r=metrics.total_r,
        profit_factor=metrics.profit_factor,
        max_drawdown=metrics.max_drawdown_r,
        average_trade_duration=(round(sum(durations) / len(durations), 3) if durations else 0.0),
        average_mfe=(
            round(sum(item.max_favorable_excursion_r for item in diagnostics) / len(diagnostics), 3)
            if diagnostics else 0.0
        ),
        average_mae=(
            round(sum(item.max_adverse_excursion_r for item in diagnostics) / len(diagnostics), 3)
            if diagnostics else 0.0
        ),
        best_strategy=best_strategy,
        worst_strategy=worst_strategy,
        best_setup=best_setup,
        worst_setup=worst_setup,
        human_readable_summary=(
            f"{regime.value.replace('_', ' ').title()} contains {len(trades)} records "
            f"and {metrics.total_trades} closed trades at {metrics.average_r:.3f}R average."
        ),
    )


def _best_and_worst(
    trades: list[BacktestTrade], attribute: str
) -> tuple[str | None, str | None]:
    groups: dict[str, list[BacktestTrade]] = defaultdict(list)
    for trade in trades:
        groups[getattr(trade, attribute)].append(trade)
    scored = [
        (name, calculate_backtest_metrics(records).average_r)
        for name, records in groups.items()
        if calculate_backtest_metrics(records).total_trades > 0
    ]
    if not scored:
        return None, None
    scored.sort(key=lambda item: (item[1], item[0]))
    return scored[-1][0], scored[0][0]


def _matrix_performance(
    regime: MarketRegime, trades: list[BacktestTrade]
) -> RegimeMatrixPerformance:
    metrics = calculate_backtest_metrics(trades)
    return RegimeMatrixPerformance(
        market_regime=regime,
        records_seen=len(trades),
        executed_trades=metrics.total_trades,
        wins=metrics.wins,
        losses=metrics.losses,
        breakeven=metrics.breakeven,
        win_rate=metrics.win_rate,
        average_r=metrics.average_r,
        total_r=metrics.total_r,
        profit_factor=metrics.profit_factor,
        max_drawdown=metrics.max_drawdown_r,
    )


def _strategy_matrix(trades: list[BacktestTrade]) -> tuple[StrategyRegimeMatrix, ...]:
    names = sorted({trade.strategy_type for trade in trades})
    return tuple(
        StrategyRegimeMatrix(
            strategy_type=name,
            performance_by_regime=tuple(
                _matrix_performance(
                    regime,
                    [
                        trade for trade in trades
                        if trade.strategy_type == name
                        and trade.market_regime is not None
                        and trade.market_regime.market_regime is regime
                    ],
                )
                for regime in MarketRegime
            ),
        )
        for name in names
    )


def _setup_matrix(trades: list[BacktestTrade]) -> tuple[SetupRegimeMatrix, ...]:
    names = sorted({trade.setup_type for trade in trades})
    return tuple(
        SetupRegimeMatrix(
            setup_type=name,
            performance_by_regime=tuple(
                _matrix_performance(
                    regime,
                    [
                        trade for trade in trades
                        if trade.setup_type == name
                        and trade.market_regime is not None
                        and trade.market_regime.market_regime is regime
                    ],
                )
                for regime in MarketRegime
            ),
        )
        for name in names
    )


def _recommendations(
    regimes: tuple[RegimePerformance, ...],
    strategies: tuple[StrategyRegimeMatrix, ...],
    setups: tuple[SetupRegimeMatrix, ...],
) -> tuple[str, ...]:
    messages: list[str] = []
    for regime in regimes:
        label = regime.market_regime.value.replace("_", " ")
        if 0 < regime.executed_trades < 5:
            messages.append(
                f"{label.title()} has only {regime.executed_trades} closed trades; "
                "collect a larger sample before drawing conclusions."
            )
        if regime.executed_trades >= 2 and regime.average_r < 0:
            messages.append(
                f"{label.title()} has historically weak expectancy of "
                f"{regime.average_r:.3f}R in this sample."
            )
        if regime.max_drawdown >= 3.0:
            messages.append(
                f"{label.title()} produced excessive sampled drawdown of "
                f"{regime.max_drawdown:.2f}R."
            )
    messages.extend(_matrix_recommendations(strategies, "Strategy", "strategy_type"))
    messages.extend(_matrix_recommendations(setups, "Setup", "setup_type"))
    if not messages:
        messages.append(
            "No regime-specific weakness or dominance cleared the minimum sample rules."
        )
    messages.append(
        "Regime findings are research observations and never alter production routing."
    )
    return tuple(messages[:25])


def _matrix_recommendations(rows: tuple[object, ...], label: str, field: str) -> list[str]:
    messages: list[str] = []
    for row in rows:
        name = getattr(row, field)
        active = [item for item in row.performance_by_regime if item.executed_trades >= 2]
        if not active:
            continue
        best = max(active, key=lambda item: (item.average_r, item.market_regime.value))
        worst = min(active, key=lambda item: (item.average_r, item.market_regime.value))
        if best.average_r > 0:
            messages.append(
                f"{label} {name.replace('_', ' ')} dominates its sampled "
                f"{best.market_regime.value.replace('_', ' ')} regime at "
                f"{best.average_r:.3f}R average."
            )
        if worst.average_r < 0:
            messages.append(
                f"{label} {name.replace('_', ' ')} underperforms in "
                f"{worst.market_regime.value.replace('_', ' ')} at "
                f"{worst.average_r:.3f}R average."
            )
    return messages


def _pick(items: list[RegimePerformance], key, *, highest: bool) -> RegimePerformance | None:
    if not items:
        return None
    return sorted(items, key=lambda item: (key(item), item.market_regime.value), reverse=highest)[0]


def _name(item: RegimePerformance | None) -> str | None:
    return item.market_regime.value if item else None
