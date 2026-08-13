# ADR-027 — Mandatory MFA and Step-Up Authentication

ID: ADR-027  
Title: Mandatory MFA and Step-Up Authentication  
Category: Decision / Security  
Status: APPROVED  
Owner: Founder  
Created: 2026-08-09  
Last Updated: 2026-08-09  
Related Entries: [Customer Account and Lifecycle Architecture](../02-product/KB-PROD-0010-customer-account-and-lifecycle-architecture.md), [Mission-Based Onboarding Architecture](../02-product/KB-PROD-0011-mission-based-onboarding-architecture.md)  
Related ADRs: [ADR-012](ADR-012-execution-safeguards.md), [ADR-017](ADR-017-ai-authority-model.md)  
Related Releases: None

## Context

StructureIQ accounts may eventually control billing, broker connections, execution approval, and autonomous authority. A valid session alone is insufficient protection for high-risk actions.

## Decision

MFA enrollment is mandatory for Explorer, Professional, and Elite during activation/onboarding. High-risk security, billing, broker, and execution-authority actions require fresh step-up authentication/MFA. Trusted-device status may reduce normal login friction but never removes step-up requirements.

Email verification is mandatory before usable protected workspace access. Approved v1 sign-in methods are Email + Password and Google Sign-In.

## Consequences

- Pending Verification users may see the Command Center shell but cannot use protected intelligence.
- Broker and Autopilot changes require fresh verification.
- Recovery codes and secure recovery flows are required parts of the intended experience.
- Exact factors, tokens, timeouts, hashing implementation, and anti-abuse mechanisms remain engineering/security implementation details.
