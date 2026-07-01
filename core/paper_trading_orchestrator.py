"""Controlled end-to-end orchestration for advisory paper trading only."""

from __future__ import annotations

import hashlib
import json
import threading
from collections import deque
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field

from core.backtesting import parse_price_level
from core.daily_report_engine import DailyReportEngine, DailyReportError
from core.live_market_monitor import LiveMarketMonitor, MonitorCycleResult, MonitorEvent
from core.paper_brokerage import PaperBrokerageEngine
from core.paper_trade_journal import PaperTradeJournal
from core.trade_lifecycle_manager import (
    ApproveCandidateRequest,
    LifecycleError,
    OrderType,
    TradeLifecycleManager,
)


class PaperTradingOrchestratorConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    auto_approve_candidates: bool = False
    require_manual_approval: bool = True
    allow_market_orders: bool = False
    default_order_type: OrderType = OrderType.LIMIT_RETEST
    allow_missing_setup_quality: bool = False
    max_candidates_per_cycle: int = Field(default=3, ge=1)
    max_new_trades_per_cycle: int = Field(default=1, ge=1)
    poll_seconds: float = Field(default=60.0, gt=0)
    generate_daily_report_after_cycle: bool = True
    report_overwrite: bool = True
    stop_on_daily_loss_limit: bool = True
    stop_on_daily_profit_lock: bool = True
    max_errors_before_pause: int = Field(default=5, ge=1)
    write_cycles: bool = False
    cycles_path: str = "reports/paper_trading_cycles.jsonl"
    max_cycles_in_memory: int = Field(default=100, ge=1, le=10_000)


@dataclass(frozen=True)
class OrchestratorAction:
    timestamp: str
    cycle_id: str
    action: str
    symbol: str | None
    source_event_id: str | None
    message: str


@dataclass(frozen=True)
class PaperTradingCycleResult:
    cycle_id: str
    started_at: str
    completed_at: str
    monitor_result: MonitorCycleResult
    candidates_seen: int
    candidates_approved: int
    orders_created: int
    orders_filled: int
    trades_opened: int
    trades_closed: int
    journal_updates: int
    daily_report_generated: bool
    blocked_reasons: tuple[str, ...]
    errors: tuple[str, ...]
    status: str
    human_readable_summary: str


@dataclass(frozen=True)
class PaperTradingOrchestratorStatus:
    running: bool
    enabled: bool
    cycle_count: int
    last_cycle_id: str | None
    last_cycle_started_at: str | None
    last_cycle_completed_at: str | None
    last_error: str | None
    error_count: int
    paused: bool
    total_candidates_seen: int
    total_candidates_approved: int
    total_orders_created: int
    total_trades_opened: int
    total_trades_closed: int
    total_reports_generated: int
    config: PaperTradingOrchestratorConfig
    paper_only: bool
    human_readable_summary: str


class PaperTradingOrchestrator:
    """Run monitor → lifecycle → brokerage → journal → report as a safe paper cycle."""

    def __init__(
        self,
        monitor: LiveMarketMonitor,
        lifecycle: TradeLifecycleManager,
        broker: PaperBrokerageEngine,
        journal: PaperTradeJournal,
        daily_reports: DailyReportEngine,
        config: PaperTradingOrchestratorConfig | None = None,
    ) -> None:
        self.monitor = monitor
        self.lifecycle = lifecycle
        self.broker = broker
        self.journal = journal
        self.daily_reports = daily_reports
        self.config = config or PaperTradingOrchestratorConfig()
        self._cycles: deque[PaperTradingCycleResult] = deque(maxlen=self.config.max_cycles_in_memory)
        self._actions: deque[OrchestratorAction] = deque(maxlen=500)
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._cycle_count = 0
        self._last_cycle_id: str | None = None
        self._last_started: str | None = None
        self._last_completed: str | None = None
        self._last_error: str | None = None
        self._error_count = 0
        self._paused = False
        self._total_candidates_seen = 0
        self._total_candidates_approved = 0
        self._total_orders_created = 0
        self._total_trades_opened = 0
        self._total_trades_closed = 0
        self._total_reports_generated = 0

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def update_config(self, config: PaperTradingOrchestratorConfig) -> None:
        with self._lock:
            if self.running:
                raise RuntimeError("stop the orchestrator before changing configuration")
            self.config = config
            self._cycles = deque(self._cycles, maxlen=config.max_cycles_in_memory)

    def run_cycle(self, config: PaperTradingOrchestratorConfig | None = None) -> PaperTradingCycleResult:
        if config is not None:
            self.update_config(config)
        started = _now()
        cycle_id = hashlib.sha256(f"paper-cycle:{started}:{self._cycle_count}".encode()).hexdigest()[:24]
        errors: list[str] = []
        blocked: list[str] = []
        approved = orders = 0
        before_open = len(self.broker.open_positions())
        before_closed = len(self.broker.closed_trades())
        before_journal_entries = len(self.journal.entries())
        before_journal_events = sum(len(item.lifecycle_events) for item in self.journal.entries())

        try:
            monitor_result = self.monitor.run_once()
        except Exception as exc:
            message = f"monitor cycle failed: {exc}"
            errors.append(message)
            monitor_result = _empty_monitor_result(message)
        errors.extend(monitor_result.errors)
        candidates = tuple(monitor_result.events[: self.config.max_candidates_per_cycle])
        if len(monitor_result.events) > len(candidates):
            blocked.append("Candidate limit reached; remaining candidates were observed only.")

        account = self.broker.account()
        approval_enabled = self.config.auto_approve_candidates and not self.config.require_manual_approval
        if not approval_enabled and candidates:
            blocked.append("Automatic approval is disabled; candidates require manual lifecycle approval.")
        elif approval_enabled:
            for candidate in candidates:
                if approved >= self.config.max_new_trades_per_cycle:
                    blocked.append("Maximum new trades per cycle reached.")
                    break
                reason = self._candidate_blocker(candidate, account)
                if reason:
                    blocked.append(f"{candidate.symbol}: {reason}")
                    self._record_action(cycle_id, "candidate_blocked", candidate, reason)
                    continue
                try:
                    self.lifecycle.approve_candidate(
                        ApproveCandidateRequest(
                            event_id=candidate.event_id,
                            order_type=self.config.default_order_type,
                        )
                    )
                    approved += 1; orders += 1
                    self._record_action(cycle_id, "candidate_approved", candidate, "Candidate passed orchestrator safety gates.")
                except LifecycleError as exc:
                    errors.append(f"{candidate.symbol}: {exc}")

        try:
            lifecycle_result = self.lifecycle.run_once()
            errors.extend(lifecycle_result.errors)
        except Exception as exc:
            errors.append(f"lifecycle cycle failed: {exc}")
            lifecycle_result = None

        after_open = len(self.broker.open_positions())
        after_closed = len(self.broker.closed_trades())
        trades_opened = max(0, after_open + after_closed - before_open - before_closed)
        trades_closed = max(0, after_closed - before_closed)
        after_journal_events = sum(len(item.lifecycle_events) for item in self.journal.entries())
        journal_updates = max(0, len(self.journal.entries()) - before_journal_entries + after_journal_events - before_journal_events)
        report_generated = False
        if self.config.generate_daily_report_after_cycle:
            try:
                self.daily_reports.generate(date.today(), overwrite=self.config.report_overwrite)
                report_generated = True
            except DailyReportError as exc:
                errors.append(f"daily report: {exc}")
            except Exception as exc:
                errors.append(f"daily report failed: {exc}")

        completed = _now()
        status = "completed_with_errors" if errors else "completed"
        result = PaperTradingCycleResult(
            cycle_id=cycle_id, started_at=started, completed_at=completed,
            monitor_result=monitor_result, candidates_seen=len(candidates),
            candidates_approved=approved, orders_created=orders,
            orders_filled=getattr(lifecycle_result, "orders_filled", 0),
            trades_opened=trades_opened, trades_closed=trades_closed,
            journal_updates=journal_updates, daily_report_generated=report_generated,
            blocked_reasons=tuple(dict.fromkeys(blocked)), errors=tuple(errors),
            status=status,
            human_readable_summary=f"Paper-trading cycle completed with {len(candidates)} candidates and {trades_opened} new trades.",
        )
        with self._lock:
            self._cycles.append(result); self._cycle_count += 1
            self._last_cycle_id = cycle_id; self._last_started = started; self._last_completed = completed
            self._total_candidates_seen += len(candidates); self._total_candidates_approved += approved
            self._total_orders_created += orders; self._total_trades_opened += trades_opened
            self._total_trades_closed += trades_closed; self._total_reports_generated += int(report_generated)
            self._error_count += len(errors)
            if errors: self._last_error = errors[-1]
            if self._error_count >= self.config.max_errors_before_pause: self._paused = True
        self._persist(result)
        return result

    def start(self, config: PaperTradingOrchestratorConfig | None = None) -> PaperTradingOrchestratorStatus:
        with self._lock:
            if self.running:
                return self.status()
            if config is not None:
                self.update_config(config)
            self.config = self.config.model_copy(update={"enabled": True})
            self._paused = False; self._stop_event.clear()
            self._thread = threading.Thread(target=self._background_loop, name="structureiq-paper-orchestrator", daemon=True)
            self._thread.start()
        return self.status()

    def stop(self) -> PaperTradingOrchestratorStatus:
        with self._lock:
            thread = self._thread; self._stop_event.set()
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=max(1.0, min(self.config.poll_seconds + 0.5, 5.0)))
        with self._lock:
            if self._thread is thread and (thread is None or not thread.is_alive()): self._thread = None
            self.config = self.config.model_copy(update={"enabled": False})
        return self.status()

    def status(self) -> PaperTradingOrchestratorStatus:
        with self._lock:
            return PaperTradingOrchestratorStatus(
                running=self.running, enabled=self.config.enabled,
                cycle_count=self._cycle_count, last_cycle_id=self._last_cycle_id,
                last_cycle_started_at=self._last_started, last_cycle_completed_at=self._last_completed,
                last_error=self._last_error, error_count=self._error_count, paused=self._paused,
                total_candidates_seen=self._total_candidates_seen,
                total_candidates_approved=self._total_candidates_approved,
                total_orders_created=self._total_orders_created,
                total_trades_opened=self._total_trades_opened,
                total_trades_closed=self._total_trades_closed,
                total_reports_generated=self._total_reports_generated,
                config=self.config, paper_only=True,
                human_readable_summary=f"Paper Trading Orchestrator is {'paused' if self._paused else 'running' if self.running else 'stopped'} and never submits live orders.",
            )

    def cycles(self, limit: int | None = None) -> tuple[PaperTradingCycleResult, ...]:
        values = tuple(self._cycles)
        return values[-limit:] if limit is not None else values

    def recent_actions(self, limit: int | None = None) -> tuple[OrchestratorAction, ...]:
        values = tuple(self._actions)
        return values[-limit:] if limit is not None else values

    def _candidate_blocker(self, candidate: MonitorEvent, account: Any) -> str | None:
        if candidate.paper_trade_created: return "candidate already created a paper trade"
        if candidate.action not in {"buy", "sell"}: return "candidate action is not buy or sell"
        quality = candidate.setup_quality or {}
        grade = str(quality.get("grade", ""))
        if not grade and not self.config.allow_missing_setup_quality: return "setup quality is missing"
        if grade in {"D", "F"}: return f"setup quality grade {grade} is not eligible"
        blockers = (candidate.execution_intelligence or {}).get("execution_blockers", ())
        if blockers: return "execution intelligence contains blockers"
        try:
            entry = parse_price_level(candidate.entry_zone, midpoint=True)
            stop = parse_price_level(candidate.stop_loss); target = parse_price_level(candidate.target)
            if entry is None or stop is None or target is None: return "entry, stop, or target is unavailable"
            if candidate.action == "buy" and not stop < entry < target: return "invalid bullish risk geometry"
            if candidate.action == "sell" and not target < entry < stop: return "invalid bearish risk geometry"
        except (TypeError, ValueError):
            return "risk geometry could not be parsed"
        if account.risk_status != "available": return f"paper account risk status is {account.risk_status}"
        if len(self.broker.open_positions()) >= self.broker.config.max_open_positions: return "maximum paper positions reached"
        if self.config.default_order_type is OrderType.MARKET and not self.config.allow_market_orders: return "market orders are disabled"
        if not self.broker.config.allow_duplicate_symbol_positions and any(item.symbol == candidate.symbol for item in self.broker.open_positions()): return "duplicate symbol position is disabled"
        if not self.broker.config.allow_duplicate_setup_positions and any(item.symbol == candidate.symbol and item.timeframe == candidate.timeframe and item.setup == candidate.setup for item in self.broker.open_positions()): return "duplicate setup position is disabled"
        return None

    def _background_loop(self) -> None:
        while not self._stop_event.is_set():
            if self._paused: break
            self.run_cycle()
            self._stop_event.wait(self.config.poll_seconds)

    def _record_action(self, cycle_id, action, candidate, message) -> None:
        self._actions.append(OrchestratorAction(_now(), cycle_id, action, candidate.symbol, candidate.event_id, message))

    def _persist(self, result: PaperTradingCycleResult) -> None:
        if not self.config.write_cycles: return
        path = Path(self.config.cycles_path); path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(jsonable_encoder(result), separators=(",", ":")) + "\n")


def _empty_monitor_result(error: str) -> MonitorCycleResult:
    now = _now()
    return MonitorCycleResult(0, 0, 0, (error,), (), now, "Monitor cycle failed safely.")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


_GLOBAL_ORCHESTRATOR: PaperTradingOrchestrator | None = None
_GLOBAL_LOCK = threading.RLock()


def get_global_paper_trading_orchestrator(monitor, lifecycle, broker, journal, daily_reports) -> PaperTradingOrchestrator:
    global _GLOBAL_ORCHESTRATOR
    with _GLOBAL_LOCK:
        if _GLOBAL_ORCHESTRATOR is None or _GLOBAL_ORCHESTRATOR.monitor is not monitor or _GLOBAL_ORCHESTRATOR.lifecycle is not lifecycle or _GLOBAL_ORCHESTRATOR.broker is not broker or _GLOBAL_ORCHESTRATOR.journal is not journal or _GLOBAL_ORCHESTRATOR.daily_reports is not daily_reports:
            _GLOBAL_ORCHESTRATOR = PaperTradingOrchestrator(monitor, lifecycle, broker, journal, daily_reports)
        return _GLOBAL_ORCHESTRATOR


def current_paper_trading_orchestrator() -> PaperTradingOrchestrator | None:
    with _GLOBAL_LOCK: return _GLOBAL_ORCHESTRATOR


def reset_global_paper_trading_orchestrator() -> None:
    global _GLOBAL_ORCHESTRATOR
    with _GLOBAL_LOCK:
        if _GLOBAL_ORCHESTRATOR is not None: _GLOBAL_ORCHESTRATOR.stop()
        _GLOBAL_ORCHESTRATOR = None
