# Operational Architecture Overview

[Operations index](README.md) · [Detailed architecture](../Architecture.md)

This page explains subsystem ownership for operators without duplicating implementation details.

## Intelligence and Research

- **Analysis Engine** turns candles into structure, decisions, setups, strategies, explanations, quality, confidence, and advisory execution output. Paper runtime does not rewrite its decisions.
- **Calibration** evaluates historical behavior across requested markets. It is resource-intensive and separate from monitoring.
- **Research** interprets calibration, statistical, regime, execution, and profile evidence. It advises and never routes trades.
- **Dashboard** projects existing evidence into compact readiness, risk, symbol, strategy, setup, and recommendation views. It does not rerun calibration.

## Paper Operations

- **Live Market Monitor** polls configured markets and emits deduplicated paper candidates.
- **Paper Trading Orchestrator** coordinates one monitor-to-report cycle; it does not own trades.
- **Continuous Paper Trading** schedules orchestrator cycles after explicit startup and applies health, validation, duration, cycle, error, and account-risk gates.
- **Trade Lifecycle Manager** owns paper approvals, pending orders, fills, and stop/target transitions.
- **Paper Brokerage** owns simulated balances, positions, P/L, sizing, and account limits.
- **Paper Journal** reconstructs append-only trade histories and research context.

## Reports and Scheduling

- **Daily Report Engine** summarizes journal, brokerage, lifecycle, monitoring, and advisory evidence into local reports.
- **Daily Report Scheduler** optionally creates previous-day reports. It is stopped by default.

## Safety and Operations

- **System Health** observes availability, runtime state, errors, and storage.
- **System Validation** independently probes major components and reports PASS, WATCHLIST, or FAIL.
- **Launcher** checks the environment, starts Uvicorn, displays localhost URLs, and controls explicit paper CLI sessions.

## Operational Data Flow

```text
Market Provider → Monitor → Orchestrator → Lifecycle → Paper Brokerage
                                      ↘ Journal → Daily Reports

Health + Validation + Account Risk → Continuous Runtime Safety Gates
Calibration + Research → Dashboard and advisory review only
```

Diagnose failures at the owning boundary. Do not move account logic into the orchestrator, decisions into the runtime, or routing into the dashboard.
