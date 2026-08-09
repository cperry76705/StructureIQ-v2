# REL-v6.0.8

ID: REL-v6.0.8  
Title: StructureIQ v6.0.8 Controlled Paper Auto-Approval Mode  
Category: Release  
Status: Historical Partial  
Owner: Founder  
Created: 2026-08-09  
Last Updated: 2026-08-09  
Related Entries: TL-0011, KB-AI-0002, VAL-0010  
Related ADRs: ADR-004, ADR-011, ADR-012  
Related Releases: REL-v6.0.7, REL-v6.0.13

## Summary

StructureIQ v6.0.8 introduced a safe, explicit, paper-only auto-approval mode so qualified candidates could become pending paper orders during validation runs.

Auto-approval remained disabled by default and required paper mode, paper-only safety, disabled live trading, disabled broker connections, passing health, acceptable validation state, valid candidate fields, existing confidence thresholds, no execution blockers, available risk status, no daily loss or profit lock, no duplicate order or position, and configured per-cycle limits.

## Test Count

Pending historical reconstruction.

## Notes

Known CLI controls included `--auto-approve-paper`, `--max-trades-per-cycle`, `--max-candidates-per-cycle`, `--allow-market-orders`, and `--order-type`. Market orders remained blocked unless explicitly allowed.

