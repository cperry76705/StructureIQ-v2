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
  "current_structure": "pullback",
  "action": "wait",
  "setup": "bullish_pullback_to_support",
  "confidence": 6.5,
  "entry_zone": "illustrative level or range",
  "stop_loss": "illustrative invalidation level",
  "target": "illustrative objective",
  "reasons": [
    "Higher-timeframe structure is bullish",
    "Lower-timeframe confirmation is incomplete"
  ],
  "multi_timeframe": {
    "higher_timeframe": "1h",
    "current_timeframe": "5m",
    "higher_timeframe_trend": "bullish",
    "current_timeframe_trend": "bullish",
    "higher_timeframe_phase": "impulse",
    "current_timeframe_phase": "pullback",
    "alignment": "mixed",
    "alignment_score": 70,
    "directional_bias": "bullish",
    "reasons": [
      "Higher timeframe 1h is bullish in an impulse phase.",
      "Current timeframe 5m is bullish in a pullback phase.",
      "Current structure is pulling back within the higher-timeframe direction."
    ],
    "human_readable_summary": "1h bullish context and 5m bullish execution structure are mixed (70/100). Directional bias is bullish."
  }
}
```

The current response contract includes:

- `higher_timeframe_bias`: `bullish`, `bearish`, or `ranging`.
- `action`: `buy`, `sell`, `wait`, or `no_trade`.
- `confidence`: a value from `0` to `10`.
- Text fields describing structure, setup, illustrative levels, and reasoning.
- `multi_timeframe`: an additive v0.3 object containing the two structure views, alignment, unified bias, and explanation.

### Multi-Timeframe Object

| Field | Values | Description |
| --- | --- | --- |
| `higher_timeframe` | string | Requested higher timeframe. |
| `current_timeframe` | string | Requested execution-context timeframe. |
| `higher_timeframe_trend` | `bullish`, `bearish`, `ranging`, `unclear` | Higher-timeframe structure classification. |
| `current_timeframe_trend` | `bullish`, `bearish`, `ranging`, `unclear` | Current-timeframe structure classification. |
| `higher_timeframe_phase` | `impulse`, `pullback`, `range`, `reversal_attempt`, `unclear` | Higher-timeframe phase. |
| `current_timeframe_phase` | same as above | Current-timeframe phase. |
| `alignment` | `aligned_bullish`, `aligned_bearish`, `mixed`, `conflicting`, `unclear` | Relationship between the two structures. |
| `alignment_score` | integer, `0–100` | Strength and clarity of alignment. |
| `directional_bias` | `bullish`, `bearish`, `neutral`, `unclear` | Unified context, led by the higher timeframe. |
| `reasons` | array of strings | Evidence supporting the classification. |
| `human_readable_summary` | string | Concise explanation of the result. |

The v0.3 response is backward-compatible at the field level: every pre-v0.3 field remains present with the same name and type. `multi_timeframe` is the only additive top-level field.

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
