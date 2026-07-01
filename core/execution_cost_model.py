"""Opt-in, deterministic execution-cost research over finalized trade records."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from statistics import mean
from typing import Any, Iterable


@dataclass(frozen=True)
class ExecutionCostAssumptions:
    spread_bps: float
    slippage_bps: float
    commission_per_trade: float
    stop_slippage_bps: float
    latency_ms: int | None
    source: str


@dataclass(frozen=True)
class ExecutionCostTrade:
    symbol: str
    strategy: str
    setup: str
    baseline_r: float
    realistic_r: float
    spread_cost_r: float
    slippage_cost_r: float
    stop_slippage_cost_r: float
    commission_cost_r: float
    latency_cost_r: float
    total_cost_r: float


@dataclass(frozen=True)
class RealisticMetrics:
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
class ExecutionCostSummary:
    enabled: bool
    modeled_trades: int
    assumptions_by_asset_class: dict[str, ExecutionCostAssumptions]
    baseline_total_r: float
    realistic_total_r: float
    baseline_expectancy: float
    realistic_expectancy: float
    total_execution_degradation_r: float
    expectancy_reduction: float
    profit_factor_reduction: float | None
    drawdown_impact_r: float
    average_spread_cost_r: float
    average_slippage_cost_r: float
    average_stop_slippage_cost_r: float
    average_commission_cost_r: float
    average_latency_cost_r: float
    human_readable_summary: str


@dataclass(frozen=True)
class CostSensitivity:
    name: str
    modeled_trades: int
    total_degradation_r: float
    average_degradation_r: float


@dataclass(frozen=True)
class AggregateExecutionCostSummary:
    enabled: bool
    baseline_total_r: float
    realistic_total_r: float
    baseline_expectancy: float
    realistic_expectancy: float
    total_degradation_r: float
    degradation_percent: float
    baseline_profit_factor: float | None
    realistic_profit_factor: float | None
    profit_factor_reduction: float | None
    baseline_drawdown_r: float
    realistic_drawdown_r: float
    drawdown_impact_r: float
    symbols_most_affected: tuple[CostSensitivity, ...]
    strategies_most_affected: tuple[CostSensitivity, ...]
    setups_most_affected: tuple[CostSensitivity, ...]
    warnings: tuple[str, ...]
    human_readable_summary: str


class ExecutionCostModel:
    """Apply adverse costs after outcomes are finalized; never changes trade selection."""

    def model(
        self,
        trades: Iterable[Any],
        *,
        enabled: bool,
        spread_bps: float | None = None,
        slippage_bps: float | None = None,
        commission_per_trade: float = 0.0,
        stop_slippage_bps: float | None = None,
        latency_ms: int | None = None,
        starting_balance: float = 10_000.0,
        risk_per_trade_percent: float = 1.0,
    ) -> tuple[ExecutionCostSummary | None, RealisticMetrics | None, tuple[str, ...], tuple[ExecutionCostTrade, ...]]:
        if not enabled:
            return None, None, (), ()
        modeled: list[ExecutionCostTrade] = []
        assumptions: dict[str, ExecutionCostAssumptions] = {}
        for trade in trades:
            baseline = getattr(trade, "realized_r", None)
            entry = getattr(trade, "entry", None)
            stop = getattr(trade, "stop_loss", None)
            if baseline is None or entry is None or stop is None:
                continue
            asset = infer_asset_class(str(getattr(trade, "symbol", "")))
            resolved = resolve_assumptions(
                asset,
                spread_bps=spread_bps,
                slippage_bps=slippage_bps,
                commission_per_trade=commission_per_trade,
                stop_slippage_bps=stop_slippage_bps,
                latency_ms=latency_ms,
            )
            assumptions[asset] = resolved
            risk = abs(float(entry) - float(stop))
            if risk <= 0:
                continue
            price = abs(float(entry))
            spread_r = price * resolved.spread_bps / 10_000 / risk
            slip_r = price * resolved.slippage_bps / 10_000 / risk
            stop_r = (
                price * resolved.stop_slippage_bps / 10_000 / risk
                if float(baseline) < 0 else 0.0
            )
            risk_capital = starting_balance * risk_per_trade_percent / 100
            commission_r = resolved.commission_per_trade / risk_capital if risk_capital > 0 else 0.0
            latency_r = (
                price * resolved.slippage_bps / 10_000 / risk
                * min(max(resolved.latency_ms or 0, 0), 5_000) / 5_000
                * 0.25
            )
            costs = [max(0.0, value) for value in (spread_r, slip_r, stop_r, commission_r, latency_r)]
            total = sum(costs)
            realistic = min(float(baseline), float(baseline) - total)
            modeled.append(
                ExecutionCostTrade(
                    symbol=str(getattr(trade, "symbol", "unknown")),
                    strategy=str(getattr(trade, "strategy_type", "unknown")),
                    setup=str(getattr(trade, "setup_type", "unknown")),
                    baseline_r=round(float(baseline), 6),
                    realistic_r=round(realistic, 6),
                    spread_cost_r=round(costs[0], 6),
                    slippage_cost_r=round(costs[1], 6),
                    stop_slippage_cost_r=round(costs[2], 6),
                    commission_cost_r=round(costs[3], 6),
                    latency_cost_r=round(costs[4], 6),
                    total_cost_r=round(total, 6),
                )
            )
        baseline_values = [item.baseline_r for item in modeled]
        realistic_values = [item.realistic_r for item in modeled]
        baseline_metrics = calculate_realistic_metrics(baseline_values)
        realistic_metrics = calculate_realistic_metrics(realistic_values)
        count = len(modeled)
        degradation = max(0.0, baseline_metrics.total_r - realistic_metrics.total_r)
        pf_reduction = _nonnegative_reduction(baseline_metrics.profit_factor, realistic_metrics.profit_factor)
        summary = ExecutionCostSummary(
            enabled=True,
            modeled_trades=count,
            assumptions_by_asset_class=assumptions,
            baseline_total_r=baseline_metrics.total_r,
            realistic_total_r=min(baseline_metrics.total_r, realistic_metrics.total_r),
            baseline_expectancy=baseline_metrics.average_r,
            realistic_expectancy=min(baseline_metrics.average_r, realistic_metrics.average_r),
            total_execution_degradation_r=round(degradation, 6),
            expectancy_reduction=round(max(0.0, baseline_metrics.average_r - realistic_metrics.average_r), 6),
            profit_factor_reduction=pf_reduction,
            drawdown_impact_r=round(max(0.0, realistic_metrics.max_drawdown_r - baseline_metrics.max_drawdown_r), 6),
            average_spread_cost_r=_average(modeled, "spread_cost_r"),
            average_slippage_cost_r=_average(modeled, "slippage_cost_r"),
            average_stop_slippage_cost_r=_average(modeled, "stop_slippage_cost_r"),
            average_commission_cost_r=_average(modeled, "commission_cost_r"),
            average_latency_cost_r=_average(modeled, "latency_cost_r"),
            human_readable_summary=(
                f"Execution costs reduced {count} completed trades from {baseline_metrics.total_r:.3f}R "
                f"to {realistic_metrics.total_r:.3f}R ({degradation:.3f}R degradation)."
                if count else "Execution-cost modeling was enabled, but no completed trades with valid risk geometry were available."
            ),
        )
        recommendations = _recommendations(summary)
        return summary, realistic_metrics, recommendations, tuple(modeled)

    def aggregate(self, modeled: Iterable[ExecutionCostTrade], summary: ExecutionCostSummary) -> AggregateExecutionCostSummary:
        records = tuple(modeled)
        baseline = calculate_realistic_metrics([item.baseline_r for item in records])
        realistic = calculate_realistic_metrics([item.realistic_r for item in records])
        degradation = max(0.0, baseline.total_r - realistic.total_r)
        percentage = degradation / abs(baseline.total_r) * 100 if baseline.total_r else 0.0
        warnings = list(_recommendations(summary))
        if percentage >= 50:
            warnings.append("Execution costs remove at least half of baseline total R.")
        return AggregateExecutionCostSummary(
            enabled=True,
            baseline_total_r=baseline.total_r,
            realistic_total_r=min(baseline.total_r, realistic.total_r),
            baseline_expectancy=baseline.average_r,
            realistic_expectancy=min(baseline.average_r, realistic.average_r),
            total_degradation_r=round(degradation, 6),
            degradation_percent=round(max(0.0, percentage), 3),
            baseline_profit_factor=baseline.profit_factor,
            realistic_profit_factor=realistic.profit_factor,
            profit_factor_reduction=_nonnegative_reduction(baseline.profit_factor, realistic.profit_factor),
            baseline_drawdown_r=baseline.max_drawdown_r,
            realistic_drawdown_r=max(baseline.max_drawdown_r, realistic.max_drawdown_r),
            drawdown_impact_r=round(max(0.0, realistic.max_drawdown_r - baseline.max_drawdown_r), 6),
            symbols_most_affected=_sensitivity(records, "symbol"),
            strategies_most_affected=_sensitivity(records, "strategy"),
            setups_most_affected=_sensitivity(records, "setup"),
            warnings=tuple(dict.fromkeys(warnings)),
            human_readable_summary=summary.human_readable_summary,
        )


def infer_asset_class(symbol: str) -> str:
    normalized = symbol.upper().replace("=X", "")
    if normalized.startswith(("BTC", "ETH")):
        return "crypto"
    compact = normalized.replace("-", "")
    currencies = {"USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD"}
    if len(compact) == 6 and compact[:3] in currencies and compact[3:] in currencies:
        return "forex"
    return "stocks_etfs"


def resolve_assumptions(asset_class: str, *, spread_bps=None, slippage_bps=None, commission_per_trade=0.0, stop_slippage_bps=None, latency_ms=None) -> ExecutionCostAssumptions:
    defaults = {
        "crypto": (8.0, 5.0, 8.0),
        "forex": (1.5, 1.0, 2.0),
        "stocks_etfs": (3.0, 2.0, 4.0),
    }[asset_class]
    custom = any(value is not None for value in (spread_bps, slippage_bps, stop_slippage_bps)) or commission_per_trade > 0 or latency_ms is not None
    return ExecutionCostAssumptions(
        spread_bps=float(defaults[0] if spread_bps is None else spread_bps),
        slippage_bps=float(defaults[1] if slippage_bps is None else slippage_bps),
        commission_per_trade=float(commission_per_trade),
        stop_slippage_bps=float(defaults[2] if stop_slippage_bps is None else stop_slippage_bps),
        latency_ms=latency_ms,
        source="custom" if custom else f"conservative_{asset_class}_default",
    )


def calculate_realistic_metrics(values: Iterable[float]) -> RealisticMetrics:
    returns = tuple(float(value) for value in values)
    wins = sum(value > 0 for value in returns); losses = sum(value < 0 for value in returns)
    breakeven = len(returns) - wins - losses
    positives = sum(value for value in returns if value > 0); negatives = abs(sum(value for value in returns if value < 0))
    equity = peak = drawdown = 0.0
    for value in returns:
        equity += value; peak = max(peak, equity); drawdown = max(drawdown, peak - equity)
    return RealisticMetrics(
        total_trades=len(returns), wins=wins, losses=losses, breakeven=breakeven,
        win_rate=round(wins / len(returns) * 100, 3) if returns else 0.0,
        average_r=round(mean(returns), 6) if returns else 0.0,
        total_r=round(sum(returns), 6),
        profit_factor=round(positives / negatives, 6) if negatives else None,
        max_drawdown_r=round(drawdown, 6),
    )


def _average(records, field):
    return round(mean(getattr(item, field) for item in records), 6) if records else 0.0


def _nonnegative_reduction(baseline, realistic):
    if baseline is None or realistic is None:
        return None
    return round(max(0.0, baseline - realistic), 6)


def _recommendations(summary: ExecutionCostSummary) -> tuple[str, ...]:
    if not summary.modeled_trades:
        return ("Collect completed trades with valid entry and stop geometry before interpreting execution costs.",)
    if summary.expectancy_reduction >= max(0.25, abs(summary.baseline_expectancy) * 0.5):
        return ("Execution degradation is material; validate symbol-specific spread, slippage, and fee assumptions before paper trading.",)
    return ("Execution degradation is currently modest; continue validating assumptions against representative venue data.",)


def _sensitivity(records, field) -> tuple[CostSensitivity, ...]:
    groups: dict[str, list[float]] = defaultdict(list)
    for item in records:
        groups[getattr(item, field)].append(item.total_cost_r)
    values = [CostSensitivity(name, len(costs), round(sum(costs), 6), round(mean(costs), 6)) for name, costs in groups.items()]
    return tuple(sorted(values, key=lambda item: item.total_degradation_r, reverse=True))
