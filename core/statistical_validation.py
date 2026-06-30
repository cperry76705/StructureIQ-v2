"""Research-only statistical weakness detection over completed trade returns."""

from dataclasses import dataclass
from math import ceil, log
from statistics import mean, pstdev


WEAKNESS_FLAGS = (
    "EDGE_DECAY",
    "HIGH_OUTLIER_DEPENDENCY",
    "LARGE_LOSING_STREAK_RISK",
    "FOLD_INSTABILITY",
    "PROFIT_CONCENTRATION",
    "NEGATIVE_RECENT_EXPECTANCY",
    "LOW_SAMPLE_SIZE",
)


@dataclass(frozen=True)
class LosingStreakSummary:
    probability_of_3_losses_in_row: float
    probability_of_5_losses_in_row: float
    probability_of_8_losses_in_row: float
    probability_of_10_losses_in_row: float
    worst_observed_losing_streak: int
    expected_losing_streak: float
    human_readable_summary: str


@dataclass(frozen=True)
class TradeDistributionSummary:
    r_distribution_buckets: dict[str, int]
    top_10_percent_trade_contribution: float
    top_5_percent_trade_contribution: float
    outlier_dependency_score: float
    human_readable_summary: str


@dataclass(frozen=True)
class EdgeDecaySummary:
    expectancy_first_third: float
    expectancy_middle_third: float
    expectancy_final_third: float
    edge_decay_score: float
    human_readable_summary: str


@dataclass(frozen=True)
class StatisticalFoldStabilitySummary:
    folds_analyzed: int
    fold_expectancies: tuple[float, ...]
    expectancy_standard_deviation: float
    positive_fold_rate: float
    fold_stability_score: float
    human_readable_summary: str


@dataclass(frozen=True)
class WeaknessDetectionSummary:
    weakness_flags: tuple[str, ...]
    weakness_score: float
    severe_weakness: bool
    readiness_blocked: bool
    human_readable_summary: str


@dataclass(frozen=True)
class StatisticalValidationSummary:
    available: bool
    sample_size: int
    average_r: float
    profitable: bool
    weakness_flag_count: int
    weakness_score: float
    overall_status: str
    human_readable_summary: str


@dataclass(frozen=True)
class StatisticalValidationResult:
    statistical_validation_summary: StatisticalValidationSummary
    losing_streak_summary: LosingStreakSummary
    trade_distribution_summary: TradeDistributionSummary
    edge_decay_summary: EdgeDecaySummary
    fold_stability_summary: StatisticalFoldStabilitySummary
    weakness_detection_summary: WeaknessDetectionSummary


def build_statistical_validation(
    realized_returns: list[float] | tuple[float, ...],
    *,
    fold_expectancies: list[float] | tuple[float, ...] = (),
) -> StatisticalValidationResult:
    """Measure hidden weakness without changing the source trade sequence."""

    returns = [float(value) for value in realized_returns]
    if not returns:
        return _unavailable()
    loss_rate = sum(value < 0 for value in returns) / len(returns)
    probabilities = {
        length: _run_probability(len(returns), loss_rate, length)
        for length in (3, 5, 8, 10)
    }
    losing = LosingStreakSummary(
        probability_of_3_losses_in_row=probabilities[3],
        probability_of_5_losses_in_row=probabilities[5],
        probability_of_8_losses_in_row=probabilities[8],
        probability_of_10_losses_in_row=probabilities[10],
        worst_observed_losing_streak=_observed_streak(returns),
        expected_losing_streak=_expected_losing_streak(
            len(returns), loss_rate
        ),
        human_readable_summary=(
            f"The observed loss rate implies a {probabilities[5]:.1f}% probability "
            f"of at least one five-loss sequence across {len(returns)} trades."
        ),
    )
    distribution = _distribution(returns)
    edge = _edge_decay(returns)
    folds = _fold_stability(fold_expectancies)
    flags = _flags(returns, losing, distribution, edge, folds)
    severe = bool(
        "NEGATIVE_RECENT_EXPECTANCY" in flags
        or edge.edge_decay_score >= 70.0
        or distribution.top_10_percent_trade_contribution > 80.0
        or folds.fold_stability_score < 50.0
        or losing.probability_of_10_losses_in_row >= 25.0
        or losing.worst_observed_losing_streak >= 10
        or "LOW_SAMPLE_SIZE" in flags
    )
    weakness_score = _weakness_score(losing, distribution, edge, folds, flags)
    weakness = WeaknessDetectionSummary(
        weakness_flags=flags,
        weakness_score=weakness_score,
        severe_weakness=severe,
        readiness_blocked=severe,
        human_readable_summary=(
            "No material statistical weakness was detected."
            if not flags else
            f"Detected {len(flags)} weakness flags: {', '.join(flags)}."
        ),
    )
    status = "FAIL" if severe else "WATCHLIST" if flags else "PASS"
    average = mean(returns)
    return StatisticalValidationResult(
        statistical_validation_summary=StatisticalValidationSummary(
            available=True,
            sample_size=len(returns),
            average_r=round(average, 6),
            profitable=average > 0,
            weakness_flag_count=len(flags),
            weakness_score=weakness_score,
            overall_status=status,
            human_readable_summary=(
                f"Statistical validation is {status} across {len(returns)} trades "
                f"with {average:.3f}R average expectancy and "
                f"{weakness_score:.1f}/100 weakness score."
            ),
        ),
        losing_streak_summary=losing,
        trade_distribution_summary=distribution,
        edge_decay_summary=edge,
        fold_stability_summary=folds,
        weakness_detection_summary=weakness,
    )


def statistical_validation_blocks_readiness(
    result: StatisticalValidationResult | None,
) -> bool:
    return bool(result and result.weakness_detection_summary.readiness_blocked)


def _distribution(returns):
    buckets = {
        "below_-1R": 0,
        "-1R_to_0R": 0,
        "0R_to_1R": 0,
        "1R_to_2R": 0,
        "2R_to_3R": 0,
        "3R_to_5R": 0,
        "above_5R": 0,
    }
    for value in returns:
        if value < -1:
            buckets["below_-1R"] += 1
        elif value < 0:
            buckets["-1R_to_0R"] += 1
        elif value < 1:
            buckets["0R_to_1R"] += 1
        elif value < 2:
            buckets["1R_to_2R"] += 1
        elif value < 3:
            buckets["2R_to_3R"] += 1
        elif value <= 5:
            buckets["3R_to_5R"] += 1
        else:
            buckets["above_5R"] += 1
    positive = sorted((value for value in returns if value > 0), reverse=True)
    total_profit = sum(positive)
    top_10 = _contribution(positive, total_profit, 0.10, len(returns))
    top_5 = _contribution(positive, total_profit, 0.05, len(returns))
    dependency = min(100.0, top_10)
    return TradeDistributionSummary(
        r_distribution_buckets=buckets,
        top_10_percent_trade_contribution=top_10,
        top_5_percent_trade_contribution=top_5,
        outlier_dependency_score=round(dependency, 3),
        human_readable_summary=(
            f"The top 10% of profitable trades contributed {top_10:.1f}% of "
            f"gross positive R."
        ),
    )


def _edge_decay(returns):
    first, middle, final = _thirds(returns)
    first_expectancy = mean(first) if first else 0.0
    middle_expectancy = mean(middle) if middle else 0.0
    final_expectancy = mean(final) if final else 0.0
    denominator = max(abs(first_expectancy), 0.1)
    decay = max(0.0, min(100.0, (first_expectancy - final_expectancy) / denominator * 100.0))
    return EdgeDecaySummary(
        expectancy_first_third=round(first_expectancy, 6),
        expectancy_middle_third=round(middle_expectancy, 6),
        expectancy_final_third=round(final_expectancy, 6),
        edge_decay_score=round(decay, 3),
        human_readable_summary=(
            f"Expectancy moved from {first_expectancy:.3f}R in the first third "
            f"to {final_expectancy:.3f}R in the final third."
        ),
    )


def _fold_stability(values):
    folds = [float(value) for value in values]
    if not folds:
        return StatisticalFoldStabilitySummary(
            0, (), 0.0, 0.0, 100.0,
            "Fold stability was not requested; no penalty was applied.",
        )
    deviation = pstdev(folds) if len(folds) > 1 else 0.0
    positive_rate = sum(value > 0 for value in folds) / len(folds) * 100.0
    stability = max(0.0, min(100.0, positive_rate * 0.5 + max(0.0, 100 - deviation * 30) * 0.5))
    return StatisticalFoldStabilitySummary(
        folds_analyzed=len(folds),
        fold_expectancies=tuple(folds),
        expectancy_standard_deviation=round(deviation, 6),
        positive_fold_rate=round(positive_rate, 3),
        fold_stability_score=round(stability, 3),
        human_readable_summary=(
            f"{len(folds)} folds produced {stability:.1f}/100 stability with "
            f"{positive_rate:.1f}% positive folds."
        ),
    )


def _flags(returns, losing, distribution, edge, folds):
    flags = []
    if edge.edge_decay_score >= 50:
        flags.append("EDGE_DECAY")
    if distribution.outlier_dependency_score >= 70:
        flags.append("HIGH_OUTLIER_DEPENDENCY")
    if losing.probability_of_8_losses_in_row >= 50 or losing.worst_observed_losing_streak >= 8:
        flags.append("LARGE_LOSING_STREAK_RISK")
    if folds.folds_analyzed and folds.fold_stability_score < 50:
        flags.append("FOLD_INSTABILITY")
    if distribution.top_10_percent_trade_contribution > 80:
        flags.append("PROFIT_CONCENTRATION")
    if edge.expectancy_final_third < 0:
        flags.append("NEGATIVE_RECENT_EXPECTANCY")
    if len(returns) < 100:
        flags.append("LOW_SAMPLE_SIZE")
    return tuple(flags)


def _weakness_score(losing, distribution, edge, folds, flags):
    streak = max(
        losing.probability_of_10_losses_in_row,
        min(100.0, losing.worst_observed_losing_streak * 10.0),
    )
    fold_weakness = 100.0 - folds.fold_stability_score
    score = (
        edge.edge_decay_score * 0.25
        + distribution.outlier_dependency_score * 0.25
        + streak * 0.20
        + fold_weakness * 0.20
        + (100.0 if "LOW_SAMPLE_SIZE" in flags else 0.0) * 0.10
    )
    return round(min(100.0, score), 3)


def _run_probability(trades, loss_probability, run_length):
    if trades < run_length or loss_probability <= 0:
        return 0.0
    if loss_probability >= 1:
        return 100.0
    states = [0.0] * run_length
    states[0] = 1.0
    for _ in range(trades):
        next_states = [0.0] * run_length
        survival = sum(states)
        next_states[0] += survival * (1.0 - loss_probability)
        for streak in range(run_length - 1):
            next_states[streak + 1] += states[streak] * loss_probability
        states = next_states
    return round((1.0 - sum(states)) * 100.0, 3)


def _observed_streak(returns):
    current = worst = 0
    for value in returns:
        current = current + 1 if value < 0 else 0
        worst = max(worst, current)
    return worst


def _expected_losing_streak(trades, loss_probability):
    """Approximate the expected longest Bernoulli loss run efficiently."""

    if not trades or loss_probability <= 0:
        return 0.0
    if loss_probability >= 1:
        return float(trades)
    opportunities = max(1.0, trades * (1.0 - loss_probability))
    return round(max(0.0, log(opportunities, 1.0 / loss_probability)), 3)


def _contribution(positive, total, fraction, sample_size):
    if not positive or total <= 0:
        return 0.0
    count = min(len(positive), max(1, ceil(sample_size * fraction)))
    return round(sum(positive[:count]) / total * 100.0, 3)


def _thirds(returns):
    size = len(returns)
    first_end = ceil(size / 3)
    second_end = ceil(size * 2 / 3)
    return returns[:first_end], returns[first_end:second_end], returns[second_end:]


def _unavailable():
    losing = LosingStreakSummary(0, 0, 0, 0, 0, 0, "No closed trades are available.")
    distribution = TradeDistributionSummary(
        {
            "below_-1R": 0, "-1R_to_0R": 0, "0R_to_1R": 0,
            "1R_to_2R": 0, "2R_to_3R": 0, "3R_to_5R": 0, "above_5R": 0,
        },
        0, 0, 0, "No return distribution is available.",
    )
    edge = EdgeDecaySummary(0, 0, 0, 0, "No edge history is available.")
    folds = StatisticalFoldStabilitySummary(
        0, (), 0, 0, 0, "No fold history is available."
    )
    weakness = WeaknessDetectionSummary(
        ("LOW_SAMPLE_SIZE",), 100, True, True,
        "Statistical validation is unavailable without closed trades.",
    )
    return StatisticalValidationResult(
        StatisticalValidationSummary(
            False, 0, 0, False, 1, 100, "INSUFFICIENT_DATA",
            "Statistical validation is unavailable because no closed trades exist.",
        ),
        losing, distribution, edge, folds, weakness,
    )
