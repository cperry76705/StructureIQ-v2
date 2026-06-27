# StructureIQ v2

A clean, rule-based market analysis API built with FastAPI. It reads real market candles from Yahoo Finance by default, performs no live execution, and does not connect to a broker.

## What it does

- Detects swing highs and lows and derives higher-timeframe bias.
- Labels higher highs, higher lows, lower highs, and lower lows.
- Detects bullish/bearish breaks of structure (BOS), changes of character (CHOCH), and liquidity sweeps.
- Classifies impulse, pullback, range, reversal-attempt, and unclear phases.
- Identifies simple support and resistance zones.
- Classifies current structure, routes to a basic strategy, and scores confluence from 0-10.
- Returns illustrative entry, stop, and target levels. These are analysis outputs, not financial advice or live orders.
- Converts provider responses into a standard `Candle` model before analysis.
- Returns HTTP 503 with an informative message when market data is unavailable.

## Setup

Run these commands from the `structureiq-v2` directory:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

The API is available at `http://127.0.0.1:8000`; interactive docs are at `http://127.0.0.1:8000/docs`.

## API

Health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Run an analysis:

```powershell
$body = @{
  symbol = "BTC-USD"
  timeframe = "5m"
  higher_timeframe = "1h"
  lookback = 200
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/analysis `
  -ContentType "application/json" -Body $body
```

## Tests

```powershell
python -m pytest
```

## Market data providers

`core/market_data.py` defines the provider contract and standardized candle model. Yahoo Finance is the default implementation. OANDA and Polygon.io adapters are present as explicit future placeholders and report that they are not configured if selected.

Provider selection is dependency-injected in `app/main.py`. Swap `get_market_data_provider()` or override that FastAPI dependency in tests; the analysis engine requires no changes.

## Market structure engine

`core/market_structure.py` analyzes only standardized `Candle` objects. Its typed result contains:

- `trend`: bullish, bearish, ranging, or unclear
- `phase`: impulse, pullback, range, reversal attempt, or unclear
- Latest confirmed swing high and low
- Recent structural events such as `higher_high`, `bullish_bos`, and `bearish_choch`
- Liquidity-sweep state, a confidence modifier, and a human-readable summary

A BOS requires a candle close through the latest confirmed swing. When that close breaks an established opposite trend, the event is classified as CHOCH. A liquidity sweep requires a wick through a confirmed swing followed by a close back inside its level.

Swings use a two-candle fractal confirmation window by default. This avoids treating every local fluctuation as structure, but means swing labels lag by two completed candles. The internal engine can report `unclear`; to preserve the existing `/analysis` response contract, an unclear higher-timeframe trend is exposed as the conservative `ranging` bias.
