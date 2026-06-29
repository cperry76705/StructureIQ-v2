# Validation and Calibration

## Purpose

StructureIQ provides deterministic tools for observing whether current decision thresholds, setup qualification, strategy ranking, and risk assumptions appear too conservative, too aggressive, or reasonably balanced over historical samples. Version 1.1 explains why records fail to become actionable before any threshold is changed.

Calibration is diagnostic. It produces recommendations for human inspection and never changes scoring weights, thresholds, setup rules, or strategy rankings automatically.

## Symbol Normalization

User-facing symbols remain stable in API requests and responses while the market data provider receives its required format. The Yahoo adapter applies these mappings:

| User symbol | Yahoo symbol |
| --- | --- |
| `BTC-USD` | `BTC-USD` |
| `ETH-USD` | `ETH-USD` |
| `EUR-USD` | `EURUSD=X` |
| `GBP-USD` | `GBPUSD=X` |
| `USD-JPY` | `USDJPY=X` |
| `AUD-USD` | `AUDUSD=X` |
| `USD-CAD` | `USDCAD=X` |
| `USD-CHF` | `USDCHF=X` |
| `NZD-USD` | `NZDUSD=X` |

Already normalized Yahoo symbols remain unchanged. Unknown symbols are trimmed, uppercased, and passed through safely.

## Calibration Request

`CalibrationRequest` contains:

- One or more user-facing symbols.
- Current timeframes.
- Higher timeframes.
- Historical lookback.
- Maximum records per backtest run.
- Risk-per-trade percentage.
- Starting balance.

The engine evaluates the Cartesian product of symbols, timeframes, and higher timeframes. Requests are limited to 100 combinations to keep the synchronous foundation bounded and testable.

## Calibration Runs

Each `CalibrationRun` records:

- User-requested and normalized symbol.
- Current and higher timeframe.
- Total backtest records.
- Skipped and open record counts.
- Backtest metrics and summary.

Every run delegates to the existing Backtesting Engine. Calibration does not introduce a second simulation model.

## Aggregate Metrics

`CalibrationMetrics` reports:

- Total runs, closed trades, and skipped records.
- Wins, losses, and breakeven trades.
- Win rate, average R, and total R.
- Profit factor.
- Maximum drawdown in R.

Metrics use the same deterministic definitions as v0.8 backtesting.

## Aggregate Skip Diagnostics

`CalibrationResult.aggregate_skip_diagnostics` combines primary skip causes from every run. It reports total skipped records, counts by reason code, counts by blocking engine, the most common reason, and a readable summary.

Each skipped record receives one primary cause according to the current authority chain. For example, a `wait` decision is attributed to the Decision Engine even if downstream setup and plan output are also non-actionable. A directional decision with a developing setup is attributed to setup confirmation. This prevents one historical window from being counted as several independent failures.

The breakdown answers two distinct questions:

- **Reason code:** which condition prevented actionability?
- **Blocking engine:** which engine owns the condition that should be inspected?

## Aggregate Decision Diagnostics

`CalibrationResult.aggregate_decision_diagnostics` combines Decision Engine snapshots from all backtest windows. It reports counts by confidence band and failed required gate, average final confidence, average raw score, the most common blocked gate, and a readable summary.

Failed-gate counts can overlap because one decision may fail several required conditions. In v1.3 the Decision Engine aggregation covers directional confidence, structure agreement, and timeframe agreement. Risk-plan availability and quality remain visible as non-required gate observations, while final failures appear in engine-level skip diagnostics under Setup or risk ownership.

This separation makes bottleneck movement measurable: if directional evidence clears but execution data is incomplete, `by_blocking_engine` should shift from `decision_engine` toward `setup_engine` or `risk_engine`. Recommendations then distinguish confidence-distribution research from level derivation or execution-quality work.

## Decision Threshold Sensitivity Study

Version 1.4 evaluates confidence thresholds `50`, `55`, `60`, `65`, and `70` over the immutable snapshots already collected by backtesting. It does not rerun the Decision Engine, alter stored actions, upgrade setup states, or change the production threshold.

A record is directionally eligible when its raw decision score reaches the studied threshold, its intended direction is bullish or bearish, and its structure and multi-timeframe gates passed. Execution readiness is evaluated separately from the recorded downstream snapshot and requires:

- Confirmed setup and actionable trader plan.
- Parseable entry, stop, and target.
- Estimated risk/reward of at least `1.5R`.
- A preferred strategy that does not conflict with the decision.

`ThresholdSensitivityResult` reports directional eligibility, total observed execution-ready snapshots, their intersection as estimated trade candidates, records still directionally blocked, and execution blockers split into missing setup, missing levels, failed risk/reward, unconfirmed setup, and strategy misalignment.

Execution-ready is intentionally independent of the tested threshold; `estimated_trade_candidates` is the intersection that passes both tests. Because downstream snapshots retain their original state, this study is conservative and does not assume a waiting setup would automatically become confirmed after a hypothetical decision change.

## Aggregate Risk/Reward and Level Diagnostics

Version 1.5 combines every backtest record into `aggregate_risk_reward_summary` and `aggregate_setup_level_summary`. Diagnostics run for skipped records, so the distribution describes the full calibration sample rather than only executed trades.

The risk summary includes missing entry, stop, and target counts; invalid geometry; below-minimum R; average and median calculated R; records between `1.2R` and `1.5R`; records at or above `1.5R`; counts by failure reason; and the most common failure.

Recommendations map dominant evidence to the owning component:

- Missing or partial levels: level generation and support/resistance inputs.
- Invalid geometry: support/resistance selection and directional ordering.
- `target_too_close`: target-selection review.
- `stop_too_wide`: structural stop-placement review.
- Material `1.2R–1.5R` clustering: a controlled minimum-R sensitivity study, not an automatic threshold reduction.
- Complete risk plans that remain unconfirmed: setup-confirmation rule review.

Version 1.6 replaces the former fixed 25-point zone floor and zero-decimal level formatting with instrument-aware metadata, ATR/percentage zone scaling, and symbol precision. Calibration summaries therefore measure the corrected numeric geometry while retaining every v1.5 execution and confirmation rule.

## Aggregate Trade Outcome Diagnostics

Version 1.7 combines executed-trade diagnostics into `aggregate_outcome_diagnostics`. It reports wins and losses, average bars to resolution, average MFE and MAE in R, counts by loss reason, same-candle ambiguity, immediate stops, and no-follow-through losses.

Recommendations remain observational:

- Immediate stops prioritize entry timing and confirmation review.
- No follow-through prioritizes confirmation quality.
- Wrong direction prioritizes market-structure and multi-timeframe review.
- Same-candle ambiguity prioritizes finer-grained data rather than rule changes.
- High MFE before eventual stop identifies cases worth inspecting for structural stop placement, without automatically widening stops.

## Aggregate Trade-Management Sensitivity

Version 1.8 returns `aggregate_trade_management_sensitivity`, calculated over all closed executed trades across calibration runs. Each rule reports simulated wins, losses, breakeven outcomes, average and total R, profit factor, maximum drawdown, and whether it improves on the unchanged baseline.

Calibration recommends only the highest-total-R improving rule and explicitly requires a larger out-of-sample sample before production consideration. The study does not mutate journal entries, backtest outcomes, setup plans, stops, targets, or production metrics.

## Setup and Strategy Performance

Closed and skipped records are grouped by `setup_type` and `strategy_type`. Each group reports record count, closed trade count, skipped count, outcomes, win rate, average R, total R, and profit factor.

These groups identify areas for investigation. A weak result does not prove that a setup or strategy is inherently invalid, especially when sample size is small.

## Recommendations

Recommendations contain category, message, severity, and suggested action. Categories are:

- `decision_threshold`
- `setup_quality`
- `strategy_selection`
- `risk_reward`
- `market_structure`
- `data_quality`

The v0.9 rules flag:

- No actionable closed trades across multiple runs.
- Very high skipped-record rates.
- Low win rate.
- Negative average R.
- Profit factor below one.
- High R drawdown.
- Setup or strategy groups with negative average R.
- Missing evaluable records.
- Dominant actionability skip reasons and their owning gates.

Recommendations now compare the lowest studied threshold with production. If lower thresholds add directional records but no estimated executable candidates, calibration identifies the dominant execution blocker and explicitly states that the study does not justify lowering confidence. If candidate counts increase, it recommends out-of-sample validation rather than changing production automatically.

## Determinism

Given the same provider candles, engine versions, request, and configuration, calibration returns the same runs, aggregates, group performance, and recommendations.

## Limitations

- Calibration inherits all simplified backtesting limitations.
- Small or homogeneous samples can produce unstable conclusions.
- The first thresholds are transparent heuristics, not statistically fitted boundaries.
- Provider history and symbol support vary by instrument and timeframe.
- Multiple comparisons can make isolated weak groups appear more meaningful than they are.
- There are no confidence intervals, significance tests, walk-forward splits, or out-of-sample validation yet.
- Calibration observes historical behavior and does not prove profitability.

## v1.9 Setup Coverage

`aggregate_setup_coverage_summary` combines candidate snapshots from all records. It reports selected, candidate, executable, and missed-executable counts plus per-family appearances, selections, executable counts, average quality, average calculated R, and dominant blockers.

If only one family produces executable candidates, the summary names it. Recommendations prioritize missed executable candidates, then candidate quality and frequency. They identify one family for inspection but do not change selection, thresholds, confirmation, or execution.

## v2.0 Bearish BOS Contribution

Calibration now states whether `bearish_bos_retest` produced closed production trades, only executable candidates, or neither. Compare its selection count, outcomes, total R, missed candidates, and blockers with `liquidity_sweep_reversal_short`; contribution alone does not justify further expansion.

## v2.1 Aggregate Execution Summary

Calibration accepts the same optional `execution_profile` and passes it unchanged into every backtest run. `aggregate_execution_summary` combines modeled fills and reports average spread, slippage, commission, degradation, perfect baseline expectancy, realistic expectancy, and expectancy reduction.

The comparison is observational. It does not recalibrate confidence, setups, strategies, stops, targets, or the `1.5R` admission gate. Random slippage remains deterministic for the same seed, symbol, and timestamp.
