# REL-v6.0.19 — Execution Opportunity Capture Diagnostics & Executed-Trade Audit

ID: REL-v6.0.19  
Category: Release  
Status: APPROVED  
Created: 2026-08-13  
Last Updated: 2026-08-13

## Scope

This release measures the path from approved candidate through order, fill, open trade, and closed trade. It adds missed-entry analysis, post-order MFE/MAE and target/stop chronology, research-only execution counterfactuals, by-symbol/asset/strategy/setup aggregation, capture-quality definitions, prop-style readiness metrics, and executed-trade linkage auditing.

## Research-First Boundary

`LIMIT_RETEST_CURRENT`, tolerance, extended-lifetime, approval-price, and confirmation-market scenarios are hypotheses only. Unsupported scenarios report `INSUFFICIENT_DATA`. No scenario changes order placement or realized campaign performance.

## Capture Metrics

- `SETUP_CAPTURE_RATE`: qualified setups / raw setups.
- `CANDIDATE_CAPTURE_RATE`: candidates / qualified setups.
- `APPROVED_ORDER_FILL_RATE`: filled approved orders / approved orders created.
- `APPROVED_TRADE_CAPTURE_RATE`: opened trades / approved candidates.
- `MISSED_FAVORABLE_MOVE_RATE`: unfilled analyzable orders whose original target was subsequently reached / analyzable unfilled orders.

## Executed-Trade Finding

The active-campaign rows observed during the audit share a reused test source event, lack lifecycle linkage and retained brokerage state, and contain identical open/close timestamps. They remain legitimate reconciliation failures. Future direct brokerage/test rows no longer inherit the current campaign implicitly; explicit metadata or an existing lifecycle-attributed record is required.

## Safety

Historical rows, campaign counters, P/L, R, balances, and timestamps are not rewritten. Strategy, market structure, qualification, confidence, risk, entry geometry, expiration, fills, management, exits, brokers, and live trading are unchanged.
