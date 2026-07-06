"""Observational diagnostics for every market evaluated by the live monitor."""

from __future__ import annotations

import json
import threading
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi.encoders import jsonable_encoder


CONFIDENCE_REFERENCE = 70.0
SETUP_QUALITY_REFERENCE = 85.0
SCORE_REFERENCE = 70.0
REASON_PRIORITY = (
    "duplicate_candidate", "directional_confidence", "confidence_threshold",
    "structure_alignment", "higher_timeframe_alignment", "trend_conflict",
    "insufficient_confirmation", "missing_liquidity_sweep",
    "minimum_setup_quality", "execution_intelligence", "execution_cost",
    "risk_filter", "market_regime_filter", "score_threshold", "unknown",
)


@dataclass(frozen=True)
class CandidateDistance:
    metric: str
    required: float
    actual: float
    distance: float


@dataclass(frozen=True)
class CandidateDiagnostic:
    timestamp: str
    symbol: str
    timeframe: str
    higher_timeframe: str
    analysis_completed: bool
    candidate_created: bool
    highest_confidence: float
    highest_setup_quality: float
    best_strategy: str
    best_setup_name: str
    market_regime: str
    trend_direction: str
    execution_cost_grade: str
    overall_score: float
    blocked_reasons: tuple[str, ...]
    warnings: tuple[str, ...]
    rule_failures: tuple[str, ...]
    distance_to_candidate: tuple[CandidateDistance, ...]


@dataclass(frozen=True)
class CandidateDiagnosticsSummary:
    markets_analyzed: int
    candidates_created: int
    candidate_rate_percent: float
    average_confidence: float
    average_setup_quality: float
    average_score: float
    highest_confidence_rejected: float | None
    highest_setup_quality_rejected: float | None
    highest_score_rejected: float | None
    closest_missed_candidate: CandidateDiagnostic | None
    most_common_rejection_reason: str | None
    rejection_reason_frequencies: dict[str, int]
    top_rejection_reasons: tuple[tuple[str, int], ...]
    human_readable_summary: str


class CandidateDiagnosticsEngine:
    """Record monitor outcomes without influencing candidate eligibility."""

    def __init__(self, path: str | Path = "research/candidate_diagnostics.jsonl") -> None:
        self.path = Path(path)
        self._records: list[CandidateDiagnostic] = []
        self._lock = threading.RLock()
        self._load()

    def record_analysis(
        self, analysis: Any, *, timeframe: str, higher_timeframe: str,
        candidate_created: bool, duplicate: bool = False,
    ) -> CandidateDiagnostic:
        confidence = float(getattr(getattr(analysis, "decision", None), "confidence", 0.0) or 0.0)
        quality = float(getattr(getattr(analysis, "setup_quality", None), "score",
                                getattr(getattr(analysis, "setup_plan", None), "setup_quality_score", 0.0)) or 0.0)
        score = float(getattr(getattr(analysis, "score_summary", None), "trade_quality_score", 0.0) or 0.0)
        reasons, failures = _rejection_reasons(analysis, candidate_created, duplicate, confidence, quality, score)
        warnings = _warnings(analysis)
        distances = () if candidate_created else (
            CandidateDistance("directional_confidence", CONFIDENCE_REFERENCE, confidence, round(confidence - CONFIDENCE_REFERENCE, 2)),
            CandidateDistance("setup_quality_reference", SETUP_QUALITY_REFERENCE, quality, round(quality - SETUP_QUALITY_REFERENCE, 2)),
            CandidateDistance("overall_score_reference", SCORE_REFERENCE, score, round(score - SCORE_REFERENCE, 2)),
        )
        record = CandidateDiagnostic(
            timestamp=_now(), symbol=str(getattr(analysis, "symbol", "unknown")),
            timeframe=timeframe, higher_timeframe=higher_timeframe,
            analysis_completed=True, candidate_created=candidate_created,
            highest_confidence=round(confidence, 2), highest_setup_quality=round(quality, 2),
            best_strategy=_value(getattr(getattr(analysis, "strategy", None), "preferred_strategy", "no_strategy")),
            best_setup_name=_value(getattr(getattr(analysis, "setup_plan", None), "setup_type", getattr(analysis, "setup", "no_valid_setup"))),
            market_regime=_value(getattr(getattr(analysis, "market_regime", None), "market_regime", "unknown")),
            trend_direction=_value(getattr(getattr(analysis, "multi_timeframe", None), "directional_bias", "unclear")),
            execution_cost_grade=str(getattr(getattr(analysis, "execution_intelligence", None), "execution_grade", "unavailable")),
            overall_score=round(score, 2), blocked_reasons=reasons,
            warnings=warnings, rule_failures=failures, distance_to_candidate=distances,
        )
        return self._append(record)

    def record_failure(self, *, symbol: str, timeframe: str, higher_timeframe: str, error: str) -> CandidateDiagnostic:
        record = CandidateDiagnostic(
            timestamp=_now(), symbol=symbol, timeframe=timeframe, higher_timeframe=higher_timeframe,
            analysis_completed=False, candidate_created=False, highest_confidence=0.0,
            highest_setup_quality=0.0, best_strategy="unavailable", best_setup_name="unavailable",
            market_regime="unknown", trend_direction="unclear", execution_cost_grade="unavailable",
            overall_score=0.0, blocked_reasons=("unknown",), warnings=(error,),
            rule_failures=(f"Analysis did not complete: {error}",), distance_to_candidate=(),
        )
        return self._append(record)

    def recent(self, limit: int = 100) -> tuple[CandidateDiagnostic, ...]:
        with self._lock: return tuple(self._records[-limit:])

    def reasons(self) -> dict[str, int]:
        with self._lock:
            counts = Counter(reason for item in self._records if not item.candidate_created for reason in item.blocked_reasons)
        return dict(sorted(counts.items(), key=lambda item: (-item[1], _priority(item[0]))))

    def near_misses(self, limit: int = 100) -> tuple[CandidateDiagnostic, ...]:
        with self._lock:
            misses = [item for item in self._records if item.analysis_completed and not item.candidate_created]
        misses.sort(key=lambda item: (_shortfall(item), -item.overall_score, item.timestamp))
        return tuple(misses[:limit])

    def summary(self) -> CandidateDiagnosticsSummary:
        with self._lock: records = tuple(self._records)
        completed = [item for item in records if item.analysis_completed]
        rejected = [item for item in completed if not item.candidate_created]
        candidates = sum(item.candidate_created for item in completed)
        reasons = self.reasons(); top = tuple(list(reasons.items())[:10])
        closest = self.near_misses(1)
        return CandidateDiagnosticsSummary(
            markets_analyzed=len(completed), candidates_created=candidates,
            candidate_rate_percent=round(candidates / len(completed) * 100, 2) if completed else 0.0,
            average_confidence=_average(completed, "highest_confidence"),
            average_setup_quality=_average(completed, "highest_setup_quality"),
            average_score=_average(completed, "overall_score"),
            highest_confidence_rejected=max((item.highest_confidence for item in rejected), default=None),
            highest_setup_quality_rejected=max((item.highest_setup_quality for item in rejected), default=None),
            highest_score_rejected=max((item.overall_score for item in rejected), default=None),
            closest_missed_candidate=closest[0] if closest else None,
            most_common_rejection_reason=top[0][0] if top else None,
            rejection_reason_frequencies=reasons, top_rejection_reasons=top,
            human_readable_summary=f"Candidate diagnostics observed {len(completed)} completed markets and {candidates} candidates ({round(candidates / len(completed) * 100, 2) if completed else 0.0}%).",
        )

    def writable(self) -> bool:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            probe = self.path.parent / ".candidate-diagnostics-write-probe"
            probe.write_text("ok", encoding="utf-8"); probe.unlink()
            return True
        except OSError:
            return False

    def _append(self, record: CandidateDiagnostic) -> CandidateDiagnostic:
        with self._lock:
            self._records.append(record)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(jsonable_encoder(record), separators=(",", ":")) + "\n")
        return record

    def _load(self) -> None:
        if not self.path.exists(): return
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                raw = json.loads(line)
                raw["blocked_reasons"] = tuple(raw.get("blocked_reasons", ()))
                raw["warnings"] = tuple(raw.get("warnings", ()))
                raw["rule_failures"] = tuple(raw.get("rule_failures", ()))
                raw["distance_to_candidate"] = tuple(CandidateDistance(**item) for item in raw.get("distance_to_candidate", ()))
                self._records.append(CandidateDiagnostic(**raw))
            except (ValueError, TypeError, json.JSONDecodeError):
                continue


def _rejection_reasons(analysis, created, duplicate, confidence, quality, score):
    if created: return (), ()
    reasons: list[str] = ["duplicate_candidate"] if duplicate else []
    failures: list[str] = []
    diagnostics = getattr(getattr(analysis, "decision", None), "decision_diagnostics", None)
    gate_map = {
        "directional_confidence": "directional_confidence", "confidence_threshold": "confidence_threshold",
        "structure_alignment": "structure_alignment", "multi_timeframe_alignment": "higher_timeframe_alignment",
        "risk_plan_available": "risk_filter", "risk_plan_quality": "risk_filter",
        "risk_reward_available": "risk_filter", "risk_reward_minimum": "risk_filter",
        "conflicting_evidence": "trend_conflict", "setup_confirmation": "insufficient_confirmation",
    }
    for gate in getattr(diagnostics, "gate_results", ()) or ():
        if getattr(gate, "required", False) and not getattr(gate, "passed", False):
            reasons.append(gate_map.get(str(getattr(gate, "gate_name", "")), str(getattr(gate, "gate_name", "unknown"))))
            if getattr(gate, "blocking_reason", None): failures.append(str(gate.blocking_reason))
    if confidence < CONFIDENCE_REFERENCE: reasons.append("directional_confidence")
    multi = getattr(analysis, "multi_timeframe", None)
    if _value(getattr(multi, "alignment", "unclear")) in {"conflicting", "unclear"}: reasons.append("higher_timeframe_alignment")
    setup = getattr(analysis, "setup_plan", None)
    if _value(getattr(setup, "setup_status", "no_setup")) != "confirmed": reasons.append("insufficient_confirmation")
    for condition in getattr(setup, "entry_conditions", ()) or ():
        if str(getattr(condition, "importance", "")) == "required" and not getattr(condition, "is_met", False):
            failures.append(str(getattr(condition, "condition", "Required setup condition is unmet.")))
    execution = getattr(analysis, "execution_intelligence", None)
    blockers = tuple(getattr(execution, "execution_blockers", ()) or ())
    if blockers: reasons.append("execution_intelligence"); failures.extend(map(str, blockers))
    ratio = getattr(setup, "estimated_risk_reward", None)
    if ratio is None or ratio < 1.5: reasons.append("risk_filter")
    if quality < SETUP_QUALITY_REFERENCE: reasons.append("minimum_setup_quality")
    if score < SCORE_REFERENCE: reasons.append("score_threshold")
    if not reasons: reasons.append("unknown")
    ordered = tuple(sorted(set(reasons), key=_priority))
    return ordered, tuple(dict.fromkeys(failures))


def _warnings(analysis):
    setup = getattr(analysis, "setup_plan", None); execution = getattr(analysis, "execution_intelligence", None)
    values = [*tuple(getattr(setup, "warning_notes", ()) or ()), *tuple(getattr(execution, "execution_warnings", ()) or ())]
    return tuple(dict.fromkeys(map(str, values)))


def _shortfall(record): return round(sum(max(0.0, -item.distance) for item in record.distance_to_candidate), 4)
def _priority(reason): return REASON_PRIORITY.index(reason) if reason in REASON_PRIORITY else len(REASON_PRIORITY)
def _average(records, field): return round(sum(float(getattr(item, field)) for item in records) / len(records), 2) if records else 0.0
def _value(value): return str(getattr(value, "value", value))
def _now(): return datetime.now(timezone.utc).isoformat()


_GLOBAL_ENGINE: CandidateDiagnosticsEngine | None = None
_GLOBAL_LOCK = threading.RLock()


def get_global_candidate_diagnostics() -> CandidateDiagnosticsEngine:
    global _GLOBAL_ENGINE
    with _GLOBAL_LOCK:
        if _GLOBAL_ENGINE is None: _GLOBAL_ENGINE = CandidateDiagnosticsEngine()
        return _GLOBAL_ENGINE


def current_candidate_diagnostics() -> CandidateDiagnosticsEngine | None: return _GLOBAL_ENGINE


def reset_global_candidate_diagnostics() -> None:
    global _GLOBAL_ENGINE
    with _GLOBAL_LOCK: _GLOBAL_ENGINE = None
