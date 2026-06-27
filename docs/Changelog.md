# Changelog

All notable changes to StructureIQ are documented in this file. The project follows an incremental roadmap toward an explainable market intelligence platform.

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
