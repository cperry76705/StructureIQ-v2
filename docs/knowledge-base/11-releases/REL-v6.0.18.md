# REL-v6.0.18 — Lifecycle Record Classification & Campaign Recovery Semantics

ID: REL-v6.0.18  
Title: Lifecycle Record Classification & Campaign Recovery Semantics  
Category: Release  
Status: APPROVED  
Owner: Founder  
Created: 2026-08-13  
Last Updated: 2026-08-13  

## Root Cause and Classification

Recovery treated journal membership and trade-like identifiers as trade evidence. Unfilled order snapshots could therefore appear to be missing trades after restart. v6.0.18 derives `PENDING_ORDER`, `EXPIRED_ORDER`, `OPEN_TRADE`, and `CLOSED_TRADE` from canonical fill/open/close evidence. An identifier, candidate approval, or order creation alone cannot establish a trade.

## Orphan and Campaign Semantics

An orphan is an executed position that cannot be reconciled with expected durable state. Pending and terminal unfilled orders remain visible but are excluded from orphan counts. Active-campaign executed orphans determine active-campaign recovery; genuine legacy anomalies remain separate and may retain legacy/global `WATCHLIST` status.

## Compatibility and Observability

Classification is derived without migrating or rewriting historical artifacts. Quarantine and synthetic-test exclusions remain intact. Recovery and reconciliation expose classification counts alongside orphan counts.

## Opportunity Coverage

Opportunity Coverage is registered at `/opportunity-coverage/summary` and its documented detail routes, plus `/campaigns/{campaign_id}/opportunity-coverage`. The bare `/opportunity-coverage` path was not part of the existing contract, so no duplicate route was added.

## Regression Coverage and Trading Behavior

Tests cover all four classifications, identifier neutrality, active/legacy isolation, genuine orphan preservation, exclusions, and restart hydration. No strategy, setup, confidence, risk/reward, order-entry, fill, exit, or trade-management behavior changed. No historical data was deleted or fabricated.
