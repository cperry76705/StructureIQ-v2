# KB-DESIGN-0005 — Guided Evaluation Step 3

Design ID: KB-DESIGN-0005  
Page name: Guided Evaluation Step 3 — Verify & Secure  
Version: 1.0  
Status: APPROVED  
Visual Source of Truth: `Guided Evaluation Step 3 v1.0.png`  
Implementation Status: APPROVED DESIGN / FRONTEND IMPLEMENTED / VISUAL FIDELITY REVIEW REQUIRED

![Guided Evaluation Step 3 v1.0](./Guided%20Evaluation%20Step%203%20v1.0.png)

## Purpose

Verify email and enroll mandatory MFA before the user enters the authenticated product.

## Key Visual Decisions

- Step 3 is highlighted in the wizard.
- Email verification and authenticator-app setup are visually paired.
- Security education remains prominent.

## Key Interaction Decisions

- Resend verification action is visible.
- Authenticator app is primary/recommended MFA.
- Six-digit code entry and Remember this device are visible.
- Recovery-code education is included.

## Related KB-PROD Entry

- [Customer Account and Lifecycle Architecture](../02-product/KB-PROD-0010-customer-account-and-lifecycle-architecture.md)

## Related ADRs

- [ADR-027 — Mandatory MFA and Step-Up Authentication](../07-decisions/ADR-027-mandatory-mfa-and-step-up-authentication.md)

## Authoritative Note

The PNG is the authoritative visual specification.
