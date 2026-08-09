# Subscription Model

ID: KB-PROD-0004  
Title: Subscription Model  
Category: Product  
Status: APPROVED  
Owner: Founder  
Created: 2026-08-09  
Last Updated: 2026-08-09  
Related Entries: [AI Partnership Model](KB-PROD-0005-ai-partnership-model.md), [Command Center](KB-PROD-0003-command-center.md)  
Related ADRs: [ADR-011](../07-decisions/ADR-011-progressive-automation.md), [ADR-017](../07-decisions/ADR-017-ai-authority-model.md), [ADR-021](../07-decisions/ADR-021-subscription-tiers-based-on-execution-authority.md)  
Related Releases: None

## Governing Principle

StructureIQ retains three subscription tiers: Explorer, Professional, and Elite.

The authoritative model is:

**All subscription tiers receive the same core StructureIQ intelligence and the same premium product experience. The primary difference between tiers is execution authority.**

This supersedes the earlier broader feature-differentiated concept where tiers might have been separated by progressively stronger intelligence, analytics, coaching, research, or visual functionality.

## Intelligence Equality Principle

Subscription tiers determine execution authority, not the quality of StructureIQ's core intelligence.

Explorer users should not receive intentionally inferior research, explanations, Market Intelligence, decision quality analysis, educational tools, or Command Center quality merely to create an upgrade incentive.

Higher tiers monetize operational capability, convenience, broker integration, assisted execution, and autonomous execution.

## Premium Experience Principle

Every subscription tier must feel like a premium StructureIQ product. StructureIQ should not create intentionally degraded dashboards, large numbers of locked intelligence widgets, visibly inferior lower-tier interfaces, or artificial educational restrictions.

The same visual system and core workspace architecture should remain recognizable across plans.

## Explorer

Explorer is the signal/manual-execution tier.

Conceptual model: **Teach me.**

Supporting language: Learn. Decide. Execute.

Explorer receives the complete core intelligence experience, including Command Center, Market Intelligence, Morning Brief within Command Center, Since Your Last Visit, Capital Intelligence, Yesterday's Debrief, Decision Quality, Today's Opportunities, AI Focus List, Intelligence Feed, Daily Scorecard, Learning & Coaching, explanations, research, trade reasoning, confidence, setup information, entry guidance, stop-loss guidance, target guidance, risk context, alerts, notifications, and performance/educational review where available.

Explorer does not permit StructureIQ to place trades for the user. The user manually enters, manages, adjusts, and exits trades.

Maximum AI Authority Level: **Observer / Manual**.

## Professional

Professional contains the same core intelligence and premium interface as Explorer.

Conceptual model: **Trade with me.**

Supporting language: Review. Approve. Partner.

Professional adds AI-assisted broker execution with mandatory user approval. StructureIQ may prepare an order from an approved trade plan and submit it through a broker only after explicit user approval.

During a trade, StructureIQ may recommend moving stops, moving to break-even, taking partial profit, holding, reducing exposure, or exiting. Any broker action that requires execution must be explicitly approved by the user.

Maximum AI Authority Levels: **Observer** and **Advisor / Co-Pilot with Required Approval**.

Professional must not silently transition into autonomous execution. The defining difference between Explorer and Professional is execution assistance, not better intelligence.

## Elite

Elite includes the same intelligence and product experience as Explorer and Professional.

Conceptual model: **Trade for me.**

Supporting language: Delegate. Monitor. Control.

Elite adds optional autonomous execution. When Autopilot is enabled and all safeguards are satisfied, StructureIQ may eventually enter trades, manage open positions, adjust stops, take partial profits, exit trades, enforce portfolio risk rules, and manage the lifecycle without individual approval.

Autopilot remains optional. Elite subscribers may operate indefinitely in Observer, Advisor, Co-Pilot/approval-required, or Autopilot mode.

Maximum AI Authority Levels: **Observer**, **Advisor**, **Co-Pilot**, and **Autopilot**.

Elite does not force users to surrender control.

## Tier vs Authority Level

Subscription Tier defines the maximum execution authority available. AI Authority Level defines how much of that available authority the customer has currently chosen to enable.

An Elite subscriber may remain in Observer or approval-required mode indefinitely. A Professional subscriber cannot enable full Autopilot because autonomous authority is outside the Professional capability. Explorer remains manual execution only.

## Safety and Execution Controls

All tiers use the same premium authenticated application shell and flagship workspace hierarchy. Navigation must not visually degrade or become a separate shell for Explorer, Professional, or Elite; only authorized behavior changes.

Professional approval and Elite Autopilot do not bypass risk controls. Broker execution must validate applicable controls such as broker connection status, user authorization, allowed symbols, risk percentage, daily loss limits, exposure, open positions, execution/slippage conditions, trade-management permissions, and kill-switch state.

## Performance Intelligence Across Tiers

Every tier receives the same core Performance Intelligence quality. Explorer emphasizes manually executed decisions and behavior. Professional may eventually compare approvals, rejections, assisted execution, and AI recommendations. Elite may eventually compare Autopilot, Co-Pilot, manual overrides, autonomous periods, and user intervention. These contexts do not create visually inferior lower-tier versions or claim that every attribution integration exists.
