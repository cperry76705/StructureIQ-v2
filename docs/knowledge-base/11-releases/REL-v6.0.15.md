# REL-v6.0.15

ID: REL-v6.0.15  
Title: StructureIQ v6.0.15 Paper Journal Integrity & Validation State Hygiene  
Category: Release  
Status: APPROVED  
Owner: Founder  
Created: 2026-08-09  
Last Updated: 2026-08-09  
Related Entries: [Risk-First Architecture](../03-engineering/KB-ENG-0003-risk-first-architecture.md), [Validation Workflow](../12-operations/validation-workflow.md), [Current Roadmap](../10-roadmap/current-roadmap.md)  
Related ADRs: [ADR-004](../07-decisions/ADR-004-paper-before-live.md), [ADR-008](../07-decisions/ADR-008-risk-first-engineering.md), [ADR-013](../07-decisions/ADR-013-research-before-production-change.md)  
Related Releases: [v6.0.14](REL-v6.0.14.md)

## Release Objective

Make paper-trading validation state trustworthy before the official seven-day production validation campaign.

## Scope

This release adds read-only integrity, duplicate, lifecycle, timestamp, quarantine, recovery, campaign, and root-cause reporting for paper journal state.

## Root-Cause Target

Trade `47cbfd066469d49904e4dc23` is explicitly supported by the root-cause investigation endpoint. If the trade is not present in the mounted workspace state, the report states that clearly instead of modifying or inventing history.

## APIs

- `GET /paper-integrity/summary`
- `GET /paper-integrity/quarantine`
- `GET /paper-integrity/duplicates`
- `GET /paper-integrity/lifecycle`
- `GET /paper-integrity/timestamps`
- `GET /paper-integrity/root-cause/{trade_id}`
- `GET /paper-integrity/campaign`
- `GET /paper-integrity/recovery`

## SAFE MODE

Critical integrity, duplicate, or timestamp corruption requires SAFE MODE and pauses continuous paper automation until validation succeeds.

## Trading Behavior Confirmation

No market structure, BOS/CHOCH, liquidity, strategy routing, candidate generation, confidence, setup quality, opportunity coverage, risk, position sizing, entries, exits, paper execution, recovery-test harness, AI explanation, or live-trading behavior changed.
