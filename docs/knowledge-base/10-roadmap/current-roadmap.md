# Current Roadmap

ID: KB-ROAD-0001  
Title: Current Roadmap  
Category: Roadmap  
Status: APPROVED  
Owner: Founder  
Created: 2026-08-09  
Last Updated: 2026-08-09  
Related Entries: [Validation Philosophy](../08-validation/VAL-0001-validation-philosophy.md), [Product Vision](../02-product/KB-PROD-0001-product-vision.md), [Market Intelligence Workspace](../02-product/KB-PROD-0006-market-intelligence-workspace.md)  
Related ADRs: [ADR-004](../07-decisions/ADR-004-paper-before-live.md), [ADR-011](../07-decisions/ADR-011-progressive-automation.md), [ADR-014](../07-decisions/ADR-014-expand-opportunity-set-before-lowering-quality.md), [ADR-021](../07-decisions/ADR-021-subscription-tiers-based-on-execution-authority.md), [ADR-022](../07-decisions/ADR-022-ai-first-market-research-workspace.md), [ADR-023](../07-decisions/ADR-023-persistent-authenticated-navigation-and-naming-standard.md)  
Related Releases: [v6.0.13](../11-releases/REL-v6.0.13.md), [v6.0.14](../11-releases/REL-v6.0.14.md), [v6.0.15](../11-releases/REL-v6.0.15.md), [v6.0.16](../11-releases/REL-v6.0.16.md), [v6.0.17](../11-releases/REL-v6.0.17.md)

## Roadmap

1. Apply audited integrity remediation, create a clean validation baseline, and clear SAFE MODE only through the v6.0.16 exit rules.
2. Run seven-day validation on the 9-symbol default universe after `/validation-readiness/7-day` returns READY.
3. Use run-bound recovery-test verification before interpreting restart-recovery health.
4. Use Opportunity Coverage Analytics and integrity-eligible execution metrics to identify where markets are lost in the pipeline.
5. Evaluate whether trade frequency remains commercially acceptable without lowering quality standards.
6. Build Trade Management Engine after entry validation.
7. Build intelligent exit behavior.
8. Build broker execution architecture that supports Manual → Approval Required → Optional Autopilot authority.
9. Build user accounts/subscriptions around Explorer, Professional, and Elite execution authority.
10. Build approval-required assisted execution for Professional.
11. Build optional autonomous execution for Elite.
12. Continue SaaS workspace design without degrading core intelligence across tiers.
13. Implement the approved Market Intelligence workspace as an AI-first research experience when frontend work resumes, keeping charts as supporting evidence and preserving Trade Intelligence as a separate future opportunity/trade-centric workspace.
14. Apply Navigation & Application Shell Design System v1.0 to future authenticated frontend work: one shell and the four authoritative flagship workspace names.
15. Complete Trade Intelligence design review without treating Market Explorer as global navigation; begin Performance Intelligence design separately.

## Recently Completed

- Completed market-session awareness in v6.0.13.
- Expanded the default monitored universe to BTC-USD, ETH-USD, and seven major USD Forex pairs in v6.0.14.
- Added read-only Opportunity Coverage Analytics for campaign funnel, symbol, asset-class, trade-frequency, and prop-readiness context.
- Added paper journal integrity, quarantine classification, root-cause reporting, and SAFE MODE validation hygiene in v6.0.15.
- Added append-only integrity remediation, clean validation baselines, centralized eligibility, derived rebuild summaries, and SAFE MODE exit rules in v6.0.16.
- Added recovery-test run identity, stale snapshot protection, and run-scoped cleanup in v6.0.17.
- Approved Market Intelligence Workspace v1.0 as a product design baseline.
- Approved the persistent authenticated navigation and naming standard; reclassified Morning Intelligence as Morning Brief within Command Center.
