# Trade Frequency vs Quality

ID: KB-RES-0005  
Title: Trade Frequency vs Quality  
Category: Research  
Status: APPROVED  
Owner: Founder  
Created: 2026-08-09  
Last Updated: 2026-08-09  
Related Entries: [Expanded Market Universe](../08-validation/VAL-0011-expanded-market-universe.md)  
Related ADRs: [ADR-009](../07-decisions/ADR-009-strategy-before-filter-relaxation.md), [ADR-014](../07-decisions/ADR-014-expand-opportunity-set-before-lowering-quality.md)  
Related Releases: [v6.0.14](../11-releases/REL-v6.0.14.md)

## Known Information

Candidate frequency has been low in some validation runs, but that is valid strategy behavior.

## Principle

The system should seek every valid high-quality opportunity, not force trades to meet an arbitrary activity target.

## v6.0.14 Update

Opportunity Coverage Analytics adds factual trade-frequency and selectivity measurements by campaign, symbol, and asset class. These metrics are descriptive only; high or low selectivity is not labeled good or bad without validation evidence.

## v6.0.19 Update

Approved opportunity frequency is now separated from executed-trade frequency. A selective engine may still have an execution-capture problem; conclusions require fill-rate, entry-distance, lifetime, and missed-favorable-move evidence.

v6.0.20 supplies prospective candle evidence while keeping alternative execution results non-realized.
