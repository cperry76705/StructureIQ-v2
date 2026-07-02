"""Local system health and observability snapshots for StructureIQ."""

from __future__ import annotations

import importlib
import json
import os
import platform
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi.encoders import jsonable_encoder

from app.config import APP_VERSION


HealthStatus = Literal["PASS", "WATCHLIST", "FAIL", "UNAVAILABLE"]
_PROCESS_STARTED = time.monotonic()


@dataclass(frozen=True)
class HealthDimension:
    name: str
    status: HealthStatus
    score: float
    details: dict[str, Any]
    warnings: tuple[str, ...]
    blocking_issues: tuple[str, ...]
    human_readable_summary: str


@dataclass(frozen=True)
class SystemHealthReport:
    status: Literal["PASS", "WATCHLIST", "FAIL"]
    score: float
    app_version: str
    uptime_seconds: float
    checked_at: str
    dimensions: tuple[HealthDimension, ...]
    warnings: tuple[str, ...]
    blocking_issues: tuple[str, ...]
    paper_trading_operational_readiness: Literal["READY", "NOT_READY", "WATCHLIST"]
    recommended_actions: tuple[str, ...]
    human_readable_summary: str


@dataclass(frozen=True)
class SystemReadiness:
    paper_trading_operational_readiness: str
    overall_health_status: str
    health_score: float
    required_components_available: bool
    blocking_issues: tuple[str, ...]
    warnings: tuple[str, ...]
    checked_at: str
    human_readable_summary: str


@dataclass(frozen=True)
class SystemErrors:
    total_errors: int
    errors: tuple[dict[str, Any], ...]
    checked_at: str
    human_readable_summary: str


class SystemHealthEngine:
    """Inspect runtime and local storage without invoking operational workflows."""

    REQUIRED_PAPER_COMPONENTS = (
        "live_monitor", "paper_brokerage", "trade_lifecycle_manager",
        "paper_trade_journal", "daily_report_engine",
        "daily_report_scheduler", "paper_trading_orchestrator",
        "continuous_paper_trading",
    )
    REQUIRED_DIRS = ("logs", "research", "reports", "reports/daily")
    OPTIONAL_FILES = (
        "research/symbol_profiles.json",
        "research/live_monitor_events.jsonl",
        "research/paper_account_state.json",
        "research/paper_trade_journal.jsonl",
        "reports/daily_scheduler_history.jsonl",
        "reports/paper_trading_cycles.jsonl",
    )

    def __init__(
        self,
        *,
        project_root: str | Path = ".",
        market_data_provider: Any | None = None,
        live_monitor: Any | None = None,
        paper_brokerage: Any | None = None,
        trade_lifecycle_manager: Any | None = None,
        paper_trade_journal: Any | None = None,
        daily_report_engine: Any | None = None,
        daily_report_scheduler: Any | None = None,
        paper_trading_orchestrator: Any | None = None,
        log_path: str | Path | None = None,
    ) -> None:
        self.root = Path(project_root).resolve()
        self.provider = market_data_provider
        self.monitor = live_monitor
        self.broker = paper_brokerage
        self.lifecycle = trade_lifecycle_manager
        self.journal = paper_trade_journal
        self.reports = daily_report_engine
        self.scheduler = daily_report_scheduler
        self.orchestrator = paper_trading_orchestrator
        self.log_path = Path(log_path) if log_path else self.root / "logs/system_health.jsonl"

    def check(self, *, write_log: bool = True) -> SystemHealthReport:
        dimensions = (
            self._application(), self._configuration(), self._provider(),
            self._runtime_component("live_monitor", self.monitor),
            self._paper_brokerage(),
            self._runtime_component("trade_lifecycle_manager", self.lifecycle),
            self._journal(), self._runtime_component("daily_report_engine", self.reports),
            self._runtime_component("daily_report_scheduler", self.scheduler),
            self._runtime_component("paper_trading_orchestrator", self.orchestrator),
            self._continuous_paper_dimension(),
            self._module_dimension("dashboard", "core.research_dashboard"),
            self.storage(), self._folder_dimension("logs", "logs"),
            self._research_files(), self._folder_dimension("reports", "reports"),
            HealthDimension("tests_status_placeholder", "UNAVAILABLE", 0.0, {"reason": "Runtime test execution is intentionally not performed."}, (), (), "Test status is unavailable at runtime by design."),
        )
        warnings = tuple(dict.fromkeys(w for item in dimensions for w in item.warnings))
        blockers = tuple(dict.fromkeys(b for item in dimensions for b in item.blocking_issues))
        scored = [item.score for item in dimensions if item.status != "UNAVAILABLE"]
        score = round(sum(scored) / len(scored), 2) if scored else 0.0
        status = "FAIL" if blockers or any(item.status == "FAIL" for item in dimensions) else "WATCHLIST" if warnings or any(item.status == "WATCHLIST" for item in dimensions) else "PASS"
        readiness = self._paper_readiness(dimensions, warnings)
        actions = _recommended_actions(blockers, warnings)
        report = SystemHealthReport(
            status=status, score=score, app_version=APP_VERSION,
            uptime_seconds=round(time.monotonic() - _PROCESS_STARTED, 3),
            checked_at=_now(), dimensions=dimensions, warnings=warnings,
            blocking_issues=blockers,
            paper_trading_operational_readiness=readiness,
            recommended_actions=actions,
            human_readable_summary=f"StructureIQ health is {status} with {len(blockers)} blocking issues.",
        )
        _set_latest(report)
        if write_log:
            self._log(report)
        return report

    def readiness(self) -> SystemReadiness:
        report = self.check()
        unavailable = any(
            item.name in self.REQUIRED_PAPER_COMPONENTS and item.status in {"UNAVAILABLE", "FAIL"}
            for item in report.dimensions
        )
        return SystemReadiness(
            paper_trading_operational_readiness=report.paper_trading_operational_readiness,
            overall_health_status=report.status, health_score=report.score,
            required_components_available=not unavailable,
            blocking_issues=report.blocking_issues, warnings=report.warnings,
            checked_at=report.checked_at,
            human_readable_summary=f"Paper-trading operational readiness is {report.paper_trading_operational_readiness}.",
        )

    def errors(self) -> SystemErrors:
        errors: list[dict[str, Any]] = []
        for name, component in (
            ("live_monitor", self.monitor), ("trade_lifecycle_manager", self.lifecycle),
            ("daily_report_scheduler", self.scheduler),
            ("paper_trading_orchestrator", self.orchestrator),
            ("continuous_paper_trading", self._continuous_runtime()),
        ):
            if component is None:
                continue
            try:
                status = component.status()
                if getattr(status, "last_error", None):
                    errors.append({"component": name, "error": status.last_error, "error_count": int(getattr(status, "error_count", 1) or 1)})
            except Exception as exc:
                errors.append({"component": name, "error": str(exc), "error_count": 1})
        return SystemErrors(
            total_errors=sum(item["error_count"] for item in errors),
            errors=tuple(errors), checked_at=_now(),
            human_readable_summary=f"{len(errors)} components currently expose known errors.",
        )

    @staticmethod
    def _continuous_runtime():
        try:
            from core.continuous_paper_trading import current_continuous_paper_trading
            return current_continuous_paper_trading()
        except Exception:
            return None

    def _continuous_paper_dimension(self) -> HealthDimension:
        runtime = self._continuous_runtime()
        if runtime is None:
            try:
                importlib.import_module("core.continuous_paper_trading")
                return HealthDimension("continuous_paper_trading", "PASS", 100.0,
                    {"available": True, "running": False, "paused": False}, (), (),
                    "Continuous paper trading is available and not auto-started.")
            except Exception as exc:
                return HealthDimension("continuous_paper_trading", "UNAVAILABLE", 0.0,
                    {"available": False}, (), (f"Continuous paper runtime import failed: {exc}",),
                    "Continuous paper trading is unavailable.")
        status = runtime.status()
        warnings = tuple(status.pause_reasons)
        return HealthDimension("continuous_paper_trading", "WATCHLIST" if status.paused else "PASS",
            75.0 if status.paused else 100.0,
            {"available": True, "running": status.running, "paused": status.paused,
             "cycle_count": status.cycle_count, "error_count": status.error_count},
            warnings, (), "Continuous paper trading is paused." if status.paused else
            "Continuous paper trading is operational and paper-only.")

    def components(self) -> tuple[HealthDimension, ...]:
        return self.check().dimensions

    def storage(self) -> HealthDimension:
        warnings: list[str] = []
        blockers: list[str] = []
        details: dict[str, Any] = {"directories": {}, "optional_files": {}}
        for relative in self.REQUIRED_DIRS:
            path = self.root / relative
            try:
                path.mkdir(parents=True, exist_ok=True)
                writable = _writable(path)
            except OSError:
                writable = False
            details["directories"][relative] = {"exists": path.is_dir(), "writable": writable}
            if not writable:
                blockers.append(f"Required storage directory is not writable: {relative}")
        for relative in self.OPTIONAL_FILES:
            path = self.root / relative
            accessible = not path.exists() or os.access(path, os.R_OK | os.W_OK)
            details["optional_files"][relative] = {"exists": path.exists(), "accessible": accessible}
            if path.exists() and not accessible:
                blockers.append(f"Optional state file is inaccessible: {relative}")
            if path.exists() and relative == "research/paper_account_state.json":
                try:
                    json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    blockers.append("Paper account state file is corrupted or unreadable.")
        status: HealthStatus = "FAIL" if blockers else "WATCHLIST" if warnings else "PASS"
        return HealthDimension(
            "storage", status, 0.0 if blockers else 85.0 if warnings else 100.0,
            details, tuple(warnings), tuple(blockers),
            "Local storage is writable." if not blockers else "Local storage has blocking issues.",
        )

    def _application(self) -> HealthDimension:
        return HealthDimension("application", "PASS", 100.0, {"python": platform.python_version(), "platform": platform.system(), "uptime_seconds": round(time.monotonic() - _PROCESS_STARTED, 3)}, (), (), "StructureIQ application runtime is available.")

    def _configuration(self) -> HealthDimension:
        try:
            importlib.import_module("app.config")
            return HealthDimension("configuration", "PASS", 100.0, {"app_version": APP_VERSION}, (), (), "Application configuration loaded successfully.")
        except Exception as exc:
            return HealthDimension("configuration", "FAIL", 0.0, {}, (), (f"Application configuration failed: {exc}",), "Application configuration is unavailable.")

    def _provider(self) -> HealthDimension:
        if self.provider is None:
            return _unavailable("market_data_provider", "Market data provider is unavailable.")
        return HealthDimension("market_data_provider", "PASS", 100.0, {"provider": getattr(self.provider, "provider_name", type(self.provider).__name__)}, (), (), "Market data provider is configured; no external request was made.")

    def _runtime_component(self, name: str, component: Any | None) -> HealthDimension:
        if component is None:
            return _unavailable(name, f"{name.replace('_', ' ').title()} is unavailable.")
        try:
            state = component.status() if hasattr(component, "status") else None
            error = getattr(state, "last_error", None)
            paused = bool(getattr(state, "paused", False))
            if name == "paper_trading_orchestrator" and paused:
                return HealthDimension(name, "FAIL", 20.0, jsonable_encoder(state), (), ("Paper Trading Orchestrator is paused due to errors.",), "Paper Trading Orchestrator is paused and requires review.")
            if paused or error:
                warning = f"{name.replace('_', ' ').title()} reports: {error or 'paused'}"
                return HealthDimension(name, "WATCHLIST", 70.0, jsonable_encoder(state), (warning,), (), f"{name.replace('_', ' ').title()} is available with warnings.")
            return HealthDimension(name, "PASS", 100.0, jsonable_encoder(state) if state else {"available": True}, (), (), f"{name.replace('_', ' ').title()} is available and safe when stopped.")
        except Exception as exc:
            return HealthDimension(name, "FAIL", 0.0, {}, (), (f"{name} state failed: {exc}",), f"{name.replace('_', ' ').title()} state is invalid.")

    def _paper_brokerage(self) -> HealthDimension:
        if self.broker is None:
            return _unavailable("paper_brokerage", "Paper Brokerage is unavailable.")
        try:
            account = self.broker.account()
            if account.balance < 0 or account.equity != account.equity:
                raise ValueError("paper account contains invalid financial state")
            warnings = () if account.risk_status == "available" else (f"Paper risk status is {account.risk_status}.",)
            return HealthDimension("paper_brokerage", "WATCHLIST" if warnings else "PASS", 75.0 if warnings else 100.0, jsonable_encoder(account), warnings, (), "Paper account state is valid.")
        except Exception as exc:
            return HealthDimension("paper_brokerage", "FAIL", 0.0, {}, (), (f"Paper account state is corrupted: {exc}",), "Paper Brokerage account state is invalid.")

    def _journal(self) -> HealthDimension:
        if self.journal is None:
            return _unavailable("paper_trade_journal", "Paper Trade Journal is unavailable.")
        try:
            summary = self.journal.summary()
            parent_writable = _writable(self.journal.path.parent)
            blockers = () if parent_writable else ("Paper journal path is not writable.",)
            return HealthDimension("paper_trade_journal", "FAIL" if blockers else "PASS", 0.0 if blockers else 100.0, {"summary": jsonable_encoder(summary), "path": str(self.journal.path)}, (), blockers, "Paper Trade Journal is available." if not blockers else "Paper Trade Journal storage is unavailable.")
        except Exception as exc:
            return HealthDimension("paper_trade_journal", "FAIL", 0.0, {}, (), (f"Paper Trade Journal failed: {exc}",), "Paper Trade Journal is invalid.")

    def _module_dimension(self, name: str, module: str) -> HealthDimension:
        try:
            importlib.import_module(module)
            return HealthDimension(name, "PASS", 100.0, {"module": module}, (), (), f"{name.replace('_', ' ').title()} module is available.")
        except Exception as exc:
            return HealthDimension(name, "FAIL", 0.0, {"module": module}, (), (f"Required module import failed: {module}: {exc}",), f"{name.replace('_', ' ').title()} module failed to import.")

    def _folder_dimension(self, name: str, relative: str) -> HealthDimension:
        path = self.root / relative
        try:
            path.mkdir(parents=True, exist_ok=True)
            writable = _writable(path)
        except OSError:
            writable = False
        blockers = () if writable else (f"{relative} directory is not writable.",)
        return HealthDimension(name, "PASS" if writable else "FAIL", 100.0 if writable else 0.0, {"path": str(path), "writable": writable}, (), blockers, f"{relative} storage is {'available' if writable else 'unavailable'}.")

    def _research_files(self) -> HealthDimension:
        details = {}
        blockers = []
        for relative in self.OPTIONAL_FILES:
            path = self.root / relative
            if not relative.startswith("research/"):
                continue
            accessible = not path.exists() or os.access(path, os.R_OK)
            details[relative] = {"exists": path.exists(), "readable": accessible}
            if not accessible:
                blockers.append(f"Research file is unreadable: {relative}")
        return HealthDimension("research_files", "FAIL" if blockers else "PASS", 0.0 if blockers else 100.0, details, (), tuple(blockers), "Optional research files are healthy; missing files are allowed.")

    def _paper_readiness(self, dimensions, warnings) -> str:
        required = [item for item in dimensions if item.name in self.REQUIRED_PAPER_COMPONENTS]
        if len(required) != len(self.REQUIRED_PAPER_COMPONENTS) or any(item.status in {"FAIL", "UNAVAILABLE"} for item in required):
            return "NOT_READY"
        if warnings or any(item.status == "WATCHLIST" for item in required):
            return "WATCHLIST"
        return "READY"

    def _log(self, report: SystemHealthReport) -> None:
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(jsonable_encoder(report), separators=(",", ":")) + "\n")
        except OSError:
            pass


def _writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / f".health-probe-{os.getpid()}-{threading.get_ident()}"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def _unavailable(name: str, summary: str) -> HealthDimension:
    return HealthDimension(name, "UNAVAILABLE", 0.0, {}, (), (), summary)


def _recommended_actions(blockers, warnings) -> tuple[str, ...]:
    actions = []
    if blockers: actions.append("Resolve all blocking health issues before continuous paper trading.")
    if warnings: actions.append("Review component warnings and recent local error history.")
    if not actions: actions.append("No corrective action is required; continue local observability checks.")
    return tuple(actions)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


_LATEST_HEALTH: SystemHealthReport | None = None
_LATEST_LOCK = threading.RLock()


def _set_latest(report: SystemHealthReport) -> None:
    global _LATEST_HEALTH
    with _LATEST_LOCK: _LATEST_HEALTH = report


def latest_system_health() -> SystemHealthReport | None:
    with _LATEST_LOCK: return _LATEST_HEALTH


def reset_latest_system_health() -> None:
    global _LATEST_HEALTH
    with _LATEST_LOCK: _LATEST_HEALTH = None
