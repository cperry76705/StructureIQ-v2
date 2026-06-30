"""Research-only historical grading for setup and strategy categories."""

from dataclasses import dataclass
from enum import Enum
from statistics import mean, pstdev

class RatingGrade(str, Enum):
    A_PLUS = "A+"
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    F = "F"


@dataclass(frozen=True)
class RatingConfidenceInterval:
    lower: float
    upper: float
    confidence_level: float
    sample_size: int


@dataclass(frozen=True)
class CategoryRating:
    name: str
    grade: RatingGrade
    rating_score: float
    sample_size: int
    sample_quality: str
    win_rate: float
    expectancy: float
    average_r: float
    total_r: float
    profit_factor: float | None
    max_drawdown: float
    confidence_interval: RatingConfidenceInterval
    statistical_significance_score: float
    out_of_sample_consistency: float | None
    overfit_risk: str
    recommendation: str
    human_readable_summary: str


@dataclass(frozen=True)
class RatingSummary:
    category_type: str
    grades: tuple[CategoryRating, ...]
    strongest: str | None
    weakest: str | None
    warnings: tuple[str, ...]
    human_readable_summary: str


@dataclass(frozen=True)
class StrategyRatingResult:
    strategy_rating_summary: RatingSummary
    setup_rating_summary: RatingSummary
    strategy_grades: tuple[CategoryRating, ...]
    setup_grades: tuple[CategoryRating, ...]
    strongest_strategy: str | None
    weakest_strategy: str | None
    strongest_setup: str | None
    weakest_setup: str | None
    strategy_rating_warnings: tuple[str, ...]
    setup_rating_warnings: tuple[str, ...]
    human_readable_summary: str


@dataclass(frozen=True)
class UnavailableCategoryRating:
    name: str
    available: bool
    grade: None
    sample_size: int
    warning: str
    human_readable_summary: str


class StrategyRatingEngine:
    """Grade completed research without affecting production category selection."""

    def rate(
        self,
        *,
        research_lab_summary,
        validation_fold_results=(),
        overfitting_summary=None,
        statistical_validation_summary=None,
        confidence_bucket_calibration=(),
        setup_performance=(),
        strategy_performance=(),
        research_rankings=None,
        performance_matrices=None,
        out_of_sample_summary=None,
        generalization_summary=None,
    ) -> StrategyRatingResult:
        del (
            setup_performance,
            strategy_performance,
            research_rankings,
            performance_matrices,
            out_of_sample_summary,
            generalization_summary,
        )
        overfit = getattr(overfitting_summary, "risk_level", "UNAVAILABLE")
        statistical_status = getattr(
            statistical_validation_summary, "overall_status", None
        )
        confidence_reliability = _confidence_reliability(
            confidence_bucket_calibration
        )
        strategy_consistency = _oos_consistency(
            validation_fold_results, "validation_strategy_performance"
        )
        setup_consistency = _oos_consistency(
            validation_fold_results, "validation_setup_performance"
        )
        strategies = tuple(
            _grade_row(
                row,
                strategy_consistency.get(row.category),
                overfit,
                statistical_status,
                confidence_reliability,
            )
            for row in research_lab_summary.strategy_performance
            if row.records_seen or row.executed_trades
        )
        setups = tuple(
            _grade_row(
                row,
                setup_consistency.get(row.category),
                overfit,
                statistical_status,
                confidence_reliability,
            )
            for row in research_lab_summary.setup_performance
            if row.records_seen or row.executed_trades
        )
        strategy_summary = _summary("strategy", strategies)
        setup_summary = _summary("setup", setups)
        return StrategyRatingResult(
            strategy_rating_summary=strategy_summary,
            setup_rating_summary=setup_summary,
            strategy_grades=strategies,
            setup_grades=setups,
            strongest_strategy=strategy_summary.strongest,
            weakest_strategy=strategy_summary.weakest,
            strongest_setup=setup_summary.strongest,
            weakest_setup=setup_summary.weakest,
            strategy_rating_warnings=strategy_summary.warnings,
            setup_rating_warnings=setup_summary.warnings,
            human_readable_summary=(
                f"Historical ratings cover {len(strategies)} strategies and "
                f"{len(setups)} setups. Ratings are advisory and cannot reroute production."
            ),
        )

    @staticmethod
    def unavailable(name: str) -> UnavailableCategoryRating:
        return UnavailableCategoryRating(
            name=name,
            available=False,
            grade=None,
            sample_size=0,
            warning="No historical category rating is loaded in live analysis.",
            human_readable_summary=(
                f"Historical rating for {name.replace('_', ' ')} is unavailable in "
                "live analysis; no production inference should be made."
            ),
        )


def _grade_row(row, oos_consistency, overfit, statistical_status, confidence_reliability):
    sample = int(row.executed_trades)
    expectancy = float(row.expectancy)
    profit_factor = row.profit_factor
    drawdown = float(row.max_drawdown)
    sample_score = 95 if sample >= 100 else 80 if sample >= 50 else 65 if sample >= 20 else 45 if sample >= 5 else 20
    expectancy_score = 95 if expectancy >= 1 else 85 if expectancy >= 0.5 else 75 if expectancy >= 0.2 else 62 if expectancy > 0 else 0
    profit_score = 92 if profit_factor is None and expectancy > 0 else 90 if profit_factor is not None and profit_factor >= 2 else 78 if profit_factor is not None and profit_factor >= 1.5 else 65 if profit_factor is not None and profit_factor >= 1.2 else 35
    drawdown_score = 92 if drawdown <= 2 else 78 if drawdown <= 5 else 58 if drawdown <= 10 else 25
    oos_score = 50.0 if oos_consistency is None else oos_consistency
    score = (
        expectancy_score * 0.25
        + profit_score * 0.15
        + drawdown_score * 0.15
        + sample_score * 0.15
        + float(row.win_rate) * 0.10
        + float(row.statistical_significance_score) * 0.10
        + oos_score * 0.10
    )
    score -= {"MEDIUM": 8, "HIGH": 20, "OVERFIT_RISK": 35}.get(
        str(overfit).upper(), 0
    )
    if statistical_status == "FAIL":
        score -= 15
    score = max(0.0, min(100.0, score))
    grade = _score_grade(score)
    if expectancy < 0:
        grade = RatingGrade.F
    elif sample < 5:
        grade = _cap_grade(grade, RatingGrade.D)
    elif sample < 20:
        grade = _cap_grade(grade, RatingGrade.B)
    elif (
        grade is RatingGrade.A_PLUS
        and not (
            sample >= 100
            and expectancy >= 0.5
            and (profit_factor is None or profit_factor >= 1.5)
            and drawdown <= 5
            and oos_consistency is not None
            and oos_consistency >= 70
            and str(overfit).upper() not in {"HIGH", "OVERFIT_RISK"}
        )
    ):
        grade = RatingGrade.A
    warnings = []
    if sample < 5:
        warnings.append("Fewer than five closed trades cap this rating at D.")
    elif sample < 20:
        warnings.append("Fewer than 20 closed trades cap this rating at B.")
    if row.sample_quality == "insufficient":
        warnings.append("Sample quality is insufficient; do not change production behavior.")
    if oos_consistency is None:
        warnings.append("Out-of-sample category consistency is unavailable.")
    if confidence_reliability in {"insufficient", "low"}:
        warnings.append("Confidence calibration evidence is sparse.")
    recommendation = (
        "Do not use this negative-expectancy category for a production change."
        if expectancy < 0 else
        "Collect more closed and OOS trades before interpretation."
        if sample < 20 else
        "Continue independent OOS review; this grade does not authorize routing changes."
    )
    return CategoryRating(
        name=row.category,
        grade=grade,
        rating_score=round(score, 3),
        sample_size=sample,
        sample_quality=row.sample_quality,
        win_rate=row.win_rate,
        expectancy=expectancy,
        average_r=row.average_r,
        total_r=row.total_r,
        profit_factor=profit_factor,
        max_drawdown=drawdown,
        confidence_interval=RatingConfidenceInterval(
            lower=row.confidence_interval.lower,
            upper=row.confidence_interval.upper,
            confidence_level=row.confidence_interval.confidence_level,
            sample_size=row.confidence_interval.sample_size,
        ),
        statistical_significance_score=row.statistical_significance_score,
        out_of_sample_consistency=(
            round(oos_consistency, 3) if oos_consistency is not None else None
        ),
        overfit_risk=str(overfit),
        recommendation=recommendation,
        human_readable_summary=(
            f"{row.category.replace('_', ' ').title()} is graded {grade.value} "
            f"({score:.1f}/100) from {sample} closed trades, {expectancy:.3f}R "
            f"expectancy, and {drawdown:.2f}R maximum drawdown."
            + (" " + " ".join(warnings) if warnings else "")
        ),
    )


def _oos_consistency(folds, attribute):
    grouped: dict[str, list[float]] = {}
    for fold in folds or ():
        for name, performance in (getattr(fold, attribute, None) or {}).items():
            if performance.trades:
                grouped.setdefault(name, []).append(performance.expectancy)
    result = {}
    for name, values in grouped.items():
        positive = sum(value > 0 for value in values) / len(values) * 100.0
        variance_score = max(0.0, 100.0 - (pstdev(values) * 30 if len(values) > 1 else 0.0))
        result[name] = (positive + variance_score) / 2
    return result


def _confidence_reliability(buckets):
    populated = [item for item in buckets or () if item.sample_size]
    if not populated:
        return "insufficient"
    order = {"insufficient": 0, "low": 1, "medium": 2, "high": 3}
    return min(
        (_value(item.confidence_reliability) for item in populated),
        key=lambda value: order.get(value, 0),
    )


def _summary(category_type, grades):
    if not grades:
        return RatingSummary(
            category_type, (), None, None,
            ("No closed historical categories are available.",),
            f"No {category_type} ratings are available yet.",
        )
    ordered = sorted(grades, key=lambda item: (item.rating_score, item.sample_size), reverse=True)
    warnings = tuple(
        f"{item.name}: {item.human_readable_summary}"
        for item in grades
        if item.sample_size < 20 or item.sample_quality == "insufficient"
    )
    return RatingSummary(
        category_type=category_type,
        grades=tuple(grades),
        strongest=ordered[0].name,
        weakest=ordered[-1].name,
        warnings=warnings,
        human_readable_summary=(
            f"Rated {len(grades)} {category_type} categories; strongest is "
            f"{ordered[0].name} ({ordered[0].grade.value}) and weakest is "
            f"{ordered[-1].name} ({ordered[-1].grade.value})."
        ),
    )


def _score_grade(score):
    return (
        RatingGrade.A_PLUS if score >= 90 else RatingGrade.A if score >= 80
        else RatingGrade.B if score >= 70 else RatingGrade.C if score >= 60
        else RatingGrade.D if score >= 45 else RatingGrade.F
    )


def _cap_grade(grade, cap):
    order = list(RatingGrade)
    return order[max(order.index(grade), order.index(cap))]


def _value(value):
    return str(getattr(value, "value", value))
