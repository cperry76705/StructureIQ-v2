# StructureIQ Roadmap

## Roadmap Principles

The roadmap builds from reliable data and deterministic structure analysis toward explainable decision support. Each version must preserve automated test coverage, stable contracts, and the separation between market intelligence and live trade execution.

## Version 0.1 — Foundation

- FastAPI.
- Tests.
- GitHub/Codespaces.
- Market data provider abstraction.

**Exit criteria:** the service runs in a repeatable development environment, exposes a health check and analysis contract, normalizes provider data, and verifies foundational behavior with automated tests.

## Version 0.2 — Market Structure Engine

- HH/HL/LH/LL.
- BOS.
- CHOCH.
- Liquidity sweeps.
- Trend/range classification.

**Exit criteria:** structure events have precise definitions, typed results, configurable confirmation rules, deterministic fixtures, and focused unit tests.

## Version 0.3 — Multi-Timeframe Analysis

- Higher timeframe bias.
- Lower timeframe execution context.
- Timeframe alignment scoring.

**Exit criteria:** analysis distinguishes bias from execution context, represents conflicts explicitly, and produces a tested alignment score.

**Status:** implemented for the request's two timeframes. The engine exposes typed context, alignment categories, a `0–100` score, unified bias, reasons, and API-ready explanations. Expanding to a larger timeframe hierarchy remains outside v0.3.

## Version 0.4 — Decision Engine

- Weighted scoring.
- Confidence calculation.
- Evidence tracking.

**Exit criteria:** every decision is reproducible and carries a complete evidence ledger showing contributions, conflicts, and missing evidence.

**Status:** implemented. The main analysis path now uses the blueprint's weighted scoring model, typed evidence ledger, confidence thresholds, alignment and risk gates, invalidation notes, and backward-compatible API mapping.

## Version 0.5 — Strategy Engine

- Pullback continuation.
- Breakout continuation.
- Range reversal.
- Liquidity sweep reversal.
- Compression breakout.

**Exit criteria:** every strategy defines qualification, confirmation, invalidation, and risk rules and can be evaluated independently against historical fixtures.

## Version 1.0 — StructureIQ Platform

- Intelligence explanations.
- Trade journal.
- Backtesting.
- Dashboard/API-ready architecture.

**Exit criteria:** users can inspect an explainable analysis, review recorded decisions and outcomes, test strategies without look-ahead bias, and consume stable platform contracts through an API or dashboard.

## Beyond Version 1.0

Future work may improve data coverage, analytical depth, portfolio-level context, alerting, and user workflows. Any future execution integration must remain a separately designed, explicitly authorized system and must not compromise StructureIQ's identity as a market intelligence platform.
