# ADR-008 — Risk-First Engineering

ID: ADR-008  
Title: Risk-First Engineering  
Category: Decision  
Status: APPROVED  
Owner: Founder  
Created: 2026-08-09  
Last Updated: 2026-08-09  
Related Entries: [Risk-First Architecture](../03-engineering/KB-ENG-0003-risk-first-architecture.md)  
Related ADRs: [ADR-004](ADR-004-paper-before-live.md)  
Related Releases: None

## Decision

Risk is a first-class subsystem.

## Consequences

Risk checks, exposure limits, daily locks, and user-level execution approval must stay separate from signal generation.
