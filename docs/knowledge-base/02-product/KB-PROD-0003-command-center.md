# StructureIQ Command Center v1.0

ID: KB-PROD-0003  
Title: StructureIQ Command Center v1.0  
Category: Product  
Status: APPROVED  
Owner: Founder  
Created: 2026-08-09  
Last Updated: 2026-08-09  
Related Entries: [Product Vision](KB-PROD-0001-product-vision.md), [AI Partnership Model](KB-PROD-0005-ai-partnership-model.md), [Market Intelligence Workspace](KB-PROD-0006-market-intelligence-workspace.md), [Navigation & Application Shell Design System](KB-PROD-0007-navigation-application-shell-design-system.md)  
Related ADRs: [ADR-016](../07-decisions/ADR-016-premium-experience-all-plans.md), [ADR-018](../07-decisions/ADR-018-command-center-decision-focus.md), [ADR-021](../07-decisions/ADR-021-subscription-tiers-based-on-execution-authority.md), [ADR-022](../07-decisions/ADR-022-ai-first-market-research-workspace.md), [ADR-023](../07-decisions/ADR-023-persistent-authenticated-navigation-and-naming-standard.md)  
Related Releases: None

## Purpose

The Command Center answers: "What should I know and do today?"

It is the authenticated home workspace and daily operating view. It is not named Dashboard in current product documentation.

Market Intelligence answers: "What is happening across the markets right now?" The Command Center may surface selected intelligence from Market Intelligence, but Market Intelligence is the deeper research workspace.

## Sections

- Morning Brief (hero briefing experience within Command Center).
- Since Your Last Visit.
- Capital Intelligence.
- Yesterday's Debrief.
- Decision Quality.
- Today's Opportunities.
- AI Focus List.
- Trade Management or Signal Center depending on plan.
- Intelligence Feed.
- Activity Timeline.
- Daily Scorecard.
- Learning & Coaching.
- AI Partnership status.

The intended daily sequence is Morning Brief, Today's Opportunities, Capital Intelligence, Yesterday's Debrief, Decision Quality, and Daily Scorecard / Coaching. Morning Brief may expand into a deeper briefing experience without becoming a separate flagship workspace. The former standalone Morning Intelligence concept is superseded by this embedded model.

## Application Shell

Command Center uses the persistent authenticated shell: the shared left sidebar, consistent top utility bar, and workspace-specific content area. Its primary-navigation peers are Market Intelligence, Trade Intelligence, and Performance Intelligence. AI Partnership / Authority remains visible in the consistent product-level status location defined by the shell standard.

## Product Rules

Win Rate is not a primary Command Center tile. It belongs in historical performance and debrief views.

Account balance is available, but not visually dominant.

Every subscription tier receives the same premium visual quality and the same core StructureIQ intelligence. Plans change execution authority, not Command Center quality.

Explorer presents execution-related workspace behavior as Signal Center / Manual Trading. Professional presents approval-required Trade Management actions. Elite may present autonomous Trade Management when Autopilot is enabled.

StructureIQ remains one recognizable interface whose behavior adapts to Subscription Tier and current AI Authority Level. It should not become three visually different applications.
