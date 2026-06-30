"""Transparent, additive evidence scoring that never controls production actions."""

from dataclasses import dataclass
from enum import Enum
from statistics import mean
from typing import Any


class ScoreGrade(str, Enum):
    A_PLUS = "A+"
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    F = "F"


@dataclass(frozen=True)
class EvidenceScoreItem:
    category: str
    score: float
    weight: float
    weighted_score: float
    available: bool
    explanation: str


@dataclass(frozen=True)
class ScoreContributor:
    category: str
    impact: float
    explanation: str


@dataclass(frozen=True)
class ScoreSummary:
    trade_quality_score: float
    confidence_score: float
    edge_score: float
    risk_score: float
    evidence_score_breakdown: tuple[EvidenceScoreItem, ...]
    positive_score_contributors: tuple[ScoreContributor, ...]
    negative_score_contributors: tuple[ScoreContributor, ...]
    neutral_score_contributors: tuple[ScoreContributor, ...]
    score_grade: ScoreGrade
    unavailable_research_inputs: tuple[str, ...]
    human_readable_summary: str


WEIGHTS = {
    "market_structure": 12.0,
    "multi_timeframe_alignment": 12.0,
    "regime_quality": 8.0,
    "setup_quality": 12.0,
    "strategy_alignment": 10.0,
    "risk_reward": 10.0,
    "confirmation": 8.0,
    "execution_readiness": 8.0,
    "historical_edge": 8.0,
    "statistical_reliability": 7.0,
    "monte_carlo_risk": 5.0,
}


class ScoreEngine:
    """Describe evidence quality after authoritative engines have completed."""

    def score(
        self,
        *,
        market_structure=None,
        multi_timeframe=None,
        market_regime=None,
        decision=None,
        setup_plan=None,
        strategy=None,
        risk_reward_ratio: float | None = None,
        research_pipeline_summary=None,
        statistical_validation_summary=None,
        monte_carlo_report=None,
    ) -> ScoreSummary:
        items = (
            self._item("market_structure", *_structure_score(market_structure)),
            self._item("multi_timeframe_alignment", *_timeframe_score(multi_timeframe)),
            self._item("regime_quality", *_regime_score(market_regime)),
            self._item("setup_quality", *_setup_score(setup_plan)),
            self._item("strategy_alignment", *_strategy_score(strategy)),
            self._item("risk_reward", *_risk_reward_score(risk_reward_ratio)),
            self._item("confirmation", *_confirmation_score(decision, setup_plan)),
            self._item("execution_readiness", *_execution_score(setup_plan)),
            self._item("historical_edge", *_historical_score(research_pipeline_summary)),
            self._item(
                "statistical_reliability",
                *_statistical_score(statistical_validation_summary),
            ),
            self._item("monte_carlo_risk", *_monte_carlo_score(monte_carlo_report)),
        )
        return _build_summary(items, decision)

    def aggregate(
        self,
        summaries: list[ScoreSummary] | tuple[ScoreSummary, ...],
        *,
        research_pipeline_summary=None,
        statistical_validation_summary=None,
        monte_carlo_report=None,
    ) -> ScoreSummary | None:
        if not summaries and not any(
            (research_pipeline_summary, statistical_validation_summary, monte_carlo_report)
        ):
            return None
        grouped: dict[str, list[EvidenceScoreItem]] = {}
        for summary in summaries:
            for item in summary.evidence_score_breakdown:
                if item.available:
                    grouped.setdefault(item.category, []).append(item)
        research = {
            "historical_edge": _historical_score(research_pipeline_summary),
            "statistical_reliability": _statistical_score(
                statistical_validation_summary
            ),
            "monte_carlo_risk": _monte_carlo_score(monte_carlo_report),
        }
        items = []
        for category, weight in WEIGHTS.items():
            if category in research:
                score, available, explanation = research[category]
            elif grouped.get(category):
                score = mean(item.score for item in grouped[category])
                available = True
                explanation = (
                    f"Average {category.replace('_', ' ')} score across "
                    f"{len(grouped[category])} calibration records."
                )
            else:
                score, available, explanation = 50.0, False, "Evidence unavailable."
            items.append(
                EvidenceScoreItem(
                    category,
                    round(score, 3),
                    weight,
                    round(score * weight / 100.0, 3),
                    available,
                    explanation,
                )
            )
        confidence = (
            mean(summary.confidence_score for summary in summaries)
            if summaries else None
        )
        return _build_summary(tuple(items), None, confidence_override=confidence)

    @staticmethod
    def _item(category, score, available, explanation):
        weight = WEIGHTS[category]
        return EvidenceScoreItem(
            category=category,
            score=round(score, 3),
            weight=weight,
            weighted_score=round(score * weight / 100.0, 3),
            available=available,
            explanation=explanation,
        )


def _build_summary(items, decision, confidence_override=None):
    available = [item for item in items if item.available]
    total_weight = sum(item.weight for item in available)
    quality = (
        sum(item.score * item.weight for item in available) / total_weight
        if total_weight else 0.0
    )
    confidence = (
        confidence_override
        if confidence_override is not None
        else float(getattr(decision, "confidence", quality))
    )
    edge_categories = {
        "market_structure", "multi_timeframe_alignment", "regime_quality",
        "setup_quality", "strategy_alignment", "historical_edge",
        "statistical_reliability",
    }
    risk_categories = {
        "risk_reward", "execution_readiness", "monte_carlo_risk"
    }
    edge = _category_average(available, edge_categories)
    risk = _category_average(available, risk_categories)
    positive = tuple(_contributor(item) for item in available if item.score >= 70)
    negative = tuple(_contributor(item) for item in available if item.score <= 40)
    neutral = tuple(_contributor(item) for item in available if 40 < item.score < 70)
    unavailable = tuple(
        item.category for item in items
        if not item.available and item.category in {
            "historical_edge", "statistical_reliability", "monte_carlo_risk"
        }
    )
    grade = _grade(quality)
    strongest = max(available, key=lambda item: item.score, default=None)
    weakest = min(available, key=lambda item: item.score, default=None)
    summary = (
        f"Trade quality is {grade.value} ({quality:.1f}/100) because "
        f"{strongest.category.replace('_', ' ') if strongest else 'available evidence'} "
        f"is strongest"
        + (
            f", but {weakest.category.replace('_', ' ')} limits the score."
            if weakest and strongest and weakest.category != strongest.category
            else "."
        )
    )
    if unavailable:
        summary += " Research inputs unavailable: " + ", ".join(unavailable) + "."
    return ScoreSummary(
        trade_quality_score=round(quality, 3),
        confidence_score=round(confidence, 3),
        edge_score=round(edge, 3),
        risk_score=round(risk, 3),
        evidence_score_breakdown=tuple(items),
        positive_score_contributors=positive,
        negative_score_contributors=negative,
        neutral_score_contributors=neutral,
        score_grade=grade,
        unavailable_research_inputs=unavailable,
        human_readable_summary=summary,
    )


def _structure_score(value):
    if value is None:
        return 50.0, False, "Market structure is unavailable."
    trend = _value(getattr(value, "trend", "unclear"))
    phase = _value(getattr(value, "phase", "unclear"))
    score = {"bullish": 82, "bearish": 82, "ranging": 58, "unclear": 25}.get(trend, 40)
    score += {"impulse": 10, "pullback": 5, "range": 0, "reversal_attempt": -5, "unclear": -10}.get(phase, 0)
    return _clamp(score), True, f"Structure is {trend} in a {phase} phase."


def _timeframe_score(value):
    if value is None:
        return 50.0, False, "Multi-timeframe evidence is unavailable."
    alignment = _value(getattr(value, "alignment", "unclear"))
    base = {"aligned_bullish": 95, "aligned_bearish": 95, "mixed": 62, "conflicting": 20, "unclear": 32}.get(alignment, 40)
    score = (base + float(getattr(value, "alignment_score", base))) / 2
    return _clamp(score), True, f"Timeframe alignment is {alignment}."


def _regime_score(value):
    if value is None:
        return 50.0, False, "Market regime is unavailable."
    regime = _value(getattr(value, "market_regime", "unknown"))
    base = {
        "strong_bull_trend": 90, "strong_bear_trend": 90,
        "weak_bull_trend": 72, "weak_bear_trend": 72,
        "expansion": 82, "range": 62, "compression": 58,
        "high_volatility": 55, "low_volatility": 52,
        "transition": 38, "unknown": 25,
    }.get(regime, 45)
    confidence = float(getattr(value, "regime_confidence", base))
    return _clamp((base + confidence) / 2), True, f"Regime is {regime}."


def _setup_score(value):
    if value is None:
        return 50.0, False, "Setup evidence is unavailable."
    status = _value(getattr(value, "setup_status", "no_setup"))
    quality = float(getattr(value, "setup_quality_score", 0.0))
    cap = {"confirmed": 100, "developing": 68, "waiting_for_confirmation": 60, "invalid": 25, "no_setup": 15}.get(status, 50)
    return min(quality, cap), True, f"Setup is {status} with {quality:.1f}/100 quality."


def _strategy_score(value):
    if value is None:
        return 50.0, False, "Strategy evidence is unavailable."
    alignment = _value(getattr(value, "strategy_alignment", "no_clear_strategy"))
    candidates = tuple(getattr(value, "candidates", ()))
    preferred = _value(getattr(value, "preferred_strategy", "no_strategy"))
    candidate = next((item for item in candidates if _value(getattr(item, "strategy_type", "")) == preferred), None)
    score = float(getattr(candidate, "score", 50.0))
    modifier = {"aligned_with_decision": 10, "partially_aligned": 0, "conflicts_with_decision": -30, "no_clear_strategy": -20}.get(alignment, -10)
    return _clamp(score + modifier), True, f"Strategy alignment is {alignment}."


def _risk_reward_score(value):
    if value is None:
        return 40.0, True, "Risk/reward is not yet available."
    ratio = float(value)
    score = 95 if ratio >= 3 else 88 if ratio >= 2 else 76 if ratio >= 1.5 else 50 if ratio >= 1 else 25
    return score, True, f"Estimated risk/reward is {ratio:.2f}R."


def _confirmation_score(decision, setup):
    if decision is None and setup is None:
        return 50.0, False, "Confirmation evidence is unavailable."
    conditions = tuple(getattr(setup, "entry_conditions", ())) if setup else ()
    required = [item for item in conditions if getattr(item, "importance", "") == "required"]
    ratio = sum(bool(getattr(item, "is_met", False)) for item in required) / len(required) if required else 0.5
    action = _value(getattr(decision, "action", "wait")) if decision else "wait"
    score = ratio * 70 + (25 if action in {"buy", "sell"} else 10 if action == "wait" else 0)
    return _clamp(score), True, f"{sum(getattr(item, 'is_met', False) for item in required)} of {len(required)} required confirmations are met."


def _execution_score(setup):
    if setup is None:
        return 50.0, False, "Execution readiness is unavailable."
    status = _value(getattr(setup, "setup_status", "no_setup"))
    levels = all(getattr(setup, name, None) for name in ("entry_zone", "stop_loss", "target"))
    score = 95 if status == "confirmed" and levels else 65 if levels else 35 if status in {"developing", "waiting_for_confirmation"} else 15
    return score, True, f"Execution levels are {'complete' if levels else 'incomplete'} and setup is {status}."


def _historical_score(value):
    if value is None:
        return 50.0, False, "Research pipeline evidence is unavailable."
    score = float(getattr(value, "generalization_score", 50.0))
    return _clamp(score), True, f"Historical generalization score is {score:.1f}/100."


def _statistical_score(value):
    if value is None:
        return 50.0, False, "Statistical validation is unavailable."
    weakness = float(getattr(value, "weakness_score", 50.0))
    available = bool(getattr(value, "available", True))
    return _clamp(100 - weakness), available, f"Statistical weakness score is {weakness:.1f}/100."


def _monte_carlo_score(value):
    if value is None:
        return 50.0, False, "Monte Carlo reporting is unavailable."
    status = _value(getattr(value, "overall_status", "WATCHLIST"))
    score = {"PASS": 90, "WATCHLIST": 62, "FAIL": 20, "INSUFFICIENT_DATA": 42}.get(status, 45)
    return score, True, f"Monte Carlo report status is {status}."


def _category_average(items, categories):
    selected = [item.score for item in items if item.category in categories]
    return mean(selected) if selected else 0.0


def _contributor(item):
    return ScoreContributor(item.category, round(item.score - 50.0, 3), item.explanation)


def _grade(score):
    return (
        ScoreGrade.A_PLUS if score >= 90 else ScoreGrade.A if score >= 80
        else ScoreGrade.B if score >= 70 else ScoreGrade.C if score >= 60
        else ScoreGrade.D if score >= 45 else ScoreGrade.F
    )


def _value(value: Any) -> str:
    return str(getattr(value, "value", value))


def _clamp(value):
    return max(0.0, min(100.0, float(value)))
