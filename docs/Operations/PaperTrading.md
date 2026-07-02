# Paper-Trading Operations

[Operations index](README.md) · [Startup](Startup.md) · [Daily workflow](DailyWorkflow.md)

StructureIQ paper mode uses simulated brokerage state only. It does not connect to a real broker and keeps automatic approval disabled by default.

## Common Sessions

```powershell
python start.py --paper --minutes 30 --label "30 Minute Validation"
python start.py --paper --hours 2 --label "2 Hour Validation"
python start.py --paper --hours 8 --label "Overnight Validation"
python start.py --paper --days 1 --label "24 Hour Validation"
python start.py --paper --weeks 1 --label "Week Validation"
python start.py --paper --months 1 --label "Month Validation"
```

The CLI validates first. WATCHLIST is printed for review and allowed; FAIL blocks the session.

## Stop, Pause, and Resume

Press `Ctrl+C` in the CLI to stop the runtime and API gracefully. From another terminal:

```powershell
Invoke-RestMethod -Method Post http://localhost:8000/continuous-paper/pause
Invoke-RestMethod -Method Post http://localhost:8000/continuous-paper/resume
Invoke-RestMethod -Method Post http://localhost:8000/continuous-paper/stop
```

Pause is resumable. Duration or cycle completion is final. Investigate safety pause reasons before resuming.

## Review Results

```powershell
Invoke-RestMethod http://localhost:8000/continuous-paper/status
Invoke-RestMethod http://localhost:8000/continuous-paper/events
Invoke-RestMethod http://localhost:8000/continuous-paper/sessions
Invoke-RestMethod http://localhost:8000/paper/account
Invoke-RestMethod http://localhost:8000/paper-journal/summary
Invoke-RestMethod http://localhost:8000/dashboard/risks
Invoke-RestMethod http://localhost:8000/reports/daily
```

Review cycles, candidates, trades, reports, errors, pause reasons, and stop reason. A no-trade session can still validate stability and data availability.

Continuous runtime generates at most one daily report for each report date. Subsequent cycles count `skipped_existing`; they do not overwrite the file or report an operational error. Use the manual report endpoint with explicit `overwrite=true` only when regeneration is intentional.

## Safety Protections

- No automatic application startup.
- Auto-approval false and manual approval by default.
- Health and validation gates.
- Daily paper loss and profit locks.
- Position and duplicate limits in Paper Brokerage.
- Error-threshold pause.
- Conservative same-candle stop/target behavior.
- Append-only runtime events and session summaries.

Never bypass a FAIL or risk lock merely to increase trade count.
