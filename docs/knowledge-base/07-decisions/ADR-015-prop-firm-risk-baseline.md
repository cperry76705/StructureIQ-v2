# ADR-015 — Prop-Firm Risk Baseline

ID: ADR-015  
Title: Prop-Firm Risk Baseline  
Category: Decision  
Status: APPROVED  
Owner: Founder  
Created: 2026-08-09  
Last Updated: 2026-08-09  
Related Entries: [Performance Positioning](../05-business/KB-BIZ-0004-performance-positioning.md)  
Related ADRs: [ADR-008](ADR-008-risk-first-engineering.md)  
Related Releases: [v6.0.14](../11-releases/REL-v6.0.14.md)

## Decision

Use disciplined prop-firm-style risk constraints as an internal benchmark for production trading behavior.

## Consequences

Risk-adjusted consistency matters more than attention-grabbing return claims.

## v6.0.14 Application

Prop evaluation readiness is added as read-only benchmark analytics. It does not hard-code one firm's rules as universal truth and does not modify risk controls.

v6.0.19 adds executed trades/day, approved opportunities/day, fill rate, realized R/day, expectancy, win rate, and drawdown in R. These remain descriptive diagnostics and make no profit or prop-firm guarantee.
