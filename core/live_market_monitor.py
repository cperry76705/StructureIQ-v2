"""Explicitly controlled, advisory-only continuous market monitoring service."""

from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import replace
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field, field_validator

from core.analysis_engine import AnalysisEngine
from core.candidate_diagnostics import CandidateDiagnosticsEngine, get_global_candidate_diagnostics
from core.market_data import MarketDataError, MarketDataProvider
from models.schemas import AnalysisRequest, AnalysisResponse


class MonitorConfig(BaseModel):
    """Safe defaults for a monitor that never starts itself."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    symbols: list[str] = Field(
        default_factory=lambda: ["BTC-USD", "ETH-USD", "EUR-USD", "GBP-USD"],
        min_length=1,
    )
    timeframes: list[str] = Field(default_factory=lambda: ["5m"], min_length=1)
    higher_timeframe: str = "1h"
    lookback: int = Field(default=300, ge=50, le=5000)
    poll_seconds: float = Field(default=60.0, gt=0)
    write_events: bool = True
    events_path: str = "research/live_monitor_events.jsonl"
    max_events_in_memory: int = Field(default=500, ge=1, le=10_000)

    @field_validator("symbols")
    @classmethod
    def normalize_symbols(cls, values: list[str]) -> list[str]:
        normalized = [item.strip().upper() for item in values]
        if any(not item for item in normalized):
            raise ValueError("monitor symbols cannot be blank")
        return normalized


@dataclass(frozen=True)
class MonitorEvent:
    event_id: str
    timestamp: str
    symbol: str
    timeframe: str
    higher_timeframe: str
    candle_timestamp: int
    action: str
    setup: str
    strategy: str
    confidence: float
    setup_quality: dict[str, Any] | None
    score_summary: dict[str, Any] | None
    execution_intelligence: dict[str, Any] | None
    confidence_calibration: dict[str, Any] | None
    symbol_profile: dict[str, Any] | None
    adaptive_strategy_router: dict[str, Any] | None
    strategy_rating: dict[str, Any] | None
    setup_rating: dict[str, Any] | None
    entry_zone: str
    stop_loss: str
    target: str
    reasons: tuple[str, ...]
    status: str = "candidate"
    paper_trade_created: bool = False


@dataclass(frozen=True)
class MonitorCycleResult:
    analyzed: int
    candidates_created: int
    duplicates_skipped: int
    errors: tuple[str, ...]
    events: tuple[MonitorEvent, ...]
    completed_at: str
    human_readable_summary: str


@dataclass(frozen=True)
class MonitorStatus:
    running: bool
    config: MonitorConfig
    last_cycle_time: str | None
    last_signal_time: str | None
    last_error: str | None
    cycle_count: int
    signal_count: int
    recent_signal_count: int
    error_count: int
    ready_for_paper_trading: bool
    human_readable_summary: str


class LiveMarketMonitor:
    """Poll configured markets and emit deduplicated candidate observations."""

    def __init__(
        self,
        provider: MarketDataProvider,
        config: MonitorConfig | None = None,
        *,
        analysis_engine_factory: Callable[[MarketDataProvider], Any] | None = None,
        candidate_diagnostics: CandidateDiagnosticsEngine | None = None,
    ) -> None:
        self.provider = provider
        self.config = config or MonitorConfig()
        self._analysis_engine_factory = analysis_engine_factory or AnalysisEngine
        self.candidate_diagnostics = candidate_diagnostics or get_global_candidate_diagnostics()
        self._events: deque[MonitorEvent] = deque(maxlen=self.config.max_events_in_memory)
        self._emitted_keys: set[tuple[str, str, int, str, str]] = set()
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_cycle_time: str | None = None
        self._last_signal_time: str | None = None
        self._last_error: str | None = None
        self._cycle_count = 0
        self._signal_count = 0
        self._error_count = 0

    def update_config(self, config: MonitorConfig) -> None:
        """Replace configuration while stopped, preserving deduplication history."""
        with self._lock:
            if self.running:
                raise RuntimeError("stop the monitor before changing its configuration")
            self.config = config
            self._events = deque(self._events, maxlen=config.max_events_in_memory)

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def run_once(self, config: MonitorConfig | None = None) -> MonitorCycleResult:
        if config is not None:
            self.update_config(config)
        engine = self._analysis_engine_factory(self.provider)
        created: list[MonitorEvent] = []
        errors: list[str] = []
        analyzed = duplicates = 0
        for symbol in self.config.symbols:
            for timeframe in self.config.timeframes:
                try:
                    candles = self.provider.get_candles(
                        symbol, timeframe, self.config.lookback
                    )
                    if not candles:
                        raise MarketDataError("provider returned no candles")
                    candle_timestamp = int(candles[-1].timestamp)
                    analysis = engine.analyze(
                        AnalysisRequest(
                            symbol=symbol,
                            timeframe=timeframe,
                            higher_timeframe=self.config.higher_timeframe,
                            lookback=self.config.lookback,
                        )
                    )
                    analyzed += 1
                    if not _is_actionable(analysis):
                        self._record_diagnostic(analysis, timeframe, False)
                        continue
                    key = (
                        symbol,
                        timeframe,
                        candle_timestamp,
                        analysis.action,
                        analysis.setup,
                    )
                    with self._lock:
                        if key in self._emitted_keys:
                            duplicates += 1
                            self._record_diagnostic(analysis, timeframe, False, duplicate=True)
                            continue
                        event = _build_event(
                            analysis, timeframe, self.config.higher_timeframe,
                            candle_timestamp, key,
                        )
                        self._emitted_keys.add(key)
                        self._events.append(event)
                        self._signal_count += 1
                        self._last_signal_time = event.timestamp
                    self._persist(event)
                    self._record_diagnostic(analysis, timeframe, True)
                    created.append(event)
                except Exception as exc:
                    message = f"{symbol} {timeframe}: {exc}"
                    errors.append(message)
                    with self._lock:
                        self._last_error = message
                        self._error_count += 1
                    try:
                        self.candidate_diagnostics.record_failure(
                            symbol=symbol, timeframe=timeframe,
                            higher_timeframe=self.config.higher_timeframe, error=str(exc),
                        )
                    except Exception:
                        pass
        completed = _now()
        with self._lock:
            self._last_cycle_time = completed
            self._cycle_count += 1
        return MonitorCycleResult(
            analyzed=analyzed,
            candidates_created=len(created),
            duplicates_skipped=duplicates,
            errors=tuple(errors),
            events=tuple(created),
            completed_at=completed,
            human_readable_summary=(
                f"Monitor analyzed {analyzed} markets and emitted {len(created)} new candidate events; "
                f"{duplicates} duplicates and {len(errors)} errors were recorded."
            ),
        )

    def start(self, config: MonitorConfig | None = None) -> MonitorStatus:
        with self._lock:
            if self.running:
                return self.status()
            if config is not None:
                self.update_config(config)
            self.config = self.config.model_copy(update={"enabled": True})
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._background_loop,
                name="structureiq-live-monitor",
                daemon=True,
            )
            self._thread.start()
        return self.status()

    def stop(self) -> MonitorStatus:
        with self._lock:
            thread = self._thread
            self._stop_event.set()
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=max(1.0, min(self.config.poll_seconds + 0.5, 5.0)))
        with self._lock:
            if self._thread is thread and (thread is None or not thread.is_alive()):
                self._thread = None
            self.config = self.config.model_copy(update={"enabled": False})
        return self.status()

    def status(self) -> MonitorStatus:
        with self._lock:
            running = self.running
            return MonitorStatus(
                running=running,
                config=self.config,
                last_cycle_time=self._last_cycle_time,
                last_signal_time=self._last_signal_time,
                last_error=self._last_error,
                cycle_count=self._cycle_count,
                signal_count=self._signal_count,
                recent_signal_count=len(self._events),
                error_count=self._error_count,
                ready_for_paper_trading=False,
                human_readable_summary=(
                    f"Live Market Monitor is {'running' if running else 'stopped'}; "
                    "candidate events are advisory and paper trading is not enabled."
                ),
            )

    def events(self, limit: int | None = None) -> tuple[MonitorEvent, ...]:
        with self._lock:
            values = tuple(self._events)
        return values[-limit:] if limit is not None else values

    def find_event(self, event_id: str) -> MonitorEvent | None:
        with self._lock:
            return next((item for item in self._events if item.event_id == event_id), None)

    def mark_paper_trade_created(self, event_id: str) -> MonitorEvent:
        """Mark a candidate only after the paper brokerage confirms an open."""
        with self._lock:
            values = list(self._events)
            for index, event in enumerate(values):
                if event.event_id == event_id:
                    updated = replace(event, paper_trade_created=True)
                    values[index] = updated
                    self._events = deque(values, maxlen=self.config.max_events_in_memory)
                    return updated
        raise KeyError("monitor event was not found")

    def _background_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.run_once()
            except Exception as exc:  # defensive: one cycle must not kill the service
                with self._lock:
                    self._last_error = f"monitor cycle: {exc}"
                    self._error_count += 1
            self._stop_event.wait(self.config.poll_seconds)

    def _persist(self, event: MonitorEvent) -> None:
        if not self.config.write_events:
            return
        path = Path(self.config.events_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(jsonable_encoder(event), separators=(",", ":")))
            stream.write("\n")

    def _record_diagnostic(self, analysis, timeframe: str, created: bool, *, duplicate: bool = False) -> None:
        """Keep diagnostics strictly observational; failures cannot affect monitoring."""
        try:
            self.candidate_diagnostics.record_analysis(
                analysis, timeframe=timeframe,
                higher_timeframe=self.config.higher_timeframe,
                candidate_created=created, duplicate=duplicate,
            )
        except Exception:
            pass


def _is_actionable(analysis: AnalysisResponse) -> bool:
    plan_status = _value(getattr(analysis.trader_analysis.trade_plan, "status", ""))
    setup_status = _value(getattr(getattr(analysis, "setup_plan", None), "setup_status", ""))
    return (
        analysis.action in {"buy", "sell"}
        and plan_status == "actionable"
        and setup_status == "confirmed"
    )


def _build_event(analysis, timeframe, higher_timeframe, candle_timestamp, key) -> MonitorEvent:
    timestamp = _now()
    event_id = hashlib.sha256("|".join(map(str, key)).encode("utf-8")).hexdigest()[:24]
    return MonitorEvent(
        event_id=event_id,
        timestamp=timestamp,
        symbol=analysis.symbol,
        timeframe=timeframe,
        higher_timeframe=higher_timeframe,
        candle_timestamp=candle_timestamp,
        action=analysis.action,
        setup=analysis.setup,
        strategy=str(getattr(analysis.strategy.preferred_strategy, "value", analysis.strategy.preferred_strategy)),
        confidence=analysis.confidence,
        setup_quality=_safe_payload(getattr(analysis, "setup_quality", None)),
        score_summary=_safe_payload(getattr(analysis, "score_summary", None)),
        execution_intelligence=_safe_payload(getattr(analysis, "execution_intelligence", None)),
        confidence_calibration=_safe_payload(getattr(analysis, "confidence_calibration", None)),
        symbol_profile=_safe_payload(getattr(analysis, "symbol_profile", None)),
        adaptive_strategy_router=_safe_payload(getattr(analysis, "adaptive_strategy_router", None)),
        strategy_rating=_safe_payload(getattr(analysis, "current_strategy_rating", None)),
        setup_rating=_safe_payload(getattr(analysis, "current_setup_rating", None)),
        entry_zone=analysis.entry_zone,
        stop_loss=analysis.stop_loss,
        target=analysis.target,
        reasons=tuple(analysis.reasons),
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _value(value: Any) -> str:
    return str(getattr(value, "value", value))


def _safe_payload(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if hasattr(value, "__dict__") and not isinstance(value, dict):
        value = vars(value)
    encoded = jsonable_encoder(value)
    return encoded if isinstance(encoded, dict) else {"value": encoded}


_GLOBAL_MONITOR: LiveMarketMonitor | None = None
_GLOBAL_LOCK = threading.RLock()


def get_global_live_market_monitor(provider: MarketDataProvider) -> LiveMarketMonitor:
    """Return the process monitor, replacing a stopped instance for a new provider."""
    global _GLOBAL_MONITOR
    with _GLOBAL_LOCK:
        if _GLOBAL_MONITOR is None:
            _GLOBAL_MONITOR = LiveMarketMonitor(provider)
        elif _GLOBAL_MONITOR.provider is not provider and not _GLOBAL_MONITOR.running:
            _GLOBAL_MONITOR = LiveMarketMonitor(provider)
        return _GLOBAL_MONITOR


def reset_global_live_market_monitor() -> None:
    """Stop and clear process monitor state; intended for tests and shutdown."""
    global _GLOBAL_MONITOR
    with _GLOBAL_LOCK:
        if _GLOBAL_MONITOR is not None:
            _GLOBAL_MONITOR.stop()
        _GLOBAL_MONITOR = None


def current_live_market_monitor_status() -> MonitorStatus | None:
    """Read current monitor state without creating or starting a monitor."""
    with _GLOBAL_LOCK:
        return _GLOBAL_MONITOR.status() if _GLOBAL_MONITOR is not None else None
