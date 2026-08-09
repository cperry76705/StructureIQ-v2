# REL-v6.0.14

ID: REL-v6.0.14  
Title: StructureIQ v6.0.14 Expanded FX Universe, Opportunity Coverage Analytics, and Knowledge Base Synchronization  
Category: Release  
Status: APPROVED  
Owner: Founder  
Created: 2026-08-09  
Last Updated: 2026-08-09  
Related Entries: [VAL-0011](../08-validation/VAL-0011-expanded-market-universe.md), [ADR-014](../07-decisions/ADR-014-expand-opportunity-set-before-lowering-quality.md), [Forex Market Sessions](../09-research/forex-market-sessions.md)  
Related ADRs: [ADR-014](../07-decisions/ADR-014-expand-opportunity-set-before-lowering-quality.md), [ADR-015](../07-decisions/ADR-015-prop-firm-risk-baseline.md)  
Related Releases: [v6.0.13](REL-v6.0.13.md)

## Release Objective

Expand StructureIQ's observed market universe and add read-only analytics that explain where opportunities are lost through the decision pipeline.

## Expanded Symbol Universe

Default configured universe:

- BTC-USD
- ETH-USD
- EUR-USD
- GBP-USD
- USD-JPY
- USD-CHF
- USD-CAD
- AUD-USD
- NZD-USD

## Market-Session Behavior

Crypto remains active continuously. Forex pairs are inactive while the Forex session is closed and automatically activate when Forex opens.

## Opportunity Coverage Architecture

The Opportunity Coverage Engine consumes existing candidate pipeline diagnostics and paper journal records. It creates reconciled funnel analytics using one primary terminal stage per analyzed market.

## New APIs

- `GET /opportunity-coverage/summary`
- `GET /opportunity-coverage/funnel`
- `GET /opportunity-coverage/by-symbol`
- `GET /opportunity-coverage/by-asset-class`
- `GET /opportunity-coverage/terminal-reasons`
- `GET /campaigns/{campaign_id}/opportunity-coverage`
- `GET /symbols/provider-validation`
- `GET /validation-readiness/7-day`

## New Analytics

- Candidate and opportunity funnel counts
- Symbol and asset-class coverage
- Terminal attrition reasons
- Trade performance by symbol
- Trade frequency
- Selectivity
- Prop evaluation readiness benchmark context

## Tests

Focused v6.0.14 tests cover the default universe, FX mappings, provider translation, session activation, opportunity funnel reconciliation, campaign isolation, synthetic fixture exclusion, dashboard integration, and readiness endpoint behavior.

## Known Limitations

Opportunity definitions are derived from existing pipeline state. They do not create new trade signals. Historical release details remain pending where prior records are incomplete.

## Knowledge Base Impact

Updated decision, validation, research, architecture, product, roadmap, changelog, and index entries. Added a documentation impact matrix seed.

## Trading Behavior Confirmation

Strategy, scoring, risk, entry, exit, execution, lifecycle, brokerage, GPT, notification, and live-trading behavior were not changed.
