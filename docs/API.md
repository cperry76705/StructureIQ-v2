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
  },
  "decision": {
    "action": "wait",
    "confidence": 68.0,
    "score_breakdown": {
      "market_structure": 22.8,
      "multi_timeframe": 17.5,
      "support_resistance_liquidity": 9.8,
      "indicators": 12.0,
      "risk_reward_volatility": 5.9,
      "total": 68.0
    },
    "positive_evidence": [
      {
        "category": "indicators",
        "message": "Available indicator context supports the structural thesis.",
        "impact": 12.0
      }
    ],
    "negative_evidence": [],
    "neutral_evidence": [
      {
        "category": "multi_timeframe",
        "message": "Current structure is pulling back within the higher-timeframe direction.",
        "impact": 0.0
      }
    ],
    "risk_notes": [
      "ATR-based volatility context is not yet available in v0.4."
    ],
    "invalidation_notes": [
      "Bullish thesis weakens if price closes below the latest confirmed swing low."
    ],
    "human_readable_summary": "StructureIQ recommends waiting because the evidence has not cleared every direction and risk gate; confidence is 68.0/100."
  }
}
```

The current response contract includes:

- `higher_timeframe_bias`: `bullish`, `bearish`, or `ranging`.
- `action`: `buy`, `sell`, `wait`, or `no_trade`.
- `confidence`: a value from `0` to `10`.
- Text fields describing structure, setup, illustrative levels, and reasoning.
- `multi_timeframe`: an additive v0.3 object containing the two structure views, alignment, unified bias, and explanation.
- `decision`: an additive v0.4 object containing the weighted recommendation and complete evidence ledger.

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

### Decision Object

| Field | Description |
| --- | --- |
| `action` | `buy`, `sell`, `wait`, or `avoid`. |
| `confidence` | Weighted evidence confidence from `0–100`. |
| `score_breakdown` | Contributions from market structure, multi-timeframe alignment, support/resistance and liquidity, indicators, and risk/reward and volatility. |
| `positive_evidence` | Supporting evidence items with category, message, and positive impact. |
| `negative_evidence` | Adverse evidence items with category, message, and negative impact. |
| `neutral_evidence` | Context that neither confirms nor invalidates the thesis. |
| `risk_notes` | Risk/reward, volatility, and trade-quality warnings. |
| `invalidation_notes` | Structural levels or conditions that weaken the thesis. |
| `human_readable_summary` | Concise explanation of the action and confidence. |

The response remains backward-compatible at the field level: every pre-v0.4 field remains present with the same name and type. `multi_timeframe` and `decision` are additive objects. The legacy top-level action is derived from the decision action, with `avoid` mapped to `no_trade`; legacy confidence is decision confidence divided by ten.

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

### Current Engine-Oriented Response

The current `/analysis` response is engine-oriented. Its top-level compatibility fields, `multi_timeframe`, and `decision` expose raw analytical state, scores, evidence, and implementation-facing summaries. This is useful for development, testing, integrations, journaling, and future backtesting, but it is not yet the final trader-facing product contract.

The existing response must remain available while downstream engines mature. Setup or presentation logic must not be embedded ad hoc into the current fields.

### Future Trader-Facing Analysis Block

A future version will add a typed trader-facing block after the Setup, Strategy, and Analysis/Explanation Engines are implemented. The working direction is an additive object such as:

```json
{
  "trader_analysis": {
    "market_summary": "Higher-timeframe structure remains bullish while the current timeframe is completing a pullback.",
    "recommended_setup": "bullish_bos_retest",
    "setup_status": "developing",
    "entry_conditions": [
      {
        "condition": "Current candle closes above the retest confirmation level",
        "status": "pending"
      }
    ],
    "invalidation": "Bullish thesis weakens below the latest confirmed swing low.",
    "risk_notes": [
      "Risk/reward must be recalculated after confirmation."
    ],
    "wait_avoid_reasoning": [
      "Wait while the entry trigger remains unconfirmed."
    ],
    "trade_plan_checklist": [
      {
        "item": "Directional decision remains bullish",
        "status": "satisfied"
      },
      {
        "item": "BOS retest confirms on the current timeframe",
        "status": "pending"
      }
    ]
  }
}
```

This example documents product direction, not a current API guarantee. Final field names and schemas will be versioned or introduced additively after the responsible engines exist.

The trader-facing block will explain internal results; it will not recalculate action, confidence, setup qualification, or strategy ranking. Evidence and checklist states must remain traceable to typed engine output.
