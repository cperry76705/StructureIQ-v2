# KB-DESIGN-0004 — Guided Evaluation Step 2

Design ID: KB-DESIGN-0004  
Page name: Guided Evaluation Step 2 — Secure Payment  
Version: 1.0  
Status: APPROVED  
Visual Source of Truth: `Guided Evaluation Step 2 v1.0.png`  
Implementation Status: APPROVED DESIGN / FRONTEND IMPLEMENTED / VISUAL FIDELITY REVIEW REQUIRED

![Guided Evaluation Step 2 v1.0](./Guided%20Evaluation%20Step%202%20v1.0.png)

## Purpose

Collect a payment method for the 14-Day Guided Evaluation while making $0-today/no-charge messaging explicit.

## Key Visual Decisions

- Same wizard shell as Step 1.
- Secure payment panel with card and billing fields.
- Evaluation summary and security/trust support panels.

## Key Interaction Decisions

- Payment details are abstracted and not stored by StructureIQ.
- User acknowledges billing terms before activation.
- Primary CTA: Activate My 14-Day Guided Evaluation.

## Related KB-PROD Entry

- [Customer Account and Lifecycle Architecture](../02-product/KB-PROD-0010-customer-account-and-lifecycle-architecture.md)

## Related ADRs

- [ADR-026 — Fourteen-Day Guided Evaluation](../07-decisions/ADR-026-fourteen-day-guided-evaluation.md)

## Authoritative Note

The PNG is the authoritative visual specification.
