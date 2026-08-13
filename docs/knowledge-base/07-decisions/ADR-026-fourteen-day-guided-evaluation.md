# ADR-026 — 14-Day Guided Evaluation

ID: ADR-026  
Title: 14-Day Guided Evaluation  
Category: Decision  
Status: APPROVED  
Owner: Founder  
Created: 2026-08-09  
Last Updated: 2026-08-09  
Related Entries: [Customer Account and Lifecycle Architecture](../02-product/KB-PROD-0010-customer-account-and-lifecycle-architecture.md), [Subscription Model](../02-product/KB-PROD-0004-subscription-model.md)  
Related ADRs: [ADR-016](ADR-016-premium-experience-all-plans.md), [ADR-021](ADR-021-subscription-tiers-based-on-execution-authority.md)  
Related Releases: None

## Context

A single trading week may not expose customers to enough market variation to understand StructureIQ. Evaluation must preserve intelligence quality while preventing anonymous access and autonomous execution.

## Decision

StructureIQ will offer one 14-Day Guided Evaluation per customer. Payment method and verified email are required before activation. The evaluation is Explorer-based, includes all four flagship workspaces and full core intelligence quality, and expires after 14 days unless converted.

The evaluation may demonstrate Professional's approval-required Co-Pilot flow, but every action requires explicit user approval. Autopilot is unavailable; Elite behavior may be explained educationally only. This decision supersedes any current 7-day customer-trial concept but does not affect seven-day engineering validation campaigns.

## Consequences

- Public evaluation and paid-account entry remain separate.
- No anonymous authenticated product access is allowed.
- Evaluation entitlements must prohibit autonomous execution and unrestricted live broker connectivity.
- Product architecture approval does not imply billing, broker, or evaluation workflow implementation.
