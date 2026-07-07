"""Read-only distribution and funnel analytics over candidate diagnostics."""

from __future__ import annotations

import json
import threading
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class DistributionBucket:
    bucket: str
    lower_bound: int
    upper_bound: int
    count: int
    percent: float


@dataclass(frozen=True)
class DistributionResult:
    metric: str
    total_records: int
    buckets: tuple[DistributionBucket, ...]
    human_readable_summary: str


@dataclass(frozen=True)
class RejectionWaterfallItem:
    reason: str
    count: int
    percent: float
    rank: int


@dataclass(frozen=True)
class RejectionWaterfallResult:
    markets_analyzed: int
    rejected_markets: int
    reasons: tuple[RejectionWaterfallItem, ...]
    human_readable_summary: str


@dataclass(frozen=True)
class ConversionFunnel:
    markets_analyzed: int
    analysis_completed: int
    candidate_created: int
    duplicate_candidate: int
    blocked_by_confidence: int
    blocked_by_htf_alignment: int
    blocked_by_structure: int
    blocked_by_setup_quality: int
    blocked_by_execution: int
    blocked_by_risk: int
    blocked_by_score: int
    near_misses: int
    paper_trades_opened: int
    human_readable_summary: str


@dataclass(frozen=True)
class SymbolAnalytics:
    symbol: str
    markets_analyzed: int
    candidates_created: int
    candidate_rate_percent: float
    average_confidence: float
    average_setup_quality: float
    average_score: float
    highest_confidence: float
    highest_setup_quality: float
    highest_score: float
    most_common_rejection_reason: str | None
    near_miss_count: int


@dataclass(frozen=True)
class CategoryAnalytics:
    name: str
    count: int
    candidate_count: int
    rejected_count: int
    candidate_rate_percent: float
    average_confidence: float
    average_setup_quality: float
    average_score: float
    top_rejection_reasons: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class GroupAnalyticsResult:
    dimension: str
    groups: tuple[Any, ...]
    human_readable_summary: str


@dataclass(frozen=True)
class NearMissSummary:
    closest_missed_candidate: dict[str, Any] | None
    near_miss_count: int
    average_distance_to_confidence_threshold: float | None
    average_distance_to_quality_threshold: float | None
    average_distance_to_score_threshold: float | None


@dataclass(frozen=True)
class CalibrationAnalyticsSummary:
    markets_analyzed: int
    candidates_created: int
    candidate_conversion_rate: float
    confidence_distribution_summary: str
    setup_quality_distribution_summary: str
    score_distribution_summary: str
    top_rejection_reason: str | None
    closest_missed_candidate: dict[str, Any] | None
    near_miss_count: int
    average_distance_to_confidence_threshold: float | None
    average_distance_to_quality_threshold: float | None
    average_distance_to_score_threshold: float | None
    best_symbol_by_candidate_rate: str | None
    weakest_symbol_by_average_score: str | None
    most_common_market_regime: str | None
    human_readable_summary: str


class CalibrationAnalyticsEngine:
    """Compute fresh analytics without writing or changing diagnostic history."""

    def __init__(
        self,
        diagnostics_path: str | Path = "research/candidate_diagnostics.jsonl",
        paper_trade_count_provider: Callable[[], int] | None = None,
    ) -> None:
        self.path = Path(diagnostics_path)
        self.paper_trade_count_provider = paper_trade_count_provider or _paper_trade_count

    def records(self) -> tuple[dict[str, Any], ...]:
        if not self.path.exists(): return ()
        records = []
        try: lines = self.path.read_text(encoding="utf-8").splitlines()
        except OSError: return ()
        for line in lines:
            try:
                value = json.loads(line)
                if isinstance(value, dict): records.append(value)
            except json.JSONDecodeError:
                continue
        return tuple(records)

    def confidence_distribution(self) -> DistributionResult:
        return self._distribution("highest_confidence", "confidence")

    def setup_quality_distribution(self) -> DistributionResult:
        return self._distribution("highest_setup_quality", "setup quality")

    def score_distribution(self) -> DistributionResult:
        return self._distribution("overall_score", "overall score")

    def rejection_waterfall(self) -> RejectionWaterfallResult:
        completed = self._completed()
        rejected = [item for item in completed if not item.get("candidate_created", False)]
        counts = Counter(reason for item in rejected for reason in item.get("blocked_reasons", ()))
        ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        reasons = tuple(RejectionWaterfallItem(reason, count, _percent(count, len(completed)), index + 1)
                        for index, (reason, count) in enumerate(ordered))
        top = reasons[0].reason if reasons else "none"
        return RejectionWaterfallResult(
            len(completed), len(rejected), reasons,
            f"Rejection reasons overlap by design; {top} is the largest observed blocker across {len(completed)} completed analyses.",
        )

    def conversion_funnel(self) -> ConversionFunnel:
        records = self.records(); completed = [item for item in records if item.get("analysis_completed", False)]
        rejected = [item for item in completed if not item.get("candidate_created", False)]
        reason_sets = [set(item.get("blocked_reasons", ())) for item in rejected]
        count = lambda *names: sum(bool(set(names) & reasons) for reasons in reason_sets)
        near = self.near_miss_summary()
        candidates = sum(bool(item.get("candidate_created", False)) for item in completed)
        return ConversionFunnel(
            markets_analyzed=len(records), analysis_completed=len(completed), candidate_created=candidates,
            duplicate_candidate=count("duplicate_candidate"),
            blocked_by_confidence=count("directional_confidence", "confidence_threshold"),
            blocked_by_htf_alignment=count("higher_timeframe_alignment", "trend_conflict"),
            blocked_by_structure=count("structure_alignment"),
            blocked_by_setup_quality=count("minimum_setup_quality", "insufficient_confirmation"),
            blocked_by_execution=count("execution_intelligence", "execution_cost"),
            blocked_by_risk=count("risk_filter"), blocked_by_score=count("score_threshold"),
            near_misses=near.near_miss_count, paper_trades_opened=int(self.paper_trade_count_provider() or 0),
            human_readable_summary=f"{len(completed)} analyses completed and {candidates} became candidates; blocker stages overlap when one market fails multiple rules.",
        )

    def by_symbol(self) -> GroupAnalyticsResult:
        groups = _group(self._completed(), "symbol")
        rows = []
        for name, items in groups.items():
            candidates = sum(bool(item.get("candidate_created")) for item in items)
            reasons = _reason_counts(items)
            rows.append(SymbolAnalytics(
                name, len(items), candidates, _percent(candidates, len(items)),
                _average(items, "highest_confidence"), _average(items, "highest_setup_quality"),
                _average(items, "overall_score"), _maximum(items, "highest_confidence"),
                _maximum(items, "highest_setup_quality"), _maximum(items, "overall_score"),
                reasons[0][0] if reasons else None, sum(_is_near_miss(item) for item in items),
            ))
        rows.sort(key=lambda item: (-item.candidate_rate_percent, -item.markets_analyzed, item.symbol))
        return GroupAnalyticsResult("symbol", tuple(rows), f"Symbol analytics cover {len(rows)} symbols; rows are ranked by candidate conversion rate.")

    def by_strategy(self) -> GroupAnalyticsResult: return self._category("best_strategy", "strategy")
    def by_regime(self) -> GroupAnalyticsResult: return self._category("market_regime", "regime")

    def near_miss_summary(self) -> NearMissSummary:
        misses = [item for item in self._completed() if _is_near_miss(item)]
        misses.sort(key=lambda item: (_total_shortfall(item), -_number(item, "overall_score"), str(item.get("timestamp", ""))))
        return NearMissSummary(
            closest_missed_candidate=misses[0] if misses else None, near_miss_count=len(misses),
            average_distance_to_confidence_threshold=_distance_average(misses, "directional_confidence"),
            average_distance_to_quality_threshold=_distance_average(misses, "setup_quality_reference"),
            average_distance_to_score_threshold=_distance_average(misses, "overall_score_reference"),
        )

    def summary(self) -> CalibrationAnalyticsSummary:
        completed = self._completed(); candidates = sum(bool(item.get("candidate_created")) for item in completed)
        waterfall = self.rejection_waterfall(); near = self.near_miss_summary()
        symbols = self.by_symbol().groups; regimes = self.by_regime().groups
        best = symbols[0].symbol if symbols else None
        weakest = min(symbols, key=lambda item: (item.average_score, -item.markets_analyzed)).symbol if symbols else None
        regime = max(regimes, key=lambda item: item.count).name if regimes else None
        confidence = self.confidence_distribution(); quality = self.setup_quality_distribution(); score = self.score_distribution()
        top = waterfall.reasons[0].reason if waterfall.reasons else None
        rate = _percent(candidates, len(completed))
        return CalibrationAnalyticsSummary(
            len(completed), candidates, rate, confidence.human_readable_summary,
            quality.human_readable_summary, score.human_readable_summary, top,
            near.closest_missed_candidate, near.near_miss_count,
            near.average_distance_to_confidence_threshold, near.average_distance_to_quality_threshold,
            near.average_distance_to_score_threshold, best, weakest, regime,
            f"Candidate conversion is {rate:.2f}%; {top or 'no rejection reason'} is the leading blocker. Review distributions and sample sizes before considering any threshold study.",
        )

    def readable(self) -> bool:
        return not self.path.exists() or self.path.is_file()

    def _completed(self): return [item for item in self.records() if item.get("analysis_completed", False)]

    def _distribution(self, field: str, label: str) -> DistributionResult:
        records = self._completed(); counts = [0] * 10
        for item in records:
            value = max(0.0, min(100.0, _number(item, field)))
            index = min(int(value // 10), 9); counts[index] += 1
        buckets = tuple(DistributionBucket(f"{i * 10}-{(i + 1) * 10}", i * 10, (i + 1) * 10,
                                             count, _percent(count, len(records))) for i, count in enumerate(counts))
        dominant = max(buckets, key=lambda item: item.count).bucket if records else "none"
        return DistributionResult(label.replace(" ", "_"), len(records), buckets,
                                  f"{label.title()} distribution contains {len(records)} completed analyses; the largest bucket is {dominant}.")

    def _category(self, field: str, dimension: str) -> GroupAnalyticsResult:
        rows = []
        for name, items in _group(self._completed(), field).items():
            candidates = sum(bool(item.get("candidate_created")) for item in items)
            rows.append(CategoryAnalytics(name, len(items), candidates, len(items) - candidates,
                _percent(candidates, len(items)), _average(items, "highest_confidence"),
                _average(items, "highest_setup_quality"), _average(items, "overall_score"),
                tuple(_reason_counts(items)[:5])))
        rows.sort(key=lambda item: (-item.candidate_rate_percent, -item.count, item.name))
        return GroupAnalyticsResult(dimension, tuple(rows), f"{dimension.title()} analytics cover {len(rows)} observed categories and remain descriptive only.")


def _group(records, field):
    groups = defaultdict(list)
    for item in records: groups[str(item.get(field) or "unknown")].append(item)
    return dict(groups)
def _number(item, field):
    try: return float(item.get(field, 0.0) or 0.0)
    except (TypeError, ValueError): return 0.0
def _average(items, field): return round(sum(_number(item, field) for item in items) / len(items), 2) if items else 0.0
def _maximum(items, field): return round(max((_number(item, field) for item in items), default=0.0), 2)
def _percent(value, total): return round(value / total * 100, 2) if total else 0.0
def _reason_counts(items): return sorted(Counter(reason for item in items if not item.get("candidate_created") for reason in item.get("blocked_reasons", ())).items(), key=lambda pair: (-pair[1], pair[0]))
def _distances(item): return item.get("distance_to_candidate", ()) or ()
def _total_shortfall(item): return round(sum(max(0.0, -float(distance.get("distance", 0.0))) for distance in _distances(item)), 4)
def _is_near_miss(item): return bool(item.get("analysis_completed") and not item.get("candidate_created") and _distances(item) and _total_shortfall(item) <= 15.0)
def _distance_average(items, metric):
    values = [float(distance.get("distance", 0.0)) for item in items for distance in _distances(item) if distance.get("metric") == metric]
    return round(sum(values) / len(values), 2) if values else None
def _paper_trade_count():
    try:
        from core.paper_brokerage import current_paper_brokerage
        broker = current_paper_brokerage()
        return len(broker.open_positions()) + len(broker.closed_trades()) if broker else 0
    except Exception: return 0


_GLOBAL_ENGINE: CalibrationAnalyticsEngine | None = None
_GLOBAL_LOCK = threading.RLock()
def get_global_calibration_analytics() -> CalibrationAnalyticsEngine:
    global _GLOBAL_ENGINE
    with _GLOBAL_LOCK:
        if _GLOBAL_ENGINE is None: _GLOBAL_ENGINE = CalibrationAnalyticsEngine()
        return _GLOBAL_ENGINE
def current_calibration_analytics() -> CalibrationAnalyticsEngine | None: return _GLOBAL_ENGINE
def reset_global_calibration_analytics() -> None:
    global _GLOBAL_ENGINE
    with _GLOBAL_LOCK: _GLOBAL_ENGINE = None
