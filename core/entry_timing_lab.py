"""Aggregate entry-timing experiments without changing production calibration."""

from dataclasses import dataclass

from core.backtesting import BacktestTrade, calculate_backtest_metrics
from core.entry_timing import EntryTimingProfile, immediate_entry_timing_profile


@dataclass(frozen=True)
class EntryTimingResult:
    profile_name: str
    description: str
    total_candidates: int
    filled_trades: int
    missed_trades: int
    wins: int
    losses: int
    breakeven: int
    win_rate: float
    average_r: float
    total_r: float
    profit_factor: float | None
    max_drawdown_r: float
    average_entry_improvement_r: float
    average_entry_delay_bars: float
    average_missed_opportunity_r: float
    fallback_used_count: int
    human_readable_summary: str


@dataclass(frozen=True)
class EntryTimingSummary:
    profiles: tuple[EntryTimingResult, ...]
    best_profile: str
    worst_profile: str
    best_expectancy_profile: str
    highest_fill_rate_profile: str
    best_risk_adjusted_profile: str
    most_missed_profile: str
    human_readable_summary: str
    recommendations: tuple[str, ...]


def ensure_immediate_baseline(
    profiles: list[EntryTimingProfile],
) -> tuple[EntryTimingProfile, ...]:
    unique: dict[str, EntryTimingProfile] = {
        "immediate": immediate_entry_timing_profile()
    }
    for profile in profiles:
        if profile.name != "immediate":
            unique.setdefault(profile.name, profile)
    return tuple(unique.values())


def build_entry_timing_summary(
    profile_runs: list[tuple[EntryTimingProfile, list[BacktestTrade]]],
) -> EntryTimingSummary:
    if not profile_runs:
        raise ValueError("entry timing laboratory requires at least one profile")
    results: list[EntryTimingResult] = []
    for profile, trades in profile_runs:
        diagnostics = [
            trade.entry_timing_diagnostics
            for trade in trades
            if trade.entry_timing_diagnostics is not None
        ]
        filled = [item for item in diagnostics if item.filled]
        missed = [item for item in diagnostics if item.missed]
        metrics = calculate_backtest_metrics(trades)
        results.append(
            EntryTimingResult(
                profile_name=profile.name,
                description=profile.description,
                total_candidates=len(diagnostics),
                filled_trades=len(filled),
                missed_trades=len(missed),
                wins=metrics.wins,
                losses=metrics.losses,
                breakeven=metrics.breakeven,
                win_rate=metrics.win_rate,
                average_r=metrics.average_r,
                total_r=metrics.total_r,
                profit_factor=metrics.profit_factor,
                max_drawdown_r=metrics.max_drawdown_r,
                average_entry_improvement_r=(
                    round(sum(item.entry_improvement_r for item in filled) / len(filled), 6)
                    if filled else 0.0
                ),
                average_entry_delay_bars=(
                    round(sum(item.delay_bars for item in filled) / len(filled), 3)
                    if filled else 0.0
                ),
                average_missed_opportunity_r=(
                    round(sum(item.missed_opportunity_r for item in missed) / len(missed), 6)
                    if missed else 0.0
                ),
                fallback_used_count=sum(item.fallback_used for item in diagnostics),
                human_readable_summary=(
                    f"{profile.name} filled {len(filled)} of {len(diagnostics)} valid "
                    f"candidates and produced {metrics.average_r:.3f}R average expectancy; "
                    f"{len(missed)} entries were missed."
                ),
            )
        )

    counts = {item.total_candidates for item in results}
    if len(counts) > 1:
        raise ValueError("entry timing profiles did not receive the same candidate set")
    by_expectancy = sorted(results, key=lambda item: (item.average_r, item.profile_name))
    by_fill = sorted(
        results,
        key=lambda item: (
            item.filled_trades / item.total_candidates if item.total_candidates else 0.0,
            item.profile_name,
        ),
    )
    by_risk = sorted(
        results,
        key=lambda item: (
            item.average_r / (1.0 + item.max_drawdown_r),
            item.profile_name,
        ),
    )
    by_missed = sorted(results, key=lambda item: (item.missed_trades, item.profile_name))
    best = by_expectancy[-1]
    worst = by_expectancy[0]
    most_missed = by_missed[-1]
    recommendations = (
        f"Inspect {best.profile_name} as the strongest expectancy scenario, but compare "
        "its fill rate and drawdown before considering any production experiment.",
        f"{most_missed.profile_name} missed {most_missed.missed_trades} valid candidates; "
        "review missed-opportunity R before favoring its entry improvement.",
        "Entry timing results are counterfactual OHLC studies and do not authorize a "
        "change to production entry behavior.",
    )
    return EntryTimingSummary(
        profiles=tuple(results),
        best_profile=best.profile_name,
        worst_profile=worst.profile_name,
        best_expectancy_profile=best.profile_name,
        highest_fill_rate_profile=by_fill[-1].profile_name,
        best_risk_adjusted_profile=by_risk[-1].profile_name,
        most_missed_profile=most_missed.profile_name,
        human_readable_summary=(
            f"Compared {len(results)} timing profiles over "
            f"{results[0].total_candidates} identical valid candidates. "
            f"{best.profile_name} had the best expectancy and {worst.profile_name} the worst."
        ),
        recommendations=recommendations,
    )
