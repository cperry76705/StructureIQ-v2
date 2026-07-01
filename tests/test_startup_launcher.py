"""Regression tests for the official StructureIQ launcher."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import start


def test_version_command_prints_current_version(capsys) -> None:
    exit_code = start.main(["--version"])

    output = capsys.readouterr().out

    assert exit_code == 0
    assert "StructureIQ v5.5.0" in output


def test_health_command_runs_startup_validation(capsys) -> None:
    exit_code = start.main(["--health"])

    output = capsys.readouterr().out

    assert exit_code == 0
    assert "System Health:" in output
    assert "PASS" in output
    assert "FastAPI import" in output


def test_directory_validation_reports_missing_required_folder(tmp_path: Path) -> None:
    for folder in ("app", "core", "models", "docs"):
        (tmp_path / folder).mkdir()
    (tmp_path / "requirements.txt").write_text("fastapi\n", encoding="utf-8")
    (tmp_path / "app" / "config.py").write_text("APP_VERSION='x'\n", encoding="utf-8")

    health = start.run_startup_checks(tmp_path)

    directory_check = next(
        check for check in health.checks if check.name == "Directory structure"
    )
    assert not directory_check.passed
    assert "tests" in directory_check.message


def test_configuration_validation_reports_missing_required_file(tmp_path: Path) -> None:
    for folder in ("app", "core", "models", "tests", "docs"):
        (tmp_path / folder).mkdir()
    (tmp_path / "app" / "config.py").write_text("APP_VERSION='x'\n", encoding="utf-8")

    health = start.run_startup_checks(tmp_path)

    configuration_check = next(
        check for check in health.checks if check.name == "Configuration files"
    )
    assert not configuration_check.passed
    assert "requirements.txt" in configuration_check.message


def test_api_launch_command_generation_uses_uvicorn_module() -> None:
    command = start.build_uvicorn_command()

    assert command[:4] == [sys.executable, "-m", "uvicorn", "app.main:app"]
    assert command[-1] == "--reload"
    assert "--host" in command
    assert "0.0.0.0" in command
    assert "--port" in command
    assert "8000" in command


def test_api_launch_command_can_disable_reload() -> None:
    command = start.build_uvicorn_command(host="127.0.0.1", port="9000", reload=False)

    assert "--reload" not in command
    assert "127.0.0.1" in command
    assert "9000" in command


def test_ctrl_c_handling_returns_standard_interrupt_code(capsys) -> None:
    def raise_keyboard_interrupt(*args, **kwargs):
        raise KeyboardInterrupt

    exit_code = start.start_api(["fake"], runner=raise_keyboard_interrupt)

    assert exit_code == 130
    assert "stopped cleanly" in capsys.readouterr().out


def test_logging_writes_startup_log(tmp_path: Path, monkeypatch) -> None:
    log_dir = tmp_path / "logs"
    log_file = log_dir / "startup.log"
    monkeypatch.setattr(start, "LOG_DIR", log_dir)
    monkeypatch.setattr(start, "LOG_FILE", log_file)

    start.write_startup_log(
        result="test_pass",
        argv=["--health"],
        version="5.5.0",
        details="ok",
    )

    contents = log_file.read_text(encoding="utf-8")
    assert "result=test_pass" in contents
    assert "version=5.5.0" in contents
    assert "arguments=--health" in contents
    assert "details=ok" in contents


def test_successful_startup_path_launches_api(monkeypatch, capsys) -> None:
    calls: list[list[str]] = []

    def fake_runner(command, cwd=None, check=False):
        calls.append(list(command))
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(start, "write_startup_log", lambda **kwargs: None)
    monkeypatch.setattr(start.subprocess, "run", fake_runner)

    exit_code = start.main(["--api"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert calls
    assert calls[0][:4] == [sys.executable, "-m", "uvicorn", "app.main:app"]
    assert "StructureIQ v5.5.0" in output
    assert "Status:" in output
    assert "READY" in output
    assert "Paper Trading: AVAILABLE/ADVISORY - NOT AUTO-STARTED" in output
    assert "Trade Lifecycle Manager: AVAILABLE/ADVISORY - NOT AUTO-STARTED" in output
    assert "Automated Journal: AVAILABLE/ADVISORY - NOT AUTO-STARTED" in output
    assert "Daily Reports: AVAILABLE/ADVISORY - NOT AUTO-STARTED" in output


def test_failed_startup_path_returns_nonzero(monkeypatch, capsys) -> None:
    failing_health = start.StartupHealth()
    failing_health.add("Directory structure", False, "Missing required folders: core")

    monkeypatch.setattr(start, "run_startup_checks", lambda: failing_health)
    monkeypatch.setattr(start, "write_startup_log", lambda **kwargs: None)

    exit_code = start.main([])

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "System Health:" in output
    assert "FAIL" in output
    assert "could not start" in output


def test_api_subprocess_failure_returns_status_code() -> None:
    def fake_runner(command, cwd=None, check=False):
        return SimpleNamespace(returncode=7)

    assert start.start_api(["fake"], runner=fake_runner) == 7
