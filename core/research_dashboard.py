"""Compact, read-only dashboard summaries over existing StructureIQ research."""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Any

from app.config import APP_VERSION
from core.research_engine import ResearchEngine, ResearchWindow
from core.symbol_profile_engine import SymbolProfileEngine
from core.live_market_monitor import current_live_market_monitor_status
from core.paper_brokerage import current_paper_brokerage
from core.trade_lifecycle_manager import current_trade_lifecycle_manager
from core.paper_trade_journal import current_paper_trade_journal
from core.daily_report_engine import current_daily_report_engine
from core.paper_trading_orchestrator import current_paper_trading_orchestrator
from core.daily_report_scheduler import current_daily_report_scheduler
from core.system_health import latest_system_health
from core.system_validation import latest_system_validation
from core.continuous_paper_trading import current_continuous_paper_trading
from core.candidate_diagnostics import current_candidate_diagnostics
from core.calibration_analytics import get_global_calibration_analytics


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
    live_monitor_status: str = "not_enabled"
    last_monitor_signal_time: str | None = None
    recent_monitor_signal_count: int = 0
    monitor_error_count: int = 0
    monitor_ready_for_paper_trading: bool = False
    paper_account_balance: float | None = None
    paper_equity: float | None = None
    paper_open_positions_count: int = 0
    paper_closed_trades_count: int = 0
    paper_total_r: float = 0.0
    paper_win_rate: float = 0.0
    paper_max_drawdown: float = 0.0
    paper_risk_status: str = "unavailable"
    paper_trading_enabled: bool = False
    lifecycle_enabled: bool = False
    pending_orders_count: int = 0
    lifecycle_open_trades_count: int = 0
    lifecycle_closed_trades_count: int = 0
    expired_orders_count: int = 0
    rejected_candidates_count: int = 0
    ambiguous_exit_count: int = 0
    lifecycle_status: str = "unavailable"
    journal_status: str = "unavailable"
    journaled_trade_count: int = 0
    latest_journaled_trade: str | None = None
    journal_rule_violations: int = 0
    journal_warnings: tuple[str, ...] = ()
    journal_ready_for_daily_reports: bool = False
    latest_daily_report_date: str | None = None
    latest_daily_report_status: str = "unavailable"
    daily_report_ready: bool = False
    daily_report_warning_count: int = 0
    daily_report_rule_violation_count: int = 0
    daily_report_total_r: float = 0.0
    daily_report_summary: str | None = None
    paper_trading_orchestrator_status: str = "unavailable"
    last_paper_trading_cycle: str | None = None
    orchestrator_running: bool = False
    orchestrator_paused: bool = False
    total_cycles: int = 0
    total_candidates_seen: int = 0
    total_trades_opened: int = 0
    total_reports_generated: int = 0
    orchestrator_warnings: tuple[str, ...] = ()
    daily_report_scheduler_running: bool = False
    daily_report_scheduler_paused: bool = False
    daily_report_scheduler_last_run: str | None = None
    daily_report_scheduler_next_run: str | None = None
    daily_report_scheduler_last_status: str | None = None
    daily_report_scheduler_error_count: int = 0
    scheduled_reporting_ready: bool = False
    system_health_status: str = "unavailable"
    system_health_score: float = 0.0
    system_blocking_issue_count: int = 0
    system_warning_count: int = 0
    paper_trading_operational_readiness: str = "NOT_READY"
    latest_health_check_at: str | None = None
    health_recommended_actions: tuple[str, ...] = ()
    latest_validation_status: str = "unavailable"
    validation_score: float = 0.0
    validation_timestamp: str | None = None
    continuous_runtime_ready: bool = False
    validation_paper_trading_ready: bool = False
    validation_blocking_issue_count: int = 0
    validation_recommendations: tuple[str, ...] = ()
    continuous_paper_running: bool = False
    continuous_paper_paused: bool = False
    continuous_paper_session_id: str | None = None
    continuous_paper_cycle_count: int = 0
    continuous_paper_last_cycle_status: str | None = None
    continuous_paper_last_validation_status: str | None = None
    continuous_paper_last_health_status: str | None = None
    continuous_paper_error_count: int = 0
    continuous_paper_pause_reasons: tuple[str, ...] = ()
    continuous_paper_total_trades_opened: int = 0
    continuous_paper_total_reports_generated: int = 0
    continuous_paper_readiness: str = "NOT_STARTED"
    candidate_markets_analyzed: int = 0
    candidate_candidates_created: int = 0
    candidate_rate_percent: float = 0.0
    candidate_average_confidence: float = 0.0
    candidate_average_setup_quality: float = 0.0
    candidate_top_rejection_reason: str | None = None
    candidate_closest_missed_setup: str | None = None
    candidate_highest_rejected_confidence: float | None = None
    candidate_highest_rejected_quality: float | None = None
    candidate_highest_rejected_score: float | None = None
    calibration_confidence_distribution_summary: str | None = None
    calibration_candidate_conversion_rate: float = 0.0
    calibration_top_rejection_reason: str | None = None
    calibration_closest_missed_candidate: str | None = None
    calibration_best_symbol_by_candidate_rate: str | None = None
    calibration_weakest_symbol_by_average_score: str | None = None
    calibration_most_common_market_regime: str | None = None
    calibration_analytics_summary: str | None = None


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
    live_monitor_status: str = "not_enabled"
    monitor_ready_for_paper_trading: bool = False
    monitor_errors: int = 0
    paper_brokerage_status: str = "unavailable"
    paper_trading_enabled: bool = False
    paper_risk_status: str = "unavailable"
    lifecycle_enabled: bool = False
    lifecycle_status: str = "unavailable"
    lifecycle_warnings: tuple[str, ...] = ()
    latest_daily_report_status: str = "unavailable"
    daily_report_ready: bool = False
    paper_trading_orchestrator_status: str = "unavailable"
    orchestrator_paused: bool = False
    orchestrator_warnings: tuple[str, ...] = ()
    daily_report_scheduler_running: bool = False
    daily_report_scheduler_paused: bool = False
    scheduled_reporting_ready: bool = False
    system_health_status: str = "unavailable"
    system_health_score: float = 0.0
    paper_trading_operational_readiness: str = "NOT_READY"
    health_recommended_actions: tuple[str, ...] = ()
    latest_validation_status: str = "unavailable"
    validation_score: float = 0.0
    continuous_runtime_ready: bool = False
    validation_paper_trading_ready: bool = False
    validation_recommendations: tuple[str, ...] = ()
    continuous_paper_running: bool = False
    continuous_paper_paused: bool = False
    continuous_paper_readiness: str = "NOT_STARTED"
    continuous_paper_pause_reasons: tuple[str, ...] = ()


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
    monitor_errors: tuple[str, ...] = ()
    live_monitor_status: str = "not_enabled"
    paper_risk_status: str = "unavailable"
    paper_risk_warnings: tuple[str, ...] = ()
    lifecycle_status: str = "unavailable"
    lifecycle_warnings: tuple[str, ...] = ()
    journal_status: str = "unavailable"
    journal_warnings: tuple[str, ...] = ()
    journal_rule_violations: int = 0
    latest_daily_report_status: str = "unavailable"
    daily_report_warnings: tuple[str, ...] = ()
    paper_trading_orchestrator_status: str = "unavailable"
    orchestrator_warnings: tuple[str, ...] = ()
    daily_report_scheduler_error_count: int = 0
    daily_report_scheduler_last_status: str | None = None
    scheduler_warnings: tuple[str, ...] = ()
    system_health_status: str = "unavailable"
    system_blocking_issues: tuple[str, ...] = ()
    system_health_warnings: tuple[str, ...] = ()
    latest_validation_status: str = "unavailable"
    validation_blocking_issues: tuple[str, ...] = ()
    validation_warnings: tuple[str, ...] = ()
    continuous_paper_status: str = "not_started"
    continuous_paper_warnings: tuple[str, ...] = ()


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
        monitor = current_live_market_monitor_status()
        paper_broker = current_paper_brokerage()
        paper = paper_broker.account() if paper_broker is not None else None
        lifecycle_manager = current_trade_lifecycle_manager()
        lifecycle = lifecycle_manager.status() if lifecycle_manager is not None else None
        journal = current_paper_trade_journal()
        journal_summary = journal.summary() if journal is not None else None
        journal_entries = journal.entries() if journal is not None else ()
        report_engine = current_daily_report_engine()
        latest_report = report_engine.latest() if report_engine is not None else None
        orchestrator = current_paper_trading_orchestrator()
        orchestrator_status = orchestrator.status() if orchestrator is not None else None
        orchestrator_warnings = (
            (str(orchestrator_status.last_error),)
            if orchestrator_status is not None and orchestrator_status.last_error else ()
        )
        scheduler = current_daily_report_scheduler()
        scheduler_status = scheduler.status() if scheduler is not None else None
        health = latest_system_health()
        validation = latest_system_validation()
        continuous = current_continuous_paper_trading()
        continuous_status = continuous.status() if continuous is not None else None
        diagnostic_engine = current_candidate_diagnostics()
        candidate_summary = diagnostic_engine.summary() if diagnostic_engine is not None else None
        calibration_summary = get_global_calibration_analytics().summary()
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
            live_monitor_status=("running" if monitor and monitor.running else "stopped" if monitor else "not_enabled"),
            last_monitor_signal_time=getattr(monitor, "last_signal_time", None),
            recent_monitor_signal_count=int(getattr(monitor, "recent_signal_count", 0) or 0),
            monitor_error_count=int(getattr(monitor, "error_count", 0) or 0),
            monitor_ready_for_paper_trading=bool(getattr(monitor, "ready_for_paper_trading", False)),
            paper_account_balance=getattr(paper, "balance", None),
            paper_equity=getattr(paper, "equity", None),
            paper_open_positions_count=int(getattr(paper, "open_positions_count", 0) or 0),
            paper_closed_trades_count=int(getattr(paper, "closed_trades_count", 0) or 0),
            paper_total_r=float(getattr(paper, "paper_total_r", 0.0) or 0.0),
            paper_win_rate=float(getattr(paper, "paper_win_rate", 0.0) or 0.0),
            paper_max_drawdown=float(getattr(paper, "paper_max_drawdown", 0.0) or 0.0),
            paper_risk_status=str(getattr(paper, "risk_status", "unavailable")),
            paper_trading_enabled=False,
            lifecycle_enabled=bool(getattr(lifecycle, "lifecycle_enabled", False)),
            pending_orders_count=int(getattr(lifecycle, "pending_orders_count", 0) or 0),
            lifecycle_open_trades_count=int(getattr(lifecycle, "lifecycle_open_trades_count", 0) or 0),
            lifecycle_closed_trades_count=int(getattr(lifecycle, "lifecycle_closed_trades_count", 0) or 0),
            expired_orders_count=int(getattr(lifecycle, "expired_orders_count", 0) or 0),
            rejected_candidates_count=int(getattr(lifecycle, "rejected_candidates_count", 0) or 0),
            ambiguous_exit_count=int(getattr(lifecycle, "ambiguous_exit_count", 0) or 0),
            lifecycle_status=str(getattr(lifecycle, "lifecycle_status", "unavailable")),
            journal_status="available" if journal is not None else "unavailable",
            journaled_trade_count=int(getattr(journal_summary, "total_journaled_trades", 0) or 0),
            latest_journaled_trade=(journal_entries[-1].trade_id if journal_entries else None),
            journal_rule_violations=int(getattr(journal_summary, "rule_violation_count", 0) or 0),
            journal_warnings=tuple(
                dict.fromkeys(warning for entry in journal_entries for warning in entry.warnings)
            ),
            journal_ready_for_daily_reports=bool(journal_entries),
            latest_daily_report_date=getattr(latest_report, "report_date", None),
            latest_daily_report_status=str(getattr(latest_report, "status", "unavailable")),
            daily_report_ready=latest_report is not None,
            daily_report_warning_count=int(getattr(getattr(latest_report, "summary", None), "warnings", 0) or 0),
            daily_report_rule_violation_count=int(getattr(getattr(latest_report, "summary", None), "rule_violations", 0) or 0),
            daily_report_total_r=float(getattr(getattr(latest_report, "summary", None), "total_r", 0.0) or 0.0),
            daily_report_summary=getattr(latest_report, "human_readable_summary", None),
            paper_trading_orchestrator_status=(
                "paused" if orchestrator_status and orchestrator_status.paused
                else "running" if orchestrator_status and orchestrator_status.running
                else "stopped_advisory" if orchestrator_status else "unavailable"
            ),
            last_paper_trading_cycle=getattr(orchestrator_status, "last_cycle_id", None),
            orchestrator_running=bool(getattr(orchestrator_status, "running", False)),
            orchestrator_paused=bool(getattr(orchestrator_status, "paused", False)),
            total_cycles=int(getattr(orchestrator_status, "cycle_count", 0) or 0),
            total_candidates_seen=int(getattr(orchestrator_status, "total_candidates_seen", 0) or 0),
            total_trades_opened=int(getattr(orchestrator_status, "total_trades_opened", 0) or 0),
            total_reports_generated=int(getattr(orchestrator_status, "total_reports_generated", 0) or 0),
            orchestrator_warnings=orchestrator_warnings,
            daily_report_scheduler_running=bool(getattr(scheduler_status, "running", False)),
            daily_report_scheduler_paused=bool(getattr(scheduler_status, "paused", False)),
            daily_report_scheduler_last_run=getattr(scheduler_status, "last_run_at", None),
            daily_report_scheduler_next_run=getattr(scheduler_status, "next_run_at", None),
            daily_report_scheduler_last_status=getattr(scheduler_status, "last_report_status", None),
            daily_report_scheduler_error_count=int(getattr(scheduler_status, "error_count", 0) or 0),
            scheduled_reporting_ready=bool(scheduler_status is not None and not scheduler_status.paused),
            system_health_status=str(getattr(health, "status", "unavailable")),
            system_health_score=float(getattr(health, "score", 0.0) or 0.0),
            system_blocking_issue_count=len(getattr(health, "blocking_issues", ()) or ()),
            system_warning_count=len(getattr(health, "warnings", ()) or ()),
            paper_trading_operational_readiness=str(getattr(health, "paper_trading_operational_readiness", "NOT_READY")),
            latest_health_check_at=getattr(health, "checked_at", None),
            health_recommended_actions=tuple(getattr(health, "recommended_actions", ()) or ()),
            latest_validation_status=str(getattr(validation, "validation_status", "unavailable")),
            validation_score=float(getattr(validation, "overall_score", 0.0) or 0.0),
            validation_timestamp=getattr(validation, "completed_at", None),
            continuous_runtime_ready=bool(getattr(validation, "continuous_runtime_ready", False)),
            validation_paper_trading_ready=bool(getattr(validation, "paper_trading_ready", False)),
            validation_blocking_issue_count=len(getattr(validation, "blocking_issues", ()) or ()),
            validation_recommendations=tuple(getattr(validation, "recommendations", ()) or ()),
            continuous_paper_running=bool(getattr(continuous_status, "running", False)),
            continuous_paper_paused=bool(getattr(continuous_status, "paused", False)),
            continuous_paper_session_id=getattr(continuous_status, "session_id", None),
            continuous_paper_cycle_count=int(getattr(continuous_status, "cycle_count", 0) or 0),
            continuous_paper_last_cycle_status=getattr(continuous_status, "last_cycle_status", None),
            continuous_paper_last_validation_status=getattr(continuous_status, "last_validation_status", None),
            continuous_paper_last_health_status=getattr(continuous_status, "last_health_status", None),
            continuous_paper_error_count=int(getattr(continuous_status, "error_count", 0) or 0),
            continuous_paper_pause_reasons=tuple(getattr(continuous_status, "pause_reasons", ()) or ()),
            continuous_paper_total_trades_opened=int(getattr(continuous_status, "total_trades_opened", 0) or 0),
            continuous_paper_total_reports_generated=int(getattr(continuous_status, "total_reports_generated", 0) or 0),
            continuous_paper_readiness=("PAUSED" if getattr(continuous_status, "paused", False) else "RUNNING" if getattr(continuous_status, "running", False) else "STOPPED" if continuous_status else "NOT_STARTED"),
            candidate_markets_analyzed=int(getattr(candidate_summary, "markets_analyzed", 0) or 0),
            candidate_candidates_created=int(getattr(candidate_summary, "candidates_created", 0) or 0),
            candidate_rate_percent=float(getattr(candidate_summary, "candidate_rate_percent", 0.0) or 0.0),
            candidate_average_confidence=float(getattr(candidate_summary, "average_confidence", 0.0) or 0.0),
            candidate_average_setup_quality=float(getattr(candidate_summary, "average_setup_quality", 0.0) or 0.0),
            candidate_top_rejection_reason=getattr(candidate_summary, "most_common_rejection_reason", None),
            candidate_closest_missed_setup=getattr(getattr(candidate_summary, "closest_missed_candidate", None), "best_setup_name", None),
            candidate_highest_rejected_confidence=getattr(candidate_summary, "highest_confidence_rejected", None),
            candidate_highest_rejected_quality=getattr(candidate_summary, "highest_setup_quality_rejected", None),
            candidate_highest_rejected_score=getattr(candidate_summary, "highest_score_rejected", None),
            calibration_confidence_distribution_summary=calibration_summary.confidence_distribution_summary,
            calibration_candidate_conversion_rate=calibration_summary.candidate_conversion_rate,
            calibration_top_rejection_reason=calibration_summary.top_rejection_reason,
            calibration_closest_missed_candidate=(calibration_summary.closest_missed_candidate or {}).get("symbol"),
            calibration_best_symbol_by_candidate_rate=calibration_summary.best_symbol_by_candidate_rate,
            calibration_weakest_symbol_by_average_score=calibration_summary.weakest_symbol_by_average_score,
            calibration_most_common_market_regime=calibration_summary.most_common_market_regime,
            calibration_analytics_summary=calibration_summary.human_readable_summary,
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
            live_monitor_status=(
                "running" if (monitor := current_live_market_monitor_status()) and monitor.running
                else "stopped" if monitor else "not_enabled"
            ),
            monitor_ready_for_paper_trading=bool(getattr(monitor, "ready_for_paper_trading", False)),
            monitor_errors=int(getattr(monitor, "error_count", 0) or 0),
            paper_brokerage_status=("available_advisory" if current_paper_brokerage() is not None else "unavailable"),
            paper_trading_enabled=False,
            paper_risk_status=(
                current_paper_brokerage().account().risk_status
                if current_paper_brokerage() is not None else "unavailable"
            ),
            lifecycle_enabled=bool(getattr((lifecycle := current_trade_lifecycle_manager().status() if current_trade_lifecycle_manager() is not None else None), "lifecycle_enabled", False)),
            lifecycle_status=str(getattr(lifecycle, "lifecycle_status", "unavailable")),
            lifecycle_warnings=(
                (str(lifecycle.last_error),) if lifecycle is not None and lifecycle.last_error else ()
            ),
            latest_daily_report_status=(
                current_daily_report_engine().latest().status
                if current_daily_report_engine() is not None and current_daily_report_engine().latest() is not None
                else "unavailable"
            ),
            daily_report_ready=(
                current_daily_report_engine() is not None and current_daily_report_engine().latest() is not None
            ),
            paper_trading_orchestrator_status=(
                "paused" if (orchestrator := current_paper_trading_orchestrator()) is not None and orchestrator.status().paused
                else "running" if orchestrator is not None and orchestrator.status().running
                else "stopped_advisory" if orchestrator is not None else "unavailable"
            ),
            orchestrator_paused=bool(orchestrator is not None and orchestrator.status().paused),
            orchestrator_warnings=(
                (str(orchestrator.status().last_error),)
                if orchestrator is not None and orchestrator.status().last_error else ()
            ),
            daily_report_scheduler_running=bool(
                (scheduler := current_daily_report_scheduler()) is not None and scheduler.status().running
            ),
            daily_report_scheduler_paused=bool(scheduler is not None and scheduler.status().paused),
            scheduled_reporting_ready=bool(scheduler is not None and not scheduler.status().paused),
            system_health_status=str(getattr((health := latest_system_health()), "status", "unavailable")),
            system_health_score=float(getattr(health, "score", 0.0) or 0.0),
            paper_trading_operational_readiness=str(getattr(health, "paper_trading_operational_readiness", "NOT_READY")),
            health_recommended_actions=tuple(getattr(health, "recommended_actions", ()) or ()),
            latest_validation_status=str(getattr((validation := latest_system_validation()), "validation_status", "unavailable")),
            validation_score=float(getattr(validation, "overall_score", 0.0) or 0.0),
            continuous_runtime_ready=bool(getattr(validation, "continuous_runtime_ready", False)),
            validation_paper_trading_ready=bool(getattr(validation, "paper_trading_ready", False)),
            validation_recommendations=tuple(getattr(validation, "recommendations", ()) or ()),
            continuous_paper_running=bool(getattr((continuous_status := current_continuous_paper_trading().status() if current_continuous_paper_trading() else None), "running", False)),
            continuous_paper_paused=bool(getattr(continuous_status, "paused", False)),
            continuous_paper_readiness=("PAUSED" if getattr(continuous_status, "paused", False) else "RUNNING" if getattr(continuous_status, "running", False) else "STOPPED" if continuous_status else "NOT_STARTED"),
            continuous_paper_pause_reasons=tuple(getattr(continuous_status, "pause_reasons", ()) or ()),
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
        monitor = current_live_market_monitor_status()
        monitor_errors = (
            (str(monitor.last_error),)
            if monitor is not None and monitor.last_error else ()
        )
        paper_broker = current_paper_brokerage()
        paper = paper_broker.account() if paper_broker is not None else None
        paper_warnings = (
            (f"Paper brokerage risk status is {paper.risk_status}.",)
            if paper is not None and paper.risk_status != "available" else ()
        )
        lifecycle_manager = current_trade_lifecycle_manager()
        lifecycle = lifecycle_manager.status() if lifecycle_manager is not None else None
        lifecycle_warnings = (
            (str(lifecycle.last_error),) if lifecycle is not None and lifecycle.last_error else ()
        )
        journal = current_paper_trade_journal()
        journal_summary = journal.summary() if journal is not None else None
        journal_entries = journal.entries() if journal is not None else ()
        journal_warnings = tuple(dict.fromkeys(warning for entry in journal_entries for warning in entry.warnings))
        report_engine = current_daily_report_engine()
        latest_report = report_engine.latest() if report_engine is not None else None
        daily_warnings = tuple(
            str(item) for item in getattr(latest_report, "key_findings", ())
            if "warning" in str(item).lower() or "error" in str(item).lower() or "risk" in str(item).lower()
        )
        orchestrator = current_paper_trading_orchestrator()
        orchestrator_status = orchestrator.status() if orchestrator is not None else None
        orchestrator_warnings = (
            (str(orchestrator_status.last_error),)
            if orchestrator_status is not None and orchestrator_status.last_error else ()
        )
        scheduler = current_daily_report_scheduler()
        scheduler_status = scheduler.status() if scheduler is not None else None
        scheduler_warnings = (
            (str(scheduler_status.last_error),)
            if scheduler_status is not None and scheduler_status.last_error else ()
        )
        health = latest_system_health()
        health_blockers = tuple(getattr(health, "blocking_issues", ()) or ())
        health_warnings = tuple(getattr(health, "warnings", ()) or ())
        validation = latest_system_validation()
        validation_blockers = tuple(getattr(validation, "blocking_issues", ()) or ())
        validation_warnings = tuple(getattr(validation, "warnings", ()) or ())
        continuous = current_continuous_paper_trading()
        continuous_status = continuous.status() if continuous is not None else None
        continuous_warnings = tuple(getattr(continuous_status, "pause_reasons", ()) or ())
        top = tuple(
            dict.fromkeys((*continuous_warnings, *validation_blockers, *validation_warnings, *health_blockers, *health_warnings, *scheduler_warnings, *orchestrator_warnings, *journal_warnings, *lifecycle_warnings, *paper_warnings, *monitor_errors, *execution_warnings, *overfit, *drawdown, *low_sample, *calibration, *confidence, *provider))
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
            monitor_errors=monitor_errors,
            live_monitor_status=("running" if monitor and monitor.running else "stopped" if monitor else "not_enabled"),
            paper_risk_status=str(getattr(paper, "risk_status", "unavailable")),
            paper_risk_warnings=paper_warnings,
            lifecycle_status=str(getattr(lifecycle, "lifecycle_status", "unavailable")),
            lifecycle_warnings=lifecycle_warnings,
            journal_status="available" if journal is not None else "unavailable",
            journal_warnings=journal_warnings,
            journal_rule_violations=int(getattr(journal_summary, "rule_violation_count", 0) or 0),
            latest_daily_report_status=str(getattr(latest_report, "status", "unavailable")),
            daily_report_warnings=daily_warnings,
            paper_trading_orchestrator_status=(
                "paused" if orchestrator_status and orchestrator_status.paused
                else "running" if orchestrator_status and orchestrator_status.running
                else "stopped_advisory" if orchestrator_status else "unavailable"
            ),
            orchestrator_warnings=orchestrator_warnings,
            daily_report_scheduler_error_count=int(getattr(scheduler_status, "error_count", 0) or 0),
            daily_report_scheduler_last_status=getattr(scheduler_status, "last_report_status", None),
            scheduler_warnings=scheduler_warnings,
            system_health_status=str(getattr(health, "status", "unavailable")),
            system_blocking_issues=health_blockers,
            system_health_warnings=health_warnings,
            latest_validation_status=str(getattr(validation, "validation_status", "unavailable")),
            validation_blocking_issues=validation_blockers,
            validation_warnings=validation_warnings,
            continuous_paper_status=("paused" if getattr(continuous_status, "paused", False) else "running" if getattr(continuous_status, "running", False) else "stopped" if continuous_status else "not_started"),
            continuous_paper_warnings=continuous_warnings,
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
        monitor = current_live_market_monitor_status()
        if monitor is not None and monitor.last_error:
            yield (
                "live_monitor",
                f"Live monitor reported an error: {monitor.last_error}",
                "medium",
                "Review provider availability and monitor configuration; do not enable paper execution.",
                "Live Market Monitor",
            )
        paper_broker = current_paper_brokerage()
        if paper_broker is not None:
            paper = paper_broker.account()
            yield (
                "paper_brokerage",
                f"Paper account has {paper.open_positions_count} open and {paper.closed_trades_count} closed simulated trades; risk status is {paper.risk_status}.",
                "medium" if paper.risk_status != "available" else "low",
                "Continue explicit advisory paper testing; automated lifecycle management remains disabled.",
                "Paper Brokerage Engine",
            )
        lifecycle_manager = current_trade_lifecycle_manager()
        if lifecycle_manager is not None:
            lifecycle = lifecycle_manager.status()
            if lifecycle.last_error or lifecycle.ambiguous_exit_count or lifecycle.expired_orders_count:
                yield (
                    "trade_lifecycle",
                    f"Lifecycle has {lifecycle.expired_orders_count} expired orders, {lifecycle.ambiguous_exit_count} ambiguous exits, and last error {lifecycle.last_error or 'none'}.",
                    "medium",
                    "Review paper lifecycle events; keep automated paper candidate consumption disabled until validated.",
                    "Trade Lifecycle Manager",
                )
        journal = current_paper_trade_journal()
        if journal is not None:
            summary = journal.summary()
            if summary.rule_violation_count or summary.most_common_warning:
                yield (
                    "paper_journal",
                    f"Paper journal has {summary.rule_violation_count} rule violations; most common warning is {summary.most_common_warning or 'none'}.",
                    "medium",
                    "Review journal evidence before enabling any automated paper workflow.",
                    "Automated Paper Trade Journal",
                )
        report_engine = current_daily_report_engine()
        latest_report = report_engine.latest() if report_engine is not None else None
        if latest_report is not None and latest_report.status in {"WATCHLIST", "FAIL"}:
            yield (
                "daily_report",
                latest_report.human_readable_summary,
                "high" if latest_report.status == "FAIL" else "medium",
                "Review the saved daily report findings before the next paper session.",
                "Daily Paper Trading Report Engine",
            )
        orchestrator = current_paper_trading_orchestrator()
        if orchestrator is not None:
            state = orchestrator.status()
            if state.paused or state.last_error:
                yield (
                    "paper_trading_orchestrator",
                    f"Paper orchestrator is {'paused' if state.paused else 'degraded'}; last error is {state.last_error or 'none'}.",
                    "high" if state.paused else "medium",
                    "Keep auto-approval disabled and review recent cycle actions and errors.",
                    "End-to-End Paper Trading Orchestrator",
                )
        scheduler = current_daily_report_scheduler()
        if scheduler is not None:
            state = scheduler.status()
            if state.paused or state.last_error:
                yield (
                    "daily_report_scheduler",
                    f"Daily report scheduler is {'paused' if state.paused else 'degraded'}; last error is {state.last_error or 'none'}.",
                    "high" if state.paused else "medium",
                    "Review local report generation and scheduler history before restarting.",
                    "Scheduled Daily Report Automation",
                )
        continuous = current_continuous_paper_trading()
        if continuous is not None:
            state = continuous.status()
            if state.paused or state.error_count:
                yield (
                    "continuous_paper_trading",
                    state.human_readable_summary,
                    "high" if state.paused else "medium",
                    "Review runtime safety events and resolve every pause reason before resuming.",
                    "Continuous Autonomous Paper Trading",
                )
        health = latest_system_health()
        if health is not None and health.status in {"WATCHLIST", "FAIL"}:
            yield (
                "system_health",
                health.human_readable_summary,
                "high" if health.status == "FAIL" else "medium",
                health.recommended_actions[0] if health.recommended_actions else "Review system health dimensions.",
                "System Health and Observability",
            )
        validation = latest_system_validation()
        if validation is not None and validation.validation_status in {"WATCHLIST", "FAIL"}:
            yield (
                "system_validation",
                validation.human_readable_summary,
                "high" if validation.validation_status == "FAIL" else "medium",
                validation.recommendations[0] if validation.recommendations else "Review validation component results.",
                "End-to-End Validation Harness",
            )
        if monitor is not None and monitor.signal_count and not monitor.last_error:
            yield (
                "live_monitor",
                f"The monitor has observed {monitor.signal_count} advisory candidate signals.",
                "low",
                "Review candidate quality manually; paper-trade creation remains disabled.",
                "Live Market Monitor",
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
