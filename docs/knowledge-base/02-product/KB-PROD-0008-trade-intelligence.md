# Trade Intelligence Workspace v1.0

ID: KB-PROD-0008  
Title: Trade Intelligence Workspace v1.0  
Category: Product  
Status: APPROVED  
Version: 1.0  
Design Status: Approved  
Owner: Founder  
Created: 2026-08-09  
Last Updated: 2026-08-09  
Related Entries: [Navigation & Application Shell Design System](KB-PROD-0007-navigation-application-shell-design-system.md), [Market Intelligence](KB-PROD-0006-market-intelligence-workspace.md), [Performance Intelligence](KB-PROD-0009-performance-intelligence.md), [AI Trade Lifecycle](../04-ai/KB-AI-0002-trade-lifecycle.md)  
Related ADRs: [ADR-019](../07-decisions/ADR-019-full-trade-lifecycle.md), [ADR-023](../07-decisions/ADR-023-persistent-authenticated-navigation-and-naming-standard.md), [ADR-024](../07-decisions/ADR-024-ai-selected-default-opportunity-with-user-override.md)  
Related Releases: None

## Mission

Trade Intelligence answers: **“What should I do next?”**

Its mission is to transform StructureIQ market research into disciplined, explainable trading opportunities while guiding the user through the full trade lifecycle from validation through execution, management, exit, review, and learning.

It is the primary decision and trade-workflow workspace—not merely a signal list, order ticket, or chart page.

## Application Shell

Trade Intelligence uses the standardized persistent authenticated shell: shared left sidebar, consistent top utility bar, and workspace-specific content. Primary navigation remains Command Center, Market Intelligence, Trade Intelligence, and Performance Intelligence. Market Explorer stays inside Trade Intelligence and never replaces global navigation. AI Authority retains the consistent product-level placement defined by the shell standard.

## Approved Workspace Structure

### AI Trade Brief

The trade-specific AI Trade Brief summarizes the current actionable opportunity environment. It may include the number of opportunities meeting StructureIQ quality thresholds, the highest-priority market, opportunities requiring confirmation, markets being avoided, and notable execution conditions. It is distinct from the broader Market Intelligence Market Brief.

### AI Focus — Recommended

AI Focus is the default operating mode. It reduces information overload by ranking the highest-priority actionable or developing opportunities using validated StructureIQ inputs such as structure, setup quality, confidence, regime, session, risk, execution conditions, and confirmation. It does not define or replace an undocumented production ranking algorithm.

Opportunity states may include Ready, Validation, Watch, and Avoid. Illustrative rankings include BTC/USD — AI Top Pick, EUR/USD — #2 Ranked, and NAS100 — #3 Ranked.

### Market Explorer — Browse All Markets

Market Explorer is the user-driven mode for browsing supported Forex, Crypto, Indices, Stocks, and Commodities beyond AI Focus. It preserves user control and remains an internal Trade Intelligence control.

### AI Top Pick and Selection Ownership

On initial load, StructureIQ automatically selects the highest-ranked current AI Focus opportunity and loads it into the Opportunity Workspace with an AI Top Pick or equivalent badge. **AI selects the initial highest-ranked opportunity. The user may override the active selection at any time.**

The user may choose another AI Focus opportunity, select another supported market through Market Explorer, or request exploratory analysis for an unsupported market. Contextual badges such as AI Top Pick, #2 Ranked Opportunity, #3 Ranked Opportunity, Explorer Selection, or Exploratory Analysis explain why the active market is loaded.

### Opportunity Workspace

Opportunity Workspace is the authoritative name for the central active-market panel; the former Selected Opportunity term is superseded. When selection changes, the chart, trade plan, confidence, execution state, lifecycle, AI reasoning, alternative scenarios, observation timeline, and learning content update together where applicable.

A supported market outside AI Focus still loads supported analysis. If it has no actionable opportunity, the workspace shows an honest state such as Observation, Neutral, Low Quality, Wait, or No Current Setup and does not fabricate an executable trade.

## Market Universe

Market Universe supersedes Universe Summary in current Trade Intelligence documentation. It may summarize supported markets, active opportunities, markets under observation, neutral or low-quality/avoid states, validation state, and planned markets where appropriate.

The product distinguishes:

- **AI Focus Markets:** currently prioritized by StructureIQ.
- **Supported Markets:** validated markets available for normal analysis even when not prioritized.
- **Exploratory Markets:** markets outside the validated production universe that a user requests manually.

Unsupported markets display **Not Currently Supported** and may offer **Exploratory Analysis**. Exploratory analysis is clearly informational/experimental and is not eligible for production recommendation status, validated signal claims, automated execution, or Autopilot until the market passes StructureIQ validation. This is an approved design concept; this entry does not claim the backend capability exists.

## Trade Plan

The Trade Plan may show Setup, Entry Zone, Stop Loss, Target 1, Target 2, Risk / Reward, User Risk, Position Size, Confidence, Estimated Hold Time, and Session. Production values must come from authoritative backend intelligence. The frontend must not invent or independently calculate production risk levels.

## Explainability and Confidence

### Why This Trade?

Shows supporting evidence such as structure alignment, confirmed pullback, momentum, favorable liquidity, session quality, and lack of major event risk.

### Why Not This Trade?

Shows counter-evidence and risks such as nearby resistance, elevated volatility, event risk, invalidation risk, market extension, and weaker execution conditions. StructureIQ must present both evidence and counter-evidence.

### AI Confidence Breakdown

Confidence should be explainable rather than a single unexplained percentage. The design may break down Structure, Momentum, Risk, Volatility, News, and Execution alongside Overall Confidence. Factors unavailable from production must not be presented as implemented or authoritative.

## Execution Panel by Subscription Tier

- **Explorer:** manual execution only; may receive the Trade Plan, guidance, manual status, and Mark as Entered/tracking workflows. StructureIQ cannot submit broker orders.
- **Professional:** approval-required AI-assisted execution; StructureIQ may prepare a trade, but **Approve Trade** or equivalent explicit approval is required before broker submission.
- **Elite:** the user may select Manual, Approval / Co-Pilot, or optional Autopilot. Autopilot is never forced.

Every execution path remains subject to risk, authorization, broker, exposure, and kill-switch safeguards. All tiers retain the same premium shell and intelligence quality.

## Trade Lifecycle

The signature lifecycle is Research → Validation → Entry → Management → Exit → Review → Learning. The UI identifies the current stage, such as **Current Stage: Awaiting Entry**, reinforcing that trading is a process rather than a single Buy or Sell action.

## Alternative Scenarios

Trade Intelligence documents contingency paths: bullish continuation if resistance breaks, bearish/invalidation behavior if structural support fails, and standing aside when major news changes conditions. Scenarios make invalidation and changed conditions explicit.

## AI Observation Timeline

The active opportunity has a trade-specific timeline for meaningful events such as pullback completion, support defense, volume increase, improved confirmation, nearly satisfied entry conditions, or changed session liquidity. This differs from the broader Market Intelligence observation timeline.

## Learning Panel

Every trade should contribute to education. Learning content may explain why StructureIQ waited, why a setup was invalidated, why confirmation mattered, why an exit occurred, or what the user should learn. The loop is Decision → Outcome → Review → Learning.

## Workspace Relationships

Market Intelligence is market-centric and answers **“What is happening across the markets right now?”** Trade Intelligence is opportunity-centric and converts relevant market intelligence into a specific opportunity and trade workflow. They remain separate workspaces.

After completion, Trade Intelligence flows conceptually into the approved Performance Intelligence workspace for review of outcomes, decision quality, discipline, execution quality, risk, and long-term improvement. Product approval does not claim that this data integration is implemented.

## Mobile Philosophy

Mobile Trade Intelligence prioritizes AI Top Pick, Priority Opportunities, opportunity status, Trade Plan, approval/manual execution control, Trade Lifecycle, alerts, and critical AI updates. It uses a mobile-native hierarchy rather than shrinking the desktop grid.

## AI Disclosure Boundary

AI ranks opportunities, chooses the initial Top Pick, explains supporting and counter-evidence, monitors lifecycle context, and guides without removing user control. Explanations are user-facing reasoning and must not reveal confidential source code, proprietary prompts, system instructions, security architecture, or sensitive model internals.

## Design Approval Record

Page: Trade Intelligence Workspace  
Version: 1.0  
Status: APPROVED  
Approved By: Founder  
Approval Notes: Approved after navigation normalization and opportunity-selection clarification.  
Final Design: Persistent left sidebar; AI Trade Brief; AI Focus; Market Explorer; AI Top Pick; Opportunity Workspace; Market Universe; Trade Plan; explainable confidence; execution panel; Trade Lifecycle; Alternative Scenarios; AI Observation Timeline; learning content; unsupported-market exploratory pathway.

## Implementation Boundary

This is the official product design baseline. It does not claim that the Trade Intelligence frontend, opportunity synchronization, exploratory-analysis backend, broker execution controls, live observation timeline, or every confidence input has been implemented. Implementation status belongs in engineering and release documentation.
