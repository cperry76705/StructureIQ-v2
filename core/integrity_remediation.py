"""Auditable paper-integrity remediation and clean-baseline utilities.

This module intentionally never edits the raw paper journal.  It stores
operator decisions in append-only JSONL registries and exposes centralized
eligibility checks that downstream reporting/recovery code can reuse.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from pydantic import BaseModel


REMEDIATION_VERSION = "6.0.16"
DEFAULT_REMEDIATION_PATH = Path("research/paper_integrity_remediation.jsonl")
DEFAULT_BASELINE_PATH = Path("research/paper_validation_baselines.jsonl")
DEFAULT_SAFE_MODE_PATH = Path("research/paper_safe_mode_state.json")

EXCLUSION_ACTIONS = {
    "QUARANTINE",
    "MARK_LEGACY",
    "MARK_TEST_FIXTURE",
    "MARK_INCOMPLETE",
    "EXCLUDE_FROM_RUNTIME",
    "EXCLUDE_FROM_CAMPAIGN",
    "EXCLUDE_FROM_PERFORMANCE",
}
SUPPORTED_REMEDIATION_ACTIONS = EXCLUSION_ACTIONS | {"ACKNOWLEDGE_WARNING", "RESTORE_ELIGIBILITY"}
CRITICAL_CLASSIFICATIONS = {"CORRUPTED", "DUPLICATE"}
INELIGIBLE_CLASSIFICATIONS = {
    "CORRUPTED",
    "DUPLICATE",
    "TEST_FIXTURE",
    "SYNTHETIC",
    "ORPHANED",
    "UNKNOWN",
}


class RemediationPreviewRequest(BaseModel):
    trade_id: str | None = None
    classification: str | None = None
    proposed_action: str = "QUARANTINE"


class RemediationApplyRequest(BaseModel):
    trade_id: str | None = None
    trade_ids: tuple[str, ...] = ()
    action: str
    reason: str
    operator: str = "system"
    automatic: bool = False
    notes: str | None = None


@dataclass(frozen=True)
class RemediationRecord:
    remediation_id: str
    created_at: str
    trade_id: str
    source_event_id: str | None
    campaign_id: str | None
    original_classification: str
    remediation_action: str
    remediation_reason: str
    operator: str
    automatic: bool
    before_state: dict[str, Any]
    after_state: dict[str, Any]
    raw_record_preserved: bool
    reversible: bool
    version: str
    notes: str | None = None


@dataclass(frozen=True)
class RemediationPreview:
    trade_id: str
    proposed_action: str
    current_classification: str
    runtime_effect: str
    campaign_effect: str
    performance_effect: str
    raw_journal_mutation: bool
    evidence: tuple[str, ...]
    eligible_before: bool
    eligible_after: bool
    human_readable_summary: str


@dataclass(frozen=True)
class RemediationApplyResult:
    status: str
    applied_count: int
    records: tuple[RemediationRecord, ...]
    skipped_trade_ids: tuple[str, ...]
    raw_journal_mutated: bool
    human_readable_summary: str


@dataclass(frozen=True)
class DuplicateGroupAnalysis:
    source_event_id: str
    record_count: int
    trade_ids: tuple[str, ...]
    campaign_ids: tuple[str, ...]
    statuses: tuple[str, ...]
    classification_summary: dict[str, int]
    is_expected: bool
    is_duplicate_trade_chain: bool
    reason: str


@dataclass(frozen=True)
class IncompleteRecordDecision:
    trade_id: str | None
    source_event_id: str | None
    campaign_id: str | None
    current_classification: str
    recommended_classification: str
    evidence: tuple[str, ...]
    human_readable_summary: str


@dataclass(frozen=True)
class RebuildDerivedStateResult:
    status: str
    rebuilt_at: str
    before_summary: dict[str, Any]
    after_summary: dict[str, Any]
    raw_journal_mutated: bool
    human_readable_summary: str


@dataclass(frozen=True)
class CampaignRebuildResult:
    campaign_id: str | None
    original_trade_count: int
    eligible_trade_count: int
    excluded_trade_count: int
    excluded_trade_ids: tuple[str, ...]
    original_total_r: float
    eligible_total_r: float
    summary_status: str
    human_readable_summary: str


@dataclass(frozen=True)
class ValidationBaseline:
    baseline_id: str
    created_at: str
    version: str
    eligible_trade_count: int
    eligible_open_trade_count: int
    eligible_closed_trade_count: int
    quarantined_count: int
    legacy_count: int
    test_fixture_count: int
    critical_unresolved_count: int
    warning_count: int
    campaign_id: str | None
    journal_hash_or_fingerprint: str
    lifecycle_fingerprint: str
    brokerage_fingerprint: str
    status: str
    human_readable_summary: str


@dataclass(frozen=True)
class SafeModeClearResult:
    safe_mode_status: str
    cleared: bool
    requirements: dict[str, bool]
    blocking_reasons: tuple[str, ...]
    baseline_id: str | None
    human_readable_summary: str


@dataclass(frozen=True)
class EnhancedIntegritySummary:
    raw_record_count: int
    eligible_runtime_records: int
    eligible_performance_records: int
    quarantined_records: int
    legacy_records: int
    test_fixture_records: int
    corrupted_records: int
    incomplete_records: int
    unresolved_critical_records: int
    resolved_critical_records: int
    safe_mode_status: str
    baseline_status: str
    latest_baseline_id: str | None
    ready_for_validation: bool
    human_readable_summary: str


@dataclass(frozen=True)
class EligibilityDecision:
    runtime_eligible: bool
    performance_eligible: bool
    campaign_eligible: bool
    reasons: tuple[str, ...]


class RemediationRegistry:
    """Append-only remediation registry."""

    def __init__(self, path: str | Path = DEFAULT_REMEDIATION_PATH) -> None:
        self.path = Path(path)

    def records(self) -> tuple[RemediationRecord, ...]:
        if not self.path.exists():
            return ()
        rows: list[RemediationRecord] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                value = json.loads(line)
                if isinstance(value, dict):
                    rows.append(RemediationRecord(**value))
            except (json.JSONDecodeError, TypeError):
                continue
        return tuple(rows)

    def history(self, trade_id: str | None = None) -> tuple[RemediationRecord, ...]:
        rows = self.records()
        if trade_id is None:
            return rows
        return tuple(item for item in rows if item.trade_id == trade_id)

    def latest_by_trade(self) -> dict[str, RemediationRecord]:
        latest: dict[str, RemediationRecord] = {}
        for record in self.records():
            latest[record.trade_id] = record
        return latest

    def preview(self, summary: Any, request: RemediationPreviewRequest) -> tuple[RemediationPreview, ...]:
        targets = _target_records(summary.records, request.trade_id, request.classification)
        return tuple(_preview_for_record(record, request.proposed_action, self.latest_by_trade().get(str(record.trade_id))) for record in targets)

    def apply(self, summary: Any, request: RemediationApplyRequest) -> RemediationApplyResult:
        if request.action not in SUPPORTED_REMEDIATION_ACTIONS:
            raise ValueError(f"Unsupported remediation action: {request.action}")
        target_ids = tuple(dict.fromkeys((*(request.trade_ids or ()), *((request.trade_id,) if request.trade_id else ()))))
        if not target_ids:
            raise ValueError("At least one trade_id is required.")
        records_by_id = {str(item.trade_id): item for item in summary.records if item.trade_id}
        targets = tuple(records_by_id[item] for item in target_ids if item in records_by_id)
        missing = tuple(item for item in target_ids if item not in records_by_id)
        if not targets:
            return RemediationApplyResult("NOOP", 0, (), missing, False, "No matching journal records were found.")
        classifications = {item.classification for item in targets}
        if len(classifications) > 1:
            raise ValueError("Batch remediation requires all records to share the same classification.")
        if request.action == "RESTORE_ELIGIBILITY" and any(item.classification in INELIGIBLE_CLASSIFICATIONS for item in targets):
            raise ValueError("RESTORE_ELIGIBILITY requires every target to pass integrity checks first.")
        existing = self.latest_by_trade()
        new_records: list[RemediationRecord] = []
        for item in targets:
            prior = existing.get(str(item.trade_id))
            if prior and prior.remediation_action == request.action and prior.remediation_reason == request.reason:
                continue
            created = _now()
            before = _state_for(item, prior)
            after = _after_state_for(item, request.action)
            record = RemediationRecord(
                remediation_id=_id("remediation", created, str(item.trade_id), request.action, request.reason),
                created_at=created,
                trade_id=str(item.trade_id),
                source_event_id=item.source_event_id,
                campaign_id=item.campaign_id,
                original_classification=item.classification,
                remediation_action=request.action,
                remediation_reason=request.reason,
                operator=request.operator,
                automatic=bool(request.automatic),
                before_state=before,
                after_state=after,
                raw_record_preserved=True,
                reversible=request.action != "RESTORE_ELIGIBILITY",
                version=REMEDIATION_VERSION,
                notes=request.notes,
            )
            self._append(record)
            new_records.append(record)
        return RemediationApplyResult(
            status="APPLIED" if new_records else "NOOP",
            applied_count=len(new_records),
            records=tuple(new_records),
            skipped_trade_ids=missing,
            raw_journal_mutated=False,
            human_readable_summary=f"Applied {len(new_records)} remediation record(s); raw paper journal was not modified.",
        )

    def _append(self, record: RemediationRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(record), sort_keys=True) + "\n")


class ValidationBaselineManager:
    """Append-only clean-validation baseline registry."""

    def __init__(self, path: str | Path = DEFAULT_BASELINE_PATH, safe_mode_path: str | Path = DEFAULT_SAFE_MODE_PATH) -> None:
        self.path = Path(path)
        self.safe_mode_path = Path(safe_mode_path)

    def baselines(self) -> tuple[ValidationBaseline, ...]:
        if not self.path.exists():
            return ()
        rows: list[ValidationBaseline] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                value = json.loads(line)
                if isinstance(value, dict):
                    rows.append(ValidationBaseline(**value))
            except (json.JSONDecodeError, TypeError):
                continue
        return tuple(rows)

    def latest(self) -> ValidationBaseline | None:
        rows = self.baselines()
        return rows[-1] if rows else None

    def get(self, baseline_id: str) -> ValidationBaseline | None:
        return next((item for item in self.baselines() if item.baseline_id == baseline_id), None)

    def create(self, summary: Any, *, campaign_id: str | None = None, lifecycle: Any | None = None, broker: Any | None = None) -> ValidationBaseline:
        enhanced = enhanced_summary(summary, self.latest(), self.safe_mode_status(summary))
        if enhanced.unresolved_critical_records:
            raise ValueError("Cannot create baseline while unresolved critical eligible records remain.")
        created = _now()
        eligible = [item for item in summary.records if eligibility_decision(item).runtime_eligible]
        closed = [item for item in eligible if item.status == "closed"]
        opened = [item for item in eligible if item.status == "open"]
        baseline = ValidationBaseline(
            baseline_id=_id("baseline", created, str(len(eligible)), campaign_id or "global"),
            created_at=created,
            version=REMEDIATION_VERSION,
            eligible_trade_count=len(eligible),
            eligible_open_trade_count=len(opened),
            eligible_closed_trade_count=len(closed),
            quarantined_count=enhanced.quarantined_records,
            legacy_count=enhanced.legacy_records,
            test_fixture_count=enhanced.test_fixture_records,
            critical_unresolved_count=enhanced.unresolved_critical_records,
            warning_count=summary.warning_count,
            campaign_id=campaign_id,
            journal_hash_or_fingerprint=_fingerprint(summary.records),
            lifecycle_fingerprint=_fingerprint(_safe_call(lifecycle, "events")),
            brokerage_fingerprint=_fingerprint((*_safe_call(broker, "open_positions"), *_safe_call(broker, "closed_trades"))),
            status="PASS",
            human_readable_summary=f"Clean validation baseline contains {len(eligible)} eligible runtime record(s) and excludes {enhanced.quarantined_records} quarantined record(s).",
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(baseline), sort_keys=True) + "\n")
        return baseline

    def safe_mode_status(self, summary: Any, registry: RemediationRegistry | None = None) -> str:
        state = self._safe_mode_state()
        enhanced = enhanced_summary(summary, self.latest(), "ACTIVE", registry)
        if state.get("status") == "CLEARED" and not enhanced.unresolved_critical_records:
            return "CLEARED"
        if enhanced.unresolved_critical_records:
            return "ACTIVE"
        return "CLEARABLE" if self.latest() and self.latest().status == "PASS" else "ACTIVE"

    def clear_safe_mode(self, summary: Any, *, recovery_status: str = "PASS", reconciliation_status: str = "PASS") -> SafeModeClearResult:
        latest = self.latest()
        enhanced = enhanced_summary(summary, latest, "ACTIVE")
        requirements = {
            "unresolved_critical_runtime_integrity_count_zero": enhanced.unresolved_critical_records == 0,
            "baseline_exists_and_valid": bool(latest and latest.status == "PASS"),
            "reconciliation_not_fail": reconciliation_status != "FAIL",
            "recovery_not_fail": recovery_status != "FAIL",
            "no_quarantined_record_runtime_eligible": all(not eligibility_decision(item).runtime_eligible for item in summary.records if item.quarantine_status == "QUARANTINED"),
        }
        blockers = tuple(name for name, ok in requirements.items() if not ok)
        if blockers:
            return SafeModeClearResult(
                safe_mode_status="ACTIVE",
                cleared=False,
                requirements=requirements,
                blocking_reasons=blockers,
                baseline_id=getattr(latest, "baseline_id", None),
                human_readable_summary="SAFE MODE remains active because one or more exit requirements failed.",
            )
        self.safe_mode_path.parent.mkdir(parents=True, exist_ok=True)
        self.safe_mode_path.write_text(json.dumps({"status": "CLEARED", "cleared_at": _now(), "baseline_id": latest.baseline_id}, indent=2), encoding="utf-8")
        return SafeModeClearResult(
            safe_mode_status="CLEARED",
            cleared=True,
            requirements=requirements,
            blocking_reasons=(),
            baseline_id=latest.baseline_id,
            human_readable_summary="SAFE MODE has been cleared after validated integrity and baseline checks.",
        )

    def _safe_mode_state(self) -> dict[str, Any]:
        if not self.safe_mode_path.exists():
            return {}
        try:
            value = json.loads(self.safe_mode_path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except json.JSONDecodeError:
            return {}


def eligibility_decision(record: Any, *, include_legacy: bool = False, remediation: RemediationRecord | None = None) -> EligibilityDecision:
    classification = getattr(record, "classification", None) or _classification_from_raw(record)
    reasons: list[str] = []
    action = getattr(remediation, "remediation_action", None)
    after_state = getattr(remediation, "after_state", {}) or {}
    if action in EXCLUSION_ACTIONS or after_state.get("operational_status") == "QUARANTINED":
        reasons.append("remediation_excluded")
    if classification in INELIGIBLE_CLASSIFICATIONS:
        reasons.append(str(classification).lower())
    if classification == "LEGACY_IMPORT" and not include_legacy:
        reasons.append("legacy_import")
    if classification == "TEST_FIXTURE" or bool(getattr(record, "test_fixture", False)):
        reasons.append("test_fixture")
    if classification == "SYNTHETIC" or bool(getattr(record, "synthetic_recovery_test", False)):
        reasons.append("synthetic")
    if classification == "INCOMPLETE":
        reasons.append("incomplete")
    for flag, reason in (
        ("exclude_from_performance", "record_excludes_performance"),
        ("exclude_from_campaign_metrics", "record_excludes_campaign"),
        ("exclude_from_daily_reports", "record_excludes_daily_reports"),
    ):
        if bool(getattr(record, flag, False)):
            reasons.append(reason)
    runtime = not reasons
    performance = runtime and "record_excludes_performance" not in reasons
    campaign = runtime and "record_excludes_campaign" not in reasons
    return EligibilityDecision(runtime, performance, campaign, tuple(dict.fromkeys(reasons)))


def is_runtime_eligible_trade(record: Any, *, include_legacy: bool = False, remediation: RemediationRecord | None = None) -> bool:
    return eligibility_decision(record, include_legacy=include_legacy, remediation=remediation).runtime_eligible


def enhanced_summary(
    summary: Any,
    latest_baseline: ValidationBaseline | None = None,
    safe_mode_status: str | None = None,
    registry: RemediationRegistry | None = None,
) -> EnhancedIntegritySummary:
    if registry is None and hasattr(summary, "unresolved_critical_records"):
        baseline_status = latest_baseline.status if latest_baseline else getattr(summary, "baseline_status", "MISSING")
        safe = safe_mode_status or getattr(summary, "safe_mode_status", "ACTIVE")
        ready = safe == "CLEARED" and baseline_status == "PASS" and int(getattr(summary, "unresolved_critical_records", 0) or 0) == 0
        return EnhancedIntegritySummary(
            raw_record_count=int(getattr(summary, "raw_record_count", getattr(summary, "total_records", 0)) or 0),
            eligible_runtime_records=int(getattr(summary, "eligible_runtime_records", 0) or 0),
            eligible_performance_records=int(getattr(summary, "eligible_performance_records", 0) or 0),
            quarantined_records=int(getattr(summary, "quarantined_records", getattr(summary, "quarantined_count", 0)) or 0),
            legacy_records=int(getattr(summary, "legacy_records", 0) or 0),
            test_fixture_records=int(getattr(summary, "test_fixture_records", 0) or 0),
            corrupted_records=int(getattr(summary, "corrupted_records", 0) or 0),
            incomplete_records=int(getattr(summary, "incomplete_records", 0) or 0),
            unresolved_critical_records=int(getattr(summary, "unresolved_critical_records", 0) or 0),
            resolved_critical_records=int(getattr(summary, "resolved_critical_records", 0) or 0),
            safe_mode_status=safe,
            baseline_status=baseline_status,
            latest_baseline_id=getattr(latest_baseline, "baseline_id", getattr(summary, "latest_baseline_id", None)),
            ready_for_validation=ready,
            human_readable_summary=f"Integrity baseline state: {getattr(summary, 'unresolved_critical_records', 0)} unresolved critical record(s), SAFE MODE {safe}.",
        )
    registry = registry or RemediationRegistry()
    remediations = registry.latest_by_trade()
    unresolved = 0
    resolved = 0
    eligible_runtime = 0
    eligible_performance = 0
    quarantined = 0
    counts = Counter(getattr(item, "classification", "UNKNOWN") for item in summary.records)
    for item in summary.records:
        remediation = remediations.get(str(getattr(item, "trade_id", "")))
        decision = eligibility_decision(item, remediation=remediation)
        if decision.runtime_eligible:
            eligible_runtime += 1
        if decision.performance_eligible:
            eligible_performance += 1
        is_critical = getattr(item, "classification", None) in CRITICAL_CLASSIFICATIONS or any(
            issue.trade_id == item.trade_id and issue.severity == "critical" for issue in summary.issues
        )
        is_resolved = bool(remediation and remediation.remediation_action in EXCLUSION_ACTIONS)
        if is_critical and is_resolved:
            resolved += 1
        elif is_critical and decision.runtime_eligible:
            unresolved += 1
        elif is_critical and not is_resolved:
            unresolved += 1
        if getattr(item, "quarantine_status", None) == "QUARANTINED" or is_resolved:
            quarantined += 1
    baseline_status = latest_baseline.status if latest_baseline else "MISSING"
    safe = safe_mode_status or ("ACTIVE" if unresolved else "CLEARABLE")
    ready = safe == "CLEARED" and baseline_status == "PASS" and unresolved == 0
    return EnhancedIntegritySummary(
        raw_record_count=getattr(summary, "raw_record_count", getattr(summary, "total_records", 0)),
        eligible_runtime_records=eligible_runtime,
        eligible_performance_records=eligible_performance,
        quarantined_records=quarantined,
        legacy_records=counts.get("LEGACY_IMPORT", 0),
        test_fixture_records=counts.get("TEST_FIXTURE", 0),
        corrupted_records=counts.get("CORRUPTED", 0),
        incomplete_records=counts.get("INCOMPLETE", 0),
        unresolved_critical_records=unresolved,
        resolved_critical_records=resolved,
        safe_mode_status=safe,
        baseline_status=baseline_status,
        latest_baseline_id=getattr(latest_baseline, "baseline_id", None),
        ready_for_validation=ready,
        human_readable_summary=f"Integrity baseline state: {unresolved} unresolved critical record(s), {quarantined} quarantined/excluded record(s), SAFE MODE {safe}.",
    )


def incomplete_decisions(summary: Any) -> tuple[IncompleteRecordDecision, ...]:
    rows = [item for item in summary.records if item.classification == "INCOMPLETE"]
    decisions = []
    for item in rows:
        evidence = []
        if item.issue_count:
            evidence.append(f"{item.issue_count} integrity issue(s)")
        if item.lifecycle_event_count == 0:
            evidence.append("missing lifecycle history")
        if item.campaign_id in {None, "legacy_campaign"}:
            recommended = "LEGACY_IMPORT"
            evidence.append("legacy/missing campaign")
        elif not item.trade_id or not item.status:
            recommended = "INCOMPLETE"
            evidence.append("missing required runtime identity/state")
        else:
            recommended = "INCOMPLETE"
        decisions.append(IncompleteRecordDecision(
            trade_id=item.trade_id,
            source_event_id=item.source_event_id,
            campaign_id=item.campaign_id,
            current_classification=item.classification,
            recommended_classification=recommended,
            evidence=tuple(evidence),
            human_readable_summary=f"{item.trade_id or 'unknown'} remains {recommended} based on available evidence.",
        ))
    return tuple(decisions)


def duplicate_group_analysis(summary: Any) -> tuple[DuplicateGroupAnalysis, ...]:
    by_source: dict[str, list[Any]] = defaultdict(list)
    for item in summary.records:
        if item.source_event_id:
            by_source[item.source_event_id].append(item)
    groups = []
    for source, rows in sorted(by_source.items()):
        if len(rows) <= 1:
            continue
        trade_ids = tuple(sorted({str(item.trade_id) for item in rows if item.trade_id}))
        campaign_ids = tuple(sorted({str(item.campaign_id) for item in rows if item.campaign_id}))
        statuses = tuple(sorted({str(item.status) for item in rows if item.status}))
        classifications = Counter(item.classification for item in rows)
        duplicate_trade_chain = len(trade_ids) > 1 and len(set((
            getattr(item, "symbol", None),
            getattr(item, "timeframe", None),
            getattr(item, "setup", None),
            getattr(item, "opened_at", None),
            getattr(item, "closed_at", None),
        ) for item in rows)) == 1
        expected = len(trade_ids) == 1 or set(statuses).issubset({"open", "closed"})
        groups.append(DuplicateGroupAnalysis(
            source_event_id=source,
            record_count=len(rows),
            trade_ids=trade_ids,
            campaign_ids=campaign_ids,
            statuses=statuses,
            classification_summary=dict(sorted(classifications.items())),
            is_expected=expected,
            is_duplicate_trade_chain=duplicate_trade_chain,
            reason=(
                "One source event produced repeated lifecycle snapshots for the same trade."
                if len(trade_ids) == 1 else
                "Source event appears across multiple trade IDs and should remain visible for audit."
            ),
        ))
    return tuple(groups)


def rebuild_derived_state(summary: Any, *, campaign_id: str | None = None) -> RebuildDerivedStateResult:
    before = _compact_counts(summary.records)
    after = _compact_counts([item for item in summary.records if eligibility_decision(item).runtime_eligible])
    return RebuildDerivedStateResult(
        status="PASS",
        rebuilt_at=_now(),
        before_summary=before,
        after_summary=after,
        raw_journal_mutated=False,
        human_readable_summary="Derived summaries were recomputed from eligible records only; raw journal rows were not changed.",
    )


def rebuild_campaign_summary(summary: Any, campaign_id: str | None = None) -> CampaignRebuildResult:
    rows = [item for item in summary.records if campaign_id is None or item.campaign_id == campaign_id]
    eligible = [item for item in rows if eligibility_decision(item).campaign_eligible]
    excluded = [item for item in rows if item not in eligible]
    original_total = sum(float(getattr(item, "realized_r", 0) or 0) for item in rows if item.status == "closed")
    eligible_total = sum(float(getattr(item, "realized_r", 0) or 0) for item in eligible if item.status == "closed")
    status = "PASS" if not any(getattr(item, "classification", None) in CRITICAL_CLASSIFICATIONS for item in eligible) else "FAIL"
    return CampaignRebuildResult(
        campaign_id=campaign_id,
        original_trade_count=len(rows),
        eligible_trade_count=len(eligible),
        excluded_trade_count=len(excluded),
        excluded_trade_ids=tuple(str(item.trade_id) for item in excluded if item.trade_id),
        original_total_r=round(original_total, 6),
        eligible_total_r=round(eligible_total, 6),
        summary_status=status,
        human_readable_summary=f"Campaign summary rebuilt with {len(eligible)} eligible trade(s) and {len(excluded)} excluded trade(s).",
    )


def _target_records(records: Iterable[Any], trade_id: str | None, classification: str | None) -> tuple[Any, ...]:
    rows = tuple(records)
    if trade_id:
        return tuple(item for item in rows if item.trade_id == trade_id)
    if classification:
        return tuple(item for item in rows if item.classification == classification)
    return ()


def _preview_for_record(record: Any, action: str, remediation: RemediationRecord | None) -> RemediationPreview:
    before = eligibility_decision(record, remediation=remediation)
    after = eligibility_decision(record, remediation=RemediationRecord(
        remediation_id="preview",
        created_at=_now(),
        trade_id=str(record.trade_id),
        source_event_id=record.source_event_id,
        campaign_id=record.campaign_id,
        original_classification=record.classification,
        remediation_action=action,
        remediation_reason="preview",
        operator="preview",
        automatic=False,
        before_state={},
        after_state=_after_state_for(record, action),
        raw_record_preserved=True,
        reversible=True,
        version=REMEDIATION_VERSION,
    ))
    excluded = action in EXCLUSION_ACTIONS
    evidence = tuple(record.quarantine_reasons or ()) or tuple(["classification:" + record.classification])
    return RemediationPreview(
        trade_id=str(record.trade_id),
        proposed_action=action,
        current_classification=record.classification,
        runtime_effect="excluded" if excluded else "eligible_if_integrity_passes",
        campaign_effect="excluded" if excluded else "eligible_if_integrity_passes",
        performance_effect="excluded" if excluded else "eligible_if_integrity_passes",
        raw_journal_mutation=False,
        evidence=evidence,
        eligible_before=before.runtime_eligible,
        eligible_after=after.runtime_eligible,
        human_readable_summary=f"{record.trade_id} would be {action.lower()} with no raw journal mutation.",
    )


def _state_for(record: Any, remediation: RemediationRecord | None) -> dict[str, Any]:
    return {
        "classification": record.classification,
        "operational_status": (remediation.after_state or {}).get("operational_status") if remediation else record.quarantine_status,
        "quarantine_reasons": list(record.quarantine_reasons),
    }


def _after_state_for(record: Any, action: str) -> dict[str, Any]:
    if action == "RESTORE_ELIGIBILITY":
        return {"classification": record.classification, "operational_status": "ELIGIBLE"}
    status = "QUARANTINED" if action in EXCLUSION_ACTIONS else "ACKNOWLEDGED"
    return {"classification": record.classification, "operational_status": status}


def _classification_from_raw(record: Any) -> str:
    if bool(getattr(record, "test_fixture", False)):
        return "TEST_FIXTURE"
    if bool(getattr(record, "synthetic_recovery_test", False)):
        return "SYNTHETIC"
    if getattr(record, "campaign_id", None) in {None, "legacy_campaign"}:
        return "LEGACY_IMPORT"
    return "VALID_RUNTIME"


def _compact_counts(records: Iterable[Any]) -> dict[str, Any]:
    rows = tuple(records)
    return {
        "trade_count": len(rows),
        "open_trade_count": sum(getattr(item, "status", None) == "open" for item in rows),
        "closed_trade_count": sum(getattr(item, "status", None) == "closed" for item in rows),
        "classification_counts": dict(sorted(Counter(getattr(item, "classification", "UNKNOWN") for item in rows).items())),
    }


def _safe_call(obj: Any, method: str) -> tuple[Any, ...]:
    if obj is None:
        return ()
    try:
        return tuple(getattr(obj, method)())
    except Exception:
        return ()


def _fingerprint(values: Iterable[Any]) -> str:
    encoded = json.dumps([_public_dict(item) for item in values], sort_keys=True, default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:24]


def _public_dict(item: Any) -> dict[str, Any]:
    if hasattr(item, "__dict__"):
        return {k: v for k, v in item.__dict__.items() if not k.startswith("_")}
    if hasattr(item, "__dataclass_fields__"):
        return asdict(item)
    return {"value": str(item)}


def _id(prefix: str, *parts: str) -> str:
    return f"{prefix}_{hashlib.sha256(':'.join(parts).encode('utf-8')).hexdigest()[:24]}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
