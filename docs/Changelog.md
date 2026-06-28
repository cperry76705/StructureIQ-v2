# Changelog

All notable changes to StructureIQ are documented in this file. The project follows an incremental roadmap toward an explainable market intelligence platform.

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
