"""Read-only paper journal integrity, quarantine, and root-cause audits.

The audit layer classifies persisted paper-trade records and reports data
quality issues without deleting, rewriting, approving, filling, closing, or
otherwise mutating trading state.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from core.integrity_remediation import (
    RemediationRegistry,
    ValidationBaselineManager,
    enhanced_summary,
)


CLASSIFICATIONS = (
    "VALID_RUNTIME",
    "VALID_HISTORICAL",
    "LEGACY_IMPORT",
    "TEST_FIXTURE",
    "SYNTHETIC",
    "ORPHANED",
    "DUPLICATE",
    "CORRUPTED",
    "INCOMPLETE",
    "UNKNOWN",
)

QUARANTINE_REASONS = (
    "duplicate",
    "legacy_import",
    "synthetic",
    "test_fixture",
    "timestamp_corruption",
    "missing_lifecycle",
    "invalid_transition",
    "invalid_state",
)


@dataclass(frozen=True)
class IntegrityIssue:
    trade_id: str | None
    campaign_id: str | None
    severity: str
    component: str
    root_cause: str
    recommended_action: str


@dataclass(frozen=True)
class JournalIntegrityRecord:
    trade_id: str | None
    source_event_id: str | None
    campaign_id: str | None
    symbol: str | None
    status: str | None
    classification: str
    quarantine_status: str | None
    quarantine_reasons: tuple[str, ...]
    issue_count: int
    lifecycle_event_count: int
    opened_at: str | None
    closed_at: str | None
    human_readable_summary: str


@dataclass(frozen=True)
class DuplicateReport:
    duplicate_trade_ids: dict[str, int]
    duplicate_lifecycle_ids: dict[str, int]
    duplicate_brokerage_ids: dict[str, int]
    duplicate_source_event_ids: dict[str, int]
    duplicate_execution_chains: dict[str, int]
    duplicate_journal_entries: dict[str, int]
    duplicate_campaign_membership: dict[str, int]
    duplicate_closes: dict[str, int]
    duplicate_opens: dict[str, int]
    impossible_state_transitions: tuple[IntegrityIssue, ...]
    human_readable_summary: str


@dataclass(frozen=True)
class LifecycleAudit:
    missing_lifecycle: tuple[IntegrityIssue, ...]
    duplicate_events: tuple[IntegrityIssue, ...]
    impossible_ordering: tuple[IntegrityIssue, ...]
    orphan_lifecycle: tuple[IntegrityIssue, ...]
    human_readable_summary: str


@dataclass(frozen=True)
class TimestampAudit:
    missing_timestamps: tuple[IntegrityIssue, ...]
    closed_before_opened: tuple[IntegrityIssue, ...]
    identical_open_close: tuple[IntegrityIssue, ...]
    negative_durations: tuple[IntegrityIssue, ...]
    future_timestamps: tuple[IntegrityIssue, ...]
    timezone_inconsistencies: tuple[IntegrityIssue, ...]
    human_readable_summary: str


@dataclass(frozen=True)
class QuarantineSummary:
    quarantined_count: int
    reasons: dict[str, int]
    trade_ids: tuple[str, ...]
    records: tuple[JournalIntegrityRecord, ...]
    human_readable_summary: str


@dataclass(frozen=True)
class RootCauseReport:
    trade_id: str
    found: bool
    originated_from: str | None
    component_created: str | None
    campaign_id: str | None
    lifecycle_id: str | None
    brokerage_id: str | None
    source_event_id: str | None
    duplicated: bool
    timestamps_corrupted: bool
    lifecycle_events_missing: bool
    deterministic_recovery_fixture: bool
    historical_import: bool
    production_campaign: bool
    classification: str
    root_cause: str
    recommended_action: str


@dataclass(frozen=True)
class JournalIntegritySummary:
    status: str
    safe_mode_required: bool
    total_records: int
    classification_counts: dict[str, int]
    issue_count: int
    critical_count: int
    warning_count: int
    quarantined_count: int
    duplicate_report: DuplicateReport
    lifecycle_audit: LifecycleAudit
    timestamp_audit: TimestampAudit
    quarantine: QuarantineSummary
    records: tuple[JournalIntegrityRecord, ...]
    issues: tuple[IntegrityIssue, ...]
    human_readable_summary: str
    raw_record_count: int = 0
    eligible_runtime_records: int = 0
    eligible_performance_records: int = 0
    quarantined_records: int = 0
    legacy_records: int = 0
    test_fixture_records: int = 0
    corrupted_records: int = 0
    incomplete_records: int = 0
    unresolved_critical_records: int = 0
    resolved_critical_records: int = 0
    safe_mode_status: str = "ACTIVE"
    baseline_status: str = "MISSING"
    latest_baseline_id: str | None = None
    ready_for_validation: bool = False


class JournalIntegrityAuditor:
    """Audit paper journal, lifecycle, brokerage, and campaign relationships."""

    def __init__(
        self,
        *,
        journal: Any | None = None,
        broker: Any | None = None,
        lifecycle: Any | None = None,
        campaigns: Any | None = None,
        journal_path: str | Path = "research/paper_trade_journal.jsonl",
        remediation_path: str | Path = "research/paper_integrity_remediation.jsonl",
        baseline_path: str | Path = "research/paper_validation_baselines.jsonl",
    ) -> None:
        self.journal = journal
        self.broker = broker
        self.lifecycle = lifecycle
        self.campaigns = campaigns
        self.journal_path = Path(getattr(journal, "path", journal_path))
        self.remediation = RemediationRegistry(remediation_path)
        self.baselines = ValidationBaselineManager(baseline_path)

    def summary(self) -> JournalIntegritySummary:
        entries = self._entries()
        raw_rows = self._raw_rows()
        issues: list[IntegrityIssue] = []
        duplicate_report = self.duplicate_report(entries, raw_rows)
        issues.extend(duplicate_report.impossible_state_transitions)
        lifecycle_audit = self.lifecycle_audit(entries)
        issues.extend(lifecycle_audit.missing_lifecycle)
        issues.extend(lifecycle_audit.duplicate_events)
        issues.extend(lifecycle_audit.impossible_ordering)
        issues.extend(lifecycle_audit.orphan_lifecycle)
        timestamp_audit = self.timestamp_audit(entries)
        issues.extend(timestamp_audit.missing_timestamps)
        issues.extend(timestamp_audit.closed_before_opened)
        issues.extend(timestamp_audit.identical_open_close)
        issues.extend(timestamp_audit.negative_durations)
        issues.extend(timestamp_audit.future_timestamps)
        issues.extend(timestamp_audit.timezone_inconsistencies)
        records = tuple(self._classify(entry, issues, duplicate_report) for entry in entries)
        counts = Counter(record.classification for record in records)
        quarantine = self.quarantine_summary(records)
        critical = sum(item.severity == "critical" for item in issues)
        warnings = sum(item.severity == "warning" for item in issues)
        duplicate_present = any(
            getattr(duplicate_report, name)
            for name in (
                "duplicate_trade_ids",
                "duplicate_lifecycle_ids",
                "duplicate_brokerage_ids",
                "duplicate_source_event_ids",
                "duplicate_execution_chains",
                "duplicate_journal_entries",
                "duplicate_campaign_membership",
                "duplicate_closes",
                "duplicate_opens",
            )
        )
        provisional = type(
            "_ProvisionalSummary",
            (),
            {
                "records": records,
                "issues": tuple(issues),
                "warning_count": warnings,
                "total_records": len(entries),
                "raw_record_count": len(raw_rows),
            },
        )()
        baseline = self.baselines.latest()
        safe_status = self.baselines.safe_mode_status(provisional, registry=self.remediation)
        enhanced = enhanced_summary(provisional, baseline, safe_status, self.remediation)
        operational_duplicate_present = any(
            getattr(duplicate_report, name)
            for name in (
                "duplicate_trade_ids",
                "duplicate_lifecycle_ids",
                "duplicate_brokerage_ids",
                "duplicate_execution_chains",
                "duplicate_journal_entries",
                "duplicate_campaign_membership",
                "duplicate_closes",
                "duplicate_opens",
            )
        )
        safe_mode = bool(enhanced.unresolved_critical_records or operational_duplicate_present or timestamp_audit.closed_before_opened or timestamp_audit.negative_durations)
        status = "FAIL" if enhanced.unresolved_critical_records or operational_duplicate_present else "WATCHLIST" if warnings or quarantine.quarantined_count else "PASS"
        return JournalIntegritySummary(
            status=status,
            safe_mode_required=safe_mode,
            total_records=len(entries),
            classification_counts={key: counts.get(key, 0) for key in CLASSIFICATIONS},
            issue_count=len(issues),
            critical_count=critical,
            warning_count=warnings,
            quarantined_count=quarantine.quarantined_count,
            duplicate_report=duplicate_report,
            lifecycle_audit=lifecycle_audit,
            timestamp_audit=timestamp_audit,
            quarantine=quarantine,
            records=records,
            issues=tuple(issues),
            human_readable_summary=f"Journal integrity is {status}: {len(entries)} records, {enhanced.unresolved_critical_records} unresolved critical issues, {enhanced.quarantined_records} quarantined/excluded records.",
            raw_record_count=len(raw_rows),
            eligible_runtime_records=enhanced.eligible_runtime_records,
            eligible_performance_records=enhanced.eligible_performance_records,
            quarantined_records=enhanced.quarantined_records,
            legacy_records=enhanced.legacy_records,
            test_fixture_records=enhanced.test_fixture_records,
            corrupted_records=enhanced.corrupted_records,
            incomplete_records=enhanced.incomplete_records,
            unresolved_critical_records=enhanced.unresolved_critical_records,
            resolved_critical_records=enhanced.resolved_critical_records,
            safe_mode_status=enhanced.safe_mode_status,
            baseline_status=enhanced.baseline_status,
            latest_baseline_id=enhanced.latest_baseline_id,
            ready_for_validation=enhanced.ready_for_validation,
        )

    def duplicate_report(self, entries: Iterable[Any] | None = None, raw_rows: Iterable[dict[str, Any]] | None = None) -> DuplicateReport:
        rows = tuple(entries if entries is not None else self._entries())
        raw = tuple(raw_rows if raw_rows is not None else self._raw_rows())
        trade_ids = _dupes(getattr(item, "trade_id", None) for item in rows)
        source_ids = _dupes(getattr(item, "source_event_id", None) for item in rows)
        chains = _dupes(_chain(item) for item in rows)
        journal_events = _dupes(
            f"{item.get('event_type')}:{(item.get('entry') or {}).get('trade_id')}:{item.get('recorded_at')}"
            for item in raw
        )
        opens = _dupes((row.get("entry") or {}).get("trade_id") for row in raw if row.get("event_type") == "paper_trade_opened")
        closes = _dupes((row.get("entry") or {}).get("trade_id") for row in raw if row.get("event_type") == "paper_trade_closed")
        campaign_membership = _dupes(f"{getattr(item, 'trade_id', None)}:{getattr(item, 'campaign_id', None)}" for item in rows)
        lifecycle_ids = _dupes(getattr(item, "event_id", None) for item in self._lifecycle_events())
        brokerage_ids = _dupes(getattr(item, "trade_id", None) for item in self._brokerage_trades())
        impossible = tuple(_transition_issues(rows))
        return DuplicateReport(
            duplicate_trade_ids=trade_ids,
            duplicate_lifecycle_ids=lifecycle_ids,
            duplicate_brokerage_ids=brokerage_ids,
            duplicate_source_event_ids=source_ids,
            duplicate_execution_chains=chains,
            duplicate_journal_entries=journal_events,
            duplicate_campaign_membership=campaign_membership,
            duplicate_closes=closes,
            duplicate_opens=opens,
            impossible_state_transitions=impossible,
            human_readable_summary=f"Duplicate audit found {sum(map(len, (trade_ids, lifecycle_ids, brokerage_ids, source_ids, chains, journal_events, campaign_membership, closes, opens)))} duplicate categories.",
        )

    def lifecycle_audit(self, entries: Iterable[Any] | None = None) -> LifecycleAudit:
        rows = tuple(entries if entries is not None else self._entries())
        missing: list[IntegrityIssue] = []
        duplicates: list[IntegrityIssue] = []
        ordering: list[IntegrityIssue] = []
        orphan: list[IntegrityIssue] = []
        journal_ids = {getattr(item, "trade_id", None) for item in rows}
        for entry in rows:
            events = tuple(getattr(entry, "lifecycle_events", ()) or ())
            trade_id = getattr(entry, "trade_id", None)
            if getattr(entry, "status", None) in {"open", "closed"} and not events:
                missing.append(_issue(entry, "warning", "trade_lifecycle_manager", "missing_lifecycle", "Review lifecycle persistence for this trade."))
            event_keys = [json.dumps(event, sort_keys=True, default=str) for event in events]
            for _, count in Counter(event_keys).items():
                if count > 1:
                    duplicates.append(_issue(entry, "critical", "trade_lifecycle_manager", "duplicate lifecycle event", "Quarantine duplicate lifecycle history before validation."))
                    break
            event_times = [_parse_time(event.get("timestamp")) for event in events if isinstance(event, dict)]
            event_times = [item for item in event_times if item is not None]
            if event_times and event_times != sorted(event_times):
                ordering.append(_issue(entry, "critical", "trade_lifecycle_manager", "impossible lifecycle ordering", "Inspect append-only lifecycle event sequence."))
        for event in self._lifecycle_events():
            trade_id = getattr(event, "trade_id", None)
            if trade_id and trade_id not in journal_ids:
                orphan.append(IntegrityIssue(trade_id, None, "warning", "trade_lifecycle_manager", "orphan lifecycle event", "Review lifecycle state against paper journal."))
        return LifecycleAudit(
            missing_lifecycle=tuple(missing),
            duplicate_events=tuple(duplicates),
            impossible_ordering=tuple(ordering),
            orphan_lifecycle=tuple(orphan),
            human_readable_summary=f"Lifecycle audit found {len(missing)} missing histories, {len(duplicates)} duplicate histories, and {len(orphan)} orphan lifecycle events.",
        )

    def timestamp_audit(self, entries: Iterable[Any] | None = None) -> TimestampAudit:
        rows = tuple(entries if entries is not None else self._entries())
        missing: list[IntegrityIssue] = []
        before: list[IntegrityIssue] = []
        identical: list[IntegrityIssue] = []
        negative: list[IntegrityIssue] = []
        future: list[IntegrityIssue] = []
        timezone_issues: list[IntegrityIssue] = []
        now = datetime.now(timezone.utc)
        for entry in rows:
            opened = getattr(entry, "opened_at", None)
            closed = getattr(entry, "closed_at", None)
            if getattr(entry, "status", None) in {"open", "closed"} and not opened:
                missing.append(_issue(entry, "critical", "paper_journal", "missing opened_at timestamp", "Quarantine or reconstruct timestamp provenance."))
            if getattr(entry, "status", None) == "closed" and not closed:
                missing.append(_issue(entry, "critical", "paper_journal", "missing closed_at timestamp", "Quarantine or reconstruct close provenance."))
            opened_dt = _parse_time(opened)
            closed_dt = _parse_time(closed)
            if opened and opened_dt is None or closed and closed_dt is None:
                timezone_issues.append(_issue(entry, "critical", "paper_journal", "timestamp parse or timezone inconsistency", "Normalize timestamp provenance before validation."))
            if opened_dt and opened_dt > now or closed_dt and closed_dt > now:
                future.append(_issue(entry, "critical", "paper_journal", "future timestamp", "Exclude future-dated record from validation."))
            if opened_dt and closed_dt:
                if closed_dt < opened_dt:
                    before.append(_issue(entry, "critical", "paper_journal", "closed before opened", "Quarantine invalid timestamp sequence."))
                    negative.append(_issue(entry, "critical", "paper_journal", "negative duration", "Quarantine invalid timestamp sequence."))
                if closed_dt == opened_dt:
                    identical.append(_issue(entry, "critical", "paper_journal", "identical opened_at and closed_at", "Verify same-instant lifecycle before validation."))
        return TimestampAudit(
            missing_timestamps=tuple(missing),
            closed_before_opened=tuple(before),
            identical_open_close=tuple(identical),
            negative_durations=tuple(negative),
            future_timestamps=tuple(future),
            timezone_inconsistencies=tuple(timezone_issues),
            human_readable_summary=f"Timestamp audit found {len(missing) + len(before) + len(identical) + len(future) + len(timezone_issues)} timestamp issues.",
        )

    def quarantine_summary(self, records: Iterable[JournalIntegrityRecord] | None = None) -> QuarantineSummary:
        rows = tuple(records if records is not None else self.summary().records)
        quarantined = tuple(row for row in rows if row.quarantine_status == "QUARANTINED")
        reasons = Counter(reason for row in quarantined for reason in row.quarantine_reasons)
        return QuarantineSummary(
            quarantined_count=len(quarantined),
            reasons=dict(sorted(reasons.items())),
            trade_ids=tuple(str(row.trade_id) for row in quarantined if row.trade_id),
            records=quarantined,
            human_readable_summary=f"{len(quarantined)} journal records are quarantined from runtime, campaign, validation, and reconciliation PASS metrics.",
        )

    def root_cause(self, trade_id: str) -> RootCauseReport:
        rows = tuple(item for item in self._entries() if getattr(item, "trade_id", None) == trade_id)
        raw = tuple(row for row in self._raw_rows() if (row.get("entry") or {}).get("trade_id") == trade_id)
        if not rows and not raw:
            return RootCauseReport(
                trade_id=trade_id,
                found=False,
                originated_from=None,
                component_created=None,
                campaign_id=None,
                lifecycle_id=None,
                brokerage_id=None,
                source_event_id=None,
                duplicated=False,
                timestamps_corrupted=False,
                lifecycle_events_missing=True,
                deterministic_recovery_fixture=False,
                historical_import=False,
                production_campaign=False,
                classification="UNKNOWN",
                root_cause="Trade ID was not found in current journal, brokerage, lifecycle, report, campaign, or source files.",
                recommended_action="Verify the correct workspace/state snapshot is mounted before modifying any historical record.",
            )
        entry = rows[-1] if rows else _RawEntry(raw[-1].get("entry") or {})
        summary = self.summary()
        record = next((item for item in summary.records if item.trade_id == trade_id), None)
        campaign_id = getattr(entry, "campaign_id", None)
        lifecycle_id = next((getattr(event, "event_id", None) for event in self._lifecycle_events() if getattr(event, "trade_id", None) == trade_id), None)
        in_broker = any(getattr(item, "trade_id", None) == trade_id for item in self._brokerage_trades())
        duplicated = len(rows) > 1 or trade_id in summary.duplicate_report.duplicate_trade_ids
        timestamp_bad = any(issue.trade_id == trade_id for issue in (
            *summary.timestamp_audit.closed_before_opened,
            *summary.timestamp_audit.identical_open_close,
            *summary.timestamp_audit.negative_durations,
            *summary.timestamp_audit.future_timestamps,
            *summary.timestamp_audit.timezone_inconsistencies,
        ))
        fixture = bool(getattr(entry, "test_fixture", False) or getattr(entry, "synthetic_recovery_test", False))
        historical = campaign_id in {None, "legacy_campaign"}
        return RootCauseReport(
            trade_id=trade_id,
            found=True,
            originated_from="paper_trade_journal",
            component_created=_creator(raw),
            campaign_id=campaign_id,
            lifecycle_id=lifecycle_id,
            brokerage_id=trade_id if in_broker else None,
            source_event_id=getattr(entry, "source_event_id", None),
            duplicated=duplicated,
            timestamps_corrupted=timestamp_bad,
            lifecycle_events_missing=not bool(getattr(entry, "lifecycle_events", ()) or lifecycle_id),
            deterministic_recovery_fixture=fixture,
            historical_import=historical,
            production_campaign=bool(campaign_id and str(campaign_id).startswith("campaign_") and not fixture),
            classification=record.classification if record else "UNKNOWN",
            root_cause="Trade is present but requires the integrity report for final classification.",
            recommended_action="Review the trade's classification, lifecycle, timestamp, duplicate, and campaign context before taking any manual remediation.",
        )

    def _classify(self, entry: Any, issues: list[IntegrityIssue], duplicates: DuplicateReport) -> JournalIntegrityRecord:
        trade_id = getattr(entry, "trade_id", None)
        entry_issues = [issue for issue in issues if issue.trade_id == trade_id]
        reasons: list[str] = []
        if trade_id in duplicates.duplicate_trade_ids:
            classification = "DUPLICATE"; reasons.append("duplicate")
        elif any(issue.severity == "critical" and issue.trade_id == trade_id for issue in entry_issues):
            classification = "CORRUPTED"
            if any("timestamp" in issue.root_cause or "duration" in issue.root_cause or "closed before" in issue.root_cause for issue in entry_issues):
                reasons.append("timestamp_corruption")
            if any("transition" in issue.root_cause or "state" in issue.root_cause for issue in entry_issues):
                reasons.append("invalid_transition")
        elif bool(getattr(entry, "test_fixture", False)):
            classification = "TEST_FIXTURE"; reasons.append("test_fixture")
        elif bool(getattr(entry, "synthetic_recovery_test", False)):
            classification = "SYNTHETIC"; reasons.append("synthetic")
        elif getattr(entry, "campaign_id", None) in {None, "legacy_campaign"}:
            classification = "LEGACY_IMPORT"; reasons.append("legacy_import")
        elif any(issue.root_cause == "missing_lifecycle" and issue.trade_id == trade_id for issue in entry_issues):
            classification = "INCOMPLETE"; reasons.append("missing_lifecycle")
        elif not getattr(entry, "trade_id", None) or not getattr(entry, "status", None):
            classification = "INCOMPLETE"; reasons.append("invalid_state")
        elif getattr(entry, "status", None) not in {"open", "closed", "rejected", "expired", "pending"}:
            classification = "UNKNOWN"
        else:
            classification = "VALID_RUNTIME" if _active_campaign(getattr(entry, "campaign_id", None), self.campaigns) else "VALID_HISTORICAL"
        remediation = self.remediation.latest_by_trade().get(str(trade_id))
        if remediation and remediation.remediation_action in {
            "QUARANTINE",
            "MARK_LEGACY",
            "MARK_TEST_FIXTURE",
            "MARK_INCOMPLETE",
            "EXCLUDE_FROM_RUNTIME",
            "EXCLUDE_FROM_CAMPAIGN",
            "EXCLUDE_FROM_PERFORMANCE",
        }:
            reasons.append(remediation.remediation_reason)
        quarantine = "QUARANTINED" if reasons else None
        return JournalIntegrityRecord(
            trade_id=trade_id,
            source_event_id=getattr(entry, "source_event_id", None),
            campaign_id=getattr(entry, "campaign_id", None),
            symbol=getattr(entry, "symbol", None),
            status=getattr(entry, "status", None),
            classification=classification,
            quarantine_status=quarantine,
            quarantine_reasons=tuple(dict.fromkeys(reasons)),
            issue_count=len(entry_issues),
            lifecycle_event_count=len(getattr(entry, "lifecycle_events", ()) or ()),
            opened_at=getattr(entry, "opened_at", None),
            closed_at=getattr(entry, "closed_at", None),
            human_readable_summary=f"{trade_id or 'unknown'} classified as {classification}.",
        )

    def _entries(self) -> tuple[Any, ...]:
        if self.journal is not None:
            try:
                return tuple(self.journal.entries())
            except Exception:
                pass
        return tuple(_RawEntry(row.get("entry") or {}) for row in self._raw_rows() if isinstance(row.get("entry"), dict))

    def _raw_rows(self) -> tuple[dict[str, Any], ...]:
        if not self.journal_path.exists():
            return ()
        rows = []
        for line in self.journal_path.read_text(encoding="utf-8").splitlines():
            try:
                value = json.loads(line)
                if isinstance(value, dict):
                    rows.append(value)
            except json.JSONDecodeError:
                rows.append({"event_type": "corrupted_json", "entry": {"trade_id": None}})
        return tuple(rows)

    def _lifecycle_events(self) -> tuple[Any, ...]:
        try:
            return tuple(self.lifecycle.events()) if self.lifecycle is not None else ()
        except Exception:
            return ()

    def _brokerage_trades(self) -> tuple[Any, ...]:
        try:
            if self.broker is None:
                return ()
            return tuple((*self.broker.open_positions(), *self.broker.closed_trades()))
        except Exception:
            return ()


def current_integrity_auditor(**kwargs: Any) -> JournalIntegrityAuditor:
    return JournalIntegrityAuditor(**kwargs)


def _dupes(values: Iterable[Any]) -> dict[str, int]:
    counts = Counter(str(item) for item in values if item not in {None, ""})
    return dict(sorted((key, count) for key, count in counts.items() if count > 1))


def _chain(item: Any) -> str | None:
    parts = (
        getattr(item, "source_event_id", None),
        getattr(item, "symbol", None),
        getattr(item, "timeframe", None),
        getattr(item, "setup", None),
        getattr(item, "opened_at", None),
        getattr(item, "closed_at", None),
    )
    return ":".join(str(part) for part in parts if part is not None) or None


def _transition_issues(rows: Iterable[Any]) -> tuple[IntegrityIssue, ...]:
    issues = []
    for entry in rows:
        if getattr(entry, "status", None) == "open" and getattr(entry, "closed_at", None):
            issues.append(_issue(entry, "critical", "paper_journal", "impossible state transition: open trade has closed_at", "Quarantine invalid state before validation."))
        if getattr(entry, "status", None) == "closed" and not getattr(entry, "closed_at", None):
            issues.append(_issue(entry, "critical", "paper_journal", "impossible state transition: closed trade missing closed_at", "Quarantine invalid state before validation."))
    return tuple(issues)


def _issue(entry: Any, severity: str, component: str, root_cause: str, action: str) -> IntegrityIssue:
    return IntegrityIssue(
        trade_id=getattr(entry, "trade_id", None),
        campaign_id=getattr(entry, "campaign_id", None),
        severity=severity,
        component=component,
        root_cause=root_cause,
        recommended_action=action,
    )


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
        return parsed if parsed.tzinfo else None
    except ValueError:
        return None


def _active_campaign(campaign_id: str | None, manager: Any | None) -> bool:
    if not campaign_id or manager is None:
        return False
    try:
        current = manager.current()
        return bool(current and current.campaign_id == campaign_id)
    except Exception:
        return False


def _creator(raw_rows: tuple[dict[str, Any], ...]) -> str | None:
    event_types = [row.get("event_type") for row in raw_rows]
    if "paper_trade_opened" in event_types:
        return "paper_brokerage"
    if event_types:
        return str(event_types[0])
    return None


class _RawEntry:
    def __init__(self, raw: dict[str, Any]) -> None:
        self.__dict__.update(raw)
        for key in ("lifecycle_events", "warnings", "rule_violations"):
            value = getattr(self, key, ())
            setattr(self, key, tuple(value or ()))
