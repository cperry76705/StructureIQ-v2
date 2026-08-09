"""Read-only opportunity coverage analytics.

This module measures where observed markets stop in the existing StructureIQ
pipeline. It does not create signals, adjust thresholds, approve candidates, or
change order/trade lifecycle behavior.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Iterable

from fastapi.encoders import jsonable_encoder

from core.candidate_pipeline_diagnostics import (
    CandidatePipelineCycleDiagnostic,
    CandidateSymbolPipelineDiagnostic,
    get_global_candidate_pipeline_diagnostics,
)
from core.market_session_engine import AssetClass, classify_symbol
from core.paper_trade_journal import PaperTradeJournal, PaperTradeJournalEntry, current_paper_trade_journal
from core.symbol_registry import DEFAULT_SYMBOL_UNIVERSE, SymbolRegistry, get_symbol_registry


STAGES: tuple[str, ...] = (
    "MARKET_AVAILABLE",
    "STRUCTURE_DETECTED",
    "DIRECTIONAL_BIAS",
    "TIMEFRAME_ALIGNMENT",
    "SETUP_DETECTED",
    "CONFIDENCE_PASSED",
    "SETUP_QUALITY_PASSED",
    "EXECUTION_PASSED",
    "RISK_PASSED",
    "CANDIDATE_CREATED",
    "AUTO_APPROVAL_PASSED",
    "ORDER_CREATED",
    "TRADE_OPENED",
    "TRADE_CLOSED",
)

TERMINAL_STAGES: tuple[str, ...] = (
    "NO_SETUP",
    "STRUCTURE",
    "BIAS",
    "TIMEFRAME_ALIGNMENT",
    "CONFIDENCE",
    "SETUP_QUALITY",
    "EXECUTION",
    "RISK",
    "DUPLICATE",
    "POSITION_LIMIT",
    "DAILY_LIMIT",
    "AUTO_APPROVAL",
    "ORDER_CREATION",
    "ORDER_NOT_FILLED",
    "MARKET_CLOSED",
    "PROVIDER_FAILURE",
    "UNKNOWN",
)

_PRIMARY_STAGE_MAP = {
    "MARKET_DATA": "PROVIDER_FAILURE",
    "MARKET_STRUCTURE": "STRUCTURE",
    "SETUP_DETECTION": "NO_SETUP",
    "CONFIDENCE": "CONFIDENCE",
    "TIMEFRAME_ALIGNMENT": "TIMEFRAME_ALIGNMENT",
    "BIAS": "BIAS",
    "SETUP_QUALITY": "SETUP_QUALITY",
    "RISK": "RISK",
    "DUPLICATE": "DUPLICATE",
    "AUTO_APPROVAL": "AUTO_APPROVAL",
}


@dataclass(frozen=True)
class OpportunityCoverageSummary:
    markets_analyzed: int
    raw_setups: int
    qualified_setups: int
    candidates_created: int
    approved_candidates: int
    orders_created: int
    trades_opened: int
    trades_closed: int
    analysis_to_setup_rate: float | None
    setup_to_qualified_rate: float | None
    qualified_to_candidate_rate: float | None
    candidate_to_approval_rate: float | None
    approval_to_order_rate: float | None
    order_to_trade_rate: float | None
    analysis_to_trade_rate: float | None
    opportunity_coverage_percent: float | None
    largest_attrition_stage: str | None
    human_readable_summary: str


@dataclass(frozen=True)
class OpportunityFunnel:
    stages: dict[str, int]
    terminal_reasons: dict[str, int]
    reconciles: bool
    human_readable_summary: str


@dataclass(frozen=True)
class OpportunityBySymbol:
    symbol: str
    asset_class: AssetClass
    markets_analyzed: int
    raw_setups: int
    qualified_setups: int
    candidates_created: int
    approved_candidates: int
    trades_opened: int
    opportunity_coverage_percent: float | None
    candidate_rate_percent: float | None
    trade_rate_percent: float | None
    top_terminal_stage: str | None


@dataclass(frozen=True)
class OpportunityByAssetClass:
    asset_class: AssetClass
    markets_analyzed: int
    setups: int
    candidates: int
    approvals: int
    trades: int
    candidate_rate: float | None
    trade_rate: float | None
    opportunity_coverage: float | None


@dataclass(frozen=True)
class SymbolPerformance:
    symbol: str
    trades: int
    wins: int
    losses: int
    breakeven: int
    win_rate: float | None
    total_r: float
    average_r: float | None
    realized_pl: float
    max_drawdown: float
    average_trade_duration: float | None


@dataclass(frozen=True)
class TradeFrequency:
    scope: str
    trades_per_day: float | None
    trades_per_active_market_day: float | None
    average_hours_between_trades: float | None


@dataclass(frozen=True)
class SelectivityAnalysis:
    selectivity_rate: float | None
    candidate_selectivity_rate: float | None
    approval_selectivity_rate: float | None
    human_readable_summary: str


@dataclass(frozen=True)
class PropEvaluationReadiness:
    benchmark_profile: str
    campaign_duration_days: float | None
    trades_opened: int
    trades_closed: int
    profit_percent: float | None
    max_daily_drawdown_percent: float | None
    max_total_drawdown_percent: float | None
    best_day_percent: float | None
    worst_day_percent: float | None
    average_daily_return_percent: float | None
    target_profit_percent: float
    max_daily_loss_percent: float
    max_total_loss_percent: float
    target_progress_percent: float | None
    daily_loss_compliant: bool | None
    total_loss_compliant: bool | None
    estimated_days_to_target: float | None
    human_readable_summary: str


@dataclass(frozen=True)
class OpportunityCoverageReport:
    summary: OpportunityCoverageSummary
    funnel: OpportunityFunnel
    by_symbol: tuple[OpportunityBySymbol, ...]
    by_asset_class: tuple[OpportunityByAssetClass, ...]
    terminal_reasons: dict[str, int]
    symbol_performance: tuple[SymbolPerformance, ...]
    trade_frequency: TradeFrequency
    selectivity: SelectivityAnalysis
    prop_evaluation_readiness: PropEvaluationReadiness
    observed_opportunity_definitions: dict[str, str]
    human_readable_summary: str


class OpportunityCoverageEngine:
    """Build reconciled opportunity analytics from existing diagnostics only."""

    def __init__(
        self,
        pipeline: Any | None = None,
        journal: PaperTradeJournal | None = None,
        *,
        campaigns_root: str | Path = "validation_campaigns",
        registry: SymbolRegistry | None = None,
    ) -> None:
        self.pipeline = pipeline or get_global_candidate_pipeline_diagnostics()
        self.journal = journal or current_paper_trade_journal()
        self.campaigns_root = Path(campaigns_root)
        self.registry = registry or get_symbol_registry()

    def report(
        self,
        *,
        campaign_id: str | None = None,
        symbol: str | None = None,
        asset_class: str | AssetClass | None = None,
    ) -> OpportunityCoverageReport:
        cycles = self._cycles(campaign_id=campaign_id)
        rows = _flatten(cycles)
        rows = [row for row in rows if not row.skipped]
        if symbol:
            rows = [row for row in rows if row.symbol == symbol.upper()]
        if asset_class:
            wanted = AssetClass(str(getattr(asset_class, "value", asset_class)).upper())
            rows = [row for row in rows if classify_symbol(row.symbol) is wanted]
        trades = self._trades(campaign_id=campaign_id, symbol=symbol, asset_class=asset_class)
        summary = _summary(rows, cycles, trades)
        funnel = _funnel(rows)
        by_symbol = _by_symbol(rows, trades, self.registry)
        by_asset = _by_asset_class(by_symbol)
        performance = _performance_by_symbol(trades, self.registry.default_symbols())
        frequency = _frequency(trades, campaign_id or "all")
        prop = _prop_readiness(trades)
        selectivity = _selectivity(summary)
        report = OpportunityCoverageReport(
            summary=summary,
            funnel=funnel,
            by_symbol=by_symbol,
            by_asset_class=by_asset,
            terminal_reasons=funnel.terminal_reasons,
            symbol_performance=performance,
            trade_frequency=frequency,
            selectivity=selectivity,
            prop_evaluation_readiness=prop,
            observed_opportunity_definitions=_definitions(),
            human_readable_summary=(
                f"Opportunity coverage analyzed {summary.markets_analyzed} markets, "
                f"{summary.qualified_setups} qualified setups, and {summary.trades_opened} opened paper trades."
            ),
        )
        if campaign_id:
            self.persist_campaign_report(campaign_id, report)
        return report

    def summary(self, **filters: Any) -> OpportunityCoverageSummary:
        return self.report(**filters).summary

    def funnel(self, **filters: Any) -> OpportunityFunnel:
        return self.report(**filters).funnel

    def by_symbol(self, **filters: Any) -> tuple[OpportunityBySymbol, ...]:
        return self.report(**filters).by_symbol

    def by_asset_class(self, **filters: Any) -> tuple[OpportunityByAssetClass, ...]:
        return self.report(**filters).by_asset_class

    def terminal_reasons(self, **filters: Any) -> dict[str, int]:
        return self.report(**filters).terminal_reasons

    def persist_campaign_report(self, campaign_id: str, report: OpportunityCoverageReport) -> None:
        if not campaign_id or campaign_id.startswith("recovery_test_"):
            return
        path = self.campaigns_root / campaign_id / "opportunity_coverage.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(jsonable_encoder(report), indent=2, sort_keys=True), encoding="utf-8")

    def safe_empty_state(self) -> bool:
        empty = OpportunityCoverageEngine(_EmptyPipeline(), None, campaigns_root=self.campaigns_root, registry=self.registry)
        return empty.summary().markets_analyzed == 0

    def _cycles(self, *, campaign_id: str | None) -> tuple[CandidatePipelineCycleDiagnostic, ...]:
        cycles = tuple(self.pipeline.recent(100_000, campaign_id=campaign_id))
        if cycles or not campaign_id:
            return cycles
        return _load_campaign_cycles(self.campaigns_root / campaign_id / "candidate_diagnostics.jsonl")

    def _trades(
        self,
        *,
        campaign_id: str | None,
        symbol: str | None,
        asset_class: str | AssetClass | None,
    ) -> tuple[PaperTradeJournalEntry, ...]:
        if self.journal is None:
            return ()
        records = [
            item for item in self.journal.entries()
            if not bool(getattr(item, "exclude_from_performance", False) or getattr(item, "synthetic_recovery_test", False) or getattr(item, "test_fixture", False))
        ]
        if campaign_id:
            records = [item for item in records if item.campaign_id == campaign_id]
        if symbol:
            records = [item for item in records if item.symbol == symbol.upper()]
        if asset_class:
            wanted = AssetClass(str(getattr(asset_class, "value", asset_class)).upper())
            records = [item for item in records if classify_symbol(item.symbol) is wanted]
        return tuple(records)


def get_global_opportunity_coverage() -> OpportunityCoverageEngine:
    return OpportunityCoverageEngine()


def _flatten(cycles: Iterable[CandidatePipelineCycleDiagnostic]) -> list[CandidateSymbolPipelineDiagnostic]:
    return [detail for cycle in cycles for detail in cycle.symbol_diagnostics]


def _summary(
    rows: list[CandidateSymbolPipelineDiagnostic],
    cycles: Iterable[CandidatePipelineCycleDiagnostic],
    trades: tuple[PaperTradeJournalEntry, ...],
) -> OpportunityCoverageSummary:
    analyzed = sum(row.analyzed and row.market_data_status != "error" for row in rows)
    raw = sum(_raw_setup(row) for row in rows)
    qualified = sum(_qualified(row) for row in rows)
    candidates = sum(row.candidate_status == "created" for row in rows)
    approved = sum(cycle.orders_created for cycle in cycles)
    orders = approved
    opened = sum(item.status in {"open", "closed"} for item in trades)
    closed = sum(item.status == "closed" for item in trades)
    terminals = Counter(_terminal(row) for row in rows if _terminal(row))
    largest = terminals.most_common(1)[0][0] if terminals else None
    return OpportunityCoverageSummary(
        markets_analyzed=int(analyzed),
        raw_setups=int(raw),
        qualified_setups=int(qualified),
        candidates_created=int(candidates),
        approved_candidates=int(approved),
        orders_created=int(orders),
        trades_opened=int(opened),
        trades_closed=int(closed),
        analysis_to_setup_rate=_rate(raw, analyzed),
        setup_to_qualified_rate=_rate(qualified, raw),
        qualified_to_candidate_rate=_rate(candidates, qualified),
        candidate_to_approval_rate=_rate(approved, candidates),
        approval_to_order_rate=_rate(orders, approved),
        order_to_trade_rate=_rate(opened, orders),
        analysis_to_trade_rate=_rate(opened, analyzed),
        opportunity_coverage_percent=_rate(opened, qualified),
        largest_attrition_stage=largest,
        human_readable_summary=f"{candidates} candidates were created from {analyzed} analyzed markets; largest attrition stage is {largest or 'unavailable'}.",
    )


def _funnel(rows: list[CandidateSymbolPipelineDiagnostic]) -> OpportunityFunnel:
    terminal = Counter(_terminal(row) for row in rows if _terminal(row))
    stages = {
        "MARKET_AVAILABLE": sum(row.analyzed and row.market_data_status != "error" for row in rows),
        "STRUCTURE_DETECTED": sum(row.structure_status == "completed" for row in rows),
        "DIRECTIONAL_BIAS": sum(row.bias_status not in {"unknown", "not_run", "unclear", ""} for row in rows),
        "TIMEFRAME_ALIGNMENT": sum(row.rejection_stage not in {"TIMEFRAME_ALIGNMENT"} and row.analyzed for row in rows),
        "SETUP_DETECTED": sum(_raw_setup(row) for row in rows),
        "CONFIDENCE_PASSED": sum((row.confidence_score or 0) >= 7.0 for row in rows),
        "SETUP_QUALITY_PASSED": sum(_quality_passed(row) for row in rows),
        "EXECUTION_PASSED": sum(row.rejection_stage not in {"AUTO_APPROVAL"} and row.analyzed for row in rows),
        "RISK_PASSED": sum(row.risk_status != "blocked" and row.analyzed for row in rows),
        "CANDIDATE_CREATED": sum(row.candidate_status == "created" for row in rows),
        "AUTO_APPROVAL_PASSED": 0,
        "ORDER_CREATED": 0,
        "TRADE_OPENED": 0,
        "TRADE_CLOSED": 0,
    }
    reconciles = sum(terminal.values()) + stages["CANDIDATE_CREATED"] == stages["MARKET_AVAILABLE"]
    return OpportunityFunnel(
        stages=stages,
        terminal_reasons=dict(sorted(terminal.items())),
        reconciles=reconciles,
        human_readable_summary=f"Primary terminal-stage funnel {'reconciles' if reconciles else 'does not reconcile'} across {stages['MARKET_AVAILABLE']} analyzed markets.",
    )


def _by_symbol(
    rows: list[CandidateSymbolPipelineDiagnostic],
    trades: tuple[PaperTradeJournalEntry, ...],
    registry: SymbolRegistry,
) -> tuple[OpportunityBySymbol, ...]:
    grouped: dict[str, list[CandidateSymbolPipelineDiagnostic]] = defaultdict(list)
    for row in rows:
        grouped[row.symbol].append(row)
    trade_counts = Counter(item.symbol for item in trades if item.status in {"open", "closed"})
    symbols = tuple(dict.fromkeys((*registry.default_symbols(), *sorted(grouped))))
    output = []
    for symbol in symbols:
        items = grouped.get(symbol, [])
        analyzed = sum(item.analyzed and item.market_data_status != "error" for item in items)
        raw = sum(_raw_setup(item) for item in items)
        qualified = sum(_qualified(item) for item in items)
        candidates = sum(item.candidate_status == "created" for item in items)
        terminals = Counter(_terminal(item) for item in items if _terminal(item))
        trades_opened = trade_counts[symbol]
        output.append(OpportunityBySymbol(
            symbol=symbol,
            asset_class=registry.classify(symbol) if registry.get(symbol) else classify_symbol(symbol),
            markets_analyzed=int(analyzed),
            raw_setups=int(raw),
            qualified_setups=int(qualified),
            candidates_created=int(candidates),
            approved_candidates=0,
            trades_opened=int(trades_opened),
            opportunity_coverage_percent=_rate(trades_opened, qualified),
            candidate_rate_percent=_rate(candidates, analyzed),
            trade_rate_percent=_rate(trades_opened, analyzed),
            top_terminal_stage=terminals.most_common(1)[0][0] if terminals else None,
        ))
    return tuple(output)


def _by_asset_class(rows: tuple[OpportunityBySymbol, ...]) -> tuple[OpportunityByAssetClass, ...]:
    grouped: dict[AssetClass, list[OpportunityBySymbol]] = defaultdict(list)
    for row in rows:
        grouped[row.asset_class].append(row)
    output = []
    for asset in (AssetClass.CRYPTO, AssetClass.FOREX):
        items = grouped.get(asset, [])
        analyzed = sum(item.markets_analyzed for item in items)
        setups = sum(item.raw_setups for item in items)
        candidates = sum(item.candidates_created for item in items)
        approvals = sum(item.approved_candidates for item in items)
        trades = sum(item.trades_opened for item in items)
        output.append(OpportunityByAssetClass(
            asset_class=asset,
            markets_analyzed=analyzed,
            setups=setups,
            candidates=candidates,
            approvals=approvals,
            trades=trades,
            candidate_rate=_rate(candidates, analyzed),
            trade_rate=_rate(trades, analyzed),
            opportunity_coverage=_rate(trades, setups),
        ))
    return tuple(output)


def _performance_by_symbol(trades: tuple[PaperTradeJournalEntry, ...], default_symbols: tuple[str, ...]) -> tuple[SymbolPerformance, ...]:
    grouped: dict[str, list[PaperTradeJournalEntry]] = defaultdict(list)
    for item in trades:
        grouped[item.symbol].append(item)
    output = []
    for symbol in tuple(dict.fromkeys((*default_symbols, *sorted(grouped)))):
        records = grouped.get(symbol, [])
        closed = [item for item in records if item.status == "closed" and item.realized_r is not None]
        returns = [float(item.realized_r or 0.0) for item in closed]
        wins = sum(value > 0 for value in returns)
        losses = sum(value < 0 for value in returns)
        breakeven = len(returns) - wins - losses
        output.append(SymbolPerformance(
            symbol=symbol,
            trades=len(records),
            wins=wins,
            losses=losses,
            breakeven=breakeven,
            win_rate=_rate(wins, len(closed)),
            total_r=round(sum(returns), 6),
            average_r=round(mean(returns), 6) if returns else None,
            realized_pl=round(sum(float(item.realized_pl or 0.0) for item in closed), 6),
            max_drawdown=_max_drawdown([float(item.realized_pl or 0.0) for item in closed]),
            average_trade_duration=_average_duration_hours(closed),
        ))
    return tuple(output)


def _frequency(trades: tuple[PaperTradeJournalEntry, ...], scope: str) -> TradeFrequency:
    opened = sorted(_parse_dt(item.opened_at) for item in trades if item.opened_at)
    opened = [item for item in opened if item is not None]
    if not opened:
        return TradeFrequency(scope=scope, trades_per_day=None, trades_per_active_market_day=None, average_hours_between_trades=None)
    days = max(1.0, (opened[-1] - opened[0]).total_seconds() / 86400)
    gaps = [(opened[index] - opened[index - 1]).total_seconds() / 3600 for index in range(1, len(opened))]
    return TradeFrequency(
        scope=scope,
        trades_per_day=round(len(opened) / days, 6),
        trades_per_active_market_day=round(len(opened) / days, 6),
        average_hours_between_trades=round(mean(gaps), 6) if gaps else None,
    )


def _prop_readiness(trades: tuple[PaperTradeJournalEntry, ...]) -> PropEvaluationReadiness:
    closed = [item for item in trades if item.status == "closed"]
    opened = [item for item in trades if item.status in {"open", "closed"}]
    pls = [float(item.realized_pl or 0.0) for item in closed]
    starting = next((float(item.account_balance_at_open or 0.0) for item in trades if item.account_balance_at_open), None)
    profit_percent = round(sum(pls) / starting * 100, 6) if starting else None
    target = 8.0
    daily = defaultdict(float)
    for item in closed:
        day = (item.closed_at or item.opened_at or "")[:10]
        if day:
            daily[day] += float(item.realized_pl or 0.0)
    daily_percents = [value / starting * 100 for value in daily.values()] if starting else []
    duration = _duration_days(opened)
    average_daily = round(mean(daily_percents), 6) if daily_percents else None
    return PropEvaluationReadiness(
        benchmark_profile="generic_prop_evaluation",
        campaign_duration_days=duration,
        trades_opened=len(opened),
        trades_closed=len(closed),
        profit_percent=profit_percent,
        max_daily_drawdown_percent=round(abs(min(daily_percents)), 6) if daily_percents else None,
        max_total_drawdown_percent=_drawdown_percent(pls, starting),
        best_day_percent=round(max(daily_percents), 6) if daily_percents else None,
        worst_day_percent=round(min(daily_percents), 6) if daily_percents else None,
        average_daily_return_percent=average_daily,
        target_profit_percent=target,
        max_daily_loss_percent=5.0,
        max_total_loss_percent=10.0,
        target_progress_percent=round((profit_percent or 0.0) / target * 100, 6) if profit_percent is not None else None,
        daily_loss_compliant=(min(daily_percents) >= -5.0) if daily_percents else None,
        total_loss_compliant=(_drawdown_percent(pls, starting) <= 10.0) if starting and pls else None,
        estimated_days_to_target=round((target - (profit_percent or 0)) / average_daily, 3) if average_daily and average_daily > 0 and profit_percent is not None else None,
        human_readable_summary="Prop evaluation analytics are read-only benchmark context and do not imply prop firm approval.",
    )


def _selectivity(summary: OpportunityCoverageSummary) -> SelectivityAnalysis:
    selectivity = None if summary.markets_analyzed == 0 else round(1 - summary.trades_opened / summary.markets_analyzed, 6)
    candidate = None if summary.markets_analyzed == 0 else round(1 - summary.candidates_created / summary.markets_analyzed, 6)
    approval = None if summary.candidates_created == 0 else round(1 - summary.approved_candidates / summary.candidates_created, 6)
    return SelectivityAnalysis(
        selectivity_rate=selectivity,
        candidate_selectivity_rate=candidate,
        approval_selectivity_rate=approval,
        human_readable_summary="Selectivity is factual pipeline attrition; high or low selectivity is not labeled good or bad.",
    )


def _terminal(row: CandidateSymbolPipelineDiagnostic) -> str | None:
    if row.candidate_status == "created":
        return None
    if row.market_data_status == "error":
        return "PROVIDER_FAILURE"
    if row.rejection_stage:
        return _PRIMARY_STAGE_MAP.get(row.rejection_stage, "UNKNOWN")
    if row.setup_status in {"unknown", "not_run", "no_valid_setup", ""}:
        return "NO_SETUP"
    return "UNKNOWN"


def _raw_setup(row: CandidateSymbolPipelineDiagnostic) -> bool:
    return bool(row.setup_status and row.setup_status not in {"unknown", "not_run", "no_valid_setup"})


def _qualified(row: CandidateSymbolPipelineDiagnostic) -> bool:
    return row.candidate_status == "created" or (
        _raw_setup(row)
        and not row.rejection_stage
        and row.market_data_status != "error"
        and bool(row.analyzed)
    )


def _quality_passed(row: CandidateSymbolPipelineDiagnostic) -> bool:
    value = row.setup_quality_score
    return value is not None and value >= 60


def _rate(numerator: int | float, denominator: int | float) -> float | None:
    return round(float(numerator) / float(denominator) * 100, 6) if denominator else None


def _definitions() -> dict[str, str]:
    return {
        "RAW_SETUP": "Existing diagnostics report a non-empty setup status other than unknown/not_run/no_valid_setup.",
        "QUALIFIED_SETUP": "Existing pipeline state indicates the setup was not stopped by confidence, setup quality, execution, risk, or duplicate gates, or it became a candidate.",
        "CANDIDATE": "Existing monitor emitted a candidate event.",
        "APPROVED_CANDIDATE": "Existing paper lifecycle created an order from an approved candidate.",
        "EXECUTED_TRADE": "Existing paper journal contains a real non-synthetic open or closed trade.",
    }


def _load_campaign_cycles(path: Path) -> tuple[CandidatePipelineCycleDiagnostic, ...]:
    if not path.exists():
        return ()
    cycles = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            raw = json.loads(line)
            raw["symbol_diagnostics"] = tuple(CandidateSymbolPipelineDiagnostic(**item) for item in raw.get("symbol_diagnostics", ()))
            raw["persistence_errors"] = tuple(raw.get("persistence_errors", ()))
            cycles.append(CandidatePipelineCycleDiagnostic(**raw))
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
    return tuple(cycles)


def _parse_dt(value: str | None):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _average_duration_hours(records: list[PaperTradeJournalEntry]) -> float | None:
    durations = []
    for item in records:
        opened = _parse_dt(item.opened_at)
        closed = _parse_dt(item.closed_at)
        if opened and closed:
            durations.append((closed - opened).total_seconds() / 3600)
    return round(mean(durations), 6) if durations else None


def _duration_days(records: list[PaperTradeJournalEntry]) -> float | None:
    dates = [_parse_dt(item.opened_at) for item in records if item.opened_at]
    dates = [item for item in dates if item is not None]
    if not dates:
        return None
    return round(max(1.0, (max(dates) - min(dates)).total_seconds() / 86400), 6)


def _max_drawdown(values: list[float]) -> float:
    peak = 0.0
    equity = 0.0
    drawdown = 0.0
    for value in values:
        equity += value
        peak = max(peak, equity)
        drawdown = max(drawdown, peak - equity)
    return round(drawdown, 6)


def _drawdown_percent(values: list[float], starting: float | None) -> float | None:
    if not starting:
        return None
    return round(_max_drawdown(values) / starting * 100, 6)


class _EmptyPipeline:
    def recent(self, limit: int = 100, *, campaign_id: str | None = None):
        del limit, campaign_id
        return ()
