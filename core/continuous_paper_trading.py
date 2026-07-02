"""Opt-in, paper-only continuous runtime built around existing coordinators."""

from __future__ import annotations

import hashlib
import json
import threading
from collections import deque
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field


class ContinuousPaperTradingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    auto_start: bool = False
    cycle_interval_seconds: float = Field(default=60.0, gt=0)
    auto_approve_candidates: bool = False
    require_validation_pass: bool = False
    allow_watchlist_validation: bool = True
    pause_on_validation_fail: bool = True
    pause_on_health_fail: bool = True
    pause_on_daily_loss_limit: bool = True
    pause_on_daily_profit_lock: bool = True
    pause_on_error_threshold: bool = True
    max_errors_before_pause: int = Field(default=5, ge=1)
    run_validation_on_start: bool = True
    validation_interval_cycles: int = Field(default=30, ge=1)
    generate_daily_reports: bool = True
    scheduler_enabled: bool = False
    session_label: str | None = None
    events_path: str = "reports/continuous_paper_events.jsonl"
    sessions_path: str = "reports/continuous_paper_sessions.jsonl"
    max_events_in_memory: int = Field(default=1000, ge=1, le=10000)


@dataclass(frozen=True)
class ContinuousPaperEvent:
    event_id: str
    timestamp: str
    session_id: str | None
    type: Literal["started", "cycle_completed", "paused", "resumed", "stopped", "error", "validation", "health_check"]
    status: Literal["PASS", "WATCHLIST", "FAIL", "INFO"]
    message: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class ContinuousPaperSession:
    session_id: str
    session_label: str | None
    started_at: str
    stopped_at: str | None
    status: Literal["running", "paused", "stopped", "failed"]
    cycle_count: int
    total_candidates_seen: int
    total_trades_opened: int
    total_trades_closed: int
    total_reports_generated: int
    error_count: int
    pause_reasons: tuple[str, ...]
    human_readable_summary: str


@dataclass(frozen=True)
class ContinuousPaperStatus:
    running: bool
    paused: bool
    enabled: bool
    session_id: str | None
    session_label: str | None
    started_at: str | None
    stopped_at: str | None
    cycle_count: int
    last_cycle_at: str | None
    last_cycle_status: str | None
    last_validation_status: str | None
    last_health_status: str | None
    error_count: int
    pause_reasons: tuple[str, ...]
    total_candidates_seen: int
    total_trades_opened: int
    total_trades_closed: int
    total_reports_generated: int
    config: ContinuousPaperTradingConfig
    paper_only: bool
    human_readable_summary: str


@dataclass(frozen=True)
class ContinuousPaperCycleResult:
    cycle_number: int
    cycle_id: str | None
    status: str
    candidates_seen: int
    trades_opened: int
    trades_closed: int
    report_generated: bool
    validation_status: str | None
    health_status: str | None
    paused: bool
    pause_reasons: tuple[str, ...]
    errors: tuple[str, ...]
    completed_at: str
    human_readable_summary: str


class ContinuousPaperTradingRuntime:
    """Repeat the existing orchestrator with health, validation, and risk guards."""

    def __init__(self, orchestrator: Any, health: Any, validation: Any, broker: Any, scheduler: Any,
                 config: ContinuousPaperTradingConfig | None = None) -> None:
        self.orchestrator, self.health, self.validation = orchestrator, health, validation
        self.broker, self.scheduler = broker, scheduler
        self.config = config or ContinuousPaperTradingConfig()
        self._events: deque[ContinuousPaperEvent] = deque(maxlen=self.config.max_events_in_memory)
        self._sessions: list[ContinuousPaperSession] = []
        self._lock = threading.RLock(); self._stop_event = threading.Event(); self._thread: threading.Thread | None = None
        self._session: ContinuousPaperSession | None = None
        self._last_cycle_at = self._last_cycle_status = self._last_validation_status = self._last_health_status = None
        self._stopped_at: str | None = None
        self._scheduler_started = False

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def start(self, config: ContinuousPaperTradingConfig | None = None) -> ContinuousPaperStatus:
        with self._lock:
            if self.running: return self.status()
            if config is not None: self.config = config; self._events = deque(self._events, maxlen=config.max_events_in_memory)
            now = _now(); sid = _id("continuous-session", now)
            self.config = self.config.model_copy(update={"enabled": True})
            self._stopped_at = None; self._stop_event.clear()
            self._session = ContinuousPaperSession(sid, self.config.session_label, now, None, "running", 0, 0, 0, 0, 0, 0, (), "Continuous paper session is running.")
            self._record("started", "INFO", "Continuous paper-trading session started.")
            if self.config.run_validation_on_start and not self._run_validation_guard():
                self._pause("Startup validation did not satisfy runtime policy.")
            if self.config.scheduler_enabled:
                try:
                    self.scheduler.start(); self._scheduler_started = True
                except Exception as exc:
                    self._record("error", "FAIL", f"Daily report scheduler could not start: {exc}")
                    self._pause("Daily report scheduler failed to start.")
            self._persist_session()
            self._thread = threading.Thread(target=self._loop, name="structureiq-continuous-paper", daemon=True)
            self._thread.start()
        return self.status()

    def stop(self) -> ContinuousPaperStatus:
        with self._lock: thread = self._thread; self._stop_event.set()
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=max(1.0, min(self.config.cycle_interval_seconds + .5, 5.0)))
        if self._scheduler_started:
            try: self.scheduler.stop()
            finally: self._scheduler_started = False
        with self._lock:
            if self._thread is thread and (thread is None or not thread.is_alive()): self._thread = None
            self.config = self.config.model_copy(update={"enabled": False})
            self._stopped_at = _now()
            if self._session:
                self._session = replace(self._session, stopped_at=self._stopped_at, status="stopped", human_readable_summary="Continuous paper session is stopped.")
            self._record("stopped", "INFO", "Continuous paper-trading session stopped."); self._persist_session()
        return self.status()

    def pause(self, reason: str = "Paused manually.") -> ContinuousPaperStatus:
        with self._lock: self._pause(reason)
        return self.status()

    def resume(self) -> ContinuousPaperStatus:
        with self._lock:
            if not self._session: raise RuntimeError("continuous paper trading has no active session")
            if not self._safety_guards(run_validation=True): return self.status()
            self._session = replace(self._session, status="running", pause_reasons=(), human_readable_summary="Continuous paper session is running.")
            self._record("resumed", "INFO", "Continuous paper-trading session resumed."); self._persist_session()
        return self.status()

    def run_once(self) -> ContinuousPaperCycleResult:
        with self._lock:
            if self._session is None:
                now = _now(); self._session = ContinuousPaperSession(_id("continuous-session", now), self.config.session_label, now, None, "running", 0, 0, 0, 0, 0, 0, (), "Manual paper validation session is active.")
            if self._session.status == "paused": return self._blocked_result("paused")
        errors: list[str] = []
        periodic = self._session.cycle_count % self.config.validation_interval_cycles == 0
        if not self._safety_guards(run_validation=periodic): return self._blocked_result("safety_paused")
        try:
            base = self.orchestrator.config.model_copy(update={
                "auto_approve_candidates": self.config.auto_approve_candidates,
                "require_manual_approval": not self.config.auto_approve_candidates,
                "generate_daily_report_after_cycle": self.config.generate_daily_reports,
            })
            result = self.orchestrator.run_cycle(base)
            errors.extend(result.errors)
        except Exception as exc:
            result = None; errors.append(str(exc)); self._record("error", "FAIL", f"Paper cycle failed: {exc}")
        with self._lock:
            old = self._session
            assert old is not None
            self._last_cycle_at = _now(); self._last_cycle_status = getattr(result, "status", "failed")
            self._session = replace(old, cycle_count=old.cycle_count + 1,
                total_candidates_seen=old.total_candidates_seen + int(getattr(result, "candidates_seen", 0)),
                total_trades_opened=old.total_trades_opened + int(getattr(result, "trades_opened", 0)),
                total_trades_closed=old.total_trades_closed + int(getattr(result, "trades_closed", 0)),
                total_reports_generated=old.total_reports_generated + int(bool(getattr(result, "daily_report_generated", False))),
                error_count=old.error_count + len(errors))
            if errors and self.config.pause_on_error_threshold and self._session.error_count >= self.config.max_errors_before_pause:
                self._pause("Runtime error threshold reached.")
            self._record("cycle_completed", "WATCHLIST" if errors else "PASS", f"Continuous paper cycle {self._session.cycle_count} completed.", {"errors": errors})
            self._persist_session()
            return ContinuousPaperCycleResult(self._session.cycle_count, getattr(result, "cycle_id", None), self._last_cycle_status,
                int(getattr(result, "candidates_seen", 0)), int(getattr(result, "trades_opened", 0)), int(getattr(result, "trades_closed", 0)),
                bool(getattr(result, "daily_report_generated", False)), self._last_validation_status, self._last_health_status,
                self._session.status == "paused", self._session.pause_reasons, tuple(errors), self._last_cycle_at,
                f"Continuous paper cycle completed with {int(getattr(result, 'trades_opened', 0))} paper trades opened.")

    def status(self) -> ContinuousPaperStatus:
        with self._lock:
            s = self._session; paused = bool(s and s.status == "paused")
            return ContinuousPaperStatus(self.running, paused, self.config.enabled, s.session_id if s else None,
                s.session_label if s else self.config.session_label, s.started_at if s else None, self._stopped_at,
                s.cycle_count if s else 0, self._last_cycle_at, self._last_cycle_status, self._last_validation_status,
                self._last_health_status, s.error_count if s else 0, s.pause_reasons if s else (),
                s.total_candidates_seen if s else 0, s.total_trades_opened if s else 0, s.total_trades_closed if s else 0,
                s.total_reports_generated if s else 0, self.config, True,
                "Continuous paper trading is paused." if paused else "Continuous paper trading is running." if self.running else "Continuous paper trading is stopped.")

    def events(self, limit: int | None = None) -> tuple[ContinuousPaperEvent, ...]:
        items = tuple(self._events); return items[-limit:] if limit else items

    def sessions(self, limit: int | None = None) -> tuple[ContinuousPaperSession, ...]:
        items = tuple(self._sessions + ([self._session] if self._session and (not self._sessions or self._sessions[-1] != self._session) else []))
        return items[-limit:] if limit else items

    def _safety_guards(self, *, run_validation: bool) -> bool:
        try:
            health = self.health.check(write_log=False); self._last_health_status = health.status
            self._record("health_check", health.status, health.human_readable_summary)
            if health.status == "FAIL" and self.config.pause_on_health_fail: self._pause("System health check failed."); return False
        except Exception as exc:
            self._record("error", "FAIL", f"Health check failed: {exc}")
            if self.config.pause_on_health_fail: self._pause("System health check could not complete."); return False
        if run_validation and not self._run_validation_guard(): return False
        risk = self.broker.account().risk_status
        if risk == "daily_loss_limit_reached" and self.config.pause_on_daily_loss_limit: self._pause("Paper account daily loss limit reached."); return False
        if risk == "daily_profit_lock_reached" and self.config.pause_on_daily_profit_lock: self._pause("Paper account daily profit lock reached."); return False
        return True

    def _run_validation_guard(self) -> bool:
        try:
            validation = self.validation.run(); self._last_validation_status = validation.validation_status
            self._record("validation", validation.validation_status, validation.human_readable_summary)
            failed = validation.validation_status == "FAIL"
            disallowed_watch = validation.validation_status == "WATCHLIST" and (self.config.require_validation_pass or not self.config.allow_watchlist_validation)
            if (failed and self.config.pause_on_validation_fail) or disallowed_watch: return False
            return True
        except Exception as exc:
            self._last_validation_status = "FAIL"; self._record("error", "FAIL", f"Validation failed: {exc}")
            return not self.config.pause_on_validation_fail

    def _pause(self, reason: str) -> None:
        if not self._session: return
        reasons = tuple(dict.fromkeys((*self._session.pause_reasons, reason)))
        self._session = replace(self._session, status="paused", pause_reasons=reasons, human_readable_summary=f"Session paused: {reason}")
        self._record("paused", "WATCHLIST", reason); self._persist_session()

    def _blocked_result(self, status: str) -> ContinuousPaperCycleResult:
        s = self._session; return ContinuousPaperCycleResult(s.cycle_count if s else 0, None, status, 0, 0, 0, False,
            self._last_validation_status, self._last_health_status, True, s.pause_reasons if s else (), (), _now(), "No cycle ran because the runtime is paused by a safety policy.")

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            if self._session and self._session.status != "paused": self.run_once()
            self._stop_event.wait(self.config.cycle_interval_seconds)

    def _record(self, kind: str, status: str, message: str, metadata: dict[str, Any] | None = None) -> None:
        now = _now(); event = ContinuousPaperEvent(_id("continuous-event", f"{now}:{len(self._events)}"), now,
            self._session.session_id if self._session else None, kind, status, message, metadata or {})
        self._events.append(event); _append_jsonl(Path(self.config.events_path), event)

    def _persist_session(self) -> None:
        if not self._session: return
        if self._sessions and self._sessions[-1].session_id == self._session.session_id: self._sessions[-1] = self._session
        else: self._sessions.append(self._session)
        _append_jsonl(Path(self.config.sessions_path), self._session)


_GLOBAL_RUNTIME: ContinuousPaperTradingRuntime | None = None
_GLOBAL_LOCK = threading.RLock()


def get_global_continuous_paper_trading(orchestrator: Any, health: Any, validation: Any, broker: Any, scheduler: Any) -> ContinuousPaperTradingRuntime:
    global _GLOBAL_RUNTIME
    with _GLOBAL_LOCK:
        if _GLOBAL_RUNTIME is None:
            _GLOBAL_RUNTIME = ContinuousPaperTradingRuntime(orchestrator, health, validation, broker, scheduler)
        return _GLOBAL_RUNTIME


def current_continuous_paper_trading() -> ContinuousPaperTradingRuntime | None:
    return _GLOBAL_RUNTIME


def _append_jsonl(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(jsonable_encoder(value), sort_keys=True) + "\n")


def _now() -> str: return datetime.now(timezone.utc).isoformat()
def _id(prefix: str, value: str) -> str: return hashlib.sha256(f"{prefix}:{value}".encode()).hexdigest()[:24]
