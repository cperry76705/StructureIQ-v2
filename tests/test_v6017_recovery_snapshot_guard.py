from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from tests.test_v6012_recovery_test_harness import _stack


def test_transactional_create_binds_fixtures_snapshot_and_run(tmp_path):
    _, _, _, _, _, _, harness = _stack(tmp_path)

    result = harness.create_recovery_test_run()

    assert result.status == "PASS"
    assert result.recovery_test_run_id.startswith("recovery_run_")
    assert result.pending_fixture.recovery_test_run_id == result.recovery_test_run_id
    assert result.open_trade_fixture.recovery_test_run_id == result.recovery_test_run_id
    assert result.snapshot.recovery_test_run_id == result.recovery_test_run_id
    assert harness.run(result.recovery_test_run_id).state == "SNAPSHOT_READY"


def test_no_valid_snapshot_returns_not_ready_and_legacy_snapshot_is_not_selected(tmp_path):
    _, _, _, _, _, _, harness = _stack(tmp_path)
    (tmp_path / "reports").mkdir(exist_ok=True)
    (tmp_path / "reports" / "recovery_test_snapshot.json").write_text(
        '{"snapshot_status":"PASS","snapshot_id":"legacy","campaign_id":"old","snapshot_at":"2026-08-09T13:28:38+00:00","fixtures":[],"ready_for_restart":true}',
        encoding="utf-8",
    )
    harness.create_pending_order()

    result = harness.verify_after_restart()

    assert result.status == "NOT_READY"
    assert result.harness_precondition_failure is True
    assert result.recovery_failure is False
    assert result.differences[0].difference_type == "RUN_STATE_DIFFERENCE"


def test_multiple_snapshot_ready_runs_are_ambiguous_without_explicit_id(tmp_path):
    _, _, _, _, _, _, harness = _stack(tmp_path)
    first = harness.create_recovery_test_run()
    second = harness.create_recovery_test_run()

    ambiguous = harness.verify_after_restart()
    explicit = harness.verify_after_restart(first.recovery_test_run_id)

    assert ambiguous.status == "AMBIGUOUS"
    assert ambiguous.harness_precondition_failure is True
    assert explicit.status in {"PASS", "FAIL", "WATCHLIST"}
    assert second.recovery_test_run_id != first.recovery_test_run_id


def test_missing_recovered_fixture_is_genuine_recovery_failure(tmp_path):
    _, _, _, _, _, _, harness = _stack(tmp_path)
    created = harness.create_recovery_test_run()
    harness.lifecycle.remove_recovery_test_fixtures(created.recovery_test_run_id)

    result = harness.verify_after_restart(created.recovery_test_run_id)

    assert result.status == "FAIL"
    assert result.recovery_failure is True
    assert all(item.difference_type == "RECOVERY_DIFFERENCE" for item in result.differences)


def test_cleanup_is_run_scoped_and_idempotent(tmp_path):
    _, _, _, _, _, _, harness = _stack(tmp_path)
    first = harness.create_recovery_test_run()
    second = harness.create_recovery_test_run()

    cleaned = harness.cleanup(first.recovery_test_run_id)
    second_status = harness.status(second.recovery_test_run_id)
    cleaned_again = harness.cleanup(first.recovery_test_run_id)

    assert cleaned.status == "PASS"
    assert cleaned.run_state == "CLEANED"
    assert second_status.active_fixture_count == 2
    assert cleaned_again.status == "PASS"
    assert cleaned_again.fixtures_archived == 0


def test_incomplete_run_snapshot_retry_and_cleanup(tmp_path):
    _, _, _, _, _, _, harness = _stack(tmp_path)
    fixture = harness.create_pending_order()
    run = harness.run(fixture.recovery_test_run_id)

    harness._transition(run.recovery_test_run_id, "INCOMPLETE", note="simulated snapshot failure")
    incomplete = harness.incomplete_runs()
    retry = harness.snapshot(run.recovery_test_run_id)
    state_after_retry = harness.run(run.recovery_test_run_id).state
    cleanup = harness.cleanup(run.recovery_test_run_id)

    assert incomplete[0].recovery_test_run_id == run.recovery_test_run_id
    assert retry.snapshot_status == "PASS"
    assert state_after_retry == "SNAPSHOT_READY"
    assert cleanup.status == "PASS"


def test_recovery_test_run_api_endpoints_registered():
    client = TestClient(app)
    paths = client.get("/openapi.json").json()["paths"]

    for path in (
        "/recovery-test/runs",
        "/recovery-test/runs/current",
        "/recovery-test/runs/incomplete",
        "/recovery-test/runs/{run_id}",
        "/recovery-test/runs/{run_id}/snapshot",
        "/recovery-test/runs/{run_id}/verify",
        "/recovery-test/runs/{run_id}/cleanup",
    ):
        assert path in paths
