# Journal and Backtesting Engine

## Purpose

StructureIQ v0.8 introduces a measurement foundation for recording analysis decisions and evaluating their directional usefulness over historical candles.

The journal and backtester are research tools. They do not place orders, reproduce broker execution, guarantee profitability, or convert StructureIQ into a live trading system.

## Journal

### Journal Entry

`JournalEntry` records:

- Stable ID and timestamp.
- Symbol, current timeframe, and higher timeframe.
- Legacy action and confidence plus the Decision Engine action.
- Setup type and status.
- Preferred strategy.
- Entry zone, stop, target, and estimated risk/reward when available.
- Outcome and realized R multiple.
- User notes.
- Raw analysis snapshot for later inspection.

Outcomes are `win`, `loss`, `breakeven`, `skipped`, `open`, or `unknown`.

### Storage

`JournalStore` uses append-only JSONL at `journal/trade_journal.jsonl` by default. It creates the parent directory when initialized, returns an empty list when the file does not exist, and skips malformed lines rather than failing the full read.

The store supports:

- Appending an entry.
- Listing all entries.
- Filtering by symbol, timeframe, or outcome.
- Producing aggregate summaries.

JSONL is intentionally simple and local. It is not a concurrent multi-user database, immutable audit service, or encrypted records system.

### Journal Summary

`JournalSummary` reports entry and outcome counts, win rate, average R, total R, and best and worst realized R.

- Win rate uses wins divided by wins, losses, and breakeven results.
- Average R uses entries with a recorded realized R multiple.
- Skipped, open, and unknown entries remain visible but are not treated as closed wins or losses.

## Backtesting

### Request

`BacktestRequest` includes symbol, current and higher timeframe, lookback, starting balance, risk per trade percentage, and maximum returned trade records.

### Deterministic Flow

The backtester:

1. Retrieves historical candles through the existing market data provider.
2. Walks chronological windows with at least 50 completed candles.
3. Runs the existing StructureIQ analysis pipeline using only data available at each window.
4. Reads Decision, Setup, Strategy, and trader-facing plan output.
5. Records a skipped result when the plan is not actionable or risk levels are unavailable.
6. For actionable buy or sell plans, scans later candles for the first stop or target touch.
7. Caps returned records using `max_trades`.
8. Calculates deterministic R-based metrics and returns explicit limitations.

### Outcome Rules

- Target before stop produces a win and the estimated or level-derived reward multiple.
- Stop before target produces a `-1R` loss.
- If both stop and target fall within one OHLC candle, the result is conservatively recorded as a loss because intrabar ordering is unknown.
- If neither level is reached in the available data, the trade remains open.
- Breakeven management is not simulated in v0.8.

### Metrics

`BacktestMetrics` includes closed trade count, wins, losses, breakeven, win rate, average R, total R, profit factor, and maximum drawdown in R.

Skipped and open records remain in `BacktestResult.trades` for auditability but are excluded from closed-trade metrics. Profit factor is null when no losing R exists.

## API Relationship

The journal endpoints persist and retrieve local records. The backtest endpoint runs the historical evaluator synchronously and returns a typed result. Existing `/health` and `/analysis` behavior remains unchanged.

## Limitations

- This is a simplified deterministic backtest, not a production execution simulator.
- OHLC candles do not expose intrabar event ordering.
- Fees, spread, slippage, latency, partial fills, and market impact are not modeled.
- Starting balance and risk percentage are recorded but position sizing and equity balances are not yet simulated.
- Entry, stop, target, and risk/reward inherit approximate upstream levels.
- Overlapping historical analysis windows may describe closely related opportunities.
- Historical performance measures past behavior and does not guarantee future profitability.
