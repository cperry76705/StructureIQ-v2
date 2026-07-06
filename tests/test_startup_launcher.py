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
    assert "StructureIQ v6.0.6" in output


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
        version="6.0.6",
        details="ok",
    )

    contents = log_file.read_text(encoding="utf-8")
    assert "result=test_pass" in contents
    assert "version=6.0.6" in contents
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
    assert "StructureIQ v6.0.6" in output
    assert "Status:" in output
    assert "READY" in output
    assert "Paper Trading: AVAILABLE/ADVISORY - NOT AUTO-STARTED" in output
    assert "Trade Lifecycle Manager: AVAILABLE/ADVISORY - NOT AUTO-STARTED" in output
    assert "Automated Journal: AVAILABLE/ADVISORY - NOT AUTO-STARTED" in output
    assert "Daily Reports: AVAILABLE/ADVISORY - NOT AUTO-STARTED" in output
    assert "Paper Trading Orchestrator: AVAILABLE/ADVISORY - NOT AUTO-STARTED" in output
    assert "Scheduled Reports: AVAILABLE/ADVISORY - NOT AUTO-STARTED" in output
    assert "System Health: AVAILABLE/ADVISORY" in output


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


def test_startup_urls_are_browser_facing_localhost(capsys) -> None:
    start.print_banner("6.0.2")
    output = capsys.readouterr().out
    assert "http://localhost:8000/docs" in output
    assert "Use localhost in your browser" in output
    assert "http://0.0.0.0" not in output


def test_urls_command_prints_expected_endpoints(capsys) -> None:
    assert start.main(["--urls"]) == 0
    output = capsys.readouterr().out
    for path in ("/docs", "/health", "/system/health", "/dashboard/overview", "/continuous-paper/status"):
        assert f"http://localhost:8000{path}" in output


def test_browser_open_success_and_failure_are_nonfatal(monkeypatch, capsys) -> None:
    seen = []
    assert start.open_docs_browser(opener=lambda url: seen.append(url) or True)
    assert seen == ["http://localhost:8000/docs"]
    monkeypatch.setattr(start, "write_startup_log", lambda **kwargs: None)
    assert not start.open_docs_browser(opener=lambda url: (_ for _ in ()).throw(RuntimeError("no browser")))
    assert "Browser open warning" in capsys.readouterr().out


def test_open_browser_flag_schedules_docs_open(monkeypatch) -> None:
    scheduled = []
    monkeypatch.setattr(start, "schedule_browser_open", lambda: scheduled.append(True))
    monkeypatch.setattr(start, "start_api", lambda: 0)
    monkeypatch.setattr(start, "write_startup_log", lambda **kwargs: None)
    assert start.main(["--open-browser"]) == 0
    assert scheduled == [True]


def test_no_browser_overrides_open_browser(monkeypatch) -> None:
    scheduled = []
    monkeypatch.setattr(start, "schedule_browser_open", lambda: scheduled.append(True))
    monkeypatch.setattr(start, "start_api", lambda: 0)
    monkeypatch.setattr(start, "write_startup_log", lambda **kwargs: None)
    assert start.main(["--open-browser", "--no-browser"]) == 0
    assert scheduled == []


def test_paper_duration_cli_mapping_and_shortest_warning() -> None:
    cases = [
        (["--paper", "--minutes", "30"], "run_for_minutes", 30),
        (["--paper", "--hours", "2"], "run_for_hours", 2),
        (["--paper", "--days", "2"], "run_for_hours", 48),
        (["--paper", "--weeks", "2"], "run_for_hours", 336),
        (["--paper", "--months", "1"], "run_for_hours", 720),
    ]
    for argv, key, expected in cases:
        payload, warnings, _ = start.build_paper_start_payload(start.parse_args(argv))
        assert payload[key] == expected and not warnings
    payload, _, _ = start.build_paper_start_payload(start.parse_args(["--paper", "--cycles", "20"]))
    assert payload["max_cycles"] == 20
    payload, warnings, _ = start.build_paper_start_payload(start.parse_args(["--paper", "--hours", "2", "--minutes", "30"]))
    assert payload["run_for_minutes"] == 30 and "run_for_hours" not in payload
    assert "shortest" in warnings[0]


class _PaperProcess:
    def __init__(self): self.terminated = False
    def poll(self): return None if not self.terminated else 0
    def terminate(self): self.terminated = True
    def wait(self, timeout=None): return 0
    def kill(self): self.terminated = True


def test_paper_mode_blocks_fail_and_allows_watchlist(capsys) -> None:
    process = _PaperProcess()
    def failed(path, **kwargs):
        if path == "/health": return {"status": "ok"}
        return {"validation_status": "FAIL"}
    args = start.parse_args(["--paper", "--minutes", "1"])
    assert start.run_paper_mode(args, process_factory=lambda *a, **k: process, api_call=failed, sleep=lambda _: None, port_available=lambda: True) == 2
    assert "blocked" in capsys.readouterr().out

    process = _PaperProcess()
    def watchlist(path, **kwargs):
        if path == "/health": return {"status": "ok"}
        if path == "/system/validation/run": return {"validation_status": "WATCHLIST"}
        if path == "/continuous-paper/start":
            return {"running": False, "paused": False, "session_label": "test", "stop_reason": "max_cycles_reached", "final_session_summary": {"cycle_count": 1, "stop_reason": "max_cycles_reached"}}
        return {"running": False}
    assert start.run_paper_mode(args, process_factory=lambda *a, **k: process, api_call=watchlist, sleep=lambda _: None, port_available=lambda: True) == 0
    assert "Validation: WATCHLIST" in capsys.readouterr().out


def test_paper_mode_ctrl_c_stops_runtime_safely() -> None:
    process = _PaperProcess(); calls = []
    def api(path, **kwargs):
        calls.append((path, kwargs.get("method")))
        if path == "/health": return {"status": "ok"}
        if path == "/system/validation/run": return {"validation_status": "PASS"}
        if path == "/continuous-paper/start": return {"running": True, "paused": False, "session_label": "test"}
        if path == "/continuous-paper/stop": return {"running": False, "stop_reason": "manual_stop"}
        return {"running": True}
    def interrupt(_): raise KeyboardInterrupt
    args = start.parse_args(["--paper", "--cycles", "2"])
    assert start.run_paper_mode(args, process_factory=lambda *a, **k: process, api_call=api, sleep=interrupt, port_available=lambda: True) == 130
    assert ("/continuous-paper/stop", "POST") in calls


def test_paper_mode_uses_one_windows_safe_no_reload_api_process() -> None:
    processes = []; api_calls = []
    def factory(command, **kwargs):
        processes.append(command)
        return _PaperProcess()
    def api(path, **kwargs):
        api_calls.append((path, kwargs.get("method")))
        if path == "/health": return {"status": "ok"}
        if path == "/system/validation/run": return {"validation_status": "PASS"}
        if path == "/continuous-paper/start":
            return {"running": False, "paused": False, "stop_reason": "max_cycles_reached", "final_session_summary": {"cycle_count": 1, "stop_reason": "max_cycles_reached"}}
        return {"running": False}
    args = start.parse_args(["--paper", "--cycles", "1"])
    result = start.run_paper_mode(args, process_factory=factory, api_call=api, sleep=lambda _: None, port_available=lambda: True)
    assert result == 0
    assert len(processes) == 1
    assert "--reload" not in processes[0]
    assert api_calls.count(("/continuous-paper/start", "POST")) == 1
    assert api_calls.index(("/health", None)) < api_calls.index(("/continuous-paper/start", "POST"))


def test_paper_mode_port_preflight_blocks_before_process_creation(capsys) -> None:
    processes = []
    args = start.parse_args(["--paper", "--hours", "2"])
    result = start.run_paper_mode(
        args,
        process_factory=lambda *a, **k: processes.append(a),
        port_available=lambda: False,
    )
    assert result == 2
    assert processes == []
    assert "Port 8000 is already in use" in capsys.readouterr().out
