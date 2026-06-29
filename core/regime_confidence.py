"""Research-only calibration diagnostics for market-regime confidence scores."""

from collections import defaultdict
from dataclasses import dataclass
from math import exp, log
from statistics import mean, median, pstdev

from core.regime_forward_validation import is_forward_prediction_correct


PUBLIC_CONFIDENCE_BANDS = ((50, 59), (60, 69), (70, 79), (80, 89), (90, 100))
ALL_CONFIDENCE_BANDS = ((0, 49), *PUBLIC_CONFIDENCE_BANDS)
MAPPING_NAMES = (
    "identity",
    "linear_compression",
    "temperature_scaling",
    "isotonic_approximation",
    "piecewise_calibration",
)


@dataclass(frozen=True)
class ConfidenceReliabilityBucket:
    confidence_band: str
    sample_size: int
    average_confidence: float
    observed_accuracy: float
    calibration_gap: float


@dataclass(frozen=True)
class ReliabilityCurvePoint:
    confidence: float
    observed_accuracy: float
    sample_count: int


@dataclass(frozen=True)
class ConfidenceDistribution:
    histogram: dict[str, int]
    mean: float
    median: float
    standard_deviation: float
    percentiles: dict[str, float]


@dataclass(frozen=True)
class OverconfidenceAnalysis:
    systematic_overconfidence: bool
    systematic_underconfidence: bool
    well_calibrated: bool
    average_calibration_gap: float


@dataclass(frozen=True)
class ConfidenceMappingSimulation:
    mapping: str
    ece: float
    mce: float
    brier_score: float
    average_confidence: float
    classification_unchanged: bool
    expected_routing_unchanged: bool


@dataclass(frozen=True)
class RecommendedConfidenceMapping:
    best_mapping: str
    expected_ece_reduction: float
    expected_confidence_reduction: float
    expected_calibration_improvement: float
    research_confidence: str


@dataclass(frozen=True)
class ClassifierConfidenceCalibration:
    classifier: str
    sample_size: int
    reliability_buckets: tuple[ConfidenceReliabilityBucket, ...]
    ece: float
    mce: float
    brier_score: float
    reliability_curve: tuple[ReliabilityCurvePoint, ...]
    confidence_distribution: ConfidenceDistribution
    overconfidence_analysis: OverconfidenceAnalysis
    mapping_simulations: tuple[ConfidenceMappingSimulation, ...]
    recommended_mapping: RecommendedConfidenceMapping
    human_readable_summary: str


@dataclass(frozen=True)
class LegacyVsTunedConfidence:
    ece_improvement: float
    mce_improvement: float
    brier_improvement: float
    confidence_reduction: float
    overconfidence_reduction: float


@dataclass(frozen=True)
class RegimeConfidenceSummary:
    legacy: ClassifierConfidenceCalibration
    tuned: ClassifierConfidenceCalibration
    recommended_mapping: RecommendedConfidenceMapping
    legacy_vs_tuned_confidence: LegacyVsTunedConfidence
    human_readable_summary: str
    recommendations: tuple[str, ...]


@dataclass(frozen=True)
class _ConfidenceSample:
    confidence: float
    correct: bool


def build_regime_confidence_summary(records: list[object]) -> RegimeConfidenceSummary:
    """Calibrate both classifiers over one shared set of forward observations."""

    shared = [
        record
        for record in records
        if getattr(record, "market_regime", None) is not None
        and getattr(record, "tuned_market_regime", None) is not None
        and getattr(record, "regime_forward_validation_observation", None) is not None
    ]
    legacy = build_classifier_confidence_calibration(shared, classifier="legacy")
    tuned = build_classifier_confidence_calibration(shared, classifier="tuned")
    comparison = LegacyVsTunedConfidence(
        ece_improvement=round(legacy.ece - tuned.ece, 3),
        mce_improvement=round(legacy.mce - tuned.mce, 3),
        brier_improvement=round(legacy.brier_score - tuned.brier_score, 6),
        confidence_reduction=round(
            legacy.confidence_distribution.mean - tuned.confidence_distribution.mean,
            3,
        ),
        overconfidence_reduction=round(
            legacy.overconfidence_analysis.average_calibration_gap
            - tuned.overconfidence_analysis.average_calibration_gap,
            3,
        ),
    )
    recommendations = [
        "Keep every mapping research-only until it is validated on a separate out-of-sample period.",
        "Do not use calibrated confidence to change regime labels, routing, or trade selection.",
    ]
    if tuned.overconfidence_analysis.systematic_overconfidence:
        recommendations.insert(
            0,
            "Tuned confidence remains systematically overconfident relative to proxy accuracy.",
        )
    return RegimeConfidenceSummary(
        legacy=legacy,
        tuned=tuned,
        recommended_mapping=tuned.recommended_mapping,
        legacy_vs_tuned_confidence=comparison,
        human_readable_summary=(
            f"Legacy ECE is {legacy.ece:.2f} points and tuned ECE is "
            f"{tuned.ece:.2f} points across {tuned.sample_size} shared "
            "record-horizon predictions. No mapping was applied."
        ),
        recommendations=tuple(recommendations),
    )


def build_classifier_confidence_calibration(
    records: list[object], *, classifier: str
) -> ClassifierConfidenceCalibration:
    """Measure calibration and simulate mappings for one classifier."""

    result_attribute = "market_regime" if classifier == "legacy" else "tuned_market_regime"
    samples: list[_ConfidenceSample] = []
    for record in records:
        result = getattr(record, result_attribute, None)
        observation = getattr(record, "regime_forward_validation_observation", None)
        if result is None or observation is None:
            continue
        samples.extend(
            _ConfidenceSample(
                confidence=result.regime_confidence,
                correct=is_forward_prediction_correct(result.market_regime, forward),
            )
            for forward in observation.horizons
        )

    confidences = [sample.confidence for sample in samples]
    outcomes = [sample.correct for sample in samples]
    ece, mce, brier = _calibration_metrics(confidences, outcomes)
    reliability = _reliability_buckets(confidences, outcomes)
    distribution = _confidence_distribution(confidences)
    overconfidence = _overconfidence(confidences, outcomes)
    simulations = _mapping_simulations(confidences, outcomes)
    recommendation = _recommended_mapping(simulations, len(samples))
    return ClassifierConfidenceCalibration(
        classifier=classifier,
        sample_size=len(samples),
        reliability_buckets=reliability,
        ece=ece,
        mce=mce,
        brier_score=brier,
        reliability_curve=tuple(
            ReliabilityCurvePoint(
                confidence=item.average_confidence,
                observed_accuracy=item.observed_accuracy,
                sample_count=item.sample_size,
            )
            for item in reliability
            if item.sample_size
        ),
        confidence_distribution=distribution,
        overconfidence_analysis=overconfidence,
        mapping_simulations=simulations,
        recommended_mapping=recommendation,
        human_readable_summary=(
            f"{classifier.title()} confidence has {ece:.2f}-point ECE, "
            f"{mce:.2f}-point MCE, and {brier:.4f} Brier score across "
            f"{len(samples)} predictions."
        ),
    )


def _reliability_buckets(
    confidences: list[float], outcomes: list[bool]
) -> tuple[ConfidenceReliabilityBucket, ...]:
    buckets: list[ConfidenceReliabilityBucket] = []
    for lower, upper in PUBLIC_CONFIDENCE_BANDS:
        indices = [
            index
            for index, confidence in enumerate(confidences)
            if lower <= confidence <= upper
        ]
        average_confidence = mean(confidences[index] for index in indices) if indices else 0.0
        observed = 100.0 * mean(outcomes[index] for index in indices) if indices else 0.0
        buckets.append(
            ConfidenceReliabilityBucket(
                confidence_band=f"{lower}-{upper}",
                sample_size=len(indices),
                average_confidence=round(average_confidence, 3),
                observed_accuracy=round(observed, 3),
                calibration_gap=round(average_confidence - observed, 3),
            )
        )
    return tuple(buckets)


def _calibration_metrics(
    confidences: list[float], outcomes: list[bool]
) -> tuple[float, float, float]:
    if not confidences:
        return 0.0, 0.0, 0.0
    weighted_gap = 0.0
    maximum_gap = 0.0
    for lower, upper in ALL_CONFIDENCE_BANDS:
        indices = [
            index
            for index, confidence in enumerate(confidences)
            if lower <= confidence <= upper
        ]
        if not indices:
            continue
        predicted = mean(confidences[index] for index in indices)
        observed = 100.0 * mean(outcomes[index] for index in indices)
        gap = abs(predicted - observed)
        weighted_gap += len(indices) / len(confidences) * gap
        maximum_gap = max(maximum_gap, gap)
    brier = mean(
        ((confidence / 100.0) - (1.0 if outcome else 0.0)) ** 2
        for confidence, outcome in zip(confidences, outcomes)
    )
    return round(weighted_gap, 3), round(maximum_gap, 3), round(brier, 6)


def _confidence_distribution(confidences: list[float]) -> ConfidenceDistribution:
    histogram = {
        f"{lower}-{upper}": sum(lower <= value <= upper for value in confidences)
        for lower, upper in ALL_CONFIDENCE_BANDS
    }
    if not confidences:
        return ConfidenceDistribution(histogram, 0.0, 0.0, 0.0, {})
    ordered = sorted(confidences)
    return ConfidenceDistribution(
        histogram=histogram,
        mean=round(mean(confidences), 3),
        median=round(float(median(confidences)), 3),
        standard_deviation=round(pstdev(confidences), 3),
        percentiles={
            name: round(_percentile(ordered, percentile), 3)
            for name, percentile in (
                ("p10", 10),
                ("p25", 25),
                ("p50", 50),
                ("p75", 75),
                ("p90", 90),
            )
        },
    )


def _overconfidence(
    confidences: list[float], outcomes: list[bool]
) -> OverconfidenceAnalysis:
    if not confidences:
        return OverconfidenceAnalysis(False, False, False, 0.0)
    gap = mean(confidences) - 100.0 * mean(outcomes)
    return OverconfidenceAnalysis(
        systematic_overconfidence=gap > 5.0,
        systematic_underconfidence=gap < -5.0,
        well_calibrated=abs(gap) <= 5.0,
        average_calibration_gap=round(gap, 3),
    )


def _mapping_simulations(
    confidences: list[float], outcomes: list[bool]
) -> tuple[ConfidenceMappingSimulation, ...]:
    mapped = {
        "identity": list(confidences),
        "linear_compression": [value * 0.75 for value in confidences],
        "temperature_scaling": [_temperature_scale(value, 1.75) for value in confidences],
        "isotonic_approximation": _isotonic_mapping(confidences, outcomes),
        "piecewise_calibration": _piecewise_mapping(confidences, outcomes),
    }
    simulations: list[ConfidenceMappingSimulation] = []
    for name in MAPPING_NAMES:
        values = [round(max(0.0, min(100.0, value)), 6) for value in mapped[name]]
        ece, mce, brier = _calibration_metrics(values, outcomes)
        simulations.append(
            ConfidenceMappingSimulation(
                mapping=name,
                ece=ece,
                mce=mce,
                brier_score=brier,
                average_confidence=round(mean(values), 3) if values else 0.0,
                classification_unchanged=True,
                expected_routing_unchanged=True,
            )
        )
    return tuple(simulations)


def _recommended_mapping(
    simulations: tuple[ConfidenceMappingSimulation, ...], sample_size: int
) -> RecommendedConfidenceMapping:
    identity = next(item for item in simulations if item.mapping == "identity")
    best = min(simulations, key=lambda item: (item.ece, item.brier_score, item.mapping))
    research_confidence = "low" if sample_size < 30 else "moderate" if sample_size < 100 else "high"
    ece_reduction = identity.ece - best.ece
    return RecommendedConfidenceMapping(
        best_mapping=best.mapping,
        expected_ece_reduction=round(ece_reduction, 3),
        expected_confidence_reduction=round(
            identity.average_confidence - best.average_confidence, 3
        ),
        expected_calibration_improvement=round(ece_reduction, 3),
        research_confidence=research_confidence,
    )


def _temperature_scale(confidence: float, temperature: float) -> float:
    probability = max(0.001, min(0.999, confidence / 100.0))
    scaled = 1.0 / (1.0 + exp(-log(probability / (1.0 - probability)) / temperature))
    return scaled * 100.0


def _isotonic_mapping(
    confidences: list[float], outcomes: list[bool]
) -> list[float]:
    if not confidences:
        return []
    grouped: dict[float, list[bool]] = defaultdict(list)
    for confidence, outcome in zip(confidences, outcomes):
        grouped[confidence].append(outcome)
    blocks: list[dict[str, object]] = []
    for confidence in sorted(grouped):
        values = grouped[confidence]
        blocks.append(
            {
                "confidences": [confidence],
                "successes": float(sum(values)),
                "count": len(values),
            }
        )
        while len(blocks) >= 2 and _block_rate(blocks[-2]) > _block_rate(blocks[-1]):
            right = blocks.pop()
            left = blocks.pop()
            blocks.append(
                {
                    "confidences": left["confidences"] + right["confidences"],
                    "successes": left["successes"] + right["successes"],
                    "count": left["count"] + right["count"],
                }
            )
    mapping: dict[float, float] = {}
    for block in blocks:
        rate = 100.0 * _block_rate(block)
        for confidence in block["confidences"]:
            mapping[confidence] = rate
    return [mapping[value] for value in confidences]


def _block_rate(block: dict[str, object]) -> float:
    return float(block["successes"]) / int(block["count"])


def _piecewise_mapping(
    confidences: list[float], outcomes: list[bool]
) -> list[float]:
    observed_by_band: dict[tuple[int, int], float] = {}
    for lower, upper in ALL_CONFIDENCE_BANDS:
        values = [
            outcome
            for confidence, outcome in zip(confidences, outcomes)
            if lower <= confidence <= upper
        ]
        if values:
            observed_by_band[(lower, upper)] = 100.0 * mean(values)
    results: list[float] = []
    for confidence in confidences:
        band = next(
            (item for item in ALL_CONFIDENCE_BANDS if item[0] <= confidence <= item[1]),
            (90, 100),
        )
        observed = observed_by_band.get(band, confidence)
        results.append(confidence * 0.3 + observed * 0.7)
    return results


def _percentile(ordered: list[float], percentile: float) -> float:
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * percentile / 100.0
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction
