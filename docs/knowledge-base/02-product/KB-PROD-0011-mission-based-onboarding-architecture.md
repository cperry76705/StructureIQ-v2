# Mission-Based Onboarding Architecture

ID: KB-PROD-0011  
Title: Mission-Based Onboarding Architecture  
Category: Product / Customer Experience  
Status: APPROVED  
Owner: Founder  
Created: 2026-08-09  
Last Updated: 2026-08-09  
Related Entries: [Customer Account and Lifecycle Architecture](KB-PROD-0010-customer-account-and-lifecycle-architecture.md), [Navigation & Application Shell Design System](KB-PROD-0007-navigation-application-shell-design-system.md), [AI Partnership Model](KB-PROD-0005-ai-partnership-model.md)  
Related ADRs: [ADR-029](../07-decisions/ADR-029-mission-based-curated-onboarding.md), [ADR-027](../07-decisions/ADR-027-mandatory-mfa-and-step-up-authentication.md)  
Related Releases: None

## Status and Philosophy

This entry is **APPROVED PRODUCT / CUSTOMER EXPERIENCE ARCHITECTURE**, not an implementation claim. Onboarding is mandatory but resumable. It is mission-based product education, not merely configuration, and cannot be freely skipped. Progress should persist and resume after interruption.

## Curated Scenarios

Onboarding uses curated educational market and trade scenarios rather than depending on live conditions. This provides a consistent, safe learning experience when markets are inactive, unusually volatile, or otherwise unsuitable. Scenarios are simulations and must never be presented as live opportunities or use live customer capital.

## Universal Layer

Every customer learns:

- StructureIQ mission and philosophy.
- Command Center.
- Market Intelligence.
- Trade Intelligence.
- Performance Intelligence.
- AI Partnership and AI Authority.
- Risk philosophy.
- Explainability philosophy.

## Subscription-Specific Layer

### Explorer

Emphasizes manual trading, reading Trade Plans, AI reasoning, Market Intelligence, performance review, and education.

### Professional

Includes Explorer material plus broker-connection education, approval-required execution, Co-Pilot workflow, trade-management approvals, responsibility, and intervention. Any broker connection or real execution remains governed by implementation readiness and step-up authentication.

### Elite

Includes Professional material plus optional Autopilot, execution safeguards, risk limits, override controls, monitoring autonomous execution, and stepping down or disabling authority. Autopilot is never forced.

## First Success

Onboarding concludes with a guided accomplishment:

- Explorer completes a curated Market Intelligence review.
- Professional reviews and approves a simulated AI-prepared trade.
- Elite reviews a guided simulated Autopilot workflow.

These outcomes demonstrate workflow understanding without live capital.

## Trading Commitment

The symbolic Trading Commitment reinforces discipline, education, responsible risk, process adherence, and realistic expectations. It does not replace legal risk disclosures, Terms of Service, or required consent.

## Activation Relationship

Account creation, payment where applicable, email verification, and MFA enrollment remain required security/activation steps. Onboarding follows those prerequisites and leads into Command Center. A resumable flow may show progress but must not unlock protected product use before required verification and security controls are complete.
