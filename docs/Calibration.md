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

Recommendations now name the specific gate to inspect—for example, the distance below 70 confidence, structure direction, mixed/conflicting timeframe states, risk/reward availability, unmet Setup Engine confirmation conditions, level derivation, or strategy eligibility. They do not apply parameter changes or recommend loosening a threshold without first measuring its distribution and historical sensitivity.

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
