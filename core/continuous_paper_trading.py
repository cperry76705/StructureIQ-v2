"""Opt-in, paper-only continuous runtime built around existing coordinators."""

from __future__ import annotations

import hashlib
import json
import threading
from collections import deque
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field

from core.trade_lifecycle_manager import OrderType


class ContinuousPaperTradingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    auto_start: bool = False
    paper_only: Literal[True] = True
    live_trading_enabled: Literal[False] = False
    broker_connections_enabled: Literal[False] = False
    cycle_interval_seconds: float = Field(default=60.0, gt=0)
    auto_approve_candidates: bool = False
    allow_market_orders: bool = False
    default_order_type: OrderType = OrderType.LIMIT_RETEST
    max_candidates_per_cycle: int = Field(default=3, ge=1)
    max_trades_per_cycle: int = Field(default=1, ge=1)
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
    campaign_name: str | None = None
    run_for_minutes: float | None = Field(default=None, gt=0)
    run_for_hours: float | None = Field(default=None, gt=0)
    max_cycles: int | None = Field(default=None, ge=1)
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
class ContinuousPaperSessionSummary:
    session_id: str
    started_at: str
    stopped_at: str
    duration_seconds: float
    cycle_count: int
    total_candidates_seen: int
    total_trades_opened: int
    total_trades_closed: int
    total_reports_generated: int
    total_reports_skipped_existing: int
    error_count: int
    pause_reasons: tuple[str, ...]
    stop_reason: str
    final_status: str
    human_readable_summary: str


@dataclass(frozen=True)
class ContinuousPaperSession:
    session_id: str
    session_label: str | None
    started_at: str
    stopped_at: str | None
    status: Literal["running", "paused", "stopped", "completed", "failed"]
    cycle_count: int
    total_candidates_seen: int
    total_trades_opened: int
    total_trades_closed: int
    total_reports_generated: int
    total_reports_skipped_existing: int
    error_count: int
    pause_reasons: tuple[str, ...]
    stop_reason: str | None
    final_session_summary: ContinuousPaperSessionSummary | None
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
    total_reports_skipped_existing: int
    estimated_stop_at: str | None
    remaining_seconds: float | None
    run_for_minutes: float | None
    run_for_hours: float | None
    max_cycles: int | None
    stop_reason: str | None
    final_session_summary: ContinuousPaperSessionSummary | None
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
    daily_report_status: str
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
        self._estimated_stop_at: str | None = None
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
            self._estimated_stop_at = _estimated_stop(now, self.config)
            self._stopped_at = None; self._stop_event.clear()
            self._session = ContinuousPaperSession(
                session_id=sid, session_label=self.config.session_label,
                started_at=now, stopped_at=None, status="running", cycle_count=0,
                total_candidates_seen=0, total_trades_opened=0,
                total_trades_closed=0, total_reports_generated=0,
                total_reports_skipped_existing=0,
                error_count=0, pause_reasons=(), stop_reason=None,
                final_session_summary=None,
                human_readable_summary="Continuous paper session is running.",
            )
            if self.config.campaign_name or self.config.session_label:
                try:
                    from core.validation_campaigns import get_global_validation_campaign_manager
                    get_global_validation_campaign_manager().start(
                        self.config.campaign_name or self.config.session_label,
                        cli=None,
                        paper_settings=self.config.model_dump(mode="json"),
                    )
                except Exception as exc:
                    self._record("error", "WATCHLIST", f"Campaign could not be started: {exc}")
            self._record("started", "INFO", "Continuous paper-trading session started.")
            if self.config.run_validation_on_start and not self._run_validation_guard():
                self._pause("Startup validation did not satisfy runtime policy.", stop_reason="safety_pause")
            if self.config.scheduler_enabled:
                try:
                    self.scheduler.start(); self._scheduler_started = True
                except Exception as exc:
                    self._record("error", "FAIL", f"Daily report scheduler could not start: {exc}")
                    self._pause("Daily report scheduler failed to start.", stop_reason="safety_pause")
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
            self._finish_session("manual_stop", "stopped")
            self._record("stopped", "INFO", "Continuous paper-trading session stopped."); self._persist_session()
        return self.status()

    def pause(self, reason: str = "Paused manually.") -> ContinuousPaperStatus:
        with self._lock: self._pause(reason)
        return self.status()

    def resume(self) -> ContinuousPaperStatus:
        with self._lock:
            if not self._session: raise RuntimeError("continuous paper trading has no active session")
            if not self._safety_guards(run_validation=True): return self.status()
            self._session = replace(self._session, status="running", pause_reasons=(), stop_reason=None,
                human_readable_summary="Continuous paper session is running.")
            self._record("resumed", "INFO", "Continuous paper-trading session resumed."); self._persist_session()
        return self.status()

    def run_once(self) -> ContinuousPaperCycleResult:
        with self._lock:
            if self._session is None:
                now = _now(); self._estimated_stop_at = _estimated_stop(now, self.config)
                self._session = ContinuousPaperSession(
                    session_id=_id("continuous-session", now), session_label=self.config.session_label,
                    started_at=now, stopped_at=None, status="running", cycle_count=0,
                    total_candidates_seen=0, total_trades_opened=0,
                    total_trades_closed=0, total_reports_generated=0,
                    total_reports_skipped_existing=0,
                    error_count=0, pause_reasons=(), stop_reason=None,
                    final_session_summary=None,
                    human_readable_summary="Manual paper validation session is active.",
                )
            if self._session.status == "paused": return self._blocked_result("paused")
        errors: list[str] = []
        periodic = self._session.cycle_count % self.config.validation_interval_cycles == 0
        if not self._safety_guards(run_validation=periodic): return self._blocked_result("safety_paused")
        try:
            base = self.orchestrator.config.model_copy(update={
                "auto_approve_candidates": self.config.auto_approve_candidates,
                "require_manual_approval": not self.config.auto_approve_candidates,
                "paper_only": self.config.paper_only,
                "live_trading_enabled": self.config.live_trading_enabled,
                "broker_connections_enabled": self.config.broker_connections_enabled,
                "allow_market_orders": self.config.allow_market_orders,
                "default_order_type": self.config.default_order_type,
                "max_candidates_per_cycle": self.config.max_candidates_per_cycle,
                "max_new_trades_per_cycle": self.config.max_trades_per_cycle,
                "generate_daily_report_after_cycle": self.config.generate_daily_reports,
                "report_overwrite": False,
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
                total_reports_skipped_existing=old.total_reports_skipped_existing + int(getattr(result, "daily_report_status", "") == "skipped_existing"),
                error_count=old.error_count + len(errors))
            if errors and self.config.pause_on_error_threshold and self._session.error_count >= self.config.max_errors_before_pause:
                self._pause("Runtime error threshold reached.", stop_reason="error_threshold")
            self._record("cycle_completed", "WATCHLIST" if errors else "PASS", f"Continuous paper cycle {self._session.cycle_count} completed.", {"errors": errors})
            self._persist_session()
            cycle_number = self._session.cycle_count
            limit_reason = self._limit_reason()
            if limit_reason and self._session.status == "running":
                self._finish_session(limit_reason, "completed")
                self._record("stopped", "PASS", f"Session completed: {limit_reason}.")
                self._persist_session()
            report_status = str(getattr(result, "daily_report_status", "generated" if getattr(result, "daily_report_generated", False) else "disabled"))
            return ContinuousPaperCycleResult(
                cycle_number=cycle_number, cycle_id=getattr(result, "cycle_id", None), status=self._last_cycle_status,
                candidates_seen=int(getattr(result, "candidates_seen", 0)), trades_opened=int(getattr(result, "trades_opened", 0)),
                trades_closed=int(getattr(result, "trades_closed", 0)), report_generated=bool(getattr(result, "daily_report_generated", False)),
                daily_report_status=report_status, validation_status=self._last_validation_status,
                health_status=self._last_health_status, paused=self._session.status == "paused",
                pause_reasons=self._session.pause_reasons, errors=tuple(errors), completed_at=self._last_cycle_at,
                human_readable_summary=f"Continuous paper cycle completed with {int(getattr(result, 'trades_opened', 0))} paper trades opened and daily report {report_status}.",
            )

    def status(self) -> ContinuousPaperStatus:
        with self._lock:
            s = self._session; paused = bool(s and s.status == "paused")
            return ContinuousPaperStatus(
                running=self.running, paused=paused, enabled=self.config.enabled,
                session_id=s.session_id if s else None,
                session_label=s.session_label if s else self.config.session_label,
                started_at=s.started_at if s else None, stopped_at=self._stopped_at,
                cycle_count=s.cycle_count if s else 0, last_cycle_at=self._last_cycle_at,
                last_cycle_status=self._last_cycle_status,
                last_validation_status=self._last_validation_status,
                last_health_status=self._last_health_status,
                error_count=s.error_count if s else 0,
                pause_reasons=s.pause_reasons if s else (),
                total_candidates_seen=s.total_candidates_seen if s else 0,
                total_trades_opened=s.total_trades_opened if s else 0,
                total_trades_closed=s.total_trades_closed if s else 0,
                total_reports_generated=s.total_reports_generated if s else 0,
                total_reports_skipped_existing=s.total_reports_skipped_existing if s else 0,
                estimated_stop_at=self._estimated_stop_at,
                remaining_seconds=self._remaining_seconds(),
                run_for_minutes=self.config.run_for_minutes,
                run_for_hours=self.config.run_for_hours,
                max_cycles=self.config.max_cycles,
                stop_reason=s.stop_reason if s else None,
                final_session_summary=s.final_session_summary if s else None,
                config=self.config, paper_only=True,
                human_readable_summary=(
                    "Continuous paper trading is paused." if paused else
                    "Continuous paper trading is running." if self.running else
                    "Continuous paper session completed." if s and s.status == "completed" else
                    "Continuous paper trading is stopped."
                ),
            )

    def events(self, limit: int | None = None) -> tuple[ContinuousPaperEvent, ...]:
        items = tuple(self._events); return items[-limit:] if limit else items

    def sessions(self, limit: int | None = None) -> tuple[ContinuousPaperSession, ...]:
        items = tuple(self._sessions + ([self._session] if self._session and (not self._sessions or self._sessions[-1] != self._session) else []))
        return items[-limit:] if limit else items

    def _safety_guards(self, *, run_validation: bool) -> bool:
        try:
            health = self.health.check(write_log=False); self._last_health_status = health.status
            self._record("health_check", health.status, health.human_readable_summary)
            if health.status == "FAIL" and self.config.pause_on_health_fail: self._pause("System health check failed.", stop_reason="safety_pause"); return False
        except Exception as exc:
            self._record("error", "FAIL", f"Health check failed: {exc}")
            if self.config.pause_on_health_fail: self._pause("System health check could not complete.", stop_reason="safety_pause"); return False
        if run_validation and not self._run_validation_guard(): return False
        risk = self.broker.account().risk_status
        if risk == "daily_loss_limit_reached" and self.config.pause_on_daily_loss_limit: self._pause("Paper account daily loss limit reached.", stop_reason="safety_pause"); return False
        if risk == "daily_profit_lock_reached" and self.config.pause_on_daily_profit_lock: self._pause("Paper account daily profit lock reached.", stop_reason="safety_pause"); return False
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

    def _pause(self, reason: str, *, stop_reason: str | None = None) -> None:
        if not self._session: return
        reasons = tuple(dict.fromkeys((*self._session.pause_reasons, reason)))
        self._session = replace(self._session, status="paused", pause_reasons=reasons,
            stop_reason=stop_reason or self._session.stop_reason,
            human_readable_summary=f"Session paused: {reason}")
        self._record("paused", "WATCHLIST", reason); self._persist_session()

    def _blocked_result(self, status: str) -> ContinuousPaperCycleResult:
        s = self._session
        return ContinuousPaperCycleResult(
            cycle_number=s.cycle_count if s else 0, cycle_id=None, status=status,
            candidates_seen=0, trades_opened=0, trades_closed=0,
            report_generated=False, daily_report_status="disabled",
            validation_status=self._last_validation_status,
            health_status=self._last_health_status, paused=True,
            pause_reasons=s.pause_reasons if s else (), errors=(), completed_at=_now(),
            human_readable_summary="No cycle ran because the runtime is paused by a safety policy.",
        )

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            with self._lock:
                reason = self._limit_reason()
                if reason and self._session and self._session.status in {"running", "paused"}:
                    self._finish_session(reason, "completed")
                    self._record("stopped", "PASS", f"Session completed: {reason}.")
                    self._persist_session()
                    break
            if self._session and self._session.status != "paused": self.run_once()
            self._stop_event.wait(self.config.cycle_interval_seconds)

    def _limit_reason(self) -> str | None:
        if not self._session: return None
        if self.config.max_cycles is not None and self._session.cycle_count >= self.config.max_cycles:
            return "max_cycles_reached"
        if self._estimated_stop_at and datetime.now(timezone.utc) >= datetime.fromisoformat(self._estimated_stop_at):
            return "duration_limit_reached"
        return None

    def _remaining_seconds(self) -> float | None:
        if not self._estimated_stop_at: return None
        if self._session and self._session.status in {"completed", "stopped", "failed"}: return 0.0
        return round(max(0.0, (datetime.fromisoformat(self._estimated_stop_at) - datetime.now(timezone.utc)).total_seconds()), 3)

    def _finish_session(self, reason: str, final_status: str) -> None:
        if not self._session or self._session.status in {"completed", "stopped", "failed"}: return
        stopped = _now(); self._stopped_at = stopped; self._stop_event.set()
        started = datetime.fromisoformat(self._session.started_at)
        duration = round(max(0.0, (datetime.fromisoformat(stopped) - started).total_seconds()), 3)
        summary = ContinuousPaperSessionSummary(
            session_id=self._session.session_id, started_at=self._session.started_at,
            stopped_at=stopped, duration_seconds=duration,
            cycle_count=self._session.cycle_count,
            total_candidates_seen=self._session.total_candidates_seen,
            total_trades_opened=self._session.total_trades_opened,
            total_trades_closed=self._session.total_trades_closed,
            total_reports_generated=self._session.total_reports_generated,
            total_reports_skipped_existing=self._session.total_reports_skipped_existing,
            error_count=self._session.error_count, pause_reasons=self._session.pause_reasons,
            stop_reason=reason, final_status=final_status,
            human_readable_summary=f"Session {final_status} after {duration:.2f} seconds and {self._session.cycle_count} cycles ({reason}).",
        )
        self._session = replace(self._session, stopped_at=stopped, status=final_status,
            stop_reason=reason, final_session_summary=summary,
            human_readable_summary=summary.human_readable_summary)
        self.config = self.config.model_copy(update={"enabled": False})
        try:
            from core.validation_campaigns import get_global_validation_campaign_manager
            current = get_global_validation_campaign_manager().current()
            if current and current.status == "running":
                get_global_validation_campaign_manager().finish(current.campaign_id, status=final_status)
        except Exception:
            pass

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


def _estimated_stop(started_at: str, config: ContinuousPaperTradingConfig) -> str | None:
    durations = []
    if config.run_for_minutes is not None: durations.append(timedelta(minutes=config.run_for_minutes))
    if config.run_for_hours is not None: durations.append(timedelta(hours=config.run_for_hours))
    if not durations: return None
    return (datetime.fromisoformat(started_at) + min(durations)).isoformat()
