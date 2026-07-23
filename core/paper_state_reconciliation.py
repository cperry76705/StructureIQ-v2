"""Read-only reconciliation across paper-trading state sources."""

from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi.encoders import jsonable_encoder


ReconciliationStatus = Literal["PASS", "WATCHLIST", "FAIL"]
DiscrepancySeverity = Literal["info", "warning", "critical"]


@dataclass(frozen=True)
class PaperStateDiscrepancy:
    severity: DiscrepancySeverity
    component: str
    trade_id: str | None
    message: str
    recommended_action: str


@dataclass(frozen=True)
class ReconciledTradeRecord:
    trade_id: str
    symbol: str | None
    timeframe: str | None
    status: str
    in_brokerage_open: bool
    in_brokerage_closed: bool
    in_lifecycle_open: bool
    in_lifecycle_closed: bool
    in_journal: bool
    journal_status: str | None
    source_event_id: str | None
    realized_r: float | None
    realized_pl: float | None
    lifecycle_event_count: int
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class PaperReconciliationSummary:
    status: ReconciliationStatus
    brokerage_open_positions: int
    brokerage_closed_trades: int
    lifecycle_pending_orders: int
    lifecycle_open_trades: int
    lifecycle_closed_trades: int
    journal_open_trades: int
    journal_closed_trades: int
    journal_total_r: float
    daily_report_total_r: float | None
    discrepancy_count: int
    warning_count: int
    critical_count: int
    human_readable_summary: str


@dataclass(frozen=True)
class PaperReconciliationResult:
    run_id: str
    checked_at: str
    status: ReconciliationStatus
    summary: PaperReconciliationSummary
    discrepancies: tuple[PaperStateDiscrepancy, ...]
    trades: tuple[ReconciledTradeRecord, ...]
    recommended_actions: tuple[str, ...]
    paper_only: bool
    human_readable_summary: str


class PaperStateReconciliationEngine:
    """Compare advisory paper subsystems without changing any trading state."""

    def __init__(
        self,
        *,
        broker: Any,
        lifecycle: Any,
        journal: Any,
        reports: Any,
        orchestrator: Any,
        history_path: str | Path = "reports/paper_reconciliation_history.jsonl",
    ) -> None:
        self.broker = broker
        self.lifecycle = lifecycle
        self.journal = journal
        self.reports = reports
        self.orchestrator = orchestrator
        self.history_path = Path(history_path)

    def status(self) -> PaperReconciliationSummary:
        """Return a current summary without persisting a reconciliation snapshot."""

        return self.run(persist=False).summary

    def summary(self) -> PaperReconciliationSummary:
        """Return a current summary without persisting a reconciliation snapshot."""

        return self.status()

    def discrepancies(self) -> tuple[PaperStateDiscrepancy, ...]:
        """Return current discrepancies without mutating source state."""

        return self.run(persist=False).discrepancies

    def trades(self) -> tuple[ReconciledTradeRecord, ...]:
        """Return current reconciled trade rows without mutating source state."""

        return self.run(persist=False).trades

    def run(self, *, persist: bool = True) -> PaperReconciliationResult:
        """Run a deterministic paper-state reconciliation pass."""

        checked_at = _now()
        broker_open = tuple(self.broker.open_positions())
        broker_closed = tuple(self.broker.closed_trades())
        performance = self.broker.performance()
        lifecycle_pending = tuple(self.lifecycle.pending_orders())
        lifecycle_open = tuple(self.lifecycle.open_trades())
        lifecycle_closed = tuple(self.lifecycle.closed_trades())
        lifecycle_events = tuple(self.lifecycle.events())
        journal_entries = tuple(self.journal.entries())
        journal_summary = self.journal.summary()
        latest_report = self.reports.latest()
        orchestrator_status = self.orchestrator.status()
        recent_actions = tuple(self.orchestrator.recent_actions())

        discrepancies: list[PaperStateDiscrepancy] = []
        records = _trade_records(
            broker_open, broker_closed, lifecycle_open, lifecycle_closed,
            journal_entries,
        )
        self._compare_trade_presence(records, discrepancies)
        self._compare_lifecycle_history(journal_entries, lifecycle_events, discrepancies)
        self._compare_totals(performance, journal_summary, latest_report, discrepancies)
        self._check_duplicate_trade_ids(journal_entries, broker_open, broker_closed, discrepancies)
        self._check_trade_integrity(journal_entries, discrepancies)
        self._compare_daily_report(latest_report, journal_summary, discrepancies)
        self._compare_orchestrator(
            orchestrator_status, recent_actions, journal_entries,
            lifecycle_pending, discrepancies,
        )
        self._check_pending_orders(lifecycle_pending, discrepancies)

        critical_count = sum(item.severity == "critical" for item in discrepancies)
        warning_count = sum(item.severity == "warning" for item in discrepancies)
        status: ReconciliationStatus = (
            "FAIL" if critical_count else "WATCHLIST" if warning_count else "PASS"
        )
        daily_total = (
            float(latest_report.summary.total_r)
            if latest_report is not None and getattr(latest_report, "summary", None) is not None
            else None
        )
        summary = PaperReconciliationSummary(
            status=status,
            brokerage_open_positions=len(broker_open),
            brokerage_closed_trades=len(broker_closed),
            lifecycle_pending_orders=len(lifecycle_pending),
            lifecycle_open_trades=len(lifecycle_open),
            lifecycle_closed_trades=len(lifecycle_closed),
            journal_open_trades=int(journal_summary.open_trades),
            journal_closed_trades=int(journal_summary.closed_trades),
            journal_total_r=float(journal_summary.total_r),
            daily_report_total_r=daily_total,
            discrepancy_count=len(discrepancies),
            warning_count=warning_count,
            critical_count=critical_count,
            human_readable_summary=_summary_text(
                status, len(discrepancies), warning_count, critical_count,
            ),
        )
        result = PaperReconciliationResult(
            run_id=_run_id(checked_at),
            checked_at=checked_at,
            status=status,
            summary=summary,
            discrepancies=tuple(discrepancies),
            trades=tuple(records.values()),
            recommended_actions=tuple(dict.fromkeys(item.recommended_action for item in discrepancies)),
            paper_only=True,
            human_readable_summary=summary.human_readable_summary,
        )
        if persist:
            self._persist(result)
            _set_latest(result)
        return result

    def writable(self) -> bool:
        try:
            self.history_path.parent.mkdir(parents=True, exist_ok=True)
            probe = self.history_path.parent / ".paper-reconciliation-probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            return True
        except OSError:
            return False

    def _compare_trade_presence(self, records: dict[str, ReconciledTradeRecord], discrepancies: list[PaperStateDiscrepancy]) -> None:
        for record in records.values():
            if record.in_journal and not (record.in_brokerage_open or record.in_brokerage_closed):
                severity: DiscrepancySeverity = "warning"
                if record.journal_status == "open":
                    message = "Open trade exists in the persisted journal but no open paper brokerage position exists in memory."
                    action = "If the service restarted, rebuild paper state from durable artifacts or treat this as expected persisted-history drift."
                else:
                    message = "Closed trade exists in the persisted journal but not in paper brokerage closed trades."
                    action = "Review whether paper brokerage state was reset while journal history persisted."
                discrepancies.append(PaperStateDiscrepancy(severity, "paper_brokerage", record.trade_id, message, action))
            if record.in_journal and record.journal_status == "open" and not record.in_brokerage_open:
                discrepancies.append(PaperStateDiscrepancy(
                    "warning", "paper_journal", record.trade_id,
                    "Journal marks the trade open while paper brokerage has no matching open position.",
                    "Confirm whether this is an in-memory restart gap; if not, inspect lifecycle and brokerage event history.",
                ))
            if record.in_journal and record.journal_status == "closed" and not record.in_brokerage_closed:
                discrepancies.append(PaperStateDiscrepancy(
                    "warning", "paper_journal", record.trade_id,
                    "Journal marks the trade closed while paper brokerage has no matching closed trade.",
                    "Review paper brokerage persistence expectations and journal append history.",
                ))

    def _compare_lifecycle_history(self, journal_entries: tuple[Any, ...], lifecycle_events: tuple[Any, ...], discrepancies: list[PaperStateDiscrepancy]) -> None:
        event_trade_ids = {item.trade_id for item in lifecycle_events if getattr(item, "trade_id", None)}
        for entry in journal_entries:
            history = tuple(getattr(entry, "lifecycle_events", ()) or ())
            if str(getattr(entry, "status", "")) in {"open", "closed"} and not history and getattr(entry, "trade_id", None) not in event_trade_ids:
                discrepancies.append(PaperStateDiscrepancy(
                    "warning", "trade_lifecycle_manager", entry.trade_id,
                    "Journaled trade has no lifecycle event history.",
                    "Review whether the trade was opened directly through paper brokerage or lifecycle state was lost after restart.",
                ))

    def _compare_totals(self, performance: Any, journal_summary: Any, latest_report: Any | None, discrepancies: list[PaperStateDiscrepancy]) -> None:
        broker_r = float(getattr(performance, "total_r", 0.0) or 0.0)
        journal_r = float(getattr(journal_summary, "total_r", 0.0) or 0.0)
        if not _close(broker_r, journal_r):
            severity: DiscrepancySeverity = "warning"
            if getattr(journal_summary, "closed_trades", 0) and getattr(performance, "closed_trades", 0) == 0:
                severity = "warning"
            discrepancies.append(PaperStateDiscrepancy(
                severity, "paper_brokerage", None,
                f"Paper brokerage total R ({broker_r:.4f}) differs from journal total R ({journal_r:.4f}).",
                "Determine whether in-memory paper brokerage state was reset while journal state persisted.",
            ))
        broker_pl = float(getattr(performance, "realized_pl", 0.0) or 0.0)
        journal_pl = float(getattr(journal_summary, "realized_pl", 0.0) or 0.0)
        if not _close(broker_pl, journal_pl):
            discrepancies.append(PaperStateDiscrepancy(
                "warning", "paper_brokerage", None,
                f"Paper brokerage realized P/L ({broker_pl:.4f}) differs from journal realized P/L ({journal_pl:.4f}).",
                "Review whether account state was reset or reconstructed differently from journal history.",
            ))

    def _check_duplicate_trade_ids(self, journal_entries: tuple[Any, ...], broker_open: tuple[Any, ...], broker_closed: tuple[Any, ...], discrepancies: list[PaperStateDiscrepancy]) -> None:
        journal_ids = [getattr(item, "trade_id", None) for item in journal_entries]
        for trade_id, count in Counter(item for item in journal_ids if item).items():
            if count > 1:
                discrepancies.append(PaperStateDiscrepancy(
                    "critical", "paper_state", str(trade_id),
                    f"Duplicate trade ID appears {count} times in paper journal state.",
                    "Stop paper automation and inspect brokerage/journal persistence before continuing.",
                ))
        broker_open_ids = {getattr(item, "trade_id", None) for item in broker_open}
        broker_closed_ids = {getattr(item, "trade_id", None) for item in broker_closed}
        for trade_id in sorted(item for item in broker_open_ids & broker_closed_ids if item):
            discrepancies.append(PaperStateDiscrepancy(
                "critical", "paper_brokerage", str(trade_id),
                "Trade ID is present in both paper brokerage open and closed state.",
                "Stop paper automation and inspect brokerage state before continuing.",
            ))

    def _check_trade_integrity(self, journal_entries: tuple[Any, ...], discrepancies: list[PaperStateDiscrepancy]) -> None:
        for entry in journal_entries:
            trade_id = getattr(entry, "trade_id", None)
            status = str(getattr(entry, "status", ""))
            closed_at = getattr(entry, "closed_at", None)
            opened_at = getattr(entry, "opened_at", None)
            realized_r = getattr(entry, "realized_r", None)
            realized_pl = getattr(entry, "realized_pl", None)
            if status == "open" and (closed_at is not None or realized_r is not None or realized_pl is not None):
                discrepancies.append(PaperStateDiscrepancy(
                    "critical", "paper_journal", trade_id,
                    "Trade is marked open while also containing close or realized P/L fields.",
                    "Treat journal state as corrupted for this trade and inspect append-only events.",
                ))
            if status == "closed" and closed_at is None:
                discrepancies.append(PaperStateDiscrepancy(
                    "critical", "paper_journal", trade_id,
                    "Trade is marked closed without a closed_at timestamp.",
                    "Inspect the close event and rebuild or annotate the affected journal record.",
                ))
            if opened_at and closed_at and opened_at == closed_at:
                discrepancies.append(PaperStateDiscrepancy(
                    "critical", "paper_journal", trade_id,
                    "Trade has identical opened_at and closed_at timestamps.",
                    "Verify whether the trade was duplicated or closed by an impossible lifecycle transition.",
                ))
            if realized_r is not None:
                value = float(realized_r)
                if not math.isfinite(value) or abs(value) > 100:
                    discrepancies.append(PaperStateDiscrepancy(
                        "critical", "paper_journal", trade_id,
                        f"Trade has an impossible realized R value: {value}.",
                        "Stop paper automation and inspect price geometry, risk amount, and journal persistence.",
                    ))
            if realized_r is not None and realized_pl is not None and getattr(entry, "risk_amount", None):
                expected = float(realized_r) * float(entry.risk_amount)
                actual = float(realized_pl)
                if not _close(expected, actual, tolerance=max(0.05, abs(expected) * 0.02)):
                    discrepancies.append(PaperStateDiscrepancy(
                        "critical", "paper_journal", trade_id,
                        f"Realized P/L ({actual:.4f}) is inconsistent with realized R x risk amount ({expected:.4f}).",
                        "Inspect position sizing, close price, and journaled risk amount for this trade.",
                    ))

    def _compare_daily_report(self, latest_report: Any | None, journal_summary: Any, discrepancies: list[PaperStateDiscrepancy]) -> None:
        if latest_report is None:
            return
        report_total = float(getattr(latest_report.summary, "total_r", 0.0) or 0.0)
        journal_total = float(getattr(journal_summary, "total_r", 0.0) or 0.0)
        if not _close(report_total, journal_total):
            discrepancies.append(PaperStateDiscrepancy(
                "warning", "daily_report_engine", None,
                f"Latest daily report total R ({report_total:.4f}) differs from current journal total R ({journal_total:.4f}).",
                "Regenerate the daily report for the relevant date if the journal changed after the report was written.",
            ))

    def _compare_orchestrator(
        self,
        orchestrator_status: Any,
        recent_actions: tuple[Any, ...],
        journal_entries: tuple[Any, ...],
        lifecycle_pending: tuple[Any, ...],
        discrepancies: list[PaperStateDiscrepancy],
    ) -> None:
        if journal_entries and getattr(orchestrator_status, "cycle_count", 0) and not recent_actions:
            discrepancies.append(PaperStateDiscrepancy(
                "warning", "paper_trading_orchestrator", None,
                "Orchestrator has cycle history and journaled trades, but recent actions are empty.",
                "If the service restarted this may be expected; otherwise inspect orchestrator recent-action retention.",
            ))
        pending_by_source = {item.source_event_id for item in lifecycle_pending}
        trade_sources = {getattr(item, "source_event_id", None) for item in journal_entries if getattr(item, "source_event_id", None)}
        converted_sources = {
            getattr(item, "source_event_id", None)
            for item in recent_actions
            if getattr(item, "action", "") in {"converted_to_pending_order", "converted_to_paper_trade"}
        }
        for action in recent_actions:
            if getattr(action, "action", "") != "candidate_auto_approved":
                continue
            source = getattr(action, "source_event_id", None)
            if source not in pending_by_source and source not in trade_sources and source not in converted_sources:
                discrepancies.append(PaperStateDiscrepancy(
                    "warning", "paper_trading_orchestrator", None,
                    f"Candidate {source} was auto-approved but no pending order or trade was found.",
                    "Review lifecycle approval events and recent orchestrator actions for this candidate.",
                ))

    def _check_pending_orders(self, lifecycle_pending: tuple[Any, ...], discrepancies: list[PaperStateDiscrepancy]) -> None:
        for order in lifecycle_pending:
            if self.lifecycle.monitor.find_event(order.source_event_id) is None:
                discrepancies.append(PaperStateDiscrepancy(
                    "warning", "trade_lifecycle_manager", None,
                    f"Pending order {order.order_id} references a missing monitor source event.",
                    "If the monitor restarted, recover the source event from persisted monitor history or cancel the stale pending order.",
                ))
            if int(getattr(order, "candles_evaluated", 0) or 0) >= int(getattr(order, "expires_after_candles", 0) or 0):
                discrepancies.append(PaperStateDiscrepancy(
                    "warning", "trade_lifecycle_manager", None,
                    f"Pending order {order.order_id} has reached its expiration candle count but is still active.",
                    "Run the lifecycle manager once or cancel the stale pending order.",
                ))

    def _persist(self, result: PaperReconciliationResult) -> None:
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        with self.history_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(jsonable_encoder(result), separators=(",", ":")))
            stream.write("\n")


def _trade_records(
    broker_open: tuple[Any, ...],
    broker_closed: tuple[Any, ...],
    lifecycle_open: tuple[Any, ...],
    lifecycle_closed: tuple[Any, ...],
    journal_entries: tuple[Any, ...],
) -> dict[str, ReconciledTradeRecord]:
    ids = {
        str(getattr(item, "trade_id", ""))
        for item in (*broker_open, *broker_closed, *lifecycle_open, *lifecycle_closed, *journal_entries)
        if getattr(item, "trade_id", None)
    }
    records: dict[str, ReconciledTradeRecord] = {}
    for trade_id in sorted(ids):
        bo = _find(broker_open, trade_id)
        bc = _find(broker_closed, trade_id)
        lo = _find(lifecycle_open, trade_id)
        lc = _find(lifecycle_closed, trade_id)
        je = _find(journal_entries, trade_id)
        source = je or bo or bc or lo or lc
        records[trade_id] = ReconciledTradeRecord(
            trade_id=trade_id,
            symbol=getattr(source, "symbol", None),
            timeframe=getattr(source, "timeframe", None),
            status=str(getattr(source, "status", "unknown")),
            in_brokerage_open=bo is not None,
            in_brokerage_closed=bc is not None,
            in_lifecycle_open=lo is not None,
            in_lifecycle_closed=lc is not None,
            in_journal=je is not None,
            journal_status=getattr(je, "status", None) if je is not None else None,
            source_event_id=getattr(source, "source_event_id", None),
            realized_r=getattr(source, "realized_r", None),
            realized_pl=getattr(source, "realized_pl", None),
            lifecycle_event_count=len(getattr(je, "lifecycle_events", ()) or ()) if je is not None else 0,
            warnings=tuple(getattr(je, "warnings", ()) or ()) if je is not None else (),
        )
    return records


def _find(items: tuple[Any, ...], trade_id: str) -> Any | None:
    return next((item for item in items if str(getattr(item, "trade_id", "")) == trade_id), None)


def _close(a: float, b: float, *, tolerance: float = 1e-6) -> bool:
    return abs(float(a) - float(b)) <= tolerance


def _summary_text(status: str, discrepancy_count: int, warning_count: int, critical_count: int) -> str:
    if status == "PASS":
        return "Paper brokerage, lifecycle, journal, daily report, and orchestrator state are consistent."
    if status == "WATCHLIST":
        return f"Paper reconciliation found {warning_count} warning-level differences, commonly explainable by in-memory runtime state versus persisted journal history."
    return f"Paper reconciliation found {critical_count} critical discrepancies that require review before further paper automation."


def _run_id(value: str) -> str:
    import hashlib
    return hashlib.sha256(f"paper-reconciliation:{value}".encode()).hexdigest()[:24]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


_LATEST_RECONCILIATION: PaperReconciliationResult | None = None


def _set_latest(value: PaperReconciliationResult | None) -> None:
    global _LATEST_RECONCILIATION
    _LATEST_RECONCILIATION = value


def latest_paper_reconciliation() -> PaperReconciliationResult | None:
    return _LATEST_RECONCILIATION
