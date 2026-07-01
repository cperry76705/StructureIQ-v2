"""Paper-only daily reporting over existing StructureIQ advisory state."""

from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field

from core.live_market_monitor import LiveMarketMonitor
from core.paper_brokerage import PaperBrokerageEngine
from core.paper_trade_journal import PaperTradeJournal, PaperTradeJournalEntry
from core.trade_lifecycle_manager import TradeLifecycleManager


class DailyReportError(ValueError):
    """A report request was invalid or conflicted with an immutable artifact."""


class DailyReportGenerateRequest(BaseModel):
    report_date: date = Field(default_factory=date.today)
    overwrite: bool = False


class DailyReportGPTRequest(BaseModel):
    report_date: date = Field(default_factory=date.today)
    generate_if_missing: bool = True


@dataclass(frozen=True)
class DailyReportSummary:
    starting_balance: float
    ending_balance: float
    realized_pl: float
    total_r: float
    win_rate: float
    closed_trades: int
    open_trades: int
    max_drawdown_r: float
    rule_violations: int
    warnings: int


@dataclass(frozen=True)
class DailyPaperTradingReport:
    report_id: str
    report_date: str
    generated_at: str
    status: Literal["PASS", "WATCHLIST", "FAIL", "NO_TRADES"]
    summary: DailyReportSummary
    trades: tuple[dict[str, Any], ...]
    open_positions: tuple[dict[str, Any], ...]
    monitor_summary: dict[str, Any]
    lifecycle_summary: dict[str, Any]
    journal_summary: dict[str, Any]
    execution_cost_summary: dict[str, Any] | None
    setup_quality_summary: dict[str, Any] | None
    risk_summary: dict[str, Any]
    readiness_summary: dict[str, Any]
    key_findings: tuple[str, ...]
    recommended_actions: tuple[str, ...]
    human_readable_summary: str


@dataclass(frozen=True)
class DailyReportListItem:
    report_date: str
    status: str
    total_r: float
    closed_trades: int
    generated_at: str
    path: str


@dataclass(frozen=True)
class DailyReportGPTPayload:
    report_date: str
    status: str
    executive_summary: str
    metrics: dict[str, Any]
    trades: tuple[dict[str, Any], ...]
    warnings: tuple[str, ...]
    rule_violations: tuple[str, ...]
    questions_for_review: tuple[str, ...]


class DailyReportEngine:
    """Generate immutable daily paper reports without invoking trading systems."""

    def __init__(
        self,
        journal: PaperTradeJournal,
        lifecycle: TradeLifecycleManager,
        broker: PaperBrokerageEngine,
        monitor: LiveMarketMonitor,
        *,
        reports_dir: str | Path = "reports/daily",
        calibration_result: Any | None = None,
        readiness_context: Any | None = None,
        risk_context: Any | None = None,
    ) -> None:
        self.journal = journal
        self.lifecycle = lifecycle
        self.broker = broker
        self.monitor = monitor
        self.reports_dir = Path(reports_dir)
        self.calibration_result = calibration_result
        self.readiness_context = readiness_context
        self.risk_context = risk_context
        self._lock = threading.RLock()

    def generate(self, report_date: date | str | None = None, *, overwrite: bool = False) -> DailyPaperTradingReport:
        day = _date(report_date)
        path = self._path(day)
        with self._lock:
            if path.exists() and not overwrite:
                raise DailyReportError(f"daily report for {day.isoformat()} already exists")
            report = self._build(day)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(jsonable_encoder(report), indent=2), encoding="utf-8")
            return report

    def get(self, report_date: date | str) -> DailyPaperTradingReport | None:
        path = self._path(_date(report_date))
        if not path.exists():
            return None
        return _report_from_dict(json.loads(path.read_text(encoding="utf-8")))

    def list_reports(self) -> tuple[DailyReportListItem, ...]:
        if not self.reports_dir.exists():
            return ()
        items = []
        for path in sorted(self.reports_dir.glob("*.json"), reverse=True):
            try:
                report = _report_from_dict(json.loads(path.read_text(encoding="utf-8")))
            except (TypeError, ValueError, KeyError, json.JSONDecodeError):
                continue
            items.append(DailyReportListItem(
                report_date=report.report_date, status=report.status,
                total_r=report.summary.total_r,
                closed_trades=report.summary.closed_trades,
                generated_at=report.generated_at, path=str(path),
            ))
        return tuple(items)

    def latest(self) -> DailyPaperTradingReport | None:
        listed = self.list_reports()
        return self.get(listed[0].report_date) if listed else None

    def export_gpt_payload(self, report_date: date | str, *, generate_if_missing: bool = True) -> DailyReportGPTPayload:
        report = self.get(report_date)
        if report is None and generate_if_missing:
            report = self.generate(report_date)
        if report is None:
            raise DailyReportError("daily report was not found")
        warnings = tuple(
            dict.fromkeys(
                warning
                for trade in (*report.trades, *report.open_positions)
                for warning in trade.get("warnings", ())
            )
        )
        violations = tuple(
            dict.fromkeys(
                violation
                for trade in (*report.trades, *report.open_positions)
                for violation in trade.get("rule_violations", ())
            )
        )
        compact_trades = tuple({
            key: trade.get(key)
            for key in ("trade_id", "symbol", "timeframe", "setup", "strategy", "status", "realized_r", "realized_pl", "close_reason")
        } for trade in report.trades)
        return DailyReportGPTPayload(
            report_date=report.report_date, status=report.status,
            executive_summary=report.human_readable_summary,
            metrics=jsonable_encoder(report.summary), trades=compact_trades,
            warnings=warnings, rule_violations=violations,
            questions_for_review=(
                "Did any setup quality bucket underperform?",
                "Did execution costs materially reduce expectancy?",
                "Were any trades taken outside risk limits?",
            ),
        )

    def _build(self, day: date) -> DailyPaperTradingReport:
        records = self.journal.entries()
        closed = tuple(item for item in records if item.status == "closed" and _same_day(item.closed_at, day))
        open_records = tuple(item for item in records if item.status == "open" and _opened_by(item.opened_at, day))
        lifecycle_only = tuple(
            item for item in records
            if item.status in {"rejected", "expired"}
            and item.lifecycle_events
            and _same_day(item.lifecycle_events[-1].get("timestamp"), day)
        )
        returns = [float(item.realized_r or 0.0) for item in closed]
        warnings = [warning for item in (*closed, *open_records, *lifecycle_only) for warning in item.warnings]
        violations = [violation for item in (*closed, *open_records, *lifecycle_only) for violation in item.rule_violations]
        lifecycle_events = tuple(item for item in self.lifecycle.events() if _same_day(item.timestamp, day))
        monitor_events = tuple(item for item in self.monitor.events() if _same_day(item.timestamp, day))
        account = self.broker.account()
        starting = closed[0].account_balance_at_open if closed and closed[0].account_balance_at_open is not None else account.starting_balance
        ending = closed[-1].account_balance_at_close if closed and closed[-1].account_balance_at_close is not None else account.balance
        realized_pl = sum(float(item.realized_pl or 0.0) for item in closed)
        wins = sum(value > 0 for value in returns)
        max_drawdown_r = _max_drawdown(returns)
        system_errors = tuple(filter(None, (self.monitor.status().last_error, self.lifecycle.status().last_error)))
        risk_critical = account.risk_status in {"daily_loss_limit_reached", "daily_profit_lock_reached"}
        status = _status(
            closed=len(closed), opened=len(open_records), total_r=sum(returns),
            violations=len(violations), warnings=len(warnings),
            drawdown=max_drawdown_r, critical=risk_critical or bool(system_errors),
        )
        summary = DailyReportSummary(
            starting_balance=round(float(starting), 6), ending_balance=round(float(ending), 6),
            realized_pl=round(realized_pl, 6), total_r=round(sum(returns), 6),
            win_rate=round(wins / len(closed) * 100, 6) if closed else 0.0,
            closed_trades=len(closed), open_trades=len(open_records),
            max_drawdown_r=max_drawdown_r, rule_violations=len(violations), warnings=len(warnings),
        )
        findings = _findings(summary, account.risk_status, system_errors)
        actions = _actions(status, warnings, violations, system_errors)
        lifecycle_status = self.lifecycle.status()
        monitor_status = self.monitor.status()
        journal_summary = self.journal.summary()
        cost = getattr(self.calibration_result, "aggregate_execution_cost_summary", None)
        quality = getattr(self.calibration_result, "setup_quality_summary", None)
        report_date = day.isoformat()
        return DailyPaperTradingReport(
            report_id=hashlib.sha256(f"structureiq-daily:{report_date}".encode()).hexdigest()[:24],
            report_date=report_date, generated_at=_now(), status=status, summary=summary,
            trades=tuple(jsonable_encoder(item) for item in closed),
            open_positions=tuple(jsonable_encoder(item) for item in open_records),
            monitor_summary={
                "events": len(monitor_events), "signal_count": monitor_status.signal_count,
                "error_count": monitor_status.error_count, "last_error": monitor_status.last_error,
                "running": monitor_status.running,
            },
            lifecycle_summary={
                "events": len(lifecycle_events), "pending_orders": lifecycle_status.pending_orders_count,
                "rejected_candidates": sum(item.state_after == "rejected" for item in lifecycle_events),
                "expired_orders": sum(item.state_after == "expired" for item in lifecycle_events),
                "ambiguous_exits": sum(bool(item.metadata.get("same_candle_ambiguous")) for item in lifecycle_events),
                "last_error": lifecycle_status.last_error,
            },
            journal_summary=jsonable_encoder(journal_summary),
            execution_cost_summary=jsonable_encoder(cost) if cost is not None else None,
            setup_quality_summary=jsonable_encoder(quality) if quality is not None else None,
            risk_summary={"paper_risk_status": account.risk_status, "system_errors": list(system_errors), "rule_violations": violations, "warnings": warnings},
            readiness_summary=jsonable_encoder(self.readiness_context) if self.readiness_context is not None else {"status": "unavailable"},
            key_findings=findings, recommended_actions=actions,
            human_readable_summary=_human_summary(status, summary),
        )

    def _path(self, day: date) -> Path:
        return self.reports_dir / f"{day.isoformat()}.json"


def _status(*, closed: int, opened: int, total_r: float, violations: int, warnings: int, drawdown: float, critical: bool) -> str:
    if closed == 0 and opened == 0:
        return "NO_TRADES"
    if critical or violations or drawdown >= 5.0:
        return "FAIL"
    if total_r > 0 and not warnings and opened == 0:
        return "PASS"
    return "WATCHLIST"


def _findings(summary, risk_status, errors) -> tuple[str, ...]:
    output = [f"Closed {summary.closed_trades} trades for {summary.total_r:+.2f}R and {summary.realized_pl:+.2f} P/L."]
    if summary.open_trades:
        output.append(f"{summary.open_trades} paper positions remain open.")
    if risk_status != "available":
        output.append(f"Paper account risk status is {risk_status}.")
    if errors:
        output.append(f"{len(errors)} monitor/lifecycle system errors require review.")
    return tuple(output)


def _actions(status, warnings, violations, errors) -> tuple[str, ...]:
    output = []
    if violations: output.append("Review every rule violation before the next paper session.")
    if warnings: output.append("Resolve or acknowledge outstanding journal warnings.")
    if errors: output.append("Investigate monitor and lifecycle errors before continuing automation research.")
    if status == "PASS": output.append("Preserve current rules and continue collecting paper samples.")
    if status == "NO_TRADES": output.append("No action required; verify monitor availability if candidates were expected.")
    return tuple(output)


def _human_summary(status: str, summary: DailyReportSummary) -> str:
    if status == "NO_TRADES":
        return "StructureIQ recorded no open or closed paper trades for the day."
    return f"StructureIQ paper trading finished the day at {summary.total_r:+.2f}R with {summary.rule_violations} rule violations; status is {status}."


def _max_drawdown(values) -> float:
    equity = peak = worst = 0.0
    for value in values:
        equity += value; peak = max(peak, equity); worst = max(worst, peak - equity)
    return round(worst, 6)


def _same_day(value: str | None, day: date) -> bool:
    return bool(value and value[:10] == day.isoformat())


def _opened_by(value: str | None, day: date) -> bool:
    return bool(value and value[:10] <= day.isoformat())


def _date(value: date | str | None) -> date:
    if value is None: return date.today()
    if isinstance(value, date): return value
    try: return date.fromisoformat(value)
    except ValueError as exc: raise DailyReportError("report_date must be YYYY-MM-DD") from exc


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _report_from_dict(raw: dict[str, Any]) -> DailyPaperTradingReport:
    return DailyPaperTradingReport(
        **{**raw, "summary": DailyReportSummary(**raw["summary"]),
           "trades": tuple(raw.get("trades", ())), "open_positions": tuple(raw.get("open_positions", ())),
           "key_findings": tuple(raw.get("key_findings", ())), "recommended_actions": tuple(raw.get("recommended_actions", ())) }
    )


_GLOBAL_REPORT_ENGINE: DailyReportEngine | None = None
_GLOBAL_LOCK = threading.RLock()


def get_global_daily_report_engine(journal, lifecycle, broker, monitor, **kwargs) -> DailyReportEngine:
    global _GLOBAL_REPORT_ENGINE
    with _GLOBAL_LOCK:
        if _GLOBAL_REPORT_ENGINE is None or _GLOBAL_REPORT_ENGINE.journal is not journal or _GLOBAL_REPORT_ENGINE.lifecycle is not lifecycle or _GLOBAL_REPORT_ENGINE.broker is not broker or _GLOBAL_REPORT_ENGINE.monitor is not monitor:
            _GLOBAL_REPORT_ENGINE = DailyReportEngine(journal, lifecycle, broker, monitor, **kwargs)
        else:
            _GLOBAL_REPORT_ENGINE.calibration_result = kwargs.get("calibration_result")
            _GLOBAL_REPORT_ENGINE.readiness_context = kwargs.get("readiness_context")
            _GLOBAL_REPORT_ENGINE.risk_context = kwargs.get("risk_context")
        return _GLOBAL_REPORT_ENGINE


def current_daily_report_engine() -> DailyReportEngine | None:
    with _GLOBAL_LOCK:
        return _GLOBAL_REPORT_ENGINE


def reset_global_daily_report_engine() -> None:
    global _GLOBAL_REPORT_ENGINE
    with _GLOBAL_LOCK:
        _GLOBAL_REPORT_ENGINE = None
