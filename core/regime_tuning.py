"""Research-only diagnostics and counterfactual tuning for regime classification."""

from collections import Counter
from dataclasses import dataclass
from statistics import median

from core.market_data import Candle
from core.market_structure import MarketStructureResult
from core.multi_timeframe import MultiTimeframeResult, TimeframeAlignment
from core.regime import MarketRegime, RegimeResult
from core.setup_engine import approximate_compression


TRANSITION_THRESHOLDS = (60, 65, 70, 75, 80)
TREND_REGIMES = {
    MarketRegime.STRONG_BULL_TREND,
    MarketRegime.WEAK_BULL_TREND,
    MarketRegime.STRONG_BEAR_TREND,
    MarketRegime.WEAK_BEAR_TREND,
}


@dataclass(frozen=True)
class RegimeEvidenceScores:
    trend_score: float
    range_score: float
    transition_score: float
    compression_score: float
    expansion_score: float


@dataclass(frozen=True)
class RegimeTuningEvidence:
    production_regime: MarketRegime
    confidence: float
    trend: str
    phase: str
    alignment: str
    alignment_score: int
    has_bos: bool
    recent_bos: bool
    has_choch: bool
    recent_choch: bool
    conflict: bool
    directional_swing_structure: bool
    scores: RegimeEvidenceScores
    transition_reasons: tuple[str, ...]


@dataclass(frozen=True)
class ClassificationMarginSummary:
    samples: int
    average_margin: float
    median_margin: float
    minimum_margin: float
    maximum_margin: float
    low_margin_count: int


@dataclass(frozen=True)
class ForwardStabilityResult:
    horizon: int
    samples: int
    stability_rate: float
    dominant_proxy_actual: str | None


@dataclass(frozen=True)
class TransitionThresholdSimulation:
    threshold: int
    regime_distribution: dict[str, int]
    transition_records: int
    transition_dominance_ratio: float
    expected_trend_classifications: int
    expected_transition_reduction: int


@dataclass(frozen=True)
class TrendEvidenceSimulation:
    simulation_name: str
    description: str
    regime_distribution: dict[str, int]
    expected_trend_classifications: int
    expected_transition_records: int
    expected_transition_reduction: int


@dataclass(frozen=True)
class RegimeTuningSummary:
    total_records: int
    current_regime_distribution: dict[str, int]
    transition_dominance_ratio: float
    transition_overuse_score: float
    trend_underclassification_score: float
    evidence_score_breakdown: RegimeEvidenceScores
    why_transition_won: dict[str, int]
    second_best_regime: str | None
    score_margin_between_winner_and_runner_up: float
    stale_transition_count: int
    transition_without_recent_choch: int
    transition_without_recent_bos: int
    transition_with_trend_structure: int
    transition_conflict_count: int
    confidence_by_regime: dict[str, float]
    confidence_histogram: dict[str, int]
    classification_margin_summary: ClassificationMarginSummary
    forward_stability: tuple[ForwardStabilityResult, ...]
    transition_threshold_simulation: tuple[TransitionThresholdSimulation, ...]
    trend_evidence_simulation: tuple[TrendEvidenceSimulation, ...]
    human_readable_summary: str
    recommendations: tuple[str, ...]


def build_regime_tuning_evidence(
    *,
    candles: list[Candle],
    market_structure: MarketStructureResult,
    multi_timeframe: MultiTimeframeResult,
    production_regime: RegimeResult,
) -> RegimeTuningEvidence:
    event_names = set(market_structure.structure_events)
    recent_cutoff = max(0, len(candles) - 6)
    recent_bos = any(
        event.type in {"bullish_bos", "bearish_bos"} and event.index >= recent_cutoff
        for event in market_structure.events
    )
    recent_choch = any(
        event.type in {"bullish_choch", "bearish_choch"} and event.index >= recent_cutoff
        for event in market_structure.events
    )
    has_bos = bool(event_names & {"bullish_bos", "bearish_bos"})
    has_choch = bool(event_names & {"bullish_choch", "bearish_choch"})
    conflict = multi_timeframe.alignment is TimeframeAlignment.CONFLICTING
    directional = market_structure.trend in {"bullish", "bearish"}
    range_ratio = _range_ratio(candles)
    scores = _scores(
        trend=market_structure.trend,
        phase=market_structure.phase,
        alignment=multi_timeframe.alignment,
        alignment_score=multi_timeframe.alignment_score,
        has_bos=has_bos,
        recent_bos=recent_bos,
        has_choch=has_choch,
        recent_choch=recent_choch,
        conflict=conflict,
        compression=approximate_compression(candles),
        range_ratio=range_ratio,
    )
    reasons: list[str] = []
    if recent_choch:
        reasons.append("recent_choch")
    elif has_choch:
        reasons.append("stale_choch")
    if market_structure.phase == "reversal_attempt":
        reasons.append("reversal_attempt_phase")
    if conflict:
        reasons.append("timeframe_conflict")
    if not reasons and production_regime.market_regime is MarketRegime.TRANSITION:
        reasons.append("transition_precedence_without_strong_recent_trigger")
    return RegimeTuningEvidence(
        production_regime=production_regime.market_regime,
        confidence=production_regime.regime_confidence,
        trend=market_structure.trend,
        phase=market_structure.phase,
        alignment=multi_timeframe.alignment.value,
        alignment_score=multi_timeframe.alignment_score,
        has_bos=has_bos,
        recent_bos=recent_bos,
        has_choch=has_choch,
        recent_choch=recent_choch,
        conflict=conflict,
        directional_swing_structure=directional,
        scores=scores,
        transition_reasons=tuple(reasons),
    )


def build_regime_tuning_summary(records: list[object]) -> RegimeTuningSummary:
    rows = [record for record in records if getattr(record, "regime_tuning_evidence", None)]
    total = len(rows)
    evidence = [record.regime_tuning_evidence for record in rows]
    distribution = Counter(item.production_regime.value for item in evidence)
    transitions = [item for item in evidence if item.production_regime is MarketRegime.TRANSITION]
    transition_count = len(transitions)
    dominance = transition_count / total if total else 0.0
    trend_count = sum(item.production_regime in TREND_REGIMES for item in evidence)
    directional_count = sum(item.directional_swing_structure for item in evidence)
    transition_overuse = max(0.0, (dominance - 0.60) / 0.40) if total else 0.0
    trend_under = (
        max(0.0, 1.0 - trend_count / directional_count)
        if directional_count else 0.0
    )
    score_average = _average_scores(evidence)
    transition_reasons = Counter(
        reason for item in transitions for reason in item.transition_reasons
    )
    margins, runners = _margins(evidence)
    runner = runners.most_common(1)[0][0] if runners else None
    confidence_by_regime = _confidence_by_regime(evidence)
    histogram = _confidence_histogram(evidence)
    margin_summary = _margin_summary(margins)
    stability = _forward_stability(rows)
    threshold_simulations = tuple(
        _threshold_simulation(evidence, threshold, transition_count)
        for threshold in TRANSITION_THRESHOLDS
    )
    trend_simulations = _trend_simulations(evidence, transition_count)
    stale = sum(
        item.production_regime is MarketRegime.TRANSITION
        and item.has_choch and not item.recent_choch and not item.conflict
        for item in evidence
    )
    summary = RegimeTuningSummary(
        total_records=total,
        current_regime_distribution=_complete_distribution(distribution),
        transition_dominance_ratio=round(dominance, 6),
        transition_overuse_score=round(min(1.0, transition_overuse), 6),
        trend_underclassification_score=round(min(1.0, trend_under), 6),
        evidence_score_breakdown=score_average,
        why_transition_won=dict(sorted(transition_reasons.items())),
        second_best_regime=runner,
        score_margin_between_winner_and_runner_up=(round(sum(margins) / len(margins), 3) if margins else 0.0),
        stale_transition_count=stale,
        transition_without_recent_choch=sum(not item.recent_choch for item in transitions),
        transition_without_recent_bos=sum(not item.recent_bos for item in transitions),
        transition_with_trend_structure=sum(item.directional_swing_structure for item in transitions),
        transition_conflict_count=sum(item.conflict for item in transitions),
        confidence_by_regime=confidence_by_regime,
        confidence_histogram=histogram,
        classification_margin_summary=margin_summary,
        forward_stability=stability,
        transition_threshold_simulation=threshold_simulations,
        trend_evidence_simulation=trend_simulations,
        human_readable_summary=(
            f"Tuning analysis inspected {total} records; transition represents "
            f"{dominance:.1%}, with {stale} stale-transition records and "
            f"{sum(item.directional_swing_structure for item in transitions)} "
            "transition labels despite directional swing structure."
        ),
        recommendations=_recommendations(
            dominance=dominance,
            stale=stale,
            directional=sum(item.directional_swing_structure for item in transitions),
            transition_count=transition_count,
            margins=margins,
        ),
    )
    return summary


def _scores(
    *,
    trend: str,
    phase: str,
    alignment: TimeframeAlignment,
    alignment_score: int,
    has_bos: bool,
    recent_bos: bool,
    has_choch: bool,
    recent_choch: bool,
    conflict: bool,
    compression: bool,
    range_ratio: float,
) -> RegimeEvidenceScores:
    trend_score = (
        (35 if trend in {"bullish", "bearish"} else 0)
        + (15 if phase == "impulse" else 5 if phase == "pullback" else 0)
        + (20 if recent_bos else 8 if has_bos else 0)
        + (18 if alignment in {TimeframeAlignment.ALIGNED_BULLISH, TimeframeAlignment.ALIGNED_BEARISH} else 8 if alignment is TimeframeAlignment.MIXED else 0)
        + (7 if alignment_score >= 70 else 0)
    )
    range_score = (55 if trend == "ranging" else 0) + (25 if phase == "range" else 0)
    transition_score = (
        (45 if recent_choch else 18 if has_choch else 0)
        + (30 if phase == "reversal_attempt" else 0)
        + (35 if conflict else 0)
        + (8 if alignment is TimeframeAlignment.MIXED else 0)
    )
    compression_score = 80 if compression else max(0.0, 40.0 * (1.0 - range_ratio))
    expansion_score = min(100.0, 50.0 * max(0.0, range_ratio - 1.0))
    return RegimeEvidenceScores(
        round(trend_score, 3),
        round(range_score, 3),
        round(transition_score, 3),
        round(compression_score, 3),
        round(expansion_score, 3),
    )


def _threshold_simulation(
    evidence: list[RegimeTuningEvidence], threshold: int, current_transitions: int
) -> TransitionThresholdSimulation:
    regimes = [_classify_scores(item, transition_threshold=threshold) for item in evidence]
    distribution = Counter(regime.value for regime in regimes)
    transition_records = distribution[MarketRegime.TRANSITION.value]
    return TransitionThresholdSimulation(
        threshold=threshold,
        regime_distribution=_complete_distribution(distribution),
        transition_records=transition_records,
        transition_dominance_ratio=(round(transition_records / len(evidence), 6) if evidence else 0.0),
        expected_trend_classifications=sum(regime in TREND_REGIMES for regime in regimes),
        expected_transition_reduction=current_transitions - transition_records,
    )


def _trend_simulations(
    evidence: list[RegimeTuningEvidence], current_transitions: int
) -> tuple[TrendEvidenceSimulation, ...]:
    definitions = (
        ("stronger_bos_weight", "Adds 20 points for recent BOS and 10 for existing BOS.", "bos", 20.0),
        ("stronger_choch_weight", "Treats CHOCH as stronger emerging-trend evidence when swing structure is directional.", "choch", 15.0),
        ("stronger_swing_structure_weight", "Adds 20 trend points for directional swing structure.", "swing", 20.0),
        ("stronger_higher_timeframe_alignment_weight", "Adds 20 trend points for aligned higher-timeframe context.", "alignment", 20.0),
    )
    results: list[TrendEvidenceSimulation] = []
    for name, description, kind, boost in definitions:
        regimes = [_classify_scores(item, transition_threshold=70, boost_kind=kind, boost=boost) for item in evidence]
        distribution = Counter(regime.value for regime in regimes)
        transition_records = distribution[MarketRegime.TRANSITION.value]
        results.append(
            TrendEvidenceSimulation(
                simulation_name=name,
                description=description,
                regime_distribution=_complete_distribution(distribution),
                expected_trend_classifications=sum(regime in TREND_REGIMES for regime in regimes),
                expected_transition_records=transition_records,
                expected_transition_reduction=current_transitions - transition_records,
            )
        )
    return tuple(results)


def _classify_scores(
    item: RegimeTuningEvidence,
    *,
    transition_threshold: float,
    boost_kind: str | None = None,
    boost: float = 0.0,
) -> MarketRegime:
    scores = {
        "trend": item.scores.trend_score,
        "range": item.scores.range_score,
        "transition": item.scores.transition_score,
        "compression": item.scores.compression_score,
        "expansion": item.scores.expansion_score,
    }
    if boost_kind == "bos" and item.has_bos:
        scores["trend"] += boost if item.recent_bos else boost / 2
    elif boost_kind == "choch" and item.has_choch and item.directional_swing_structure:
        scores["trend"] += boost if item.recent_choch else boost / 2
    elif boost_kind == "swing" and item.directional_swing_structure:
        scores["trend"] += boost
    elif boost_kind == "alignment" and item.alignment in {"aligned_bullish", "aligned_bearish"}:
        scores["trend"] += boost
    if scores["transition"] < transition_threshold:
        scores["transition"] = -1.0
    winner = max(scores, key=lambda key: (scores[key], key))
    if winner == "transition":
        return MarketRegime.TRANSITION
    if winner == "range":
        return MarketRegime.RANGE
    if winner == "compression":
        return MarketRegime.COMPRESSION
    if winner == "expansion":
        return MarketRegime.EXPANSION
    if item.trend == "bullish":
        return MarketRegime.STRONG_BULL_TREND if scores["trend"] >= 70 else MarketRegime.WEAK_BULL_TREND
    if item.trend == "bearish":
        return MarketRegime.STRONG_BEAR_TREND if scores["trend"] >= 70 else MarketRegime.WEAK_BEAR_TREND
    return MarketRegime.UNKNOWN


def _margins(
    evidence: list[RegimeTuningEvidence],
) -> tuple[list[float], Counter[str]]:
    margins: list[float] = []
    runners: Counter[str] = Counter()
    for item in evidence:
        score_map = {
            "trend": item.scores.trend_score,
            "range": item.scores.range_score,
            "transition": item.scores.transition_score,
            "compression": item.scores.compression_score,
            "expansion": item.scores.expansion_score,
        }
        if item.production_regime is MarketRegime.TRANSITION:
            runner_name, runner_score = max(
                (
                    (name, score)
                    for name, score in score_map.items()
                    if name != "transition"
                ),
                key=lambda pair: (pair[1], pair[0]),
            )
            margins.append(score_map["transition"] - runner_score)
            runners[_regime_label_for_category(item, runner_name, runner_score)] += 1
        else:
            ordered = sorted(
                score_map.items(),
                key=lambda pair: (pair[1], pair[0]),
                reverse=True,
            )
            margins.append(ordered[0][1] - ordered[1][1])
    return margins, runners


def _regime_label_for_category(
    item: RegimeTuningEvidence, category: str, score: float
) -> str:
    if category != "trend":
        return category
    strength = "strong" if score >= 70 else "weak"
    direction = item.trend if item.trend in {"bullish", "bearish"} else "unknown"
    if direction == "unknown":
        return MarketRegime.UNKNOWN.value
    abbreviated = "bull" if direction == "bullish" else "bear"
    return f"{strength}_{abbreviated}_trend"


def _forward_stability(records: list[object]) -> tuple[ForwardStabilityResult, ...]:
    results: list[ForwardStabilityResult] = []
    for horizon in (5, 10, 20):
        proxies: list[tuple[str, str]] = []
        for record in records:
            snapshot = getattr(record, "regime_forward_observation", None)
            if snapshot is None or not snapshot.horizons:
                continue
            target = next((item for item in snapshot.horizons if item.horizon == horizon), None)
            reference = next((item for item in snapshot.horizons if item.horizon == 20), snapshot.horizons[-1])
            if target is not None:
                proxies.append((target.proxy_actual_regime, reference.proxy_actual_regime))
        counts = Counter(item[0] for item in proxies)
        results.append(
            ForwardStabilityResult(
                horizon=horizon,
                samples=len(proxies),
                stability_rate=(round(100.0 * sum(a == b for a, b in proxies) / len(proxies), 3) if proxies else 0.0),
                dominant_proxy_actual=counts.most_common(1)[0][0] if counts else None,
            )
        )
    return tuple(results)


def _average_scores(evidence: list[RegimeTuningEvidence]) -> RegimeEvidenceScores:
    if not evidence:
        return RegimeEvidenceScores(0, 0, 0, 0, 0)
    return RegimeEvidenceScores(*(
        round(sum(getattr(item.scores, field) for item in evidence) / len(evidence), 3)
        for field in ("trend_score", "range_score", "transition_score", "compression_score", "expansion_score")
    ))


def _confidence_by_regime(evidence: list[RegimeTuningEvidence]) -> dict[str, float]:
    groups: dict[str, list[float]] = {}
    for item in evidence:
        groups.setdefault(item.production_regime.value, []).append(item.confidence)
    return {
        regime.value: (
            round(sum(groups[regime.value]) / len(groups[regime.value]), 3)
            if regime.value in groups else 0.0
        )
        for regime in MarketRegime
    }


def _complete_distribution(counts: Counter[str]) -> dict[str, int]:
    return {regime.value: counts[regime.value] for regime in MarketRegime}


def _confidence_histogram(evidence: list[RegimeTuningEvidence]) -> dict[str, int]:
    histogram = {"0-49": 0, "50-59": 0, "60-69": 0, "70-79": 0, "80-89": 0, "90-100": 0}
    for item in evidence:
        value = item.confidence
        bucket = "0-49" if value < 50 else "50-59" if value < 60 else "60-69" if value < 70 else "70-79" if value < 80 else "80-89" if value < 90 else "90-100"
        histogram[bucket] += 1
    return histogram


def _margin_summary(margins: list[float]) -> ClassificationMarginSummary:
    return ClassificationMarginSummary(
        samples=len(margins),
        average_margin=(round(sum(margins) / len(margins), 3) if margins else 0.0),
        median_margin=(round(float(median(margins)), 3) if margins else 0.0),
        minimum_margin=(round(min(margins), 3) if margins else 0.0),
        maximum_margin=(round(max(margins), 3) if margins else 0.0),
        low_margin_count=sum(value <= 10 for value in margins),
    )


def _recommendations(
    *, dominance: float, stale: int, directional: int, transition_count: int, margins: list[float]
) -> tuple[str, ...]:
    messages: list[str] = []
    if dominance > 0.60:
        messages.append("Transition exceeds 60%; inspect transition threshold simulations before changing production rules.")
    if stale:
        messages.append(f"{stale} transition labels rely on non-recent CHOCH evidence; inspect event recency handling.")
    if directional:
        messages.append(f"{directional} transition labels coexist with directional swing structure; compare swing and alignment weight simulations.")
    if margins and sum(value <= 10 for value in margins) / len(margins) >= 0.3:
        messages.append("Many classifications have a margin of 10 points or less; treat threshold changes as sensitive.")
    if not messages:
        messages.append("No dominant tuning defect cleared the documented research thresholds.")
    messages.append("All simulations are counterfactual and leave the production Regime Engine unchanged.")
    return tuple(messages)


def _range_ratio(candles: list[Candle]) -> float:
    if len(candles) < 8:
        return 1.0
    ranges = [max(0.0, candle.high - candle.low) for candle in candles]
    recent = ranges[-4:]
    baseline = ranges[-12:-4] if len(ranges) >= 12 else ranges[:-4]
    average = sum(baseline) / len(baseline) if baseline else 0.0
    return (sum(recent) / len(recent)) / average if average else 1.0
