# ADR-017 — AI Authority Model

ID: ADR-017  
Title: AI Authority Model  
Category: Decision  
Status: APPROVED  
Owner: Founder  
Created: 2026-08-09  
Last Updated: 2026-08-09  
Related Entries: [AI Partnership Model](../02-product/KB-PROD-0005-ai-partnership-model.md)  
Related ADRs: [ADR-011](ADR-011-progressive-automation.md), [ADR-016](ADR-016-premium-experience-all-plans.md), [ADR-021](ADR-021-subscription-tiers-based-on-execution-authority.md)  
Related Releases: None

## Decision

AI Authority Level is a separate behavioral control from Subscription Tier and subscription visual quality.

Subscription Tier defines the maximum execution authority available. AI Authority Level defines how much of that available authority the customer currently chooses to enable.

## Consequences

Users can understand what the AI is allowed to do independently from the product's visual tier.

Explorer is manual execution only. Professional supports approval-required Co-Pilot execution but not Autopilot. Elite supports optional Autopilot while still allowing the user to remain in Observer, Advisor, or Co-Pilot mode.
