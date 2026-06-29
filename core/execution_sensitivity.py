"""Side-by-side execution-profile experiments over immutable backtest inputs."""

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from core.backtesting import BacktestTrade, calculate_backtest_metrics
from core.execution import (
    CommissionType,
    ExecutionProfile,
    FillModel,
    SlippageType,
    calculate_execution_summary,
)


class ExecutionSensitivityProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=500)
    execution_profile: ExecutionProfile


@dataclass(frozen=True)
class ExecutionSensitivityResult:
    profile_name: str
    description: str
    total_trades: int
    wins: int
    losses: int
    breakeven: int
    win_rate: float
    average_r: float
    total_r: float
    profit_factor: float | None
    max_drawdown_r: float
    baseline_expectancy: float
    realistic_expectancy: float
    expectancy_reduction: float
    average_spread_cost: float
    average_slippage_cost: float
    average_commission: float
    average_execution_degradation: float
    human_readable_summary: str


@dataclass(frozen=True)
class ExecutionSensitivitySummary:
    profiles: tuple[ExecutionSensitivityResult, ...]
    best_profile: str
    worst_profile: str
    largest_expectancy_drop_profile: str
    most_sensitive_cost_component: str
    human_readable_summary: str
    recommendations: tuple[str, ...]


def perfect_sensitivity_profile() -> ExecutionSensitivityProfile:
    return ExecutionSensitivityProfile(
        name="perfect",
        description="Perfect execution baseline with no modeled costs or fill delay.",
        execution_profile=ExecutionProfile(),
    )


def ensure_perfect_baseline(
    profiles: list[ExecutionSensitivityProfile],
) -> tuple[ExecutionSensitivityProfile, ...]:
    """Prepend one canonical perfect baseline and deterministically de-duplicate names."""

    unique: dict[str, ExecutionSensitivityProfile] = {
        "perfect": perfect_sensitivity_profile()
    }
    for profile in profiles:
        if profile.name != "perfect":
            unique.setdefault(profile.name, profile)
    return tuple(unique.values())


def build_execution_sensitivity_summary(
    profile_runs: list[tuple[ExecutionSensitivityProfile, list[BacktestTrade]]],
) -> ExecutionSensitivitySummary:
    if not profile_runs:
        raise ValueError("execution sensitivity requires at least one profile run")
    perfect_trades = next(
        trades for profile, trades in profile_runs if profile.name == "perfect"
    )
    baseline_expectancy = calculate_backtest_metrics(perfect_trades).average_r
    results: list[ExecutionSensitivityResult] = []
    component_drops: dict[str, float] = {}
    for profile, trades in profile_runs:
        metrics = calculate_backtest_metrics(trades)
        execution = calculate_execution_summary(
            [trade.execution_diagnostics for trade in trades if trade.execution_diagnostics]
        )
        reduction = round(baseline_expectancy - metrics.average_r, 6)
        result = ExecutionSensitivityResult(
            profile_name=profile.name,
            description=profile.description,
            total_trades=metrics.total_trades,
            wins=metrics.wins,
            losses=metrics.losses,
            breakeven=metrics.breakeven,
            win_rate=metrics.win_rate,
            average_r=metrics.average_r,
            total_r=metrics.total_r,
            profit_factor=metrics.profit_factor,
            max_drawdown_r=metrics.max_drawdown_r,
            baseline_expectancy=baseline_expectancy,
            realistic_expectancy=metrics.average_r,
            expectancy_reduction=reduction,
            average_spread_cost=execution.average_spread_cost,
            average_slippage_cost=execution.average_slippage_cost,
            average_commission=execution.average_commission,
            average_execution_degradation=execution.average_execution_degradation,
            human_readable_summary=(
                f"{profile.name} produced {metrics.total_trades} closed trades at "
                f"{metrics.average_r:.3f}R expectancy versus {baseline_expectancy:.3f}R "
                f"perfect execution ({reduction:.3f}R reduction)."
            ),
        )
        results.append(result)
        if profile.name != "perfect":
            component = _profile_component(profile.execution_profile)
            component_drops[component] = max(
                component_drops.get(component, float("-inf")), reduction
            )

    ranked = sorted(results, key=lambda item: (item.average_r, item.profile_name))
    worst = ranked[0]
    best = ranked[-1]
    largest = sorted(
        results,
        key=lambda item: (item.expectancy_reduction, item.profile_name),
    )[-1]
    sensitive_component = (
        sorted(component_drops, key=lambda key: (component_drops[key], key))[-1]
        if component_drops
        else "none"
    )
    recommendations = _recommendations(
        largest=largest,
        component=sensitive_component,
        component_drop=component_drops.get(sensitive_component, 0.0),
    )
    return ExecutionSensitivitySummary(
        profiles=tuple(results),
        best_profile=best.profile_name,
        worst_profile=worst.profile_name,
        largest_expectancy_drop_profile=largest.profile_name,
        most_sensitive_cost_component=sensitive_component,
        human_readable_summary=(
            f"Compared {len(results)} execution profiles. {best.profile_name} had the "
            f"highest expectancy, {worst.profile_name} had the lowest, and "
            f"{sensitive_component.replace('_', ' ')} was the most sensitive component."
        ),
        recommendations=recommendations,
    )


def _profile_component(profile: ExecutionProfile) -> str:
    components: list[str] = []
    if profile.spread > 0:
        components.append("spread")
    if profile.slippage > 0 and profile.slippage_type is not SlippageType.NONE:
        components.append("slippage")
    if profile.commission_per_trade > 0:
        components.append("commission")
    if profile.fill_model is not FillModel.IMMEDIATE or profile.allow_partial_fill:
        components.append("fill_model")
    if not components:
        return "none"
    return components[0] if len(components) == 1 else "combined_costs"


def _recommendations(
    *, largest: ExecutionSensitivityResult, component: str, component_drop: float
) -> tuple[str, ...]:
    messages = [
        f"Inspect {largest.profile_name} first; it reduced expectancy by "
        f"{largest.expectancy_reduction:.3f}R versus perfect execution."
    ]
    if component == "combined_costs":
        messages.append(
            "Combined costs dominate the tested profiles; compare the isolated spread, "
            "slippage, commission, and fill-model rows before changing assumptions."
        )
    elif component != "none":
        messages.append(
            f"{component.replace('_', ' ').title()} produced the largest isolated "
            f"expectancy reduction ({component_drop:.3f}R). Validate its input range "
            "against venue-specific observations."
        )
    messages.append(
        "Treat every supplied profile as a scenario, not a broker-cost estimate or a "
        "reason to change production trading logic."
    )
    return tuple(messages)


def forex_execution_sensitivity_profiles() -> tuple[ExecutionSensitivityProfile, ...]:
    """Illustrative five-decimal FX scenarios, not broker guarantees."""

    return (
        perfect_sensitivity_profile(),
        _profile("forex_spread_only_mild", "Mild one-pip spread only.", spread=0.0001),
        _profile("forex_slippage_only_mild", "Mild seeded random slippage only.", slippage=0.00005, slippage_type=SlippageType.RANDOM),
        _profile("forex_commission_only_mild", "Mild fixed round-trip commission only.", commission_per_trade=2.0),
        _profile("forex_next_bar_only", "Next-bar-open fill without explicit costs.", fill_model=FillModel.NEXT_BAR),
        _profile("forex_mild_realistic", "Illustrative mild combined FX assumptions.", spread=0.0001, slippage=0.00005, slippage_type=SlippageType.RANDOM, commission_per_trade=2.0),
        _profile("forex_moderate_realistic", "Illustrative moderate combined FX assumptions.", spread=0.0002, slippage=0.0001, slippage_type=SlippageType.RANDOM, commission_per_trade=5.0, fill_model=FillModel.NEXT_BAR),
        _profile("forex_harsh_realistic", "Illustrative harsh combined FX assumptions.", spread=0.0004, slippage=0.0002, slippage_type=SlippageType.RANDOM, commission_per_trade=10.0, fill_model=FillModel.NEXT_BAR),
    )


def crypto_execution_sensitivity_profiles() -> tuple[ExecutionSensitivityProfile, ...]:
    """Illustrative price-unit crypto scenarios, not exchange guarantees."""

    return (
        perfect_sensitivity_profile(),
        _profile("crypto_spread_only_mild", "Mild two-unit spread only.", spread=2.0),
        _profile("crypto_slippage_only_mild", "Mild seeded random slippage only.", slippage=1.0, slippage_type=SlippageType.RANDOM),
        _profile("crypto_commission_only_mild", "Mild percentage commission only.", commission_per_trade=0.02, commission_type=CommissionType.PERCENT),
        _profile("crypto_next_bar_only", "Next-bar-open fill without explicit costs.", fill_model=FillModel.NEXT_BAR),
        _profile("crypto_mild_realistic", "Illustrative mild combined crypto assumptions.", spread=2.0, slippage=1.0, slippage_type=SlippageType.RANDOM, commission_per_trade=0.02, commission_type=CommissionType.PERCENT),
        _profile("crypto_moderate_realistic", "Illustrative moderate combined crypto assumptions.", spread=5.0, slippage=2.5, slippage_type=SlippageType.RANDOM, commission_per_trade=0.05, commission_type=CommissionType.PERCENT, fill_model=FillModel.NEXT_BAR),
        _profile("crypto_harsh_realistic", "Illustrative harsh combined crypto assumptions.", spread=10.0, slippage=5.0, slippage_type=SlippageType.RANDOM, commission_per_trade=0.1, commission_type=CommissionType.PERCENT, fill_model=FillModel.NEXT_BAR),
    )


def _profile(
    name: str,
    description: str,
    **values: object,
) -> ExecutionSensitivityProfile:
    return ExecutionSensitivityProfile(
        name=name,
        description=description,
        execution_profile=ExecutionProfile(**values),
    )
