# ADR-028 — Customer Lifecycle and Account-State Model

ID: ADR-028  
Title: Customer Lifecycle and Account-State Model  
Category: Decision / Product Architecture  
Status: APPROVED  
Owner: Founder  
Created: 2026-08-09  
Last Updated: 2026-08-09  
Related Entries: [Customer Account and Lifecycle Architecture](../02-product/KB-PROD-0010-customer-account-and-lifecycle-architecture.md), [Subscription Model](../02-product/KB-PROD-0004-subscription-model.md)  
Related ADRs: [ADR-021](ADR-021-subscription-tiers-based-on-execution-authority.md), [ADR-027](ADR-027-mandatory-mfa-and-step-up-authentication.md)  
Related Releases: None

## Context

Billing status, subscription, security posture, and AI Authority jointly determine what a customer may access. Treating subscription name alone as authorization would create unsafe and inconsistent lifecycle behavior.

## Decision

StructureIQ will model Visitor, Pending Registration, Pending Verification, Guided Evaluation, Active Explorer, Active Professional, Active Elite, Grace Period, Suspended, Canceled, Locked, and Deleted states. Effective permissions derive from Account State + Subscription + AI Authority + Security Status.

Upgrades take effect after successful processing; downgrades take effect next billing cycle, with one plan change permitted per billing cycle. Failed renewals receive a conceptual seven-day grace period. Cancellation ends renewal but preserves paid access through the current term. Inactive/suspended history is retained approximately 90 days before deletion processing, subject to legal/privacy validation.

## Consequences

- State transitions must fail safely and cannot silently elevate execution authority.
- Account Health may expose verification, MFA, payment, broker, device, and security status without an unvalidated numeric score.
- Billing schedules, transition orchestration, and deletion jobs remain future implementation details.
