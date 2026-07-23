# StructureIQ Architecture

## Calibration Analytics Boundary

`CalibrationAnalyticsEngine` reparses the append-only candidate diagnostics history for every requested projection. It owns no state, writes no files, and cannot call analysis or execution engines. Fixed distributions, overlapping funnels, rejection waterfalls, near-miss summaries, and grouped symbol/strategy/regime views feed only API and dashboard readers. System validation exercises both empty and populated temporary histories without touching operational diagnostics.

## Candidate Diagnostics Boundary

`CandidateDiagnosticsEngine` observes completed Live Market Monitor analyses after every authoritative engine has finished. It records emission, rejection, duplicate, and failure context, but its output is never consumed by analysis, decision, setup, strategy, risk, lifecycle, or brokerage paths. Persistence is append-only, and diagnostic write failures are isolated so they cannot alter monitor outcomes. Dashboard and validation layers read aggregate projections only.

## Local Launcher and Paper CLI Boundary

The launcher continues to bind Uvicorn to `0.0.0.0` so local interfaces remain reachable, but presents `localhost` URLs for browsers. Browser opening is opt-in and failure is non-blocking. Paper CLI mode starts a manageable local API process, validates it, and controls `ContinuousPaperTradingRuntime` exclusively through its existing API. Unit conversion, terminal rendering, and child-process lifecycle are launcher concerns; analysis, routing, risk, orchestration, and brokerage remain owned by their existing engines.

## Continuous Paper Trading Boundary

`ContinuousPaperTradingRuntime` is an opt-in scheduling and safety shell around `PaperTradingOrchestrator`. It does not duplicate monitoring, approval, lifecycle, brokerage, journaling, or reporting rules. Before cycles it consults `SystemHealthEngine`, `SystemValidationHarness`, and the Paper Brokerage risk status; configured failures pause the session without mutating production analysis. Events and session snapshots append locally. The runtime never auto-starts and has no live broker, GPT, email, or real-execution path.

The Runtime Session Manager adds optional wall-clock and completed-cycle limits to that shell. The earliest configured limit completes the session, signals the loop to stop, and records an immutable final summary. A completed session is distinct from a resumable safety pause and does not alter orchestrator behavior.

## System Validation Boundary

`SystemValidationHarness` is a test-oriented coordinator over health, configuration, storage, synthetic analysis, and paper-service readiness. Each timed component is exception-isolated, so failures are reported without aborting later checks. Analysis and orchestrator probes use deterministic in-memory candles and isolated temporary paper state. The harness never fetches external data, changes production configuration, or connects to brokers, GPT, email, or live execution. Completed results append to `reports/system_validation_history.jsonl` and feed read-only dashboard projections.

## System Health Boundary

`SystemHealthEngine` is a read-only observer over configured runtime services and local storage. It never polls providers, runs analysis, advances lifecycle state, or generates reports. Storage checks may create required directories and temporary write probes, which are immediately removed. Health snapshots append locally to `logs/system_health.jsonl`; no credentials, external APIs, brokers, or production behavior are involved.

## Daily Report Scheduler Boundary

`DailyReportScheduler` is a local clock-and-thread wrapper around `DailyReportEngine`. It is never auto-started by application import or launch. Scheduled and manual runs only request dated report generation; duplicate artifacts are skipped unless overwrite is explicit. History is append-only, repeated errors pause the worker, and no network, GPT, email, broker, analysis, or trading path exists.

## Paper Trading Orchestrator Boundary

`PaperTradingOrchestrator` coordinates existing paper services but owns none of their domain state. LiveMarketMonitor remains the candidate source, TradeLifecycleManager owns order transitions, PaperBrokerage owns positions and P/L, PaperTradeJournal owns journal views, and DailyReportEngine owns dated reports. Default cycles only observe candidates. Auto-approval requires explicit configuration and all safety gates. The background loop is opt-in, pauses after repeated errors, and has no real broker, network, GPT, email, or production decision path.

## Paper State Reconciliation Boundary

`PaperStateReconciliationEngine` is a read-only audit layer over PaperBrokerage, TradeLifecycleManager, PaperTradeJournal, DailyReportEngine, and PaperTradingOrchestrator recent actions. It explains expected drift between process-local state and persisted append-only journal history after restarts, and it flags critical contradictions such as duplicate IDs, impossible R values, or inconsistent P/L. It never repairs state, rebuilds positions, approves candidates, closes trades, changes risk, or affects any trading decision.

## Daily Report Boundary

`DailyReportEngine` is a pure read-side projection over journal, lifecycle, brokerage, monitor, calibration, readiness, and risk state. Report generation never invokes analysis, monitoring, order evaluation, or account mutation. Dated JSON artifacts are immutable unless overwrite is explicitly requested. GPT payload export is local structured data only; no model, email, network, or broker integration exists.

## Automated Paper Journal Boundary

`PaperTradeJournal` observes Paper Brokerage open/close notifications and Trade Lifecycle transitions. It never owns positions, balances, routing, or management. Every update appends a complete latest snapshot to JSONL; API reads reconstruct the newest record per trade. Observer failures are swallowed by the authoritative engines so journaling cannot roll back or modify paper actions. Exports are compact research artifacts for future daily reports and contain no secrets.

## Trade Lifecycle Manager Boundary

`TradeLifecycleManager` orchestrates monitor candidates and paper orders but delegates every simulated open, close, balance change, and P/L calculation to `PaperBrokerageEngine`. Manual approval is the default. Pending orders are evaluated only during explicit lifecycle cycles. Same-candle stop/target ambiguity closes at the stop conservatively. Break-even and trailing rules emit advisory states without altering brokerage levels. No lifecycle path connects to a real broker or production analysis.

## Paper Brokerage Boundary

`PaperBrokerageEngine` owns process-local simulated account and position state. It accepts positions only through explicit paper APIs, validates geometry and account risk, and never subscribes to monitor events automatically. A monitor candidate is marked used only after a successful simulated open. Optional JSON state contains no credentials. Dashboard readers observe paper metrics but cannot open or close positions. A future Trade Lifecycle Manager may orchestrate these interfaces without changing the brokerage contract.

## Live Market Monitor Boundary

`LiveMarketMonitor` wraps the existing provider and `AnalysisEngine`. It may poll synchronously or in an explicitly started daemon thread, but it cannot modify analysis or create trades. Only confirmed actionable buy/sell analyses become immutable `candidate` events. Process-lifetime keys prevent duplicate symbol/timeframe/candle/action/setup events; failures are isolated per market. Optional JSONL is append-only. Dashboard consumers observe state but cannot promote candidates.

## Realistic Execution Cost Modeling Boundary

`ExecutionCostModel` runs only after historical trade selection and outcome calculation. It translates bps assumptions into R using immutable entry/stop geometry, applies adverse costs, and emits a parallel realistic metric set. Baseline backtest and calibration metrics are never replaced. The dashboard reads the latest aggregate snapshot and cannot trigger modeling or alter production behavior.

## Setup Quality Intelligence Boundary

The research-only `SetupQualityEngine` observes already-computed structure, liquidity, confirmation, multi-timeframe, risk/reward, volatility, and freshness evidence. It emits a score and grade after setup selection and is never consumed by decision, setup, strategy, risk, execution, or readiness paths. Calibration aggregates immutable snapshots and the dashboard renders those aggregates. Its stable interface permits a future statistical or ML scorer without changing public response shapes.

## Architectural Goal

StructureIQ is evolving from a raw market-analysis API into a trader-facing decision-support platform. Its architecture separates deterministic market intelligence from the language and plans presented to a trader.

The separation protects three principles:

1. Internal engines remain testable, reproducible, and independent of presentation.
2. Trader-facing output remains traceable to structured evidence rather than invented narrative.
3. Decision support remains separate from broker execution and live trading.

## Application Launcher Boundary

Version 4.2 adds `start.py` as the official startup entry point. The launcher is outside the trading and research pipeline. It validates the local Python/runtime environment, confirms required project folders and configuration files, imports `app.main`, prints startup diagnostics, creates `logs/startup.log`, and delegates serving to uvicorn as a subprocess.

The launcher does not contain FastAPI route logic, domain scoring, calibration behavior, or trading rules. Its future sections for Paper Trading, Live Trading, Scheduler, AI Research, Broker Connections, and Web Dashboard are displayed as `NOT ENABLED` placeholders only.

## Research Dashboard Boundary

Version 4.3 adds a compact dashboard API above existing research artifacts. The dashboard reads the latest process-local calibration result, persisted symbol profiles, and continuous research snapshots. It converts those large research objects into overview, symbol, strategy, setup, readiness, risk, and recommendation summaries for review workflows.

The dashboard never runs calibration, backtesting, analysis, routing, setup selection, execution simulation, or confidence recalculation. If no calibration snapshot exists, it returns controlled unavailable summaries and uses persisted symbol profiles where possible. This makes the dashboard a reporting layer only, not a research or trading engine.

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

#### Continuous Research Engine

The v3.1 Continuous Research Engine observes completed calibration records after their production metrics have been finalized. It maintains a process-local, read-only history and builds cached reports for the latest 250, 500, or 1,000 closed trades, all-time records, or a custom closed-trade lookback. It ranks symbol, timeframe, setup, strategy, regime, confidence, Eastern-time hour, weekday, and cross-dimensional combinations.

The reporting store has no dependency path back into Decision, Setup, Strategy, Risk, Execution, Backtesting, or Calibration calculations. Refresh operations only replace cached research snapshots. The optional scheduler is explicitly started, daemonized, and disabled by default; v3.1 does not persist research state across process restarts.

#### Research Pipeline and Walk-Forward Intelligence

Version 3.2 adds a terminal research orchestrator that runs only after calibration, statistical research, and OOS validation objects are finalized. The pipeline consumes summaries and per-fold category performance; it cannot access or mutate live analysis state. Per-fold setup, strategy, and regime measurements are additive reporting snapshots derived from the same immutable training and validation trades.

Walk-Forward Intelligence measures expectancy decay, fold consistency and variance, drawdown and trade-frequency stability, confidence drift, and symbol/timeframe/setup/strategy/regime dependency. A deterministic scoring layer produces robustness and promotion-readiness labels. Sample size is a hard safety boundary: fewer than 100 validation trades cannot qualify for paper trading. Overfit risk and concentrated dependency apply explicit penalties.

Readiness output is advisory workflow metadata. No Decision, Setup, Strategy, Risk, Execution, Entry Timing, Trade Management, Backtesting, or Analysis component imports or reads pipeline output.

#### Monte Carlo Simulation Engine

Version 3.3 consumes copied realized-R sequences after calibration or OOS validation completes. It alternates deterministic order reshuffling and bootstrap sampling, then applies seeded skipped-trade stress and optional degradation sampled from existing execution diagnostics. It owns simulated equity, drawdown, streak, expectancy, profit-factor, ruin, and tail-probability reporting.

When both OOS research and Monte Carlo are enabled, only the aggregate risk summary may flow into the downstream promotion-readiness report. Elevated ruin risk or a high probability of drawdown beyond 20% can remove a readiness label. Monte Carlo never changes fold results, calibration metrics, trades, position sizing, or any production engine.

#### Monte Carlo Reporting and Risk Intelligence

Version 3.4 interprets immutable v3.3 simulation paths after simulation completes. It owns percentile and target reporting, categorical heatmaps, approximate expectancy intervals, Kelly research estimates, failure codes, and overall status. Peak R and balance are recorded separately from ending outcomes so target-hit probability is not confused with final profitability.

Only explicit report blockers may flow into downstream promotion readiness: insufficient validation sample, elevated ruin or 20% drawdown probability, non-positive 95% expectancy lower bound, or high ruin/tail heatmap risk. Kelly fractions and target probabilities have no path into Risk, Decision, Setup, Strategy, Execution, or Trade Management engines.

#### Advanced Statistical Validation

Version 3.5 consumes the chronological completed-R sequence and optional OOS fold expectancies after all production simulation is complete. It owns exact Bernoulli run-probability estimates, R buckets, gross-profit concentration, chronological expectancy thirds, edge-decay scoring, fold stability, outlier dependency, and named weakness flags.

Only severe weakness status may flow into promotion readiness. Negative recent expectancy, severe decay, over-80% top-decile profit concentration, poor folds, extreme losing streaks, or insufficient samples remove paper-trading readiness. The validator cannot change the source sequence, folds, calibration metrics, or production engines.

#### Centralized Evidence Scoring Engine

Version 3.6 runs after authoritative analysis engines complete. It reads Market Structure, Multi-Timeframe, Regime, Decision, Setup, Strategy, risk/reward, confirmation, and execution-readiness results and produces a normalized transparent score. Optional research pipeline, statistical validation, and Monte Carlo reports extend calibration scoring only when available.

The scoring dependency is one-way: Analysis and Calibration call ScoreEngine after their authoritative outputs exist; Decision, Setup, Strategy, Risk, Execution, and Trade Management never import or read `ScoreSummary`. Historical backtests retain score snapshots as non-serialized research metadata so aggregation cannot change their trade outcomes.

#### Execution Intelligence Layer

Version 3.7 runs after action, setup, strategy, entry, stop, and target are finalized. It assesses execution coherence, confirmation, level completeness, R:R, and preferred advisory timing style. No-trade output is always avoidance guidance; valid setups may receive market, retest, confirmation-close, or pullback-wait explanations.

Backtests retain advisory snapshots as non-serialized research metadata. Calibration aggregates them and may append findings from MFE/MAE diagnostics, Entry Timing Laboratory, Trade Management Laboratory, Monte Carlo, and Advanced Statistical Validation. Neither live nor aggregate guidance is consumed by any production engine.

#### Confidence Calibration Engine

Version 3.8 reads the finalized Decision Engine confidence after action and gate evaluation. Live analysis has no historical outcome sample and therefore returns an explicit identity mapping. Calibration groups completed trade outcomes into fixed raw-confidence buckets and estimates empirical win probability only when at least 20 observations exist.

The calibrated value is a parallel research field. Decision, Setup, Strategy, Risk, Execution, and Trade Management never import or consume it. Reliability is graded independently by bucket sample size, and sparse buckets preserve the original score.

#### Strategy Rating Engine

Version 3.9 runs after Statistical Research, optional OOS validation, confidence calibration, and weakness analysis complete. It grades only observed historical setup and strategy categories using rich research rows and category-level fold consistency. Global overfit and statistical failures may penalize grades.

Live analysis cannot access the calibration research store, so it returns unavailable named ratings. Calibration ratings cannot promote, demote, select, suppress, or reroute any category; no production engine imports rating output.

#### Adaptive Symbol Profile Engine

Version 4.0 owns a durable local observation store containing only completed calibration trade facts: symbol, timestamp, outcome, realized R, confidence, setup, strategy, and regime. On every calibration it appends new observations, rebuilds deterministic symbol/category statistics, and delegates category grades to Strategy Rating Engine.

#### Adaptive Strategy Router Laboratory

Version 4.1 compares the already-selected production setup/strategy with persisted symbol preferences. It is downstream of routing: calibration compares finalized records after profiles update, and analysis exposes read-only diagnostics. No output flows into Decision, Setup, Strategy, Risk, or Execution engines.

Analysis has read-only access to the resulting profile view. The profile is constructed after historical calibration and has no dependency path into Market Structure, Decision, Setup, Strategy, Confidence, Risk, Execution, or Trade Management. Persistence uses an atomic local JSON replacement and preserves previous observations across service restarts.

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
| What combinations are currently strongest or weakest across rolling history? | Continuous Research Engine |
| Is an OOS result stable and sufficiently sampled for further research review? | Research Pipeline and Walk-Forward Intelligence |
| How sensitive are completed results to trade order, sampling, and tail drawdown? | Monte Carlo Simulation Engine |
| How should simulation tails, targets, confidence, and sizing uncertainty be interpreted? | Monte Carlo Reporting and Risk Intelligence |
| Is aggregate profit hiding decay, concentration, outliers, or unstable loss sequences? | Advanced Statistical Validation |
| How strong is the combined evidence, and which categories raise or lower quality? | Centralized Evidence Scoring Engine |
| How could an already-valid setup be executed, and what execution risks remain? | Execution Intelligence Layer |
| How closely do raw confidence scores match historical win probabilities? | Confidence Calibration Engine |
| Which historical setups and strategies appear strongest, weakest, or under-tested? | Strategy Rating Engine |
| How has each symbol behaved historically, and which rated categories fit it best? | Adaptive Symbol Profile Engine |
| How should the local application validate and start? | Application Launcher |
| How can existing research be reviewed without inspecting full calibration JSON? | Research Dashboard API |
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

Versions 0.1 through 4.3 provide the FastAPI foundation, provider abstraction and symbol normalization, typed structure and timeframe analysis, weighted decisions, setup and strategy qualification, trader-facing explanations, journaling, deterministic historical evaluation, calibration diagnostics, execution and timing laboratories, market-regime research, independent validation, automatic statistical research, durable symbol profiles, adaptive-route diagnostics, an official startup launcher, and compact research dashboard endpoints. StructureIQ remains decision-support and research software; none of these layers connect to a broker or place trades.
