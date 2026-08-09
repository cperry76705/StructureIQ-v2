# REL-v6.0.13

ID: REL-v6.0.13  
Title: StructureIQ v6.0.13 Intelligent Market Session Awareness  
Category: Release  
Status: Historical Partial  
Owner: Founder  
Created: 2026-08-09  
Last Updated: 2026-08-09  
Related Entries: TL-0012, VAL-0011, forex-market-sessions  
Related ADRs: ADR-013, ADR-014  
Related Releases: REL-v6.0.8

## Summary

StructureIQ v6.0.13 added intelligent market session awareness so the platform can understand whether markets are currently open, closed, active, inactive, or available continuously depending on symbol class.

Known behavior includes crypto 24/7 availability, forex availability from Sunday 5:00 PM Central Time through Friday 4:00 PM Central Time, symbol classification, `/market-sessions`, `/watchlist/active`, candidate skip diagnostics, campaign skip counters, dashboard visibility, and CLI reporting.

## Test Count

524 tests passed during the v6.0.13 validation run.

## Notes

This release improved validation realism by distinguishing unavailable markets from weak trading opportunities.

