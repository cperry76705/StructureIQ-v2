# Expanded Market Universe

ID: VAL-0011  
Title: Expanded Market Universe  
Category: Validation  
Status: APPROVED  
Owner: Founder  
Created: 2026-08-09  
Last Updated: 2026-08-09  
Related Entries: [Trade Frequency vs Quality](../09-research/trade-frequency-vs-quality.md), [Forex Market Sessions](../09-research/forex-market-sessions.md)  
Related ADRs: [ADR-014](../07-decisions/ADR-014-expand-opportunity-set-before-lowering-quality.md)  
Related Releases: [v6.0.13](../11-releases/REL-v6.0.13.md), [v6.0.14](../11-releases/REL-v6.0.14.md)

## Summary

StructureIQ now defaults to a 9-symbol monitored universe: BTC-USD, ETH-USD, EUR-USD, GBP-USD, USD-JPY, USD-CHF, USD-CAD, AUD-USD, and NZD-USD.

The purpose of expansion is to observe more valid markets before considering any threshold or strategy changes.

## Principle

Expand opportunity coverage before weakening quality standards.

## v6.0.14 Validation Focus

- Confirm market-session filtering activates crypto continuously and Forex only during configured Forex hours.
- Measure whether increased opportunity flow comes from broader coverage, not looser standards.
- Use Opportunity Coverage Analytics to reconcile where each observed market stops.
