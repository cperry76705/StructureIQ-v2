"""Deterministic execution-cost and fill modeling for historical research only."""

import random
from dataclasses import dataclass
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from core.market_data import Candle


class CommissionType(str, Enum):
    FIXED = "fixed"
    PERCENT = "percent"


class FillModel(str, Enum):
    IMMEDIATE = "immediate"
    NEXT_BAR = "next_bar"
    TOUCH = "touch"


class SlippageType(str, Enum):
    NONE = "none"
    FIXED = "fixed"
    RANDOM = "random"


ExecutionQuality = Literal["perfect", "good", "degraded", "partial", "unfilled"]


class ExecutionProfile(BaseModel):
    """Explicit execution assumptions; omitted profiles retain perfect execution."""

    model_config = ConfigDict(extra="forbid")

    spread: float = Field(default=0.0, ge=0.0)
    slippage: float = Field(default=0.0, ge=0.0)
    slippage_type: SlippageType = SlippageType.FIXED
    commission_per_trade: float = Field(default=0.0, ge=0.0)
    commission_type: CommissionType = CommissionType.FIXED
    allow_partial_fill: bool = False
    partial_fill_probability: float = Field(default=0.0, ge=0.0, le=1.0)
    fill_model: FillModel = FillModel.IMMEDIATE
    random_seed: int = 0

    @model_validator(mode="after")
    def validate_partial_fill(self) -> "ExecutionProfile":
        if not self.allow_partial_fill and self.partial_fill_probability:
            raise ValueError(
                "partial_fill_probability requires allow_partial_fill=true"
            )
        return self


@dataclass(frozen=True)
class ExecutionDiagnostics:
    requested_entry: float
    actual_entry: float | None
    spread_cost: float
    slippage_cost: float
    commission_cost: float
    execution_quality: ExecutionQuality
    fill_model_used: str
    human_readable_summary: str
    baseline_realized_r: float | None = None
    realistic_realized_r: float | None = None
    execution_degradation_r: float | None = None


@dataclass(frozen=True)
class ExecutionSummary:
    modeled_trades: int
    average_spread_cost: float
    average_slippage_cost: float
    average_commission: float
    average_execution_degradation: float
    baseline_expectancy: float
    realistic_expectancy: float
    expectancy_reduction: float
    human_readable_summary: str


@dataclass(frozen=True)
class PreparedExecution:
    actual_entry: float | None
    evaluation_candles: tuple[Candle, ...]
    spread_cost: float
    slippage_cost: float
    commission_cost_r: float
    fill_fraction: float
    execution_quality: ExecutionQuality
    fill_model_used: str


class ExecutionEngine:
    """Apply deterministic adverse execution assumptions to an eligible trade."""

    def __init__(self, profile: ExecutionProfile) -> None:
        self.profile = profile

    def prepare(
        self,
        *,
        action: str,
        requested_entry: float,
        stop_loss: float,
        future_candles: list[Candle],
        symbol: str,
        timestamp: int,
        starting_balance: float,
        risk_per_trade_percent: float,
    ) -> PreparedExecution:
        base_entry, evaluation = self._fill_base(requested_entry, future_candles)
        if base_entry is None:
            return PreparedExecution(
                None, (), 0.0, 0.0, 0.0, 0.0, "unfilled", self.profile.fill_model.value
            )

        direction = 1.0 if action == "buy" else -1.0
        slippage = self._slippage(symbol, timestamp)
        actual_entry = base_entry + direction * (self.profile.spread + slippage)
        partial = self._partial_fill(symbol, timestamp)
        fill_fraction = 0.5 if partial else 1.0
        risk_capital = starting_balance * risk_per_trade_percent / 100.0
        price_risk = abs(actual_entry - stop_loss)
        commission_r = self._commission_r(
            actual_entry=actual_entry,
            price_risk=price_risk,
            risk_capital=risk_capital,
            fill_fraction=fill_fraction,
        )
        degraded = (
            self.profile.spread > 0
            or slippage > 0
            or commission_r > 0
            or self.profile.fill_model is not FillModel.IMMEDIATE
        )
        quality: ExecutionQuality = (
            "partial" if partial else "degraded" if degraded else "perfect"
        )
        return PreparedExecution(
            actual_entry=actual_entry,
            evaluation_candles=tuple(evaluation),
            spread_cost=self.profile.spread,
            slippage_cost=slippage,
            commission_cost_r=commission_r,
            fill_fraction=fill_fraction,
            execution_quality=quality,
            fill_model_used=self.profile.fill_model.value,
        )

    def _fill_base(
        self, requested_entry: float, future_candles: list[Candle]
    ) -> tuple[float | None, list[Candle]]:
        if self.profile.fill_model is FillModel.IMMEDIATE:
            return requested_entry, future_candles
        if not future_candles:
            return None, []
        if self.profile.fill_model is FillModel.NEXT_BAR:
            return future_candles[0].open, future_candles
        for index, candle in enumerate(future_candles):
            if candle.low <= requested_entry <= candle.high:
                return requested_entry, future_candles[index:]
        return None, []

    def _slippage(self, symbol: str, timestamp: int) -> float:
        if self.profile.slippage_type is SlippageType.NONE:
            return 0.0
        if self.profile.slippage_type is SlippageType.FIXED:
            return self.profile.slippage
        rng = random.Random(
            f"{self.profile.random_seed}:{symbol}:{timestamp}:slippage"
        )
        return round(rng.uniform(0.0, self.profile.slippage), 10)

    def _partial_fill(self, symbol: str, timestamp: int) -> bool:
        if not self.profile.allow_partial_fill:
            return False
        rng = random.Random(
            f"{self.profile.random_seed}:{symbol}:{timestamp}:partial"
        )
        return rng.random() < self.profile.partial_fill_probability

    def _commission_r(
        self,
        *,
        actual_entry: float,
        price_risk: float,
        risk_capital: float,
        fill_fraction: float,
    ) -> float:
        if self.profile.commission_per_trade <= 0 or risk_capital <= 0:
            return 0.0
        if self.profile.commission_type is CommissionType.FIXED:
            commission_cash = self.profile.commission_per_trade
        elif price_risk > 0:
            units = risk_capital / price_risk
            notional = abs(actual_entry) * units * fill_fraction
            commission_cash = notional * self.profile.commission_per_trade / 100.0
        else:
            commission_cash = 0.0
        return round(commission_cash / risk_capital, 6)


def build_execution_diagnostics(
    *,
    prepared: PreparedExecution,
    requested_entry: float,
    baseline_realized_r: float | None,
    realistic_realized_r: float | None,
) -> ExecutionDiagnostics:
    degradation = (
        round(baseline_realized_r - realistic_realized_r, 6)
        if baseline_realized_r is not None and realistic_realized_r is not None
        else None
    )
    if prepared.actual_entry is None:
        summary = (
            f"The {prepared.fill_model_used.replace('_', ' ')} model did not fill "
            "the requested entry in available candles."
        )
    else:
        summary = (
            f"{prepared.fill_model_used.replace('_', ' ').title()} execution filled "
            f"at {prepared.actual_entry:.6f}; spread was {prepared.spread_cost:.6f}, "
            f"slippage was {prepared.slippage_cost:.6f}, and commission reduced "
            f"the result by {prepared.commission_cost_r:.3f}R."
        )
    return ExecutionDiagnostics(
        requested_entry=requested_entry,
        actual_entry=prepared.actual_entry,
        spread_cost=prepared.spread_cost,
        slippage_cost=prepared.slippage_cost,
        commission_cost=prepared.commission_cost_r,
        execution_quality=prepared.execution_quality,
        fill_model_used=prepared.fill_model_used,
        human_readable_summary=summary,
        baseline_realized_r=baseline_realized_r,
        realistic_realized_r=realistic_realized_r,
        execution_degradation_r=degradation,
    )


def calculate_execution_summary(
    diagnostics: list[ExecutionDiagnostics],
) -> ExecutionSummary:
    if not diagnostics:
        return ExecutionSummary(
            0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
            "No execution profiles were modeled; perfect execution remains in effect.",
        )
    paired = [
        item for item in diagnostics
        if item.baseline_realized_r is not None and item.realistic_realized_r is not None
    ]
    baseline = [item.baseline_realized_r for item in paired]
    realistic = [item.realistic_realized_r for item in paired]
    degradations = [item.execution_degradation_r for item in diagnostics if item.execution_degradation_r is not None]
    baseline_expectancy = round(sum(baseline) / len(baseline), 6) if baseline else 0.0
    realistic_expectancy = round(sum(realistic) / len(realistic), 6) if realistic else 0.0
    reduction = round(baseline_expectancy - realistic_expectancy, 6)
    count = len(diagnostics)
    return ExecutionSummary(
        modeled_trades=count,
        average_spread_cost=round(sum(item.spread_cost for item in diagnostics) / count, 6),
        average_slippage_cost=round(sum(item.slippage_cost for item in diagnostics) / count, 6),
        average_commission=round(sum(item.commission_cost for item in diagnostics) / count, 6),
        average_execution_degradation=(
            round(sum(degradations) / len(degradations), 6) if degradations else 0.0
        ),
        baseline_expectancy=baseline_expectancy,
        realistic_expectancy=realistic_expectancy,
        expectancy_reduction=reduction,
        human_readable_summary=(
            f"Execution modeling covered {count} fills; expectancy changed from "
            f"{baseline_expectancy:.3f}R to {realistic_expectancy:.3f}R "
            f"({reduction:.3f}R reduction)."
        ),
    )
