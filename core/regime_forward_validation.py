"""Proxy forward validation for legacy and tuned market-regime classifiers."""

from collections import defaultdict
from dataclasses import dataclass
from statistics import mean, median, pstdev

from core.market_data import Candle
from core.regime import MarketRegime, RegimeResult


FORWARD_HORIZONS = (5, 10, 20)
TREND_REGIMES = {
    MarketRegime.STRONG_BULL_TREND,
    MarketRegime.WEAK_BULL_TREND,
    MarketRegime.STRONG_BEAR_TREND,
    MarketRegime.WEAK_BEAR_TREND,
}


@dataclass(frozen=True)
class ForwardBehaviorHorizon:
    horizon: int
    directional_return: float
    maximum_upside_excursion: float
    maximum_downside_excursion: float
    directional_threshold: float
    volatility_expansion: bool
    volatility_compression: bool
    range_persistence: bool
    proxy_actual_regime: MarketRegime


@dataclass(frozen=True)
class RegimeForwardValidationObservation:
    horizons: tuple[ForwardBehaviorHorizon, ...]


@dataclass(frozen=True)
class ValidationMetric:
    value: float
    sample_size: int
    standard_deviation: float
    confidence_interval_low: float
    confidence_interval_high: float


@dataclass(frozen=True)
class ConfidenceReliabilityPoint:
    confidence_band: str
    sample_size: int
    average_prediction_confidence: float
    observed_accuracy: float
    calibration_gap: float


@dataclass(frozen=True)
class RegimePersistenceValidation:
    market_regime: MarketRegime
    sample_size: int
    persistence_rate: float


@dataclass(frozen=True)
class ForwardHorizonStatistics:
    horizon: int
    sample_size: int
    average_directional_return: float
    median_directional_return: float
    directional_return_standard_deviation: float
    directional_return_confidence_interval_low: float
    directional_return_confidence_interval_high: float
    average_maximum_favorable_excursion: float
    average_maximum_adverse_excursion: float
    continuation_probability: float
    reversal_probability: float
    volatility_expansion_rate: float
    range_persistence_rate: float
    trend_persistence_rate: float


@dataclass(frozen=True)
class ForwardValidationStatisticalSummary:
    record_count: int
    evaluated_predictions: int
    horizons: tuple[ForwardHorizonStatistics, ...]
    flags: tuple[str, ...]


@dataclass(frozen=True)
class RegimeForwardValidationResult:
    classifier: str
    overall_accuracy: ValidationMetric
    precision: ValidationMetric
    recall: ValidationMetric
    f1_score: ValidationMetric
    average_prediction_confidence: ValidationMetric
    direction_accuracy: ValidationMetric
    trend_accuracy: ValidationMetric
    range_accuracy: ValidationMetric
    transition_accuracy: ValidationMetric
    compression_accuracy: ValidationMetric
    expansion_accuracy: ValidationMetric
    confusion_matrix: dict[str, dict[str, int]]
    confidence_reliability_curve: tuple[ConfidenceReliabilityPoint, ...]
    regime_persistence_validation: tuple[RegimePersistenceValidation, ...]
    statistical_summary: ForwardValidationStatisticalSummary
    human_readable_summary: str
    recommendations: tuple[str, ...]


@dataclass(frozen=True)
class ForwardValidationComparison:
    shared_record_count: int
    shared_evaluation_count: int
    overall_accuracy_delta: float
    trend_accuracy_delta: float
    range_accuracy_delta: float
    transition_accuracy_delta: float
    compression_accuracy_delta: float
    expansion_accuracy_delta: float
    best_classifier: str
    confidence_delta: float
    human_readable_summary: str
    recommendations: tuple[str, ...]


@dataclass(frozen=True)
class _Evaluation:
    predicted: MarketRegime
    actual: MarketRegime
    confidence: float
    horizon: int
    correct: bool
    direction_correct: bool
    continuation: bool
    reversal: bool
    trend_persistence: bool
    directional_return: float
    maximum_favorable_excursion: float
    maximum_adverse_excursion: float
    volatility_expansion: bool
    range_persistence: bool


def build_forward_validation_observation(
    *, start_price: float | None, future_candles: list[Candle]
) -> RegimeForwardValidationObservation | None:
    """Capture raw forward behavior without exposing it through backtest output."""

    if start_price is None or start_price == 0:
        return None
    observations: list[ForwardBehaviorHorizon] = []
    for horizon in FORWARD_HORIZONS:
        if len(future_candles) < horizon:
            continue
        candles = future_candles[:horizon]
        ranges = [max(0.0, candle.high - candle.low) for candle in candles]
        average_range = mean(ranges)
        threshold = max(average_range / abs(start_price), 0.001)
        directional_return = (candles[-1].close - start_price) / abs(start_price)
        upside = (max(candle.high for candle in candles) - start_price) / abs(start_price)
        downside = (start_price - min(candle.low for candle in candles)) / abs(start_price)
        split = max(1, horizon // 2)
        early_range = mean(ranges[:split])
        late_range = mean(ranges[split:]) if ranges[split:] else early_range
        expansion = early_range > 0 and late_range >= early_range * 1.5
        compression = early_range > 0 and late_range <= early_range * 0.65
        path_width = max(candle.high for candle in candles) - min(
            candle.low for candle in candles
        )
        contained = (
            abs(directional_return) < threshold
            and path_width <= max(average_range * 3.0, abs(start_price) * 0.002)
        )
        actual = _proxy_actual_regime(
            directional_return=directional_return,
            threshold=threshold,
            expansion=expansion,
            compression=compression,
            contained=contained,
        )
        observations.append(
            ForwardBehaviorHorizon(
                horizon=horizon,
                directional_return=round(directional_return, 8),
                maximum_upside_excursion=round(max(0.0, upside), 8),
                maximum_downside_excursion=round(max(0.0, downside), 8),
                directional_threshold=round(threshold, 8),
                volatility_expansion=expansion,
                volatility_compression=compression,
                range_persistence=contained,
                proxy_actual_regime=actual,
            )
        )
    return RegimeForwardValidationObservation(tuple(observations))


def build_classifier_forward_validation(
    records: list[object], *, classifier: str
) -> RegimeForwardValidationResult:
    """Score one classifier against deterministic forward-behavior proxies."""

    result_attribute = "market_regime" if classifier == "legacy" else "tuned_market_regime"
    comparable = [
        record
        for record in records
        if getattr(record, result_attribute, None) is not None
        and getattr(record, "regime_forward_validation_observation", None) is not None
    ]
    evaluations: list[_Evaluation] = []
    for record in comparable:
        prediction: RegimeResult = getattr(record, result_attribute)
        observation = record.regime_forward_validation_observation
        evaluations.extend(
            _evaluate(prediction, horizon) for horizon in observation.horizons
        )

    confusion = _confusion_matrix(evaluations)
    accuracy_values = [1.0 if item.correct else 0.0 for item in evaluations]
    precision_value, recall_value, f1_value = _macro_classification_metrics(confusion)
    precision_samples = sum(sum(row.values()) for row in confusion.values())
    confidence_values = [item.confidence for item in evaluations]
    trend_evaluations = [item for item in evaluations if item.predicted in TREND_REGIMES]
    result = RegimeForwardValidationResult(
        classifier=classifier,
        overall_accuracy=_rate_metric(accuracy_values),
        precision=_scalar_metric(precision_value, precision_samples),
        recall=_scalar_metric(recall_value, precision_samples),
        f1_score=_scalar_metric(f1_value, precision_samples),
        average_prediction_confidence=_continuous_metric(confidence_values),
        direction_accuracy=_rate_metric(
            [1.0 if item.direction_correct else 0.0 for item in trend_evaluations]
        ),
        trend_accuracy=_accuracy_for(evaluations, TREND_REGIMES),
        range_accuracy=_accuracy_for(evaluations, {MarketRegime.RANGE}),
        transition_accuracy=_accuracy_for(evaluations, {MarketRegime.TRANSITION}),
        compression_accuracy=_accuracy_for(evaluations, {MarketRegime.COMPRESSION}),
        expansion_accuracy=_accuracy_for(evaluations, {MarketRegime.EXPANSION}),
        confusion_matrix=confusion,
        confidence_reliability_curve=_reliability_curve(evaluations),
        regime_persistence_validation=_persistence(evaluations),
        statistical_summary=_statistical_summary(comparable, evaluations),
        human_readable_summary=(
            f"{classifier.title()} classifier produced "
            f"{_percentage(accuracy_values):.1f}% proxy accuracy across "
            f"{len(evaluations)} forward evaluations from {len(comparable)} records."
        ),
        recommendations=_recommendations(classifier, comparable, evaluations),
    )
    return result


def build_forward_validation_comparison(
    legacy: RegimeForwardValidationResult,
    tuned: RegimeForwardValidationResult,
) -> ForwardValidationComparison:
    """Compare validation metrics without changing either classifier or trade data."""

    overall_delta = tuned.overall_accuracy.value - legacy.overall_accuracy.value
    trend_delta = tuned.trend_accuracy.value - legacy.trend_accuracy.value
    if overall_delta > 0.001:
        best = "tuned"
    elif overall_delta < -0.001:
        best = "legacy"
    else:
        best = "tie"
    recommendations: list[str] = []
    if best == "tuned":
        recommendations.append(
            "Tuned labels show higher proxy accuracy; confirm the improvement on "
            "an out-of-sample period before considering adoption."
        )
    elif best == "legacy":
        recommendations.append(
            "Legacy labels retain higher proxy accuracy; inspect tuned trend false "
            "positives before further promotion."
        )
    else:
        recommendations.append(
            "Neither classifier has a meaningful overall proxy-accuracy advantage in this sample."
        )
    if (
        legacy.statistical_summary.evaluated_predictions < 30
        or tuned.statistical_summary.evaluated_predictions < 30
    ):
        recommendations.append(
            "LOW_SAMPLE: collect at least 30 forward evaluations per classifier "
            "before relying on the comparison."
        )
    recommendations.append(
        "Forward regimes are deterministic proxies rather than labeled ground truth."
    )
    shared_evaluations = min(
        legacy.statistical_summary.evaluated_predictions,
        tuned.statistical_summary.evaluated_predictions,
    )
    return ForwardValidationComparison(
        shared_record_count=min(
            legacy.statistical_summary.record_count,
            tuned.statistical_summary.record_count,
        ),
        shared_evaluation_count=shared_evaluations,
        overall_accuracy_delta=round(overall_delta, 3),
        trend_accuracy_delta=round(trend_delta, 3),
        range_accuracy_delta=round(
            tuned.range_accuracy.value - legacy.range_accuracy.value, 3
        ),
        transition_accuracy_delta=round(
            tuned.transition_accuracy.value - legacy.transition_accuracy.value, 3
        ),
        compression_accuracy_delta=round(
            tuned.compression_accuracy.value - legacy.compression_accuracy.value, 3
        ),
        expansion_accuracy_delta=round(
            tuned.expansion_accuracy.value - legacy.expansion_accuracy.value, 3
        ),
        best_classifier=best,
        confidence_delta=round(
            tuned.average_prediction_confidence.value
            - legacy.average_prediction_confidence.value,
            3,
        ),
        human_readable_summary=(
            f"Tuned minus legacy proxy accuracy is {overall_delta:+.2f} percentage "
            f"points across {shared_evaluations} "
            f"shared evaluations; {best} is the stronger classifier in this sample."
        ),
        recommendations=tuple(recommendations),
    )


def build_matched_forward_validation(
    records: list[object],
) -> tuple[
    RegimeForwardValidationResult,
    RegimeForwardValidationResult,
    ForwardValidationComparison,
]:
    """Validate both classifiers over one explicitly shared record set."""

    shared = [
        record
        for record in records
        if getattr(record, "market_regime", None) is not None
        and getattr(record, "tuned_market_regime", None) is not None
        and getattr(record, "regime_forward_validation_observation", None) is not None
    ]
    legacy = build_classifier_forward_validation(shared, classifier="legacy")
    tuned = build_classifier_forward_validation(shared, classifier="tuned")
    return legacy, tuned, build_forward_validation_comparison(legacy, tuned)


def _evaluate(
    prediction: RegimeResult, forward: ForwardBehaviorHorizon
) -> _Evaluation:
    predicted = prediction.market_regime
    actual = forward.proxy_actual_regime
    bullish = predicted in {
        MarketRegime.STRONG_BULL_TREND,
        MarketRegime.WEAK_BULL_TREND,
    }
    bearish = predicted in {
        MarketRegime.STRONG_BEAR_TREND,
        MarketRegime.WEAK_BEAR_TREND,
    }
    oriented_return = (
        forward.directional_return if bullish
        else -forward.directional_return if bearish
        else forward.directional_return
    )
    favorable = (
        forward.maximum_upside_excursion if bullish
        else forward.maximum_downside_excursion if bearish
        else max(
            forward.maximum_upside_excursion,
            forward.maximum_downside_excursion,
        )
    )
    adverse = (
        forward.maximum_downside_excursion if bullish
        else forward.maximum_upside_excursion if bearish
        else min(
            forward.maximum_upside_excursion,
            forward.maximum_downside_excursion,
        )
    )
    direction_correct = (
        actual in {MarketRegime.STRONG_BULL_TREND, MarketRegime.WEAK_BULL_TREND}
        if bullish
        else actual in {MarketRegime.STRONG_BEAR_TREND, MarketRegime.WEAK_BEAR_TREND}
        if bearish
        else False
    )
    continuation = (
        oriented_return >= forward.directional_threshold
        if bullish or bearish
        else _is_correct(predicted, actual, forward)
    )
    reversal = (
        oriented_return <= -forward.directional_threshold if bullish or bearish else False
    )
    return _Evaluation(
        predicted=predicted,
        actual=actual,
        confidence=prediction.regime_confidence,
        horizon=forward.horizon,
        correct=_is_correct(predicted, actual, forward),
        direction_correct=direction_correct,
        continuation=continuation,
        reversal=reversal,
        trend_persistence=direction_correct,
        directional_return=oriented_return,
        maximum_favorable_excursion=favorable,
        maximum_adverse_excursion=adverse,
        volatility_expansion=forward.volatility_expansion,
        range_persistence=forward.range_persistence,
    )


def _proxy_actual_regime(
    *,
    directional_return: float,
    threshold: float,
    expansion: bool,
    compression: bool,
    contained: bool,
) -> MarketRegime:
    if contained:
        return MarketRegime.RANGE
    if expansion:
        return MarketRegime.EXPANSION
    if compression:
        return MarketRegime.COMPRESSION
    if directional_return >= threshold * 2:
        return MarketRegime.STRONG_BULL_TREND
    if directional_return >= threshold:
        return MarketRegime.WEAK_BULL_TREND
    if directional_return <= -threshold * 2:
        return MarketRegime.STRONG_BEAR_TREND
    if directional_return <= -threshold:
        return MarketRegime.WEAK_BEAR_TREND
    return MarketRegime.TRANSITION


def _is_correct(
    predicted: MarketRegime,
    actual: MarketRegime,
    forward: ForwardBehaviorHorizon,
) -> bool:
    if predicted is MarketRegime.COMPRESSION:
        return actual in {MarketRegime.COMPRESSION, MarketRegime.EXPANSION}
    if predicted is MarketRegime.EXPANSION:
        return actual in {
            MarketRegime.EXPANSION,
            MarketRegime.STRONG_BULL_TREND,
            MarketRegime.STRONG_BEAR_TREND,
        }
    if predicted is MarketRegime.HIGH_VOLATILITY:
        return forward.volatility_expansion or actual is MarketRegime.EXPANSION
    if predicted is MarketRegime.LOW_VOLATILITY:
        return actual in {MarketRegime.COMPRESSION, MarketRegime.RANGE}
    if predicted is MarketRegime.UNKNOWN:
        return actual is MarketRegime.TRANSITION
    if predicted in {
        MarketRegime.WEAK_BULL_TREND,
        MarketRegime.WEAK_BEAR_TREND,
    }:
        same_weak = actual is predicted
        same_strong = (
            predicted is MarketRegime.WEAK_BULL_TREND
            and actual is MarketRegime.STRONG_BULL_TREND
        ) or (
            predicted is MarketRegime.WEAK_BEAR_TREND
            and actual is MarketRegime.STRONG_BEAR_TREND
        )
        return same_weak or (
            same_strong
            and min(
                forward.maximum_upside_excursion,
                forward.maximum_downside_excursion,
            ) >= forward.directional_threshold * 0.5
        )
    return predicted is actual


def _confusion_matrix(evaluations: list[_Evaluation]) -> dict[str, dict[str, int]]:
    matrix: dict[str, dict[str, int]] = {
        predicted.value: {actual.value: 0 for actual in MarketRegime}
        for predicted in MarketRegime
    }
    for item in evaluations:
        matrix[item.predicted.value][item.actual.value] += 1
    return matrix


def _macro_classification_metrics(
    confusion: dict[str, dict[str, int]],
) -> tuple[float, float, float]:
    precisions: list[float] = []
    recalls: list[float] = []
    f1_values: list[float] = []
    for regime in MarketRegime:
        name = regime.value
        true_positive = confusion[name][name]
        predicted_total = sum(confusion[name].values())
        actual_total = sum(row[name] for row in confusion.values())
        if predicted_total == 0 and actual_total == 0:
            continue
        precision = true_positive / predicted_total if predicted_total else 0.0
        recall = true_positive / actual_total if actual_total else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision + recall else 0.0
        )
        precisions.append(precision)
        recalls.append(recall)
        f1_values.append(f1)
    return (
        100.0 * mean(precisions) if precisions else 0.0,
        100.0 * mean(recalls) if recalls else 0.0,
        100.0 * mean(f1_values) if f1_values else 0.0,
    )


def _accuracy_for(
    evaluations: list[_Evaluation], regimes: set[MarketRegime]
) -> ValidationMetric:
    selected = [item for item in evaluations if item.predicted in regimes]
    return _rate_metric([1.0 if item.correct else 0.0 for item in selected])


def _rate_metric(values: list[float]) -> ValidationMetric:
    if not values:
        return ValidationMetric(0.0, 0, 0.0, 0.0, 0.0)
    rate = mean(values)
    standard_error = (rate * (1.0 - rate) / len(values)) ** 0.5
    return ValidationMetric(
        value=round(rate * 100.0, 3),
        sample_size=len(values),
        standard_deviation=round(pstdev(values) * 100.0, 3),
        confidence_interval_low=round(max(0.0, rate - 1.96 * standard_error) * 100.0, 3),
        confidence_interval_high=round(min(1.0, rate + 1.96 * standard_error) * 100.0, 3),
    )


def _continuous_metric(values: list[float]) -> ValidationMetric:
    if not values:
        return ValidationMetric(0.0, 0, 0.0, 0.0, 0.0)
    average = mean(values)
    deviation = pstdev(values)
    margin = 1.96 * deviation / (len(values) ** 0.5)
    return ValidationMetric(
        round(average, 3),
        len(values),
        round(deviation, 3),
        round(average - margin, 3),
        round(average + margin, 3),
    )


def _scalar_metric(value: float, sample_size: int) -> ValidationMetric:
    return ValidationMetric(round(value, 3), sample_size, 0.0, round(value, 3), round(value, 3))


def _percentage(values: list[float]) -> float:
    return 100.0 * mean(values) if values else 0.0


def _reliability_curve(
    evaluations: list[_Evaluation],
) -> tuple[ConfidenceReliabilityPoint, ...]:
    bands = ((0, 49), (50, 59), (60, 69), (70, 79), (80, 89), (90, 100))
    points: list[ConfidenceReliabilityPoint] = []
    for lower, upper in bands:
        selected = [
            item for item in evaluations if lower <= item.confidence <= upper
        ]
        average_confidence = mean(item.confidence for item in selected) if selected else 0.0
        observed_accuracy = (
            _percentage([1.0 if item.correct else 0.0 for item in selected])
            if selected else 0.0
        )
        points.append(
            ConfidenceReliabilityPoint(
                confidence_band=f"{lower}-{upper}",
                sample_size=len(selected),
                average_prediction_confidence=round(average_confidence, 3),
                observed_accuracy=round(observed_accuracy, 3),
                calibration_gap=round(average_confidence - observed_accuracy, 3),
            )
        )
    return tuple(points)


def _persistence(
    evaluations: list[_Evaluation],
) -> tuple[RegimePersistenceValidation, ...]:
    grouped: dict[MarketRegime, list[_Evaluation]] = defaultdict(list)
    for item in evaluations:
        grouped[item.predicted].append(item)
    return tuple(
        RegimePersistenceValidation(
            market_regime=regime,
            sample_size=len(grouped[regime]),
            persistence_rate=round(
                _percentage(
                    [1.0 if item.correct else 0.0 for item in grouped[regime]]
                ),
                3,
            ),
        )
        for regime in MarketRegime
    )


def _statistical_summary(
    records: list[object], evaluations: list[_Evaluation]
) -> ForwardValidationStatisticalSummary:
    horizons: list[ForwardHorizonStatistics] = []
    for horizon in FORWARD_HORIZONS:
        selected = [item for item in evaluations if item.horizon == horizon]
        returns = [item.directional_return for item in selected]
        deviation = pstdev(returns) if returns else 0.0
        margin = 1.96 * deviation / (len(returns) ** 0.5) if returns else 0.0
        average_return = mean(returns) if returns else 0.0
        horizons.append(
            ForwardHorizonStatistics(
                horizon=horizon,
                sample_size=len(selected),
                average_directional_return=round(average_return, 8),
                median_directional_return=round(float(median(returns)), 8) if returns else 0.0,
                directional_return_standard_deviation=round(deviation, 8),
                directional_return_confidence_interval_low=round(average_return - margin, 8),
                directional_return_confidence_interval_high=round(average_return + margin, 8),
                average_maximum_favorable_excursion=round(
                    mean(item.maximum_favorable_excursion for item in selected), 8
                ) if selected else 0.0,
                average_maximum_adverse_excursion=round(
                    mean(item.maximum_adverse_excursion for item in selected), 8
                ) if selected else 0.0,
                continuation_probability=round(
                    _percentage([1.0 if item.continuation else 0.0 for item in selected]), 3
                ),
                reversal_probability=round(
                    _percentage([1.0 if item.reversal else 0.0 for item in selected]), 3
                ),
                volatility_expansion_rate=round(
                    _percentage([1.0 if item.volatility_expansion else 0.0 for item in selected]), 3
                ),
                range_persistence_rate=round(
                    _percentage([1.0 if item.range_persistence else 0.0 for item in selected]), 3
                ),
                trend_persistence_rate=round(
                    _percentage([1.0 if item.trend_persistence else 0.0 for item in selected]), 3
                ),
            )
        )
    flags: list[str] = []
    if len(evaluations) < 30:
        flags.append("LOW_SAMPLE")
    if evaluations and mean(item.confidence for item in evaluations) >= 80:
        flags.append("HIGH_CONFIDENCE")
    if not evaluations or any(item.sample_size == 0 for item in horizons):
        flags.append("INSUFFICIENT_DATA")
    return ForwardValidationStatisticalSummary(
        record_count=len(records),
        evaluated_predictions=len(evaluations),
        horizons=tuple(horizons),
        flags=tuple(flags),
    )


def _recommendations(
    classifier: str,
    records: list[object],
    evaluations: list[_Evaluation],
) -> tuple[str, ...]:
    messages: list[str] = []
    if len(evaluations) < 30:
        messages.append(
            "LOW_SAMPLE: collect more forward observations before comparing classifier quality."
        )
    if not evaluations:
        messages.append(
            "INSUFFICIENT_DATA: no complete 5/10/20-bar forward windows were available."
        )
    elif mean(item.confidence for item in evaluations) >= 80:
        messages.append(
            "HIGH_CONFIDENCE: compare confidence with observed accuracy for possible overconfidence."
        )
    messages.append(
        f"{classifier.title()} validation uses proxy forward behavior, not labeled "
        "market regimes or profitability evidence."
    )
    return tuple(messages)
