# Continuous Paper Validation

ID: VAL-0010  
Title: Continuous Paper Validation  
Category: Validation  
Status: APPROVED  
Owner: Founder  
Created: 2026-08-09  
Last Updated: 2026-08-09  
Related Entries: [Continuous Paper Trading Timeline](../06-timeline/TL-0011-continuous-paper-trading.md)  
Related ADRs: [ADR-004](../07-decisions/ADR-004-paper-before-live.md), [ADR-012](../07-decisions/ADR-012-execution-safeguards.md)  
Related Releases: [v6.0.8](../11-releases/REL-v6.0.8.md), [v6.0.13](../11-releases/REL-v6.0.13.md), [v6.0.16](../11-releases/REL-v6.0.16.md), [v6.0.17](../11-releases/REL-v6.0.17.md)

## Summary

Continuous paper validation includes 24-hour and planned 7-day validation campaigns.

## Purpose

Long-running paper validation tests runtime stability, candidate frequency, lifecycle safety, recovery behavior, diagnostics, and reporting.

## Integrity Gate

Formal seven-day validation requires a clean paper integrity baseline, zero unresolved critical eligible records, SAFE MODE cleared through validated exit rules, and recovery/reconciliation statuses that are not FAIL. Historical or quarantined evidence remains auditable but must not contaminate operational validation metrics.

## Recovery Test Guard

Deterministic recovery tests must be verified by `recovery_test_run_id`. A stale legacy snapshot, incomplete run, or ambiguous set of ready runs is a harness precondition failure, not a recovery failure. Genuine recovery failures are reported separately as `RECOVERY_DIFFERENCE`.
