# Command Reference

[Operations index](README.md) · [Root cheat sheet](../../COMMANDS.md)

Run commands from the repository root with `.venv` activated.

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

## Startup, Validation, and URLs

```powershell
python start.py
python start.py --open-browser
python start.py --urls
python start.py --health
python start.py --validate
python -m pytest -q
```

## Paper Trading

```powershell
python start.py --paper --minutes 30
python start.py --paper --hours 2 --label "Two Hour Validation"
python start.py --paper --days 1
python start.py --paper --cycles 100
Invoke-RestMethod http://localhost:8000/continuous-paper/status
Invoke-RestMethod -Method Post http://localhost:8000/continuous-paper/pause
Invoke-RestMethod -Method Post http://localhost:8000/continuous-paper/resume
Invoke-RestMethod -Method Post http://localhost:8000/continuous-paper/stop
```

## Health, Dashboard, and Validation

```powershell
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8000/system/health
Invoke-RestMethod http://localhost:8000/system/readiness
Invoke-RestMethod -Method Post http://localhost:8000/system/validation/run
Invoke-RestMethod http://localhost:8000/dashboard/overview
Invoke-RestMethod http://localhost:8000/dashboard/readiness
Invoke-RestMethod http://localhost:8000/dashboard/risks
Invoke-RestMethod http://localhost:8000/dashboard/recommendations
```

## Reports, Monitoring, Lifecycle, and Journal

```powershell
Invoke-RestMethod http://localhost:8000/reports/daily
Invoke-RestMethod -Method Post http://localhost:8000/reports/scheduler/run-now
Invoke-RestMethod http://localhost:8000/monitor/status
Invoke-RestMethod -Method Post http://localhost:8000/monitor/run-once
Invoke-RestMethod http://localhost:8000/lifecycle/status
Invoke-RestMethod http://localhost:8000/lifecycle/pending-orders
Invoke-RestMethod http://localhost:8000/paper/account
Invoke-RestMethod http://localhost:8000/paper-journal/summary
Invoke-RestMethod -Method Post http://localhost:8000/paper-journal/export
```

## Useful URLs

- Swagger: <http://localhost:8000/docs>
- API root: <http://localhost:8000>
- Health: <http://localhost:8000/health>
- System health: <http://localhost:8000/system/health>
- Dashboard: <http://localhost:8000/dashboard/overview>
- Continuous paper: <http://localhost:8000/continuous-paper/status>
