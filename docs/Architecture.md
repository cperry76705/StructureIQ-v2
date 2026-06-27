# StructureIQ Architecture

## Architectural Goal

StructureIQ uses a modular, API-first architecture in which market observations move through focused analytical engines. Each engine has a narrow responsibility, explicit inputs and outputs, and independent tests. This separation allows data providers, analytical methods, and strategies to evolve without coupling the platform to live order execution.

## Analysis Flow

```text
Market Data
    -> Market Structure
    -> Multi-Timeframe Context
    -> Indicator and Context Evidence
    -> Decision Model
    -> Strategy Qualification
    -> Intelligence and Explanation
    -> API / Journal / Backtesting Consumers
```

The flow is analytical rather than transactional. No component in the core blueprint submits or manages broker orders.

## Engines

### 1. Market Data Engine

The Market Data Engine retrieves and normalizes candles and related market data from provider-specific formats into stable internal models. It owns provider abstraction, timeframe requests, validation, error handling, and data-quality checks.

Provider adapters must not leak provider-specific representations into downstream engines. Missing, stale, or invalid data must be surfaced explicitly rather than silently treated as valid evidence.

### 2. Market Structure Engine

The Market Structure Engine derives objective price behavior from normalized candles. It identifies confirmed swings, HH/HL/LH/LL sequences, BOS, CHOCH, liquidity sweeps, and structural phases such as impulse, pullback, range, compression, and expansion.

Its output is a typed structural snapshot with events, relevant levels, trend or range classification, and the evidence used to reach that classification.

### 3. Multi-Timeframe Engine

The Multi-Timeframe Engine relates higher-timeframe bias to lower-timeframe execution context. It determines whether timeframes are aligned, conflicting, or neutral and calculates an alignment score without allowing a lower timeframe to erase material higher-timeframe risk.

The v0.3 implementation evaluates exactly two inputs from the existing analysis request:

- `higher_timeframe` supplies directional bias and broad context.
- `timeframe` supplies current execution context.

Each side is represented by a typed `TimeframeAnalysis` derived from the Market Structure Engine. The resulting `MultiTimeframeResult` records both trends and phases, an alignment category, a `0–100` alignment score, unified directional bias, reasons, and a human-readable summary.

Alignment is directional agreement, not prediction. Matching impulse structures receive strong alignment; an in-direction current pullback or range remains mixed within the higher-timeframe bias; opposite directional structures conflict; and unclear structure reduces the score. Strategy qualification and confidence consume this result without changing the underlying structure observations.

The engine accepts named timeframe inputs rather than hard-coding a hierarchy, leaving room for a later multi-level implementation while deliberately limiting v0.3 to two timeframes.

### 4. Indicator Framework

The Indicator Framework calculates standardized indicator observations and translates them into evidence that confirms, weakens, or remains neutral toward the structure-led thesis. Indicators never create the primary thesis independently.

### 5. Decision Engine

The Decision Engine combines weighted evidence across market structure, multi-timeframe alignment, support/resistance and liquidity, indicators, and risk/reward and volatility. It produces a normalized score, confidence, evidence ledger, conflicts, and a decision state such as buy, sell, wait, or no trade.

The v0.4 implementation is a dedicated domain engine independent of FastAPI. It consumes typed market-structure and multi-timeframe results plus normalized context inputs. `ScoreBreakdown` enforces the blueprint's `35/25/15/15/10` weighting, while `EvidenceItem` separates supportive, adverse, and neutral observations. Risk and invalidation notes remain first-class output rather than being reconstructed in the API layer.

Action selection occurs after scoring. Confidence thresholds, alignment agreement, current-timeframe confirmation, and minimum risk/reward act as explicit gates. The analysis orchestrator maps the result into both the new nested decision contract and the legacy top-level action and confidence fields; it does not maintain a second decision algorithm.

### 6. Strategy Engine

The Strategy Engine determines whether current conditions satisfy a named, rule-based setup. Initial strategy families are pullback continuation, breakout continuation, range reversal, liquidity sweep reversal, and compression breakout.

Strategies consume analytical state; they do not modify it to force qualification. Each setup must define prerequisites, confirmation, invalidation, and risk constraints.

### 7. Intelligence/Explanation Engine

The Intelligence/Explanation Engine converts structured analytical output into concise, human-readable reasoning. It must distinguish observation from interpretation, identify conflicting evidence, state why confidence is high or low, and describe confirmation and invalidation conditions.

Explanations must be traceable to engine outputs. They must not invent evidence or present probabilistic conclusions as certainty.

### 8. Journal/Backtesting Engine

The Journal/Backtesting Engine records analysis snapshots, decisions, setup metadata, outcomes, and review notes. It applies the same deterministic analytical and strategy rules to historical data to measure behavior across market regimes.

Backtesting results must account for data quality, fees, slippage assumptions, and look-ahead bias. Historical performance is evidence about past behavior, not a guarantee of future results.

## Shared Architectural Rules

- Engines communicate through validated, typed contracts.
- Engine outputs contain both conclusions and supporting evidence.
- Configuration, thresholds, and model versions are recorded for reproducibility.
- Market data providers are replaceable through dependency injection.
- Analytical engines remain independent of FastAPI and external delivery channels.
- The API coordinates engines but does not contain domain logic.
- Failures are explicit and observable; ambiguous data produces uncertainty, not fabricated precision.
- New functionality preserves backward compatibility unless a versioned contract intentionally changes it.

## Current Platform State

The current application provides a FastAPI service, a market data provider abstraction, normalized candle data, typed market structure analysis, two-timeframe alignment, a weighted decision engine, strategy setup routing, and tests. The blueprint describes the intended boundaries as these capabilities mature into independently versioned engines.
