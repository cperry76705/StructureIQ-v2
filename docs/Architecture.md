# StructureIQ Architecture

## Architectural Goal

StructureIQ is evolving from a raw market-analysis API into a trader-facing decision-support platform. Its architecture separates deterministic market intelligence from the language and plans presented to a trader.

The separation protects three principles:

1. Internal engines remain testable, reproducible, and independent of presentation.
2. Trader-facing output remains traceable to structured evidence rather than invented narrative.
3. Decision support remains separate from broker execution and live trading.

## Output Boundaries

### Internal Engine Output

Internal output is machine-readable domain state produced by focused engines. It includes:

- Raw market structure, confirmed swings, BOS, CHOCH, sweeps, trend, and phase.
- Multi-timeframe alignment, alignment score, and directional context.
- Weighted decision scoring and action.
- Positive, negative, and neutral evidence.
- Setup qualification, failed conditions, and invalidation levels.
- Strategy and playbook comparisons.

Internal output favors precision, provenance, and completeness. It may contain implementation-oriented fields that are useful for testing, APIs, journals, and backtesting but are too detailed for a trader's primary view.

### Trader-Facing Analysis Output

Trader-facing output translates the internal state into a concise decision-support experience. It includes:

- A plain-English market summary.
- The recommended setup, or an explicit statement that no setup qualifies.
- Entry conditions that must become true before action.
- Structural invalidation.
- Risk and volatility notes.
- Clear wait or avoid reasoning.
- A checklist-style trade plan.

Trader-facing output does not replace or mutate engine conclusions. Every statement and checklist item must be traceable to internal output.

## Processing Flow

```text
Market Data Engine
    -> Market Structure Engine
    -> Multi-Timeframe Engine + Indicator Framework
    -> Decision Engine
    -> Setup Engine
    -> Strategy Engine
    -> Analysis/Explanation Engine
    -> Trader-Facing Analysis Output
             |
             +-> API / Future UI

Internal outputs from every stage
    -> Journal/Backtesting Engine
```

The numbered components below describe architectural responsibilities. At runtime, the Analysis/Explanation Engine is the presentation boundary and consumes all internal results required for the final plan, including setup and strategy output.

## Components

### 1. Market Data Engine

The Market Data Engine retrieves, validates, and normalizes candles and related market data into stable internal models. It owns provider abstraction, timeframe requests, chronological ordering, data-quality checks, and informative provider failures.

Provider-specific representations must not leak into analytical engines. Missing, stale, or invalid data is reported explicitly rather than converted into false evidence.

The v0.9 symbol-normalization boundary preserves user-facing symbols while translating known forex pairs into Yahoo-specific identifiers. Unknown symbols pass through safely, and analytical/API outputs retain the requested symbol.

### 2. Market Structure Engine

The Market Structure Engine identifies confirmed swing highs and lows, HH/HL/LH/LL relationships, BOS, CHOCH, liquidity sweeps, and structural phases. It classifies trend as bullish, bearish, ranging, or unclear and returns both conclusions and timestamped supporting events.

Market structure establishes the primary thesis. It does not choose a trade setup or write trader-facing guidance.

### 3. Multi-Timeframe Engine

The Multi-Timeframe Engine relates higher-timeframe directional context to current-timeframe execution structure. It returns aligned bullish, aligned bearish, mixed, conflicting, or unclear alignment; a `0–100` alignment score; unified directional bias; reasons; and a structured summary.

The current implementation evaluates exactly the `higher_timeframe` and `timeframe` supplied to `/analysis`. Its contracts allow a broader hierarchy later without requiring it now.

### 4. Indicator Framework

The Indicator Framework calculates standardized indicator observations and interprets whether they confirm, weaken, or remain neutral toward the market-structure thesis. Indicators never create the primary thesis independently.

Indicator results are evidence inputs. They do not select setups or actions.

### 5. Decision Engine

The Decision Engine determines directional action and confidence using weighted evidence. It answers one question: should the current evidence produce `buy`, `sell`, `wait`, or `avoid`?

It applies the blueprint's `35/25/15/15/10` weighting across market structure, multi-timeframe alignment, support/resistance and liquidity, indicators, and risk/reward and volatility. Its output includes the action, confidence, score breakdown, evidence ledger, risk notes, invalidation notes, and a factual summary.

The Decision Engine does not name a setup, choose a broader playbook, or build the trader-facing plan.

### 6. Setup Engine

The Setup Engine identifies the specific trade setup type and validates whether its required conditions are present. Initial setup families include:

- Bullish BOS retest.
- Bearish BOS retest.
- Pullback continuation.
- Range reversal.
- Liquidity sweep reversal.
- Compression breakout.

It returns a typed setup plan containing setup type and status, direction, quality score, entry and risk levels, checklist conditions, invalidation rules, evidence, warnings, and explanation. A directional decision does not imply that a setup is ready; the Setup Engine may reject or defer every candidate.

The v0.5 engine is the primary setup-planning path for `/analysis`. The earlier strategy router remains compatibility code and does not own current setup qualification.

### 7. Analysis/Explanation Engine

The Analysis/Explanation Engine converts internal engine output into trader-facing language and structured plans. It does not make the decision itself.

It explains the Decision Engine result, presents the recommended qualified setup, describes entry and invalidation conditions, summarizes risk, explains wait or avoid outcomes, and builds a checklist-style trade plan. It must preserve uncertainty and cite only supplied engine evidence.

The v0.6 implementation is the trader-facing boundary for `/analysis`. It maps existing Decision and Setup results into typed narratives, recommendations, risks, confidence language, next actions, and trade plans. It does not contain decision thresholds or setup qualification rules.

### 8. Strategy Engine

The Strategy Engine selects broader playbooks and compares possible approaches based on current market conditions. It comes after Setup Engine qualification, not before it.

For example, it may compare continuation and reversal playbooks when multiple setup candidates exist, rank valid approaches, or recommend observation when no playbook has sufficient edge. It cannot override a Decision Engine action or make an invalid setup valid.

The v0.7 implementation evaluates trend continuation, pullback continuation, breakout continuation, range reversal, liquidity-sweep reversal, and compression breakout. It returns ranked candidates with structured fit scores and evidence before the Analysis/Explanation Engine produces trader-facing language.

### 9. Journal/Backtesting Engine

The Journal/Backtesting Engine records market snapshots, engine versions, decisions, setup qualifications, plans, user actions, and outcomes. It applies the same deterministic analytical rules to historical data while guarding against look-ahead bias.

Backtesting must disclose data quality, fees, slippage, execution assumptions, and sample size. Historical performance is evidence about past behavior, not a future guarantee.

The v0.8 implementation stores journal records in a local append-only JSONL file and provides a deterministic historical candle-window runner. Non-actionable analyses are retained as skipped records, while actionable plans use first-touch stop/target simulation and R-based metrics. The implementation explicitly reports its execution-model limitations.

#### Execution Realism Engine

Version 2.1 adds a backtesting-only execution boundary after an actionable plan is produced. An optional `ExecutionProfile` models adverse spread and slippage, commissions, immediate/next-bar/touch fills, and deterministic partial-fill studies. It never feeds results back into analysis, decision confidence, setup selection, strategy ranking, stops, or targets.

Each modeled fill retains the perfect-execution result as a comparator. Execution diagnostics and summaries report requested versus actual entry and expectancy degradation. Seeded random slippage is reproducible; OHLC ordering, latency, order-book depth, and market impact remain explicit limitations.

#### Execution Sensitivity Laboratory

Version 2.2 runs isolated and combined execution profiles over a frozen calibration candle snapshot. A perfect profile is always the baseline. Laboratory results are stored separately from ordinary calibration runs, metrics, setup/strategy performance, and recommendations, so scenario analysis cannot mutate the production research result.

The laboratory ranks profile expectancy and drawdown, measures reductions from perfect execution, and classifies profile settings as spread, slippage, commission, fill model, or combined costs. Profile names are descriptive only; attribution comes from typed settings. Default Forex and Crypto helpers are illustrative scenario generators rather than market-cost assertions.

#### Entry Timing Laboratory

Version 2.3 inserts an alternative-entry research stage before optional execution costs. It replays only candidates that already passed production actionability, level, confirmation, and R:R gates. Timing may move the entry or leave it unfilled, but the original stop, target, decision, setup, and strategy remain immutable.

Every profile receives the same cached candles and candidate count. The laboratory tracks adjusted-entry R, delay, misses, production-winning opportunities missed, and structural-level fallbacks. Timing summaries are isolated from ordinary backtest and calibration metrics. OHLC candles cannot establish intrabar touch order, so same-candle ambiguity remains conservative.

#### Market Regime Laboratory

Version 2.4 classifies each analysis in parallel with production engines. It uses existing trend, phase, swing structure, BOS/CHOCH, range contraction or expansion, ATR, recent range behavior, momentum, and timeframe alignment. One exclusive regime, confidence score, reasons, and summary are emitted; no regime label is consumed by production routing.

When requested, calibration groups immutable backtest snapshots by regime and builds strategy and setup cross-matrices. The laboratory reports all regime categories, including empty ones, and treats small samples as insufficient evidence. Recommendations are observations only and cannot tune or suppress a strategy.

#### Regime Validation Laboratory

Version 2.5 validates existing regime labels without changing them. Backtesting captures compact forward observations at 5, 10, and 20 bars from the same cached candle windows. Validation measures distribution, confidence, persistence, transition exits, forward behavior, and predicted-versus-proxy counts.

Forward proxy regimes use deterministic return and range-shape rules. They are not human labels, ground truth, ML targets, or production routing inputs. The validator reports missing horizons and explicitly separates imbalance, label noise, and forward mismatch.

#### Regime Classifier Tuning Laboratory

Version 2.6 records a non-serialized evidence snapshot beside each historical regime result. The snapshot captures competing trend, range, transition, compression, and expansion scores; BOS/CHOCH existence and recency; swing direction; timeframe alignment; conflict; and production confidence. It is available only to backtesting and calibration research and is excluded from `/analysis` and `/backtest` response payloads.

The tuning laboratory explains transition precedence, classification margins, confidence clustering, stale transition evidence, and forward-proxy stability. It then reclassifies copied scores under transition thresholds `60`, `65`, `70`, `75`, and `80`, plus isolated BOS, CHOCH, swing-structure, and higher-timeframe alignment weight boosts. These counterfactual labels never replace the immutable production label or feed any trading engine.

#### Tuned Regime Classifier

Version 2.7 adds a second, research-only classifier beside the unchanged legacy classifier. The tuned classifier preserves compression, expansion, and range rules, then gives current directional swing structure primary weight. Only recent BOS/CHOCH events are eligible for confirmation or transition pressure; old CHOCH observations cannot preempt a current directional sequence. Higher-timeframe alignment and directionally consistent mixed context strengthen trend evidence.

Both labels are retained internally on the same analysis and backtest record. Calibration can group immutable records through a legacy view, tuned view, or side-by-side comparison. Neither label is read by Decision, Setup, Strategy, Explanation, entry, execution, or risk code.

#### Tuned Regime Forward Validation

Version 2.8 captures a second non-serialized forward snapshot containing returns, upside/downside excursions, volatility shape, range containment, and a deterministic proxy regime at 5, 10, and 20 bars. Compare-mode calibration evaluates the legacy and tuned labels against that single shared snapshot.

Validation is downstream of completed backtest records. It cannot recalculate analyses, mutate labels, select trades, or replace ordinary metrics. The validation module owns proxy scoring, uncertainty statistics, confusion matrices, reliability curves, persistence, and classifier comparison; its observations remain absent from `/analysis` and `/backtest` contracts.

#### Regime Confidence Calibration Laboratory

Version 2.9 consumes the matched correctness outcomes produced by forward validation and compares them with the original legacy and tuned confidence values. It owns reliability buckets, ECE, MCE, Brier score, confidence distributions, overconfidence diagnosis, and research-only mapping simulations.

Calibration mappings operate on copied numeric confidence arrays after classifications and trades are complete. They cannot update `RegimeResult`, analysis responses, backtest records, routing inputs, or trading metrics. This separation keeps confidence calibration observational even when a simulated mapping appears materially better.

#### Out-of-Sample Validation Laboratory

Version 3.0 adds a research orchestrator above the unchanged Backtesting Engine. It partitions raw candle histories chronologically, creates a fresh bounded provider and backtester for every training and validation segment, and aggregates only completed result objects after each independent run.

Validation segments may read prior raw candles for the same 49-bar warm-up required by production analysis, but never reuse training decisions, setup plans, confidence results, or trades. Generalization, stability, dependency, and overfitting diagnostics are downstream reports and have no path back into production engines.

#### Statistical Research Laboratory

Version 3.1 adds an automatic terminal aggregation stage after ordinary calibration and all requested optional laboratories complete. It reads immutable backtest records and existing management, entry-timing, and execution-profile summaries; it never initiates or modifies a production engine.

The laboratory owns category normalization, uncertainty estimates, sample-quality rules, time buckets, cross-dimensional matrices, rankings, concentration checks, and executive research language. Empty standard categories and future observed categories share the same typed contracts, keeping coverage explicit and extensible.

### Validation and Calibration Layer

The v0.9 Calibration Engine is a cross-cutting observation layer over the Backtesting Engine. It runs historical evaluation across requested symbol and timeframe combinations, aggregates behavior, groups setup and strategy performance, and reports possible conservatism, aggressiveness, or data-quality concerns.

Calibration cannot mutate Decision Engine weights, Setup Engine thresholds, Strategy Engine rankings, or risk rules. Recommendations are inspection prompts for maintainers, not automatic optimization.

## Ownership Rules

| Question | Owning component |
| --- | --- |
| What is price doing? | Market Structure Engine |
| Do the timeframes agree? | Multi-Timeframe Engine |
| Do indicators confirm the thesis? | Indicator Framework |
| Buy, sell, wait, or avoid—and with what confidence? | Decision Engine |
| Which specific setup is present and valid? | Setup Engine |
| Which broader playbook is most appropriate? | Strategy Engine |
| How should the result be explained and presented as a plan? | Analysis/Explanation Engine |
| How did the analysis and outcome perform over time? | Journal/Backtesting Engine |
| How sensitive is historical performance to fill and cost assumptions? | Execution Realism Engine |
| Which execution variable causes the largest historical degradation? | Execution Sensitivity Laboratory |
| Does a better or later entry improve expectancy enough to justify missed trades? | Entry Timing Laboratory |
| Which setup and strategy historically fit each market condition? | Market Regime Laboratory |
| Are regime labels balanced, persistent, and aligned with forward proxy behavior? | Regime Validation Laboratory |
| Why does transition dominate, and which controlled tuning hypothesis merits study? | Regime Classifier Tuning Laboratory |
| How do legacy and tuned labels differ over identical records? | Tuned Regime Classifier comparison |
| Which classifier better matches shared future-behavior proxies? | Tuned Regime Forward Validation |
| Are regime confidence values reliable, and which mapping merits further research? | Regime Confidence Calibration Laboratory |
| Does sampled system performance survive completely unseen chronological data? | Out-of-Sample Validation Laboratory |
| Why does sampled performance vary across symbols, setups, regimes, time, and execution assumptions? | Statistical Research Laboratory |

## Shared Architectural Rules

- Engines communicate through validated, typed contracts.
- Conclusions retain their evidence, configuration, timeframe, and rule version.
- Missing evidence lowers certainty; it is never silently treated as confirmation.
- The API coordinates components but does not contain domain scoring or explanation logic.
- The explanation layer cannot invent evidence, alter scores, or upgrade a setup.
- Wait and avoid are successful analytical outcomes, not system failures.
- New fields are introduced additively or through explicit API versioning.
- No core component places orders or manages brokerage accounts.

## Current Platform State

Versions 0.1 through 3.1 provide the FastAPI foundation, provider abstraction and symbol normalization, typed structure and timeframe analysis, weighted decisions, setup and strategy qualification, trader-facing explanations, journaling, deterministic historical evaluation, calibration diagnostics, execution and timing laboratories, market-regime research, independent validation, and automatic statistical research. StructureIQ remains decision-support and research software; none of these layers connect to a broker or place trades.
