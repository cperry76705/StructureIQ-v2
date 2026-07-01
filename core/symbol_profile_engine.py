"""Persistent, research-only symbol behavior profiles from calibration history."""

import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from math import sqrt
from pathlib import Path
from statistics import mean
from threading import RLock
from typing import Callable

from core.strategy_rating_engine import StrategyRatingEngine


MARKET_CHARACTERS = (
    "trending",
    "mean_reverting",
    "range_bound",
    "high_volatility",
    "low_volatility",
    "liquidity_sweep_heavy",
    "momentum_driven",
    "false_breakout_prone",
    "mixed",
    "insufficient_data",
)


@dataclass(frozen=True)
class SymbolCategoryRanking:
    name: str
    grade: str
    rating_score: float
    sample_size: int
    win_rate: float
    expectancy: float
    average_r: float
    total_r: float
    profit_factor: float | None
    max_drawdown: float


@dataclass(frozen=True)
class SymbolProfile:
    symbol: str
    total_trades: int
    wins: int
    losses: int
    win_rate: float
    expectancy: float
    average_r: float
    total_r: float
    profit_factor: float | None
    max_drawdown: float
    confidence: float
    sample_size: int
    market_character: str
    preferred_strategy: str | None
    preferred_setup: str | None
    strategy_grade: str | None
    setup_grade: str | None
    last_updated: str
    strategy_rankings: tuple[SymbolCategoryRanking, ...]
    setup_rankings: tuple[SymbolCategoryRanking, ...]


@dataclass(frozen=True)
class SymbolProfileView:
    status: str
    symbol: str
    market_character: str
    preferred_strategy: str | None
    preferred_setup: str | None
    strategy_grade: str | None
    setup_grade: str | None
    confidence: float
    sample_size: int
    warning: str | None


@dataclass(frozen=True)
class SymbolProfileSummary:
    profiles: tuple[SymbolProfile, ...]
    updated_symbols: tuple[str, ...]
    total_profiles: int
    human_readable_summary: str


@dataclass(frozen=True)
class _Observation:
    timestamp: int
    symbol: str
    outcome: str
    realized_r: float
    confidence: float
    strategy: str
    setup: str
    regime: str


@dataclass(frozen=True)
class _Interval:
    lower: float
    upper: float
    confidence_level: float
    sample_size: int


@dataclass(frozen=True)
class _PerformanceRow:
    category: str
    records_seen: int
    executed_trades: int
    win_rate: float
    average_r: float
    total_r: float
    expectancy: float
    profit_factor: float | None
    max_drawdown: float
    confidence_interval: _Interval
    statistical_significance_score: float
    sample_quality: str


@dataclass(frozen=True)
class _ResearchSummary:
    strategy_performance: tuple[_PerformanceRow, ...]
    setup_performance: tuple[_PerformanceRow, ...]


class SymbolProfileEngine:
    """Merge completed calibration observations into durable symbol research."""

    def __init__(
        self,
        path: str | Path | None = "research/symbol_profiles.json",
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.path = Path(path) if path is not None else None
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock = RLock()
        self._observations = self._load()

    def update(self, trades) -> SymbolProfileSummary:
        observations = [_observation(trade) for trade in trades]
        completed = [item for item in observations if item is not None]
        with self._lock:
            self._observations.extend(completed)
            self._persist()
            symbols = tuple(sorted({item.symbol for item in completed}))
            profiles = self.list_profiles()
        return SymbolProfileSummary(
            profiles=profiles,
            updated_symbols=symbols,
            total_profiles=len(profiles),
            human_readable_summary=(
                f"Symbol profiles contain {len(self._observations)} completed historical "
                f"trades across {len(profiles)} symbols; updated {len(symbols)} symbols."
            ),
        )

    def get_profile(self, symbol: str) -> SymbolProfile | None:
        normalized = symbol.strip().upper()
        with self._lock:
            records = [item for item in self._observations if item.symbol == normalized]
            return self._build_profile(normalized, records) if records else None

    def get_view(self, symbol: str) -> SymbolProfileView:
        profile = self.get_profile(symbol)
        normalized = symbol.strip().upper()
        if profile is None or profile.sample_size < 20:
            return SymbolProfileView(
                status="unavailable",
                symbol=normalized,
                market_character="insufficient_data",
                preferred_strategy=None,
                preferred_setup=None,
                strategy_grade=None,
                setup_grade=None,
                confidence=profile.confidence if profile else 0.0,
                sample_size=profile.sample_size if profile else 0,
                warning="Not enough historical calibration data.",
            )
        return SymbolProfileView(
            status="available",
            symbol=profile.symbol,
            market_character=profile.market_character,
            preferred_strategy=profile.preferred_strategy,
            preferred_setup=profile.preferred_setup,
            strategy_grade=profile.strategy_grade,
            setup_grade=profile.setup_grade,
            confidence=profile.confidence,
            sample_size=profile.sample_size,
            warning=(
                "Market character requires at least 30 trades."
                if profile.market_character == "insufficient_data" else None
            ),
        )

    def list_profiles(self) -> tuple[SymbolProfile, ...]:
        symbols = sorted({item.symbol for item in self._observations})
        return tuple(
            self._build_profile(
                symbol, [item for item in self._observations if item.symbol == symbol]
            )
            for symbol in symbols
        )

    def _build_profile(self, symbol, records):
        returns = [item.realized_r for item in records]
        wins = sum(item.outcome == "win" for item in records)
        losses = sum(item.outcome == "loss" for item in records)
        strategy_rows = _performance_rows(records, "strategy")
        setup_rows = _performance_rows(records, "setup")
        rating = StrategyRatingEngine().rate(
            research_lab_summary=_ResearchSummary(strategy_rows, setup_rows)
        )
        strategy_rankings = tuple(_ranking(item) for item in rating.strategy_grades)
        setup_rankings = tuple(_ranking(item) for item in rating.setup_grades)
        preferred_strategy = _preferred(strategy_rankings)
        preferred_setup = _preferred(setup_rankings)
        strategy_grade = _grade_for(strategy_rankings, preferred_strategy)
        setup_grade = _grade_for(setup_rankings, preferred_setup)
        character, dominance = _market_character(records)
        confidence = min(
            100.0,
            50.0 + min(30.0, len(records) / 10.0) + dominance * 0.20,
        )
        if len(records) < 30 or confidence < 60:
            character = "insufficient_data"
        return SymbolProfile(
            symbol=symbol,
            total_trades=len(records),
            wins=wins,
            losses=losses,
            win_rate=round(wins / len(records) * 100.0 if records else 0.0, 3),
            expectancy=round(mean(returns), 6) if returns else 0.0,
            average_r=round(mean(returns), 6) if returns else 0.0,
            total_r=round(sum(returns), 6),
            profit_factor=_profit_factor(returns),
            max_drawdown=_max_drawdown(returns),
            confidence=round(confidence, 3),
            sample_size=len(records),
            market_character=character,
            preferred_strategy=preferred_strategy,
            preferred_setup=preferred_setup,
            strategy_grade=strategy_grade,
            setup_grade=setup_grade,
            last_updated=self._clock().astimezone(timezone.utc).isoformat(),
            strategy_rankings=strategy_rankings,
            setup_rankings=setup_rankings,
        )

    def _load(self):
        if self.path is None or not self.path.exists():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            return [_Observation(**item) for item in payload.get("observations", [])]
        except (OSError, ValueError, TypeError):
            return []

    def _persist(self):
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"observations": [asdict(item) for item in self._observations]}
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
        temporary.replace(self.path)


_GLOBAL_SYMBOL_PROFILE_ENGINE = SymbolProfileEngine()


def get_global_symbol_profile_engine() -> SymbolProfileEngine:
    return _GLOBAL_SYMBOL_PROFILE_ENGINE


def _observation(trade):
    outcome = _value(getattr(trade, "outcome", "unknown"))
    realized = getattr(trade, "realized_r", None)
    if outcome not in {"win", "loss", "breakeven"} or realized is None:
        return None
    diagnostics = getattr(trade, "decision_diagnostics", None)
    regime = getattr(trade, "market_regime", None)
    return _Observation(
        timestamp=int(getattr(trade, "timestamp", 0)),
        symbol=str(getattr(trade, "symbol", "UNKNOWN")).strip().upper(),
        outcome=outcome,
        realized_r=float(realized),
        confidence=float(getattr(diagnostics, "final_confidence", 0.0)),
        strategy=str(getattr(trade, "strategy_type", "no_strategy")),
        setup=str(getattr(trade, "setup_type", "no_valid_setup")),
        regime=(
            _value(getattr(regime, "market_regime", "unknown"))
            if regime is not None else "unknown"
        ),
    )


def _performance_rows(records, attribute):
    groups: dict[str, list[_Observation]] = {}
    for item in records:
        groups.setdefault(getattr(item, attribute), []).append(item)
    return tuple(_performance_row(name, group) for name, group in sorted(groups.items()))


def _performance_row(name, records):
    returns = [item.realized_r for item in records]
    average = mean(returns)
    deviation = sqrt(sum((value - average) ** 2 for value in returns) / len(returns)) if len(returns) > 1 else 0.0
    margin = 1.96 * deviation / sqrt(len(returns)) if returns else 0.0
    sample = len(records)
    return _PerformanceRow(
        category=name,
        records_seen=sample,
        executed_trades=sample,
        win_rate=round(sum(item.outcome == "win" for item in records) / sample * 100.0, 3),
        average_r=round(average, 6),
        total_r=round(sum(returns), 6),
        expectancy=round(average, 6),
        profit_factor=_profit_factor(returns),
        max_drawdown=_max_drawdown(returns),
        confidence_interval=_Interval(
            round(average - margin, 6), round(average + margin, 6), 0.95, sample
        ),
        statistical_significance_score=round(min(100.0, sample / 100 * 100), 3),
        sample_quality=(
            "high" if sample >= 50 else "moderate" if sample >= 20
            else "low" if sample >= 5 else "insufficient"
        ),
    )


def _market_character(records):
    regimes = Counter(item.regime for item in records)
    strategies = Counter(item.strategy for item in records)
    setups = Counter(item.setup for item in records)
    total = len(records)
    candidates = {
        "trending": sum(regimes[name] for name in ("strong_bull_trend", "weak_bull_trend", "strong_bear_trend", "weak_bear_trend")),
        "range_bound": regimes["range"],
        "high_volatility": regimes["high_volatility"],
        "low_volatility": regimes["low_volatility"],
        "liquidity_sweep_heavy": sum(count for name, count in setups.items() if "liquidity_sweep" in name),
        "momentum_driven": strategies["trend_continuation"] + strategies["breakout_continuation"] + regimes["expansion"],
        "mean_reverting": strategies["mean_reversion"] + strategies["range_reversal"],
    }
    breakout = [item for item in records if "breakout" in item.strategy or "bos_retest" in item.setup]
    if len(breakout) >= 10:
        failed = sum(item.outcome == "loss" for item in breakout)
        candidates["false_breakout_prone"] = failed if failed / len(breakout) >= 0.6 else 0
    name, count = max(candidates.items(), key=lambda item: (item[1], item[0]))
    dominance = count / total * 100.0 if total else 0.0
    if count == 0:
        return "mixed", 50.0
    second = sorted(candidates.values(), reverse=True)[1]
    if second >= count * 0.85:
        return "mixed", max(50.0, dominance)
    return name, dominance


def _preferred(rankings):
    eligible = [
        item for item in rankings
        if item.sample_size >= 20
        and item.expectancy > 0
        and (item.profit_factor is None or item.profit_factor >= 1)
    ]
    if not eligible:
        return None
    return max(eligible, key=lambda item: (item.rating_score, item.expectancy, item.sample_size)).name


def _ranking(item):
    return SymbolCategoryRanking(
        name=item.name,
        grade=item.grade.value,
        rating_score=item.rating_score,
        sample_size=item.sample_size,
        win_rate=item.win_rate,
        expectancy=item.expectancy,
        average_r=item.average_r,
        total_r=item.total_r,
        profit_factor=item.profit_factor,
        max_drawdown=item.max_drawdown,
    )


def _grade_for(rankings, name):
    return next((item.grade for item in rankings if item.name == name), None)


def _profit_factor(returns):
    gains = sum(value for value in returns if value > 0)
    losses = -sum(value for value in returns if value < 0)
    return round(gains / losses, 6) if losses else None


def _max_drawdown(returns):
    total = peak = drawdown = 0.0
    for value in returns:
        total += value
        peak = max(peak, total)
        drawdown = max(drawdown, peak - total)
    return round(drawdown, 6)


def _value(value):
    return str(getattr(value, "value", value))
