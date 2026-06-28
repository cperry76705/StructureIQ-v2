"""Simplified deterministic historical evaluation for StructureIQ analyses."""

import re
from collections import Counter
from dataclasses import dataclass, field
from statistics import median
from typing import Callable, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.config import SUPPORTED_TIMEFRAMES
from core.analysis_engine import AnalysisEngine
from core.decision_engine import DecisionDiagnostics
from core.journal import TradeOutcome
from core.market_data import Candle, MarketDataProvider
from core.risk import RiskRewardDiagnostics, diagnose_risk_reward
from core.setup_engine import (
    MINIMUM_ACCEPTABLE_RISK_REWARD,
    SetupLevelDiagnostics,
)
from models.schemas import AnalysisRequest, AnalysisResponse


SkipReasonCode = Literal[
    "decision_not_actionable",
    "setup_not_confirmed",
    "setup_missing_levels",
    "trader_plan_not_actionable",
    "strategy_not_aligned",
    "risk_reward_missing",
    "risk_reward_too_low",
    "no_valid_setup",
    "no_strategy",
    "unknown",
]
BlockingEngine = Literal[
    "decision_engine",
    "setup_engine",
    "strategy_engine",
    "explanation_engine",
    "risk_engine",
    "backtesting_engine",
    "unknown",
]
ActionabilityStatus = Literal[
    "actionable",
    "waiting",
    "developing",
    "avoid",
    "no_trade",
    "skipped",
]


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
class ExecutionReadinessSnapshot:
    """Downstream state retained for threshold sensitivity analysis."""

    setup_status: str
    plan_status: str
    entry_zone: str | None
    stop_loss: str | None
    target: str | None
    estimated_risk_reward: float | None
    preferred_strategy: str
    strategy_alignment: str


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
    skip_reason_code: SkipReasonCode | None = None
    skip_reason_detail: str | None = None
    blocking_engine: BlockingEngine | None = None
    actionability_status: ActionabilityStatus = "actionable"
    decision_diagnostics: DecisionDiagnostics | None = None
    execution_readiness: ExecutionReadinessSnapshot | None = None
    risk_reward_diagnostics: RiskRewardDiagnostics | None = None
    setup_level_diagnostics: SetupLevelDiagnostics | None = None


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
class SkipDiagnostics:
    total_skipped: int
    by_reason_code: dict[str, int]
    by_blocking_engine: dict[str, int]
    most_common_reason: str | None
    human_readable_summary: str


@dataclass(frozen=True)
class DecisionDiagnosticsSummary:
    by_confidence_band: dict[str, int]
    by_blocked_gate: dict[str, int]
    average_confidence: float
    average_raw_score: float
    most_common_blocked_gate: str | None
    human_readable_summary: str


@dataclass(frozen=True)
class RiskRewardSummary:
    total_records: int
    complete_level_records: int
    missing_entry_count: int
    missing_stop_count: int
    missing_target_count: int
    invalid_geometry_count: int
    below_minimum_r_count: int
    average_estimated_r: float
    median_estimated_r: float
    records_near_threshold_1_2_to_1_5: int
    records_above_1_5: int
    by_failure_reason: dict[str, int]
    most_common_failure_reason: str | None
    human_readable_summary: str


@dataclass(frozen=True)
class SetupLevelSummary:
    total_records: int
    complete_level_records: int
    partial_level_records: int
    missing_level_records: int
    invalid_level_records: int
    missing_entry_count: int
    missing_stop_count: int
    missing_target_count: int
    by_level_quality: dict[str, int]
    most_common_level_quality: str | None
    human_readable_summary: str


@dataclass(frozen=True)
class BacktestResult:
    request: BacktestRequest
    trades: tuple[BacktestTrade, ...]
    metrics: BacktestMetrics
    human_readable_summary: str
    limitations: tuple[str, ...]
    skip_diagnostics: SkipDiagnostics = field(
        default_factory=lambda: _empty_skip_diagnostics()
    )
    decision_diagnostics_summary: DecisionDiagnosticsSummary = field(
        default_factory=lambda: _empty_decision_diagnostics_summary()
    )
    risk_reward_summary: RiskRewardSummary = field(
        default_factory=lambda: _empty_risk_reward_summary()
    )
    setup_level_summary: SetupLevelSummary = field(
        default_factory=lambda: _empty_setup_level_summary()
    )


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
        skip_diagnostics = calculate_skip_diagnostics(trades)
        decision_diagnostics_summary = calculate_decision_diagnostics_summary(
            trades
        )
        risk_reward_summary = calculate_risk_reward_summary(trades)
        setup_level_summary = calculate_setup_level_summary(trades)
        limitations = backtest_limitations()
        summary = (
            f"Backtest evaluated {len(trades)} analysis windows and produced "
            f"{metrics.total_trades} closed simulated trades with "
            f"{metrics.total_r:.2f}R total performance; "
            f"{skip_diagnostics.total_skipped} records were skipped."
        )
        return BacktestResult(
            request=request,
            trades=tuple(trades),
            metrics=metrics,
            human_readable_summary=summary,
            limitations=limitations,
            skip_diagnostics=skip_diagnostics,
            decision_diagnostics_summary=decision_diagnostics_summary,
            risk_reward_summary=risk_reward_summary,
            setup_level_summary=setup_level_summary,
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
    decision_diagnostics = getattr(
        analysis.decision, "decision_diagnostics", None
    )
    execution_readiness = _build_execution_readiness_snapshot(analysis)
    setup_level_diagnostics = getattr(
        analysis.setup_plan, "setup_level_diagnostics", None
    )
    risk_reward_diagnostics = diagnose_risk_reward(
        direction=_enum_value(getattr(analysis.setup_plan, "direction", None))
        or action,
        entry_zone=getattr(plan, "entry_zone", None),
        stop_loss=getattr(plan, "stop_loss", None),
        target=getattr(plan, "target", None),
        minimum_required_r=MINIMUM_ACCEPTABLE_RISK_REWARD,
    )
    if plan.status != "actionable" or action not in {"buy", "sell"}:
        code, engine, detail = diagnose_non_actionable_analysis(analysis)
        return _skipped_trade(
            timestamp=timestamp,
            symbol=symbol,
            action=action,
            setup_type=setup_type,
            strategy_type=strategy_type,
            estimated_risk_reward=plan.estimated_risk_reward,
            reason="Trade skipped because the trader-facing plan was not actionable.",
            skip_reason_code=code,
            skip_reason_detail=detail,
            blocking_engine=engine,
            actionability_status=_actionability_status(plan.status),
            decision_diagnostics=decision_diagnostics,
            execution_readiness=execution_readiness,
            risk_reward_diagnostics=risk_reward_diagnostics,
            setup_level_diagnostics=setup_level_diagnostics,
        )

    entry = parse_price_level(plan.entry_zone, midpoint=True)
    stop = parse_price_level(plan.stop_loss)
    target = parse_price_level(plan.target)
    if entry is None or stop is None or target is None:
        detail = "Entry, stop loss, or target could not be parsed from the setup plan."
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
            skip_reason_code="setup_missing_levels",
            skip_reason_detail=detail,
            blocking_engine="setup_engine",
            actionability_status=_actionability_status(plan.status),
            decision_diagnostics=decision_diagnostics,
            execution_readiness=execution_readiness,
            risk_reward_diagnostics=risk_reward_diagnostics,
            setup_level_diagnostics=setup_level_diagnostics,
        )

    if plan.estimated_risk_reward is None:
        return BacktestTrade(
            timestamp=timestamp,
            symbol=symbol,
            action=action,
            setup_type=setup_type,
            strategy_type=strategy_type,
            entry=entry,
            stop_loss=stop,
            target=target,
            estimated_risk_reward=None,
            outcome=TradeOutcome.SKIPPED,
            realized_r=None,
            reason="Trade skipped because risk/reward was unavailable.",
            skip_reason_code="risk_reward_missing",
            skip_reason_detail=(
                "Entry, stop, and target were parseable, but the actionable plan "
                "did not provide estimated risk/reward."
            ),
            blocking_engine="risk_engine",
            actionability_status=_actionability_status(plan.status),
            decision_diagnostics=decision_diagnostics,
            execution_readiness=execution_readiness,
            risk_reward_diagnostics=risk_reward_diagnostics,
            setup_level_diagnostics=setup_level_diagnostics,
        )
    if plan.estimated_risk_reward < MINIMUM_ACCEPTABLE_RISK_REWARD:
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
            reason="Trade skipped because risk/reward was below the execution minimum.",
            skip_reason_code="risk_reward_too_low",
            skip_reason_detail=(
                f"Estimated risk/reward {plan.estimated_risk_reward:.2f}R is below "
                f"the {MINIMUM_ACCEPTABLE_RISK_REWARD:.2f}R execution gate."
            ),
            blocking_engine="risk_engine",
            actionability_status=_actionability_status(plan.status),
            decision_diagnostics=decision_diagnostics,
            execution_readiness=execution_readiness,
            risk_reward_diagnostics=risk_reward_diagnostics,
            setup_level_diagnostics=setup_level_diagnostics,
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
        actionability_status="actionable",
        decision_diagnostics=decision_diagnostics,
        execution_readiness=execution_readiness,
        risk_reward_diagnostics=risk_reward_diagnostics,
        setup_level_diagnostics=setup_level_diagnostics,
    )


def diagnose_non_actionable_analysis(
    analysis: AnalysisResponse,
) -> tuple[SkipReasonCode, BlockingEngine, str]:
    """Identify the first explanatory gate without changing execution behavior."""

    decision_action = _enum_value(analysis.decision.action)
    setup = analysis.setup_plan
    setup_status = _enum_value(getattr(setup, "setup_status", None))
    plan = analysis.trader_analysis.trade_plan
    strategy = analysis.strategy

    if decision_action not in {"buy", "sell"}:
        return (
            "decision_not_actionable",
            "decision_engine",
            f"Decision Engine returned {decision_action or 'an unknown action'}.",
        )
    if setup_status in {"invalid", "no_setup"}:
        return (
            "no_valid_setup",
            "setup_engine",
            f"Setup Engine returned {setup_status.replace('_', ' ')}.",
        )
    setup_levels = (
        getattr(setup, "entry_zone", getattr(plan, "entry_zone", None)),
        getattr(setup, "stop_loss", getattr(plan, "stop_loss", None)),
        getattr(setup, "target", getattr(plan, "target", None)),
    )
    if any(level is None for level in setup_levels):
        return (
            "setup_missing_levels",
            "setup_engine",
            "Setup entry, stop loss, or target is missing.",
        )

    risk_reward = getattr(setup, "estimated_risk_reward", None)
    if risk_reward is None:
        risk_reward = getattr(plan, "estimated_risk_reward", None)
    if risk_reward is None:
        return (
            "risk_reward_missing",
            "risk_engine",
            "Estimated risk/reward is unavailable.",
        )
    if risk_reward < MINIMUM_ACCEPTABLE_RISK_REWARD:
        return (
            "risk_reward_too_low",
            "risk_engine",
            f"Estimated risk/reward {risk_reward:.2f}R is below the "
            f"{MINIMUM_ACCEPTABLE_RISK_REWARD:.2f}R setup gate.",
        )
    if setup_status in {"developing", "waiting_for_confirmation"}:
        return (
            "setup_not_confirmed",
            "setup_engine",
            f"Setup status is {setup_status.replace('_', ' ')}.",
        )

    preferred_strategy = _enum_value(getattr(strategy, "preferred_strategy", None))
    strategy_alignment = _enum_value(getattr(strategy, "strategy_alignment", None))
    if preferred_strategy == "no_strategy":
        return (
            "no_strategy",
            "strategy_engine",
            "Strategy Engine did not identify a preferred playbook.",
        )
    if strategy_alignment in {"conflicts_with_decision", "no_clear_strategy"}:
        return (
            "strategy_not_aligned",
            "strategy_engine",
            f"Strategy alignment is {strategy_alignment.replace('_', ' ')}.",
        )
    if _actionability_status(plan.status) != "actionable":
        return (
            "trader_plan_not_actionable",
            "explanation_engine",
            f"Trader-facing plan status is {_actionability_status(plan.status)}.",
        )
    return (
        "unknown",
        "backtesting_engine",
        "The analysis was non-actionable but no known blocking gate was identified.",
    )


def _build_execution_readiness_snapshot(
    analysis: AnalysisResponse,
) -> ExecutionReadinessSnapshot:
    plan = analysis.trader_analysis.trade_plan
    setup = analysis.setup_plan
    strategy = analysis.strategy
    return ExecutionReadinessSnapshot(
        setup_status=_enum_value(getattr(setup, "setup_status", None)) or "unknown",
        plan_status=_enum_value(getattr(plan, "status", None)) or "unknown",
        entry_zone=getattr(plan, "entry_zone", None),
        stop_loss=getattr(plan, "stop_loss", None),
        target=getattr(plan, "target", None),
        estimated_risk_reward=getattr(plan, "estimated_risk_reward", None),
        preferred_strategy=(
            _enum_value(getattr(strategy, "preferred_strategy", None)) or "unknown"
        ),
        strategy_alignment=(
            _enum_value(getattr(strategy, "strategy_alignment", None)) or "unknown"
        ),
    )


def calculate_skip_diagnostics(trades: list[BacktestTrade]) -> SkipDiagnostics:
    """Aggregate primary skip reasons and their owning engines."""

    skipped = [trade for trade in trades if trade.outcome is TradeOutcome.SKIPPED]
    reasons = Counter(trade.skip_reason_code or "unknown" for trade in skipped)
    engines = Counter(trade.blocking_engine or "unknown" for trade in skipped)
    most_common = (
        sorted(reasons, key=lambda key: (-reasons[key], key))[0] if reasons else None
    )
    if not skipped:
        summary = "No analysis records were skipped."
    else:
        dominant_engine = sorted(
            engines, key=lambda key: (-engines[key], key)
        )[0]
        summary = (
            f"{len(skipped)} records were skipped; the most common reason was "
            f"{most_common.replace('_', ' ')}, primarily blocked by "
            f"{dominant_engine.replace('_', ' ')}."
        )
    return SkipDiagnostics(
        total_skipped=len(skipped),
        by_reason_code=dict(sorted(reasons.items())),
        by_blocking_engine=dict(sorted(engines.items())),
        most_common_reason=most_common,
        human_readable_summary=summary,
    )


def calculate_decision_diagnostics_summary(
    trades: list[BacktestTrade],
) -> DecisionDiagnosticsSummary:
    """Aggregate available Decision Engine snapshots across analysis windows."""

    diagnostics = [
        trade.decision_diagnostics
        for trade in trades
        if trade.decision_diagnostics is not None
        and trade.decision_diagnostics.gate_results
    ]
    bands = Counter(item.confidence_band for item in diagnostics)
    blocked_gates = Counter(
        gate for item in diagnostics for gate in item.blocked_by
    )
    most_common = (
        sorted(
            blocked_gates,
            key=lambda key: (-blocked_gates[key], key),
        )[0]
        if blocked_gates
        else None
    )
    average_confidence = (
        round(sum(item.final_confidence for item in diagnostics) / len(diagnostics), 2)
        if diagnostics
        else 0.0
    )
    average_raw_score = (
        round(sum(item.raw_score for item in diagnostics) / len(diagnostics), 2)
        if diagnostics
        else 0.0
    )
    if not diagnostics:
        summary = "No Decision Engine diagnostic snapshots were available."
    elif most_common is None:
        summary = (
            f"{len(diagnostics)} decision snapshots averaged "
            f"{average_confidence:.1f}/100 and no required gate was blocked."
        )
    else:
        summary = (
            f"{len(diagnostics)} decision snapshots averaged "
            f"{average_confidence:.1f}/100; the most common blocked gate was "
            f"{most_common.replace('_', ' ')} ({blocked_gates[most_common]} records)."
        )
    return DecisionDiagnosticsSummary(
        by_confidence_band=dict(sorted(bands.items())),
        by_blocked_gate=dict(sorted(blocked_gates.items())),
        average_confidence=average_confidence,
        average_raw_score=average_raw_score,
        most_common_blocked_gate=most_common,
        human_readable_summary=summary,
    )


def calculate_risk_reward_summary(trades: list[BacktestTrade]) -> RiskRewardSummary:
    diagnostics = [
        trade.risk_reward_diagnostics
        for trade in trades
        if trade.risk_reward_diagnostics is not None
    ]
    complete = [item for item in diagnostics if item.has_entry and item.has_stop and item.has_target]
    estimates = [item.estimated_r for item in diagnostics if item.estimated_r is not None]
    failures = Counter(
        item.failure_reason.value
        for item in diagnostics
        if item.failure_reason is not None
    )
    common = (
        sorted(failures, key=lambda key: (-failures[key], key))[0]
        if failures
        else None
    )
    below = sum(
        value < MINIMUM_ACCEPTABLE_RISK_REWARD for value in estimates
    )
    near = sum(1.2 <= value < 1.5 for value in estimates)
    above = sum(value >= 1.5 for value in estimates)
    average = round(sum(estimates) / len(estimates), 3) if estimates else 0.0
    median_value = round(float(median(estimates)), 3) if estimates else 0.0
    summary = (
        f"{len(diagnostics)} records produced {len(complete)} complete level sets; "
        f"{above} met 1.5R and {below} were below the minimum."
    )
    return RiskRewardSummary(
        total_records=len(diagnostics),
        complete_level_records=len(complete),
        missing_entry_count=sum(not item.has_entry for item in diagnostics),
        missing_stop_count=sum(not item.has_stop for item in diagnostics),
        missing_target_count=sum(not item.has_target for item in diagnostics),
        invalid_geometry_count=sum(
            item.failure_reason is not None
            and item.failure_reason.value == "invalid_price_geometry"
            for item in diagnostics
        ),
        below_minimum_r_count=below,
        average_estimated_r=average,
        median_estimated_r=median_value,
        records_near_threshold_1_2_to_1_5=near,
        records_above_1_5=above,
        by_failure_reason=dict(sorted(failures.items())),
        most_common_failure_reason=common,
        human_readable_summary=summary,
    )


def calculate_setup_level_summary(trades: list[BacktestTrade]) -> SetupLevelSummary:
    diagnostics = [
        trade.setup_level_diagnostics
        for trade in trades
        if trade.setup_level_diagnostics is not None
    ]
    qualities = Counter(item.level_quality for item in diagnostics)
    common = (
        sorted(qualities, key=lambda key: (-qualities[key], key))[0]
        if qualities
        else None
    )
    risk = [
        trade.risk_reward_diagnostics
        for trade in trades
        if trade.setup_level_diagnostics is not None
        and trade.risk_reward_diagnostics is not None
    ]
    return SetupLevelSummary(
        total_records=len(diagnostics),
        complete_level_records=qualities["complete"],
        partial_level_records=qualities["partial"],
        missing_level_records=qualities["missing"],
        invalid_level_records=qualities["invalid"],
        missing_entry_count=sum(not item.has_entry for item in risk),
        missing_stop_count=sum(not item.has_stop for item in risk),
        missing_target_count=sum(not item.has_target for item in risk),
        by_level_quality=dict(sorted(qualities.items())),
        most_common_level_quality=common,
        human_readable_summary=(
            f"{len(diagnostics)} setup snapshots include {qualities['complete']} complete, "
            f"{qualities['partial']} partial, {qualities['missing']} missing, and "
            f"{qualities['invalid']} invalid level sets."
        ),
    )


def _empty_skip_diagnostics() -> SkipDiagnostics:
    return SkipDiagnostics(0, {}, {}, None, "No analysis records were skipped.")


def _empty_decision_diagnostics_summary() -> DecisionDiagnosticsSummary:
    return DecisionDiagnosticsSummary(
        {},
        {},
        0.0,
        0.0,
        None,
        "No Decision Engine diagnostic snapshots were available.",
    )


def _empty_risk_reward_summary() -> RiskRewardSummary:
    return RiskRewardSummary(0, 0, 0, 0, 0, 0, 0, 0.0, 0.0, 0, 0, {}, None, "No risk/reward diagnostics were available.")


def _empty_setup_level_summary() -> SetupLevelSummary:
    return SetupLevelSummary(0, 0, 0, 0, 0, 0, 0, 0, {}, None, "No setup-level diagnostics were available.")


def _skipped_trade(
    *,
    timestamp: int,
    symbol: str,
    action: str,
    setup_type: str,
    strategy_type: str,
    estimated_risk_reward: float | None,
    reason: str,
    skip_reason_code: SkipReasonCode,
    skip_reason_detail: str,
    blocking_engine: BlockingEngine,
    actionability_status: ActionabilityStatus,
    decision_diagnostics: DecisionDiagnostics | None,
    execution_readiness: ExecutionReadinessSnapshot | None,
    risk_reward_diagnostics: RiskRewardDiagnostics | None,
    setup_level_diagnostics: SetupLevelDiagnostics | None,
) -> BacktestTrade:
    return BacktestTrade(
        timestamp=timestamp,
        symbol=symbol,
        action=action,
        setup_type=setup_type,
        strategy_type=strategy_type,
        entry=None,
        stop_loss=None,
        target=None,
        estimated_risk_reward=estimated_risk_reward,
        outcome=TradeOutcome.SKIPPED,
        realized_r=None,
        reason=reason,
        skip_reason_code=skip_reason_code,
        skip_reason_detail=skip_reason_detail,
        blocking_engine=blocking_engine,
        actionability_status=actionability_status,
        decision_diagnostics=decision_diagnostics,
        execution_readiness=execution_readiness,
        risk_reward_diagnostics=risk_reward_diagnostics,
        setup_level_diagnostics=setup_level_diagnostics,
    )


def _enum_value(value: object) -> str:
    raw = getattr(value, "value", value)
    return raw if isinstance(raw, str) else ""


def _actionability_status(value: object) -> ActionabilityStatus:
    raw = _enum_value(value)
    if raw in {"actionable", "waiting", "developing", "avoid", "no_trade"}:
        return raw  # type: ignore[return-value]
    return "skipped"


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
