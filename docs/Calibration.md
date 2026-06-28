# Validation and Calibration

## Purpose

StructureIQ v0.9 adds deterministic tools for observing whether current decision thresholds, setup qualification, strategy ranking, and risk assumptions appear too conservative, too aggressive, or reasonably balanced over historical samples.

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

Recommendations ask maintainers to inspect evidence and rules. They do not apply parameter changes.

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
