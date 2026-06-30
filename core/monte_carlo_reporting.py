"""Professional research-risk interpretation for Monte Carlo simulations."""

from dataclasses import dataclass
from math import sqrt
from statistics import mean, median, pstdev
from typing import Literal

from core.monte_carlo import MonteCarloResult


RiskStatus = Literal["LOW", "MEDIUM", "HIGH"]
ReportStatus = Literal["PASS", "WATCHLIST", "FAIL", "INSUFFICIENT_DATA"]


@dataclass(frozen=True)
class MonteCarloReport:
    simulations: int
    source_trades: int
    median_ending_balance: float
    average_ending_balance: float
    best_case: float
    worst_case: float
    percentile_5_ending_balance: float
    percentile_1_ending_balance: float
    median_total_r: float
    worst_5_percent_total_r: float
    worst_1_percent_total_r: float
    median_max_drawdown: float
    worst_max_drawdown: float
    probability_of_profit: float
    probability_of_loss: float
    risk_of_ruin: float
    probability_of_drawdown_over_5_percent: float
    probability_of_drawdown_over_10_percent: float
    probability_of_drawdown_over_20_percent: float
    probability_of_drawdown_over_30_percent: float
    median_longest_losing_streak: float
    worst_longest_losing_streak: int
    overall_status: ReportStatus
    human_readable_summary: str


@dataclass(frozen=True)
class MonteCarloTargetProbabilities:
    probability_reaching_5r: float
    probability_reaching_10r: float
    probability_reaching_20r: float
    probability_reaching_50r: float
    probability_growth_10_percent: float
    probability_growth_25_percent: float
    probability_growth_50_percent: float
    probability_account_doubling: float
    probability_finishing_below_starting_balance: float


@dataclass(frozen=True)
class RiskHeatmapItem:
    status: RiskStatus
    score: float
    explanation: str


@dataclass(frozen=True)
class MonteCarloRiskHeatmap:
    drawdown_risk: RiskHeatmapItem
    ruin_risk: RiskHeatmapItem
    losing_streak_risk: RiskHeatmapItem
    tail_risk: RiskHeatmapItem
    profit_stability: RiskHeatmapItem


@dataclass(frozen=True)
class ConfidenceInterval:
    lower: float
    upper: float


@dataclass(frozen=True)
class MonteCarloExpectancyConfidence:
    mean_expectancy: float
    standard_deviation: float
    standard_error: float
    confidence_interval_90: ConfidenceInterval
    confidence_interval_95: ConfidenceInterval
    confidence_interval_99: ConfidenceInterval
    lower_bound_positive: bool
    sample_warning: str | None


@dataclass(frozen=True)
class MonteCarloKellySummary:
    average_win_r: float
    average_loss_r: float
    win_rate: float
    loss_rate: float
    full_kelly_fraction: float
    half_kelly_fraction: float
    quarter_kelly_fraction: float
    recommended_research_risk_fraction: float
    warning: str | None


@dataclass(frozen=True)
class MonteCarloReportingResult:
    report: MonteCarloReport
    risk_heatmap: MonteCarloRiskHeatmap
    target_probabilities: MonteCarloTargetProbabilities
    expectancy_confidence: MonteCarloExpectancyConfidence
    kelly_summary: MonteCarloKellySummary
    failure_reasons: tuple[str, ...]


def build_monte_carlo_report(
    monte_carlo: MonteCarloResult,
    source_returns: list[float] | tuple[float, ...],
) -> MonteCarloReportingResult:
    """Interpret simulation output without applying any production adjustment."""

    returns = [float(value) for value in source_returns]
    simulations = list(monte_carlo.distribution.simulations)
    confidence = _expectancy_confidence(returns)
    kelly = _kelly(returns)
    if not simulations:
        return _unavailable(monte_carlo, confidence, kelly)

    endings = sorted(item.ending_balance for item in simulations)
    totals = sorted(item.total_r for item in simulations)
    peak_totals = [item.peak_total_r for item in simulations]
    peak_balances = [item.peak_balance for item in simulations]
    drawdowns = [item.max_drawdown_percent for item in simulations]
    streaks = [item.longest_losing_streak for item in simulations]
    starting = monte_carlo.summary.starting_balance
    probability_profit = _percentage(
        sum(item.ending_balance > starting for item in simulations), len(simulations)
    )
    probability_loss = _percentage(
        sum(item.ending_balance < starting for item in simulations), len(simulations)
    )
    probability_30 = _percentage(
        sum(item.max_drawdown_percent > 30.0 for item in simulations), len(simulations)
    )
    targets = MonteCarloTargetProbabilities(
        probability_reaching_5r=_threshold_probability(peak_totals, 5.0),
        probability_reaching_10r=_threshold_probability(peak_totals, 10.0),
        probability_reaching_20r=_threshold_probability(peak_totals, 20.0),
        probability_reaching_50r=_threshold_probability(peak_totals, 50.0),
        probability_growth_10_percent=_threshold_probability(
            peak_balances, starting * 1.10
        ),
        probability_growth_25_percent=_threshold_probability(
            peak_balances, starting * 1.25
        ),
        probability_growth_50_percent=_threshold_probability(
            peak_balances, starting * 1.50
        ),
        probability_account_doubling=_threshold_probability(
            peak_balances, starting * 2.0
        ),
        probability_finishing_below_starting_balance=probability_loss,
    )
    heatmap = _heatmap(
        monte_carlo,
        probability_loss,
        _percentile(totals, 1),
        max(streaks),
    )
    provisional = MonteCarloReport(
        simulations=len(simulations),
        source_trades=len(returns),
        median_ending_balance=round(median(endings), 2),
        average_ending_balance=round(mean(endings), 2),
        best_case=round(max(endings), 2),
        worst_case=round(min(endings), 2),
        percentile_5_ending_balance=round(_percentile(endings, 5), 2),
        percentile_1_ending_balance=round(_percentile(endings, 1), 2),
        median_total_r=round(median(totals), 4),
        worst_5_percent_total_r=round(_percentile(totals, 5), 4),
        worst_1_percent_total_r=round(_percentile(totals, 1), 4),
        median_max_drawdown=round(median(drawdowns), 4),
        worst_max_drawdown=round(max(drawdowns), 4),
        probability_of_profit=probability_profit,
        probability_of_loss=probability_loss,
        risk_of_ruin=monte_carlo.risk_summary.risk_of_ruin,
        probability_of_drawdown_over_5_percent=(
            monte_carlo.risk_summary.probability_of_drawdown_over_5_percent
        ),
        probability_of_drawdown_over_10_percent=(
            monte_carlo.risk_summary.probability_of_drawdown_over_10_percent
        ),
        probability_of_drawdown_over_20_percent=(
            monte_carlo.risk_summary.probability_of_drawdown_over_20_percent
        ),
        probability_of_drawdown_over_30_percent=probability_30,
        median_longest_losing_streak=round(median(streaks), 3),
        worst_longest_losing_streak=max(streaks),
        overall_status="WATCHLIST",
        human_readable_summary="",
    )
    failures = _failure_reasons(provisional, heatmap, confidence)
    status = _status(provisional, heatmap, confidence, failures)
    report = MonteCarloReport(
        **{
            **provisional.__dict__,
            "overall_status": status,
            "human_readable_summary": (
                f"Monte Carlo risk status is {status} across {len(simulations)} "
                f"simulations and {len(returns)} source trades. Profit probability "
                f"is {probability_profit:.1f}%, ruin risk is "
                f"{provisional.risk_of_ruin:.1f}%, and 20% drawdown probability "
                f"is {provisional.probability_of_drawdown_over_20_percent:.1f}%."
            ),
        }
    )
    return MonteCarloReportingResult(
        report=report,
        risk_heatmap=heatmap,
        target_probabilities=targets,
        expectancy_confidence=confidence,
        kelly_summary=kelly,
        failure_reasons=failures,
    )


def monte_carlo_blocks_readiness(result: MonteCarloReportingResult | None) -> bool:
    if result is None:
        return False
    report = result.report
    return bool(
        report.risk_of_ruin >= 5.0
        or report.probability_of_drawdown_over_20_percent >= 25.0
        or not result.expectancy_confidence.lower_bound_positive
        or report.source_trades < 100
        or result.risk_heatmap.tail_risk.status == "HIGH"
        or result.risk_heatmap.ruin_risk.status == "HIGH"
    )


def _expectancy_confidence(returns):
    count = len(returns)
    average = mean(returns) if returns else 0.0
    deviation = pstdev(returns) if len(returns) > 1 else 0.0
    error = deviation / sqrt(count) if count else 0.0
    interval_90 = _interval(average, error, 1.645)
    interval_95 = _interval(average, error, 1.96)
    interval_99 = _interval(average, error, 2.576)
    return MonteCarloExpectancyConfidence(
        mean_expectancy=round(average, 6),
        standard_deviation=round(deviation, 6),
        standard_error=round(error, 6),
        confidence_interval_90=interval_90,
        confidence_interval_95=interval_95,
        confidence_interval_99=interval_99,
        lower_bound_positive=interval_95.lower > 0,
        sample_warning=(
            f"Only {count} closed trades are available; at least 100 are required."
            if count < 100 else None
        ),
    )


def _kelly(returns):
    wins = [value for value in returns if value > 0]
    losses = [-value for value in returns if value < 0]
    closed = len(wins) + len(losses)
    average_win = mean(wins) if wins else 0.0
    average_loss = mean(losses) if losses else 0.0
    win_rate = len(wins) / closed if closed else 0.0
    loss_rate = len(losses) / closed if closed else 0.0
    payoff = average_win / average_loss if average_loss else 0.0
    full = win_rate - loss_rate / payoff if payoff else 0.0
    full = max(-1.0, min(1.0, full))
    extreme = bool(
        returns
        and median(abs(value) for value in returns) > 0
        and max(abs(value) for value in returns)
        > median(abs(value) for value in returns) * 5
    )
    warning = (
        "Kelly estimate is unstable because fewer than 100 closed trades are available."
        if len(returns) < 100 else
        "Kelly estimate is unstable because extreme R outcomes dominate the sample."
        if extreme else None
    )
    quarter = full / 4.0
    return MonteCarloKellySummary(
        average_win_r=round(average_win, 6),
        average_loss_r=round(average_loss, 6),
        win_rate=round(win_rate * 100.0, 3),
        loss_rate=round(loss_rate * 100.0, 3),
        full_kelly_fraction=round(full, 6),
        half_kelly_fraction=round(full / 2.0, 6),
        quarter_kelly_fraction=round(quarter, 6),
        recommended_research_risk_fraction=round(max(0.0, min(0.02, quarter)), 6),
        warning=warning,
    )


def _heatmap(monte_carlo, probability_loss, worst_1_r, worst_streak):
    risk = monte_carlo.risk_summary
    drawdown_score = min(
        100.0,
        risk.probability_of_drawdown_over_20_percent * 2.0
        + risk.probability_of_drawdown_over_10_percent * 0.5,
    )
    ruin_score = min(100.0, risk.risk_of_ruin * 10.0)
    streak_score = min(100.0, worst_streak * 10.0)
    tail_score = min(100.0, probability_loss + (25.0 if worst_1_r < 0 else 0.0))
    stability_score = min(100.0, probability_loss)
    return MonteCarloRiskHeatmap(
        drawdown_risk=_heat_item(
            drawdown_score,
            f"20% drawdown probability is {risk.probability_of_drawdown_over_20_percent:.1f}%.",
        ),
        ruin_risk=_heat_item(
            ruin_score, f"Simulated risk of ruin is {risk.risk_of_ruin:.1f}%."
        ),
        losing_streak_risk=_heat_item(
            streak_score, f"Worst simulated losing streak is {worst_streak} trades."
        ),
        tail_risk=_heat_item(
            tail_score,
            f"Worst 1% total R is {worst_1_r:.2f}R and loss probability is {probability_loss:.1f}%.",
        ),
        profit_stability=_heat_item(
            stability_score,
            f"Probability of finishing below starting balance is {probability_loss:.1f}%.",
        ),
    )


def _heat_item(score, explanation):
    status: RiskStatus = "HIGH" if score >= 50 else "MEDIUM" if score >= 20 else "LOW"
    return RiskHeatmapItem(status, round(score, 3), explanation)


def _failure_reasons(report, heatmap, confidence):
    reasons = []
    if report.risk_of_ruin >= 5.0:
        reasons.append("risk_of_ruin_too_high")
    if report.probability_of_drawdown_over_20_percent >= 25.0:
        reasons.append("drawdown_probability_too_high")
    if report.source_trades < 100:
        reasons.append("insufficient_trade_sample")
    if heatmap.tail_risk.status == "HIGH":
        reasons.append("unstable_tail_distribution")
    if report.worst_case < 0 or report.worst_1_percent_total_r < 0:
        reasons.append("negative_worst_case")
    if not confidence.lower_bound_positive:
        reasons.append("expectancy_confidence_crosses_zero")
    if heatmap.losing_streak_risk.status == "HIGH":
        reasons.append("excessive_losing_streak_risk")
    return tuple(reasons)


def _status(report, heatmap, confidence, failures):
    if report.source_trades < 100:
        return "INSUFFICIENT_DATA"
    hard_failures = {
        "risk_of_ruin_too_high",
        "drawdown_probability_too_high",
        "unstable_tail_distribution",
        "expectancy_confidence_crosses_zero",
    }
    if hard_failures.intersection(failures):
        return "FAIL"
    if heatmap.drawdown_risk.status == "MEDIUM" or report.probability_of_profit < 75:
        return "WATCHLIST"
    return "PASS"


def _unavailable(monte_carlo, confidence, kelly):
    starting = monte_carlo.summary.starting_balance
    empty_item = RiskHeatmapItem("HIGH", 100.0, "No closed trades are available.")
    return MonteCarloReportingResult(
        report=MonteCarloReport(
            simulations=0,
            source_trades=0,
            median_ending_balance=starting,
            average_ending_balance=starting,
            best_case=starting,
            worst_case=starting,
            percentile_5_ending_balance=starting,
            percentile_1_ending_balance=starting,
            median_total_r=0.0,
            worst_5_percent_total_r=0.0,
            worst_1_percent_total_r=0.0,
            median_max_drawdown=0.0,
            worst_max_drawdown=0.0,
            probability_of_profit=0.0,
            probability_of_loss=0.0,
            risk_of_ruin=0.0,
            probability_of_drawdown_over_5_percent=0.0,
            probability_of_drawdown_over_10_percent=0.0,
            probability_of_drawdown_over_20_percent=0.0,
            probability_of_drawdown_over_30_percent=0.0,
            median_longest_losing_streak=0.0,
            worst_longest_losing_streak=0,
            overall_status="INSUFFICIENT_DATA",
            human_readable_summary="Monte Carlo reporting is unavailable without closed trades.",
        ),
        risk_heatmap=MonteCarloRiskHeatmap(
            empty_item, empty_item, empty_item, empty_item, empty_item
        ),
        target_probabilities=MonteCarloTargetProbabilities(
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
        ),
        expectancy_confidence=confidence,
        kelly_summary=kelly,
        failure_reasons=("insufficient_trade_sample",),
    )


def _interval(average, error, z):
    return ConfidenceInterval(
        round(average - z * error, 6), round(average + z * error, 6)
    )


def _percentage(count, total):
    return round(count / total * 100.0 if total else 0.0, 3)


def _threshold_probability(values, threshold):
    return _percentage(sum(value >= threshold for value in values), len(values))


def _percentile(values, percentile):
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    position = (len(values) - 1) * percentile / 100.0
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    weight = position - lower
    return values[lower] * (1.0 - weight) + values[upper] * weight
