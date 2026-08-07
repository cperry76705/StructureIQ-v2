from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

import start
from app.main import app, get_candidate_pipeline_diagnostics_engine, get_paper_state_reconciliation_engine
from core.candidate_diagnostics import CandidateDiagnosticsEngine
from core.candidate_pipeline_diagnostics import CandidatePipelineDiagnosticsEngine
from core.paper_recovery import PaperRecoveryEngine
from core.paper_state_reconciliation import PaperStateReconciliationEngine
from core.validation_campaigns import ValidationCampaignManager


class _Journal:
    def __init__(self, entries):
        self._entries = tuple(entries)
    def entries(self):
        return self._entries
    def summary(self):
        closed = [item for item in self._entries if item.status == "closed" and item.realized_r is not None]
        return SimpleNamespace(
            open_trades=sum(item.status == "open" for item in self._entries),
            closed_trades=len(closed),
            total_r=sum(float(item.realized_r or 0) for item in closed),
            realized_pl=sum(float(item.realized_pl or 0) for item in closed),
        )


class _Broker:
    def open_positions(self): return ()
    def closed_trades(self): return ()
    def performance(self): return SimpleNamespace(total_r=0.0, realized_pl=0.0)
    def account(self): return SimpleNamespace(balance=10000.0)
    def recover_from_storage(self): return None


class _Lifecycle:
    def pending_orders(self): return ()
    def open_trades(self): return ()
    def closed_trades(self): return ()
    def events(self): return ()
    def recover_from_storage(self): return None


class _Reports:
    def latest(self): return None


class _Orchestrator:
    def status(self): return SimpleNamespace(cycle_count=0)
    def recent_actions(self, limit=None): return ()


def _entry(trade_id, *, campaign_id=None, status="closed", realized_r=3.0):
    return SimpleNamespace(
        trade_id=trade_id, campaign_id=campaign_id, symbol="BTC-USD", timeframe="5m",
        status=status, realized_r=realized_r, realized_pl=(realized_r or 0) * 100,
        source_event_id=f"event-{trade_id}", lifecycle_events=(), warnings=(),
        opened_at="2026-07-23T00:00:00+00:00",
        closed_at="2026-07-23T00:05:00+00:00" if status == "closed" else None,
        risk_amount=100,
    )


class _Campaigns:
    def __init__(self, campaign_id="campaign_active"):
        self._current = SimpleNamespace(campaign_id=campaign_id, status="running")
    def current(self):
        return self._current


def _reconciliation(entries, *, campaigns=None):
    return PaperStateReconciliationEngine(
        broker=_Broker(), lifecycle=_Lifecycle(), journal=_Journal(entries),
        reports=_Reports(), orchestrator=_Orchestrator(), campaigns=campaigns,
    )


def test_active_campaign_reconciliation_excludes_legacy_discrepancies():
    engine = _reconciliation(
        [_entry("legacy-1", campaign_id=None), _entry("active-1", campaign_id="campaign_active")],
        campaigns=_Campaigns("campaign_active"),
    )

    global_result = engine.run(persist=False, scope="global")
    active_result = engine.run(persist=False, scope="active_campaign")

    assert global_result.summary.discrepancy_count > active_result.summary.discrepancy_count
    assert active_result.summary.scope == "active_campaign"
    assert active_result.summary.active_campaign_id == "campaign_active"
    assert all(item.campaign_id == "campaign_active" for item in active_result.trades)


def test_invalid_and_missing_campaign_reconciliation_scope():
    engine = _reconciliation([], campaigns=_Campaigns())
    try:
        engine.run(persist=False, scope="banana")
    except ValueError as exc:
        assert "unsupported" in str(exc)
    else:
        raise AssertionError("invalid reconciliation scope should fail")
    try:
        engine.run(persist=False, scope="campaign")
    except ValueError as exc:
        assert "campaign_id" in str(exc)
    else:
        raise AssertionError("campaign scope requires campaign_id")


def test_orphan_classifications_separate_legacy_from_current(tmp_path: Path):
    entries = [_entry("legacy-1", campaign_id=None), _entry("current-1", campaign_id="campaign_active")]
    reconciliation = _reconciliation(entries, campaigns=_Campaigns("campaign_active"))
    recovery = PaperRecoveryEngine(
        broker=_Broker(), lifecycle=_Lifecycle(), journal=_Journal(entries),
        reconciliation=reconciliation, orphan_path=tmp_path / "orphans.json",
    )

    result = recovery.run(persist_reconciliation=False)

    classifications = {item.trade_id: item.orphan_classification for item in result.orphans}
    assert classifications["legacy-1"] == "LEGACY_PRE_PERSISTENCE"
    assert classifications["current-1"] == "CLOSED_TRADE_NOT_RECOVERED"
    assert result.summary.legacy_orphaned_trades == 1
    assert result.summary.current_campaign_orphaned_trades == 1


def test_legacy_campaign_audit_explains_count_and_r_difference(tmp_path: Path):
    current_entries = [
        _entry("legacy-1", campaign_id=None, realized_r=3),
        _entry("legacy-2", campaign_id=None, realized_r=3),
        _entry("post-1", campaign_id="campaign_new", realized_r=3),
        _entry("open-1", campaign_id="campaign_new", status="open", realized_r=None),
    ]
    manager = ValidationCampaignManager(tmp_path / "validation_campaigns", _Journal(current_entries[:2]))
    snapshot = tmp_path / "validation_campaigns" / "legacy_campaign" / "journal.jsonl"
    snapshot.write_text("\n".join(json.dumps({"trade_id": e.trade_id, "campaign_id": e.campaign_id, "status": e.status, "realized_r": e.realized_r, "opened_at": e.opened_at, "closed_at": e.closed_at}) for e in current_entries[:2]), encoding="utf-8")
    manager.journal = _Journal(current_entries)

    audit = manager.legacy_audit()

    assert audit.journal_record_count == 4
    assert audit.legacy_campaign_trade_count == 2
    assert audit.journal_closed_count == 3
    assert audit.journal_open_count == 1
    assert audit.count_difference == 2
    assert audit.r_difference == 3
    assert "post-1" in audit.mismatched_trade_ids


def test_candidate_pipeline_zero_candidate_persistence_and_api(tmp_path: Path):
    market = CandidateDiagnosticsEngine(tmp_path / "market.jsonl")
    market.record_failure(symbol="BTC-USD", timeframe="5m", higher_timeframe="1h", error="provider unavailable")
    pipeline = CandidatePipelineDiagnosticsEngine(tmp_path / "cycles.jsonl", campaigns_root=tmp_path / "campaigns")
    cycle = pipeline.record_cycle(
        cycle_id="cycle-1", campaign_id="campaign_a",
        started_at="2026-07-23T00:00:00+00:00",
        completed_at="2026-07-23T00:00:01+00:00",
        monitor_result=SimpleNamespace(analyzed=0, candidates_created=0, errors=("BTC-USD 5m: provider unavailable",), events=()),
        orders_created=0, trades_opened=0, cycle_status="completed_with_errors",
        configured_symbols=("BTC-USD",), configured_timeframes=("5m",),
        recent_market_diagnostics=market.recent(),
    )

    assert cycle.zero_candidate_explanation
    assert pipeline.summary(campaign_id="campaign_a").symbols_without_data == 1
    assert (tmp_path / "cycles.jsonl").exists()
    assert (tmp_path / "campaigns" / "campaign_a" / "candidate_diagnostics.jsonl").exists()

    app.dependency_overrides[get_candidate_pipeline_diagnostics_engine] = lambda: pipeline
    try:
        client = TestClient(app)
        paths = client.get("/openapi.json").json()["paths"]
        assert "/candidate-diagnostics/cycles/{cycle_id}" in paths
        assert "/candidate-diagnostics/rejections" in paths
        assert client.get("/candidate-diagnostics/cycles/cycle-1").json()["cycle_id"] == "cycle-1"
        assert client.get("/campaigns/campaign_a/candidate-diagnostics").json()["cycles"] == 1
    finally:
        app.dependency_overrides.clear()


def test_reconciliation_scope_api_returns_422_for_invalid_scope():
    engine = _reconciliation([], campaigns=_Campaigns())
    app.dependency_overrides[get_paper_state_reconciliation_engine] = lambda: engine
    try:
        client = TestClient(app)
        assert client.get("/paper-reconciliation/summary?scope=active_campaign").json()["scope"] == "active_campaign"
        assert client.get("/paper-reconciliation/summary?scope=invalid").status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_cli_auto_approve_aliases_and_campaign_display(capsys):
    payload, _, _ = start.build_paper_start_payload(start.parse_args(["--paper", "--campaign-name", "Recovery Validation", "--auto-approve"]))
    assert payload["auto_approve_candidates"] is True
    assert payload["session_label"] == "Recovery Validation"
    payload, _, _ = start.build_paper_start_payload(start.parse_args(["--paper", "--auto-approve-paper", "--no-auto-approve"]))
    assert payload["auto_approve_candidates"] is False

    calls = []
    def api(path, **kwargs):
        calls.append(path)
        if path == "/health": return {"status": "ok"}
        if path == "/system/validation/run": return {"validation_status": "PASS"}
        if path == "/campaigns/current": return {"name": "Recovery Validation", "campaign_id": "campaign_123"}
        if path == "/continuous-paper/start":
            return {"running": False, "paused": False, "session_label": "Recovery Validation", "final_session_summary": {"cycle_count": 0, "stop_reason": "max_cycles_reached"}}
        if path == "/candidate-diagnostics/summary":
            return {"pipeline": {"latest_cycle": {"symbols_scanned": 0, "symbols_with_market_data": 0, "zero_candidate_explanation": "No candidates reached the approval stage."}}}
        return {"running": False}
    assert start.run_paper_mode(
        start.parse_args(["--paper", "--cycles", "1", "--campaign-name", "Recovery Validation", "--auto-approve"]),
        process_factory=lambda *a, **k: SimpleNamespace(poll=lambda: 0, terminate=lambda: None, wait=lambda timeout=None: 0, kill=lambda: None),
        api_call=api, sleep=lambda _: None, port_available=lambda: True,
    ) == 0
    output = capsys.readouterr().out
    assert "Campaign Name: Recovery Validation" in output
    assert "Campaign ID: campaign_123" in output
    assert "Session Label: Recovery Validation" in output
    assert "Auto Approval: true" in output
