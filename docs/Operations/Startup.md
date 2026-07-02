# Startup and Local Environment

[Operations index](README.md) · [Commands](Commands.md) · [Troubleshooting](Troubleshooting.md)

## Prepare PowerShell

```powershell
.\.venv\Scripts\Activate.ps1
python --version
```

If `.venv` does not exist:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Standard Startup

```powershell
python start.py
```

Expected output includes the current version, startup checks, and `http://localhost:8000/docs`. The API stays in the foreground; press `Ctrl+C` for graceful shutdown.

## Validation, Browser, and URLs

```powershell
python start.py --validate
python start.py --health
python start.py --open-browser
python start.py --urls
```

Validation exit codes are 0 PASS, 1 WATCHLIST, and 2 FAIL. Browser opening is optional and failure is warning-only.

## Controlled Paper CLI

```powershell
python start.py --paper --minutes 30
python start.py --paper --hours 2
python start.py --paper --days 7
python start.py --paper --weeks 2
python start.py --paper --months 1
python start.py --paper --cycles 100
python start.py --paper --hours 2 --label "2 Hour Local Validation"
```

The CLI starts the API, validates it, permits WATCHLIST, blocks FAIL, and invokes the existing continuous paper runtime. Auto-approval remains false. Multiple duration flags select the shortest.

Paper CLI uses one Uvicorn process with reload disabled. Before process creation it verifies that local port 8000 is free, then waits for `/health` before starting the continuous runtime. If port 8000 is occupied, stop the existing API or paper session and retry.

## localhost vs 0.0.0.0

`0.0.0.0` is Uvicorn’s server bind address. It is not the browser URL. Use `http://localhost:8000` and `http://localhost:8000/docs`.

## Common Problems

- Activation blocked: see [PowerShell execution policy](Troubleshooting.md#powershell-execution-policy).
- Port busy: see [port 8000](Troubleshooting.md#port-8000-is-already-in-use).
- Imports fail: activate `.venv` and reinstall `requirements.txt`.
- Swagger fails: check `/health`, launcher output, then `/system/health`.
