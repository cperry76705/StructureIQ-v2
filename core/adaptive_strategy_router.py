"""Research-only comparison of production routes with persisted symbol intelligence."""

from collections import Counter
from dataclasses import dataclass
from typing import Any, Literal

from core.symbol_profile_engine import SymbolCategoryRanking, SymbolProfile


RoutingAlignment = Literal["aligned", "partially_aligned", "misaligned", "unavailable"]
RouterStatus = Literal["available", "unavailable", "insufficient_sample", "no_trade"]


@dataclass(frozen=True)
class AdaptiveCandidateRanking:
    category_type: Literal["strategy", "setup"]
    name: str
    grade: str
    rating_score: float
    sample_size: int
    is_profile_preferred: bool
    is_production_selected: bool


@dataclass(frozen=True)
class AdaptiveStrategyRouterResult:
    adaptive_strategy_router: str
    status: RouterStatus
    production_strategy: str | None
    profile_preferred_strategy: str | None
    production_setup: str | None
    profile_preferred_setup: str | None
    routing_alignment: RoutingAlignment
    adaptive_candidate_rankings: tuple[AdaptiveCandidateRanking, ...]
    route_confidence: float
    sample_size: int
    warnings: tuple[str, ...]
    human_readable_summary: str


@dataclass(frozen=True)
class AggregateAdaptiveStrategyRouterSummary:
    aligned_count: int
    partially_aligned_count: int
    misaligned_count: int
    unavailable_count: int
    most_common_misalignment: str | None
    strongest_profile_preferred_strategy: str | None
    strongest_profile_preferred_setup: str | None
    human_readable_summary: str


def _value(value: Any) -> str | None:
    if value is None:
        return None
    raw = getattr(value, "value", value)
    return str(raw)


def _candidate_rows(
    category_type: Literal["strategy", "setup"],
    rows: tuple[SymbolCategoryRanking, ...],
    preferred: str | None,
    production: str | None,
) -> tuple[AdaptiveCandidateRanking, ...]:
    return tuple(
        AdaptiveCandidateRanking(
            category_type=category_type,
            name=row.name,
            grade=row.grade,
            rating_score=row.rating_score,
            sample_size=row.sample_size,
            is_profile_preferred=row.name == preferred,
            is_production_selected=row.name == production,
        )
        for row in rows
    )


class AdaptiveStrategyRouterEngine:
    """Compare routes without selecting, promoting, or executing a strategy."""

    def analyze(
        self,
        *,
        symbol: str,
        production_setup: Any,
        production_strategy: Any,
        action: Any,
        score_summary: Any = None,
        execution_intelligence: Any = None,
        symbol_profile: SymbolProfile | None,
        strategy_rating_summary: Any = None,
        setup_rating_summary: Any = None,
    ) -> AdaptiveStrategyRouterResult:
        del score_summary, execution_intelligence, strategy_rating_summary, setup_rating_summary
        strategy = _value(production_strategy)
        setup = _value(production_setup)
        action_value = _value(action)
        if symbol_profile is None:
            return self._unavailable(symbol, strategy, setup)

        preferred_strategy = symbol_profile.preferred_strategy
        preferred_setup = symbol_profile.preferred_setup
        candidates = (
            *_candidate_rows(
                "strategy", symbol_profile.strategy_rankings, preferred_strategy, strategy
            ),
            *_candidate_rows("setup", symbol_profile.setup_rankings, preferred_setup, setup),
        )
        if action_value in {"avoid", "no_trade"}:
            return AdaptiveStrategyRouterResult(
                adaptive_strategy_router="diagnostic_only",
                status="no_trade",
                production_strategy=strategy,
                profile_preferred_strategy=preferred_strategy,
                production_setup=setup,
                profile_preferred_setup=preferred_setup,
                routing_alignment="unavailable",
                adaptive_candidate_rankings=tuple(candidates),
                route_confidence=0.0,
                sample_size=symbol_profile.sample_size,
                warnings=("No execution route is suggested for an avoid/no-trade action.",),
                human_readable_summary=(
                    f"{symbol} is not actionable; historical route preferences are "
                    "shown for research only and do not suggest execution."
                ),
            )

        preferred_rows = [row for row in candidates if row.is_profile_preferred]
        low_sample = [row for row in preferred_rows if row.sample_size < 20]
        if not preferred_strategy or not preferred_setup:
            return self._unavailable(symbol, strategy, setup, symbol_profile, tuple(candidates))
        if low_sample:
            names = ", ".join(row.name for row in low_sample)
            return AdaptiveStrategyRouterResult(
                adaptive_strategy_router="diagnostic_only",
                status="insufficient_sample",
                production_strategy=strategy,
                profile_preferred_strategy=preferred_strategy,
                production_setup=setup,
                profile_preferred_setup=preferred_setup,
                routing_alignment="unavailable",
                adaptive_candidate_rankings=tuple(candidates),
                route_confidence=0.0,
                sample_size=symbol_profile.sample_size,
                warnings=(f"Preferred route has fewer than 20 trades: {names}.",),
                human_readable_summary=(
                    f"{symbol} has a historical preference, but its route sample is "
                    "too small for an alignment judgment."
                ),
            )

        if strategy == preferred_strategy:
            alignment: RoutingAlignment = "aligned"
        elif setup == preferred_setup:
            alignment = "partially_aligned"
        else:
            alignment = "misaligned"
        confidence = round(min(100.0, max(0.0, symbol_profile.confidence)), 2)
        return AdaptiveStrategyRouterResult(
            adaptive_strategy_router="diagnostic_only",
            status="available",
            production_strategy=strategy,
            profile_preferred_strategy=preferred_strategy,
            production_setup=setup,
            profile_preferred_setup=preferred_setup,
            routing_alignment=alignment,
            adaptive_candidate_rankings=tuple(candidates),
            route_confidence=confidence,
            sample_size=symbol_profile.sample_size,
            warnings=("Diagnostic only; the production route remains unchanged.",),
            human_readable_summary=(
                f"The production route is {alignment.replace('_', ' ')} with {symbol}'s "
                "historical profile. This comparison does not override production routing."
            ),
        )

    def summarize(
        self, results: tuple[AdaptiveStrategyRouterResult, ...]
    ) -> AggregateAdaptiveStrategyRouterSummary:
        counts = Counter(result.routing_alignment for result in results)
        mismatches = Counter(
            f"{result.production_strategy} -> {result.profile_preferred_strategy}"
            for result in results
            if result.routing_alignment == "misaligned"
        )
        strategies = Counter(
            result.profile_preferred_strategy
            for result in results
            if result.profile_preferred_strategy
        )
        setups = Counter(
            result.profile_preferred_setup
            for result in results
            if result.profile_preferred_setup
        )
        unavailable = counts["unavailable"]
        return AggregateAdaptiveStrategyRouterSummary(
            aligned_count=counts["aligned"],
            partially_aligned_count=counts["partially_aligned"],
            misaligned_count=counts["misaligned"],
            unavailable_count=unavailable,
            most_common_misalignment=mismatches.most_common(1)[0][0] if mismatches else None,
            strongest_profile_preferred_strategy=(
                strategies.most_common(1)[0][0] if strategies else None
            ),
            strongest_profile_preferred_setup=setups.most_common(1)[0][0] if setups else None,
            human_readable_summary=(
                f"Adaptive route diagnostics found {counts['aligned']} aligned, "
                f"{counts['partially_aligned']} partially aligned, "
                f"{counts['misaligned']} misaligned, and {unavailable} unavailable records. "
                "Production routing was not changed."
            ),
        )

    @staticmethod
    def _unavailable(
        symbol: str,
        strategy: str | None,
        setup: str | None,
        profile: SymbolProfile | None = None,
        candidates: tuple[AdaptiveCandidateRanking, ...] = (),
    ) -> AdaptiveStrategyRouterResult:
        return AdaptiveStrategyRouterResult(
            adaptive_strategy_router="diagnostic_only",
            status="unavailable",
            production_strategy=strategy,
            profile_preferred_strategy=profile.preferred_strategy if profile else None,
            production_setup=setup,
            profile_preferred_setup=profile.preferred_setup if profile else None,
            routing_alignment="unavailable",
            adaptive_candidate_rankings=candidates,
            route_confidence=0.0,
            sample_size=profile.sample_size if profile else 0,
            warnings=("Not enough historical symbol-profile data.",),
            human_readable_summary=(
                f"Adaptive route diagnostics are unavailable for {symbol} because "
                "historical profile evidence is insufficient."
            ),
        )
