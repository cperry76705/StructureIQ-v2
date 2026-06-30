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
- **Calibration Engine** — aggregates backtests and recommends areas for human review without tuning automatically.

See [Architecture](docs/Architecture.md), [API reference](docs/API.md), and the [project blueprint](docs/Vision.md) for details.

## Quick Start

Python 3.11 or newer is recommended.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

The API is available at `http://127.0.0.1:8000`; interactive OpenAPI documentation is at `/docs`.

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

## Limitations

- Market structure and confidence are heuristic interpretations, not forecasts or guarantees.
- The default Yahoo adapter depends on external data availability, quality, and interval limits.
- Backtests optionally approximate fees, spread, slippage, delayed fills, and 50% partial fills. They do not model latency, order-book depth, market impact, or portfolio exposure.
- Calibration observes historical behavior; it does not prove profitability or change production thresholds automatically.
- The local JSONL journal is intended for a single local process, not concurrent or multi-user deployment.
- There is no dashboard, broker integration, order execution, alerting, or live-trading loop.

## Roadmap and Release Information

Version `3.1.0` adds automatic statistical research, cross-dimensional matrices, rankings, uncertainty, and executive findings. Production behavior remains unchanged.

- [Roadmap](docs/Roadmap.md)
- [Changelog](docs/Changelog.md)
- [v1.0.0 Release Notes](docs/ReleaseNotes_v1.0.0.md)
- [Contributing](CONTRIBUTING.md)
- [Security Policy](SECURITY.md)

## Disclaimer

StructureIQ is decision-support and research software. It is not financial, investment, legal, or tax advice. Its outputs may be incomplete or wrong. Users are solely responsible for validating data, assessing risk, and making trading decisions. Past or simulated performance does not guarantee future results.
