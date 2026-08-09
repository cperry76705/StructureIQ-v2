# Navigation & Application Shell Design System

ID: KB-PROD-0007  
Title: Navigation & Application Shell Design System  
Category: Product / Design System  
Status: APPROVED  
Version: 1.0  
Owner: Founder  
Created: 2026-08-09  
Last Updated: 2026-08-09  
Related Entries: [Command Center](KB-PROD-0003-command-center.md), [Market Intelligence](KB-PROD-0006-market-intelligence-workspace.md), [Trade Intelligence](KB-PROD-0008-trade-intelligence.md), [Performance Intelligence](KB-PROD-0009-performance-intelligence.md)  
Related ADRs: [ADR-016](../07-decisions/ADR-016-premium-experience-all-plans.md), [ADR-017](../07-decisions/ADR-017-ai-authority-model.md), [ADR-021](../07-decisions/ADR-021-subscription-tiers-based-on-execution-authority.md), [ADR-023](../07-decisions/ADR-023-persistent-authenticated-navigation-and-naming-standard.md)  
Related Releases: None

## Purpose

This is the authoritative StructureIQ Navigation & Design System v1.0 standard. Every authenticated workspace must feel like part of one institutional-grade application: a persistent left sidebar, a consistent top utility bar, and a workspace-specific main content area. Workspace sub-navigation may organize local content but must not replace the global shell.

## Navigation Hierarchy

Primary flagship navigation, in order:

1. Command Center
2. Market Intelligence
3. Trade Intelligence
4. Performance Intelligence

Secondary navigation, below the flagship group:

- Watchlists
- Strategy Lab
- Economic Calendar
- News Intelligence
- AI Reports
- Journal & Coaching

The lower sidebar contains Notifications, Broker Connections, Settings, and System Status. User profile, plan summary, and AI Partnership / Authority may appear there or in the top utility area, but placement must remain consistent.

## Authenticated Shell

### Left Sidebar

The desktop sidebar is persistent across flagship workspaces and contains the StructureIQ logo, primary, secondary, and account/system navigation, plus AI Partnership / Authority and user/plan summary where appropriate. It must not radically change between workspaces. Primary items have a clear selected state using more than color alone; secondary and account groups are visually subordinate but discoverable.

### Top Utility Bar

The shared utility bar may contain global search, market/session status, notifications, user profile, current time/timezone, and contextual workspace controls. Shared elements keep stable ordering and placement. Contextual controls must be distinguishable from global controls, and unrelated controls must not be duplicated inconsistently.

### Main Content and Workspace Header

Each flagship workspace uses a consistent header: page title, short mission descriptor, and optional contextual status or mode. Working examples are:

- Command Center — “Your daily operating view.”
- Market Intelligence — “Understand the market. Find your edge.”
- Trade Intelligence — “Actionable opportunities. Disciplined execution.”
- Performance Intelligence — “Understand your results. Improve your decisions.”

These descriptors are guidance, not immutable marketing copy. The shared utility bar remains above or aligned consistently with the workspace header.

## Naming Standard

Use “Intelligence” where it defines the primary Market Intelligence, Trade Intelligence, and Performance Intelligence workspaces. Command Center is the daily operating-workspace exception. Do not use Dashboard, Markets, Trades, or Performance as current aliases for flagship destinations.

Supporting features should use concise names such as Morning Brief, AI Focus, Opportunity Radar, Trade Brief, Intelligence Feed, and AI Reports. AI capability alone does not justify adding “Intelligence” to every feature.

Morning Brief is a major hero and briefing experience inside Command Center. It may expand into deeper briefing content but is not a standalone primary workspace. “Morning Intelligence” is retained only when explicitly documenting superseded historical design evolution.

## Page Hierarchy and Product Narrative

The core journey is Landing Page → Authentication / Onboarding → Command Center → Market Intelligence → Trade Intelligence → Performance Intelligence.

- Landing Page: public marketing and conversion.
- Command Center: “What should I know and do today?”
- Market Intelligence: “What is happening across the markets right now?”
- Trade Intelligence: “What should I do next?”
- Performance Intelligence: “How am I performing and improving?”

## Active and Interaction States

Only one primary destination is active at a time. Active state combines a semantic indicator, contrast, and `aria-current`-equivalent meaning rather than color alone. Hover, focus, disabled, notification, loading, error, and unavailable states must be distinct. Local tabs or filters indicate their own state without suggesting a global workspace change.

## Mobile and Responsive Philosophy

Mobile preserves the same names and hierarchy without merely shrinking the desktop sidebar. Use a compact top bar and a mobile-native structure, such as bottom primary navigation for the flagship destinations plus a slide-out or More menu for secondary and account destinations. Exact mechanics remain an implementation decision.

The shell moves intentionally between expanded desktop, compact desktop/tablet, and mobile-native states. Content reflows before controls become illegible. Critical actions and status remain reachable; secondary tools may progressively disclose. Navigation labels, active state, page title, and authority state retain meaning at every breakpoint.

## Subscription and AI Authority Consistency

Explorer uses manual execution, Professional uses approval-required AI-assisted execution, and Elite may enable optional autonomous execution. All tiers receive the same premium shell and core intelligence quality. Navigation and visual quality must not degrade by tier, and separate tier-specific shells are prohibited.

Authority progression remains Observer → Advisor → Co-Pilot → Autopilot. Authority is persistent product-level status, not a page feature. Place it consistently in the lower sidebar, account area, or shared top-level status control. Account mode and authority may change behavior and permissions, not global information architecture.

## Visual Standards

Use design tokens by semantic role; authoritative values should come from the implemented token source when established. Roles include primary brand blue, AI accent purple, success green, warning amber, critical red, neutral slate/gray, dark application background, elevated dark card surfaces, high-contrast white primary text, and muted secondary text. Green and red communicate meaningful status, outcome, risk, or validation—not decorative excitement. The visual character remains disciplined and institutional.

## Reusable Component Vocabulary

The conceptual system includes Workspace Header, Sidebar Navigation Item, Utility Search, KPI Card, Intelligence Card, Status Badge, Quality Grade, Confidence Meter, Data Table, Timeline, AI Explanation Panel, Opportunity Card, Chart Container, Execution Control, Alert / Warning, Empty State, and Unsupported Market State. Implementations should reuse shared behavior and tokens rather than create workspace-specific lookalikes.

## Accessibility

Navigation and controls must support keyboard operation, visible focus, semantic landmarks, meaningful accessible names, predictable tab order, adequate contrast, and non-color state cues. Icon-only controls require accessible labels. Motion respects reduced-motion preferences. Status changes need an appropriate announcement strategy, and touch targets remain usable on mobile.

## Governance

This entry governs current product documentation and future authenticated design work. Historical screenshots and documents may retain former terminology when clearly labeled superseded. Any change to flagship names, hierarchy, or the persistent-shell decision requires a future ADR.
