# REL-v6.0.20 — Execution Research Data Capture & Shadow Execution Lab

ID: REL-v6.0.20  
Category: Release  
Status: APPROVED  
Created: 2026-08-13  
Last Updated: 2026-08-13

## Architecture

Approved lifecycle orders create immutable research snapshots under `research/execution_research`. Subsequent provider candles are retained per order with timestamp deduplication, atomic file replacement, configurable 24-hour horizon, and bounded candle count. Incomplete captures reload after restart and can resume asynchronously.

## Shadow Scenarios

The lab evaluates current limit retest, 0.10/0.25/0.50 percent tolerance, 2x/4x lifetime, and approval-price entry. Confirmation-market entry remains `INSUFFICIENT_DATA` because no deterministic reconstructable confirmation rule exists. Outcomes include not filled, win, loss, open at horizon, ambiguity, and insufficient data.

## Isolation

Every result is labeled `RESEARCH_ONLY`, `SHADOW_EXECUTION`, and `NON_REALIZED`. The lab cannot open brokerage positions, mutate lifecycle state, journal P/L, campaign P/L, balances, or risk locks. Collection failure is advisory and never escapes the lifecycle listener.

## Coverage and Limitations

Coverage reports complete, partial, empty, and evaluable orders. The interrupted v6.0.19 campaign has no reliable retained candle archive and remains `INSUFFICIENT_DATA`; no backfill outcome was fabricated.

## Prospective Validation

After operator review, a future four-hour collection may use the existing paper command with `--hours 4 --campaign-name "Execution Research Validation" --auto-approve`. This release does not start it automatically.

## Non-Regression

Strategy, market structure, setup qualification, confidence, risk, sizing, entry placement, expiration, fills, management, exits, brokers, and live trading are unchanged.
