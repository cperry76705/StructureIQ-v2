# ADR-024 — AI-Selected Default Opportunity With User Override

ID: ADR-024  
Title: AI-Selected Default Opportunity With User Override  
Category: Decision  
Status: APPROVED  
Owner: Founder  
Created: 2026-08-09  
Last Updated: 2026-08-09  
Related Entries: [Trade Intelligence](../02-product/KB-PROD-0008-trade-intelligence.md)  
Related ADRs: [ADR-017](ADR-017-ai-authority-model.md), [ADR-023](ADR-023-persistent-authenticated-navigation-and-naming-standard.md)  
Related Releases: None

## Context

Trade Intelligence needs to give users immediate direction without hiding the broader market universe or transferring final selection control to the AI. AI Focus, Market Explorer, and the Opportunity Workspace need an explicit ownership model.

## Decision

On initial page load, Trade Intelligence automatically selects the highest-ranked current AI Focus opportunity and loads it into the Opportunity Workspace as AI Top Pick or an equivalent approved label. The user may override the active selection at any time by selecting another AI Focus opportunity, any other supported market in Market Explorer, or an exploratory market pathway.

AI Focus is the recommended default mode. Market Explorer remains the user-controlled Browse All Markets mode. Unsupported markets remain clearly separated from validated production markets and receive an informational exploratory experience only.

## Reasoning

1. Beginners benefit from immediate direction.
2. Advanced traders retain control.
3. The design reduces information overload without locking users into AI recommendations.
4. AI Top Pick makes recommendation ownership explicit.
5. Market Explorer supports broader research.
6. The model balances AI guidance and human agency.
7. Unsupported markets remain clearly separated from validated production markets.

## Consequences

- The initial active opportunity is deterministic from the current approved AI Focus ranking, subject to authoritative backend availability.
- Selection badges explain why the Opportunity Workspace contains a market.
- User selection updates the connected opportunity context without inventing a trade.
- Exploratory markets cannot receive validated recommendation or automated-execution status.
- This ADR approves product behavior, not its current frontend or backend implementation.
