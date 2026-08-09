# ADR-004 — Paper Before Live

ID: ADR-004  
Title: Paper Before Live  
Category: Decision  
Status: APPROVED  
Owner: Founder  
Created: 2026-08-09  
Last Updated: 2026-08-09  
Related Entries: [Risk-First Architecture](../03-engineering/KB-ENG-0003-risk-first-architecture.md), [Continuous Paper Validation](../08-validation/VAL-0010-continuous-paper-validation.md)  
Related ADRs: [ADR-008](ADR-008-risk-first-engineering.md)  
Related Releases: [v6.0.8](../11-releases/REL-v6.0.8.md)

## Decision

Paper trading and validation precede live trading.

## Consequences

Live execution must remain blocked until validation, recovery, risk controls, and operational safeguards are proven.
