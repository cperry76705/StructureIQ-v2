import time
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app, get_continuous_paper_trading
from core.continuous_paper_trading import ContinuousPaperTradingConfig, ContinuousPaperTradingRuntime
from core.paper_trading_orchestrator import PaperTradingOrchestratorConfig
from core.system_health import SystemHealthEngine


class _Orchestrator:
    def __init__(self, *, errors=()):
        self.config = PaperTradingOrchestratorConfig(generate_daily_report_after_cycle=False)
        self.calls = 0; self.errors = errors

    def run_cycle(self, config):
        self.calls += 1; self.config = config
        return SimpleNamespace(cycle_id=f"cycle-{self.calls}", status="completed_with_errors" if self.errors else "completed",
            candidates_seen=2, trades_opened=1, trades_closed=0, daily_report_generated=config.generate_daily_report_after_cycle,
            errors=tuple(self.errors))


class _Health:
    def __init__(self, status="PASS"): self.value = status
    def check(self, write_log=False): return SimpleNamespace(status=self.value, human_readable_summary=f"Health is {self.value}.")


class _Validation:
    def __init__(self, status="PASS"): self.value = status; self.calls = 0
    def run(self):
        self.calls += 1
        return SimpleNamespace(validation_status=self.value, human_readable_summary=f"Validation is {self.value}.")


class _Broker:
    def __init__(self, risk="available"): self.risk = risk
    def account(self): return SimpleNamespace(risk_status=self.risk)


def _runtime(tmp_path: Path, *, health="PASS", validation="PASS", risk="available", errors=(), **updates):
    config = ContinuousPaperTradingConfig(events_path=str(tmp_path / "events.jsonl"), sessions_path=str(tmp_path / "sessions.jsonl"),
        cycle_interval_seconds=.01, run_validation_on_start=False, **updates)
    return ContinuousPaperTradingRuntime(_Orchestrator(errors=errors), _Health(health), _Validation(validation), _Broker(risk), SimpleNamespace(), config)


def test_runtime_initializes_stopped(tmp_path):
    state = _runtime(tmp_path).status()
    assert not state.running and not state.paused and not state.enabled and state.paper_only


def test_run_once_executes_existing_orchestrator_and_updates_session(tmp_path):
    runtime = _runtime(tmp_path)
    result = runtime.run_once()
    assert result.status == "completed" and result.trades_opened == 1
    assert runtime.status().cycle_count == 1 and runtime.status().total_candidates_seen == 2


def test_start_stop_pause_and_resume_are_safe(tmp_path):
    runtime = _runtime(tmp_path)
    assert runtime.start().running
    time.sleep(.03)
    runtime.pause("manual test")
    # An already-running cycle may finish; once settled, pause prevents new work.
    time.sleep(.02)
    paused_cycles = runtime.status().cycle_count
    time.sleep(.03)
    assert runtime.status().cycle_count == paused_cycles
    assert not runtime.resume().paused
    time.sleep(.02)
    assert runtime.stop().running is False


def test_validation_fail_pauses_but_watchlist_can_run(tmp_path):
    failed = _runtime(tmp_path / "fail", validation="FAIL", pause_on_validation_fail=True)
    failed.config = failed.config.model_copy(update={"run_validation_on_start": True})
    assert failed.start().paused
    failed.stop()
    watch = _runtime(tmp_path / "watch", validation="WATCHLIST", allow_watchlist_validation=True)
    assert watch.run_once().status == "completed"


def test_health_and_paper_risk_pause_runtime(tmp_path):
    assert _runtime(tmp_path / "health", health="FAIL").run_once().paused
    assert "daily loss" in _runtime(tmp_path / "loss", risk="daily_loss_limit_reached").run_once().pause_reasons[0].lower()
    assert "profit lock" in _runtime(tmp_path / "profit", risk="daily_profit_lock_reached").run_once().pause_reasons[0].lower()


def test_error_threshold_events_and_persistence(tmp_path):
    runtime = _runtime(tmp_path, errors=("recoverable",), max_errors_before_pause=1)
    result = runtime.run_once()
    assert result.paused and runtime.status().error_count == 1
    assert any(item.type == "cycle_completed" for item in runtime.events())
    assert (tmp_path / "events.jsonl").read_text(encoding="utf-8").strip()
    assert (tmp_path / "sessions.jsonl").read_text(encoding="utf-8").strip()


def test_api_endpoints_and_dashboard_fields(tmp_path):
    runtime = _runtime(tmp_path)
    app.dependency_overrides[get_continuous_paper_trading] = lambda: runtime
    try:
        client = TestClient(app)
        paths = client.get("/openapi.json").json()["paths"]
        assert all(path in paths for path in ("/continuous-paper/status", "/continuous-paper/start", "/continuous-paper/stop", "/continuous-paper/pause", "/continuous-paper/resume", "/continuous-paper/run-once", "/continuous-paper/events", "/continuous-paper/sessions"))
        assert client.post("/continuous-paper/run-once").status_code == 200
        assert client.get("/continuous-paper/status").json()["cycle_count"] == 1
        overview = client.get("/dashboard/overview").json()
        assert "continuous_paper_running" in overview and "continuous_paper_readiness" in overview
    finally:
        app.dependency_overrides.clear()


def test_system_health_exposes_continuous_component(tmp_path):
    report = SystemHealthEngine(project_root=tmp_path).check(write_log=False)
    assert "continuous_paper_trading" in {item.name for item in report.dimensions}


def test_minute_and_hour_limits_set_estimated_stop_and_remaining_time(tmp_path):
    minutes = _runtime(tmp_path / "minutes", run_for_minutes=30)
    minute_status = minutes.start()
    assert minute_status.estimated_stop_at and 0 < minute_status.remaining_seconds <= 1800
    minutes.stop()

    hours = _runtime(tmp_path / "hours", run_for_hours=1)
    hour_status = hours.start()
    assert hour_status.estimated_stop_at and 3500 < hour_status.remaining_seconds <= 3600
    hours.stop()


def test_max_cycles_automatically_completes_session(tmp_path):
    runtime = _runtime(tmp_path, max_cycles=2)
    runtime.start()
    deadline = time.time() + 1
    while runtime.status().stop_reason is None and time.time() < deadline:
        time.sleep(.01)
    status = runtime.status()
    assert status.stop_reason == "max_cycles_reached"
    assert status.final_session_summary.final_status == "completed"
    assert status.final_session_summary.cycle_count == 2
    assert runtime.sessions()[-1].status == "completed"


def test_first_limit_wins_and_duration_auto_stop_is_completed(tmp_path):
    cycles = _runtime(tmp_path / "cycles", max_cycles=1, run_for_hours=1)
    cycles.start()
    deadline = time.time() + 1
    while cycles.status().stop_reason is None and time.time() < deadline:
        time.sleep(.01)
    assert cycles.status().stop_reason == "max_cycles_reached"

    duration = _runtime(tmp_path / "duration", run_for_minutes=.0005, max_cycles=100)
    duration.start()
    deadline = time.time() + 1
    while duration.status().stop_reason is None and time.time() < deadline:
        time.sleep(.01)
    assert duration.status().stop_reason == "duration_limit_reached"
    assert duration.sessions()[-1].final_session_summary.duration_seconds >= 0


def test_manual_stop_records_reason_and_final_summary(tmp_path):
    runtime = _runtime(tmp_path, run_for_hours=1)
    runtime.start(); status = runtime.stop()
    assert status.stop_reason == "manual_stop"
    assert status.final_session_summary.stop_reason == "manual_stop"
    assert status.final_session_summary.final_status == "stopped"
