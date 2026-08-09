# Market Intelligence Workspace v1.0

ID: KB-PROD-0006  
Title: Market Intelligence Workspace v1.0  
Category: Product  
Status: APPROVED  
Owner: Founder  
Created: 2026-08-09  
Last Updated: 2026-08-09  
Version: 1.0  
Design Status: Approved  
Related Entries: [Product Vision](KB-PROD-0001-product-vision.md), [Command Center](KB-PROD-0003-command-center.md), [AI Partnership Model](KB-PROD-0005-ai-partnership-model.md)  
Related ADRs: [ADR-003](../07-decisions/ADR-003-explainable-ai.md), [ADR-022](../07-decisions/ADR-022-ai-first-market-research-workspace.md)  
Related Releases: None

## Product Mission

Market Intelligence transforms market data, structure, sessions, volatility, news context, and AI analysis into a clear, explainable understanding of current market conditions so traders know where to focus their attention before considering a trade.

Market Intelligence is an **AI-first market research workspace**. It is not primarily an execution screen, and it must not be framed as a buy/sell signals page.

Its job is:

- Research.
- Explanation.
- Prioritization.
- Market understanding.
- Attention management.
- Context.

## Core User Question

Market Intelligence answers: **"What is actually happening across the markets right now?"**

This is distinct from future Trade Intelligence, which will answer: **"What should I do?"**

## Governing Design Principle

StructureIQ begins with intelligence and uses charts as supporting evidence. It does not begin with charts and force users to derive the intelligence themselves.

This workspace reinforces StructureIQ's identity as an AI Trading Intelligence platform rather than a charting-first platform or signal service.

## Information Hierarchy

Market Intelligence begins with synthesized market context, then narrows toward selected-market analysis and supporting evidence.

1. Broad AI market brief.
2. Market-level sentiment and health.
3. Ranked attention priorities.
4. Selected-market chart evidence.
5. Selected-market AI explanation.
6. Session, driver, calendar, and volatility context.
7. Observation timeline showing meaningful StructureIQ observations.

## Approved Desktop Layout

### 1. AI Market Brief

The AI Market Brief is the first major content area. It provides an AI-generated summary of the current market environment before the user begins deeper analysis.

The brief may summarize global risk sentiment, major directional themes, notable market changes, volatility, scheduled events, markets currently meeting preferred conditions, and important warnings. It should feel like an institutional morning or intraday briefing.

The brief is intentionally placed before the primary chart.

### 2. Market Sentiment

Market Sentiment provides a compact visual summary of the broader market environment.

It may include bullish, bearish, or neutral orientation; a numeric sentiment score; comparison with a prior period; and broad market trend context. This is market-level context, not trade-entry confidence.

### 3. Market Health Dashboard

The Market Health Dashboard provides an at-a-glance comparison across tracked markets.

Approved conceptual fields include:

- Market.
- Trend.
- Quality.
- Volatility.
- Opportunity.

Example opportunity states include Excellent, Good, Watch, Wait, and Avoid.

The purpose is to reduce information overload and quickly show where market conditions appear strongest.

### 4. Opportunity Radar

Opportunity Radar ranks markets by research priority. It ranks markets, not individual executable trades.

It helps answer: **"Where should I spend my attention?"**

Possible inputs include market structure, trend, liquidity, volatility, confidence, regime, session conditions, execution conditions, and event risk. It must not be documented or designed as an execution queue.

### 5. Chart Analysis

The primary interactive chart is supporting evidence for the intelligence layer.

The chart may eventually support overlays such as structure, swing points, trend, support/resistance, liquidity zones, regime, session ranges, news markers, confidence, AI annotations, VWAP, or other approved contextual tools.

Charts support intelligence; they do not define the workspace.

### 6. AI Analysis Panel

The AI Analysis Panel is a signature Market Intelligence element.

For the selected market, StructureIQ should explain topics such as:

- Structure.
- Price Action.
- Momentum.
- Context.
- Key Levels.
- Outlook.

The language should be explanatory and educational. The panel should not merely say "BUY EUR/USD." It should explain what structure is doing, why buyers or sellers appear in control, what conditions are changing, what risks exist, and what the trader should monitor next.

### 7. Session Intelligence

Session Intelligence is especially important for Forex and other session-sensitive markets.

It may include current session, upcoming session, session strength, liquidity conditions, overlaps, time until the next major session, and whether the selected market is currently in an active or quiet period.

Known examples include Asia, London, New York, and the London/New York overlap. The existing Market Session Engine should eventually provide authoritative session information, but this product entry does not claim that every frontend integration already exists.

### 8. Market Drivers

Market Drivers summarize the most important forces influencing markets.

Possible categories include USD, rates, oil, crypto, equity indices, commodities, and macroeconomic themes. The goal is concise context rather than an unfiltered news feed.

### 9. Economic Calendar

The Economic Calendar provides upcoming economic events relevant to monitored markets.

Potential fields include time, event, impact, actual, and forecast. This is contextual research information. This entry does not claim that all calendar integrations currently exist in production.

### 10. Volatility Overview

Volatility Overview provides relative volatility context across monitored assets.

It may show low, medium, or high volatility; volatility scores; and broader volatility indicators where appropriate. The purpose is to help users understand current market conditions and execution risk.

### 11. AI Observation Timeline

The AI Observation Timeline is a signature Market Intelligence component.

It shows a chronological stream of meaningful observations made by StructureIQ, such as structure break confirmed, retest failed, volatility increased, session opened, directional strength changed, event risk increased, or confidence declined.

It should feel like an analyst continuously watching the market. It should not display every low-value internal event; only meaningful user-facing observations should eventually appear.

## Approved Navigation Context

Market Intelligence is a major authenticated workspace alongside:

- Command Center.
- Trade Intelligence.
- Portfolio Intelligence.
- Research / AI Reports.
- Economic Calendar.
- News Intelligence.
- Strategy Lab.

Market Intelligence itself is approved. Future workspace designs should not be marked as fully approved unless separately approved.

## Mobile Experience

Mobile Market Intelligence should behave more like a briefing application than a compressed desktop dashboard.

Priority mobile cards should include:

- AI Market Brief.
- Top Markets / Opportunity Radar.
- Selected Market AI Analysis.
- Session Status.
- Watchlist.
- Alerts.
- Key Market Drivers.

Charts may remain available, but they should not dominate the first mobile view.

## AI Behavior

Market Intelligence AI may summarize market conditions, explain structure, identify important changes, prioritize markets, summarize major drivers, and create meaningful observation events.

Explanations should be user-facing reasoning, not raw source code, confidential internals, or sensitive proprietary logic. The AI should explain what it sees and why it matters without exposing implementation details merely because a user asks for an explanation.

## Relationship to Command Center

Command Center answers: **"What should I know and do today?"**

Market Intelligence answers: **"What is happening across the markets right now?"**

The Command Center may surface selected intelligence from Market Intelligence, but Market Intelligence is the deeper research workspace.

## Relationship to Trade Intelligence

Trade Intelligence is a separate future workspace.

Market Intelligence is market-centric. Trade Intelligence will be opportunity/trade-centric. Market Intelligence should not become overloaded with trade execution controls.

## Future Enhancements

The following concepts are **FUTURE / NOT YET APPROVED FOR IMPLEMENTATION** unless separately approved:

- **Market Story:** a continuously updated AI-generated narrative of the day's broader market story.
- **Research Confidence Map:** ranking markets based on confidence in the quality of current market research/context. This is not necessarily trade confidence.
- **"Why Not?" Explanation:** when StructureIQ ranks a market poorly, it should eventually explain why, such as weak structure, low volatility, poor alignment, event risk, execution conditions, or low confidence.

## Design Approval Record

Page: Market Intelligence Workspace  
Version: 1.0  
Status: APPROVED  
Approved By: Founder  
Approval Notes: High-fidelity Market Intelligence v1.0 concept approved without requested revisions.  
Design Philosophy: AI-first market research. Charts support intelligence.

## Implementation Boundary

This entry is an approved product design specification. It does not claim that a frontend Market Intelligence workspace, economic calendar API, news API, chart integration, live Market Drivers integration, or AI Observation Timeline has already been implemented.

Implemented engine capabilities should be documented separately in engineering, release, and API entries.
