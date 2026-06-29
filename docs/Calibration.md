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

## v2.2 Execution Sensitivity Laboratory

`CalibrationRequest.execution_sensitivity_profiles` accepts named descriptions and typed execution profiles. When supplied, calibration adds `execution_sensitivity_summary` and automatically includes canonical perfect execution. When omitted, the existing calibration path runs once and the optional summary is null.

Each result reports outcomes, R metrics, profit factor, drawdown, perfect baseline expectancy, modeled expectancy, expectancy reduction, and average execution costs. The summary names the best, worst, and largest-drop profiles, attributes the dominant component from settings, and returns inspection recommendations. Ordinary calibration metrics are never replaced.

Helper functions provide eight illustrative scenarios per asset family: perfect, mild spread only, mild slippage only, mild commission only, next-bar only, and mild, moderate, and harsh combined profiles. Forex examples use five-decimal price units; Crypto examples use whole price units and percentage commissions. All values must be replaced or validated against the intended venue and instrument before interpreting results.

| Helper profile | Example assumptions |
| --- | --- |
| `perfect` | No costs; immediate fill |
| `forex_spread_only_mild` | `0.0001` spread |
| `forex_slippage_only_mild` | Random slippage up to `0.00005` |
| `forex_commission_only_mild` | `2.00` fixed commission |
| `forex_next_bar_only` | Next-bar-open fill |
| `forex_mild_realistic` | `0.0001` spread, random `0.00005` slippage, `2.00` fixed commission |
| `forex_moderate_realistic` | `0.0002`, `0.0001`, `5.00`, next-bar fill |
| `forex_harsh_realistic` | `0.0004`, `0.0002`, `10.00`, next-bar fill |
| `crypto_spread_only_mild` | `2.0` price-unit spread |
| `crypto_slippage_only_mild` | Random slippage up to `1.0` price unit |
| `crypto_commission_only_mild` | `0.02%` notional commission |
| `crypto_next_bar_only` | Next-bar-open fill |
| `crypto_mild_realistic` | `2.0` spread, random `1.0` slippage, `0.02%` commission |
| `crypto_moderate_realistic` | `5.0`, `2.5`, `0.05%`, next-bar fill |
| `crypto_harsh_realistic` | `10.0`, `5.0`, `0.1%`, next-bar fill |

## v2.3 Entry Timing Laboratory

`CalibrationRequest.entry_timing_profiles` adds a separate `entry_timing_summary`; omission leaves it null and preserves the existing calibration path. The laboratory automatically prepends immediate production timing and rejects comparisons whose profiles do not receive the same valid candidate count.

Supported models are `immediate`, `next_bar_open`, `signal_close`, `midpoint_between_entry_and_stop`, `midpoint_between_entry_and_target`, `quarter_pullback_from_entry_to_stop`, `quarter_pullback_from_entry_to_target`, `retest_entry`, and `conservative_limit`.

Results report candidates, fills, misses, outcomes, R metrics, drawdown, average entry improvement, delay, missed-opportunity R, and fallback count. The summary identifies best and worst expectancy, highest fill rate, best expectancy-to-drawdown profile, and the profile with most misses. These are counterfactual findings and cannot alter production entry behavior.

## v2.4 Market Regime Laboratory

Set `market_regime_analysis` to true to return `market_regime_summary`, `strategy_regime_matrix`, and `setup_regime_matrix`. The flag defaults to false and does not rerun or mutate ordinary calibration trades.

Classification uses only existing structure, timeframe, ATR, range, swing, BOS/CHOCH, momentum, and volatility evidence. Regime precedence is transition, compression or expansion, range, volatility extremes, then directional trend strength. This produces one stable label while retaining reasons for the other evidence dimensions.

Every regime row reports records, closed trades, outcomes, expectancy, total R, profit factor, drawdown, duration, MFE/MAE, and best/worst strategy and setup. Matrices provide the same core performance measures for every strategy-regime and setup-regime pair. Recommendations flag negative expectancy, drawdown of at least `3R`, fewer than five closed trades, and sampled dominance or underperformance. These thresholds are reporting rules, not statistical proof or production controls.

## v2.5 Regime Validation Laboratory

Set `regime_validation_analysis` to true to return `regime_validation_summary`. The flag is independent of `market_regime_analysis`; validation uses regime snapshots already attached to every backtest record and does not modify classifications.

Distribution reports every regime's record share, closed trades, and confidence. Transition is considered overused only when it exceeds 60% of classified records. Persistence is calculated from consecutive labels within each symbol/current-timeframe/higher-timeframe sequence.

Forward validation uses available candles at deterministic 5, 10, and 20-bar horizons. It reports returns, directional follow-through, range behavior, expansion, and compression. A proxy actual bucket is derived from those outcomes for confusion-style counts. Missing horizons remain explicit and may trigger `insufficient_samples`.

Proxy buckets are diagnostic approximations, not labeled ground truth. Recommendations may suggest inspecting transition handling, trend or range detection, confidence, persistence, or sample coverage, but never tune rules automatically.

## v2.6 Regime Classifier Tuning Laboratory

Set `regime_tuning_analysis` to true to return `regime_tuning_summary`. The opt-in report uses immutable production labels and hidden research evidence already captured for each calibration record. It can run independently of `market_regime_analysis` and `regime_validation_analysis`.

The summary reports the current distribution, transition dominance and normalized overuse score, trend underclassification score, average competing evidence scores, transition-win reasons, runner-up and classification margins, stale transitions, transitions lacking recent BOS or CHOCH, directional structures labeled transition, timeframe conflicts, confidence by regime, confidence histogram, and 5/10/20-bar forward stability.

Two deterministic counterfactual groups are included:

- Transition thresholds `60`, `65`, `70`, `75`, and `80`, each with its simulated distribution, transition share, trend count, and transition reduction.
- Isolated boosts for BOS, CHOCH, swing structure, and higher-timeframe alignment evidence, each with the expected distribution and transition reduction.

A negative classification margin means production transition won by precedence even though the laboratory's strongest non-transition evidence score was higher. Counterfactual distributions diagnose sensitivity only: they are not proposed defaults, profitability studies, or automatic tuning. Production classifications and all trade records remain unchanged.

## v2.7 Tuned Regime Classifier

`regime_classifier_mode` accepts `legacy`, `tuned`, or `compare` and defaults to `legacy`.

- `legacy` preserves all v2.6 behavior. `market_regime_analysis` groups records by the original classifier.
- `tuned` groups regime research by the tuned label and returns `tuned_market_regime_summary` without replacing the stored legacy label.
- `compare` returns `legacy_market_regime_summary`, `tuned_market_regime_summary`, and `regime_classifier_comparison` over the same records.

The comparison reports transition ratios and reduction, trend counts and increase, changed records and agreement, plus transition-to-trend, range, compression, and expansion counts. Ratios use `0–1`; `changed_percentage` and `agreement_rate` use `0–100` percentages.

The tuned classifier ignores stale CHOCH as current transition pressure, weights directional swing structure first, treats recent directional BOS as confirmation, and uses aligned or directionally consistent mixed higher-timeframe evidence as support. Range, compression, and expansion rules remain intact. Calibration metrics, skips, outcomes, setup/strategy performance, and every production trade decision remain calculated once from the unchanged backtest path.

## v2.8 Tuned Regime Forward Validation

Set `forward_validation` to true together with `regime_classifier_mode: compare`. No validation runs for legacy or tuned mode alone, and false remains the default.

Both classifiers receive the exact same records and available 5-, 10-, and 20-bar future windows. Deterministic proxies distinguish strong/weak bullish and bearish follow-through, range containment, compression, expansion, and mixed transition behavior. Compression is considered useful when compression persists or an expansion follows within the horizon; transition is correct only when behavior remains mixed.

Per-classifier reports include metric sample sizes, standard deviations and approximate confidence intervals where meaningful, confusion matrices, confidence-reliability curves, regime persistence, and horizon-level return, MFE, MAE, continuation, reversal, volatility expansion, range persistence, and trend persistence statistics. Returns and excursions are normalized price-return fractions, not trade R multiples.

`forward_validation_comparison` reports tuned-minus-legacy accuracy deltas, confidence delta, the best sampled classifier, and recommendations. `LOW_SAMPLE`, `HIGH_CONFIDENCE`, and `INSUFFICIENT_DATA` flags make uncertainty explicit. These are proxy outcomes rather than expert-labeled regimes, statistical proof, or profitability evidence.
