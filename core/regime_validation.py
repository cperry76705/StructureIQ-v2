"""Proxy validation of regime balance, persistence, and forward behavior."""

from collections import Counter, defaultdict
from dataclasses import dataclass
from statistics import median
from typing import Literal

from core.market_data import Candle
from core.regime import MarketRegime


ProxyActualRegime = Literal[
    "actual_bullish",
    "actual_bearish",
    "actual_range",
    "actual_expansion",
    "actual_compression",
    "actual_unclear",
]
FORWARD_HORIZONS = (5, 10, 20)
TRANSITION_OVERUSE_THRESHOLD = 0.60


@dataclass(frozen=True)
class ForwardHorizonObservation:
    horizon: int
    forward_return: float
    bullish_follow_through: bool
    bearish_follow_through: bool
    range_behavior: bool
    expansion: bool
    compression: bool
    proxy_actual_regime: ProxyActualRegime


@dataclass(frozen=True)
class RegimeForwardObservation:
    horizons: tuple[ForwardHorizonObservation, ...]


@dataclass(frozen=True)
class ClassificationDistributionItem:
    market_regime: MarketRegime
    records: int
    percentage_of_total: float
    executed_trades: int
    average_confidence: float


@dataclass(frozen=True)
class RegimePersistence:
    market_regime: MarketRegime
    occurrences: int
    average_duration_bars: float
    max_duration_bars: int
    median_duration_bars: float


@dataclass(frozen=True)
class ForwardHorizonSummary:
    horizon: int
    samples: int
    average_forward_return: float
    median_forward_return: float
    bullish_follow_through_rate: float
    bearish_follow_through_rate: float
    range_behavior_rate: float
    expansion_rate: float
    compression_rate: float


@dataclass(frozen=True)
class ForwardBehaviorByRegime:
    market_regime: MarketRegime
    horizons: tuple[ForwardHorizonSummary, ...]


@dataclass(frozen=True)
class TransitionExitAnalysis:
    transition_records: int
    transitions_to_bullish: int
    transitions_to_bearish: int
    transitions_to_range: int
    transitions_to_compression: int
    transitions_to_expansion: int
    remained_transition: int
    average_bars_to_exit_transition: float


@dataclass(frozen=True)
class RegimeConfusionProxy:
    predicted_vs_actual: dict[str, dict[str, int]]
    total_compared: int
    insufficient_forward_records: int


@dataclass(frozen=True)
class RegimeValidationSummary:
    total_records: int
    classification_distribution: tuple[ClassificationDistributionItem, ...]
    transition_dominance_ratio: float
    transition_is_overused: bool
    average_regime_confidence: float
    confidence_by_regime: dict[str, float]
    persistence_by_regime: tuple[RegimePersistence, ...]
    forward_behavior_by_regime: tuple[ForwardBehaviorByRegime, ...]
    transition_exit_analysis: TransitionExitAnalysis
    regime_confusion_proxy: RegimeConfusionProxy
    dominant_failure_modes: tuple[str, ...]
    human_readable_summary: str
    recommendations: tuple[str, ...]


def build_forward_observation(
    *, start_price: float | None, future_candles: list[Candle]
) -> RegimeForwardObservation | None:
    if start_price is None or start_price == 0:
        return None
    observations: list[ForwardHorizonObservation] = []
    for horizon in FORWARD_HORIZONS:
        if len(future_candles) < horizon:
            continue
        candles = future_candles[:horizon]
        final_return = (candles[-1].close - start_price) / abs(start_price)
        ranges = [max(0.0, candle.high - candle.low) for candle in candles]
        average_range = sum(ranges) / len(ranges)
        directional_threshold = max(average_range / abs(start_price), 0.001)
        split = max(1, horizon // 2)
        early = sum(ranges[:split]) / len(ranges[:split])
        late = sum(ranges[split:]) / len(ranges[split:]) if ranges[split:] else early
        expansion = early > 0 and late >= early * 1.5
        compression = early > 0 and late <= early * 0.65
        path_width = max(candle.high for candle in candles) - min(
            candle.low for candle in candles
        )
        range_behavior = (
            abs(final_return) < directional_threshold
            and path_width <= max(average_range * 3.0, abs(start_price) * 0.002)
        )
        proxy = _proxy_actual(
            final_return=final_return,
            threshold=directional_threshold,
            range_behavior=range_behavior,
            expansion=expansion,
            compression=compression,
        )
        observations.append(
            ForwardHorizonObservation(
                horizon=horizon,
                forward_return=round(final_return, 8),
                bullish_follow_through=final_return >= directional_threshold,
                bearish_follow_through=final_return <= -directional_threshold,
                range_behavior=range_behavior,
                expansion=expansion,
                compression=compression,
                proxy_actual_regime=proxy,
            )
        )
    return RegimeForwardObservation(tuple(observations))


def build_regime_validation_summary(records: list[object]) -> RegimeValidationSummary:
    classified = [record for record in records if getattr(record, "market_regime", None)]
    total = len(classified)
    distribution = _classification_distribution(classified)
    transition_records = next(
        (item.records for item in distribution if item.market_regime is MarketRegime.TRANSITION),
        0,
    )
    dominance = round(transition_records / total, 6) if total else 0.0
    confidence_values = [record.market_regime.regime_confidence for record in classified]
    average_confidence = (
        round(sum(confidence_values) / len(confidence_values), 3)
        if confidence_values else 0.0
    )
    confidence_by_regime = {
        item.market_regime.value: item.average_confidence for item in distribution
    }
    persistence = _persistence(classified)
    forward = _forward_behavior(classified)
    exits = _transition_exits(classified)
    confusion = _confusion_proxy(classified)
    failures = _failure_modes(
        total=total,
        distribution=distribution,
        dominance=dominance,
        average_confidence=average_confidence,
        persistence=persistence,
        confusion=confusion,
    )
    recommendations = _recommendations(failures)
    return RegimeValidationSummary(
        total_records=total,
        classification_distribution=distribution,
        transition_dominance_ratio=dominance,
        transition_is_overused=dominance > TRANSITION_OVERUSE_THRESHOLD,
        average_regime_confidence=average_confidence,
        confidence_by_regime=confidence_by_regime,
        persistence_by_regime=persistence,
        forward_behavior_by_regime=forward,
        transition_exit_analysis=exits,
        regime_confusion_proxy=confusion,
        dominant_failure_modes=failures,
        human_readable_summary=(
            f"Validated {total} classified records; transition represents "
            f"{dominance:.1%} of labels and is "
            f"{'overused' if dominance > TRANSITION_OVERUSE_THRESHOLD else 'within the documented 60% limit'}."
        ),
        recommendations=recommendations,
    )


def _classification_distribution(
    records: list[object],
) -> tuple[ClassificationDistributionItem, ...]:
    total = len(records)
    items: list[ClassificationDistributionItem] = []
    for regime in MarketRegime:
        group = [record for record in records if record.market_regime.market_regime is regime]
        confidence = [record.market_regime.regime_confidence for record in group]
        items.append(
            ClassificationDistributionItem(
                market_regime=regime,
                records=len(group),
                percentage_of_total=(round(100.0 * len(group) / total, 3) if total else 0.0),
                executed_trades=sum(_is_closed(record) for record in group),
                average_confidence=(round(sum(confidence) / len(confidence), 3) if confidence else 0.0),
            )
        )
    return tuple(items)


def _persistence(records: list[object]) -> tuple[RegimePersistence, ...]:
    durations: dict[MarketRegime, list[int]] = defaultdict(list)
    for group in _sequence_groups(records).values():
        current: MarketRegime | None = None
        length = 0
        for record in group:
            regime = record.market_regime.market_regime
            if regime is current:
                length += 1
            else:
                if current is not None:
                    durations[current].append(length)
                current, length = regime, 1
        if current is not None:
            durations[current].append(length)
    return tuple(
        RegimePersistence(
            market_regime=regime,
            occurrences=len(durations.get(regime, [])),
            average_duration_bars=(round(sum(durations[regime]) / len(durations[regime]), 3) if durations.get(regime) else 0.0),
            max_duration_bars=max(durations.get(regime, [0])),
            median_duration_bars=(round(float(median(durations[regime])), 3) if durations.get(regime) else 0.0),
        )
        for regime in MarketRegime
    )


def _forward_behavior(records: list[object]) -> tuple[ForwardBehaviorByRegime, ...]:
    results: list[ForwardBehaviorByRegime] = []
    for regime in MarketRegime:
        observations = [
            observation
            for record in records
            if record.market_regime.market_regime is regime
            and (snapshot := getattr(record, "regime_forward_observation", None)) is not None
            for observation in snapshot.horizons
        ]
        horizons: list[ForwardHorizonSummary] = []
        for horizon in FORWARD_HORIZONS:
            group = [item for item in observations if item.horizon == horizon]
            returns = [item.forward_return for item in group]
            count = len(group)
            horizons.append(
                ForwardHorizonSummary(
                    horizon=horizon,
                    samples=count,
                    average_forward_return=(round(sum(returns) / count, 8) if count else 0.0),
                    median_forward_return=(round(float(median(returns)), 8) if returns else 0.0),
                    bullish_follow_through_rate=_rate(group, "bullish_follow_through"),
                    bearish_follow_through_rate=_rate(group, "bearish_follow_through"),
                    range_behavior_rate=_rate(group, "range_behavior"),
                    expansion_rate=_rate(group, "expansion"),
                    compression_rate=_rate(group, "compression"),
                )
            )
        results.append(ForwardBehaviorByRegime(regime, tuple(horizons)))
    return tuple(results)


def _transition_exits(records: list[object]) -> TransitionExitAnalysis:
    counts = Counter()
    bars: list[int] = []
    transitions = 0
    for group in _sequence_groups(records).values():
        for index, record in enumerate(group):
            if record.market_regime.market_regime is not MarketRegime.TRANSITION:
                continue
            transitions += 1
            destination = None
            for future_index in range(index + 1, len(group)):
                future = group[future_index].market_regime.market_regime
                if future is not MarketRegime.TRANSITION:
                    destination = future
                    bars.append(future_index - index)
                    break
            bucket = _exit_bucket(destination)
            counts[bucket] += 1
    return TransitionExitAnalysis(
        transition_records=transitions,
        transitions_to_bullish=counts["bullish"],
        transitions_to_bearish=counts["bearish"],
        transitions_to_range=counts["range"],
        transitions_to_compression=counts["compression"],
        transitions_to_expansion=counts["expansion"],
        remained_transition=counts["remained"],
        average_bars_to_exit_transition=(round(sum(bars) / len(bars), 3) if bars else 0.0),
    )


def _confusion_proxy(records: list[object]) -> RegimeConfusionProxy:
    matrix: dict[str, Counter[str]] = defaultdict(Counter)
    compared = 0
    insufficient = 0
    for record in records:
        snapshot = getattr(record, "regime_forward_observation", None)
        if snapshot is None or not snapshot.horizons:
            insufficient += 1
            continue
        preferred = next((item for item in snapshot.horizons if item.horizon == 20), snapshot.horizons[-1])
        matrix[record.market_regime.market_regime.value][preferred.proxy_actual_regime] += 1
        compared += 1
    return RegimeConfusionProxy(
        predicted_vs_actual={key: dict(sorted(value.items())) for key, value in sorted(matrix.items())},
        total_compared=compared,
        insufficient_forward_records=insufficient,
    )


def _failure_modes(
    *,
    total: int,
    distribution: tuple[ClassificationDistributionItem, ...],
    dominance: float,
    average_confidence: float,
    persistence: tuple[RegimePersistence, ...],
    confusion: RegimeConfusionProxy,
) -> tuple[str, ...]:
    failures: list[str] = []
    if dominance > TRANSITION_OVERUSE_THRESHOLD:
        failures.append("transition_overuse")
    trend_records = sum(
        item.records for item in distribution
        if item.market_regime in {
            MarketRegime.STRONG_BULL_TREND,
            MarketRegime.WEAK_BULL_TREND,
            MarketRegime.STRONG_BEAR_TREND,
            MarketRegime.WEAK_BEAR_TREND,
        }
    )
    if total >= 20 and trend_records / total < 0.1:
        failures.append("trend_underclassification")
    if total and average_confidence < 50:
        failures.append("low_confidence_clustering")
    active_durations = [item.average_duration_bars for item in persistence if item.occurrences]
    if total >= 20 and active_durations and sum(active_durations) / len(active_durations) < 2:
        failures.append("regime_short_duration_noise")
    mismatch, directional = _directional_mismatch(confusion.predicted_vs_actual)
    if directional >= 5 and mismatch / directional >= 0.4:
        failures.append("forward_behavior_mismatch")
    if confusion.total_compared < max(5, int(total * 0.1)):
        failures.append("insufficient_samples")
    return tuple(failures)


def _recommendations(failures: tuple[str, ...]) -> tuple[str, ...]:
    mapping = {
        "transition_overuse": "Inspect CHOCH recency and timeframe-conflict handling; transition exceeds the documented 60% balance threshold.",
        "trend_underclassification": "Review strong/weak trend evidence thresholds and whether stale transition evidence masks valid directional structure.",
        "low_confidence_clustering": "Inspect confidence contributions before changing classification thresholds.",
        "regime_short_duration_noise": "Review persistence smoothing or event recency because labels change too frequently.",
        "forward_behavior_mismatch": "Compare predicted regimes with forward proxy buckets and inspect trend, range, and transition rules with the largest mismatch.",
        "insufficient_samples": "Collect longer forward windows or more historical records before interpreting predictive behavior.",
    }
    messages = [mapping[item] for item in failures]
    if not messages:
        messages.append("No dominant validation failure cleared the documented diagnostic thresholds.")
    messages.append("Forward behavior is a deterministic proxy, not labeled regime ground truth.")
    return tuple(messages)


def _proxy_actual(
    *,
    final_return: float,
    threshold: float,
    range_behavior: bool,
    expansion: bool,
    compression: bool,
) -> ProxyActualRegime:
    if compression:
        return "actual_compression"
    if expansion:
        return "actual_expansion"
    if final_return >= threshold:
        return "actual_bullish"
    if final_return <= -threshold:
        return "actual_bearish"
    if range_behavior:
        return "actual_range"
    return "actual_unclear"


def _sequence_groups(records: list[object]) -> dict[tuple[str, str, str], list[object]]:
    groups: dict[tuple[str, str, str], list[object]] = defaultdict(list)
    for record in records:
        groups[
            (
                record.symbol,
                getattr(record, "timeframe", None) or "unknown",
                getattr(record, "higher_timeframe", None) or "unknown",
            )
        ].append(record)
    for group in groups.values():
        group.sort(key=lambda record: record.timestamp)
    return groups


def _exit_bucket(regime: MarketRegime | None) -> str:
    if regime in {MarketRegime.STRONG_BULL_TREND, MarketRegime.WEAK_BULL_TREND}:
        return "bullish"
    if regime in {MarketRegime.STRONG_BEAR_TREND, MarketRegime.WEAK_BEAR_TREND}:
        return "bearish"
    if regime is MarketRegime.RANGE:
        return "range"
    if regime is MarketRegime.COMPRESSION:
        return "compression"
    if regime is MarketRegime.EXPANSION:
        return "expansion"
    return "remained"


def _rate(items: list[object], attribute: str) -> float:
    return round(100.0 * sum(bool(getattr(item, attribute)) for item in items) / len(items), 3) if items else 0.0


def _is_closed(record: object) -> bool:
    outcome = getattr(getattr(record, "outcome", None), "value", getattr(record, "outcome", None))
    return outcome in {"win", "loss", "breakeven"}


def _directional_mismatch(matrix: dict[str, dict[str, int]]) -> tuple[int, int]:
    mismatch = 0
    total = 0
    for predicted, actuals in matrix.items():
        if "bull" in predicted:
            mismatch += actuals.get("actual_bearish", 0)
            total += actuals.get("actual_bullish", 0) + actuals.get("actual_bearish", 0)
        elif "bear" in predicted:
            mismatch += actuals.get("actual_bullish", 0)
            total += actuals.get("actual_bullish", 0) + actuals.get("actual_bearish", 0)
    return mismatch, total
