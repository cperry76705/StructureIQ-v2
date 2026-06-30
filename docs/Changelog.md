# Changelog

All notable changes to StructureIQ are documented in this file. The project follows an incremental roadmap toward an explainable market intelligence platform.

## Version 3.8.0 — Confidence Calibration Engine — 2026-06-30

### Added

- Live identity confidence calibration with explicit insufficient reliability.
- Empirical calibration buckets for raw scores from 50 through 100.
- Per-bucket outcomes, win probability, calibrated confidence, sample reliability, method, and warnings.
- Aggregate calibration summary with raw-versus-calibrated averages and fallback buckets.
- Additive `/analysis` and `/calibrate` response fields.

### Production Safety

- Raw Decision Engine confidence remains authoritative and unchanged.
- Calibrated confidence cannot alter action, thresholds, setup, strategy, execution, sizing, or management.
- Aggregate calibration metrics remain independent.

### Verification

- 312 automated tests pass together, including missing history, sparse identity fallback, strong empirical samples, live API output, aggregate bucket output, action invariance, and metric invariance.

## Version 3.7.0 — Execution Intelligence Layer — 2026-06-30

### Added

- Advisory execution quality, grade, preferred style, timing guidance, and level/R:R assessments.
- Explicit execution warnings and blockers with human-readable summaries.
- Additive `/analysis` `execution_intelligence`.
- Additive calibration `aggregate_execution_intelligence_summary`.
- Optional aggregate enrichment from timing, management, MFE/MAE, Monte Carlo, and statistical research.

### Production Safety

- Guidance runs only after action, setup, strategy, and levels are finalized.
- Existing entries, stops, targets, sizing, execution, and management remain unchanged.
- Historical advisory snapshots are internal and cannot affect backtest outcomes or calibration metrics.

### Verification

- 307 automated tests pass together, including avoidance, valid retest, weak confirmation, strong R:R, missing research, level diagnostics, aggregate API output, action invariance, and metric invariance.

## Version 3.6.0 — Centralized Evidence Scoring Engine — 2026-06-30

### Added

- Eleven-category centralized evidence scoring across live analysis and optional research.
- Trade quality, confidence, edge, risk quality, weighted breakdown, contributors, grades, and explanations.
- Additive `/analysis` `score_summary`.
- Additive calibration `aggregate_score_summary` using immutable per-window score snapshots.
- Explicit unavailable-state handling for pipeline, statistical, and Monte Carlo research.

### Production Safety

- ScoreEngine runs only after authoritative decisions, setups, strategies, and levels are finalized.
- Scores cannot alter actions, thresholds, routing, execution, risk, or management.
- Backtest score snapshots are internal research metadata and do not change serialized trades or metrics.

### Verification

- 301 automated tests pass together, including strong, weak, mixed, missing-research, analysis/API, aggregate calibration, action invariance, and metric invariance coverage.

## Version 3.5.0 — Advanced Statistical Validation — 2026-06-30

### Added

- Exact 3/5/8/10-loss run probabilities plus observed and expected losing streaks.
- Seven-bucket R distribution and top 5%/10% gross-profit contribution.
- Chronological first/middle/final-third expectancy and edge-decay scoring.
- OOS fold stability, outlier dependency, weakness score, and named weakness flags.
- Six additive calibration response fields controlled by `statistical_validation_analysis`.

### Readiness Safety

- Negative recent expectancy, severe decay, concentrated profit, poor folds, extreme streak risk, and insufficient samples block paper-trading readiness.
- Validation can only downgrade research status and cannot alter production behavior.
- Aggregate calibration metrics remain unchanged.

### Verification

- 296 automated tests pass together, including stable samples, profitable outlier dependence, profitable decay, negative recent expectancy, fold variance, distributions, API gating, readiness blocking, and metric invariance.

## Version 3.4.0 — Monte Carlo Reporting and Risk Intelligence — 2026-06-30

### Added

- Professional Monte Carlo report with 1st/5th percentile balance and R tails, 30% drawdown probability, and status interpretation.
- Peak-path target probabilities for R thresholds, account growth, and doubling.
- Five-part risk heatmap with categorical status, score, and explanation.
- Approximate 90%, 95%, and 99% expectancy confidence intervals.
- Deterministic Kelly estimates with conservative capped research fraction and stability warnings.
- Explicit failure codes and six additive calibration response fields.

### Readiness Safety

- Insufficient samples, elevated ruin or 20% drawdown risk, non-positive expectancy confidence, and high ruin/tail risk block paper-trading readiness.
- Reporting can only downgrade research readiness; Kelly estimates never alter sizing.
- Production calibration metrics and every trading engine remain unchanged.

### Verification

- 289 automated tests pass together, including status behavior, tails, targets, heatmaps, confidence, Kelly determinism, readiness blocking, API gating, human-readable output, and metric invariance.

## Version 3.3.0 — Monte Carlo Simulation Engine — 2026-06-30

### Added

- Deterministic trade-order reshuffling and bootstrap sampling with replacement.
- Seeded skipped-trade stress and optional stress from observed execution degradation.
- Per-simulation balance, R, drawdown, streak, profit factor, win rate, ruin, profit, and tail-risk metrics.
- Aggregate balance percentiles, drawdown and losing-streak extremes, expectancy dispersion, and drawdown-threshold probabilities.
- Optional calibration request controls and four additive response fields.
- Controlled unavailable output for samples without closed trades.

### Research Safety

- OOS validation returns are used when available; source folds and calibration metrics remain unchanged.
- High ruin or large-drawdown probability can block research promotion readiness only.
- Monte Carlo output cannot change production decisions, setup/strategy routing, risk, execution, or management behavior.

### Verification

- 282 automated tests pass together, including determinism, empty samples, profitable and losing distributions, execution stress, readiness blocking, API gating, and metric invariance.

## Version 3.2.0 — Research Pipeline and Walk-Forward Intelligence — 2026-06-30

### Added

- Unified research pipeline over finalized calibration, statistical research, and OOS artifacts.
- Per-fold setup, strategy, and regime performance snapshots alongside existing symbol and timeframe validation.
- Walk-forward intelligence for expectancy decay, variance, consistency, dependency, drawdown stability, trade frequency, and confidence drift.
- Robustness rankings with training/validation metrics, fold consistency, sample quality, readiness, and human-readable conclusions.
- Conservative promotion statuses with hard 100-trade minimum and 300/500-trade strong/excellent sample standards.
- Additive pipeline summaries, readiness report, and research action items on OOS-enabled calibration responses.

### Compatibility and Safety

- Pipeline fields remain null when OOS validation is disabled.
- Rankings consume completed result objects only and cannot modify calibration metrics or production engines.
- `READY_FOR_PAPER_TRADING` is advisory and requires separate human review; it starts no process and changes no rule.

### Verification

- 275 automated tests pass together, including sample gates, fold-variance penalties, overfit penalties, stable-sample readiness, API gating, readable recommendations, and production-metric invariance.

## Version 3.1.1 — Yahoo Provider Resilience Fix — 2026-06-29

### Fixed

- Capped Yahoo chart ranges to `7d` for `1m`, `1mo` for `5m`/`15m`/`30m`, and `2y` for `1h`; daily selection remains unchanged.
- Added detailed Yahoo failure context containing requested and normalized symbols, timeframe, interval, lookback, selected range, and capped range.
- Isolated calibration market-data failures per run so available symbol/timeframe combinations continue.
- Made all-failed calibration requests return controlled zero metrics and human-readable availability diagnostics instead of an unhandled `503`.

### API

- Added `provider_failures`, `failed_runs`, and `data_availability_summary` to calibration responses.
- Completed-run aggregate metrics exclude failed provider combinations and remain otherwise unchanged.

### Verification

- 270 automated tests pass together, including interval caps, daily-range compatibility, provider error context, partial completion, all-failed responses, API serialization, and existing regressions.

## Version 3.1.0 — Statistical Research Laboratory — 2026-06-29

### Added

- Automatic post-calibration research across symbols, timeframes, setup families, strategies, regimes, confidence buckets, UTC hours and weekdays, and trade duration.
- Process-local Continuous Research Engine that ingests finalized calibration records and refreshes read-only rolling reports.
- Rolling windows for the latest 250, 500, or 1,000 closed trades, all-time history, and custom lookbacks.
- Research status, rankings, strongest-combination, weakest-combination, and manual-refresh endpoints.
- Optional background refresh scheduler that remains disabled until explicitly started.
- Consistent performance rows with outcomes, expectancy, risk/excursion measures, confidence intervals, significance, sample quality, and recommendations.
- Existing stop-management, entry-timing, and execution-profile comparison ingestion.
- Regime/strategy, setup/regime, symbol/setup, and timeframe/setup matrices.
- Top and bottom ten combination rankings plus headline expectancy, profit factor, drawdown, significance, and sample-size leaders.
- Executive summary, overfitting concentration checks, insufficient-sample warnings, promising under-tested findings, and statistically insignificant findings.

### Compatibility and Safety

- Research executes only after calibration records and optional laboratories are complete.
- No production decision, setup, strategy, confidence, entry, stop, target, risk, execution, or management rule reads research output.
- Existing aggregate calibration metrics remain unchanged.
- All response fields are additive.
- Continuous research snapshots are reporting-only and have no dependency path into production engines.

### Verification

- 260 automated tests pass together, including deterministic statistics, confidence intervals, rolling research windows, rankings, API reporting, scheduler defaults, and production-metric invariance.

## Version 3.0.1 — OOS Response Reporting Hardening — 2026-06-29

### Fixed

- Added the exact 300-candle walk-forward request to the generated OpenAPI examples; the previous primary example represented ordinary calibration with OOS disabled.
- Added an enabled-request response invariant preventing OOS validation from silently returning null laboratory sections.
- Added HTTP regression coverage proving all eight OOS response fields serialize and the five primary sections are non-null for the documented request.
- Confirmed disabled requests retain null OOS fields and unchanged calibration metrics.

### Verification

- 251 automated tests pass together.

## Version 3.0.0 — Out-of-Sample Validation Framework — 2026-06-29

### Added

- Opt-in chronological, rolling-window, walk-forward, expanding-window, and anchored validation methods.
- Fresh bounded market-data providers and production backtesters for every training and validation segment.
- Fold, aggregate, symbol, and timeframe measurements covering performance, confidence, setup, strategy, regime, execution, and management behavior.
- Generalization score, decay, drift, stability, variance, coefficient-of-variation, and trade-frequency diagnostics.
- Automatic collapse, instability, variance, risk, market, symbol, and timeframe dependency detection with LOW/MEDIUM/HIGH/OVERFIT_RISK levels.
- Additive out-of-sample summaries, fold results, overfitting and stability reports, and research recommendations.

### Compatibility and Safety

- Candles remain chronological and are never shuffled.
- Each fold reruns production engines from raw candles without cached training decisions.
- Warm-up context contains candles only; no analysis or trade object crosses the split.
- `/analysis`, `/backtest`, production classifiers, decisions, setups, strategies, thresholds, risk, execution, timing, and management are unchanged.
- Ordinary calibration metrics are identical with validation enabled or disabled.

### Verification

- 250 automated tests pass together, including every split family, deterministic folds, generalization and overfit diagnostics, additive API behavior, and production regression protection.

## Version 2.9.0 — Regime Confidence Calibration Laboratory — 2026-06-29

### Added

- Opt-in `regime_confidence_analysis` gated by compare-mode forward validation.
- Legacy and tuned confidence reliability buckets, ECE, MCE, Brier score, curves, distributions, and calibration-state flags.
- Deterministic identity, linear compression, temperature scaling, isotonic approximation, and piecewise mapping simulations.
- Mapping recommendation with expected ECE/confidence reduction, improvement, and sample-based research confidence.
- Legacy-versus-tuned ECE, MCE, Brier, confidence, and overconfidence comparison.

### Compatibility and Safety

- Production regime labels and confidence values remain unchanged.
- No mapping is applied to analysis, routing, backtesting, or trading behavior.
- `/analysis` and `/backtest` contracts remain unchanged.
- Ordinary calibration metrics and trade outcomes are identical with confidence analysis enabled or disabled.

### Verification

- 245 automated tests pass together, including exact ECE/MCE/Brier fixtures, reliability and distribution checks, deterministic mappings, recommendation selection, request gating, and metric invariance.

## Version 2.8.0 — Tuned Regime Forward Validation — 2026-06-29

### Added

- Opt-in `forward_validation` for `regime_classifier_mode: compare`.
- Matched legacy and tuned validation over identical 5/10/20-bar future windows.
- Directional return, MFE/MAE, continuation, reversal, volatility expansion, range persistence, and trend persistence statistics.
- Accuracy, macro precision/recall/F1, direction and regime-family accuracy, confusion matrices, confidence reliability, and persistence validation.
- Sample sizes, dispersion, approximate confidence intervals, and `LOW_SAMPLE`, `HIGH_CONFIDENCE`, and `INSUFFICIENT_DATA` flags.
- Direct tuned-minus-legacy comparison and research recommendations.

### Compatibility and Safety

- Validation is disabled by default and cannot run outside compare mode.
- `/analysis` request/output and `/backtest` output remain unchanged.
- Forward snapshots are internal and excluded from serialization.
- Classifications, decisions, setups, strategies, trade selection, risk levels, outcomes, and aggregate metrics are unchanged.

### Verification

- 240 automated tests pass together, including matched samples, confusion/reliability/persistence outputs, mode gating, low-sample flags, and metric invariance.

## Version 2.7.0 — Tuned Regime Classifier — 2026-06-29

### Added

- Parallel `TunedMarketRegimeEngine` that prioritizes current directional swing structure and recent event evidence.
- Optional `regime_classifier_mode` with `legacy`, `tuned`, and `compare`; legacy remains the default.
- Side-by-side legacy and tuned regime summaries over identical calibration records.
- Classifier comparison covering transition reduction, trend restoration, changed labels, agreement, and transition destinations.
- Internal tuned labels on analysis/backtest records, excluded from public serialization.

### Compatibility and Safety

- The legacy `MarketRegimeEngine` is unchanged.
- `/analysis` request and response contracts are unchanged.
- Decision, setup, strategy, entry, stop, target, risk, execution, and backtest trade-selection logic are unchanged.
- Calibration computes trading metrics once; classifier modes only regroup the same immutable records for regime research.
- Existing market-regime, validation, and tuning laboratories continue to use their established behavior.

### Verification

- 235 automated tests pass together, including legacy defaults, stale-CHOCH handling, preserved range/compression/expansion behavior, BOS and higher-timeframe evidence, compare mode, and metric invariance.

## Version 2.6.0 — Regime Classifier Tuning Laboratory — 2026-06-28

### Added

- Optional `regime_tuning_analysis` calibration flag and additive `regime_tuning_summary`.
- Competing trend, range, transition, compression, and expansion evidence scores retained as non-serialized research snapshots.
- Diagnostics for transition reasons, stale CHOCH, absent recent BOS/CHOCH, directional structure hidden by transition, conflicts, confidence, and classification margins.
- Deterministic forward stability at 5, 10, and 20 bars.
- Counterfactual transition thresholds at 60, 65, 70, 75, and 80.
- Isolated stronger-BOS, CHOCH, swing-structure, and higher-timeframe-alignment simulations.

### Compatibility

- The production Regime Engine is unchanged; simulations operate only on copied research scores.
- `/analysis` request and response contracts are unchanged, and `/backtest` does not serialize internal tuning evidence.
- Decision, setup, strategy, timing, stops, targets, thresholds, and execution behavior are unchanged.
- Existing regime analysis and validation flags remain independent and functional.

### Verification

- 227 automated tests pass together, including focused tuning, counterfactual immutability, opt-in API, and legacy contract tests.

## Version 2.5.0 — Regime Validation Laboratory — 2026-06-28

### Added

- Optional proxy validation of classification balance, confidence, persistence, and 5/10/20-bar forward behavior.
- Documented transition-overuse threshold of greater than 60%.
- Transition-exit analysis, predicted-versus-forward-proxy confusion counts, and insufficient-sample reporting.
- Diagnostics for transition overuse, trend underclassification, low-confidence clustering, short-duration noise, forward mismatch, and insufficient samples.
- Compact forward observations on backtest records using existing cached candles.

### Compatibility

- Existing Regime Engine classifications and all production trading behavior are unchanged.
- `regime_validation_analysis` defaults to false and does not affect ordinary calibration or regime-analysis output.
- Forward proxy labels are explicitly diagnostic approximations, not ground truth.

### Verification

- 222 automated tests pass together.

## Version 2.4.0 — Market Regime Laboratory — 2026-06-28

### Added

- Deterministic regime classification for trend strength, range, compression, expansion, volatility, transition, and unknown conditions.
- Additive regime confidence, evidence, and summary on `/analysis` and backtest records.
- Optional calibration regime summaries with outcomes, R, drawdown, duration, MFE/MAE, and best/worst setup and strategy.
- Strategy-by-regime and setup-by-regime performance matrices.
- Research recommendations for weak expectancy, excessive drawdown, sparse samples, dominance, and underperformance.

### Compatibility

- Regime output never feeds Decision, Setup, Strategy, entry, execution, stop, target, threshold, or risk logic.
- `market_regime_analysis` defaults to false; existing calibration metrics and laboratories are unchanged.
- No indicators, ML, external dependencies, broker integration, or live trading were added.

### Verification

- 217 automated tests pass together.

## Version 2.3.0 — Entry Timing Laboratory — 2026-06-28

### Added

- Optional `entry_timing_profiles` on calibration with an automatic immediate-entry baseline.
- Nine deterministic timing models covering market timing, pullbacks, momentum entries, retests, and conservative limits.
- Fill, miss, fallback, delay, entry-improvement, and missed-opportunity diagnostics over identical valid candidates.
- Entry-timing summaries ranking expectancy, fill rate, risk-adjusted performance, and missed entries.

### Compatibility

- Timing scenarios are isolated from production calibration metrics and ordinary backtest metrics.
- Production entry, decisions, setups, strategies, thresholds, stops, and targets are unchanged.
- Existing requests without timing profiles follow the previous code path.

### Verification

- 212 automated tests pass together.

## Version 2.2.0 — Execution Sensitivity Laboratory — 2026-06-28

### Added

- Optional `execution_sensitivity_profiles` on calibration requests with an automatically included perfect baseline.
- Side-by-side performance, cost, drawdown, and expectancy comparison without mutating production calibration metrics.
- Deterministic attribution to spread, slippage, commission, fill model, or combined costs.
- Documented eight-profile Forex and Crypto helper sets ranging from perfect through harsh illustrative scenarios.
- A calibration data cache ensuring every profile receives the same candle snapshot.

### Compatibility

- Omitting sensitivity profiles preserves the existing calibration call path and metrics.
- Analysis, decisions, setups, strategies, thresholds, stops, targets, and ordinary execution profiles are unchanged.
- Scenario defaults are examples, not broker or exchange cost claims.

### Verification

- 204 automated tests pass together.

## Version 2.1.0 — Execution Realism Engine — 2026-06-28

### Added

- Optional typed execution profiles for spread, fixed or seeded-random slippage, fixed or percentage commissions, partial-fill studies, and immediate, next-bar, or touch fills.
- Per-trade execution diagnostics with requested and actual entry, costs, fill model, quality, baseline R, realistic R, and degradation.
- Backtest and calibration execution summaries comparing perfect and modeled expectancy.
- Deterministic execution tests for bullish and bearish spread, slippage, commissions, delayed fills, diagnostics, aggregation, and perfect-execution compatibility.

### Compatibility

- Omitting `execution_profile` retains the existing perfect-execution path.
- Analysis, decisions, setup selection, thresholds, and stop/target rules are unchanged.
- Execution realism applies only to historical backtesting and calibration.

### Verification

- 196 automated tests pass together.

## Version 2.0.0 — Bearish BOS Retest Expansion — 2026-06-28

### Added

- Conservative production comparison between simultaneous bearish BOS retest and liquidity-sweep reversal short candidates.
- Eligibility gates for bearish structure, recent BOS, resistance retest, bearish or mixed-bearish alignment, complete valid levels, confirmation, and at least `1.5R`.
- Evidence-weighted tie-breaking with explicit selection and non-selection reasons.
- Calibration reporting that states whether bearish BOS retests contribute closed production trades.

### Compatibility

- Liquidity-sweep reversal short remains selectable and wins when reversal evidence is stronger.
- Confidence, confirmation, `1.5R`, strategy, and backtest execution gates are unchanged.
- `/analysis` remains backward-compatible.

### Verification

- 184 automated tests pass together.

## Version 1.9.0 — Setup Expansion and Candidate Coverage Diagnostics — 2026-06-28

### Added

- Additive candidate diagnostics covering selection, status, direction, levels, geometry, R:R, quality, and the primary blocker.
- Per-backtest `setup_coverage_summary` and calibration `aggregate_setup_coverage_summary`, including per-family and missed-executable counts.
- Evidence-based setup-family recommendations without automatic selection or expansion.

### Compatibility

- First-match setup selection, confidence and confirmation thresholds, strategy routing, execution gates, and outcome simulation are unchanged.
- `/analysis` only gains an additive nested diagnostic collection.
- No dashboard, broker execution, live trading, or automatic setup expansion was added.

### Verification

- 180 automated tests pass together.

## Version 1.8.0 — Stop Management and Profit Protection Study — 2026-06-28

### Added

- Typed management rules for unchanged, break-even, partial-profit, and trailing studies at `1R` and `1.5R`.
- Per-backtest and aggregate calibration `TradeManagementSensitivityResult` collections.
- Deterministic R, profit-factor, and drawdown comparisons against the unchanged baseline.
- Conservative handling that excludes same-candle ambiguity and requires prior completed-candle threshold reach for losing trades.
- Recommendations naming the strongest improving rule while requiring out-of-sample validation.
- Focused break-even, partial-profit, trailing, baseline-equivalence, aggregation, and production-metric regression tests.

### Compatibility

- Production stop/target behavior and the original backtest simulator are unchanged.
- `/analysis` request and response remain unchanged.
- Strategy selection, thresholds, and setup confirmation remain unchanged.
- New `/backtest` and `/calibrate` fields are additive research output.
- No dashboard, broker execution, live trading, or automatic management adoption was added.

### Changed

- Application and OpenAPI version are now `1.8.0`.

### Verification

- 176 automated tests pass together.
- The live four-symbol calibration ranked `trail_after_1r` highest at 1.75R versus 0.50R baseline on three closed trades; the sample is explicitly too small for production adoption.

## Version 1.7.0 — Trade Outcome Diagnostics — 2026-06-28

### Added

- Typed `TradeOutcomeDiagnostics`, `LossReason`, first-touch state, bars to outcome, and R-based MFE/MAE.
- Initial directional follow-through detection requiring a completed `+0.5R` move before stop.
- Per-backtest and aggregate calibration outcome summaries.
- Dominant-loss recommendations for entry timing, confirmation, structure/alignment, ambiguity, and risk review.
- Focused target-first, stop-first, ambiguity, bullish/bearish excursion, immediate-stop, no-follow-through, aggregation, and unchanged-outcome tests.

### Compatibility

- The existing simulator and conservative same-candle loss rule are unchanged.
- `/analysis` request and response remain unchanged.
- Strategy selection, confidence thresholds, setup confirmation, stops, and targets are unchanged.
- New `/backtest` and `/calibrate` fields are additive.
- No dashboard, broker execution, or live trading was added.

### Changed

- Application and OpenAPI version are now `1.7.0`.

### Verification

- 171 automated tests pass together.
- The requested live four-symbol calibration produced three losses classified as `stop_too_tight`, with 1.276R average MFE and no same-candle ambiguity or immediate-stop losses.

## Version 1.6.0 — Instrument-Aware Level Precision and Zone Width — 2026-06-28

### Added

- Instrument metadata helpers for asset class, precision, tick size, pip size, minimum zone width, ATR, and adaptive zone width.
- Numeric risk-level plans calculated before public formatting.
- Focused forex, crypto, zone-width, formatting, geometry, numeric-R, and unchanged-gate tests.

### Changed

- Removed the fixed `25.0` minimum zone width in favor of instrument floors plus percentage/ATR scaling.
- EUR-USD and GBP-USD levels preserve five decimals; BTC-USD, ETH-USD, and default symbols preserve two.
- Analysis estimated R now derives from the same numeric entry, stop, and target geometry represented by the plan.
- Application and OpenAPI version are now `1.6.0`.

### Compatibility

- `/analysis` request and response fields remain unchanged.
- Execution simulation, setup confirmation, strategy routing, and the `1.5R` minimum are unchanged.
- No dashboard, broker execution, live trading, or forced trade qualification was added.

### Verification

- 163 automated tests pass together.
- The requested live four-symbol calibration was rerun with 200 records after implementation.

## Version 1.5.0 — Risk/Reward and Setup Level Diagnostics — 2026-06-28

### Added

- Typed `RiskRewardDiagnostics`, failure reasons, and deterministic bullish/bearish geometry validation.
- Typed `SetupLevelDiagnostics` with level provenance, structural context, and level quality.
- Per-record risk/reward and setup-level diagnostics for skipped and simulated backtest records.
- Backtest and calibration summaries for missing levels, invalid geometry, below-minimum R, average and median R, near-threshold clustering, passing R, and dominant failures.
- Target-selection, stop-placement, support/resistance, level-generation, and controlled minimum-R study recommendations.
- Focused geometry, distribution, API, setup provenance, and aggregation tests.

### Compatibility

- `/analysis` request and existing response fields remain unchanged.
- Backtest execution behavior, setup confirmation, and the `1.5R` minimum remain unchanged.
- New API fields are additive and diagnostics run on skipped records.
- No dashboard, broker execution, live trading, or automatic tuning was added.

### Changed

- Application and OpenAPI version are now `1.5.0`.

### Verification

- 155 automated tests pass together.
- Tests cover bullish and bearish passing geometry, each missing level, invalid geometry, close targets, wide stops, near-threshold distributions, API fields, and calibration aggregation.

## Version 1.4.0 — Decision Threshold Sensitivity Study — 2026-06-27

### Added

- Typed `ThresholdSensitivityResult` output for thresholds 50, 55, 60, 65, and 70.
- Immutable execution-readiness snapshots on backtest records.
- Directional eligibility based on raw score plus existing structure and timeframe gates.
- Separate execution blocker counts for missing setup, levels, risk/reward, confirmation, and strategy alignment.
- Estimated trade-candidate counts using the intersection of directional and execution eligibility.
- Calibration recommendations explaining when lower confidence thresholds would still produce no executable candidates.

### Compatibility

- Production Decision Engine behavior and thresholds are unchanged.
- Existing backtest trades and outcomes are unchanged.
- `/analysis` request and response remain unchanged.
- `/calibrate` and backtest records only add response fields.
- No dashboard, broker execution, live trading, or automatic tuning was added.

### Changed

- Application and OpenAPI version are now `1.4.0`.

### Verification

- 147 automated tests pass together.
- Tests confirm threshold 50 increases directional eligibility relative to 70 without mutating production decisions or backtest outcomes.

## Version 1.3.0 — Risk/Reward Calibration and Gate Refinement — 2026-06-27

### Changed

- Decision Engine risk/reward remains weighted evidence but missing or low ratios no longer independently veto directional buy/sell output.
- Missing risk/reward applies a moderate confidence penalty and execution warning rather than dominating the decision score.
- Decision diagnostics now separate required `directional_confidence`, structure, and timeframe gates from non-required execution and risk-plan observations.
- Setup confirmation now explicitly requires entry zone, stop loss, target, and at least `1.5R`.
- Backtesting independently rejects missing, malformed, or sub-`1.5R` execution plans.
- Calibration recommendations distinguish directional confidence research from Setup/risk execution bottlenecks.
- Application and OpenAPI version are now `1.3.0`.

### Compatibility

- `/analysis` request and existing response fields remain unchanged.
- Risk/reward logic was retained and moved to the engine layer that owns execution readiness.
- No dashboard, broker execution, live trading, or automatic threshold tuning was added.

### Verification

- 143 automated tests pass together.
- Regression coverage confirms missing risk plans remain non-executable while no longer acting as automatic directional vetoes.

## Version 1.2.0 — Decision Engine Sensitivity Report — 2026-06-27

### Added

- Typed `DecisionDiagnostics` and `GateResult` output on every engine-generated decision.
- Raw score, final confidence, intended direction, confidence band, failed required gates, and deterministic gate results.
- Decision diagnostic snapshots on backtest records and result-level confidence/gate aggregation.
- Aggregate Decision Engine diagnostics and dominant-gate recommendations in calibration.
- Focused decision, backtest, calibration, API, and unchanged-action tests.

### Changed

- Application and OpenAPI version are now `1.2.0`.
- Analysis, backtest, and calibration responses add diagnostic fields without changing existing fields or decision behavior.

### Compatibility

- The `/analysis` request body and existing response fields are unchanged.
- Existing confidence, structure, timeframe, and risk/reward thresholds are unchanged.
- Setup confirmation is identified as downstream rather than misrepresented as a Decision Engine gate.
- No dashboard, broker execution, or live trading was added.

### Verification

- 139 automated tests pass together.
- Regression coverage confirms diagnostics do not alter buy, sell, wait, or avoid actions.

## Version 1.1.0 — Actionability Diagnostics — 2026-06-27

### Added

- Primary skip reason code, detail, blocking engine, and actionability status on backtest records.
- Typed `SkipDiagnostics` on backtest results with reason and engine counts.
- Aggregate skip diagnostics across all calibration runs.
- Gate-specific calibration recommendations based on the dominant skip cause.
- Focused diagnostics, aggregation, API, and unchanged-behavior regression tests.

### Changed

- Centralized the existing `1.5R` Setup Engine minimum so diagnostics describe the current gate without duplicating or changing it.
- Backtest and calibration summaries expose skipped-record context while preserving simulation and scoring behavior.
- Application and OpenAPI version are now `1.1.0`.

### Compatibility

- `/analysis` input and output are unchanged.
- `/backtest` and `/calibrate` only add response fields.
- No decision, setup, strategy, confidence, or risk/reward threshold was loosened.
- No dashboard, broker execution, or live trading was added.

### Verification

- 135 automated tests pass together.
- Regression coverage confirms actionable trade simulation and `/analysis` compatibility remain unchanged.

## Version 1.0.0 — Stable MVP Release Candidate — 2026-06-27

### Added

- Central `APP_VERSION` release identity used by FastAPI and OpenAPI.
- Professional project overview, architecture summary, quick start, API examples, limitations, roadmap, and decision-support disclaimer in `README.md`.
- Contribution and security policies, a distribution-license placeholder, and a pull-request test workflow.
- `docs/ReleaseNotes_v1.0.0.md` with the Stable MVP scope, endpoints, limitations, and next improvements.
- Release contract tests for the version identity and complete OpenAPI endpoint/method surface.

### Changed

- Added endpoint grouping, summaries, and docstrings to improve generated OpenAPI documentation without changing request or response contracts.
- Expanded ignore rules for secrets, editor state, coverage output, and Python build artifacts.
- Reviewed legacy scoring and strategy-router compatibility layers; they remain intentionally available while primary analysis uses the dedicated engines.
- Updated roadmap, API, and testing documentation for the release-candidate state.

### Compatibility

- The `/analysis` request body is unchanged.
- Existing response fields and all seven public endpoint paths remain available.
- No dashboard, broker execution, live trading, or major trading feature was added.

### Verification

- 126 automated tests pass together.
- The release contract is checked through generated OpenAPI metadata.

## Version 0.9 — Validation and Calibration — 2026-06-27

### Added

- Provider-boundary symbol normalization in `core/symbols.py`.
- Yahoo mappings for supported user-facing forex pairs while preserving crypto, existing Yahoo symbols, and unknown symbols safely.
- Deterministic calibration in `core/calibration.py`.
- Typed `CalibrationRequest`, `CalibrationResult`, `CalibrationRun`, `CalibrationMetrics`, `SetupPerformance`, `StrategyPerformance`, and `CalibrationRecommendation` models.
- Cartesian calibration runs across requested symbols, current timeframes, and higher timeframes.
- Aggregate closed/skipped behavior, setup and strategy performance groups, and R-based metrics.
- Diagnostic recommendations for conservative, aggressive, weak setup, weak strategy, risk, and data-quality behavior.
- `POST /calibrate` endpoint.
- `docs/Calibration.md` describing normalization, metrics, recommendations, determinism, and limitations.
- Focused symbol, provider integration, calibration aggregation, recommendation, endpoint, and regression tests.

### Changed

- `/analysis`, `/backtest`, and `/calibrate` can use friendly forex symbols with the default Yahoo provider while preserving the requested symbol in public results.
- Calibration recommendations remain observational and never change weights or thresholds automatically.

### Verification

- 124 automated tests pass.
- The complete v0.1 through v0.9 suite passes together.

### Scope

- Calibration inherits the simplified backtest's execution assumptions and has no statistical significance or out-of-sample model yet.
- No automatic optimization, machine learning, dashboard, broker execution, or live trading was added.

## Version 0.8 — Journal and Backtesting — 2026-06-27

### Added

- Local append-only JSONL journaling in `core/journal.py`.
- Typed `JournalEntry`, `JournalStore`, `TradeOutcome`, and `JournalSummary` models.
- Journal filtering by symbol, timeframe, and outcome plus R-based summaries.
- Deterministic historical evaluation in `core/backtesting.py`.
- Typed `BacktestRequest`, `BacktestResult`, `BacktestTrade`, and `BacktestMetrics` models.
- Historical analysis-window replay using the existing market data provider and StructureIQ pipeline.
- Conservative stop/target simulation, skipped-plan records, maximum trade caps, R metrics, profit factor, and maximum drawdown.
- `POST /journal`, `GET /journal`, `GET /journal/summary`, and `POST /backtest` endpoints.
- Focused journal, backtest, metrics, persistence, filtering, limitation, endpoint, and regression tests.
- `docs/JournalBacktesting.md` describing storage, simulation rules, metrics, and limitations.

### Changed

- The platform can now measure historical directional usefulness without adding execution behavior.
- Existing `/health` and `/analysis` contracts remain unchanged.

### Verification

- 105 automated tests pass.
- The complete v0.1 through v0.8 suite passes together.

### Scope

- The backtest is intentionally simplified and does not model position sizing, fees, spread, slippage, latency, partial fills, or market impact.
- No dashboard, broker execution, live trading, or machine learning was added.

## Version 0.7 — Strategy Engine — 2026-06-27

### Added

- Dedicated playbook comparison in `core/strategy_engine.py`.
- Typed `StrategyResult`, `StrategyCandidate`, `StrategyType`, `StrategyStatus`, and `StrategyScoreBreakdown` models.
- Ranked trend-continuation, pullback-continuation, breakout-continuation, range-reversal, liquidity-sweep reversal, and compression-breakout candidates.
- A `25/25/25/15/10` fit model across structure, timeframes, setup, risk, and existing indicator confirmation.
- Candidate supporting evidence, opposing evidence, required conditions, invalidation, and notes.
- Additive `strategy` data on successful `POST /analysis` responses.
- Strategy context supplied to the Analysis/Explanation Engine after ranking.
- Focused tests for all playbooks, decision constraints, selection, alignment, score breakdowns, evidence, no-strategy behavior, and API compatibility.

### Changed

- Broader playbook ranking now occurs after Setup Engine qualification and before trader-facing explanation.
- Avoid rejects all candidates; wait permits developing or viable candidates but never promotes them to preferred status.
- The legacy strategy router remains available but is not part of the primary analysis path.

### Verification

- 84 automated tests pass.
- The complete v0.1 through v0.7 suite passes together.

### Scope

- Scores are deterministic heuristics and have not yet been calibrated with backtesting.
- No journal, dashboard, broker execution, or live trading work was added.

## Version 0.6 — Analysis/Explanation Engine — 2026-06-27

### Added

- Dedicated trader-facing explanation logic in `core/explanation_engine.py`.
- Typed `TraderAnalysis`, `TradePlan`, `ExplanationSection`, `WaitForCondition`, `KeyRisk`, and `MarketNarrative` models.
- Plain-English headlines, market narratives, recommendations, evidence explanations, key risks, and next actions.
- Checklist projection of unmet required setup conditions and structural invalidation rules.
- Confidence interpretation for weak, moderate, strong, and high-conviction evidence ranges.
- Additive `trader_analysis` data on successful `POST /analysis` responses.
- Fallback language and nullable plan fields when optional setup data is unavailable.
- Focused tests for actionable buy and sell plans, wait and avoid outcomes, checklists, invalidation, confidence bands, fallback behavior, and API compatibility.

### Changed

- `/analysis` now exposes both detailed internal engine output and a separate trader-facing analysis layer.
- Explanation logic consumes Decision and Setup results without recomputing or overriding either result.

### Verification

- 71 automated tests pass.
- The complete v0.1 through v0.6 suite passes together.

### Scope

- The engine uses deterministic templates; natural-language generation and personalization are not included.
- Strategy comparison, journaling, dashboard work, broker execution, and live trading remain out of scope.

## Version 0.5 — Setup Engine — 2026-06-27

### Added

- Dedicated setup qualification in `core/setup_engine.py`.
- Typed `SetupResult`, `SetupType`, `SetupStatus`, `EntryCondition`, and `InvalidationRule` models.
- Bullish and bearish BOS retest and pullback-continuation candidates.
- Long and short range-reversal, liquidity-sweep reversal, and compression-breakout candidates.
- Checklist-style entry conditions, structural invalidation, quality scoring, warning notes, and estimated risk/reward.
- Additive `setup_plan` data on successful `POST /analysis` responses.
- Focused tests for all required setup families, avoid and wait constraints, range location, checklist output, invalidation, risk/reward, and API compatibility.

### Changed

- The Setup Engine is now the primary source of the legacy top-level `setup` value and the nested setup plan.
- `core/strategy_router.py` remains available for compatibility but is no longer used by the main analysis path.
- Compression is approximated from candle-range contraction without adding a new indicator.

### Verification

- 60 automated tests pass.
- The complete v0.1 through v0.5 suite passes together.

### Scope

- BOS retests currently use the relevant support or resistance zone as a proxy for the persisted broken level.
- No trader-facing explanation engine, dashboard, broker execution, live trading, or new indicator work was added.

## Blueprint Adjustment — Trader-Facing Decision Support — 2026-06-27

### Changed

- Reframed the product evolution from a raw analysis API toward a trader-facing decision-support platform.
- Separated internal engine output from trader-facing analysis output.
- Split setup qualification, broader strategy selection, and explanation into distinct architectural responsibilities.
- Defined the Decision Engine as the sole owner of buy, sell, wait, avoid, and weighted confidence.
- Positioned the Setup Engine after decision scoring and the Strategy Engine after setup qualification.
- Defined the Analysis/Explanation Engine as a presentation layer that explains decisions and builds plans without making or changing them.
- Expanded the roadmap through versions 0.5–0.8 before the version 1.0 platform milestone.
- Documented the current `/analysis` response as engine-oriented and described the future additive trader-facing analysis direction.

### Added

- `docs/SetupEngine.md` with setup responsibilities, types, validation, entry checklists, invalidation, and engine relationships.
- `docs/StrategyEngine.md` with post-qualification playbook selection and ownership boundaries.
- Checklist-style trade plans as a formal trader-facing output concept.

### Scope

- Documentation and architecture only.
- No application code, API behavior, dashboard, broker execution, or live trading functionality changed.

## Version 0.4 — Decision Engine — 2026-06-27

### Added

- Dedicated weighted decision logic in `core/decision_engine.py`.
- Typed `DecisionResult`, `EvidenceItem`, `ScoreBreakdown`, and `DecisionAction` models.
- Blueprint-aligned category weights for structure, multi-timeframe alignment, price and liquidity context, indicators, and risk/reward and volatility.
- Positive, negative, and neutral evidence ledgers with signed impacts.
- Explicit risk notes, structural invalidation notes, confidence gates, and human-readable recommendations.
- Additive `decision` data on successful `POST /analysis` responses.
- Focused tests for bullish and bearish decisions, mixed and conflicting context, confidence thresholds, score totals, evidence, risk, invalidation, and API compatibility.

### Changed

- The Decision Engine is now the single source of top-level `/analysis` action and confidence.
- Legacy top-level confidence remains on a `0–10` scale and is derived from nested decision confidence on a `0–100` scale.
- Nested `avoid` decisions map to the existing top-level `no_trade` action.
- `core/scoring.py` remains available for compatibility but is no longer used by the main analysis path.

### Verification

- 47 automated tests pass.
- The complete v0.1 through v0.4 suite passes together.

### Scope

- Existing RSI support is used as indicator confirmation; no new indicators were added.
- ATR-based volatility quality is reported as unavailable rather than inferred.
- No dashboard, broker execution, or live trading work was added.

## Version 0.3 — Multi-Timeframe Analysis — 2026-06-27

### Added

- Two-timeframe analysis in `core/multi_timeframe.py`.
- Typed `TimeframeAnalysis`, `TimeframeAlignment`, and `MultiTimeframeResult` models.
- Alignment classifications for aligned bullish, aligned bearish, mixed, conflicting, and unclear structure.
- A deterministic `0–100` alignment score, unified directional bias, evidence reasons, and a human-readable summary.
- Additive `multi_timeframe` data on successful `POST /analysis` responses.
- Focused tests for aligned, pullback, ranging, conflicting, unclear, confidence, routing, and API compatibility behavior.

### Changed

- Confidence now rewards strong timeframe agreement and penalizes direct conflict or unclear context.
- Strategy routing waits on conflicting or unclear alignment.
- Mixed alignment requires the current trend, key-level context, and candle confirmation to support the higher-timeframe direction before producing an actionable assessment.
- All legacy `/analysis` response fields retain their existing names and types.

### Verification

- 38 automated tests pass.
- The complete v0.1, v0.2, and v0.3 suite passes together.

### Scope

- v0.3 is intentionally limited to the request's higher and current timeframes.
- No dashboard, broker execution, live trading, or new indicator work was added.

## Version 0.2 — Market Structure Engine — 2026-06-27

### Added

- Typed `SwingPoint`, `StructureEvent`, and `MarketStructureResult` metadata for explainable structure analysis.
- Explicit swing kind, HH/HL/LH/LL relationship, and confirmation index tracking.
- Detailed BOS, CHOCH, and liquidity-sweep events with timestamps, prices, reference swings, and explanations.
- Complete confirmed swing collections and chronological detailed events on each structure result.
- Focused synthetic tests for required trend, break, reversal, sweep, metadata, and summary behavior.

### Changed

- Structural events now use only confirmed fractal swings.
- Repeated sweeps of the same reference swing are deduplicated.
- Human-readable summaries now include the latest directional swing sequence as well as structural breaks and sweeps.
- The existing `/analysis` request and response contract remains unchanged.

### Verification

- 26 automated tests pass.
- Required coverage includes bullish, bearish, ranging, bullish and bearish BOS, bullish and bearish CHOCH, and high and low liquidity sweeps.

### Scope

- No dashboard, broker execution, or new indicator work was added.

## Current Foundation — 2026-06-27

### Added

- FastAPI application with `GET /health` and `POST /analysis` endpoints.
- Validated request and response schemas.
- Market data provider abstraction and normalized candle model.
- Yahoo Finance provider as the default data source.
- Explicit OANDA and Polygon provider placeholders for future integration.
- Foundational market structure analysis for swings, HH/HL/LH/LL, BOS, CHOCH, liquidity sweeps, and market phases.
- Support/resistance, indicator, risk, scoring, strategy-routing, and analysis modules.
- Dependency injection for provider replacement and deterministic API testing.
- Informative `503 Service Unavailable` behavior for market data failures.
- Initial official project blueprint in `docs/`.

### Verification

- 20 automated tests currently pass.

### Scope

- StructureIQ is defined as a market intelligence and decision-support platform.
- The current foundation performs no live trade execution and does not connect to a broker for order placement.
