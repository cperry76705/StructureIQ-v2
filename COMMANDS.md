# StructureIQ Command Cheat Sheet

## Controlled paper auto-approval

```powershell
.\.venv\Scripts\python.exe start.py --paper --hours 2 --label "Auto Approval Validation" --auto-approve-paper --max-trades-per-cycle 1 --max-candidates-per-cycle 3 --order-type limit_retest
```

Auto-approval is off unless `--auto-approve-paper` is present. Simulated market orders additionally require `--allow-market-orders --order-type market`.

Full manual: [docs/Operations/README.md](docs/Operations/README.md)

## Environment and Startup

```powershell
.\.venv\Scripts\Activate.ps1
python start.py
python start.py --open-browser
python start.py --urls
python start.py --version
```

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
Invoke-RestMethod http://localhost:8000/dashboard/overview
Invoke-RestMethod http://localhost:8000/dashboard/risks
Invoke-RestMethod http://localhost:8000/paper-journal/summary
Invoke-RestMethod http://localhost:8000/candidate-diagnostics/summary
Invoke-RestMethod http://localhost:8000/candidate-diagnostics/near-misses?limit=20
Invoke-RestMethod http://localhost:8000/calibration-analytics/summary
Invoke-RestMethod http://localhost:8000/calibration-analytics/conversion-funnel
Invoke-RestMethod http://localhost:8000/paper-reconciliation/status
Invoke-RestMethod http://localhost:8000/paper-reconciliation/discrepancies
Invoke-RestMethod -Method Post http://localhost:8000/paper-reconciliation/run
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
