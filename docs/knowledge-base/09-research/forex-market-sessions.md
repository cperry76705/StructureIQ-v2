# Forex Market Sessions

ID: KB-RES-0004  
Title: Forex Market Sessions  
Category: Research  
Status: APPROVED  
Owner: Founder  
Created: 2026-08-09  
Last Updated: 2026-08-09  
Related Entries: [Market Session Awareness Timeline](../06-timeline/TL-0012-market-session-awareness.md)  
Related ADRs: [ADR-014](../07-decisions/ADR-014-expand-opportunity-set-before-lowering-quality.md)  
Related Releases: [v6.0.13](../11-releases/REL-v6.0.13.md), [v6.0.14](../11-releases/REL-v6.0.14.md)

## Known Information

Forex is modeled as open from Sunday 5 PM Central through Friday 4 PM Central. Crypto remains available on weekends.

## Product Impact

During weekends, BTC-USD and ETH-USD can remain active while Forex pairs are skipped.

## v6.0.14 Update

The seven default Forex pairs are EUR-USD, GBP-USD, USD-JPY, USD-CHF, USD-CAD, AUD-USD, and NZD-USD. They remain inactive while the Forex market is closed and automatically activate when the Forex session opens.
