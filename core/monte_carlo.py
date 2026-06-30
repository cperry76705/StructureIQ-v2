"""Deterministic, research-only Monte Carlo trade-sequence simulation."""

from dataclasses import dataclass
from random import Random
from statistics import mean, median


@dataclass(frozen=True)
class MonteCarloSimulationResult:
    simulation: int
    method: str
    ending_balance: float
    total_r: float
    average_r: float
    max_drawdown_r: float
    max_drawdown_percent: float
    longest_losing_streak: int
    longest_winning_streak: int
    profit_factor: float | None
    win_rate: float
    risk_of_ruin: bool
    probability_of_profit: float
    probability_of_drawdown_over_5_percent: float
    probability_of_drawdown_over_10_percent: float
    probability_of_drawdown_over_20_percent: float
    peak_total_r: float
    peak_balance: float


@dataclass(frozen=True)
class MonteCarloSummary:
    available: bool
    simulations: int
    source_trades: int
    random_seed: int
    starting_balance: float
    risk_per_trade_percent: float
    methods: tuple[str, ...]
    median_ending_balance: float
    average_ending_balance: float
    best_case: float
    worst_case: float
    percentile_5: float
    percentile_25: float
    percentile_75: float
    percentile_95: float
    median_max_drawdown_r: float
    worst_max_drawdown_r: float
    average_losing_streak: float
    worst_losing_streak: int
    human_readable_summary: str


@dataclass(frozen=True)
class MonteCarloDistribution:
    simulations: tuple[MonteCarloSimulationResult, ...]


@dataclass(frozen=True)
class MonteCarloRiskSummary:
    risk_of_ruin: float
    probability_of_finishing_profitable: float
    probability_of_drawdown_over_5_percent: float
    probability_of_drawdown_over_10_percent: float
    probability_of_drawdown_over_20_percent: float
    expectancy_mean: float
    expectancy_standard_deviation: float
    risk_level: str
    human_readable_summary: str


@dataclass(frozen=True)
class MonteCarloResult:
    summary: MonteCarloSummary
    distribution: MonteCarloDistribution
    risk_summary: MonteCarloRiskSummary
    recommendations: tuple[str, ...]


def run_monte_carlo(
    realized_returns: list[float] | tuple[float, ...],
    *,
    simulations: int = 1_000,
    random_seed: int = 42,
    starting_balance: float = 10_000.0,
    risk_per_trade_percent: float = 1.0,
    execution_degradations: list[float] | tuple[float, ...] = (),
    skipped_trade_probability: float = 0.05,
) -> MonteCarloResult:
    """Resample completed R outcomes without modifying their source records."""

    returns = [float(value) for value in realized_returns]
    if not returns:
        return _unavailable(
            simulations, random_seed, starting_balance, risk_per_trade_percent
        )
    rng = Random(random_seed)
    degradations = [max(0.0, float(value)) for value in execution_degradations]
    results: list[MonteCarloSimulationResult] = []
    for index in range(simulations):
        if index % 2 == 0:
            sequence = list(returns)
            rng.shuffle(sequence)
            method = "trade_order_reshuffle"
        else:
            sequence = [rng.choice(returns) for _ in returns]
            method = "sampling_with_replacement"
        stressed: list[float] = []
        for value in sequence:
            adjusted = 0.0 if rng.random() < skipped_trade_probability else value
            if degradations and adjusted != 0.0:
                adjusted -= rng.choice(degradations) * rng.random()
            stressed.append(adjusted)
        results.append(
            _simulate_sequence(
                index + 1,
                method,
                stressed,
                starting_balance,
                risk_per_trade_percent,
            )
        )
    distribution = MonteCarloDistribution(tuple(results))
    risk = _risk_summary(results)
    endings = sorted(item.ending_balance for item in results)
    drawdowns = [item.max_drawdown_r for item in results]
    losing_streaks = [item.longest_losing_streak for item in results]
    summary = MonteCarloSummary(
        available=True,
        simulations=simulations,
        source_trades=len(returns),
        random_seed=random_seed,
        starting_balance=starting_balance,
        risk_per_trade_percent=risk_per_trade_percent,
        methods=("trade_order_reshuffle", "sampling_with_replacement"),
        median_ending_balance=round(median(endings), 2),
        average_ending_balance=round(mean(endings), 2),
        best_case=round(max(endings), 2),
        worst_case=round(min(endings), 2),
        percentile_5=round(_percentile(endings, 5), 2),
        percentile_25=round(_percentile(endings, 25), 2),
        percentile_75=round(_percentile(endings, 75), 2),
        percentile_95=round(_percentile(endings, 95), 2),
        median_max_drawdown_r=round(median(drawdowns), 4),
        worst_max_drawdown_r=round(max(drawdowns), 4),
        average_losing_streak=round(mean(losing_streaks), 3),
        worst_losing_streak=max(losing_streaks),
        human_readable_summary=(
            f"Monte Carlo ran {simulations} deterministic simulations over "
            f"{len(returns)} completed trades. Median ending balance was "
            f"{median(endings):.2f}, with {risk.probability_of_finishing_profitable:.1f}% "
            f"probability of finishing profitable."
        ),
    )
    return MonteCarloResult(
        summary=summary,
        distribution=distribution,
        risk_summary=risk,
        recommendations=_recommendations(risk, len(returns)),
    )


def _simulate_sequence(index, method, returns, starting_balance, risk_percent):
    balance = starting_balance
    peak_balance = balance
    cumulative_r = 0.0
    peak_r = 0.0
    max_drawdown_r = 0.0
    max_drawdown_percent = 0.0
    ruined = False
    winning = losing = longest_winning = longest_losing = 0
    for value in returns:
        cumulative_r += value
        peak_r = max(peak_r, cumulative_r)
        max_drawdown_r = max(max_drawdown_r, peak_r - cumulative_r)
        balance *= max(0.0, 1.0 + value * risk_percent / 100.0)
        peak_balance = max(peak_balance, balance)
        if peak_balance:
            max_drawdown_percent = max(
                max_drawdown_percent,
                (peak_balance - balance) / peak_balance * 100.0,
            )
        ruined = ruined or balance <= starting_balance * 0.5
        if value > 0:
            winning += 1
            losing = 0
        elif value < 0:
            losing += 1
            winning = 0
        else:
            winning = losing = 0
        longest_winning = max(longest_winning, winning)
        longest_losing = max(longest_losing, losing)
    wins = [value for value in returns if value > 0]
    losses = [-value for value in returns if value < 0]
    closed = len(wins) + len(losses)
    profit_factor = sum(wins) / sum(losses) if losses else None
    total_r = sum(returns)
    return MonteCarloSimulationResult(
        simulation=index,
        method=method,
        ending_balance=round(balance, 2),
        total_r=round(total_r, 6),
        average_r=round(total_r / len(returns), 6),
        max_drawdown_r=round(max_drawdown_r, 6),
        max_drawdown_percent=round(max_drawdown_percent, 6),
        longest_losing_streak=longest_losing,
        longest_winning_streak=longest_winning,
        profit_factor=round(profit_factor, 6) if profit_factor is not None else None,
        win_rate=round(len(wins) / closed * 100.0 if closed else 0.0, 3),
        risk_of_ruin=ruined,
        probability_of_profit=100.0 if balance > starting_balance else 0.0,
        probability_of_drawdown_over_5_percent=(
            100.0 if max_drawdown_percent > 5.0 else 0.0
        ),
        probability_of_drawdown_over_10_percent=(
            100.0 if max_drawdown_percent > 10.0 else 0.0
        ),
        probability_of_drawdown_over_20_percent=(
            100.0 if max_drawdown_percent > 20.0 else 0.0
        ),
        peak_total_r=round(peak_r, 6),
        peak_balance=round(peak_balance, 2),
    )


def _risk_summary(results):
    count = len(results)
    expectancies = [item.average_r for item in results]
    expectancy_mean = mean(expectancies)
    variance = mean((value - expectancy_mean) ** 2 for value in expectancies)
    ruin = sum(item.risk_of_ruin for item in results) / count * 100.0
    profit_probability = sum(item.probability_of_profit for item in results) / count
    drawdown_5 = sum(item.probability_of_drawdown_over_5_percent for item in results) / count
    drawdown_10 = sum(item.probability_of_drawdown_over_10_percent for item in results) / count
    drawdown_20 = sum(item.probability_of_drawdown_over_20_percent for item in results) / count
    risk_level = (
        "high" if ruin >= 5.0 or drawdown_20 >= 25.0
        else "medium" if drawdown_10 >= 25.0 or profit_probability < 60.0
        else "low"
    )
    return MonteCarloRiskSummary(
        risk_of_ruin=round(ruin, 3),
        probability_of_finishing_profitable=round(profit_probability, 3),
        probability_of_drawdown_over_5_percent=round(drawdown_5, 3),
        probability_of_drawdown_over_10_percent=round(drawdown_10, 3),
        probability_of_drawdown_over_20_percent=round(drawdown_20, 3),
        expectancy_mean=round(expectancy_mean, 6),
        expectancy_standard_deviation=round(variance ** 0.5, 6),
        risk_level=risk_level,
        human_readable_summary=(
            f"Sequence risk is {risk_level}: ruin probability is {ruin:.1f}%, "
            f"profit probability is {profit_probability:.1f}%, and the probability "
            f"of drawdown beyond 20% is {drawdown_20:.1f}%."
        ),
    )


def _recommendations(risk, source_trades):
    items = []
    if source_trades < 100:
        items.append(
            "Collect at least 100 closed validation trades before interpreting "
            "Monte Carlo tail risk as stable."
        )
    if risk.risk_of_ruin >= 5.0:
        items.append("Do not promote while simulated risk of ruin remains elevated.")
    if risk.probability_of_drawdown_over_20_percent >= 25.0:
        items.append(
            "Review sequence and sizing risk before any paper-trading proposal."
        )
    if not items:
        items.append(
            "Continue out-of-sample monitoring; Monte Carlo results do not authorize "
            "a production change."
        )
    return tuple(items)


def _percentile(values, percentile):
    if len(values) == 1:
        return values[0]
    position = (len(values) - 1) * percentile / 100.0
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    weight = position - lower
    return values[lower] * (1.0 - weight) + values[upper] * weight


def _unavailable(simulations, seed, balance, risk_percent):
    summary = MonteCarloSummary(
        available=False,
        simulations=0,
        source_trades=0,
        random_seed=seed,
        starting_balance=balance,
        risk_per_trade_percent=risk_percent,
        methods=(),
        median_ending_balance=balance,
        average_ending_balance=balance,
        best_case=balance,
        worst_case=balance,
        percentile_5=balance,
        percentile_25=balance,
        percentile_75=balance,
        percentile_95=balance,
        median_max_drawdown_r=0.0,
        worst_max_drawdown_r=0.0,
        average_losing_streak=0.0,
        worst_losing_streak=0,
        human_readable_summary=(
            "Monte Carlo analysis is unavailable because no closed trades exist."
        ),
    )
    risk = MonteCarloRiskSummary(
        risk_of_ruin=0.0,
        probability_of_finishing_profitable=0.0,
        probability_of_drawdown_over_5_percent=0.0,
        probability_of_drawdown_over_10_percent=0.0,
        probability_of_drawdown_over_20_percent=0.0,
        expectancy_mean=0.0,
        expectancy_standard_deviation=0.0,
        risk_level="unavailable",
        human_readable_summary="No completed sequence is available for risk analysis.",
    )
    return MonteCarloResult(
        summary,
        MonteCarloDistribution(()),
        risk,
        ("Run calibration until closed trades are available.",),
    )
