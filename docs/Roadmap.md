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

## Version 1.4 — Decision Threshold Sensitivity Study

- Compare directional eligibility at confidence thresholds 50, 55, 60, 65, and 70.
- Preserve production decisions and thresholds.
- Retain immutable setup, plan, level, risk/reward, and strategy snapshots.
- Separate directional eligibility, observed execution readiness, and their candidate intersection.
- Recommend confidence research only when lower thresholds produce executable candidates.

**Status:** implemented.

**Outcome:** calibration can show whether confidence is the binding constraint or merely the first visible gate. Lower-threshold records remain non-candidates when their original execution plans lack setup confirmation, levels, risk quality, or strategy alignment.

## Version 1.5 — Risk/Reward and Setup Level Diagnostics

- Validate bullish and bearish entry/stop/target geometry for every analysis window.
- Classify missing fields, invalid geometry, wide stops, close targets, and below-minimum R.
- Retain setup-level sources, swings, and nearest structural zones.
- Aggregate average, median, near-threshold, and passing R distributions.
- Recommend level calculation, support/resistance, stop, target, threshold-study, or confirmation-rule review.

**Status:** implemented.

**Outcome:** maintainers can identify why execution readiness fails and choose the correct controlled experiment without reducing the `1.5R` minimum or relaxing setup confirmation.

## Version 1.6 — Instrument-Aware Level Precision and Zone Width

- Infer forex, crypto, and default instrument metadata from symbols.
- Preserve five-decimal forex and two-decimal crypto price levels.
- Replace the fixed 25-point zone floor with tick-aware percentage/ATR scaling.
- Calculate estimated R from numeric geometry before formatting.
- Preserve execution, setup-confirmation, strategy, and `1.5R` rules.

**Status:** implemented.

**Outcome:** level geometry remains proportional across instruments with radically different price scales, allowing calibration to measure genuine setup quality instead of formatting and fixed-width artifacts.

## Version 1.7 — Trade Outcome Diagnostics

- Record first stop/target touch and same-candle ambiguity.
- Measure bars to outcome and MFE/MAE in R.
- Identify initial `+0.5R` directional follow-through before stops.
- Classify immediate stops, no follow-through, wrong direction, weak confirmation, adverse reversals, and possible stop/target placement issues.
- Aggregate executed-trade behavior without changing simulation or strategy rules.

**Status:** implemented.

**Outcome:** maintainers can inspect why qualified trades win or lose before considering any strategy, threshold, confirmation, stop, or target changes.

## Version 1.8 — Stop Management and Profit Protection Study

- Compare unchanged management with break-even rules at `1R` and `1.5R`.
- Approximate half-position partial profit at `1R` and `1.5R`.
- Study protective trailing floors after `1R` and `1.5R`.
- Preserve conservative same-candle ambiguity and production metrics.
- Rank results by R, profit factor, and drawdown without automatic adoption.

**Status:** implemented.

**Outcome:** maintainers can measure whether favorable excursion can be protected before changing production stops, targets, or trade-management behavior.

## Version 1.9 — Setup Expansion and Candidate Coverage Diagnostics

- Compare every plausible setup candidate beside the unchanged selected setup.
- Diagnose level, geometry, R:R, direction, location, and confirmation blockers.
- Count selected, executable, and missed executable candidates by family.
- Recommend one family for focused expansion based on calibration evidence.

**Status:** implemented.

**Outcome:** maintainers can distinguish absent opportunities from setup-family coverage and first-match selection gaps without changing production behavior.

## Version 2.0 — Bearish BOS Retest Expansion

- Compare bearish BOS retests fairly with competing short liquidity-sweep reversals.
- Require bearish structure, recent BOS, resistance retest, valid levels, confirmation, alignment, and at least `1.5R`.
- Explain selection and preserve executable losing candidates in coverage diagnostics.
- Report whether bearish BOS retests begin contributing production backtest trades.

**Status:** implemented.

**Outcome:** bearish BOS retests can become production-selected when continuation evidence is strongest, without relaxing confidence, confirmation, risk, strategy, or execution gates.

## Version 2.1 — Execution Realism Engine

- Add optional spread, slippage, commission, fill-delay, and partial-fill assumptions.
- Preserve perfect execution as the default baseline.
- Compare baseline expectancy with modeled expectancy in backtesting and calibration.
- Keep all production analysis, selection, threshold, and risk rules unchanged.

**Status:** implemented.

**Outcome:** historical results can quantify execution-cost sensitivity without implying broker connectivity or changing trade recommendations.

## Version 2.2 — Execution Sensitivity Laboratory

- Compare perfect, isolated-cost, delayed-fill, and combined execution scenarios.
- Freeze calibration candle inputs across every profile.
- Rank best, worst, and largest expectancy-drop profiles.
- Attribute degradation to spread, slippage, commission, fill model, or combined costs.
- Keep ordinary calibration and production trading logic unchanged.

**Status:** implemented.

**Outcome:** maintainers can identify which execution assumption dominates historical degradation before validating costs against venue-specific evidence.

## Version 2.3 — Entry Timing Laboratory

- Compare immediate, delayed, signal-close, pullback, momentum, retest, and conservative-limit entries.
- Preserve one identical valid candidate set across every timing profile.
- Recalculate R from adjusted entry with unchanged stop and target.
- Measure fill rate, delay, entry improvement, missed entries, and missed winning opportunities.
- Keep production entry behavior and calibration metrics unchanged.

**Status:** implemented.

**Outcome:** maintainers can distinguish directional edge from timing fragility and quantify the cost of waiting for a better entry before designing any production experiment.

## Version 2.4 — Market Regime Laboratory

- Classify every analysis into one deterministic market regime with confidence and reasons.
- Aggregate expectancy, drawdown, duration, MFE/MAE, and outcomes by regime.
- Cross-tab strategy and setup performance against all regimes.
- Identify sparse, weak, dominant, and high-drawdown regime relationships.
- Keep every production decision and execution rule unchanged.

**Status:** implemented.

**Outcome:** maintainers can study which setups and strategies historically fit specific market conditions without allowing those findings to alter production routing.

## Version 2.5 — Regime Validation Laboratory

- Measure classification balance and transition dominance.
- Measure regime persistence and short-duration label noise.
- Compare predicted regimes with deterministic 5/10/20-bar forward proxies.
- Analyze transition exits and directional/range/volatility outcomes.
- Recommend classifier areas for inspection without changing classifications or trades.

**Status:** implemented.

**Outcome:** maintainers can diagnose transition overuse and regime underclassification before considering any controlled classifier threshold experiment.

## Version 2.6 — Regime Classifier Tuning Laboratory

- Explain transition dominance using competing evidence scores and event recency.
- Report confidence distributions, classification margins, and forward stability.
- Simulate transition thresholds from 60 through 80 without changing production rules.
- Isolate stronger BOS, CHOCH, swing-structure, and higher-timeframe alignment evidence.
- Preserve all production regime labels, analysis behavior, and trade execution.

**Status:** implemented.

**Outcome:** maintainers can distinguish stale transition precedence, evidence conflict, and insufficient trend weighting, then choose a controlled future experiment without silently tuning the classifier.

## Version 2.7 — Tuned Regime Classifier

- Preserve the legacy classifier as the default.
- Add tuned classification that prioritizes current directional swing structure.
- Use recent BOS and higher-timeframe alignment as trend confirmation.
- Prevent stale CHOCH from dominating current structure.
- Compare legacy and tuned summaries over identical records without changing trades.

**Status:** implemented.

**Outcome:** calibration can measure whether tuned labels reduce transition dominance and restore meaningful trend coverage while every production trading decision remains unchanged.

## Version 2.8 — Tuned Regime Forward Validation

- Validate legacy and tuned labels over identical 5/10/20-bar windows.
- Measure directional behavior, excursions, continuation, reversal, volatility, range, and trend persistence.
- Report class metrics, confusion matrices, confidence reliability, uncertainty, and sample flags.
- Compare accuracy deltas without changing classifications or trades.

**Status:** implemented.

**Outcome:** maintainers can evaluate whether restored trend coverage is more predictive than legacy transition dominance before considering any classifier promotion.

## Version 2.9 — Regime Confidence Calibration Laboratory

- Measure reliability, ECE, MCE, Brier score, distributions, and overconfidence.
- Compare legacy and tuned confidence calibration over shared forward outcomes.
- Simulate five deterministic calibration mappings without applying them.
- Recommend one mapping for further out-of-sample research.
- Preserve all production labels, confidence values, routing, and trades.

**Status:** implemented.

**Outcome:** maintainers can separate improved tuned classification accuracy from unreliable confidence magnitudes before proposing any production confidence changes.

## Version 3.0 — Out-of-Sample Validation Framework

- Split raw history chronologically through holdout, rolling, walk-forward, expanding, and anchored methods.
- Rebuild the complete production pipeline independently for every fold.
- Measure training, validation, full-sample, symbol, and timeframe behavior.
- Quantify generalization decay, drift, stability, variance, and dependency.
- Detect overfit risk without changing production behavior.

**Status:** implemented.

**Outcome:** StructureIQ can test whether historical performance survives unseen market periods without changing a single production trade.

## Version 3.1 — Statistical Research Laboratory

- Analyze every completed calibration across symbols, timeframes, setups, strategies, regimes, confidence, time, and duration.
- Compare existing management, entry-timing, and execution-profile research.
- Build four cross-dimensional performance matrices.
- Rank strongest and weakest combinations with uncertainty and sample-quality warnings.
- Generate an executive summary without changing production behavior.

**Status:** implemented.

**Outcome:** StructureIQ explains where historical performance comes from, where it fails, and where evidence remains too weak to justify changes.

## Beyond Version 3.1

Future work may validate one tuning hypothesis out of sample before any production classifier change. It may also improve data coverage, alerting, portfolio context, personalization, and research workflows. Any execution integration would require a separate architecture, explicit authorization, and independent safety controls; it is not implied by this roadmap.
