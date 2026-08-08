"""Cycle-level candidate pipeline diagnostics for paper runtime validation.

This module is intentionally observational. It records what the existing monitor
and orchestrator already did; it never changes candidate creation, approvals,
orders, or paper trades.
"""

from __future__ import annotations

import json
import threading
from collections import Counter, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi.encoders import jsonable_encoder


REJECTION_STAGE_MAP = {
    "unknown": "UNKNOWN",
    "directional_confidence": "CONFIDENCE",
    "confidence_threshold": "CONFIDENCE",
    "higher_timeframe_alignment": "TIMEFRAME_ALIGNMENT",
    "structure_alignment": "MARKET_STRUCTURE",
    "trend_conflict": "BIAS",
    "insufficient_confirmation": "SETUP_DETECTION",
    "missing_liquidity_sweep": "SETUP_DETECTION",
    "minimum_setup_quality": "SETUP_QUALITY",
    "execution_intelligence": "AUTO_APPROVAL",
    "execution_cost": "AUTO_APPROVAL",
    "risk_filter": "RISK",
    "duplicate_candidate": "DUPLICATE",
    "score_threshold": "CONFIDENCE",
}


@dataclass(frozen=True)
class CandidateSymbolPipelineDiagnostic:
    symbol: str
    market_data_status: str
    candles_received: int
    timeframes_received: int
    structure_status: str
    bias_status: str
    setup_status: str
    confidence_score: float | None
    setup_quality_score: float | None
    risk_status: str
    candidate_status: str
    final_outcome: str
    rejection_stage: str | None
    rejection_reason: str | None
    exception_type: str | None
    exception_message: str | None
    analyzed: bool = True
    skipped: bool = False
    skipped_reason: str | None = None


@dataclass(frozen=True)
class CandidatePipelineCycleDiagnostic:
    cycle_id: str
    campaign_id: str | None
    started_at: str
    completed_at: str
    symbols_requested: int
    symbols_scanned: int
    symbols_with_market_data: int
    symbols_without_market_data: int
    symbols_skipped: int
    symbols_skipped_market_closed: int
    candidates_created: int
    candidates_rejected: int
    orders_created: int
    trades_opened: int
    cycle_status: str
    cycle_duration_ms: float
    symbol_diagnostics: tuple[CandidateSymbolPipelineDiagnostic, ...]
    persistence_errors: tuple[str, ...]
    zero_candidate_explanation: str | None


@dataclass(frozen=True)
class CandidatePipelineSummary:
    cycles: int
    symbols_requested: int
    symbols_scanned: int
    symbols_with_data: int
    symbols_without_data: int
    symbols_skipped: int
    symbols_skipped_market_closed: int
    candidates_created: int
    candidates_rejected: int
    trades_opened: int
    top_rejection_stages: tuple[tuple[str, int], ...]
    top_rejection_reasons: tuple[tuple[str, int], ...]
    data_availability_rate: float
    candidate_conversion_rate: float
    trade_conversion_rate: float
    latest_cycle: CandidatePipelineCycleDiagnostic | None
    closest_zero_candidate_explanation: str | None
    human_readable_summary: str


class CandidatePipelineDiagnosticsEngine:
    """Persist and summarize one candidate-pipeline row per paper cycle."""

    def __init__(
        self,
        path: str | Path = "reports/candidate_pipeline_diagnostics.jsonl",
        *,
        campaigns_root: str | Path = "validation_campaigns",
        max_cycles_in_memory: int = 500,
    ) -> None:
        self.path = Path(path)
        self.campaigns_root = Path(campaigns_root)
        self._cycles: deque[CandidatePipelineCycleDiagnostic] = deque(maxlen=max_cycles_in_memory)
        self._persistence_errors: deque[str] = deque(maxlen=50)
        self._lock = threading.RLock()
        self._load()

    def record_cycle(
        self,
        *,
        cycle_id: str,
        campaign_id: str | None,
        started_at: str,
        completed_at: str,
        monitor_result: Any,
        orders_created: int,
        trades_opened: int,
        cycle_status: str,
        configured_symbols: tuple[str, ...],
        configured_timeframes: tuple[str, ...],
        recent_market_diagnostics: tuple[Any, ...] = (),
    ) -> CandidatePipelineCycleDiagnostic:
        requested = max(1, len(configured_symbols) * len(configured_timeframes))
        errors = tuple(getattr(monitor_result, "errors", ()) or ())
        candidates = int(getattr(monitor_result, "candidates_created", 0) or 0)
        analyzed = int(getattr(monitor_result, "analyzed", 0) or 0)
        symbols_without_data = len(errors)
        skipped_symbols = tuple(getattr(monitor_result, "skipped_symbols", ()) or ())
        skipped_count = int(getattr(monitor_result, "markets_skipped", 0) or len(skipped_symbols) * max(1, len(configured_timeframes)))
        skipped_market_closed = sum(
            "closed" in str(reason).lower()
            for reason in (getattr(monitor_result, "skipped_reasons", {}) or {}).values()
        ) * max(1, len(configured_timeframes))
        scanned = analyzed + symbols_without_data
        rejected = max(0, scanned - candidates)
        details = _build_symbol_details(recent_market_diagnostics, errors, configured_symbols, monitor_result=monitor_result)
        if not details and scanned == 0:
            details = tuple(
                CandidateSymbolPipelineDiagnostic(
                    symbol=symbol,
                    market_data_status="not_scanned",
                    candles_received=0,
                    timeframes_received=0,
                    structure_status="unknown",
                    bias_status="unknown",
                    setup_status="unknown",
                    confidence_score=None,
                    setup_quality_score=None,
                    risk_status="unknown",
                    candidate_status="not_created",
                    final_outcome="not_scanned",
                    rejection_stage="UNKNOWN",
                    rejection_reason="monitor did not scan this symbol",
                    exception_type=None,
                    exception_message=None,
                    analyzed=False,
                    skipped=False,
                    skipped_reason=None,
                )
                for symbol in configured_symbols
            )
        zero_explanation = _zero_candidate_explanation(details, candidates)
        duration = _duration_ms(started_at, completed_at)
        cycle = CandidatePipelineCycleDiagnostic(
            cycle_id=cycle_id,
            campaign_id=campaign_id,
            started_at=started_at,
            completed_at=completed_at,
            symbols_requested=requested,
            symbols_scanned=scanned,
            symbols_with_market_data=analyzed,
            symbols_without_market_data=symbols_without_data,
            symbols_skipped=skipped_count,
            symbols_skipped_market_closed=skipped_market_closed,
            candidates_created=candidates,
            candidates_rejected=rejected,
            orders_created=int(orders_created or 0),
            trades_opened=int(trades_opened or 0),
            cycle_status=cycle_status,
            cycle_duration_ms=duration,
            symbol_diagnostics=details,
            persistence_errors=(),
            zero_candidate_explanation=zero_explanation,
        )
        errors_seen = self._persist(cycle)
        if errors_seen:
            cycle = CandidatePipelineCycleDiagnostic(**{**cycle.__dict__, "persistence_errors": tuple(errors_seen)})
        with self._lock:
            self._cycles.append(cycle)
        return cycle

    def summary(
        self,
        *,
        campaign_id: str | None = None,
        symbol: str | None = None,
        rejection_stage: str | None = None,
    ) -> CandidatePipelineSummary:
        cycles = self._filtered(campaign_id=campaign_id, symbol=symbol, rejection_stage=rejection_stage)
        requested = sum(item.symbols_requested for item in cycles)
        scanned = sum(item.symbols_scanned for item in cycles)
        with_data = sum(item.symbols_with_market_data for item in cycles)
        without_data = sum(item.symbols_without_market_data for item in cycles)
        skipped = sum(getattr(item, "symbols_skipped", 0) for item in cycles)
        skipped_closed = sum(getattr(item, "symbols_skipped_market_closed", 0) for item in cycles)
        candidates = sum(item.candidates_created for item in cycles)
        rejected = sum(item.candidates_rejected for item in cycles)
        trades = sum(item.trades_opened for item in cycles)
        stage_counts, reason_counts = _counts(cycles)
        latest = cycles[-1] if cycles else None
        return CandidatePipelineSummary(
            cycles=len(cycles),
            symbols_requested=requested,
            symbols_scanned=scanned,
            symbols_with_data=with_data,
            symbols_without_data=without_data,
            symbols_skipped=skipped,
            symbols_skipped_market_closed=skipped_closed,
            candidates_created=candidates,
            candidates_rejected=rejected,
            trades_opened=trades,
            top_rejection_stages=tuple(stage_counts.most_common(10)),
            top_rejection_reasons=tuple(reason_counts.most_common(10)),
            data_availability_rate=round(with_data / scanned * 100, 3) if scanned else 0.0,
            candidate_conversion_rate=round(candidates / scanned * 100, 3) if scanned else 0.0,
            trade_conversion_rate=round(trades / scanned * 100, 3) if scanned else 0.0,
            latest_cycle=latest,
            closest_zero_candidate_explanation=latest.zero_candidate_explanation if latest else None,
            human_readable_summary=(
                f"Candidate pipeline recorded {len(cycles)} cycles, {scanned} scanned markets, "
                f"{candidates} candidates, and {trades} paper trades."
            ),
        )

    def recent(self, limit: int = 100, *, campaign_id: str | None = None) -> tuple[CandidatePipelineCycleDiagnostic, ...]:
        cycles = self._filtered(campaign_id=campaign_id)
        return tuple(cycles[-limit:])

    def cycle(self, cycle_id: str) -> CandidatePipelineCycleDiagnostic | None:
        with self._lock:
            return next((item for item in self._cycles if item.cycle_id == cycle_id), None)

    def rejections(self, *, campaign_id: str | None = None) -> dict[str, Any]:
        cycles = self._filtered(campaign_id=campaign_id)
        stages, reasons = _counts(cycles)
        return {
            "top_rejection_stages": tuple(stages.most_common()),
            "top_rejection_reasons": tuple(reasons.most_common()),
            "human_readable_summary": f"Found {sum(stages.values())} stage-level rejections across {len(cycles)} cycles.",
        }

    def writable(self) -> bool:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            probe = self.path.parent / ".candidate-pipeline-probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            return True
        except OSError:
            return False

    def persistence_errors(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(self._persistence_errors)

    def _filtered(self, *, campaign_id: str | None = None, symbol: str | None = None, rejection_stage: str | None = None) -> list[CandidatePipelineCycleDiagnostic]:
        with self._lock:
            cycles = list(self._cycles)
        if campaign_id is not None:
            cycles = [item for item in cycles if item.campaign_id == campaign_id]
        if symbol is not None:
            cycles = [
                item for item in cycles
                if any(detail.symbol == symbol for detail in item.symbol_diagnostics)
            ]
        if rejection_stage is not None:
            cycles = [
                item for item in cycles
                if any(detail.rejection_stage == rejection_stage for detail in item.symbol_diagnostics)
            ]
        return cycles

    def _persist(self, cycle: CandidatePipelineCycleDiagnostic) -> list[str]:
        errors: list[str] = []
        for path in (self.path, self._campaign_path(cycle.campaign_id) if cycle.campaign_id else None):
            if path is None:
                continue
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(jsonable_encoder(cycle), separators=(",", ":")) + "\n")
            except OSError as exc:
                message = f"{path}: {exc}"
                errors.append(message)
                with self._lock:
                    self._persistence_errors.append(message)
        return errors

    def _campaign_path(self, campaign_id: str | None) -> Path | None:
        return self.campaigns_root / campaign_id / "candidate_diagnostics.jsonl" if campaign_id else None

    def _load(self) -> None:
        if not self.path.exists():
            return
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                raw = json.loads(line)
                raw["symbol_diagnostics"] = tuple(CandidateSymbolPipelineDiagnostic(**item) for item in raw.get("symbol_diagnostics", ()))
                raw["persistence_errors"] = tuple(raw.get("persistence_errors", ()))
                raw.setdefault("symbols_skipped", 0)
                raw.setdefault("symbols_skipped_market_closed", 0)
                self._cycles.append(CandidatePipelineCycleDiagnostic(**raw))
            except (TypeError, ValueError, json.JSONDecodeError):
                continue


def _build_symbol_details(records: tuple[Any, ...], errors: tuple[str, ...], configured_symbols: tuple[str, ...], *, monitor_result: Any | None = None) -> tuple[CandidateSymbolPipelineDiagnostic, ...]:
    details: list[CandidateSymbolPipelineDiagnostic] = []
    for item in records:
        reason = (tuple(getattr(item, "blocked_reasons", ()) or ()) or ("unknown",))[0]
        stage = None if getattr(item, "candidate_created", False) else REJECTION_STAGE_MAP.get(reason, "UNKNOWN")
        details.append(CandidateSymbolPipelineDiagnostic(
            symbol=str(getattr(item, "symbol", "unknown")),
            market_data_status="available" if getattr(item, "analysis_completed", False) else "unavailable",
            candles_received=1 if getattr(item, "analysis_completed", False) else 0,
            timeframes_received=1 if getattr(item, "analysis_completed", False) else 0,
            structure_status="completed" if getattr(item, "analysis_completed", False) else "unavailable",
            bias_status=str(getattr(item, "trend_direction", "unknown")),
            setup_status=str(getattr(item, "best_setup_name", "unknown")),
            confidence_score=getattr(item, "highest_confidence", None),
            setup_quality_score=getattr(item, "highest_setup_quality", None),
            risk_status="blocked" if reason == "risk_filter" else "available",
            candidate_status="created" if getattr(item, "candidate_created", False) else "rejected",
            final_outcome="candidate_created" if getattr(item, "candidate_created", False) else "candidate_rejected",
            rejection_stage=stage,
            rejection_reason=None if getattr(item, "candidate_created", False) else reason,
            exception_type=None,
            exception_message=None,
            analyzed=True,
            skipped=False,
            skipped_reason=None,
        ))
    for error in errors:
        symbol = error.split(" ", 1)[0] if error else "unknown"
        if configured_symbols and symbol not in configured_symbols:
            symbol = "unknown"
        details.append(CandidateSymbolPipelineDiagnostic(
            symbol=symbol,
            market_data_status="error",
            candles_received=0,
            timeframes_received=0,
            structure_status="not_run",
            bias_status="not_run",
            setup_status="not_run",
            confidence_score=None,
            setup_quality_score=None,
            risk_status="not_run",
            candidate_status="not_created",
            final_outcome="provider_or_analysis_error",
            rejection_stage="MARKET_DATA",
            rejection_reason="market data or analysis failed",
            exception_type="MarketDataError",
            exception_message=error,
            analyzed=False,
            skipped=False,
            skipped_reason=None,
        ))
    skipped_reasons = getattr(monitor_result, "skipped_reasons", None) or {}
    for symbol, reason in skipped_reasons.items():
        if configured_symbols and symbol not in configured_symbols:
            continue
        details.append(CandidateSymbolPipelineDiagnostic(
            symbol=symbol,
            market_data_status="skipped",
            candles_received=0,
            timeframes_received=0,
            structure_status="not_run",
            bias_status="not_run",
            setup_status="not_run",
            confidence_score=None,
            setup_quality_score=None,
            risk_status="not_run",
            candidate_status="skipped",
            final_outcome="market_session_skipped",
            rejection_stage=None,
            rejection_reason=None,
            exception_type=None,
            exception_message=None,
            analyzed=False,
            skipped=True,
            skipped_reason=str(reason),
        ))
    return tuple(details)


def _counts(cycles: list[CandidatePipelineCycleDiagnostic]) -> tuple[Counter[str], Counter[str]]:
    stages: Counter[str] = Counter()
    reasons: Counter[str] = Counter()
    for cycle in cycles:
        for detail in cycle.symbol_diagnostics:
            if getattr(detail, "skipped", False):
                continue
            if detail.rejection_stage:
                stages[detail.rejection_stage] += 1
            if detail.rejection_reason:
                reasons[detail.rejection_reason] += 1
    return stages, reasons


def _zero_candidate_explanation(details: tuple[CandidateSymbolPipelineDiagnostic, ...], candidates: int) -> str | None:
    if candidates:
        return None
    stages = Counter(detail.rejection_stage for detail in details if detail.rejection_stage and not getattr(detail, "skipped", False))
    if not stages:
        skipped = [detail for detail in details if getattr(detail, "skipped", False)]
        if skipped:
            return f"No candidates were created. {len(skipped)} markets were skipped before analysis because their market session was closed."
        return "No candidates were created and no rejection-stage diagnostics were available."
    stage, count = stages.most_common(1)[0]
    return f"No candidates reached the approval stage. Most symbols were rejected during {stage} ({count} records)."


def _duration_ms(started_at: str, completed_at: str) -> float:
    from datetime import datetime
    try:
        return round(max(0.0, (datetime.fromisoformat(completed_at) - datetime.fromisoformat(started_at)).total_seconds() * 1000), 3)
    except ValueError:
        return 0.0


_GLOBAL_PIPELINE_ENGINE: CandidatePipelineDiagnosticsEngine | None = None
_GLOBAL_LOCK = threading.RLock()


def get_global_candidate_pipeline_diagnostics() -> CandidatePipelineDiagnosticsEngine:
    global _GLOBAL_PIPELINE_ENGINE
    with _GLOBAL_LOCK:
        if _GLOBAL_PIPELINE_ENGINE is None:
            _GLOBAL_PIPELINE_ENGINE = CandidatePipelineDiagnosticsEngine()
        return _GLOBAL_PIPELINE_ENGINE


def current_candidate_pipeline_diagnostics() -> CandidatePipelineDiagnosticsEngine | None:
    return _GLOBAL_PIPELINE_ENGINE


def reset_global_candidate_pipeline_diagnostics() -> None:
    global _GLOBAL_PIPELINE_ENGINE
    with _GLOBAL_LOCK:
        _GLOBAL_PIPELINE_ENGINE = None
