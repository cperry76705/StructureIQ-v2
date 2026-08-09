from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app, get_journal_integrity_auditor
from core.continuous_paper_trading import ContinuousPaperTradingConfig, ContinuousPaperTradingRuntime
from core.journal_integrity import JournalIntegrityAuditor
from core.paper_recovery import PaperRecoveryEngine


def _write_journal(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps(entry) + "\n")


def _row(trade_id: str, **entry_extra):
    entry = {
        "trade_id": trade_id,
        "source_event_id": f"event-{trade_id}",
        "campaign_id": "campaign-prod",
        "symbol": "BTC-USD",
        "timeframe": "5m",
        "status": "closed",
        "opened_at": "2026-08-09T00:00:00+00:00",
        "closed_at": "2026-08-09T01:00:00+00:00",
        "realized_r": 1.0,
        "realized_pl": 100.0,
        "risk_amount": 100.0,
        "lifecycle_events": [{"event_id": f"life-{trade_id}", "timestamp": "2026-08-09T00:30:00+00:00"}],
    }
    entry.update(entry_extra)
    return {"event_type": "paper_trade_closed", "recorded_at": "2026-08-09T01:00:00+00:00", "entry": entry}


def test_integrity_audit_detects_duplicates_timestamps_and_quarantine(tmp_path: Path):
    journal_path = tmp_path / "paper_trade_journal.jsonl"
    _write_journal(
        journal_path,
        [
            _row("dup", source_event_id="same-source"),
            _row("dup", source_event_id="same-source"),
            _row("bad-time", opened_at="2026-08-09T02:00:00+00:00", closed_at="2026-08-09T01:00:00+00:00"),
            _row("fixture", test_fixture=True),
            _row("synthetic", synthetic_recovery_test=True),
            _row("legacy", campaign_id="legacy_campaign"),
            _row("missing-life", lifecycle_events=[]),
        ],
    )

    summary = JournalIntegrityAuditor(journal_path=journal_path).summary()

    assert summary.status == "FAIL"
    assert summary.safe_mode_required is True
    assert summary.duplicate_report.duplicate_trade_ids == {"dup": 2}
    assert summary.timestamp_audit.closed_before_opened[0].trade_id == "bad-time"
    assert summary.classification_counts["TEST_FIXTURE"] == 1
    assert summary.classification_counts["SYNTHETIC"] == 1
    assert summary.classification_counts["LEGACY_IMPORT"] == 1
    assert summary.quarantine.reasons["duplicate"] == 2
    assert summary.quarantine.reasons["timestamp_corruption"] == 1
    assert "missing_lifecycle" in summary.quarantine.reasons


def test_root_cause_reports_missing_target_trade_without_mutation(tmp_path: Path):
    journal_path = tmp_path / "paper_trade_journal.jsonl"
    _write_journal(journal_path, [_row("other")])

    report = JournalIntegrityAuditor(journal_path=journal_path).root_cause("47cbfd066469d49904e4dc23")

    assert report.found is False
    assert report.classification == "UNKNOWN"
    assert "not found" in report.root_cause


def test_read_only_api_endpoints_expose_integrity_reports(tmp_path: Path):
    journal_path = tmp_path / "paper_trade_journal.jsonl"
    _write_journal(journal_path, [_row("api"), _row("api")])
    auditor = JournalIntegrityAuditor(journal_path=journal_path)
    app.dependency_overrides[get_journal_integrity_auditor] = lambda: auditor
    try:
        client = TestClient(app)
        assert client.get("/paper-integrity/summary").json()["status"] == "FAIL"
        assert client.get("/paper-integrity/quarantine").json()["quarantined_count"] == 2
        assert client.get("/paper-integrity/duplicates").json()["duplicate_trade_ids"] == {"api": 2}
        assert client.get("/paper-integrity/lifecycle").status_code == 200
        assert client.get("/paper-integrity/timestamps").status_code == 200
        assert client.get("/paper-integrity/root-cause/api").json()["found"] is True
        assert client.get("/paper-integrity/campaign?campaign_id=campaign-prod").json()["quarantined_count"] == 2
        assert client.get("/paper-integrity/recovery").status_code == 200
    finally:
        app.dependency_overrides.clear()


class _Broker:
    def account(self):
        return SimpleNamespace(risk_status="available")


class _Orchestrator:
    def __init__(self, journal_path):
        self.journal = SimpleNamespace(path=journal_path, entries=lambda: ())
        self.lifecycle = None
        self.config = SimpleNamespace(model_copy=lambda update: SimpleNamespace(**update))
        self._journal_path = journal_path

    def run_cycle(self, config):
        raise AssertionError("safe mode should block cycles before orchestrator execution")


class _Health:
    def check(self, write_log=False):
        return SimpleNamespace(status="PASS", human_readable_summary="ok")


class _Validation:
    def run(self):
        return SimpleNamespace(validation_status="PASS", human_readable_summary="ok")


class _Scheduler:
    def start(self):
        pass

    def stop(self):
        pass


def test_safe_mode_pauses_continuous_runtime_when_integrity_fails(tmp_path: Path, monkeypatch):
    journal_path = tmp_path / "paper_trade_journal.jsonl"
    _write_journal(journal_path, [_row("safe"), _row("safe")])
    import core.continuous_paper_trading as runtime_module

    original = runtime_module.JournalIntegrityAuditor if hasattr(runtime_module, "JournalIntegrityAuditor") else None
    monkeypatch.setattr(
        "core.journal_integrity.JournalIntegrityAuditor",
        lambda **kwargs: JournalIntegrityAuditor(journal_path=journal_path),
    )
    runtime = ContinuousPaperTradingRuntime(
        _Orchestrator(journal_path),
        _Health(),
        _Validation(),
        _Broker(),
        _Scheduler(),
        ContinuousPaperTradingConfig(run_validation_on_start=False),
    )

    result = runtime.run_once()

    assert result.paused is True
    assert "SAFE MODE" in result.pause_reasons[0]


def test_recovery_excludes_quarantined_records_from_orphans(tmp_path: Path, monkeypatch):
    journal_path = tmp_path / "paper_trade_journal.jsonl"
    _write_journal(journal_path, [_row("orphan"), _row("orphan")])

    class Journal:
        path = journal_path

        def entries(self):
            return JournalIntegrityAuditor(journal_path=journal_path)._entries()

    class EmptyBroker:
        def recover_from_storage(self): pass
        def open_positions(self): return ()
        def closed_trades(self): return ()
        def account(self): return SimpleNamespace(balance=10000)
        def performance(self): return SimpleNamespace(total_r=0)

    class EmptyLifecycle:
        def recover_from_storage(self): pass
        def open_trades(self): return ()
        def closed_trades(self): return ()
        def pending_orders(self): return ()
        def events(self): return ()

    class Reconciliation:
        def run(self, persist=True):
            return SimpleNamespace(status="PASS")

    recovery = PaperRecoveryEngine(
        broker=EmptyBroker(),
        lifecycle=EmptyLifecycle(),
        journal=Journal(),
        reconciliation=Reconciliation(),
        orphan_path=tmp_path / "orphans.json",
    )

    result = recovery.run()

    assert result.summary.orphaned_trades == 0
    assert result.summary.quarantined_recovery_excluded == 2
