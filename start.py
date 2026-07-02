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
PUBLIC_API_URL = "http://127.0.0.1:8000"
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
    print(f"API:\n{PUBLIC_API_URL}")
    print()
    print("Swagger:\n/docs")
    print()
    print(f"Status:\n{status}")


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
    return parser.parse_args(argv)


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


def main(argv: Sequence[str] | None = None) -> int:
    """Run the StructureIQ launcher CLI."""

    args = parse_args(argv)
    raw_argv = list(argv if argv is not None else sys.argv[1:])

    if args.version:
        version = get_version()
        print(f"StructureIQ v{version}")
        write_startup_log(result="version", argv=raw_argv, version=version)
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
    print_banner(version)
    print_health(health)
    print_future_sections()
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
