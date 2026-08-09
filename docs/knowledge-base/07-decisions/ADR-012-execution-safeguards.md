# ADR-012 — Execution Safeguards

ID: ADR-012  
Title: Execution Safeguards  
Category: Decision  
Status: APPROVED  
Owner: Founder  
Created: 2026-08-09  
Last Updated: 2026-08-09  
Related Entries: [Risk-First Architecture](../03-engineering/KB-ENG-0003-risk-first-architecture.md)  
Related ADRs: [ADR-004](ADR-004-paper-before-live.md), [ADR-008](ADR-008-risk-first-engineering.md)  
Related Releases: [v6.0.8](../11-releases/REL-v6.0.8.md)

## Decision

Automatic execution must validate risk limits, broker status, allowed symbols, open exposure, and account restrictions.

## Consequences

Ambiguous or incomplete execution state must fail closed.
