# ADR-002 — No TradingView Scraping

ID: ADR-002  
Title: No TradingView Scraping  
Category: Decision  
Status: APPROVED  
Owner: Founder  
Created: 2026-08-09  
Last Updated: 2026-08-09  
Related Entries: [System Architecture](../03-engineering/KB-ENG-0001-system-architecture.md)  
Related ADRs: [ADR-001](ADR-001-original-intellectual-property.md)  
Related Releases: None

## Decision

TradingView may be used as visualization where appropriate, but core calculations rely on owned or licensed market data.

## Consequences

The platform avoids brittle scraping dependence and preserves a cleaner legal/technical foundation.
