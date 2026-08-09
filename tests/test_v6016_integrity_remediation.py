from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from fastapi.testclient import TestClient

from app.main import (
    app,
    get_journal_integrity_auditor,
    get_remediation_registry,
    get_validation_baseline_manager,
)
from core.integrity_remediation import (
    RemediationApplyRequest,
    RemediationPreviewRequest,
    RemediationRegistry,
    ValidationBaselineManager,
    duplicate_group_analysis,
    eligibility_decision,
    enhanced_summary,
    incomplete_decisions,
    rebuild_campaign_summary,
    rebuild_derived_state,
)
from core.journal_integrity import JournalIntegrityAuditor


@dataclass(frozen=True)
class Entry:
    trade_id: str
    source_event_id: str | None = None
    campaign_id: str | None = "campaign_active"
    symbol: str = "BTC-USD"
    timeframe: str = "5m"
    setup: str = "pullback"
    status: str = "closed"
    opened_at: str | None = "2026-08-09T01:00:00+00:00"
    closed_at: str | None = "2026-08-09T01:05:00+00:00"
    realized_r: float | None = 1.0
    lifecycle_events: tuple[dict, ...] = field(default_factory=lambda: ({"timestamp": "2026-08-09T01:00:00+00:00"},))
    test_fixture: bool = False
    synthetic_recovery_test: bool = False
    exclude_from_performance: bool = False
    exclude_from_campaign_metrics: bool = False
    exclude_from_daily_reports: bool = False


class Journal:
    def __init__(self, entries, path):
        self._entries = tuple(entries)
        self.path = path

    def entries(self):
        return self._entries


def _summary(tmp_path, entries, raw_lines=None):
    path = tmp_path / "paper_trade_journal.jsonl"
    if raw_lines is None:
        raw_lines = []
    path.write_text("\n".join(raw_lines), encoding="utf-8")
    return JournalIntegrityAuditor(
        journal=Journal(entries, path),
        remediation_path=tmp_path / "remediation.jsonl",
        baseline_path=tmp_path / "baselines.jsonl",
    ).summary()


def test_quarantine_confirmed_corruption_preserves_raw_journal(tmp_path):
    bad = Entry(
        trade_id="47cbfd066469d49904e4dc23",
        source_event_id="41f7446af495d4975e2e5989",
        opened_at="2026-08-09T06:59:59.994165+00:00",
        closed_at="2026-08-09T06:59:59.994165+00:00",
        lifecycle_events=(),
    )
    raw = '{"event_type":"paper_trade_closed","entry":{"trade_id":"47cbfd066469d49904e4dc23"}}'
    summary = _summary(tmp_path, [bad], [raw])
    assert summary.unresolved_critical_records == 1

    registry = RemediationRegistry(tmp_path / "remediation.jsonl")
    result = registry.apply(summary, RemediationApplyRequest(
        trade_id=bad.trade_id,
        action="QUARANTINE",
        reason="identical_open_close_timestamp_and_missing_lifecycle",
    ))

    assert result.applied_count == 1
    assert result.raw_journal_mutated is False
    assert (tmp_path / "paper_trade_journal.jsonl").read_text(encoding="utf-8") == raw

    remediated = JournalIntegrityAuditor(
        journal=Journal([bad], tmp_path / "paper_trade_journal.jsonl"),
        remediation_path=tmp_path / "remediation.jsonl",
        baseline_path=tmp_path / "baselines.jsonl",
    ).summary()
    assert remediated.resolved_critical_records == 1
    assert remediated.unresolved_critical_records == 0
    assert remediated.quarantined_records == 1


def test_runtime_performance_and_campaign_eligibility_exclude_remediation(tmp_path):
    entry = Entry("t1")
    summary = _summary(tmp_path, [entry])
    registry = RemediationRegistry(tmp_path / "remediation.jsonl")
    registry.apply(summary, RemediationApplyRequest(trade_id="t1", action="EXCLUDE_FROM_PERFORMANCE", reason="operator_review"))
    remediation = registry.latest_by_trade()["t1"]

    decision = eligibility_decision(summary.records[0], remediation=remediation)
    assert decision.runtime_eligible is False
    assert decision.performance_eligible is False
    assert decision.campaign_eligible is False


def test_incomplete_record_audit_and_duplicate_source_analysis(tmp_path):
    incomplete = Entry("missing_lifecycle", lifecycle_events=())
    duplicate_a = Entry("a", source_event_id="same-source")
    duplicate_b = Entry("b", source_event_id="same-source")
    summary = _summary(tmp_path, [incomplete, duplicate_a, duplicate_b])

    decisions = incomplete_decisions(summary)
    assert decisions
    assert decisions[0].recommended_classification == "INCOMPLETE"

    groups = duplicate_group_analysis(summary)
    assert groups[0].source_event_id == "same-source"
    assert groups[0].record_count == 2
    assert groups[0].is_duplicate_trade_chain is True


def test_baseline_rejects_unresolved_critical_and_persists_after_remediation(tmp_path):
    bad = Entry("bad", opened_at="2026-08-09T01:00:00+00:00", closed_at="2026-08-09T01:00:00+00:00")
    summary = _summary(tmp_path, [bad])
    manager = ValidationBaselineManager(tmp_path / "baselines.jsonl", tmp_path / "safe.json")

    with pytest.raises(ValueError):
        manager.create(summary)

    registry = RemediationRegistry(tmp_path / "remediation.jsonl")
    registry.apply(summary, RemediationApplyRequest(trade_id="bad", action="QUARANTINE", reason="timestamp_corruption"))
    remediated = JournalIntegrityAuditor(
        journal=Journal([bad], tmp_path / "paper_trade_journal.jsonl"),
        remediation_path=tmp_path / "remediation.jsonl",
        baseline_path=tmp_path / "baselines.jsonl",
    ).summary()
    baseline = manager.create(remediated)

    assert baseline.status == "PASS"
    assert manager.latest().baseline_id == baseline.baseline_id
    assert baseline.journal_hash_or_fingerprint


def test_safe_mode_active_clearable_and_cleared(tmp_path):
    entry = Entry("good")
    summary = _summary(tmp_path, [entry])
    manager = ValidationBaselineManager(tmp_path / "baselines.jsonl", tmp_path / "safe.json")

    assert manager.safe_mode_status(summary) == "ACTIVE"
    result = manager.clear_safe_mode(summary)
    assert result.cleared is False
    assert "baseline_exists_and_valid" in result.blocking_reasons

    manager.create(summary)
    assert manager.safe_mode_status(summary) == "CLEARABLE"
    cleared = manager.clear_safe_mode(summary)
    assert cleared.cleared is True
    assert manager.safe_mode_status(summary) == "CLEARED"


def test_remediation_preview_apply_history_and_idempotency(tmp_path):
    entry = Entry("t1", lifecycle_events=())
    summary = _summary(tmp_path, [entry])
    registry = RemediationRegistry(tmp_path / "remediation.jsonl")

    preview = registry.preview(summary, RemediationPreviewRequest(trade_id="t1", proposed_action="QUARANTINE"))
    assert preview[0].raw_journal_mutation is False
    assert preview[0].runtime_effect == "excluded"

    request = RemediationApplyRequest(trade_id="t1", action="QUARANTINE", reason="missing_lifecycle")
    first = registry.apply(summary, request)
    second = registry.apply(summary, request)

    assert first.applied_count == 1
    assert second.applied_count == 0
    assert len(registry.history("t1")) == 1


def test_derived_and_campaign_rebuild_use_eligible_records(tmp_path):
    valid = Entry("valid", campaign_id="campaign_x", realized_r=2.0)
    legacy = Entry("legacy", campaign_id="legacy_campaign", realized_r=5.0)
    summary = _summary(tmp_path, [valid, legacy])

    rebuilt = rebuild_derived_state(summary)
    campaign = rebuild_campaign_summary(summary, "campaign_x")

    assert rebuilt.status == "PASS"
    assert rebuilt.raw_journal_mutated is False
    assert campaign.original_trade_count == 1
    assert campaign.eligible_trade_count == 1
    assert campaign.eligible_total_r == 0.0  # integrity records intentionally exclude P/L fields


def test_enhanced_summary_ready_only_after_cleared_baseline(tmp_path):
    entry = Entry("good")
    summary = _summary(tmp_path, [entry])
    manager = ValidationBaselineManager(tmp_path / "baselines.jsonl", tmp_path / "safe.json")
    baseline = manager.create(summary)
    manager.clear_safe_mode(summary)

    enhanced = enhanced_summary(summary, baseline, manager.safe_mode_status(summary))

    assert enhanced.baseline_status == "PASS"
    assert enhanced.safe_mode_status == "CLEARED"
    assert enhanced.ready_for_validation is True


def test_api_endpoints_and_no_diagnostic_mutation(tmp_path):
    entry = Entry("api_bad", opened_at="2026-08-09T01:00:00+00:00", closed_at="2026-08-09T01:00:00+00:00")
    journal_path = tmp_path / "paper_trade_journal.jsonl"
    journal_path.write_text('{"event_type":"paper_trade_closed","entry":{"trade_id":"api_bad"}}', encoding="utf-8")
    remediation_path = tmp_path / "remediation.jsonl"
    baseline_path = tmp_path / "baselines.jsonl"
    safe_path = tmp_path / "safe.json"

    def auditor_override():
        return JournalIntegrityAuditor(
            journal=Journal([entry], journal_path),
            remediation_path=remediation_path,
            baseline_path=baseline_path,
        )

    app.dependency_overrides[get_journal_integrity_auditor] = auditor_override
    app.dependency_overrides[get_remediation_registry] = lambda: RemediationRegistry(remediation_path)
    app.dependency_overrides[get_validation_baseline_manager] = lambda: ValidationBaselineManager(baseline_path, safe_path)
    try:
        client = TestClient(app)
        before = journal_path.read_text(encoding="utf-8")
        summary = client.get("/paper-integrity/summary")
        preview = client.post("/paper-integrity/remediation/preview", json={"trade_id": "api_bad", "proposed_action": "QUARANTINE"})
        apply = client.post("/paper-integrity/remediation/apply", json={"trade_id": "api_bad", "action": "QUARANTINE", "reason": "timestamp_corruption"})
        baseline = client.post("/paper-integrity/create-baseline")
        history = client.get("/paper-integrity/remediation/api_bad")

        assert summary.status_code == 200
        assert preview.status_code == 200
        assert apply.status_code == 200
        assert baseline.status_code == 200
        assert history.status_code == 200
        assert journal_path.read_text(encoding="utf-8") == before
    finally:
        app.dependency_overrides.clear()
