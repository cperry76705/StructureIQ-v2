# AI Partnership Model

ID: KB-PROD-0005  
Title: AI Partnership Model  
Category: Product  
Status: APPROVED  
Owner: Founder  
Created: 2026-08-09  
Last Updated: 2026-08-09  
Related Entries: [Subscription Model](KB-PROD-0004-subscription-model.md), [AI Principles](../04-ai/KB-AI-0001-ai-principles.md), [Market Intelligence Workspace](KB-PROD-0006-market-intelligence-workspace.md)  
Related ADRs: [ADR-011](../07-decisions/ADR-011-progressive-automation.md), [ADR-017](../07-decisions/ADR-017-ai-authority-model.md), [ADR-021](../07-decisions/ADR-021-subscription-tiers-based-on-execution-authority.md), [ADR-022](../07-decisions/ADR-022-ai-first-market-research-workspace.md)  
Related Releases: [v6.0.14](../11-releases/REL-v6.0.14.md)

## Authority Levels

- Observer: AI provides analysis and explanation only.
- Advisor: AI recommends actions; the user decides and executes unless assisted execution is separately available.
- Co-Pilot: StructureIQ prepares and may submit broker actions only after explicit user approval.
- Autopilot: StructureIQ may execute approved categories of actions automatically within user-defined safeguards.

AI Authority Level is separate from Subscription Tier. Subscription Tier defines the maximum execution authority available; AI Authority Level defines how much authority the customer has currently enabled.

Explorer is manual execution only. Professional may use Observer, Advisor, and approval-required Co-Pilot behavior. Elite may use Observer, Advisor, Co-Pilot, or optional Autopilot.

AI Authority Level is also separate from visual subscription quality. UI quality and core intelligence stay premium across plans; authority controls behavior.

AI Authority is persistent product-level status. Its location may be the lower sidebar, account area, or a consistent top-level status control, but it must remain stable across flagship workspaces rather than moving unpredictably by page.

Professional approval and Elite Autopilot never bypass execution safeguards, risk controls, user authorization, allowed-symbol checks, exposure limits, daily loss limits, broker connection checks, or kill-switch state.

## Market Intelligence Behavior

Within Market Intelligence, the AI behaves as a market research partner. It may summarize market conditions, explain structure, identify important changes, prioritize markets, summarize major drivers, and create meaningful observation events.

This behavior is explanatory and educational. It should not expose raw implementation details, source code, confidential logic, or sensitive proprietary scoring internals merely because the user asks why a conclusion was reached.

## v6.0.14 Product Implication

Opportunity Coverage strengthens the AI partnership model by explaining where potential opportunities were lost: session availability, provider data, setup quality, confidence, risk, approval, order creation, or fills.
