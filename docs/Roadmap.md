# StructureIQ Roadmap

## Product Direction

StructureIQ is moving from a raw analysis API toward a trader-facing decision-support platform. Development proceeds in two layers:

1. Build deterministic internal engines that produce traceable structure, evidence, decisions, and setup qualifications.
2. Translate those results into plain-English guidance and disciplined trade plans without adding autonomous execution.

Every version must preserve automated tests, stable contracts, explainability, and the separation between analysis and live trading.

## Version 0.1 — Foundation

- FastAPI.
- Tests.
- GitHub/Codespaces.
- Market data provider abstraction.

**Status:** implemented.

**Outcome:** a repeatable service with validated health and analysis contracts, normalized provider data, dependency injection, and automated tests.

## Version 0.2 — Market Structure Engine

- Confirmed swing highs and lows.
- HH/HL/LH/LL.
- BOS and CHOCH.
- Liquidity sweeps.
- Trend and phase classification.

**Status:** implemented.

**Outcome:** typed, explainable, and tested price-action structure independent of providers and presentation.

## Version 0.3 — Multi-Timeframe Analysis

- Higher-timeframe directional context.
- Current-timeframe execution context.
- Alignment categories and `0–100` scoring.
- Unified directional bias and reasons.

**Status:** implemented for the two timeframes already present in `/analysis`.

**Outcome:** explicit agreement, mixed context, conflict, and uncertainty without prematurely expanding into a full timeframe hierarchy.

## Version 0.4 — Decision Engine

- Weighted scoring.
- Buy, sell, wait, and avoid decisions.
- Confidence calculation.
- Positive, negative, and neutral evidence.
- Risk and invalidation notes.

**Status:** implemented.

**Outcome:** one reproducible decision source using the blueprint's `35/25/15/15/10` evidence model, with backward-compatible API mapping.

## Version 0.5 — Setup Engine

- Bullish BOS retest.
- Bearish BOS retest.
- Pullback continuation.
- Range reversal.
- Liquidity sweep reversal.
- Compression breakout.
- Setup qualification, missing conditions, entry checklist, and invalidation.

**Status:** planned.

**Exit criteria:** each setup has deterministic prerequisites, confirmation, entry conditions, invalidation, and rejection reasons. A decision can exist without a qualified setup.

## Version 0.6 — Analysis/Explanation Engine

- Plain-English market summary.
- Recommended qualified setup.
- Entry conditions and invalidation.
- Risk notes.
- Wait and avoid explanations.
- Checklist-style trade plan.
- Trader-facing analysis API contract.

**Status:** planned.

**Exit criteria:** trader-facing output is concise, traceable to internal results, and incapable of inventing or changing decisions and setup qualifications.

## Version 0.7 — Strategy Engine

- Broader playbook selection.
- Comparison of valid continuation, reversal, range, and breakout approaches.
- Ranking among qualified setup candidates.
- Market-regime-aware strategy recommendations.

**Status:** planned.

**Exit criteria:** the engine evaluates playbooks only after setup qualification and cannot override risk, decision, or invalidation gates.

## Version 0.8 — Journal and Backtesting

- Analysis and decision snapshots.
- Setup and plan journaling.
- Outcome and review tracking.
- Historical strategy evaluation.
- Look-ahead, fees, slippage, and data-quality controls.

**Status:** planned.

**Exit criteria:** users can review decision quality and test deterministic rules across historical regimes with explicit assumptions.

## Version 1.0 — StructureIQ Platform

- Cohesive trader-facing decision-support experience.
- Stable internal and trader-facing API contracts.
- Explainable analysis and checklist plans.
- Qualified setups and strategy playbooks.
- Journal and backtesting workflows.
- Dashboard-ready architecture without coupling domain engines to a UI.

**Status:** planned.

**Exit criteria:** StructureIQ consistently turns market data into traceable internal intelligence and a disciplined trader-facing plan while remaining a decision-support platform, not a live trading bot.

## Beyond Version 1.0

Future work may improve data coverage, alerting, portfolio context, personalization, and research workflows. Any execution integration would require a separate architecture, explicit authorization, and independent safety controls; it is not implied by this roadmap.
