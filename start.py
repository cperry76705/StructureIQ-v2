"""Official StructureIQ application launcher.

This module owns startup checks, user-friendly diagnostics, logging, and the
subprocess handoff to uvicorn. It intentionally does not duplicate or modify
FastAPI application logic.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.metadata
import os
import platform
import subprocess
import sys
import json
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


PROJECT_ROOT = Path(__file__).resolve().parent
MIN_PYTHON = (3, 11)
REQUIRED_DIRECTORIES = ("app", "core", "models", "tests", "docs")
REQUIRED_FILES = ("requirements.txt", "app/config.py")
REQUIRED_PACKAGES = ("fastapi", "uvicorn", "pydantic", "pytest", "httpx")
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = "8000"
PUBLIC_API_URL = "http://localhost:8000"
LOCAL_URLS = {
    "Swagger UI": f"{PUBLIC_API_URL}/docs",
    "API Root": PUBLIC_API_URL,
    "Health": f"{PUBLIC_API_URL}/health",
    "System Health": f"{PUBLIC_API_URL}/system/health",
    "Dashboard Overview": f"{PUBLIC_API_URL}/dashboard/overview",
    "Continuous Paper Status": f"{PUBLIC_API_URL}/continuous-paper/status",
}
LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIR / "startup.log"


@dataclass(slots=True)
class CheckResult:
    """One startup validation result."""

    name: str
    passed: bool
    message: str


@dataclass(slots=True)
class StartupHealth:
    """Aggregated launcher health state."""

    checks: list[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """Return true when every startup check passed."""

        return all(check.passed for check in self.checks)

    def add(self, name: str, passed: bool, message: str) -> None:
        """Append a named check result."""

        self.checks.append(CheckResult(name=name, passed=passed, message=message))


def get_version() -> str:
    """Read StructureIQ version from app.config dynamically."""

    from app.config import APP_VERSION

    return APP_VERSION


def build_uvicorn_command(
    *,
    host: str = DEFAULT_HOST,
    port: str = DEFAULT_PORT,
    reload: bool = True,
) -> list[str]:
    """Return the uvicorn subprocess command used by the launcher."""

    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        host,
        "--port",
        str(port),
    ]
    if reload:
        command.append("--reload")
    return command


def _package_installed(package_name: str) -> bool:
    """Return whether a required distribution is installed."""

    try:
        importlib.metadata.version(package_name)
    except importlib.metadata.PackageNotFoundError:
        return False
    return True


def run_startup_checks(project_root: Path = PROJECT_ROOT) -> StartupHealth:
    """Validate the local environment without launching the API server."""

    health = StartupHealth()

    python_ok = sys.version_info >= MIN_PYTHON
    health.add(
        "Python version",
        python_ok,
        (
            f"Python {platform.python_version()} detected"
            if python_ok
            else (
                "Python "
                f"{MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ is required; "
                f"detected {platform.python_version()}"
            )
        ),
    )

    missing_dirs = [
        directory
        for directory in REQUIRED_DIRECTORIES
        if not (project_root / directory).is_dir()
    ]
    health.add(
        "Directory structure",
        not missing_dirs,
        (
            "Required project folders are present"
            if not missing_dirs
            else f"Missing required folders: {', '.join(missing_dirs)}"
        ),
    )

    missing_files = [
        file_name for file_name in REQUIRED_FILES if not (project_root / file_name).is_file()
    ]
    health.add(
        "Configuration files",
        not missing_files,
        (
            "Required configuration files are present"
            if not missing_files
            else f"Missing required files: {', '.join(missing_files)}"
        ),
    )

    missing_packages = [
        package for package in REQUIRED_PACKAGES if not _package_installed(package)
    ]
    health.add(
        "Required packages",
        not missing_packages,
        (
            "Required Python packages are installed"
            if not missing_packages
            else f"Missing packages: {', '.join(missing_packages)}"
        ),
    )

    try:
        importlib.import_module("app.config")
        version = get_version()
        health.add("Configuration import", True, f"Configuration loaded ({version})")
    except Exception as exc:  # pragma: no cover - message is tested through monkeypatch
        health.add("Configuration import", False, f"Could not load app.config: {exc}")

    try:
        importlib.import_module("app.main")
        health.add("FastAPI import", True, "app.main imported successfully")
    except Exception as exc:
        health.add("FastAPI import", False, f"Could not import app.main: {exc}")

    try:
        importlib.import_module("core.system_health")
        health.add("System Health module", True, "System Health is available")
    except Exception as exc:
        health.add("System Health module", False, f"Could not import System Health: {exc}")

    return health


def ensure_log_dir() -> None:
    """Create the launcher log directory if needed."""

    LOG_DIR.mkdir(parents=True, exist_ok=True)


def write_startup_log(
    *,
    result: str,
    argv: Sequence[str],
    version: str | None = None,
    details: str | None = None,
) -> None:
    """Append a startup event to logs/startup.log."""

    ensure_log_dir()
    resolved_version = version or _safe_version()
    timestamp = datetime.now(timezone.utc).isoformat()
    args = " ".join(argv) if argv else "start.py"
    lines = [
        f"[{timestamp}] result={result}",
        f"version={resolved_version}",
        f"python={platform.python_version()}",
        f"os={platform.platform()}",
        f"arguments={args}",
    ]
    if details:
        lines.append(f"details={details}")
    LOG_FILE.open("a", encoding="utf-8").write("\n".join(lines) + "\n\n")


def _safe_version() -> str:
    """Return the configured version or a fallback for failure logging."""

    try:
        return get_version()
    except Exception:
        return "unknown"


def print_banner(version: str, status: str = "READY") -> None:
    """Display the StructureIQ startup banner."""

    ok = _status_symbol(True)
    print("=" * 50)
    print(f"{f'StructureIQ v{version}':^50}")
    print("=" * 50)
    print()
    print(f"{ok} Configuration Loaded")
    print(f"{ok} Research Engine Loaded")
    print(f"{ok} Symbol Profiles Loaded")
    print(f"{ok} API Starting")
    print()
    print(f"StructureIQ v{version} is running locally.")
    print()
    print_local_urls()
    print()
    print("Note: Uvicorn may display 0.0.0.0 because the server listens on all interfaces.")
    print("Use localhost in your browser.")
    print()
    print(f"Status:\n{status}")


def print_local_urls() -> None:
    """Print stable browser-facing localhost endpoints."""
    for label, url in LOCAL_URLS.items():
        print(f"{label}:\n{url}")


def open_docs_browser(*, opener=None) -> bool:
    """Open Swagger locally; browser failures are warning-only."""
    try:
        opened = (opener or webbrowser.open)(LOCAL_URLS["Swagger UI"])
        if opened is False:
            raise RuntimeError("default browser declined the request")
        return True
    except Exception as exc:
        warning = f"Browser open warning: {exc}"
        print(warning)
        write_startup_log(result="browser_open_warning", argv=("--open-browser",), details=warning)
        return False


def schedule_browser_open(*, delay_seconds: float = 1.0) -> threading.Thread:
    """Attempt browser opening asynchronously so Uvicorn remains the foreground process."""
    thread = threading.Thread(target=lambda: (time.sleep(delay_seconds), open_docs_browser()), daemon=True)
    thread.start()
    return thread


def print_future_sections() -> None:
    """Show reserved application areas without enabling them."""

    print()
    print("Future Reserved Sections:")
    try:
        importlib.import_module("core.paper_brokerage")
        print("- Paper Trading: AVAILABLE/ADVISORY - NOT AUTO-STARTED")
    except Exception:
        print("- Paper Trading: NOT ENABLED")
    try:
        importlib.import_module("core.trade_lifecycle_manager")
        print("- Trade Lifecycle Manager: AVAILABLE/ADVISORY - NOT AUTO-STARTED")
    except Exception:
        print("- Trade Lifecycle Manager: NOT ENABLED")
    try:
        importlib.import_module("core.paper_trade_journal")
        print("- Automated Journal: AVAILABLE/ADVISORY - NOT AUTO-STARTED")
    except Exception:
        print("- Automated Journal: NOT ENABLED")
    try:
        importlib.import_module("core.daily_report_engine")
        print("- Daily Reports: AVAILABLE/ADVISORY - NOT AUTO-STARTED")
    except Exception:
        print("- Daily Reports: NOT ENABLED")
    try:
        importlib.import_module("core.paper_trading_orchestrator")
        print("- Paper Trading Orchestrator: AVAILABLE/ADVISORY - NOT AUTO-STARTED")
    except Exception:
        print("- Paper Trading Orchestrator: NOT ENABLED")
    try:
        importlib.import_module("core.daily_report_scheduler")
        print("- Scheduled Reports: AVAILABLE/ADVISORY - NOT AUTO-STARTED")
    except Exception:
        print("- Scheduled Reports: NOT ENABLED")
    try:
        importlib.import_module("core.system_health")
        print("- System Health: AVAILABLE/ADVISORY")
    except Exception:
        print("- System Health: NOT ENABLED")
    try:
        importlib.import_module("core.continuous_paper_trading")
        print("- Continuous Paper Trading Sessions: AVAILABLE/ADVISORY - NOT AUTO-STARTED")
    except Exception:
        print("- Continuous Paper Trading: NOT ENABLED")
    for section in (
        "Live Market Monitor",
        "Live Trading",
        "Scheduler",
        "AI Research",
        "Broker Connections",
        "Web Dashboard",
    ):
        print(f"- {section}: NOT ENABLED")


def _status_symbol(passed: bool) -> str:
    """Return a terminal-safe status symbol."""

    preferred = "✓" if passed else "✗"
    fallback = "[OK]" if passed else "[FAIL]"
    encoding = sys.stdout.encoding or ""
    try:
        preferred.encode(encoding or "utf-8")
    except (LookupError, UnicodeEncodeError):
        return fallback
    return preferred


def print_health(health: StartupHealth) -> None:
    """Print a friendly startup health report."""

    print("Startup Diagnostics:")
    for check in health.checks:
        icon = _status_symbol(check.passed)
        print(f"{icon} {check.name}: {check.message}")
    print()
    print(f"System Health:\n{'PASS' if health.passed else 'FAIL'}")


def start_api(
    command: Sequence[str] | None = None,
    *,
    runner=None,
) -> int:
    """Start the FastAPI server and wait for completion."""

    launch_command = list(command or build_uvicorn_command())
    run_subprocess = runner or subprocess.run
    try:
        completed = run_subprocess(launch_command, cwd=str(PROJECT_ROOT), check=False)
        return int(getattr(completed, "returncode", 0))
    except KeyboardInterrupt:
        print()
        print("Shutdown requested. StructureIQ stopped cleanly.")
        return 130
    except FileNotFoundError as exc:
        print(f"Could not start the API server: {exc}")
        return 1
    except Exception as exc:
        print(f"Startup failed: {exc}")
        return 1


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse launcher CLI arguments."""

    parser = argparse.ArgumentParser(
        description="Start and validate the StructureIQ application.",
    )
    parser.add_argument(
        "--api",
        action="store_true",
        help="Start only the FastAPI API server.",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Display the current StructureIQ version and exit.",
    )
    parser.add_argument(
        "--health",
        action="store_true",
        help="Run startup validation checks without launching the server.",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Run complete local system validation and exit.",
    )
    parser.add_argument("--open-browser", action="store_true", help="Open the local Swagger UI after startup.")
    parser.add_argument("--no-browser", action="store_true", help="Never open a browser window.")
    parser.add_argument("--urls", action="store_true", help="Print useful localhost URLs and exit.")
    parser.add_argument("--paper", action="store_true", help="Run an explicitly controlled paper-only session.")
    parser.add_argument("--minutes", type=float, help="Stop paper mode after this many minutes.")
    parser.add_argument("--hours", type=float, help="Stop paper mode after this many hours.")
    parser.add_argument("--days", type=float, help="Stop paper mode after this many 24-hour days.")
    parser.add_argument("--weeks", type=float, help="Stop paper mode after this many seven-day weeks.")
    parser.add_argument("--months", type=float, help="Stop paper mode after this many 30-day months.")
    parser.add_argument("--cycles", type=int, help="Stop paper mode after this many completed cycles.")
    parser.add_argument("--label", help="Optional paper runtime session label.")
    return parser.parse_args(argv)


def build_paper_start_payload(args: argparse.Namespace) -> tuple[dict, tuple[str, ...], str]:
    """Convert CLI duration options into the existing continuous-runtime request."""
    durations = []
    if args.minutes is not None: durations.append((args.minutes * 60, "run_for_minutes", args.minutes, f"{args.minutes:g} minutes"))
    if args.hours is not None: durations.append((args.hours * 3600, "run_for_hours", args.hours, f"{args.hours:g} hours"))
    if args.days is not None: durations.append((args.days * 86400, "run_for_hours", args.days * 24, f"{args.days:g} days"))
    if args.weeks is not None: durations.append((args.weeks * 604800, "run_for_hours", args.weeks * 7 * 24, f"{args.weeks:g} weeks"))
    if args.months is not None: durations.append((args.months * 30 * 86400, "run_for_hours", args.months * 30 * 24, f"{args.months:g} months"))
    if any(item[0] <= 0 for item in durations) or (args.cycles is not None and args.cycles <= 0):
        raise ValueError("paper durations and cycle limits must be greater than zero")
    payload = {"session_label": args.label, "auto_approve_candidates": False}
    warnings = []
    description = "unlimited"
    if durations:
        chosen = min(durations, key=lambda item: item[0])
        payload[chosen[1]] = chosen[2]; description = chosen[3]
        if len(durations) > 1:
            warnings.append(f"Multiple duration flags were provided; using the shortest duration ({description}).")
    if args.cycles is not None: payload["max_cycles"] = args.cycles
    return payload, tuple(warnings), description


def run_system_validation() -> int:
    """Run the local validation API in-process and print component results."""
    from fastapi.testclient import TestClient
    from app.main import app

    response = TestClient(app).post("/system/validation/run")
    if response.status_code != 200:
        print(f"System validation failed to run: HTTP {response.status_code}")
        return 2
    result = response.json()
    print(f"StructureIQ v{get_version()} System Validation")
    print("=" * 50)
    for component in result["component_results"]:
        print(f"[{component['status']}] {component['component']} ({component['duration_ms']:.2f} ms)")
        print(f"  {component['human_readable_summary']}")
    print()
    print(f"Overall: {result['validation_status']} ({result['overall_score']:.2f}/100)")
    print(result["human_readable_summary"])
    return {"PASS": 0, "WATCHLIST": 1, "FAIL": 2}[result["validation_status"]]


def _api_json(path: str, *, method: str = "GET", payload: dict | None = None, timeout: float = 10.0) -> dict:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        f"{PUBLIC_API_URL}{path}", data=body, method=method,
        headers={"Content-Type": "application/json"} if body is not None else {},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def wait_for_local_api(*, api_call=_api_json, timeout_seconds: float = 30.0, sleep=time.sleep) -> bool:
    """Wait for the locally started API without contacting external services."""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            api_call("/health")
            return True
        except Exception:
            sleep(.2)
    return False


def _stop_process(process) -> None:
    if getattr(process, "poll", lambda: None)() is None:
        process.terminate()
        try: process.wait(timeout=5)
        except Exception: process.kill()


def run_paper_mode(
    args: argparse.Namespace,
    *,
    process_factory=None,
    api_call=_api_json,
    sleep=time.sleep,
) -> int:
    """Launch the local API and control the existing continuous-paper runtime."""
    try:
        payload, warnings, duration = build_paper_start_payload(args)
    except ValueError as exc:
        print(f"Paper mode configuration error: {exc}")
        return 2
    for warning in warnings: print(f"Warning: {warning}")
    print("Starting API...")
    print(f"Swagger UI: {LOCAL_URLS['Swagger UI']}")
    factory = process_factory or subprocess.Popen
    process = factory(build_uvicorn_command(reload=False), cwd=str(PROJECT_ROOT))
    try:
        if not wait_for_local_api(api_call=api_call, sleep=sleep):
            print("Local API did not become ready in time.")
            return 2
        validation = api_call("/system/validation/run", method="POST")
        validation_status = validation.get("validation_status", "FAIL")
        print(f"Validation: {validation_status}")
        if validation_status == "FAIL":
            print("Paper mode blocked because system validation failed.")
            return 2
        status = api_call("/continuous-paper/start", method="POST", payload=payload)
        if args.open_browser and not args.no_browser: open_docs_browser()
        print("Starting continuous paper trading...")
        print(f"Session: {status.get('session_label') or 'Unlabeled local session'}")
        print(f"Duration: {duration}")
        print("Auto Approval: false")
        print("Paper Only: true")
        print("\nPaper trading is running.\nPress CTRL+C to stop early.")
        while status.get("running") or status.get("paused"):
            if status.get("final_session_summary"): break
            sleep(.5)
            status = api_call("/continuous-paper/status")
        _print_final_paper_summary(status)
        return 0
    except KeyboardInterrupt:
        print("\nStopping paper session early...")
        try: status = api_call("/continuous-paper/stop", method="POST")
        except Exception: status = {}
        _print_final_paper_summary(status)
        return 130
    except Exception as exc:
        print(f"Paper mode failed safely: {exc}")
        return 2
    finally:
        _stop_process(process)


def _print_final_paper_summary(status: dict) -> None:
    summary = status.get("final_session_summary") or {}
    print("\nPaper trading session completed.")
    print(f"Cycles: {summary.get('cycle_count', status.get('cycle_count', 0))}")
    print(f"Candidates Seen: {summary.get('total_candidates_seen', status.get('total_candidates_seen', 0))}")
    print(f"Trades Opened: {summary.get('total_trades_opened', status.get('total_trades_opened', 0))}")
    print(f"Reports Generated: {summary.get('total_reports_generated', status.get('total_reports_generated', 0))}")
    print(f"Stop Reason: {summary.get('stop_reason', status.get('stop_reason', 'unknown'))}")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the StructureIQ launcher CLI."""

    args = parse_args(argv)
    raw_argv = list(argv if argv is not None else sys.argv[1:])

    if args.version:
        version = get_version()
        print(f"StructureIQ v{version}")
        write_startup_log(result="version", argv=raw_argv, version=version)
        return 0

    if args.urls:
        print_local_urls()
        return 0

    if args.validate:
        exit_code = run_system_validation()
        write_startup_log(result="system_validation", argv=raw_argv, details=f"exit_code={exit_code}")
        return exit_code

    health = run_startup_checks()

    if args.health:
        print_health(health)
        write_startup_log(
            result="health_pass" if health.passed else "health_fail",
            argv=raw_argv,
            details="; ".join(check.message for check in health.checks if not check.passed),
        )
        return 0 if health.passed else 1

    if not health.passed:
        print_health(health)
        print()
        print("StructureIQ could not start because startup validation failed.")
        write_startup_log(
            result="startup_validation_failed",
            argv=raw_argv,
            details="; ".join(check.message for check in health.checks if not check.passed),
        )
        return 1

    version = get_version()
    if args.paper:
        print(f"StructureIQ v{version}")
        exit_code = run_paper_mode(args)
        write_startup_log(result="paper_session", argv=raw_argv, version=version, details=f"exit_code={exit_code}")
        return exit_code
    print_banner(version)
    print_health(health)
    print_future_sections()
    if args.open_browser and not args.no_browser:
        schedule_browser_open()
    write_startup_log(result="startup_begin", argv=raw_argv, version=version)
    status_code = start_api()
    write_startup_log(
        result="shutdown" if status_code in (0, 130) else "startup_failed",
        argv=raw_argv,
        version=version,
        details=f"exit_code={status_code}",
    )
    return status_code


if __name__ == "__main__":
    raise SystemExit(main())
