# StructureIQ API

## Overview

StructureIQ `2.1.0` exposes a FastAPI HTTP interface for analysis, local journaling, simplified backtesting, and observational calibration. The API provides market intelligence only. It does not expose endpoints for broker authentication, order placement, position management, or live execution.

Interactive OpenAPI documentation is available at `/docs` and the machine-readable schema at `/openapi.json` when the service is running. Public endpoints use explicit response models; validation failures use FastAPI's standard `422` detail format, and provider failures return `503` with a market-data message.

## Symbol Normalization

Public requests and responses preserve user-facing symbols. The default Yahoo provider translates supported forex pairs only when requesting market data. For example, `EUR-USD` is queried as `EURUSD=X`, while `BTC-USD`, existing Yahoo symbols such as `EURUSD=X`, and unknown symbols pass through safely.

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
  "setup": "bullish_pullback_continuation",
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
    "human_readable_summary": "StructureIQ recommends waiting because the evidence has not cleared every direction and risk gate; confidence is 68.0/100.",
    "decision_diagnostics": {
      "raw_score": 68.0,
      "final_confidence": 68.0,
      "intended_direction": "bullish",
      "confidence_band": "wait",
      "blocked_by": ["directional_confidence"],
      "gate_results": [
        {
          "gate_name": "directional_confidence",
          "passed": false,
          "required": true,
          "actual_value": 68.0,
          "expected_value": ">= 70.0",
          "impact": -2.0,
          "blocking_reason": "Confidence is below the existing directional-action threshold."
        }
      ],
      "human_readable_summary": "The wait decision is blocked by confidence threshold; confidence is 68.0/100 (wait)."
    }
  },
  "setup_plan": {
    "setup_type": "bullish_pullback_continuation",
    "setup_status": "waiting_for_confirmation",
    "direction": "bullish",
    "setup_quality_score": 72.0,
    "entry_zone": "1.13520-1.13545",
    "stop_loss": "1.13380",
    "target": "1.13950",
    "estimated_risk_reward": 1.8,
    "entry_conditions": [
      {
        "condition": "Bullish confirmation candle forms at the setup level.",
        "is_met": false,
        "importance": "required"
      }
    ],
    "invalidation_rules": [
      {
        "rule": "Bullish setup invalidates if price closes below the latest confirmed swing low.",
        "trigger_level": "1.13380",
        "severity": "hard"
      }
    ],
    "supporting_evidence": [
      "Bullish trend and pullback structure support continuation."
    ],
    "warning_notes": [
      "One or more required entry conditions remain unmet."
    ],
    "human_readable_summary": "A bullish pullback continuation setup is waiting for required confirmation before entry.",
    "setup_level_diagnostics": {
      "setup_type": "bullish_pullback_continuation",
      "setup_status": "waiting_for_confirmation",
      "entry_zone_source": "support_zone",
      "stop_loss_source": "support_zone_extension",
      "target_source": "resistance_zone",
      "latest_swing_high": 1.138,
      "latest_swing_low": 1.1338,
      "nearest_support": 1.1353,
      "nearest_resistance": 1.1395,
      "level_quality": "complete",
      "human_readable_summary": "Bullish pullback continuation levels are complete."
    }
  },
  "strategy": {
    "preferred_strategy": "pullback_continuation",
    "strategy_alignment": "partially_aligned",
    "human_readable_summary": "Pullback continuation is most relevant but still developing for the current decision and setup context.",
    "candidates": [
      {
        "strategy_type": "pullback_continuation",
        "status": "developing",
        "direction": "bullish",
        "score": 85.0,
        "score_breakdown": {
          "structure_fit": 25.0,
          "timeframe_fit": 18.0,
          "setup_fit": 20.0,
          "risk_fit": 12.0,
          "indicator_confirmation": 10.0,
          "total": 85.0
        },
        "supporting_evidence": [
          "Directional structure is in a pullback phase."
        ],
        "opposing_evidence": [],
        "required_conditions": [
          "Bullish confirmation candle forms at the setup level."
        ],
        "invalidation": [
          "Bullish setup invalidates if price closes below the latest confirmed swing low."
        ],
        "notes": [
          "One or more required entry conditions remain unmet."
        ]
      }
    ]
  },
  "trader_analysis": {
    "headline": "EUR/USD is bullish, but the entry is not confirmed yet.",
    "summary": "The higher timeframe remains bullish while the current timeframe is pulling back. The Decision Engine remains wait at 68.0/100 confidence. The bullish pullback continuation setup is waiting for confirmation.",
    "recommendation": "Wait for the missing setup conditions before considering entry.",
    "market_narrative": {
      "bias": "bullish",
      "phase": "pullback",
      "context": "The 1h context remains bullish, while 5m execution structure is bullish in a pullback phase."
    },
    "why": [
      "The 1h context remains bullish, while 5m execution structure is bullish in a pullback phase.",
      "Weighted evidence produced wait with 68.0/100 confidence.",
      "A bullish pullback continuation setup is waiting for required confirmation before entry."
    ],
    "trade_plan": {
      "status": "waiting",
      "setup_type": "bullish_pullback_continuation",
      "direction": "bullish",
      "entry_zone": "1.13520-1.13545",
      "stop_loss": "1.13380",
      "target": "1.13950",
      "estimated_risk_reward": 1.8,
      "wait_for": [
        {
          "condition": "Bullish confirmation candle forms at the setup level.",
          "importance": "required",
          "source": "setup_engine"
        }
      ],
      "invalidation": [
        "Bullish setup invalidates if price closes below the latest confirmed swing low. The trigger level is 1.13380."
      ],
      "notes": [
        "One or more required entry conditions remain unmet."
      ]
    },
    "key_risks": [
      {
        "risk": "Execution timeframe has not confirmed continuation.",
        "severity": "medium",
        "reason": "This evidence reduced the Decision Engine's confidence."
      }
    ],
    "confidence_interpretation": "Moderate but incomplete edge. More confirmation is required.",
    "next_best_action": "Wait for this required condition: Bullish confirmation candle forms at the setup level."
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
- `setup_plan`: an additive v0.5 object containing setup qualification, entry conditions, invalidation, and risk context.
- `strategy`: an additive v0.7 object containing ranked broader playbooks and selection evidence.
- `trader_analysis`: an additive v0.6 object containing the trader-facing narrative and checklist plan.

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

### Setup Plan Object

| Field | Description |
| --- | --- |
| `setup_type` | Named setup type or `no_valid_setup`. |
| `setup_status` | `confirmed`, `developing`, `waiting_for_confirmation`, `invalid`, or `no_setup`. |
| `direction` | `bullish`, `bearish`, or `neutral`. |
| `setup_quality_score` | Setup-condition completeness from `0–100`; distinct from Decision Engine confidence. |
| `entry_zone` | Relevant entry context when available. |
| `stop_loss` | Illustrative structural risk level when available. |
| `target` | Illustrative objective when available. |
| `estimated_risk_reward` | Estimated reward-to-risk ratio, or `null` when it cannot be measured. |
| `entry_conditions` | Checklist items with condition, completion state, and importance. |
| `invalidation_rules` | Soft or hard invalidation rules and optional trigger levels. |
| `supporting_evidence` | Internal observations supporting the setup candidate. |
| `warning_notes` | Missing conditions, conflicts, and risk warnings. |
| `human_readable_summary` | Factual setup qualification summary. |

### Trader Analysis Object

| Field | Description |
| --- | --- |
| `headline` | Short trader-facing statement of the current opportunity or lack of edge. |
| `summary` | Plain-English synthesis of context, decision, and setup status. |
| `recommendation` | Explanation of whether the current plan is actionable, waiting, developing, avoid, or no trade. |
| `market_narrative` | Directional bias, current phase, and timeframe context. |
| `why` | Traceable plain-English reasons sourced from internal engine results. |
| `trade_plan` | Setup levels, status, unmet required conditions, invalidation, and notes. |
| `key_risks` | Risk, severity, and reason derived from negative evidence and warnings. |
| `confidence_interpretation` | Trader-friendly interpretation of Decision Engine confidence. |
| `next_best_action` | The next condition or review step implied by the current plan. |

### Strategy Object

| Field | Description |
| --- | --- |
| `preferred_strategy` | Highest-scoring aligned playbook or `no_strategy`. |
| `strategy_alignment` | `aligned_with_decision`, `partially_aligned`, `conflicts_with_decision`, or `no_clear_strategy`. |
| `human_readable_summary` | Factual ranking summary for downstream explanation. |
| `candidates` | Ranked strategy candidates with status, direction, score, breakdown, evidence, conditions, invalidation, and notes. |

Candidate scores contain structure fit, timeframe fit, setup fit, risk fit, and indicator confirmation. They compare playbook suitability; they do not replace Decision Engine confidence or Setup Engine quality.

The response remains backward-compatible at the field level: every pre-v0.7 field remains present with the same name and type. `multi_timeframe`, `decision`, `setup_plan`, `strategy`, and `trader_analysis` are additive objects. The legacy top-level action and confidence remain derived from the Decision Engine, while the legacy top-level setup mirrors `setup_plan.setup_type`.

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

## `POST /journal`

Appends a journal record to the local JSONL store. The body may contain explicit `JournalEntry`-compatible fields or a complete `/analysis` response. Missing ID and timestamp values are generated automatically.

Example explicit payload:

```json
{
  "symbol": "BTC-USD",
  "timeframe": "5m",
  "higher_timeframe": "1h",
  "action": "wait",
  "confidence": 64,
  "decision_action": "wait",
  "setup_type": "bullish_pullback_continuation",
  "setup_status": "developing",
  "strategy_type": "pullback_continuation",
  "entry_zone": "100-101",
  "stop_loss": "98",
  "target": "105",
  "estimated_risk_reward": 2.0,
  "outcome": "unknown",
  "realized_r_multiple": null,
  "notes": ["Waiting for confirmation"],
  "raw_analysis_snapshot": {}
}
```

The saved `JournalEntry` is returned.

## `GET /journal`

Returns journal entries in append order. Optional query parameters are:

- `symbol` — case-insensitive exact symbol filter.
- `timeframe` — exact timeframe filter.
- `outcome` — `win`, `loss`, `breakeven`, `skipped`, `open`, or `unknown`.

An absent journal file returns an empty array.

## `GET /journal/summary`

Returns journal counts and R-based aggregate statistics:

```json
{
  "total_entries": 4,
  "wins": 1,
  "losses": 1,
  "breakeven": 1,
  "skipped": 1,
  "open": 0,
  "unknown": 0,
  "win_rate": 33.33,
  "average_r": 0.33,
  "total_r": 1.0,
  "best_trade_r": 2.0,
  "worst_trade_r": -1.0
}
```

## `POST /backtest`

Runs the simplified deterministic historical evaluator using the configured market data provider.

Request:

```json
{
  "symbol": "BTC-USD",
  "timeframe": "5m",
  "higher_timeframe": "1h",
  "lookback": 500,
  "starting_balance": 10000,
  "risk_per_trade_percent": 1,
  "max_trades": 100,
  "execution_profile": {
    "spread": 0.5,
    "slippage": 0.25,
    "slippage_type": "fixed",
    "commission_per_trade": 2.0,
    "commission_type": "fixed",
    "allow_partial_fill": false,
    "partial_fill_probability": 0.0,
    "fill_model": "next_bar",
    "random_seed": 42
  }
}
```

`execution_profile` is optional. Omitting it uses the original perfect-execution simulator. Slippage types are `none`, `fixed`, and seeded `random`; fill models are `immediate`, `next_bar`, and `touch`. Spread and slippage use price units. Fixed commissions use account-currency units; percentage commissions apply to estimated filled notional. Commission diagnostics report the resulting R deduction.

The response contains the validated request, simulated or skipped trade records, aggregate metrics, skip diagnostics, a summary, and explicit limitations. `max_trades` caps returned analysis-window records, including skipped records.

Skipped trade records add `skip_reason_code`, `skip_reason_detail`, `blocking_engine`, and `actionability_status`. Actionable records retain these fields with null skip metadata and `actionability_status: "actionable"`.

Each record also snapshots `decision_diagnostics` when supplied by the analysis pipeline. The result-level `decision_diagnostics_summary` contains `by_confidence_band`, `by_blocked_gate`, `average_confidence`, `average_raw_score`, `most_common_blocked_gate`, and a readable summary.

In v1.3, only directional confidence, structure alignment, and multi-timeframe alignment are required Decision Engine gates. `execution_readiness`, `risk_plan_available`, and `risk_plan_quality` are non-required decision observations. Setup and Backtesting enforce complete levels and the `1.5R` execution minimum.

Version 1.5 adds per-record `risk_reward_diagnostics` and `setup_level_diagnostics`, plus result-level `risk_reward_summary` and `setup_level_summary`. These are observational additions and do not change skipped or simulated outcomes.

Version 1.7 adds `outcome_diagnostics` to executed backtest records and `outcome_diagnostics_summary` to the result. Skipped records expose `null` because no trade path exists. First-touch and excursion fields are derived from the same candles used by the unchanged simulator.

Version 1.8 adds `trade_management_sensitivity` to `/backtest`. It always includes `none`, break-even at `1R` and `1.5R`, partial profit at `1R` and `1.5R`, and trailing after `1R` and `1.5R`. Results are counterfactual and never replace production metrics.

Version 2.1 adds per-trade `execution_diagnostics` and result-level `execution_summary`. Diagnostics contain requested and actual entry, spread, slippage, commission, quality, fill model, baseline R, realistic R, and degradation. The summary reports average costs, degradation, baseline expectancy, realistic expectancy, and expectancy reduction.

```json
{
  "skip_diagnostics": {
    "total_skipped": 50,
    "by_reason_code": {
      "decision_not_actionable": 38,
      "setup_not_confirmed": 12
    },
    "by_blocking_engine": {
      "decision_engine": 38,
      "setup_engine": 12
    },
    "most_common_reason": "decision_not_actionable",
    "human_readable_summary": "50 records were skipped; the most common reason was decision not actionable, primarily blocked by decision engine."
  }
}
```

`BacktestMetrics.total_trades` counts closed wins, losses, and breakeven trades; skipped and open records remain visible in `trades` but are excluded from closed-trade metrics. Profit factor is `null` when no losing R exists.

This endpoint is synchronous and research-oriented. Execution profiles are deterministic approximations, not live execution or a profitability guarantee.

## `POST /calibrate`

Runs the existing Backtesting Engine across the Cartesian product of requested symbols, current timeframes, and higher timeframes, then aggregates behavior and returns diagnostic recommendations.

Request:

```json
{
  "symbols": ["BTC-USD", "EUR-USD"],
  "timeframes": ["5m"],
  "higher_timeframes": ["1h"],
  "lookback": 300,
  "max_trades_per_run": 25,
  "risk_per_trade_percent": 1.0,
  "starting_balance": 10000,
  "execution_profile": {
    "spread": 0.0001,
    "slippage": 0.00005,
    "slippage_type": "random",
    "commission_per_trade": 0.01,
    "commission_type": "percent",
    "fill_model": "touch",
    "random_seed": 42
  }
}
```

Calibration passes an optional execution profile to every run and returns `aggregate_execution_summary`. Existing requests without the field remain valid and report zero modeled fills.

Response shape:

```json
{
  "runs": [
    {
      "symbol": "EUR-USD",
      "normalized_symbol": "EURUSD=X",
      "timeframe": "5m",
      "higher_timeframe": "1h",
      "total_records": 25,
      "total_skipped": 20,
      "total_open": 1,
      "metrics": {
        "total_trades": 4,
        "wins": 2,
        "losses": 2,
        "breakeven": 0,
        "win_rate": 50.0,
        "average_r": 0.5,
        "total_r": 2.0,
        "profit_factor": 2.0,
        "max_drawdown_r": 1.0
      },
      "human_readable_summary": "Historical run summary."
    }
  ],
  "aggregate_metrics": {
    "total_runs": 2,
    "total_trades": 8,
    "total_skipped": 40,
    "wins": 4,
    "losses": 4,
    "breakeven": 0,
    "win_rate": 50.0,
    "average_r": 0.5,
    "total_r": 4.0,
    "profit_factor": 2.0,
    "max_drawdown_r": 2.0
  },
  "aggregate_skip_diagnostics": {
    "total_skipped": 40,
    "by_reason_code": {
      "decision_not_actionable": 30,
      "setup_not_confirmed": 10
    },
    "by_blocking_engine": {
      "decision_engine": 30,
      "setup_engine": 10
    },
    "most_common_reason": "decision_not_actionable",
    "human_readable_summary": "40 records were skipped; the most common reason was decision not actionable, primarily blocked by decision engine."
  },
  "aggregate_decision_diagnostics": {
    "by_confidence_band": {"avoid": 8, "wait": 32},
    "by_blocked_gate": {"directional_confidence": 40},
    "average_confidence": 61.8,
    "average_raw_score": 61.77,
    "most_common_blocked_gate": "directional_confidence",
    "human_readable_summary": "40 decision snapshots averaged 61.8/100; the most common blocked gate was directional confidence (40 records)."
  },
  "threshold_sensitivity": [
    {
      "threshold": 50.0,
      "directionally_eligible": 120,
      "execution_ready": 8,
      "missing_setup": 30,
      "missing_levels": 24,
      "risk_reward_failed": 28,
      "setup_not_confirmed": 25,
      "strategy_not_aligned": 5,
      "still_blocked": 80,
      "estimated_trade_candidates": 8,
      "human_readable_summary": "At 50 confidence, 120 records are directionally eligible, 8 have execution-ready snapshots, and 8 pass both."
    }
  ],
  "aggregate_risk_reward_summary": {
    "total_records": 200,
    "complete_level_records": 176,
    "missing_entry_count": 8,
    "missing_stop_count": 10,
    "missing_target_count": 6,
    "invalid_geometry_count": 4,
    "below_minimum_r_count": 112,
    "average_estimated_r": 1.18,
    "median_estimated_r": 1.21,
    "records_near_threshold_1_2_to_1_5": 37,
    "records_above_1_5": 60,
    "by_failure_reason": {"target_too_close": 70, "stop_too_wide": 42},
    "most_common_failure_reason": "target_too_close",
    "human_readable_summary": "200 records produced 176 complete level sets; 60 met 1.5R and 112 were below the minimum."
  },
  "aggregate_setup_level_summary": {
    "total_records": 200,
    "complete_level_records": 176,
    "partial_level_records": 18,
    "missing_level_records": 6,
    "invalid_level_records": 4,
    "missing_entry_count": 8,
    "missing_stop_count": 10,
    "missing_target_count": 6,
    "by_level_quality": {"complete": 176, "invalid": 4, "missing": 6, "partial": 18},
    "most_common_level_quality": "complete",
    "human_readable_summary": "200 setup snapshots include 176 complete, 18 partial, 6 missing, and 4 invalid level sets."
  },
  "aggregate_outcome_diagnostics": {
    "executed_trades": 3,
    "wins": 1,
    "losses": 2,
    "average_bars_to_outcome": 4.333,
    "average_mfe_r": 2.159,
    "average_mae_r": 0.904,
    "by_loss_reason": {"adverse_move_before_follow_through": 1, "stop_too_tight": 1},
    "same_candle_ambiguity_count": 0,
    "stopped_immediately_count": 0,
    "no_follow_through_count": 0,
    "human_readable_summary": "3 executed trades produced 1 win and 2 losses, with average MFE 2.16R."
  },
  "aggregate_trade_management_sensitivity": [
    {
      "rule": "none",
      "simulated_trades": 3,
      "wins": 1,
      "losses": 2,
      "breakeven": 0,
      "average_r": 0.167,
      "total_r": 0.5,
      "profit_factor": 1.25,
      "max_drawdown_r": 1.0,
      "improved_vs_baseline": false,
      "human_readable_summary": "None produces 0.50R across 3 closed trades versus 0.50R baseline."
    },
    {
      "rule": "trail_after_1r",
      "simulated_trades": 3,
      "wins": 2,
      "losses": 1,
      "breakeven": 0,
      "average_r": 0.583,
      "total_r": 1.75,
      "profit_factor": 2.75,
      "max_drawdown_r": 1.0,
      "improved_vs_baseline": true,
      "human_readable_summary": "Trail After 1R produces 1.75R across 3 closed trades versus 0.50R baseline."
    }
  ],
  "setup_performance": [],
  "strategy_performance": [],
  "recommendations": [
    {
      "category": "setup_quality",
      "message": "80% of calibration records were skipped.",
      "severity": "medium",
      "suggested_action": "Review which required setup conditions most often remain unmet."
    }
  ],
  "human_readable_summary": "Calibration completed 2 runs with 8 closed trades, 40 skipped records, and 4.00R aggregate performance.",
  "limitations": [
    "Recommendations identify historical patterns for inspection; they do not tune weights automatically."
  ]
}
```

Calibration combinations are capped at 100 per request. Recommendations use `decision_threshold`, `setup_quality`, `strategy_selection`, `risk_reward`, `market_structure`, or `data_quality` categories with low, medium, or high severity.

`threshold_sensitivity` always evaluates `[50, 55, 60, 65, 70]` without changing production decisions. Counts use existing backtest snapshots; `estimated_trade_candidates` is directional eligibility intersected with observed execution readiness, not a simulated outcome or profitability estimate.

Risk/reward summaries calculate R from parsed geometry rather than trusting a supplied ratio. The report preserves the current `1.5R` minimum and is intended to identify the next controlled level-generation or threshold experiment.

As of v1.6, public price strings preserve instrument precision: supported non-JPY forex pairs use five decimals, crypto uses two decimals, and the default uses two. Internal estimated R is calculated from numeric levels before formatting.

Calibration is deterministic for the same data and engine versions. It observes historical behavior and suggests areas to inspect; it does not optimize or change application logic automatically.

## Contract Evolution

The `/analysis` response now exposes both architectural layers:

- `multi_timeframe`, `decision`, `setup_plan`, and `strategy` preserve detailed internal engine output.
- `trader_analysis` translates those results into a readable narrative and checklist plan.

The trader-facing block does not recalculate action, confidence, setup qualification, or strategy ranking. Evidence and checklist states remain traceable to typed engine output. Journal, backtest, and calibration endpoints consume, replay, or aggregate these contracts without changing `/analysis` request or response behavior.

## v1.9 Additive Setup Coverage Fields

`setup_plan.setup_candidate_diagnostics` and each backtest trade expose candidate type, direction, selection flag, status, level completeness, geometry validity, estimated R, minimum-R result, blocker, quality, and summary. `/backtest` adds `setup_coverage_summary`; `/calibrate` adds `aggregate_setup_coverage_summary` with counts and per-family records. These fields are observational and do not change the selected setup, strategy, or execution result.

In v2.0, an executable non-selected BOS or sweep candidate may report `stronger_candidate_selected`. It remains executable for coverage and missed-candidate totals; the code records comparative selection rather than a failed execution-quality gate. Existing field shapes are unchanged.
