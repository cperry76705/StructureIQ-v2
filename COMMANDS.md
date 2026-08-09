# StructureIQ Command Cheat Sheet

## Paper integrity remediation and clean baseline

```powershell
.\.venv\Scripts\python.exe start.py --integrity-audit
.\.venv\Scripts\python.exe start.py --integrity-remediate --remediation-trade-id 47cbfd066469d49904e4dc23
.\.venv\Scripts\python.exe start.py --integrity-remediate --remediation-trade-id 47cbfd066469d49904e4dc23 --remediation-action QUARANTINE --remediation-reason identical_open_close_timestamp_and_missing_lifecycle --confirm-remediation
.\.venv\Scripts\python.exe start.py --integrity-rebuild
.\.venv\Scripts\python.exe start.py --integrity-baseline
.\.venv\Scripts\python.exe start.py --integrity-clear-safe-mode
.\.venv\Scripts\python.exe start.py --validate
.\.venv\Scripts\python.exe start.py --validation-readiness
```

The remediation command previews by default. `--confirm-remediation` appends metadata to `research/paper_integrity_remediation.jsonl`; it does not edit or delete raw journal rows. There is no force clear for SAFE MODE.

## Controlled paper auto-approval

```powershell
.\.venv\Scripts\python.exe start.py --paper --hours 2 --label "Auto Approval Validation" --auto-approve-paper --max-trades-per-cycle 1 --max-candidates-per-cycle 3 --order-type limit_retest
python start.py --paper --hours 2 --campaign-name "Recovery Validation 2" --auto-approve
python start.py --paper --hours 24 --campaign-name "Stability Validation" --no-auto-approve
```

Auto-approval is off unless `--auto-approve-paper` or `--auto-approve` is present. `--no-auto-approve` forces manual approval for that run. Simulated market orders additionally require `--allow-market-orders --order-type market`.

Full manual: [docs/Operations/README.md](docs/Operations/README.md)

## Deterministic recovery infrastructure test

```powershell
.\.venv\Scripts\python.exe start.py --recovery-test-create
.\.venv\Scripts\python.exe start.py --recovery-test-verify
.\.venv\Scripts\python.exe start.py --recovery-test-cleanup
```

The harness creates only tagged synthetic paper fixtures and excludes them from normal performance, campaign, daily report, calibration, and research statistics.

## Environment and Startup

```powershell
.\.venv\Scripts\Activate.ps1
python start.py
python start.py --open-browser
python start.py --urls
python start.py --version
```

Startup prints current market sessions and the active/skipped watchlist. Forex symbols are automatically skipped while the Forex session is closed unless monitor configuration explicitly sets `ignore_market_sessions=true`.

## Validation and Tests

```powershell
python start.py --health
python start.py --validate
python -m pytest -q
```

## Paper CLI

```powershell
python start.py --paper --minutes 30 --label "Quick Validation"
python start.py --paper --hours 2 --label "Two Hour Validation"
python start.py --paper --hours 8 --label "Overnight Validation"
python start.py --paper --days 1
python start.py --paper --weeks 1
python start.py --paper --months 1
python start.py --paper --cycles 100
python start.py --paper --days 7 --campaign-name "July 7 Day Validation"
```

## Runtime Controls

```powershell
Invoke-RestMethod http://localhost:8000/continuous-paper/status
Invoke-RestMethod -Method Post http://localhost:8000/continuous-paper/pause
Invoke-RestMethod -Method Post http://localhost:8000/continuous-paper/resume
Invoke-RestMethod -Method Post http://localhost:8000/continuous-paper/stop
```

## Reports, Health, and Dashboard

```powershell
Invoke-RestMethod http://localhost:8000/reports/daily
Invoke-RestMethod -Method Post http://localhost:8000/reports/scheduler/run-now
Invoke-RestMethod http://localhost:8000/system/health
Invoke-RestMethod http://localhost:8000/system/readiness
Invoke-RestMethod http://localhost:8000/market-sessions
Invoke-RestMethod http://localhost:8000/watchlist/active
Invoke-RestMethod http://localhost:8000/dashboard/overview
Invoke-RestMethod http://localhost:8000/dashboard/risks
Invoke-RestMethod http://localhost:8000/paper-journal/summary
Invoke-RestMethod http://localhost:8000/candidate-diagnostics/summary
Invoke-RestMethod http://localhost:8000/candidate-diagnostics/rejections
Invoke-RestMethod http://localhost:8000/candidate-diagnostics/cycles/<cycle_id>
Invoke-RestMethod http://localhost:8000/candidate-diagnostics/near-misses?limit=20
Invoke-RestMethod http://localhost:8000/calibration-analytics/summary
Invoke-RestMethod http://localhost:8000/calibration-analytics/conversion-funnel
Invoke-RestMethod http://localhost:8000/opportunity-coverage/summary
Invoke-RestMethod http://localhost:8000/opportunity-coverage/funnel
Invoke-RestMethod http://localhost:8000/opportunity-coverage/by-symbol
Invoke-RestMethod http://localhost:8000/opportunity-coverage/by-asset-class
Invoke-RestMethod http://localhost:8000/opportunity-coverage/terminal-reasons
Invoke-RestMethod http://localhost:8000/symbols/provider-validation
Invoke-RestMethod http://localhost:8000/validation-readiness/7-day
Invoke-RestMethod http://localhost:8000/paper-reconciliation/status
Invoke-RestMethod "http://localhost:8000/paper-reconciliation/summary?scope=active_campaign"
Invoke-RestMethod "http://localhost:8000/paper-reconciliation/discrepancies?scope=campaign&campaign_id=<campaign_id>"
Invoke-RestMethod http://localhost:8000/paper-reconciliation/discrepancies
Invoke-RestMethod -Method Post http://localhost:8000/paper-reconciliation/run
Invoke-RestMethod http://localhost:8000/paper-recovery/status
Invoke-RestMethod -Method Post http://localhost:8000/paper-recovery/run
Invoke-RestMethod http://localhost:8000/paper-integrity/summary
Invoke-RestMethod http://localhost:8000/paper-integrity/quarantine
Invoke-RestMethod http://localhost:8000/paper-integrity/duplicates
Invoke-RestMethod http://localhost:8000/paper-integrity/lifecycle
Invoke-RestMethod http://localhost:8000/paper-integrity/timestamps
Invoke-RestMethod http://localhost:8000/paper-integrity/root-cause/47cbfd066469d49904e4dc23
Invoke-RestMethod -Method Post http://localhost:8000/recovery-test/create-pending-order
Invoke-RestMethod -Method Post http://localhost:8000/recovery-test/create-open-trade
Invoke-RestMethod -Method Post http://localhost:8000/recovery-test/create-closed-trade
Invoke-RestMethod http://localhost:8000/recovery-test/status
Invoke-RestMethod -Method Post http://localhost:8000/recovery-test/snapshot
Invoke-RestMethod -Method Post http://localhost:8000/recovery-test/verify-after-restart
Invoke-RestMethod http://localhost:8000/recovery-test/history
Invoke-RestMethod -Method Post http://localhost:8000/recovery-test/cleanup
Invoke-RestMethod http://localhost:8000/campaigns
Invoke-RestMethod http://localhost:8000/campaigns/current
Invoke-RestMethod http://localhost:8000/campaigns/legacy_campaign/audit
Invoke-RestMethod -Method Post http://localhost:8000/campaigns/<campaign_id>/refresh-summary
Invoke-RestMethod http://localhost:8000/campaigns/<campaign_id>/candidate-diagnostics
Invoke-RestMethod http://localhost:8000/campaigns/<campaign_id>/opportunity-coverage
```

## Git

```powershell
git status
git pull
git diff
git add .
git diff --staged
git commit -m "Describe the change"
git push
```

## Local URLs

- Swagger: <http://localhost:8000/docs>
- API root: <http://localhost:8000>
- Health: <http://localhost:8000/health>
- System health: <http://localhost:8000/system/health>
- Dashboard: <http://localhost:8000/dashboard/overview>
- Continuous paper: <http://localhost:8000/continuous-paper/status>

> Uvicorn may print `0.0.0.0`; use `localhost` in the browser. All paper commands remain simulated and broker-free.
