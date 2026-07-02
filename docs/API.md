# StructureIQ API

## Overview

StructureIQ `6.0.3` exposes a FastAPI HTTP interface for analysis, controlled continuous paper sessions, end-to-end validation, local system observability, local report scheduling, controlled paper orchestration, daily paper reporting, automated paper journaling, simulated paper-account and lifecycle management, simplified backtesting, observational calibration, continuous monitoring, continuous research, and compact research dashboards. The API provides market intelligence only. It does not expose endpoints for real broker authentication, live order placement, or live position management.

## Application Launcher

The official local startup entry point is:

```powershell
python start.py
```

The launcher performs environment checks, prints the current version, writes `logs/startup.log`, displays reserved future components as `NOT ENABLED`, and starts the unchanged FastAPI application through:

```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Supported launcher commands:

| Command | Behavior |
| --- | --- |
| `python start.py` | Run health checks, display the startup banner, and launch the API. |
| `python start.py --api` | Start only the API process after validation. |
| `python start.py --version` | Print the version from `app/config.py` and exit. |
| `python start.py --health` | Validate Python, folders, files, packages, config import, and `app.main` import without launching uvicorn. |
| `python start.py --urls` | Print browser-facing localhost URLs and exit. |
| `python start.py --open-browser` | Start normally and attempt to open local Swagger; failure is warning-only. |
| `python start.py --paper --hours 2` | Start the API, validate it, and run a two-hour paper-only session. |
| `python start.py --paper --cycles 20` | Run a paper-only session capped at 20 completed cycles. |
| `python start.py --help` | Display launcher options. |

Browser-facing output always uses `http://localhost:8000`. Uvicorn still displays and binds `0.0.0.0`, which means it listens on local interfaces; users should use localhost in a browser. Paper CLI duration options include `--minutes`, `--hours`, `--days`, `--weeks`, and `--months` (30 days), plus `--cycles` and `--label`. Multiple duration flags select the shortest and print a warning. Validation WATCHLIST is allowed; FAIL blocks startup. Ctrl+C explicitly stops the continuous runtime before terminating the local API.

The launcher is not an API endpoint and does not modify request or response contracts.

## Research Dashboard API

Version 4.3 adds dashboard-friendly read-only endpoints under the `dashboard` OpenAPI tag. They summarize existing research artifacts and the latest completed process-local calibration snapshot. They do not rerun calibration, mutate symbol profiles, alter strategy routing, or change any production trade behavior.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/dashboard/overview` | Current version, latest research status, headline metrics, best categories, readiness, and major warnings. |
| `GET` | `/dashboard/symbols` | Ranked persisted symbol profiles from `research/symbol_profiles.json` when available. |
| `GET` | `/dashboard/strategies` | Compact rows from the latest `strategy_rating_summary`. |
| `GET` | `/dashboard/setups` | Compact rows from the latest `setup_rating_summary`. |
| `GET` | `/dashboard/readiness` | Conservative paper-trading readiness from promotion readiness, OOS, Monte Carlo, statistical validation, confidence calibration, symbol profiles, and adaptive routing. |
| `GET` | `/dashboard/risks` | Overfit, drawdown, low-sample, confidence, calibration, provider, and data-availability warnings. |
| `GET` | `/dashboard/recommendations` | Prioritized advisory action items combined from calibration, research, ratings, confidence, profiles, adaptive routing, statistical validation, and Monte Carlo findings. |

If `/calibrate` has not completed since service startup, dashboard endpoints return controlled unavailable summaries. After restart, they can still read persisted symbol profiles and the process-local continuous research store when those sources are available, but they do not persist or reload the full calibration result.

Example `/dashboard/overview` response:

```json
{
  "app_version": "6.0.3",
  "latest_research_status": "No completed calibration research is available yet.",
  "total_symbols_profiled": 0,
  "best_symbol": null,
  "best_strategy": null,
  "best_setup": null,
  "aggregate_win_rate": null,
  "aggregate_expectancy": null,
  "aggregate_total_r": null,
  "aggregate_profit_factor": null,
  "aggregate_drawdown": null,
  "paper_trading_readiness": "UNAVAILABLE",
  "major_warnings": [],
  "human_readable_summary": "Dashboard is unavailable until calibration or symbol-profile research exists."
}
```

Example `/dashboard/readiness` response:

```json
{
  "paper_trading_status": "NEEDS_MORE_DATA",
  "readiness_score": 45,
  "blocking_reasons": ["Fewer than 100 completed validation trades are available."],
  "watchlist_reasons": ["Minimum validation sample has not reached 100 trades."],
  "minimum_data_requirements": [
    "At least 100 completed validation trades for paper-trading consideration.",
    "300 validation trades is strong; 500+ is excellent.",
    "Monte Carlo and statistical validation must not block readiness."
  ],
  "current_sample_summary": "42 validation trades; 58 completed calibration trades.",
  "out_of_sample_status": "available",
  "monte_carlo_status": "unavailable",
  "statistical_validation_status": "unavailable",
  "confidence_calibration_status": "available",
  "symbol_profile_status": "available",
  "adaptive_router_status": "available",
  "human_readable_summary": "Paper-trading readiness is NEEDS_MORE_DATA. This dashboard is advisory and cannot change production behavior."
}
```

Interactive OpenAPI documentation is available at `/docs` and the machine-readable schema at `/openapi.json` when the service is running. Public endpoints use explicit response models; validation failures use FastAPI's standard `422` detail format. `/analysis` and `/backtest` provider failures return `503`; `/calibrate` isolates failures per run and returns availability diagnostics.

## Live Market Monitor

The monitor is disabled by default and starts only through `POST /monitor/start`. `POST /monitor/run-once` performs one synchronous cycle; `POST /monitor/stop` is idempotent. `GET /monitor/status` reports configuration, running state, cycle/signal/error counts, last cycle, last signal, and last error. `GET /monitor/events` returns bounded recent candidate events.

Both run-once and start accept an optional `MonitorConfig` body. Defaults monitor BTC-USD, ETH-USD, EUR-USD, and GBP-USD on 5m with 1h context, 300 candles, a 60-second poll, 500 in-memory events, and append-only `research/live_monitor_events.jsonl` output. The event file is ignored by Git.

Events include the candle identity, unchanged action/setup/strategy, confidence, setup quality, score, execution guidance, levels, and reasons. A process-lifetime key of symbol, timeframe, candle timestamp, action, and setup prevents duplicates. Only actionable confirmed buy/sell results emit events; every event remains `status: candidate` and `paper_trade_created: false`. Provider errors are isolated per market and never create trades.

## Paper Brokerage Engine

The paper brokerage is an in-memory simulation and is never connected to a real broker. `GET /paper/account` returns balance, equity, realized/unrealized P/L, counts, R performance, drawdown, and risk status. `POST /paper/reset` accepts optional account configuration. `GET /paper/open-positions`, `/paper/closed-trades`, and `/paper/performance` expose the simulated lifecycle. Optional `latest_prices` is a JSON query object used only for deterministic mark-to-market.

`POST /paper/open` accepts either complete explicit trade fields or a single recent monitor `event_id`. Explicit trades require symbol, timeframes, buy/sell action, setup, strategy, entry, stop, and target. Event opens parse the candidate entry midpoint, stop, and target; successful opens mark the event `paper_trade_created=true`. Nothing consumes monitor candidates automatically.

Position risk equals current balance multiplied by the requested risk percentage. Position size is risk amount divided by entry-to-stop distance. Buy geometry requires `stop < entry < target`; sell geometry requires `target < entry < stop`. Per-trade maximum risk, daily loss, daily profit lock, maximum positions, duplicate symbol, and duplicate setup gates are enforced before opening. `POST /paper/close` accepts `trade_id` and `exit_price`, then updates balance and realized R/P&L.

Paper state is process-local. Supplying `persistence_path` in account configuration writes a non-sensitive JSON snapshot; `research/paper_account_state.json` is ignored by Git. Dashboard output remains advisory and reports `paper_trading_enabled=false`; the lifecycle manager does not enable automated paper trading.

## Trade Lifecycle Manager

The lifecycle manager is paper-only and disabled for automatic consumption by default. `POST /lifecycle/approve-candidate` accepts a recent monitor `event_id`, an order type (`market`, `limit_retest`, or `confirmation_close`), and optional paper-risk percentage. Manual approval validates action, levels, and directional geometry, then creates a pending order. Market orders explicitly open through Paper Brokerage immediately; other types wait for `POST /lifecycle/run-once` candle evidence.

Each run-once cycle evaluates pending fills, increments deterministic expiry counters, and checks lifecycle-managed open paper positions against the latest candle. If stop and target are both touched, the trade closes at the stop and records same-candle ambiguity. Optional break-even and trailing rules emit advisory eligibility states only; they do not mutate brokerage stops.

Additional endpoints expose status, lifecycle events, pending orders, managed open/closed trades, manual rejection, and cancellation. Default configuration requires manual approval, expires pending orders after three evaluated candles, disables automatic monitor consumption, and bounds event memory at 1,000 transitions. Dashboard output includes lifecycle counters, state, and warnings. Paper Brokerage remains the sole account and P/L authority.

## Automated Paper Trade Journal

`PaperTradeJournal` subscribes to paper-brokerage open/close notifications and lifecycle events. It captures planned and actual levels, balance snapshots, risk and size, realized outcomes, close reason, lifecycle history, warnings, violations, and available monitor research context including setup quality, score, confidence calibration, ratings, symbol profile, adaptive routing, and execution intelligence.

Every update appends a full latest snapshot to `research/paper_trade_journal.jsonl`; existing lines are never rewritten. API reads reconstruct the newest view per trade. `GET /paper-journal/entries`, `/summary`, and `/trade/{trade_id}` expose current views. `POST /paper-journal/rebuild-from-paper-state` replays current brokerage and lifecycle state, while `/export` returns compact JSON-compatible trade data and daily-report readiness.

Journal summaries report counts, win rate, R and cash P/L, best/worst trades, setup and strategy groupings, average setup quality, warnings, and rule violations. Dashboard overview, risks, and recommendations surface journal availability and review needs. Journal observers are advisory and cannot fail, reverse, or alter authoritative paper actions.

## Daily Paper Trading Reports

`POST /reports/daily/generate` accepts `report_date` and `overwrite=false`. Reports are saved to `reports/daily/YYYY-MM-DD.json`; existing files return a conflict unless overwrite is explicitly true. `GET /reports/daily` lists saved artifacts, while `GET /reports/daily/{report_date}` returns one report.

Status is `NO_TRADES` when no open or closed trades exist, `PASS` for positive closed R without warnings, violations, open risk, or critical state, `WATCHLIST` for unresolved warnings/open risk/flat or negative performance, and `FAIL` for violations, system errors, critical account risk, or severe drawdown. Reports include trades, open positions, monitor/lifecycle/journal summaries, available execution-cost and setup-quality research, risk/readiness context, findings, and recommended actions.

`POST /reports/daily/export-gpt-payload` returns compact metrics, trades, warnings, violations, and review questions suitable for future automation. It does not contact GPT, send email, use a network, or modify any paper or production state. Dashboard overview, readiness, risks, and recommendations expose the latest saved report status.

## End-to-End Paper Trading Orchestrator

`POST /paper-trading/run-cycle` runs one synchronous monitor → candidate review → lifecycle → brokerage → journal → report cycle. Defaults are disabled and observe-only: `auto_approve_candidates=false`, `require_manual_approval=true`, and market orders are disallowed. Manual approval remains available through lifecycle APIs.

Auto-approval requires explicit `auto_approve_candidates=true` and `require_manual_approval=false`. Candidates must be buy/sell, carry eligible setup quality, have valid risk geometry, contain no execution blockers, remain unused, and pass Paper Brokerage risk/position/duplicate rules. D/F or missing quality is blocked unless missing quality is explicitly permitted. Candidate and new-trade caps apply per cycle.

`POST /paper-trading/start` and `/stop` control an opt-in daemon loop. Repeated errors pause it at the configured threshold. Status, recent cycles, and approval/block actions are available through GET endpoints. Optional cycle persistence appends to `reports/paper_trading_cycles.jsonl`. Dashboard views expose orchestrator state, counts, and warnings. No cycle can access a real broker, GPT, email, or production decision path.

## Scheduled Daily Report Automation

`POST /reports/scheduler/run-now` generates the previous day in the configured timezone by default or accepts an explicit `report_date`. Its optional `overwrite` value overrides scheduler policy for that run. Existing reports are returned as `skipped_existing` unless overwrite is enabled.

`POST /reports/scheduler/start` and `/stop` control a local daemon scheduler; it never auto-starts with the API. `GET /reports/scheduler/status` reports running, enabled, paused, last/next run, last report, counts, and errors. `/history` returns append-only run records stored in `reports/daily_scheduler_history.jsonl`. The default is 06:00 America/Chicago, previous day, weekends included, and overwrite disabled. Repeated failures pause scheduling. Dashboard responses expose scheduler readiness and warnings. No external service, GPT, email, broker, or trading call exists.

## Continuous Autonomous Paper Trading

`GET /continuous-paper/status` reports runtime and session counters. `POST /continuous-paper/start`, `/stop`, `/pause`, and `/resume` provide explicit controls; `POST /continuous-paper/run-once` executes exactly one guarded orchestrator cycle. `/continuous-paper/events` and `/sessions` expose bounded local state backed by append-only JSONL.

The runtime is disabled and stopped by default. It delegates cycles to `PaperTradingOrchestrator`, permits WATCHLIST validation only when configured, and can pause on validation failure, health failure, paper daily limits, or accumulated errors. It remains paper-only and cannot call a broker, GPT, email, or live execution.

Optional start controls are `run_for_minutes`, `run_for_hours`, `max_cycles`, and `session_label`. When multiple limits are supplied, the first reached completes the session. Status adds `estimated_stop_at`, `remaining_seconds`, configured limits, `stop_reason`, and `final_session_summary`. Automatic completion uses `duration_limit_reached` or `max_cycles_reached`; manual stop uses `manual_stop`, while safety and error pauses remain resumable.

```json
{
  "run_for_minutes": 30,
  "max_cycles": 20,
  "session_label": "30-minute validation run"
}
```

## End-to-End System Validation

- `GET /system/validation` returns the latest completed validation or `null` before the first run.
- `POST /system/validation/run` executes every component check independently and returns timed PASS/WATCHLIST/FAIL results.
- `GET /system/validation/history` reads append-only local history.
- `POST /system/validation/reset-history` clears local history and process-local latest state.

Validation uses synthetic in-memory market data and isolated temporary paper state. It does not call external providers, brokers, GPT, email, or live execution. `python start.py --validate` runs the same endpoint and returns exit code 0 for PASS, 1 for WATCHLIST, or 2 for FAIL.

## System Health and Observability

`GET /system/health` returns the complete graded report with uptime, dimensions, warnings, blockers, operational readiness, and recommended actions. Dimensions cover application, configuration, provider wiring, monitor, paper brokerage, lifecycle, journal, daily reports, scheduler, orchestrator, dashboard, storage, logs, research files, reports, and a deliberately unavailable runtime test placeholder.

`GET /system/readiness` returns compact paper operational readiness. `/errors` aggregates known monitor, lifecycle, scheduler, and orchestrator errors. `/storage` verifies or creates required local folders and tests write access with immediately removed probes. `/components` lists dimension results. Optional missing state files are allowed; inaccessible storage, corrupted paper-account JSON, required import failure, or an error-paused orchestrator can fail health.

Every full check appends to `logs/system_health.jsonl`. Health endpoints do not fetch candles, invoke analysis, advance paper state, generate reports, contact external services, or trade. Dashboard overview, readiness, risks, and recommendations reflect the latest completed health snapshot.

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

### Provider availability and partial completion

Version 3.1.1 treats each symbol/current-timeframe/higher-timeframe combination as an independent data request. If Yahoo or another provider fails one combination, calibration continues with the remaining combinations and returns HTTP `200` with additive fields:

- `provider_failures`: structured symbol, normalized symbol, timeframe, higher timeframe, provider, message, failure type, and `skipped: true` records.
- `failed_runs`: number of combinations that could not obtain market data.
- `data_availability_summary`: requested, completed, and failed run counts; completion rate; all-failed flag; and plain-English summary.

`runs` and `aggregate_metrics.total_runs` include completed runs only. Provider failures never become trades and therefore cannot affect closed trades, win rate, R, drawdown, setup/strategy performance, or research statistics. If every combination fails, the response remains a valid calibration result with zero completed runs and a clear `all_runs_failed` availability summary.

The Yahoo chart adapter caps ranges before requesting intraday data: `1m` to `7d`, `5m`, `15m`, and `30m` to `1mo`, and `1h` to `2y`. Daily requests keep the pre-v3.1.1 selection behavior. Provider errors include the requested and normalized symbols, timeframe, Yahoo interval, lookback, selected range, and capped range for diagnosis.

### Execution Sensitivity Laboratory

Add `execution_sensitivity_profiles` to compare scenarios without changing the ordinary calibration result. Perfect execution is inserted automatically, so callers should send only the scenarios they want to compare:

```json
{
  "symbols": ["EUR-USD", "GBP-USD"],
  "timeframes": ["5m"],
  "higher_timeframes": ["1h"],
  "lookback": 300,
  "max_trades_per_run": 50,
  "risk_per_trade_percent": 1.0,
  "starting_balance": 10000,
  "execution_sensitivity_profiles": [
    {
      "name": "forex_spread_only_mild",
      "description": "Illustrative one-pip spread-only scenario.",
      "execution_profile": {"spread": 0.0001}
    },
    {
      "name": "forex_mild_realistic",
      "description": "Illustrative mild combined Forex scenario.",
      "execution_profile": {
        "spread": 0.0001,
        "slippage": 0.00005,
        "slippage_type": "random",
        "commission_per_trade": 2.0,
        "commission_type": "fixed",
        "random_seed": 42
      }
    }
  ]
}
```

Crypto scenarios use instrument price units rather than Forex values:

```json
{
  "symbols": ["BTC-USD", "ETH-USD"],
  "timeframes": ["5m"],
  "higher_timeframes": ["1h"],
  "lookback": 300,
  "max_trades_per_run": 50,
  "risk_per_trade_percent": 1.0,
  "starting_balance": 10000,
  "execution_sensitivity_profiles": [
    {
      "name": "crypto_slippage_only_mild",
      "description": "Illustrative seeded slippage-only scenario.",
      "execution_profile": {
        "slippage": 1.0,
        "slippage_type": "random",
        "random_seed": 42
      }
    },
    {
      "name": "crypto_moderate_realistic",
      "description": "Illustrative moderate combined Crypto scenario.",
      "execution_profile": {
        "spread": 5.0,
        "slippage": 2.5,
        "slippage_type": "random",
        "commission_per_trade": 0.05,
        "commission_type": "percent",
        "fill_model": "next_bar",
        "random_seed": 42
      }
    }
  ]
}
```

`execution_sensitivity_summary` contains `profiles`, `best_profile`, `worst_profile`, `largest_expectancy_drop_profile`, `most_sensitive_cost_component`, a readable summary, and recommendations. Every profile result includes outcomes, expectancy, R metrics, drawdown, and average costs. Scenario runs never replace `aggregate_metrics` or `aggregate_execution_summary`.

### Entry Timing Laboratory

Add `entry_timing_profiles` to compare alternative entries over the same already-valid candidate set. Immediate production timing is inserted automatically.

Forex example:

```json
{
  "symbols": ["EUR-USD", "GBP-USD"],
  "timeframes": ["5m"],
  "higher_timeframes": ["1h"],
  "lookback": 300,
  "max_trades_per_run": 50,
  "risk_per_trade_percent": 1.0,
  "starting_balance": 10000,
  "entry_timing_profiles": [
    {
      "name": "forex_next_bar",
      "description": "Enter at the next candle open.",
      "entry_model": "next_bar_open",
      "allow_missed_entries": false,
      "max_wait_bars": 3,
      "require_touch": false
    },
    {
      "name": "forex_quarter_pullback",
      "description": "Wait 25% toward the original stop.",
      "entry_model": "quarter_pullback_from_entry_to_stop",
      "allow_missed_entries": true,
      "max_wait_bars": 5,
      "require_touch": true
    }
  ]
}
```

Crypto example:

```json
{
  "symbols": ["BTC-USD", "ETH-USD"],
  "timeframes": ["5m"],
  "higher_timeframes": ["1h"],
  "lookback": 300,
  "max_trades_per_run": 50,
  "risk_per_trade_percent": 1.0,
  "starting_balance": 10000,
  "entry_timing_profiles": [
    {
      "name": "crypto_signal_close",
      "description": "Use the signal candle close.",
      "entry_model": "signal_close",
      "allow_missed_entries": false,
      "max_wait_bars": 3,
      "require_touch": false
    },
    {
      "name": "crypto_conservative_limit",
      "description": "Prefer an improved limit and allow misses.",
      "entry_model": "conservative_limit",
      "allow_missed_entries": true,
      "max_wait_bars": 8,
      "require_touch": true,
      "random_seed": 42
    }
  ]
}
```

`entry_timing_summary` includes profile results and names the best, worst, best-expectancy, highest-fill-rate, best risk-adjusted, and most-missed profiles. Each result reports candidate and fill counts, outcomes, R metrics, entry improvement, delay, missed-opportunity R, and fallback count. Timing runs do not replace production calibration fields.

### Market Regime Laboratory

Every `/analysis` response now includes an additive `market_regime` object:

```json
{
  "market_regime": "strong_bear_trend",
  "regime_confidence": 91.0,
  "regime_reasons": [
    "Confirmed swing structure is bearish.",
    "Multi-timeframe structure is directionally aligned.",
    "A recent break of structure supports the trend."
  ],
  "human_readable_summary": "Market regime is strong bear trend with 91/100 confidence."
}
```

Enable regime research during calibration:

```json
{
  "symbols": ["BTC-USD", "ETH-USD", "EUR-USD", "GBP-USD"],
  "timeframes": ["5m"],
  "higher_timeframes": ["1h"],
  "lookback": 300,
  "max_trades_per_run": 50,
  "risk_per_trade_percent": 1.0,
  "starting_balance": 10000,
  "market_regime_analysis": true
}
```

Enabled responses add `market_regime_summary`, `strategy_regime_matrix`, and `setup_regime_matrix`. The summary includes every regime category, headline rankings, and research recommendations. Matrix rows expose `strategy_type` or `setup_type` plus `performance_by_regime`. When the flag is false, all three optional fields are null and ordinary calibration behavior is unchanged.

### Regime Validation Laboratory

Regime validation is enabled independently:

```json
{
  "symbols": ["BTC-USD", "ETH-USD", "EUR-USD", "GBP-USD"],
  "timeframes": ["5m"],
  "higher_timeframes": ["1h"],
  "lookback": 300,
  "max_trades_per_run": 200,
  "risk_per_trade_percent": 1.0,
  "starting_balance": 10000,
  "regime_validation_analysis": true
}
```

The additive `regime_validation_summary` contains:

- Classification distribution and transition dominance.
- Average confidence and confidence by regime.
- Consecutive-label persistence statistics.
- Forward behavior at 5, 10, and 20 bars.
- Transition destination counts and average exit time.
- Predicted-versus-proxy actual counts.
- Dominant failure modes and recommendations.

Transition is flagged as overused above 60%. Records without enough forward candles are counted in `insufficient_forward_records`; they are never silently dropped from the classification distribution. Forward proxy categories are deterministic approximations and must not be interpreted as labeled regime truth.

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

## v2.6 Regime Classifier Tuning Laboratory

Add the optional calibration flag without changing any other request field:

```json
{
  "symbols": ["BTC-USD", "ETH-USD", "EUR-USD", "GBP-USD"],
  "timeframes": ["5m"],
  "higher_timeframes": ["1h"],
  "lookback": 300,
  "max_trades_per_run": 50,
  "risk_per_trade_percent": 1.0,
  "starting_balance": 10000,
  "regime_tuning_analysis": true
}
```

When enabled, `/calibrate` adds `regime_tuning_summary`. It contains current distribution and dominance, normalized overuse and underclassification scores, evidence score averages, transition reasons and staleness counts, confidence and margin summaries, forward stability, five transition-threshold simulations, four isolated trend-evidence simulations, plain-English findings, and recommendations.

When the flag is omitted or false, the laboratory does not run and the additive optional summary is null. `/analysis` has no new request or response fields: its internal tuning evidence is explicitly excluded from serialization. No simulated classification changes a production label, trade, metric, or existing laboratory result.

## v2.7 Regime Classifier Modes

`POST /calibrate` accepts the optional field `regime_classifier_mode` with values `legacy`, `tuned`, or `compare`. Its default is `legacy`.

```json
{
  "symbols": ["BTC-USD", "ETH-USD", "EUR-USD", "GBP-USD"],
  "timeframes": ["5m"],
  "higher_timeframes": ["1h"],
  "lookback": 300,
  "max_trades_per_run": 50,
  "risk_per_trade_percent": 1.0,
  "starting_balance": 10000,
  "regime_classifier_mode": "compare"
}
```

Compare mode adds `legacy_market_regime_summary`, `tuned_market_regime_summary`, and `regime_classifier_comparison`. The comparison includes legacy/tuned transition ratios, transition reduction, trend counts, changed and agreed labels, transition destination counts, a summary, and recommendations.

The `/analysis` request and serialized response are unchanged. Tuned labels are internal research metadata and are excluded from ordinary `/analysis` and `/backtest` payloads. Classifier mode cannot change aggregate calibration metrics or any trade outcome.

## v2.8 Tuned Regime Forward Validation

Forward validation runs only when both conditions are present:

```json
{
  "symbols": ["BTC-USD", "ETH-USD", "EUR-USD", "GBP-USD"],
  "timeframes": ["5m"],
  "higher_timeframes": ["1h"],
  "lookback": 300,
  "max_trades_per_run": 50,
  "risk_per_trade_percent": 1.0,
  "starting_balance": 10000,
  "regime_classifier_mode": "compare",
  "forward_validation": true
}
```

The response adds `legacy_forward_validation`, `tuned_forward_validation`, and `forward_validation_comparison`. Classifier results contain accuracy, precision, recall, F1, confidence, directional and per-regime accuracy, full confusion matrices, confidence-reliability buckets, persistence, and statistical summaries for 5/10/20-bar behavior.

Each accuracy metric includes its sample size, standard deviation, and approximate 95% confidence interval. Horizon statistics include directional return, MFE/MAE, continuation, reversal, volatility expansion, range persistence, and trend persistence. Flags may include `LOW_SAMPLE`, `HIGH_CONFIDENCE`, and `INSUFFICIENT_DATA`.

If either condition is absent, the optional fields are null and validation does not run. The future-behavior snapshot is excluded from `/backtest`; `/analysis` and `/backtest` schemas and payloads are unchanged.

## v2.9 Regime Confidence Calibration Laboratory

Confidence analysis requires compare-mode forward validation:

```json
{
  "symbols": ["BTC-USD", "ETH-USD", "EUR-USD", "GBP-USD"],
  "timeframes": ["5m"],
  "higher_timeframes": ["1h"],
  "lookback": 300,
  "max_trades_per_run": 50,
  "risk_per_trade_percent": 1.0,
  "starting_balance": 10000,
  "regime_classifier_mode": "compare",
  "forward_validation": true,
  "regime_confidence_analysis": true
}
```

The additive `regime_confidence_summary` contains legacy and tuned reliability buckets, ECE and MCE in percentage points, Brier scores on `0–1` probabilities, reliability curves, confidence histograms and percentiles, over/underconfidence flags, five deterministic mapping simulations, a tuned mapping recommendation, and legacy-versus-tuned calibration deltas.

Every mapping reports `classification_unchanged: true` and `expected_routing_unchanged: true`. Mappings are fitted and scored diagnostically on the supplied sample; none is applied to analysis output or any engine. If confidence analysis is omitted, false, or requested without compare-mode forward data, the summary remains null.

## v3.0 Out-of-Sample Validation Framework

```json
{
  "symbols": ["BTC-USD", "ETH-USD", "EUR-USD", "GBP-USD"],
  "timeframes": ["5m", "15m"],
  "higher_timeframes": ["1h"],
  "lookback": 300,
  "max_trades_per_run": 50,
  "starting_balance": 10000,
  "risk_per_trade_percent": 1.0,
  "out_of_sample_validation": true,
  "validation_method": "walk_forward",
  "training_percent": 70,
  "validation_percent": 30,
  "validation_folds": 5
}
```

`validation_method` accepts `chronological`, `rolling_window`, `walk_forward`, `expanding_window`, or `anchored`. Percentages must be positive and cannot total more than 100; folds range from 1 to 20. Candles are never shuffled.

When enabled, `/calibrate` adds `out_of_sample_summary`, `validation_fold_results`, `generalization_summary`, `overfitting_summary`, `stability_summary`, `symbol_validation_summary`, `timeframe_validation_summary`, and `research_recommendations`.

Each fold reports separate training and validation measurements for trades, win rate, R, profit factor, drawdown, expectancy, MFE/MAE, duration, skips, confidence, setup, strategy, regime, execution degradation, and trade-management sensitivity. The generalization report adds decay, drift, variance, stability, and overfit risk. When disabled, all additive fields remain null and ordinary calibration follows its established path.

Validation segments use prior raw candles only as indicator/structure warm-up context. Every fold creates a fresh backtester and reruns the complete production pipeline; no cached decision, setup, or trade state crosses the split.

Version 3.0.1 also exposes this OOS request as a first-class OpenAPI example. When `out_of_sample_validation` is true, calibration now enforces a response invariant: all eight OOS sections must be populated rather than failing silently. Clients running an older long-lived application process must restart it to load the v3.0.1 schema and implementation.

### v3.2 Research Pipeline and Walk-Forward Intelligence

When `out_of_sample_validation` is `true`, calibration also returns:

- `research_pipeline_summary`
- `walk_forward_intelligence_summary`
- `strategy_robustness_rankings`
- `promotion_readiness_summary`
- `research_action_items`

The pipeline combines finalized aggregate calibration metrics, statistical research summaries and matrices, OOS measurements, folds, generalization, overfitting, stability, and symbol/timeframe validation. Rankings cover observed symbols, timeframes, setups, strategies, regimes, symbol/timeframe/setup combinations, and symbol/timeframe/strategy combinations. Every row reports training and validation trades, expectancy and decay, validation win rate and profit factor, maximum validation drawdown, fold consistency, robustness, sample quality, readiness, and a plain-English conclusion.

Readiness is conservative: fewer than 100 validation trades is `NEEDS_MORE_DATA` for a positive edge and can never become `READY_FOR_PAPER_TRADING`. Samples of 100, 300, and 500 trades are labeled acceptable, strong, and excellent respectively. Negative expectancy, weak fold consistency, high variance, excessive drawdown, high/overfit risk, or category dependency reduces robustness and readiness.

Statuses are research workflow labels only: `NOT_READY`, `NEEDS_MORE_DATA`, `WATCHLIST`, `READY_FOR_REVIEW`, and `READY_FOR_PAPER_TRADING`. Paper-trading readiness means a result may be submitted for a separately authorized, controlled paper-trading design. It does not enable paper trading, alter production behavior, or authorize a live trade.

When OOS validation is omitted or false, all five v3.2 fields are `null`.

### v3.3 Monte Carlo Simulation Engine

Add these optional calibration fields:

```json
{
  "monte_carlo_analysis": true,
  "monte_carlo_simulations": 1000,
  "monte_carlo_random_seed": 42
}
```

Simulation count defaults to 1,000 and accepts 1–10,000. Starting balance and risk per trade reuse the existing calibration fields. With OOS enabled, Monte Carlo uses completed validation returns; otherwise it uses completed calibration returns. No closed trades produces a controlled `available: false` summary.

Enabled responses add `monte_carlo_summary`, `monte_carlo_distribution`, `monte_carlo_risk_summary`, and `monte_carlo_recommendations`. The distribution contains deterministic per-simulation balance, R, drawdown, streak, profit-factor, win-rate, ruin, profit, and drawdown-threshold results. Aggregate summaries report ending-balance percentiles, median/worst drawdown, streak risk, expectancy dispersion, probability of profit, risk of ruin, and probabilities of exceeding 5%, 10%, and 20% drawdown.

The simulator alternates trade-order reshuffling and sampling with replacement. It applies deterministic skipped-trade stress and, when available, random stress sampled from observed execution degradation. High ruin risk or at least 25% probability of drawdown beyond 20% prevents `READY_FOR_PAPER_TRADING`; this modifies research readiness output only. When disabled, all four Monte Carlo fields are `null`.

### v3.4 Monte Carlo Reporting and Risk Intelligence

The same `monte_carlo_analysis: true` flag adds six interpretation fields:

- `monte_carlo_report`
- `monte_carlo_risk_heatmap`
- `monte_carlo_target_probabilities`
- `monte_carlo_expectancy_confidence`
- `monte_carlo_kelly_summary`
- `monte_carlo_failure_reasons`

The report includes 1st/5th percentile balance and R tails, median/worst drawdown, profit/loss/ruin probabilities, 5%/10%/20%/30% drawdown probabilities, losing-streak statistics, status, and plain-English interpretation. Target probabilities use peak path values and cover +5R, +10R, +20R, +50R, 10%/25%/50% growth, account doubling, and finishing below starting balance.

The heatmap assigns `LOW`, `MEDIUM`, or `HIGH` risk plus a 0–100 score and explanation to drawdown, ruin, losing streak, tail risk, and profit stability. Expectancy output provides approximate normal 90%, 95%, and 99% intervals. Kelly output provides full, half, and quarter fractions plus a capped research-risk estimate and instability warning; no fraction is applied to trading.

Failure codes identify ruin, drawdown, sample, tail, worst-case, confidence, and streak concerns. Paper-trading readiness is blocked when source validation has fewer than 100 trades, ruin reaches 5%, 20% drawdown probability reaches 25%, the 95% expectancy lower bound is non-positive, or ruin/tail heatmap risk is `HIGH`. Disabled Monte Carlo analysis leaves all six fields null.

### v3.5 Advanced Statistical Validation

Add `"statistical_validation_analysis": true` to a calibration request. Enabled responses add:

- `statistical_validation_summary`
- `losing_streak_summary`
- `trade_distribution_summary`
- `edge_decay_summary`
- `fold_stability_summary`
- `weakness_detection_summary`

The validator uses completed OOS validation returns when OOS is enabled and completed calibration returns otherwise. Losing-streak output estimates probabilities of at least one 3-, 5-, 8-, or 10-loss run and reports observed/expected streaks. Distribution output groups R outcomes from below -1R through above 5R and measures top 5%/10% gross-profit contribution.

Edge decay compares chronological first, middle, and final thirds. OOS-enabled requests also measure validation expectancy variance and positive-fold rate. Weakness flags are `EDGE_DECAY`, `HIGH_OUTLIER_DEPENDENCY`, `LARGE_LOSING_STREAK_RISK`, `FOLD_INSTABILITY`, `PROFIT_CONCENTRATION`, `NEGATIVE_RECENT_EXPECTANCY`, and `LOW_SAMPLE_SIZE`.

Severe decay, negative final-third expectancy, over-80% top-10% profit concentration, poor fold stability, extreme losing-streak risk, or fewer than 100 trades prevents `READY_FOR_PAPER_TRADING`. This only downgrades research readiness. Disabled validation leaves all six fields null.

### v3.6 Centralized Evidence Scoring

`POST /analysis` includes additive `score_summary`. It reports:

- `trade_quality_score`, `confidence_score`, `edge_score`, and risk-quality `risk_score`
- `evidence_score_breakdown`
- positive, negative, and neutral contributors
- `score_grade` from `A+` through `F`
- unavailable research inputs
- human-readable summary

The eleven categories are market structure, multi-timeframe alignment, regime quality, setup quality, strategy alignment, risk/reward, confirmation, execution readiness, historical edge, statistical reliability, and Monte Carlo risk. Live analysis has no historical research context, so the last three are marked unavailable and excluded from score normalization rather than treated as failures.

`POST /calibrate` adds `aggregate_score_summary` when analysis records or research evidence exist. It averages immutable per-window live evidence, then includes pipeline, statistical, or Monte Carlo categories only when those optional reports are present. The score is descriptive and never replaces Decision Engine action, Setup selection, Strategy routing, execution gates, or risk rules.

### v3.7 Execution Intelligence

`POST /analysis` includes additive `execution_intelligence` with:

- `execution_quality_score` and grade
- preferred style: `market_entry`, `limit_retest`, `confirmation_close`, `wait_for_pullback`, or `avoid_execution`
- entry-timing guidance
- stop, target, and risk/reward assessments
- research-only trade-management guidance
- warnings, blockers, available research inputs, and summary

No-trade and `no_valid_setup` results always use `avoid_execution`. Developing or weakly confirmed setups use confirmation-close or pullback-wait guidance. Confirmed retest, pullback, and liquidity-sweep setups generally favor limit-retest guidance; this never modifies the existing entry zone.

`POST /calibrate` adds `aggregate_execution_intelligence_summary` when analysis records exist. It averages immutable advisory scores and may explain aggregate MFE/MAE, timing-lab findings, management sensitivities, Monte Carlo status, and statistical validation. Guidance is descriptive only and cannot change entries, stops, targets, selection, sizing, or management.

### v3.8 Confidence Calibration

`POST /analysis` adds `confidence_calibration` containing raw score, calibrated confidence, historical win probability, confidence band, sample size, reliability, method, bucket, warning, and summary. Since live analysis does not load historical outcomes, it uses identity mapping and marks reliability `insufficient`.

`POST /calibrate` adds `aggregate_confidence_calibration_summary` and `confidence_bucket_calibration`. Standard buckets are `50-59`, `60-69`, `70-79`, `80-89`, and `90-100`. Each reports outcomes, average raw score, historical win probability, calibrated probability, method, warning, and reliability.

- No sample: `insufficient`, identity mapping.
- 1–19 trades: `low`, identity mapping.
- 20–99 trades: `medium`, empirical mapping.
- 100 or more trades: `high`, empirical mapping.

Scores below 50 remain outside the requested empirical buckets and retain their authoritative raw value. Calibrated confidence is reporting-only and never changes Decision Engine action, confidence gates, setup qualification, or trade eligibility.

### v3.9 Strategy and Setup Ratings

`POST /analysis` adds `current_strategy_rating` and `current_setup_rating`. Because live analysis does not load historical category research, both are explicitly `available: false`, carry no grade, and include a prominent warning. The selected setup and strategy remain unchanged.

`POST /calibrate` adds `strategy_rating_summary` and `setup_rating_summary`. Each contains observed category grades, strongest and weakest names, low-sample warnings, and a readable summary. Every category grade reports rating score, sample size/quality, win rate, expectancy, average/total R, profit factor, drawdown, confidence interval, significance, OOS consistency, overfit risk, recommendation, and explanation.

Grades range from `A+` through `F`. Fewer than five closed trades cap a grade at `D`; fewer than 20 cap it at `B`; negative expectancy is always `F`. `A+` additionally requires at least 100 trades, strong expectancy/profit factor, controlled drawdown, stable category-level OOS evidence, and no high overfit risk. Ratings are advisory and cannot alter routing or eligibility.

### v4.0 Adaptive Symbol Profiles

`POST /analysis` adds `symbol_profile`. With sufficient stored calibration history it reports status, market character, preferred historical strategy/setup, their grades, profile confidence, sample size, and warning. With fewer than 20 completed trades it returns `status: unavailable` and `Not enough historical calibration data.`

Example available response:

```json
{
  "status": "available",
  "symbol": "BTC-USD",
  "market_character": "trending",
  "preferred_strategy": "liquidity_sweep_reversal",
  "preferred_setup": "bearish_bos_retest",
  "strategy_grade": "A",
  "setup_grade": "A",
  "confidence": 82,
  "sample_size": 164,
  "warning": null
}
```

`POST /calibrate` adds `symbol_profile_summary`, containing every persisted profile, symbols updated by the current request, profile count, and summary. Each profile includes outcomes, R statistics, profit factor, drawdown, confidence, market character, preferred categories, grades, timestamps, and complete strategy/setup rankings.

Market character requires at least 30 completed trades. Preferred categories require at least 20 category trades, positive expectancy, and profit factor of at least 1. Profiles are stored locally in `research/symbol_profiles.json` and merged across calibration runs. Profile output is never consumed by production analysis.

### v4.1 Adaptive Strategy Router Laboratory

`POST /analysis` adds `adaptive_strategy_router`: finalized production and profile-preferred routes, alignment, historical candidates, route confidence, sample size, warnings, and explanation. Missing profiles are unavailable, avoid/no-trade actions never suggest execution, and preferred categories under 20 trades are marked `insufficient_sample`.

`POST /calibrate` adds `aggregate_adaptive_strategy_router_summary` with alignment counts, common mismatches, strongest profile-preferred categories, and a readable summary. It cannot alter routing or calibration metrics.

### Setup quality intelligence (v4.4)

`POST /analysis` adds `setup_quality` with `score`, `grade`, eight component scores, and a human-readable summary. Component maxima are market structure 20, liquidity 15, confirmation 15, higher-timeframe confluence 15, risk/reward 10, trend alignment 10, volatility 10, and freshness 5. Grades are A+ (95–100), A (90–94), B+ (85–89), B (80–84), C+ (75–79), C (70–74), D (65–69), and F below 65.

`POST /calibrate` adds always-on `setup_quality_summary`: average/highest/lowest quality, averages by symbol/strategy/setup/regime, quality and grade distributions, correlations against outcome, R, profit proxy, drawdown, duration, confidence, and the existing trade-quality score, plus advisory recommendations. Developing and skipped setups contribute to coverage statistics; only completed trades contribute to outcome correlations.

Dashboard overview adds average quality, highest-quality setup, best-quality symbol, and grade distribution. Dashboard setup rows add average quality and quality rank; quality findings also appear in dashboard recommendations. These fields never alter readiness or production behavior.

### Realistic execution cost modeling (v5.0)

`POST /backtest` and `POST /calibrate` accept the optional fields `execution_cost_modeling` (default `false`), `spread_bps`, `slippage_bps`, `commission_per_trade`, `stop_slippage_bps`, and `latency_ms`. When enabled without explicit bps values, the model uses documented conservative examples by asset class: crypto has higher assumed friction, Forex lower friction, and stocks/ETFs moderate friction. These are research defaults, not broker quotes.

```json
{
  "symbol": "EUR-USD",
  "timeframe": "5m",
  "higher_timeframe": "1h",
  "lookback": 300,
  "starting_balance": 10000,
  "risk_per_trade_percent": 1,
  "max_trades": 50,
  "execution_cost_modeling": true,
  "spread_bps": 1.5,
  "slippage_bps": 1.0,
  "commission_per_trade": 2.0,
  "stop_slippage_bps": 2.0,
  "latency_ms": 100
}
```

Backtests add `execution_cost_summary`, `realistic_metrics`, and `execution_cost_recommendations`. Calibration adds the same parallel result plus `aggregate_execution_cost_summary`, which reports baseline versus realistic R and expectancy, degradation percentage, profit-factor/drawdown impact, and the symbols, strategies, and setups most affected. Disabled requests retain null additive fields and exact baseline behavior. Dashboard overview, risks, and recommendations expose only the latest stored cost snapshot; they never rerun research or alter readiness automatically.

## v3.1 Statistical Research Laboratory

The research laboratory runs automatically after every successful `POST /calibrate`; no request flag is required. It adds:

- `research_lab_summary`
- `research_rankings`
- `performance_matrices`
- `research_statistics`
- `research_recommendations`

The summary reports symbol, timeframe, setup, strategy, regime, confidence bucket, UTC hour, UTC day, trade duration, stop-management, entry-model, and execution-profile performance. Entry and execution comparisons reflect profiles supplied to their existing optional laboratories; stop-management rules use the existing automatic sensitivity results.

Every performance row includes records, closed outcomes, win rate, R and expectancy, profit factor, drawdown, MFE/MAE, duration, confidence, a 95% interval for average R, deterministic significance score, sample quality, and a research recommendation. Empty requested standard categories remain visible with zero samples, and observed future categories are added automatically.

Matrices cover regime/strategy, setup/regime, symbol/setup, and timeframe/setup. Rankings identify the top and bottom ten observed combinations plus headline expectancy, profit factor, drawdown, significance, and sample-size leaders. Research output is downstream-only and cannot alter any calibration or production metric.

## v3.1 Continuous Research Endpoints

Every successful calibration publishes its finalized backtest records to a process-local, read-only research store after all production metrics are complete. The store powers these additive endpoints:

| Method | Path | Response |
|---|---|---|
| `GET` | `/research/status` | Current leaders, warnings, record counts, and a human-readable status statement |
| `GET` | `/research/rankings` | Strongest and weakest rows for each supported research dimension |
| `GET` | `/research/best-combinations` | Up to ten highest-expectancy cross-dimensional combinations |
| `GET` | `/research/weakest-combinations` | Up to ten lowest-expectancy cross-dimensional combinations |
| `POST` | `/research/refresh` | A recalculated status snapshot for the selected rolling window |

The four `GET` endpoints accept `window=all_time|last_250|last_500|last_1000|custom`. A custom window also requires a positive `custom_lookback` query parameter. Built-in rolling windows count the latest completed trades, while all-time status preserves every ingested calibration record.

Refresh request example:

```json
{
  "window": "custom",
  "custom_lookback": 400
}
```

Performance objects include records, executed trades, wins, losses, win rate, average and total R, expectancy, profit factor, drawdown, MFE/MAE, a confidence interval, sample quality, and `last_updated`. Rankings cover symbols, timeframes, setups, strategies, market regimes, confidence buckets, Eastern-time hours, weekdays, and setup/regime, symbol/setup, and timeframe/setup pairs.

The service does not start a background refresh thread automatically. The optional scheduler must be explicitly started by an embedding application. Research state is process-local and non-durable in v3.1; restarting the API clears it. None of these endpoints can alter decisions, setups, strategies, risk, execution, trade outcomes, or calibration metrics.
