# REL-v6.0.17 — Recovery Test Snapshot Integrity Guard

ID: REL-v6.0.17  
Title: Recovery Test Snapshot Integrity Guard  
Category: Release  
Status: APPROVED  
Owner: Founder  
Created: 2026-08-09  
Last Updated: 2026-08-09  
Related Entries: [Continuous Paper Validation](../08-validation/VAL-0010-continuous-paper-validation.md), [Validation Workflow](../12-operations/validation-workflow.md), [Development Workflow](../12-operations/development-workflow.md)  
Related ADRs: [ADR-004 Paper Before Live](../07-decisions/ADR-004-paper-before-live.md)

## Purpose

StructureIQ v6.0.17 prevents the deterministic recovery-test harness from verifying against unrelated or stale snapshots. The release protects validation infrastructure; it does not change trading behavior.

## Recovery-Test Run Identity

Every deterministic recovery test has a `recovery_test_run_id`. Fixtures, snapshots, verification events, cleanup events, and history rows carry the same run ID. Campaign IDs and timestamps are no longer sufficient to resolve the current recovery test.

## Transactional Create Flow

The create command now starts a run, creates the pending-order fixture, creates the open-trade fixture, marks fixtures created, creates a snapshot, validates the snapshot, and transitions the run to `SNAPSHOT_READY`. If the snapshot phase fails, the run is marked `INCOMPLETE`.

## Stale Snapshot Protection

Verification only uses a snapshot when the requested/current run is `SNAPSHOT_READY` and the snapshot is bound to that same run ID with `snapshot_status=PASS`. Legacy history rows without run IDs remain viewable but are never selected automatically.

## Run-Scoped Cleanup

Cleanup requires a resolved or explicit run ID and only removes fixtures tagged with the matching `recovery_test_run_id`. Cleanup is idempotent and marks the run `CLEANED`.

## Incomplete Run Handling

Incomplete runs can be listed, cleaned, or snapshotted again if fixtures remain valid. Snapshot retry does not create a new run implicitly.

## Recovery Failure vs Harness Preconditions

Harness-state problems return `NOT_READY` or `AMBIGUOUS` with `RUN_STATE_DIFFERENCE`, `SNAPSHOT_DIFFERENCE`, or `HARNESS_STATE_DIFFERENCE`. Only `RECOVERY_DIFFERENCE` represents a genuine recovery failure.

## Trading Behavior

No strategy, market structure, candidate generation, confidence scoring, setup quality, risk, entries, exits, fills, normal lifecycle behavior, opportunity coverage, broker integration, GPT, notifications, or live-trading behavior changed.
