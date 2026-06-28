# Changelog

All notable changes to StructureIQ are documented in this file. The project follows an incremental roadmap toward an explainable market intelligence platform.

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
