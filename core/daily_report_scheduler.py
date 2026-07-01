"""Local-only scheduler for previous-day paper report generation."""

from __future__ import annotations

import hashlib
import json
import threading
from collections import deque
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field, field_validator

from core.daily_report_engine import (
    DailyPaperTradingReport,
    DailyReportEngine,
    DailyReportError,
    DailyReportSummary,
)


class DailyReportSchedulerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    report_time: str = "06:00"
    timezone: str = "America/Chicago"
    generate_previous_day: bool = True
    overwrite_existing: bool = False
    include_weekends: bool = True
    auto_start: bool = False
    max_errors_before_pause: int = Field(default=5, ge=1)
    history_path: str = "reports/daily_scheduler_history.jsonl"
    max_history_in_memory: int = Field(default=500, ge=1, le=10_000)

    @field_validator("report_time")
    @classmethod
    def validate_report_time(cls, value: str) -> str:
        try:
            datetime.strptime(value, "%H:%M")
        except ValueError as exc:
            raise ValueError("report_time must use HH:MM 24-hour format") from exc
        return value

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            _zone(value, date.today())
        except ZoneInfoNotFoundError as exc:
            raise ValueError("timezone must be a valid IANA timezone") from exc
        return value


class SchedulerRunNowRequest(BaseModel):
    report_date: date | None = None
    overwrite: bool | None = None


@dataclass(frozen=True)
class SchedulerHistoryItem:
    run_id: str
    started_at: str
    completed_at: str
    report_date: str
    status: str
    report_status: str | None
    report_path: str
    error: str | None
    report_summary: DailyReportSummary | None = None


@dataclass(frozen=True)
class DailyReportSchedulerStatus:
    running: bool
    enabled: bool
    paused: bool
    report_time: str
    timezone: str
    last_run_at: str | None
    next_run_at: str | None
    last_report_date: str | None
    last_report_status: str | None
    run_count: int
    error_count: int
    last_error: str | None
    human_readable_summary: str


class DailyReportScheduler:
    """Schedule local report writes without external services or trading calls."""

    def __init__(self, report_engine: DailyReportEngine, config: DailyReportSchedulerConfig | None = None) -> None:
        self.report_engine = report_engine
        self.config = config or DailyReportSchedulerConfig()
        self._history: deque[SchedulerHistoryItem] = deque(maxlen=self.config.max_history_in_memory)
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._paused = False
        self._last_run_at: str | None = None
        self._last_report_date: str | None = None
        self._last_report_status: str | None = None
        self._run_count = 0
        self._error_count = 0
        self._last_error: str | None = None

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def update_config(self, config: DailyReportSchedulerConfig) -> None:
        with self._lock:
            if self.running:
                raise RuntimeError("stop the scheduler before changing configuration")
            self.config = config
            self._history = deque(self._history, maxlen=config.max_history_in_memory)

    def run_now(self, report_date: date | None = None, overwrite: bool | None = None) -> SchedulerHistoryItem:
        started = _now()
        target = report_date or self._default_report_date()
        effective_overwrite = self.config.overwrite_existing if overwrite is None else overwrite
        path = self.report_engine.reports_dir / f"{target.isoformat()}.json"
        existing = self.report_engine.get(target)
        report: DailyPaperTradingReport | None = None
        error: str | None = None
        if existing is not None and not effective_overwrite:
            status = "skipped_existing"
            report = existing
        else:
            try:
                report = self.report_engine.generate(target, overwrite=effective_overwrite)
                status = "completed"
            except Exception as exc:
                status = "failed"
                error = str(exc)
        completed = _now()
        item = SchedulerHistoryItem(
            run_id=hashlib.sha256(f"scheduler:{started}:{target}".encode()).hexdigest()[:24],
            started_at=started, completed_at=completed,
            report_date=target.isoformat(), status=status,
            report_status=report.status if report else None,
            report_path=str(path), error=error,
            report_summary=report.summary if report else None,
        )
        with self._lock:
            self._history.append(item); self._run_count += 1
            self._last_run_at = completed; self._last_report_date = target.isoformat()
            self._last_report_status = item.report_status or status
            if error:
                self._error_count += 1; self._last_error = error
                if self._error_count >= self.config.max_errors_before_pause:
                    self._paused = True
        self._persist(item)
        return item

    def start(self, config: DailyReportSchedulerConfig | None = None) -> DailyReportSchedulerStatus:
        with self._lock:
            if self.running:
                return self.status()
            if config is not None:
                self.update_config(config)
            self.config = self.config.model_copy(update={"enabled": True})
            self._paused = False; self._stop_event.clear()
            self._thread = threading.Thread(target=self._background_loop, name="structureiq-daily-report-scheduler", daemon=True)
            self._thread.start()
        return self.status()

    def stop(self) -> DailyReportSchedulerStatus:
        with self._lock:
            thread = self._thread; self._stop_event.set()
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=2.0)
        with self._lock:
            if self._thread is thread and (thread is None or not thread.is_alive()): self._thread = None
            self.config = self.config.model_copy(update={"enabled": False})
        return self.status()

    def status(self) -> DailyReportSchedulerStatus:
        with self._lock:
            running = self.running
            return DailyReportSchedulerStatus(
                running=running, enabled=self.config.enabled, paused=self._paused,
                report_time=self.config.report_time, timezone=self.config.timezone,
                last_run_at=self._last_run_at,
                next_run_at=self.next_run_time().isoformat() if running and not self._paused else None,
                last_report_date=self._last_report_date,
                last_report_status=self._last_report_status,
                run_count=self._run_count, error_count=self._error_count,
                last_error=self._last_error,
                human_readable_summary=f"Daily report scheduler is {'paused' if self._paused else 'running' if running else 'stopped'}.",
            )

    def history(self, limit: int | None = None) -> tuple[SchedulerHistoryItem, ...]:
        values = tuple(self._history)
        return values[-limit:] if limit is not None else values

    def next_run_time(self, now: datetime | None = None) -> datetime:
        reference = (now.date() if now else datetime.now(timezone.utc).date())
        zone = _zone(self.config.timezone, reference)
        current = now.astimezone(zone) if now else datetime.now(zone)
        hour, minute = map(int, self.config.report_time.split(":"))
        target = datetime.combine(current.date(), time(hour, minute), tzinfo=zone)
        if target <= current:
            target += timedelta(days=1)
        return target

    def _default_report_date(self) -> date:
        zone = _zone(self.config.timezone, datetime.now(timezone.utc).date())
        target = datetime.now(zone).date()
        if self.config.generate_previous_day:
            target -= timedelta(days=1)
        if not self.config.include_weekends:
            while target.weekday() >= 5:
                target -= timedelta(days=1)
        return target

    def _background_loop(self) -> None:
        while not self._stop_event.is_set() and not self._paused:
            zone = _zone(self.config.timezone, datetime.now(timezone.utc).date())
            wait_seconds = max(0.0, (self.next_run_time() - datetime.now(zone)).total_seconds())
            if self._stop_event.wait(wait_seconds):
                break
            self.run_now()

    def _persist(self, item: SchedulerHistoryItem) -> None:
        path = Path(self.config.history_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(jsonable_encoder(item), separators=(",", ":")) + "\n")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _zone(name: str, reference: date):
    """Resolve IANA zones, with a no-dependency U.S. Central fallback on Windows."""
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        if name != "America/Chicago":
            raise
        # U.S. DST: second Sunday in March through first Sunday in November.
        march_first = date(reference.year, 3, 1)
        second_sunday = 8 + ((6 - march_first.weekday()) % 7)
        november_first = date(reference.year, 11, 1)
        first_sunday = 1 + ((6 - november_first.weekday()) % 7)
        daylight = date(reference.year, 3, second_sunday) <= reference < date(reference.year, 11, first_sunday)
        return timezone(timedelta(hours=-5 if daylight else -6), name)


_GLOBAL_SCHEDULER: DailyReportScheduler | None = None
_GLOBAL_LOCK = threading.RLock()


def get_global_daily_report_scheduler(report_engine: DailyReportEngine) -> DailyReportScheduler:
    global _GLOBAL_SCHEDULER
    with _GLOBAL_LOCK:
        if _GLOBAL_SCHEDULER is None or _GLOBAL_SCHEDULER.report_engine is not report_engine:
            _GLOBAL_SCHEDULER = DailyReportScheduler(report_engine)
        return _GLOBAL_SCHEDULER


def current_daily_report_scheduler() -> DailyReportScheduler | None:
    with _GLOBAL_LOCK: return _GLOBAL_SCHEDULER


def reset_global_daily_report_scheduler() -> None:
    global _GLOBAL_SCHEDULER
    with _GLOBAL_LOCK:
        if _GLOBAL_SCHEDULER is not None: _GLOBAL_SCHEDULER.stop()
        _GLOBAL_SCHEDULER = None
