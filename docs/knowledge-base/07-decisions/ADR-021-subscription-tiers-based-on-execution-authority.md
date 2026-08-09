# ADR-021 — Subscription Tiers Based on Execution Authority

ID: ADR-021  
Title: Subscription Tiers Based on Execution Authority  
Category: Decision  
Status: APPROVED  
Owner: Founder  
Created: 2026-08-09  
Last Updated: 2026-08-09  
Related Entries: [Subscription Model](../02-product/KB-PROD-0004-subscription-model.md), [AI Partnership Model](../02-product/KB-PROD-0005-ai-partnership-model.md), [Commercial Model](../05-business/KB-BIZ-0001-commercial-model.md)  
Related ADRs: [ADR-011](ADR-011-progressive-automation.md), [ADR-016](ADR-016-premium-experience-all-plans.md), [ADR-017](ADR-017-ai-authority-model.md)  
Related Releases: None

## Decision

StructureIQ subscription differentiation will primarily be based on execution authority rather than intelligence quality.

- Explorer = manual execution.
- Professional = AI-prepared / AI-assisted execution requiring explicit user approval.
- Elite = optional autonomous execution within user-defined safeguards.

The authoritative customer journey is:

- Explorer: **Teach me.**
- Professional: **Trade with me.**
- Elite: **Trade for me.**

## Reasoning

1. Core intelligence is the principal value of StructureIQ and should not be artificially degraded for lower-tier subscribers.
2. Education is especially important for newer traders, who are likely to enter through Explorer.
3. The Professional tier provides an important psychological and operational bridge between manual trading and full automation.
4. Users should not have to choose between completely manual trading and immediately surrendering full execution authority.
5. Execution capability creates a natural SaaS upgrade path based on increasing trust in StructureIQ.
6. The model aligns with the existing AI Partnership philosophy.
7. It creates a clearer commercial story: Teach → Partner → Delegate.

## Consequences

Explorer, Professional, and Elite share the same core StructureIQ intelligence and premium product experience. Subscription tiers define the maximum execution authority available. AI Authority Level defines the authority the user currently chooses to enable within that subscription.

The previous broader feature-differentiated tier concept is **SUPERSEDED** for current product planning. Historical references should remain preserved as historical evidence, but current product documentation must use the execution-authority model.

Professional cannot silently transition into autonomous execution. Elite Autopilot remains optional. No tier bypasses execution safeguards, broker authorization, risk controls, allowed-symbol checks, exposure limits, daily loss limits, or kill-switch state.
