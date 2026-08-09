# Performance Intelligence Workspace v1.0

ID: KB-PROD-0009  
Title: Performance Intelligence Workspace v1.0  
Category: Product  
Status: APPROVED  
Version: 1.0  
Design Status: Approved  
Owner: Founder  
Created: 2026-08-09  
Last Updated: 2026-08-09  
Related Entries: [Navigation & Application Shell Design System](KB-PROD-0007-navigation-application-shell-design-system.md), [Product Vision](KB-PROD-0001-product-vision.md), [Trade Intelligence](KB-PROD-0008-trade-intelligence.md), [AI Principles](../04-ai/KB-AI-0001-ai-principles.md)  
Related ADRs: [ADR-018](../07-decisions/ADR-018-command-center-decision-focus.md), [ADR-021](../07-decisions/ADR-021-subscription-tiers-based-on-execution-authority.md), [ADR-023](../07-decisions/ADR-023-persistent-authenticated-navigation-and-naming-standard.md), [ADR-025](../07-decisions/ADR-025-decision-quality-over-outcome-only-performance-evaluation.md)  
Related Releases: None

## Mission

Performance Intelligence answers: **“How am I performing and improving as a trader?”**

Its mission is to turn trading history into actionable intelligence about performance, decision quality, discipline, risk, strengths, weaknesses, repeatability, and improvement. It is not merely a brokerage statement, P&L page, win-rate dashboard, or collection of vanity metrics. Its purpose is to help users understand whether their trading process is improving and why.

**Performance Intelligence is the continuous improvement engine of StructureIQ.** It connects Trading Behavior → Outcomes → Review → Coaching → Improvement.

## Governing Product Philosophy

**Performance Intelligence evaluates both outcomes and decision quality.** It distinguishes a good decision that lost money, a bad decision that made money, a disciplined skip, an execution mistake, a correct override, and a harmful override. Profitability alone does not prove decision quality.

## Application Shell

Performance Intelligence uses the approved persistent authenticated shell and is the fourth flagship destination after Command Center, Market Intelligence, and Trade Intelligence. The shared left sidebar, top utility bar, AI Authority placement, and premium visual quality remain consistent.

## Approved Workspace Structure

### AI Performance Brief

The hero brief summarizes recent performance before raw metrics. It may explain improvement or regression in decision quality, risk adherence, discipline trends, strengths, major performance drivers, missed opportunities, exit-management issues, and the most important coaching focus. Rather than reporting only “+4.2R,” it explains why results changed, which behaviors helped or hurt, and what should improve next.

### Decision Quality

Decision Quality is the primary behavioral KPI and is more prominent than P&L. Potential dimensions include Setup Selection, Entry Discipline, Risk Discipline, Management Quality, Exit Quality, Rule Adherence, Patience, and Research Completion.

This is an **Approved Product Design / Metric Framework** until exact validated engine logic is finalized. This entry does not define a production scoring formula. A losing trade may receive a high Decision Quality evaluation when it followed a valid plan with disciplined reasoning.

### Performance Summary

The compact traditional-performance section retains the approved name **Performance Summary**. Potential metrics include Net Return, Total R, Profit Factor, Expectancy, Win Rate, Average Winner, Average Loser, Total Trades, Maximum Drawdown, and Recovery Factor across Today, 7D, 30D, 90D, YTD, and All ranges. These metrics support the page but do not define it.

### Equity Curve

The Equity Curve shows account and performance development over time. Potential overlays include Balance, Equity, Drawdown, and Decision Quality. An overlay must not be presented as implemented unless authoritative technical documentation supports it.

### Performance Attribution

Performance Attribution answers: **“Where is my edge actually coming from?”** It may eventually analyze results by Market, Setup, Session, Strategy, Confidence, Timeframe, Direction, and AI Authority Mode to identify strong and weak markets, sessions, setups, strategies, or differences between manual and AI-assisted periods. This design does not invent a production attribution algorithm.

### Discipline Intelligence

Discipline Intelligence evaluates behavior rather than profitability. Potential dimensions include Patience, Risk Discipline, Rule Adherence, Entry Discipline, Exit Quality, Overtrading Risk, Manual Overrides, and Early Entries. High Risk Discipline means rules were followed; Low Overtrading Risk means behavior does not currently indicate excessive trading. Behavioral classifications remain product-design concepts until validated engine support is documented.

### Strengths

The Strengths panel reinforces repeatable positive behaviors such as patience, risk-plan adherence, regime-specific performance, research completion, setup selection, and disciplined entries.

### Needs Improvement

Needs Improvement identifies specific weaknesses such as closing winners early, unnecessary overrides, weak market performance, premature entries, poor session selection, or inconsistent exit management. Its tone is analytical and constructive, never punitive.

### Missed Opportunity Intelligence

Missed Opportunity Intelligence avoids hindsight bias by evaluating information available when the decision occurred.

- **Correct Skip:** the market later moved favorably, but required rules or confirmation were absent at decision time; this is not a mistake.
- **Execution Miss:** the opportunity satisfied the approved plan, but the user declined or failed to execute; this may warrant review.

### AI Coach

AI Coach identifies the current behavioral priority, why it matters, evidence from recent trades, and a clear next action—for example, **“Let winners reach your targets.”** It may link to Journal & Coaching without creating a duplicate coaching system. The approved design may retain both AI Coach and AI Coaching Focus cards; future consolidation requires a later design revision.

### Performance Milestones

Milestones may recognize trades completed within risk plans, consecutive disciplined sessions, positive R milestones, rule-following streaks, and review completion. They reward process consistency and must avoid gambling-like or excessive-risk encouragement.

### Weekly Goal Progress

Weekly process goals may include Morning Brief reviewed, research completed, trades reviewed, journal entries completed, and coaching session completed. They support sustainable habits and engagement.

### StructureIQ Edge Score

Status: **CONCEPT / FUTURE**

Edge Score may eventually estimate how repeatable and structurally healthy a trader's current edge appears using potential inputs such as expectancy, Decision Quality, drawdown, consistency, rule adherence, sample size, strategy stability, and risk behavior. No formula is approved, and the score must not be described as production-ready or statistically validated until research confirms it. The design may display a visible Concept / Coming Soon state.

### Quick Insights

Quick Insights provides compact pattern recognition such as best day, most challenging day, best market, weakest market, and current focus area.

### Bottom Action Layer

- **Understand Your Edge:** opens deeper attribution.
- **Review Your Trades:** leads to historical review or replay.
- **Improve Consistency:** leads toward coaching or Journal & Coaching.

## Subscription and AI Authority Context

All tiers receive the same core Performance Intelligence quality and premium shell.

- **Explorer:** focuses on manually executed decisions and trading behavior.
- **Professional:** may compare approvals, rejections, assisted execution, and AI recommendations.
- **Elite:** may compare Autopilot activity, manual overrides, Co-Pilot periods, autonomous periods, and user intervention.

Observer, Advisor, Co-Pilot, and Autopilot remain the authority levels. Performance may eventually attribute results by authority mode, but this entry does not claim those data integrations exist.

## Flagship Decision Loop

- Command Center: “What should I know and do today?”
- Market Intelligence: “What is happening across the markets right now?”
- Trade Intelligence: “What should I do next?”
- Performance Intelligence: “How am I performing and improving?”

Together they form the complete flagship daily decision and improvement loop.

## Mobile Philosophy

Mobile prioritizes AI Performance Brief, Decision Quality, Performance Summary, Discipline Intelligence, Strengths / Needs Improvement, AI Coach, key alerts, and milestones. Charts and attribution may become drill-down views rather than dominate the initial experience. The desktop grid must not simply be shrunk.

## AI Disclosure Boundary

AI may summarize performance, identify strengths and weaknesses, distinguish correct skips from execution misses, evaluate discipline patterns, recommend coaching priorities, explain attribution, and compare periods. User-facing explanation is required, while private system prompts, proprietary logic, source code, security architecture, hidden instructions, and sensitive internals remain undisclosed.

## Design Approval Record

Page: Performance Intelligence Workspace  
Version: 1.0  
Status: APPROVED  
Approved By: Founder  
Approval Notes: High-fidelity Performance Intelligence v1.0 concept approved without requested revision.  
Approved Design: AI Performance Brief; Decision Quality; Performance Summary; Equity Curve; Performance Attribution; Discipline Intelligence; Strengths; Needs Improvement; Missed Opportunity Intelligence; AI Coach; Performance Milestones; Weekly Goal Progress; StructureIQ Edge Score as Concept; Quick Insights; bottom improvement actions.

## Implementation Boundary

This is the official product design baseline. It does not claim that the Performance Intelligence frontend, Decision Quality engine, behavioral classifications, attribution analysis, AI Coach integrations, Equity Curve overlays, Edge Score, or authority-mode comparisons have been implemented. Implementation status belongs in engineering and release documentation.
