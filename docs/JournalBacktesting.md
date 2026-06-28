# Journal and Backtesting Engine

## Purpose

StructureIQ provides a measurement foundation for recording analysis decisions and evaluating their directional usefulness over historical candles. Version 1.1 adds actionability diagnostics without changing which records become simulated trades.

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

### Actionability Diagnostics

Every `BacktestTrade` records `actionability_status`. Skipped records also identify one primary `skip_reason_code`, a plain-English `skip_reason_detail`, and the `blocking_engine` that owns the first explanatory gate.

Reason codes cover non-actionable decisions, unconfirmed or absent setups, missing setup levels, non-actionable trader plans, strategy alignment, missing or insufficient risk/reward, and unclassified backtesting conditions. The diagnostic order follows existing engine authority: decision state is inspected before setup qualification, then levels, risk context, strategy context, and trader-plan presentation.

`BacktestResult.skip_diagnostics` aggregates:

- Total skipped records.
- Counts by primary reason code.
- Counts by blocking engine.
- The most common reason, with deterministic tie handling.
- A readable summary of the dominant gate.

Diagnostics do not add an execution gate. The existing behavior remains unchanged: only a directional decision with an actionable trader plan and parseable entry, stop, and target is simulated.

### Decision Diagnostics Summary

Version 1.2 snapshots `decision_diagnostics` on each backtest record when available. `BacktestResult.decision_diagnostics_summary` aggregates confidence bands, failed required gates, average final confidence, average raw score, and the most common blocked gate.

One record may fail more than one required Decision Engine gate, so blocked-gate counts answer a different question from the single primary skip reason. This report measures decision sensitivity while `skip_diagnostics` identifies the first engine-level actionability blocker. Neither changes whether the record is simulated.

Version 1.3 limits Decision Engine blockers to directional confidence, structure, and timeframe agreement. Missing levels are attributed to `setup_engine`; missing or sub-`1.5R` execution plans are attributed to `risk_engine` once directional evidence is ready.

Backtesting remains the final conservative validation layer. Even if an inconsistent upstream payload labels a plan actionable, the backtester skips it unless entry, stop, and target parse successfully and estimated risk/reward is present and at least `1.5R`.

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

## Calibration Relationship

The v0.9 Calibration Engine composes multiple Backtesting Engine runs across symbol and timeframe combinations. It reuses backtest trades and metrics, then aggregates results and groups them by setup and strategy.

Calibration does not change the backtest simulation model and does not tune application rules. Its recommendations identify historical behavior for human inspection.

Version 1.1 aggregates skip diagnostics across calibration runs so maintainers can distinguish Decision, Setup, Strategy, Explanation, risk-context, and backtesting blockers. Version 1.2 additionally aggregates the Decision Engine's confidence bands and required gate failures before any threshold experiment is designed.

Known forex symbols are normalized only when the Yahoo provider is queried. Backtest and calibration requests and results preserve the user-facing symbol.

## Limitations

- This is a simplified deterministic backtest, not a production execution simulator.
- OHLC candles do not expose intrabar event ordering.
- Fees, spread, slippage, latency, partial fills, and market impact are not modeled.
- Starting balance and risk percentage are recorded but position sizing and equity balances are not yet simulated.
- Entry, stop, target, and risk/reward inherit approximate upstream levels.
- Overlapping historical analysis windows may describe closely related opportunities.
- Historical performance measures past behavior and does not guarantee future profitability.
