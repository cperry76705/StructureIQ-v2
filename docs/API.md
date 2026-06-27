# StructureIQ API

## Overview

StructureIQ currently exposes a FastAPI HTTP interface for service health and market analysis. The API provides market intelligence only. It does not expose endpoints for broker authentication, order placement, position management, or live execution.

Interactive OpenAPI documentation is available at `/docs` when the service is running.

## `GET /health`

Reports whether the API application is running.

### Success Response

Status: `200 OK`

```json
{
  "status": "ok",
  "app": "StructureIQ v2"
}
```

`status` is currently `ok`; `app` contains the configured application name.

## `POST /analysis`

Retrieves market data through the configured provider and returns a structured analysis.

### Request Body

```json
{
  "symbol": "BTC-USD",
  "timeframe": "5m",
  "higher_timeframe": "1h",
  "lookback": 200
}
```

| Field | Type | Description |
| --- | --- | --- |
| `symbol` | string | Market symbol. Input is trimmed and normalized to uppercase. |
| `timeframe` | string | Primary analysis or execution-context timeframe. |
| `higher_timeframe` | string | Timeframe used to establish higher-timeframe bias. |
| `lookback` | integer | Number of candles requested, subject to configured limits. |

### Success Response

Status: `200 OK`

```json
{
  "symbol": "BTC-USD",
  "timeframe": "5m",
  "higher_timeframe_bias": "bullish",
  "current_structure": "bullish pullback",
  "action": "wait",
  "setup": "pullback continuation",
  "confidence": 6.5,
  "entry_zone": "illustrative level or range",
  "stop_loss": "illustrative invalidation level",
  "target": "illustrative objective",
  "reasons": [
    "Higher-timeframe structure is bullish",
    "Lower-timeframe confirmation is incomplete"
  ]
}
```

The current response contract includes:

- `higher_timeframe_bias`: `bullish`, `bearish`, or `ranging`.
- `action`: `buy`, `sell`, `wait`, or `no_trade`.
- `confidence`: a value from `0` to `10`.
- Text fields describing structure, setup, illustrative levels, and reasoning.

Illustrative entry, stop, and target values are analytical outputs. They are not live orders, financial advice, or guarantees.

### Errors

- `422 Unprocessable Entity`: request validation failed.
- `503 Service Unavailable`: market data could not be retrieved. The response includes an informative `detail` message.

Example:

```json
{
  "detail": "Market data unavailable: provider error"
}
```

## Contract Evolution

Future engine outputs should be introduced through explicit, typed, backward-compatible contracts or a versioned API. Evidence, confidence, and explanation metadata should remain machine-readable so API and dashboard consumers receive the same underlying analysis.
