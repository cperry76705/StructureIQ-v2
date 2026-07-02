# Troubleshooting and Recovery

[Operations index](README.md) · [Startup](Startup.md) · [Git](Git.md)

## PowerShell Execution Policy

```powershell
Get-ExecutionPolicy -List
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

The process-scoped change is temporary. Do not weaken machine policy without approval.

## Port 8000 Is Already in Use

```powershell
Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
Get-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess
```

Identify the process, then stop a known stale StructureIQ instance gracefully. Do not terminate an unknown process.

## 0.0.0.0 vs localhost

`0.0.0.0` is Uvicorn’s bind address. Open <http://localhost:8000/docs>.

## Virtual Environment Activation

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Get-Command python
```

## Swagger Is Not Loading

1. Confirm the launcher still runs.
2. Open <http://localhost:8000/health>.
3. Run `python start.py --urls`.
4. Inspect launcher output and `logs/startup.log`.
5. Check port 8000 and firewall policy.

## Validation WATCHLIST

Read every warning. It often indicates stopped optional services or advisory findings. Paper CLI permits WATCHLIST, but it is not PASS.

## Validation FAIL

Do not bypass it. Inspect the failed component, blocking issues, `/system/health`, storage permissions, imports, and required APIs. Repair and rerun validation.

## Codespaces Timeout

Commit and push before long breaks. After reconnecting, verify the branch, pull, restore dependencies, and rerun tests and validation. Runtime sessions do not survive suspension.

## Browser Will Not Open

`--open-browser` failure does not stop the API. Copy <http://localhost:8000/docs> manually or run `python start.py --urls`.

## Git Merge Conflicts

Run `git status`, resolve conflict markers, stage resolved files, test, then complete the merge. See [Git Operations](Git.md#merge-conflicts).

## Missing Requirements

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python start.py --health
```

## Corrupt Research or State Files

Stop paper runtimes. Preserve a backup, identify the file reported by health, and inspect its JSON/JSONL boundary. Do not silently delete journals or account state. Use supported reset or rebuild endpoints and document the action.

## Recovery Order

1. Stop active paper processes.
2. Preserve logs and affected state.
3. Run startup health and validation.
4. Repair configuration, dependencies, storage, or file integrity.
5. Run tests.
6. Run a short labeled paper validation before a long session.
