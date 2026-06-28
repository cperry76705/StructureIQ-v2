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
  "max_trades": 25
}
```

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

## Limitations

- Market structure and confidence are heuristic interpretations, not forecasts or guarantees.
- The default Yahoo adapter depends on external data availability, quality, and interval limits.
- Backtests use simplified fills and do not model fees, slippage, spread, latency, partial fills, or portfolio exposure.
- Calibration observes historical behavior; it does not prove profitability or change production thresholds automatically.
- The local JSONL journal is intended for a single local process, not concurrent or multi-user deployment.
- There is no dashboard, broker integration, order execution, alerting, or live-trading loop.

## Roadmap and Release Information

Version `1.1.0` extends the Stable MVP with actionability diagnostics: backtests and calibration now explain which existing gate causes skipped records without loosening thresholds. Future work focuses on controlled sensitivity studies, data-quality controls, stronger out-of-sample validation, persistence options, observability, and client experiences—not autonomous execution.

- [Roadmap](docs/Roadmap.md)
- [Changelog](docs/Changelog.md)
- [v1.0.0 Release Notes](docs/ReleaseNotes_v1.0.0.md)
- [Contributing](CONTRIBUTING.md)
- [Security Policy](SECURITY.md)

## Disclaimer

StructureIQ is decision-support and research software. It is not financial, investment, legal, or tax advice. Its outputs may be incomplete or wrong. Users are solely responsible for validating data, assessing risk, and making trading decisions. Past or simulated performance does not guarantee future results.
