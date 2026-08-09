# Multi-Tenant Architecture

ID: KB-BIZ-0002  
Title: Multi-Tenant Architecture  
Category: Business  
Status: APPROVED  
Owner: Founder  
Created: 2026-08-09  
Last Updated: 2026-08-09  
Related Entries: [Commercial Model](KB-BIZ-0001-commercial-model.md)  
Related ADRs: [ADR-010](../07-decisions/ADR-010-centralized-ai-multitenancy.md), [ADR-012](../07-decisions/ADR-012-execution-safeguards.md), [ADR-021](../07-decisions/ADR-021-subscription-tiers-based-on-execution-authority.md)  
Related Releases: None

## Principle

One central AI decision engine should not be duplicated once per subscriber.

A generated opportunity may be shared across subscribers. Each subscriber receives individualized position sizing, risk validation, account rules, and execution eligibility.

## Subscription Implication

Centralized intelligence can serve all tiers without intentionally degrading lower-tier analysis. Tenant-specific behavior should apply at the execution-authority layer:

- Explorer receives intelligence and manual execution workflow.
- Professional may connect broker execution, but submitted actions require explicit approval.
- Elite may enable optional Autopilot within safeguards.

Broker execution eligibility remains tenant-specific and must validate authorization, permissions, risk controls, allowed symbols, exposure, open positions, and kill-switch state regardless of tier.
