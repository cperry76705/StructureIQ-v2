# StructureIQ

StructureIQ is an explainable market-intelligence and trader decision-support platform. It does not predict markets or place trades. It interprets current price structure, quantifies weighted evidence, explains uncertainty, and helps traders make disciplined decisions.

## Project Overview

The service turns historical candle data into two deliberately separate outputs:

1. Internal engine output: structure events, timeframe alignment, decision scores, setup qualification, and ranked strategy candidates.
2. Trader-facing output: a plain-English narrative, recommendation, risks, invalidation, and checklist-style trade plan.

All results are deterministic for the same inputs and provider data. StructureIQ is a research and decision-support tool, not an autonomous trading system.

## Architecture

The analysis path is modular:

`Market Data -> Market Structure -> Multi-Timeframe -> Indicators -> Decision -> Setup -> Strategy -> Explanation`

The platform includes:

- **Market Data Engine** — provider abstraction, candle normalization, and friendly-symbol mapping.
- **Market Structure Engine** — swings, HH/HL/LH/LL, BOS, CHOCH, liquidity sweeps, trend, and phase.
- **Multi-Timeframe Engine** — higher-timeframe context, execution-timeframe state, alignment, and directional bias.
- **Indicator Framework** — EMA, RSI, MACD, ATR, ADX, and volume confirmation where data permits.
- **Decision Engine** — weighted evidence producing `buy`, `sell`, `wait`, or `avoid` with confidence.
- **Setup Engine** — qualifies a specific setup and its entry, risk, confirmation, and invalidation conditions.
- **Strategy Engine** — compares broader playbooks without overriding the decision or setup.
- **Analysis/Explanation Engine** — translates internal outputs into a trader-facing narrative and plan.
- **Journal/Backtesting Engine** — local journaling and simplified deterministic historical evaluation.
- **Execution Realism Engine** — optional deterministic spread, slippage, commission, delayed-fill, and partial-fill research assumptions.
- **Execution Sensitivity Laboratory** — compares isolated and combined execution scenarios against a frozen perfect baseline.
- **Entry Timing Laboratory** — compares immediate, delayed, pullback, momentum, retest, and conservative-limit entries without changing production behavior.
- **Market Regime Laboratory** — classifies market conditions and cross-tabulates strategy and setup performance without changing routing.
- **Regime Validation Laboratory** — measures regime balance, persistence, transition exits, and forward proxy behavior without changing classifications.
- **Regime Classifier Tuning Laboratory** — explains transition dominance and compares threshold and evidence-weight counterfactuals without changing the production classifier.
- **Tuned Regime Classifier** — provides a parallel research label that prioritizes current swing structure and recent evidence while retaining the legacy classifier.
- **Tuned Regime Forward Validation** — compares legacy and tuned labels against matched 5/10/20-bar forward-behavior proxies.
- **Regime Confidence Calibration Laboratory** — measures confidence reliability and simulates non-production calibration mappings.
- **Out-of-Sample Validation Laboratory** — rebuilds the complete production pipeline across deterministic unseen-data folds and measures generalization.
- **Statistical Research Laboratory** — automatically ranks symbols, timeframes, setups, strategies, regimes, timing, execution, and cross-dimensional performance after every calibration.
- **Continuous Research Engine** — retains completed calibration records in a process-local reporting store and refreshes rolling strongest/weakest findings on demand.
- **Research Pipeline and Walk-Forward Intelligence** — combines finalized calibration, statistical research, and OOS folds into conservative robustness rankings and human-reviewed promotion readiness.
- **Monte Carlo Simulation Engine** — stress-tests completed calibration or OOS validation returns through deterministic reshuffling, bootstrap sampling, skipped-trade stress, and observed execution degradation.
- **Monte Carlo Risk Intelligence** — turns simulation paths into target probabilities, tail-risk heatmaps, expectancy confidence intervals, research-only Kelly estimates, and explicit pass/fail findings.
- **Advanced Statistical Validation** — detects edge decay, loss-sequence risk, outlier dependency, profit concentration, unstable folds, and negative recent expectancy hidden by aggregate profitability.
- **Centralized Evidence Scoring Engine** — consolidates live engine evidence and optional research reliability into a transparent quality score without controlling decisions.
- **Execution Intelligence Layer** — explains timing style, level quality, R:R, blockers, warnings, and research-only management guidance while preserving production execution.
- **Confidence Calibration Engine** — maps immutable raw decision scores to empirical historical win probabilities while preserving identity output when evidence is insufficient.
- **Strategy Rating Engine** — grades observed setups and strategies from historical performance, OOS consistency, sample quality, drawdown, significance, and research risk.
- **Adaptive Symbol Profile Engine** — persistently learns symbol-level performance, market character, and historically preferred rated categories from completed calibration trades.
- **Adaptive Strategy Router Laboratory** — compares unchanged production routes with symbol-profile preferences without rerouting trades.
- **Application Launcher** — validates the local environment, writes startup logs, displays diagnostics, and starts the unchanged FastAPI app through uvicorn.
- **Calibration Engine** — aggregates backtests and recommends areas for human review without tuning automatically.

See [Architecture](docs/Architecture.md), [API reference](docs/API.md), and the [project blueprint](docs/Vision.md) for details.

## Quick Start

Python 3.11 or newer is recommended.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python start.py
```

The API is available at `http://127.0.0.1:8000`; interactive OpenAPI documentation is at `/docs`.

The official launcher supports:

```powershell
python start.py              # Validate startup health and launch the API
python start.py --api         # Start only the API process after validation
python start.py --health      # Run startup checks without launching uvicorn
python start.py --version     # Print the current StructureIQ version
python start.py --help        # Show launcher options
```

The launcher reads the version from `app/config.py`, verifies Python, package, folder, file, configuration, and `app.main` import health, creates `logs/` if needed, and appends startup events to `logs/startup.log`. It delegates API serving to `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`; FastAPI behavior remains unchanged.

## Running Tests

```powershell
python -m pytest
```

Tests use deterministic fixtures and do not require live market-data access.

## API Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Service liveness |
| `POST` | `/analysis` | Full market analysis and trader-facing explanation |
| `POST` | `/journal` | Save an entry or compatible analysis snapshot |
| `GET` | `/journal` | List and filter journal entries |
| `GET` | `/journal/summary` | Aggregate journal outcomes |
| `POST` | `/backtest` | Run simplified historical evaluation |
| `POST` | `/calibrate` | Aggregate backtests across requested combinations |
| `GET` | `/research/status` | Read the latest human-readable research status |
| `GET` | `/research/rankings` | Rank current research dimensions |
| `GET` | `/research/best-combinations` | List strongest historical combinations |
| `GET` | `/research/weakest-combinations` | List weakest historical combinations |
| `POST` | `/research/refresh` | Recalculate a rolling research snapshot |

### Analysis Request

```json
{
  "symbol": "EUR-USD",
  "timeframe": "5m",
  "higher_timeframe": "1h",
  "lookback": 200
}
```

The response preserves established top-level fields and adds typed internal blocks (`multi_timeframe`, `decision`, `setup_plan`, and `strategy`) plus the trader-facing `trader_analysis` block.

### Backtest Request

```json
{
  "symbol": "BTC-USD",
  "timeframe": "5m",
  "higher_timeframe": "1h",
  "lookback": 300,
  "starting_balance": 10000,
  "risk_per_trade_percent": 1.0,
  "max_trades": 25,
  "execution_profile": {
    "spread": 0.5,
    "slippage": 0.25,
    "slippage_type": "fixed",
    "commission_per_trade": 2.0,
    "commission_type": "fixed",
    "fill_model": "next_bar"
  }
}
```

Remove `execution_profile` to retain the original perfect-execution baseline.

### Calibration Request

```json
{
  "symbols": ["BTC-USD", "EUR-USD"],
  "timeframes": ["5m"],
  "higher_timeframes": ["1h"],
  "lookback": 300,
  "max_trades_per_run": 25,
  "risk_per_trade_percent": 1.0,
  "starting_balance": 10000
}
```

Calibration also accepts optional `execution_sensitivity_profiles`. StructureIQ automatically adds perfect execution, freezes candle inputs across scenarios, and returns a separate `execution_sensitivity_summary`; see the API reference for Forex and Crypto examples.

Optional `entry_timing_profiles` run the same valid candidates through alternative entry methods and return an isolated `entry_timing_summary`. Immediate production timing is always included as the baseline.

Set `market_regime_analysis` to `true` during calibration to return regime performance plus strategy-regime and setup-regime matrices. The default is off, and regime findings never alter production behavior.

Set `regime_validation_analysis` to `true` to diagnose classification balance and 5/10/20-bar forward behavior. Transition use above 60% is flagged for inspection. Forward buckets are proxies, not ground truth.

Set `regime_tuning_analysis` to `true` to return the production distribution, competing evidence scores, transition staleness and conflict diagnostics, confidence and margin distributions, forward stability, transition-threshold simulations at 60–80, and isolated trend-evidence simulations. These are research counterfactuals; they do not replace any production regime label.

Set `regime_classifier_mode` to `legacy`, `tuned`, or `compare`. The default is `legacy`. Compare mode returns side-by-side legacy and tuned summaries plus label-change diagnostics over identical backtest records. Classifier mode never changes decisions, trade selection, stops, targets, outcomes, or aggregate calibration metrics.

In compare mode, set `forward_validation` to `true` to validate both classifiers against the exact same future windows. Results include accuracy, class metrics, confusion matrices, confidence reliability, persistence, return and excursion statistics, uncertainty flags, and a direct comparison. Forward regimes are deterministic proxies, not labeled ground truth.

Add `regime_confidence_analysis: true` to the compare-mode forward-validation request to measure ECE, MCE, Brier score, confidence distributions, reliability, and overconfidence for both classifiers. Mapping simulations never alter stored confidence, labels, routing, or trades.

Set `out_of_sample_validation` to `true` to run chronological, rolling, walk-forward, expanding, or anchored research folds. Training and validation pipelines are instantiated independently from bounded raw candle data; no decision or setup is reused across the split.

Every completed calibration now returns `research_lab_summary`, `research_rankings`, `performance_matrices`, `research_statistics`, and `research_recommendations`. Standard research categories remain visible even with zero samples, while future observed categories are included automatically.

Completed calibration records also feed the process-local Continuous Research Engine. Research endpoints support `all_time`, `last_250`, `last_500`, `last_1000`, and `custom` windows. `POST /research/refresh` recalculates reports only; it cannot change calibration or trading behavior. Optional background refresh support exists but is stopped by default. Research history is intentionally non-durable in v3.1 and resets when the service process restarts.

The v3.1.1 Yahoo adapter caps intraday chart ranges to combinations accepted reliably by Yahoo (`1m: 7d`, `5m/15m/30m: 1mo`, `1h: 2y`). Calibration isolates provider failures by run: available combinations still complete, while unavailable combinations appear in `provider_failures` and `data_availability_summary`. Analysis and standalone backtesting retain their existing provider-error behavior.

When OOS validation is enabled, v3.2 adds a unified research pipeline. It compares training and validation behavior by symbol, timeframe, setup, strategy, and regime; penalizes variance, decay, drawdown, overfit risk, and dependency; and assigns research-only promotion statuses. Fewer than 100 validation trades can never qualify for paper trading, regardless of expectancy. These reports are observational and cannot update any production engine.

Set `monte_carlo_analysis` to `true` to run v3.3 deterministic sequence-risk research. The engine uses OOS validation returns when OOS is enabled and completed calibration returns otherwise. It reports balance percentiles, R and drawdown distributions, streaks, profit probability, ruin risk, and drawdown-threshold probabilities. High ruin risk or a high probability of drawdown beyond 20% blocks research promotion to paper-trading readiness but changes no trade.

Version 3.4 adds a professional interpretation layer to the same simulations: probabilities of reaching R and account-growth targets, risk heatmaps, 90%/95%/99% expectancy intervals, deterministic Kelly fractions, failure codes, and `PASS`, `WATCHLIST`, `FAIL`, or `INSUFFICIENT_DATA` status. Kelly output is a research estimate only and is never applied to risk sizing.

Set `statistical_validation_analysis` to `true` for v3.5 hidden-weakness research. It measures consecutive-loss probabilities, R-distribution buckets, top-trade profit concentration, chronological expectancy thirds, edge decay, OOS fold stability, and explicit weakness flags. Severe findings can only downgrade research promotion readiness.

Every `/analysis` response now includes v3.6 `score_summary`, with trade quality, confidence, edge, risk, category breakdown, contributors, grade, unavailable research inputs, and plain-English interpretation. Calibration aggregates these immutable analysis scores into `aggregate_score_summary` and adds research categories when their reports exist. Scores never determine action or execution.

Version 3.7 adds `execution_intelligence` to `/analysis`. It recommends advisory styles such as limit retest, confirmation close, or wait for pullback using the already-selected setup and unchanged levels. Calibration returns an aggregate advisory summary enriched by MFE/MAE, entry-timing, management, Monte Carlo, and statistical research when available.

Version 3.8 adds `confidence_calibration` to `/analysis`; without historical context it mirrors the raw Decision Engine score and reports insufficient reliability. Calibration returns empirical 50–59 through 90–100 buckets, sample reliability, historical win probability, identity fallbacks, and an aggregate calibration summary. Calibrated confidence is never used for actionability.

Version 3.9 adds unavailable current setup/strategy ratings to live analysis and historical `strategy_rating_summary` plus `setup_rating_summary` to calibration. Ratings enforce hard low-sample and negative-expectancy caps and cannot promote, demote, or reroute production categories.

Version 4.0 persistently merges completed calibration observations into local symbol profiles. `/analysis` can display market character, preferred historical strategy/setup, grades, confidence, and sample size, while `/calibrate` returns the updated profile collection. Profiles are informational and never enter production analysis logic.

## Limitations

- Market structure and confidence are heuristic interpretations, not forecasts or guarantees.
- The default Yahoo adapter depends on external data availability, quality, and interval limits.
- Backtests optionally approximate fees, spread, slippage, delayed fills, and 50% partial fills. They do not model latency, order-book depth, market impact, or portfolio exposure.
- Calibration observes historical behavior; it does not prove profitability or change production thresholds automatically.
- The local JSONL journal is intended for a single local process, not concurrent or multi-user deployment.
- There is no dashboard, broker integration, order execution, alerting, or live-trading loop.

## Roadmap and Release Information

Version `4.2.0` adds the official application launcher and startup health checks. Production behavior remains unchanged.

- [Roadmap](docs/Roadmap.md)
- [Changelog](docs/Changelog.md)
- [v1.0.0 Release Notes](docs/ReleaseNotes_v1.0.0.md)
- [Contributing](CONTRIBUTING.md)
- [Security Policy](SECURITY.md)

## Disclaimer

StructureIQ is decision-support and research software. It is not financial, investment, legal, or tax advice. Its outputs may be incomplete or wrong. Users are solely responsible for validating data, assessing risk, and making trading decisions. Past or simulated performance does not guarantee future results.
