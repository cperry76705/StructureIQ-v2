# ADR-023 — Persistent Authenticated Navigation and Naming Standard

ID: ADR-023  
Title: Persistent Authenticated Navigation and Naming Standard  
Category: Decision  
Status: APPROVED  
Owner: Founder  
Created: 2026-08-09  
Last Updated: 2026-08-09  
Related Entries: [Navigation & Application Shell Design System](../02-product/KB-PROD-0007-navigation-application-shell-design-system.md), [Command Center](../02-product/KB-PROD-0003-command-center.md), [Market Intelligence](../02-product/KB-PROD-0006-market-intelligence-workspace.md), [Trade Intelligence](../02-product/KB-PROD-0008-trade-intelligence.md), [Performance Intelligence](../02-product/KB-PROD-0009-performance-intelligence.md)  
Related ADRs: [ADR-016](ADR-016-premium-experience-all-plans.md), [ADR-017](ADR-017-ai-authority-model.md), [ADR-021](ADR-021-subscription-tiers-based-on-execution-authority.md)  
Related Releases: None

## Context

Side-by-side review of the Landing Page, Command Center, former Morning Intelligence concept, Market Intelligence, and Trade Intelligence exposed inconsistent page names and switches between top and left navigation. These differences made related workspaces feel like separate dashboard concepts.

## Decision

StructureIQ will use one consistent authenticated navigation shell across major workspaces: persistent left sidebar navigation, a consistent top utility bar, and workspace-specific main content.

The primary workspace names are Command Center, Market Intelligence, Trade Intelligence, and Performance Intelligence. Morning Brief is embedded within Command Center rather than functioning as a separate primary workspace. Supporting and account/system destinations remain subordinate to the four-workspace hierarchy.

## Reasoning

1. Users need consistent navigation muscle memory.
2. Switching between top and left navigation makes the product feel fragmented.
3. Different names for the same destination create cognitive friction.
4. A stable shell improves perceived quality and institutional credibility.
5. StructureIQ should feel like one operating system, not multiple dashboard concepts.
6. Consistent naming improves documentation, product analytics, support, and frontend implementation.
7. The four flagship workspaces form the core daily product loop.

## Consequences

- Current authoritative documentation uses the four approved names and one shared-shell assumption.
- Morning Intelligence remains only as explicitly superseded historical terminology.
- Workspace-specific controls stay inside their workspace and cannot replace global navigation.
- Mobile preserves the hierarchy through a mobile-native pattern.
- Future changes to flagship naming or hierarchy require a new ADR.
