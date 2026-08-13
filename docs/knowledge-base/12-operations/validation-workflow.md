# Validation Workflow

ID: OPS-0004  
Title: Validation Workflow  
Category: Operations  
Status: APPROVED  
Owner: Founder  
Created: 2026-08-09  
Last Updated: 2026-08-09  
Related Entries: [Validation Philosophy](../08-validation/VAL-0001-validation-philosophy.md)  
Related ADRs: [ADR-004](../07-decisions/ADR-004-paper-before-live.md), [ADR-013](../07-decisions/ADR-013-research-before-production-change.md)  
Related Releases: [v6.0.16](../11-releases/REL-v6.0.16.md), [v6.0.17](../11-releases/REL-v6.0.17.md)

## v6.0.20 Execution Research Collection

An operator may run a four-hour paper campaign using the existing command with `--hours 4`, a campaign name, and auto-approval. Research attaches automatically when enabled; actual and shadow results remain separate. No campaign starts automatically.

## Workflow

Define the validation objective, run tests, run paper campaigns where needed, preserve diagnostics, separate historical drift from active campaign behavior, and document findings before changing production behavior.

## Integrity Baseline Gate

Before a formal seven-day validation, run the paper integrity audit, preview remediation, apply only approved evidence-based remediation metadata, rebuild derived summaries, create a clean validation baseline, clear SAFE MODE through the validated endpoint, run system validation, and confirm `/validation-readiness/7-day` returns READY.

Raw journal rows must remain preserved. Remediation excludes invalid evidence from operational calculations; it does not repair trades or fabricate lifecycle history.

## Recovery Test Workflow

Recovery-test create, verify, and cleanup commands must use the same `recovery_test_run_id`. If verification returns `NOT_READY` or `AMBIGUOUS`, treat it as a harness-state issue and resolve the run state before interpreting recovery health.
