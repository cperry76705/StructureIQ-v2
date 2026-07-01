"""Compact, read-only dashboard summaries over existing StructureIQ research."""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Any

from app.config import APP_VERSION
from core.research_engine import ResearchEngine, ResearchWindow
from core.symbol_profile_engine import SymbolProfileEngine


_LATEST_CALIBRATION: Any | None = None
_STATE_LOCK = RLock()


@dataclass(frozen=True)
class DashboardOverview:
    app_version: str
    latest_research_status: str
    total_symbols_profiled: int
    best_symbol: str | None
    best_strategy: str | None
    best_setup: str | None
    aggregate_win_rate: float | None
    aggregate_expectancy: float | None
    aggregate_total_r: float | None
    aggregate_profit_factor: float | None
    aggregate_drawdown: float | None
    paper_trading_readiness: str
    major_warnings: tuple[str, ...]
    human_readable_summary: str
    average_quality_score: float | None = None
    highest_quality_setup: str | None = None
    best_quality_symbol: str | None = None
    quality_grade_distribution: dict[str, int] | None = None
    execution_cost_status: str = "disabled"
    baseline_total_r_after_cost_model: float | None = None
    realistic_total_r: float | None = None
    execution_degradation_r: float | None = None
    highest_cost_sensitivity: str | None = None


@dataclass(frozen=True)
class DashboardSymbolRow:
    symbol: str
    status: str
    sample_size: int
    win_rate: float
    expectancy: float
    total_r: float
    profit_factor: float | None
    max_drawdown: float
    market_character: str
    preferred_strategy: str | None
    preferred_setup: str | None
    confidence: float
    warnings: tuple[str, ...]
    recommendation: str


@dataclass(frozen=True)
class DashboardSymbols:
    symbols: tuple[DashboardSymbolRow, ...]
    total_symbols: int
    human_readable_summary: str


@dataclass(frozen=True)
class DashboardRatingRow:
    name: str
    grade: str | None
    sample_size: int
    sample_quality: str
    win_rate: float
    expectancy: float
    total_r: float
    profit_factor: float | None
    max_drawdown: float
    overfit_risk: str
    readiness_status: str
    recommendation: str
    average_quality: float | None = None
    quality_rank: int | None = None


@dataclass(frozen=True)
class DashboardStrategies:
    strategies: tuple[DashboardRatingRow, ...]
    human_readable_summary: str


@dataclass(frozen=True)
class DashboardSetups:
    setups: tuple[DashboardRatingRow, ...]
    human_readable_summary: str


@dataclass(frozen=True)
class DashboardReadiness:
    paper_trading_status: str
    readiness_score: float
    blocking_reasons: tuple[str, ...]
    watchlist_reasons: tuple[str, ...]
    minimum_data_requirements: tuple[str, ...]
    current_sample_summary: str
    out_of_sample_status: str
    monte_carlo_status: str
    statistical_validation_status: str
    confidence_calibration_status: str
    symbol_profile_status: str
    adaptive_router_status: str
    human_readable_summary: str


@dataclass(frozen=True)
class DashboardRisks:
    top_risks: tuple[str, ...]
    overfit_warnings: tuple[str, ...]
    drawdown_warnings: tuple[str, ...]
    low_sample_warnings: tuple[str, ...]
    calibration_warnings: tuple[str, ...]
    confidence_warnings: tuple[str, ...]
    provider_failures: tuple[str, ...]
    data_availability_summary: Any | None
    risk_grade: str
    human_readable_summary: str
    execution_cost_warnings: tuple[str, ...] = ()
    execution_cost_status: str = "disabled"
    execution_degradation_r: float | None = None
    highest_cost_sensitivity: str | None = None


@dataclass(frozen=True)
class DashboardRecommendation:
    priority: int
    category: str
    message: str
    evidence: str
    suggested_action: str
    severity: str
    production_safe: bool
    human_readable_summary: str


@dataclass(frozen=True)
class DashboardRecommendations:
    recommendations: tuple[DashboardRecommendation, ...]
    human_readable_summary: str


def store_latest_calibration(result: Any) -> None:
    """Store the latest completed calibration result in process-local memory."""

    global _LATEST_CALIBRATION
    with _STATE_LOCK:
        _LATEST_CALIBRATION = result


def clear_dashboard_state() -> None:
    """Clear process-local dashboard state; intended for tests."""

    global _LATEST_CALIBRATION
    with _STATE_LOCK:
        _LATEST_CALIBRATION = None


def latest_calibration() -> Any | None:
    """Return the latest process-local calibration snapshot."""

    with _STATE_LOCK:
        return _LATEST_CALIBRATION


class ResearchDashboardService:
    """Build compact dashboard responses from existing research artifacts only."""

    def __init__(
        self,
        *,
        symbol_profiles: SymbolProfileEngine,
        research_engine: ResearchEngine,
        calibration_result: Any | None = None,
    ) -> None:
        self.symbol_profiles = symbol_profiles
        self.research_engine = research_engine
        self.calibration = calibration_result if calibration_result is not None else latest_calibration()

    def overview(self) -> DashboardOverview:
        status = self._research_status()
        profiles = self.symbol_profiles.list_profiles()
        metrics = getattr(self.calibration, "aggregate_metrics", None)
        readiness = self.readiness()
        best_symbol = self._best_symbol(status, profiles)
        best_strategy = _first_non_empty(
            getattr(status, "best_strategy", None),
            _strongest_name(getattr(self.calibration, "strategy_rating_summary", None)),
        )
        best_setup = _first_non_empty(
            getattr(status, "best_setup", None),
            _strongest_name(getattr(self.calibration, "setup_rating_summary", None)),
        )
        warnings = tuple(
            dict.fromkeys(
                (
                    *self._low_sample_warnings(),
                    *self._overfit_warnings(),
                    *self._provider_failure_messages(),
                )
            )
        )[:10]
        available = self.calibration is not None or bool(profiles)
        quality = getattr(self.calibration, "setup_quality_summary", None)
        quality_setups = getattr(quality, "average_quality_by_setup", ()) or ()
        quality_symbols = getattr(quality, "average_quality_by_symbol", ()) or ()
        costs = getattr(self.calibration, "aggregate_execution_cost_summary", None)
        sensitivities = getattr(costs, "symbols_most_affected", ()) or ()
        return DashboardOverview(
            app_version=APP_VERSION,
            latest_research_status=getattr(
                status,
                "latest_research_status_statement",
                "No completed calibration research is available yet.",
            ),
            total_symbols_profiled=len(profiles),
            best_symbol=best_symbol,
            best_strategy=best_strategy,
            best_setup=best_setup,
            aggregate_win_rate=getattr(metrics, "win_rate", None),
            aggregate_expectancy=getattr(metrics, "average_r", None),
            aggregate_total_r=getattr(metrics, "total_r", None),
            aggregate_profit_factor=getattr(metrics, "profit_factor", None),
            aggregate_drawdown=getattr(metrics, "max_drawdown_r", None),
            paper_trading_readiness=readiness.paper_trading_status,
            major_warnings=warnings,
            human_readable_summary=(
                "Dashboard is available from the latest calibration snapshot."
                if available
                else "Dashboard is unavailable until calibration or symbol-profile research exists."
            ),
            average_quality_score=getattr(quality, "average_quality_score", None),
            highest_quality_setup=(quality_setups[0].name if quality_setups else None),
            best_quality_symbol=(quality_symbols[0].name if quality_symbols else None),
            quality_grade_distribution=(
                getattr(quality, "grade_distribution", None) if quality else None
            ),
            execution_cost_status="enabled" if costs is not None else "disabled",
            baseline_total_r_after_cost_model=getattr(costs, "baseline_total_r", None),
            realistic_total_r=getattr(costs, "realistic_total_r", None),
            execution_degradation_r=getattr(costs, "total_degradation_r", None),
            highest_cost_sensitivity=(sensitivities[0].name if sensitivities else None),
        )

    def symbols(self) -> DashboardSymbols:
        rows = tuple(
            sorted(
                (_symbol_row(profile) for profile in self.symbol_profiles.list_profiles()),
                key=lambda item: (item.expectancy, item.sample_size),
                reverse=True,
            )
        )
        return DashboardSymbols(
            symbols=rows,
            total_symbols=len(rows),
            human_readable_summary=(
                f"{len(rows)} symbol profiles are available."
                if rows
                else "No symbol profiles are available yet."
            ),
        )

    def strategies(self) -> DashboardStrategies:
        rows = _rating_rows(getattr(self.calibration, "strategy_rating_summary", None))
        return DashboardStrategies(
            strategies=rows,
            human_readable_summary=(
                f"{len(rows)} strategy ratings are available."
                if rows
                else "Strategy ratings are unavailable until calibration completes."
            ),
        )

    def setups(self) -> DashboardSetups:
        rows = _rating_rows(
            getattr(self.calibration, "setup_rating_summary", None),
            quality_groups=getattr(
                getattr(self.calibration, "setup_quality_summary", None),
                "average_quality_by_setup",
                (),
            ),
        )
        return DashboardSetups(
            setups=rows,
            human_readable_summary=(
                f"{len(rows)} setup ratings are available."
                if rows
                else "Setup ratings are unavailable until calibration completes."
            ),
        )

    def readiness(self) -> DashboardReadiness:
        promotion = getattr(self.calibration, "promotion_readiness_summary", None)
        validation_trades = _validation_trades(self.calibration)
        profiles = self.symbol_profiles.list_profiles()
        blockers: list[str] = []
        watchlist: list[str] = []
        if promotion is None:
            status = "UNAVAILABLE"
            blockers.append("Out-of-sample promotion readiness has not been requested.")
            score = 0.0
        else:
            status = _enum_value(getattr(promotion, "overall_status", "UNAVAILABLE"))
            score = _readiness_score(status)
            blockers.extend(getattr(promotion, "reasons", ()))
            if status == "READY_FOR_PAPER_TRADING" and validation_trades < 100:
                status = "NEEDS_MORE_DATA"
                score = min(score, 55.0)
                blockers.append(
                    "Fewer than 100 completed validation trades are available."
                )
            if getattr(promotion, "monte_carlo_readiness_blocked", False):
                status = "NOT_READY"
                score = min(score, 25.0)
                blockers.append("Monte Carlo risk blocks paper-trading readiness.")
            if getattr(promotion, "statistical_validation_readiness_blocked", False):
                status = "NOT_READY"
                score = min(score, 25.0)
                blockers.append(
                    "Severe statistical validation weakness blocks readiness."
                )

        if validation_trades < 100:
            watchlist.append("Minimum validation sample has not reached 100 trades.")
        low_samples = self._low_sample_warnings()
        watchlist.extend(low_samples[:5])
        confidence_status = _confidence_status(self.calibration)
        symbol_status = "available" if profiles else "unavailable"
        adaptive = getattr(
            self.calibration,
            "aggregate_adaptive_strategy_router_summary",
            None,
        )
        return DashboardReadiness(
            paper_trading_status=status,
            readiness_score=score,
            blocking_reasons=tuple(dict.fromkeys(blockers)),
            watchlist_reasons=tuple(dict.fromkeys(watchlist)),
            minimum_data_requirements=(
                "At least 100 completed validation trades for paper-trading consideration.",
                "300 validation trades is strong; 500+ is excellent.",
                "Monte Carlo and statistical validation must not block readiness.",
            ),
            current_sample_summary=(
                f"{validation_trades} validation trades; "
                f"{getattr(getattr(self.calibration, 'aggregate_metrics', None), 'total_trades', 0)} completed calibration trades."
            ),
            out_of_sample_status=(
                "available" if getattr(self.calibration, "out_of_sample_summary", None) else "unavailable"
            ),
            monte_carlo_status=_monte_carlo_status(self.calibration),
            statistical_validation_status=_statistical_status(self.calibration),
            confidence_calibration_status=confidence_status,
            symbol_profile_status=symbol_status,
            adaptive_router_status=(
                "available" if adaptive is not None else "unavailable"
            ),
            human_readable_summary=(
                f"Paper-trading readiness is {status}. "
                "This dashboard is advisory and cannot change production behavior."
            ),
        )

    def risks(self) -> DashboardRisks:
        overfit = self._overfit_warnings()
        low_sample = self._low_sample_warnings()
        calibration = self._calibration_warning_messages()
        confidence = self._confidence_warnings()
        provider = self._provider_failure_messages()
        drawdown = self._drawdown_warnings()
        execution_costs = getattr(self.calibration, "aggregate_execution_cost_summary", None)
        execution_warnings = tuple(getattr(execution_costs, "warnings", ()) or ())
        cost_sensitivities = getattr(execution_costs, "symbols_most_affected", ()) or ()
        top = tuple(
            dict.fromkeys((*execution_warnings, *overfit, *drawdown, *low_sample, *calibration, *confidence, *provider))
        )[:12]
        risk_grade = _risk_grade(top, overfit, drawdown)
        return DashboardRisks(
            top_risks=top,
            overfit_warnings=overfit,
            drawdown_warnings=drawdown,
            low_sample_warnings=low_sample,
            calibration_warnings=calibration,
            confidence_warnings=confidence,
            provider_failures=provider,
            data_availability_summary=getattr(
                self.calibration, "data_availability_summary", None
            ),
            risk_grade=risk_grade,
            human_readable_summary=(
                f"Dashboard risk grade is {risk_grade} based on existing research."
            ),
            execution_cost_warnings=execution_warnings,
            execution_cost_status="enabled" if execution_costs is not None else "disabled",
            execution_degradation_r=getattr(execution_costs, "total_degradation_r", None),
            highest_cost_sensitivity=(cost_sensitivities[0].name if cost_sensitivities else None),
        )

    def recommendations(self) -> DashboardRecommendations:
        items: list[DashboardRecommendation] = []
        priority = 1
        for category, message, severity, action, evidence in self._recommendation_sources():
            items.append(
                DashboardRecommendation(
                    priority=priority,
                    category=category,
                    message=message,
                    evidence=evidence,
                    suggested_action=action,
                    severity=severity,
                    production_safe=True,
                    human_readable_summary=(
                        f"{category}: {message} Recommended action: {action}"
                    ),
                )
            )
            priority += 1
        return DashboardRecommendations(
            recommendations=tuple(items[:25]),
            human_readable_summary=(
                f"{min(len(items), 25)} prioritized advisory action items are available."
                if items
                else "No dashboard recommendations are available yet."
            ),
        )

    def _research_status(self):
        try:
            return self.research_engine.snapshot(ResearchWindow.ALL_TIME, None).status
        except Exception:
            return None

    def _best_symbol(self, status, profiles) -> str | None:
        if getattr(status, "best_symbol", None):
            return status.best_symbol
        if profiles:
            return max(profiles, key=lambda item: (item.expectancy, item.sample_size)).symbol
        return None

    def _overfit_warnings(self) -> tuple[str, ...]:
        warnings: list[str] = []
        overfit = getattr(self.calibration, "overfitting_summary", None)
        if overfit is not None:
            risk = getattr(overfit, "risk_level", None)
            if risk and str(risk).upper() not in {"LOW", "UNAVAILABLE"}:
                warnings.append(f"Overfitting risk is {risk}.")
            warnings.extend(str(item) for item in getattr(overfit, "risk_factors", ()) or ())
        stats = getattr(self.calibration, "research_statistics", None)
        warnings.extend(str(item) for item in getattr(stats, "possible_overfitting", ()) or ())
        return tuple(dict.fromkeys(warnings))

    def _low_sample_warnings(self) -> tuple[str, ...]:
        warnings: list[str] = []
        for summary in (
            getattr(self.calibration, "strategy_rating_summary", None),
            getattr(self.calibration, "setup_rating_summary", None),
        ):
            warnings.extend(str(item) for item in getattr(summary, "warnings", ()) or ())
            for grade in getattr(summary, "grades", ()) or ():
                if getattr(grade, "sample_quality", "") in {"insufficient", "low"}:
                    warnings.append(
                        f"{getattr(grade, 'name', 'category')} has low sample quality "
                        f"({getattr(grade, 'sample_size', 0)} trades)."
                    )
        stats = getattr(self.calibration, "research_statistics", None)
        warnings.extend(str(item) for item in getattr(stats, "promising_under_tested", ()) or ())
        return tuple(dict.fromkeys(warnings))

    def _calibration_warning_messages(self) -> tuple[str, ...]:
        messages = []
        for rec in getattr(self.calibration, "recommendations", ()) or ():
            if str(_enum_value(getattr(rec, "severity", ""))).lower() in {"high", "medium"}:
                messages.append(getattr(rec, "message", str(rec)))
        return tuple(dict.fromkeys(messages))

    def _confidence_warnings(self) -> tuple[str, ...]:
        warnings = []
        aggregate = getattr(
            self.calibration,
            "aggregate_confidence_calibration_summary",
            None,
        )
        if aggregate is not None:
            reliability = getattr(aggregate, "overall_reliability", None)
            if reliability and str(reliability).lower() in {"low", "insufficient"}:
                warnings.append(f"Confidence calibration reliability is {reliability}.")
        for bucket in getattr(self.calibration, "confidence_bucket_calibration", ()) or ():
            reliability = getattr(bucket, "confidence_reliability", None)
            if reliability and str(reliability).lower() in {"low", "insufficient"}:
                warnings.append(
                    f"Confidence bucket {getattr(bucket, 'bucket', 'unknown')} has {reliability} reliability."
                )
        return tuple(dict.fromkeys(warnings))

    def _provider_failure_messages(self) -> tuple[str, ...]:
        return tuple(
            f"{item.symbol} {item.timeframe}/{item.higher_timeframe}: {item.error_message}"
            for item in getattr(self.calibration, "provider_failures", ()) or ()
        )

    def _drawdown_warnings(self) -> tuple[str, ...]:
        warnings = []
        metrics = getattr(self.calibration, "aggregate_metrics", None)
        drawdown = abs(float(getattr(metrics, "max_drawdown_r", 0.0) or 0.0))
        if drawdown >= 5:
            warnings.append(f"Aggregate drawdown is {drawdown:.2f}R.")
        report = getattr(self.calibration, "monte_carlo_report", None)
        if report is not None:
            probability = getattr(report, "probability_of_drawdown_over_20_percent", 0)
            if probability and probability >= 25:
                warnings.append(
                    "Monte Carlo shows elevated probability of drawdown over 20%."
                )
        return tuple(warnings)

    def _recommendation_sources(self):
        for rec in getattr(self.calibration, "recommendations", ()) or ():
            yield (
                _enum_value(getattr(rec, "category", "calibration")),
                getattr(rec, "message", str(rec)),
                _enum_value(getattr(rec, "severity", "medium")),
                getattr(rec, "suggested_action", "Review the underlying evidence."),
                "Calibration recommendation",
            )
        for message in getattr(self.calibration, "research_action_items", ()) or ():
            yield ("research_pipeline", str(message), "medium", str(message), "Walk-forward intelligence")
        for message in getattr(self.calibration, "research_recommendations", ()) or ():
            yield ("research", str(message), "medium", "Review research sample and category performance.", "Research laboratory")
        for summary_name in ("strategy_rating_summary", "setup_rating_summary"):
            summary = getattr(self.calibration, summary_name, None)
            category = summary_name.removesuffix("_summary")
            for warning in getattr(summary, "warnings", ()) or ():
                yield (category, str(warning), "medium", "Collect more validation data before changing production behavior.", "Rating warning")
        for warning in self._confidence_warnings():
            yield ("confidence_calibration", warning, "medium", "Inspect confidence bucket reliability.", "Confidence calibration")
        for profile in self.symbol_profiles.list_profiles():
            if profile.sample_size < 30:
                yield (
                    "symbol_profile",
                    f"{profile.symbol} has insufficient profile history.",
                    "low",
                    "Run more calibration before using symbol preferences.",
                    "Symbol profile",
                )
        adaptive = getattr(
            self.calibration,
            "aggregate_adaptive_strategy_router_summary",
            None,
        )
        if adaptive is not None and getattr(adaptive, "misaligned_count", 0):
            yield (
                "adaptive_router",
                f"{adaptive.misaligned_count} production routes differed from symbol-profile preferences.",
                "medium",
                "Review route misalignment diagnostics without changing routing automatically.",
                "Adaptive router summary",
            )
        weakness = getattr(self.calibration, "weakness_detection_summary", None)
        for flag in getattr(weakness, "weakness_flags", ()) or ():
            yield (
                "statistical_validation",
                f"Statistical weakness detected: {flag}",
                "high",
                "Do not promote until weakness is resolved or disproven out of sample.",
                "Statistical validation",
            )
        for reason in getattr(self.calibration, "monte_carlo_failure_reasons", ()) or ():
            yield (
                "monte_carlo",
                f"Monte Carlo readiness blocker: {reason}",
                "high",
                "Review sequence and drawdown risk before paper-trading review.",
                "Monte Carlo report",
            )
        quality = getattr(self.calibration, "setup_quality_summary", None)
        for message in getattr(quality, "recommendations", ()) or ():
            yield (
                "setup_quality",
                str(message),
                "low",
                "Review setup-quality evidence; do not alter production rules automatically.",
                "Setup Quality Intelligence Engine",
            )
        costs = getattr(self.calibration, "aggregate_execution_cost_summary", None)
        for message in getattr(costs, "warnings", ()) or ():
            yield (
                "execution_cost",
                str(message),
                "high" if getattr(costs, "degradation_percent", 0) >= 50 else "medium",
                "Validate venue-specific cost assumptions and execution feasibility before paper trading.",
                "Realistic Execution Cost Model",
            )


def _symbol_row(profile) -> DashboardSymbolRow:
    warnings = []
    if profile.sample_size < 20:
        warnings.append("Insufficient sample for preferred strategy/setup.")
    if profile.market_character == "insufficient_data":
        warnings.append("Market character requires at least 30 completed trades.")
    return DashboardSymbolRow(
        symbol=profile.symbol,
        status="available" if profile.sample_size >= 20 else "insufficient_data",
        sample_size=profile.sample_size,
        win_rate=profile.win_rate,
        expectancy=profile.expectancy,
        total_r=profile.total_r,
        profit_factor=profile.profit_factor,
        max_drawdown=profile.max_drawdown,
        market_character=profile.market_character,
        preferred_strategy=profile.preferred_strategy,
        preferred_setup=profile.preferred_setup,
        confidence=profile.confidence,
        warnings=tuple(warnings),
        recommendation=(
            "Profile is usable for advisory review."
            if not warnings
            else "Collect more completed calibration trades before relying on this profile."
        ),
    )


def _rating_rows(summary, quality_groups=()) -> tuple[DashboardRatingRow, ...]:
    quality = {getattr(item, "name", ""): item for item in quality_groups or ()}
    rows = [
        DashboardRatingRow(
            name=getattr(grade, "name", "unknown"),
            grade=_enum_value(getattr(grade, "grade", None)),
            sample_size=int(getattr(grade, "sample_size", 0)),
            sample_quality=str(getattr(grade, "sample_quality", "unavailable")),
            win_rate=float(getattr(grade, "win_rate", 0.0) or 0.0),
            expectancy=float(getattr(grade, "expectancy", 0.0) or 0.0),
            total_r=float(getattr(grade, "total_r", 0.0) or 0.0),
            profit_factor=getattr(grade, "profit_factor", None),
            max_drawdown=float(getattr(grade, "max_drawdown", 0.0) or 0.0),
            overfit_risk=str(getattr(grade, "overfit_risk", "unavailable")),
            readiness_status=_rating_readiness(grade),
            recommendation=str(getattr(grade, "recommendation", "Unavailable.")),
            average_quality=getattr(quality.get(getattr(grade, "name", "")), "average_quality", None),
            quality_rank=getattr(quality.get(getattr(grade, "name", "")), "quality_rank", None),
        )
        for grade in getattr(summary, "grades", ()) or ()
    ]
    rated_names = {item.name for item in rows}
    for name, item in quality.items():
        if name in rated_names:
            continue
        rows.append(
            DashboardRatingRow(
                name=name,
                grade=getattr(item, "grade", None),
                sample_size=int(getattr(item, "records", 0)),
                sample_quality="research_only",
                win_rate=float(getattr(item, "win_rate", 0.0)),
                expectancy=float(getattr(item, "expectancy", 0.0)),
                total_r=0.0,
                profit_factor=getattr(item, "profit_factor", None),
                max_drawdown=float(getattr(item, "max_drawdown", 0.0)),
                overfit_risk="unavailable",
                readiness_status="RESEARCH_ONLY",
                recommendation="Review quality evidence without changing setup selection.",
                average_quality=float(getattr(item, "average_quality", 0.0)),
                quality_rank=int(getattr(item, "quality_rank", 0)),
            )
        )
    return tuple(
        sorted(
            rows,
            key=lambda item: (_grade_rank(item.grade), item.expectancy, item.sample_size),
            reverse=True,
        )
    )


def _rating_readiness(grade) -> str:
    if int(getattr(grade, "sample_size", 0) or 0) < 20:
        return "NEEDS_MORE_DATA"
    if float(getattr(grade, "expectancy", 0.0) or 0.0) <= 0:
        return "NOT_READY"
    if _enum_value(getattr(grade, "grade", "")) in {"A+", "A"}:
        return "WATCHLIST"
    return "RESEARCH_ONLY"


def _strongest_name(summary) -> str | None:
    return getattr(summary, "strongest", None)


def _validation_trades(calibration) -> int:
    walk = getattr(calibration, "walk_forward_intelligence_summary", None)
    if walk is not None:
        return int(getattr(walk, "validation_trades", 0) or 0)
    oos = getattr(calibration, "out_of_sample_summary", None)
    validation = getattr(oos, "validation", None)
    return int(getattr(validation, "trades", 0) or 0)


def _readiness_score(status: str) -> float:
    return {
        "READY_FOR_PAPER_TRADING": 90.0,
        "READY_FOR_REVIEW": 80.0,
        "WATCHLIST": 65.0,
        "NEEDS_MORE_DATA": 45.0,
        "NOT_READY": 20.0,
    }.get(status, 0.0)


def _confidence_status(calibration) -> str:
    if getattr(calibration, "aggregate_confidence_calibration_summary", None) is None:
        return "unavailable"
    return "available"


def _monte_carlo_status(calibration) -> str:
    report = getattr(calibration, "monte_carlo_report", None)
    if report is not None:
        return str(getattr(report, "overall_status", "available"))
    if getattr(calibration, "monte_carlo_summary", None) is not None:
        return "available"
    return "unavailable"


def _statistical_status(calibration) -> str:
    summary = getattr(calibration, "statistical_validation_summary", None)
    if summary is None:
        return "unavailable"
    return str(getattr(summary, "overall_status", "available"))


def _risk_grade(top, overfit, drawdown) -> str:
    if any("high" in item.lower() or "severe" in item.lower() for item in top):
        return "HIGH"
    if overfit or drawdown or len(top) >= 5:
        return "MEDIUM"
    if top:
        return "LOW"
    return "UNAVAILABLE"


def _first_non_empty(*values):
    for value in values:
        if value:
            return value
    return None


def _enum_value(value) -> str | None:
    if value is None:
        return None
    return str(getattr(value, "value", value))


def _grade_rank(grade: str | None) -> int:
    return {"A+": 6, "A": 5, "B": 4, "C": 3, "D": 2, "F": 1}.get(grade or "", 0)
