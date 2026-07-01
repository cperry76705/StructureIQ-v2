"""Research-only, replaceable setup-quality scoring and historical analytics."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from math import sqrt
from statistics import mean
from typing import Any, Iterable


@dataclass(frozen=True)
class SetupQualityComponents:
    market_structure: float
    liquidity: float
    confirmation: float
    higher_timeframe: float
    risk_reward: float
    trend_alignment: float
    volatility: float
    freshness: float


@dataclass(frozen=True)
class SetupQualityResult:
    score: float
    grade: str
    components: SetupQualityComponents
    human_readable_summary: str

    @property
    def summary(self) -> str:
        """Backward-friendly short alias used by dashboard clients."""
        return self.human_readable_summary


@dataclass(frozen=True)
class SetupQualityGroup:
    name: str
    records: int
    average_quality: float
    grade: str
    wins: int
    win_rate: float
    average_r: float
    expectancy: float
    profit_factor: float | None
    max_drawdown: float
    quality_rank: int = 0


@dataclass(frozen=True)
class SetupQualityCorrelation:
    metric: str
    coefficient: float | None
    sample_size: int
    interpretation: str


@dataclass(frozen=True)
class SetupQualitySummary:
    average_quality_score: float
    highest_quality_trade: SetupQualityResult | None
    lowest_quality_trade: SetupQualityResult | None
    average_quality_by_symbol: tuple[SetupQualityGroup, ...]
    average_quality_by_strategy: tuple[SetupQualityGroup, ...]
    average_quality_by_setup: tuple[SetupQualityGroup, ...]
    average_quality_by_regime: tuple[SetupQualityGroup, ...]
    quality_distribution: dict[str, int]
    grade_distribution: dict[str, int]
    correlations: tuple[SetupQualityCorrelation, ...]
    recommendations: tuple[str, ...]
    total_records: int
    completed_trades: int
    human_readable_summary: str


def grade_for_score(score: float) -> str:
    """Map a bounded score to the public v4.4 grade scale."""
    value = max(0.0, min(100.0, float(score)))
    if value >= 95:
        return "A+"
    if value >= 90:
        return "A"
    if value >= 85:
        return "B+"
    if value >= 80:
        return "B"
    if value >= 75:
        return "C+"
    if value >= 70:
        return "C"
    if value >= 65:
        return "D"
    return "F"


class SetupQualityEngine:
    """Score existing evidence without selecting, confirming, or executing setups.

    ``score`` is the stable public extension point. A future statistical or ML
    scorer can implement the same input/output contract without changing APIs.
    """

    def score(
        self,
        *,
        market_structure: Any = None,
        multi_timeframe: Any = None,
        setup_plan: Any = None,
        market_regime: Any = None,
        decision: Any = None,
        candles: Iterable[Any] = (),
    ) -> SetupQualityResult:
        events = set(getattr(market_structure, "structure_events", ()) or ())
        trend = _value(getattr(market_structure, "trend", "unclear"))
        phase = _value(getattr(market_structure, "phase", "unclear"))
        structure = 4.0
        structure += 6.0 if any("bos" in item for item in events) else 0.0
        structure += 3.0 if any("choch" in item for item in events) else 0.0
        structure += 4.0 if trend in {"bullish", "bearish"} else (2.0 if trend == "ranging" else 0.0)
        structure += min(3.0, (len(getattr(market_structure, "swing_highs", ())) + len(getattr(market_structure, "swing_lows", ()))) * 0.5)

        swept = bool(getattr(market_structure, "liquidity_sweep_detected", False))
        liquidity = 3.0 + (9.0 if swept else 0.0)
        liquidity += 3.0 if "liquidity_sweep" in _value(getattr(setup_plan, "setup_type", "")) else 0.0

        conditions = tuple(getattr(setup_plan, "entry_conditions", ()) or ())
        required = [item for item in conditions if _value(getattr(item, "importance", "")) == "required"]
        met = sum(bool(getattr(item, "is_met", False)) for item in required)
        confirmation = 4.0 if not required else 15.0 * met / len(required)
        if _value(getattr(setup_plan, "setup_status", "")) == "confirmed":
            confirmation = max(confirmation, 13.0)

        alignment = _value(getattr(multi_timeframe, "alignment", "unclear"))
        alignment_score = float(getattr(multi_timeframe, "alignment_score", 0.0) or 0.0)
        higher = min(15.0, max(0.0, alignment_score * 0.15))
        if alignment == "conflicting":
            higher = min(higher, 3.0)

        ratio = getattr(setup_plan, "estimated_risk_reward", None)
        risk_reward = 2.0 if ratio is None else min(10.0, max(0.0, float(ratio) / 2.5 * 10.0))
        level_quality = _value(getattr(getattr(setup_plan, "setup_level_diagnostics", None), "level_quality", "missing"))
        if level_quality != "complete":
            risk_reward *= {"partial": 0.7, "invalid": 0.25}.get(level_quality, 0.4)

        direction = _value(getattr(setup_plan, "direction", "neutral"))
        bias = _value(getattr(multi_timeframe, "directional_bias", "unclear"))
        direction_matches = (direction == "bullish" and bias == "bullish") or (direction == "bearish" and bias == "bearish")
        trend_alignment = 9.0 if direction_matches else (5.0 if alignment == "mixed" else 2.0)

        candle_list = tuple(candles)
        volatility = _volatility_score(candle_list, phase, market_regime)
        freshness = 5.0 if swept else (4.0 if any("bos" in item for item in events) else 2.0)
        if len([item for item in events if "sweep" in item or "bos" in item]) > 3:
            freshness = max(1.0, freshness - 1.0)

        components = SetupQualityComponents(
            market_structure=round(min(20.0, structure), 2),
            liquidity=round(min(15.0, liquidity), 2),
            confirmation=round(min(15.0, confirmation), 2),
            higher_timeframe=round(min(15.0, higher), 2),
            risk_reward=round(min(10.0, risk_reward), 2),
            trend_alignment=round(min(10.0, trend_alignment), 2),
            volatility=round(min(10.0, volatility), 2),
            freshness=round(min(5.0, freshness), 2),
        )
        total = round(max(0.0, min(100.0, sum(vars(components).values()))), 2)
        strongest = max(vars(components), key=vars(components).get)
        weakest = min(vars(components), key=vars(components).get)
        return SetupQualityResult(
            score=total,
            grade=grade_for_score(total),
            components=components,
            human_readable_summary=(
                f"Setup quality is {grade_for_score(total)} ({total:.1f}/100); "
                f"{strongest.replace('_', ' ')} is strongest while "
                f"{weakest.replace('_', ' ')} limits the evidence."
            ),
        )

    def summarize(self, trades: Iterable[Any]) -> SetupQualitySummary:
        records = tuple(trades)
        scored = tuple(item for item in records if getattr(item, "setup_quality", None) is not None)
        closed = tuple(item for item in scored if getattr(item, "realized_r", None) is not None)
        qualities = [float(item.setup_quality.score) for item in scored]
        correlations = _correlations(closed)
        by_setup = _groups(scored, lambda item: getattr(item, "setup_type", "unknown"))
        recommendations = _recommendations(scored, closed, correlations)
        return SetupQualitySummary(
            average_quality_score=round(mean(qualities), 3) if qualities else 0.0,
            highest_quality_trade=max((item.setup_quality for item in scored), key=lambda item: item.score, default=None),
            lowest_quality_trade=min((item.setup_quality for item in scored), key=lambda item: item.score, default=None),
            average_quality_by_symbol=_groups(scored, lambda item: getattr(item, "symbol", "unknown")),
            average_quality_by_strategy=_groups(scored, lambda item: getattr(item, "strategy_type", "unknown")),
            average_quality_by_setup=by_setup,
            average_quality_by_regime=_groups(scored, lambda item: _value(getattr(getattr(item, "market_regime", None), "market_regime", "unknown"))),
            quality_distribution=_quality_distribution(qualities),
            grade_distribution=dict(Counter(item.setup_quality.grade for item in scored)),
            correlations=correlations,
            recommendations=recommendations,
            total_records=len(scored),
            completed_trades=len(closed),
            human_readable_summary=(
                f"{len(scored)} setup records averaged {mean(qualities):.1f}/100 across {len(closed)} completed trades."
                if scored else "Setup quality is unavailable because no setup records were analyzed."
            ),
        )


def _volatility_score(candles, phase: str, regime: Any) -> float:
    regime_name = _value(getattr(regime, "market_regime", "unknown"))
    base = 8.0 if regime_name in {"expansion", "high_volatility"} or phase == "impulse" else 5.0
    if regime_name in {"compression", "low_volatility"}:
        base = 6.0
    if len(candles) >= 6:
        recent = mean(max(0.0, item.high - item.low) for item in candles[-3:])
        prior = mean(max(0.0, item.high - item.low) for item in candles[-6:-3])
        if prior > 0:
            base += max(-2.0, min(2.0, (recent / prior - 1.0) * 4.0))
    return max(0.0, min(10.0, base))


def _groups(records, key_fn) -> tuple[SetupQualityGroup, ...]:
    grouped: dict[str, list[Any]] = defaultdict(list)
    for item in records:
        grouped[str(key_fn(item))].append(item)
    raw = []
    for name, items in grouped.items():
        returns = [float(item.realized_r) for item in items if getattr(item, "realized_r", None) is not None]
        wins = sum(value > 0 for value in returns)
        positives = sum(value for value in returns if value > 0)
        negatives = abs(sum(value for value in returns if value < 0))
        avg_quality = mean(item.setup_quality.score for item in items)
        raw.append(SetupQualityGroup(name, len(items), round(avg_quality, 3), grade_for_score(avg_quality), wins, round(wins / len(returns) * 100, 3) if returns else 0.0, round(mean(returns), 4) if returns else 0.0, round(mean(returns), 4) if returns else 0.0, round(positives / negatives, 4) if negatives else None, _max_drawdown(returns)))
    raw.sort(key=lambda item: (item.average_quality, item.records), reverse=True)
    return tuple(SetupQualityGroup(**{**vars(item), "quality_rank": rank}) for rank, item in enumerate(raw, 1))


def _correlations(trades) -> tuple[SetupQualityCorrelation, ...]:
    metrics = {
        "win_rate": [1.0 if float(item.realized_r) > 0 else 0.0 for item in trades],
        "average_r": [float(item.realized_r) for item in trades],
        "profit_factor": [max(0.0, float(item.realized_r)) for item in trades],
        "drawdown": [min(0.0, float(item.realized_r)) for item in trades],
        "trade_duration": [float(getattr(getattr(item, "outcome_diagnostics", None), "bars_to_outcome", 0) or 0) for item in trades],
        "confidence_score": [float(getattr(getattr(item, "decision_diagnostics", None), "final_confidence", 0) or 0) for item in trades],
        "trade_quality_score": [float(getattr(getattr(item, "score_summary", None), "trade_quality_score", 0) or 0) for item in trades],
    }
    x = [float(item.setup_quality.score) for item in trades]
    return tuple(SetupQualityCorrelation(name, (value := _pearson(x, values)), len(x), _correlation_text(value)) for name, values in metrics.items())


def _pearson(x, y) -> float | None:
    if len(x) < 3 or len(x) != len(y):
        return None
    mx, my = mean(x), mean(y)
    numerator = sum((a - mx) * (b - my) for a, b in zip(x, y))
    dx = sqrt(sum((a - mx) ** 2 for a in x)); dy = sqrt(sum((b - my) ** 2 for b in y))
    return round(numerator / (dx * dy), 4) if dx and dy else None


def _correlation_text(value) -> str:
    if value is None:
        return "Insufficient variation or sample size."
    strength = "strong" if abs(value) >= 0.6 else "moderate" if abs(value) >= 0.3 else "weak"
    return f"{strength.capitalize()} {'positive' if value >= 0 else 'negative'} relationship."


def _recommendations(records, closed, correlations) -> tuple[str, ...]:
    if len(closed) < 20:
        return ("Quality relationships are under-tested; collect at least 20 completed trades before drawing conclusions.",)
    high = [float(item.realized_r) for item in closed if item.setup_quality.score >= 90]
    low = [float(item.realized_r) for item in closed if item.setup_quality.score < 70]
    output = []
    if high: output.append(f"Trades scoring above 90 averaged {mean(high):.2f}R.")
    if low: output.append(f"Trades below 70 averaged {mean(low):.2f}R.")
    r_corr = next((item for item in correlations if item.metric == "average_r"), None)
    c_corr = next((item for item in correlations if item.metric == "confidence_score"), None)
    if r_corr and r_corr.coefficient is not None and abs(r_corr.coefficient) >= 0.3:
        output.append(f"Quality score has a {r_corr.interpretation.lower()} with expectancy.")
    elif c_corr and c_corr.coefficient is not None:
        output.append("No statistically significant quality-to-expectancy relationship is evident yet.")
    return tuple(output) or ("No statistically significant relationship detected.",)


def _quality_distribution(values) -> dict[str, int]:
    return {
        "0-64": sum(value < 65 for value in values), "65-69": sum(65 <= value < 70 for value in values),
        "70-74": sum(70 <= value < 75 for value in values), "75-79": sum(75 <= value < 80 for value in values),
        "80-84": sum(80 <= value < 85 for value in values), "85-89": sum(85 <= value < 90 for value in values),
        "90-94": sum(90 <= value < 95 for value in values), "95-100": sum(value >= 95 for value in values),
    }


def _max_drawdown(values) -> float:
    equity = peak = worst = 0.0
    for value in values:
        equity += value; peak = max(peak, equity); worst = max(worst, peak - equity)
    return round(worst, 4)


def _value(value: Any) -> str:
    return str(getattr(value, "value", value))
