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

**Status:** implemented.

**Outcome:** each supported setup has deterministic candidate selection, checklist conditions, confirmation status, risk threshold, invalidation, warning notes, and explicit no-setup behavior. A decision can exist without a confirmed setup.

## Version 0.6 — Analysis/Explanation Engine

- Plain-English market summary.
- Recommended qualified setup.
- Entry conditions and invalidation.
- Risk notes.
- Wait and avoid explanations.
- Checklist-style trade plan.
- Trader-facing analysis API contract.

**Status:** implemented.

**Outcome:** `/analysis` now includes a typed trader-facing narrative, recommendation, confidence interpretation, key risks, next action, and checklist plan that remain traceable to internal outputs and cannot alter decisions or setup qualifications.

## Version 0.7 — Strategy Engine

- Broader playbook selection.
- Comparison of valid continuation, reversal, range, and breakout approaches.
- Ranking among qualified setup candidates.
- Market-regime-aware strategy recommendations.

**Status:** implemented.

**Outcome:** all six playbook families are scored and ranked against structure, timeframe, setup, risk, and existing indicator evidence. Selection occurs after setup qualification and cannot override decision, setup, risk, or invalidation gates.

## Version 0.8 — Journal and Backtesting

- Analysis and decision snapshots.
- Setup and plan journaling.
- Outcome and review tracking.
- Historical strategy evaluation.
- Look-ahead, fees, slippage, and data-quality controls.

**Status:** implemented.

**Outcome:** users can persist analysis snapshots in a filterable local journal and replay the current analysis pipeline over historical candle windows with skipped-plan records, conservative stop/target simulation, R-based metrics, and explicit limitations.

## Version 0.9 — Validation and Calibration

- User-facing to provider-specific symbol normalization.
- Multi-symbol and multi-timeframe calibration runs.
- Aggregate backtest behavior.
- Setup and strategy performance groups.
- Conservative and aggressive behavior diagnostics.
- Severity-ranked recommendations for human inspection.
- No automatic parameter tuning.

**Status:** implemented.

**Outcome:** maintainers can measure how often the current engine acts or skips, inspect historical R-based behavior by setup and strategy, and identify rules worth reviewing without allowing calibration to modify production logic.

## Version 1.0 — StructureIQ Platform

- Cohesive trader-facing decision-support experience.
- Stable internal and trader-facing API contracts.
- Explainable analysis and checklist plans.
- Qualified setups and strategy playbooks.
- Journal and backtesting workflows.
- Dashboard-ready architecture without coupling domain engines to a UI.

**Status:** release candidate; Stable MVP prepared.

**Outcome:** StructureIQ consistently turns market data into traceable internal intelligence and a disciplined trader-facing plan. The complete API surface, repository guidance, release identity, automated contract coverage, journal, backtesting, and calibration foundations are documented and verified while the product remains decision-support software rather than a live trading bot.

**Release gate:** tag `v1.0.0` after the release candidate passes continuous integration and the owner approves the distribution license and deployment security posture.

## Version 1.1 — Actionability Diagnostics and Conservative-Gate Calibration

- Per-record skip reason, detail, blocking engine, and actionability status.
- Backtest skip aggregation by reason and engine.
- Cross-run calibration skip diagnostics.
- Gate-specific recommendations for human inspection.
- No automatic threshold or scoring changes.

**Status:** implemented.

**Outcome:** maintainers can identify whether Decision, Setup, Strategy, Explanation, risk context, or the backtester is the dominant actionability blocker before designing a controlled threshold experiment. Trade-selection behavior remains unchanged.

## Version 1.2 — Decision Engine Sensitivity Report

- Per-analysis raw score, final confidence, direction, confidence band, and gate results.
- Explicit failed required gates for wait and avoid decisions.
- Backtest confidence-band and blocked-gate aggregation.
- Cross-run calibration Decision Engine sensitivity reporting.
- Dominant-gate recommendations without automatic tuning.

**Status:** implemented.

**Outcome:** maintainers can distinguish a low confidence score from structure disagreement, timeframe misalignment, or risk/reward gating across historical windows. The report identifies the next controlled measurement to run while preserving every v1.1 decision and threshold.

## Version 1.3 — Risk/Reward Calibration and Decision Gate Refinement

- Separate directional confidence from execution readiness.
- Retain risk/reward as weighted decision evidence without using missing data as an early directional veto.
- Require complete entry, stop, target, and `1.5R` quality for setup confirmation.
- Revalidate levels and risk/reward before backtest simulation.
- Attribute calibration bottlenecks to the engine that owns the unresolved condition.

**Status:** implemented.

**Outcome:** strong directional evidence can progress without a premature risk-plan veto, while incomplete or low-quality execution plans remain non-actionable. Calibration can now distinguish Decision Engine conservatism from Setup and risk-plan incompleteness.

## Beyond Version 1.0

Future work may add score histograms, distance-to-threshold buckets, per-condition setup diagnostics, and controlled counterfactual sensitivity experiments before any gate changes. It may also improve data coverage, alerting, portfolio context, personalization, and research workflows. Any execution integration would require a separate architecture, explicit authorization, and independent safety controls; it is not implied by this roadmap.
