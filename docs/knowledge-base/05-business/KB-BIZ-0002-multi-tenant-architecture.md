# Multi-Tenant Architecture

ID: KB-BIZ-0002  
Title: Multi-Tenant Architecture  
Category: Business  
Status: APPROVED  
Owner: Founder  
Created: 2026-08-09  
Last Updated: 2026-08-09  
Related Entries: [Commercial Model](KB-BIZ-0001-commercial-model.md)  
Related ADRs: [ADR-010](../07-decisions/ADR-010-centralized-ai-multitenancy.md), [ADR-012](../07-decisions/ADR-012-execution-safeguards.md)  
Related Releases: None

## Principle

One central AI decision engine should not be duplicated once per subscriber.

A generated opportunity may be shared across subscribers. Each subscriber receives individualized position sizing, risk validation, account rules, and execution eligibility.
