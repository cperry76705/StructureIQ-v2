"""Continuous, read-only research snapshots over completed calibration records."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from threading import RLock
from typing import Callable

from pydantic import BaseModel, Field, model_validator

from core.backtesting import BacktestTrade
from core.journal import TradeOutcome
from core.research_lab import (
    ResearchConfidenceInterval,
    ResearchPerformance,
    build_research_lab,
    calculate_research_performance,
)


class ResearchWindow(str, Enum):
    LAST_250 = "last_250"
    LAST_500 = "last_500"
    LAST_1000 = "last_1000"
    ALL_TIME = "all_time"
    CUSTOM = "custom"


class ResearchRefreshRequest(BaseModel):
    window: ResearchWindow = ResearchWindow.ALL_TIME
    custom_lookback: int | None = Field(default=None, ge=1, le=100_000)

    @model_validator(mode="after")
    def validate_custom_lookback(self) -> "ResearchRefreshRequest":
        if self.window is ResearchWindow.CUSTOM and self.custom_lookback is None:
            raise ValueError("custom_lookback is required when window is custom")
        return self


@dataclass(frozen=True)
class ContinuousResearchPerformance:
    dimension: str
    category: str
    records_seen: int
    executed_trades: int
    wins: int
    losses: int
    win_rate: float
    average_r: float
    total_r: float
    expectancy: float
    profit_factor: float | None
    max_drawdown: float
    average_mfe: float
    average_mae: float
    confidence_interval: ResearchConfidenceInterval
    sample_quality: str
    last_updated: str


@dataclass(frozen=True)
class ResearchCombination:
    symbol: str
    timeframe: str
    setup: str
    strategy: str
    market_regime: str
    confidence_bucket: str
    hour_of_day: str
    day_of_week: str
    performance: ContinuousResearchPerformance


@dataclass(frozen=True)
class DimensionRanking:
    dimension: str
    strongest: tuple[ContinuousResearchPerformance, ...]
    weakest: tuple[ContinuousResearchPerformance, ...]


@dataclass(frozen=True)
class ContinuousResearchRankings:
    window: ResearchWindow
    custom_lookback: int | None
    rankings: tuple[DimensionRanking, ...]
    last_updated: str


@dataclass(frozen=True)
class ContinuousResearchStatus:
    window: ResearchWindow
    custom_lookback: int | None
    records_seen: int
    executed_trades: int
    best_symbol: str | None
    best_timeframe: str | None
    best_setup: str | None
    best_strategy: str | None
    best_market_regime: str | None
    best_confidence_bucket: str | None
    best_hour_of_day: str | None
    best_day_of_week: str | None
    best_setup_regime_combination: str | None
    best_symbol_setup_combination: str | None
    best_timeframe_setup_combination: str | None
    insufficient_sample_warnings: tuple[str, ...]
    overfitting_warnings: tuple[str, ...]
    latest_research_status_statement: str
    last_updated: str


@dataclass(frozen=True)
class ContinuousResearchSnapshot:
    status: ContinuousResearchStatus
    rankings: ContinuousResearchRankings
    best_combinations: tuple[ResearchCombination, ...]
    weakest_combinations: tuple[ResearchCombination, ...]


class ResearchEngine:
    """Maintain rolling research reports without modifying calibration records."""

    def __init__(self, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._records: list[BacktestTrade] = []
        self._snapshots: dict[tuple[ResearchWindow, int | None], ContinuousResearchSnapshot] = {}
        self._lock = RLock()

    def ingest(self, records: list[BacktestTrade]) -> ContinuousResearchStatus:
        """Append immutable calibration records and refresh all-time research."""

        with self._lock:
            self._records.extend(records)
            self._snapshots.clear()
            return self._build_snapshot(ResearchWindow.ALL_TIME, None).status

    def refresh(
        self,
        window: ResearchWindow = ResearchWindow.ALL_TIME,
        custom_lookback: int | None = None,
    ) -> ContinuousResearchStatus:
        with self._lock:
            key = self._key(window, custom_lookback)
            self._snapshots[key] = self._calculate(window, custom_lookback)
            return self._snapshots[key].status

    def snapshot(
        self,
        window: ResearchWindow = ResearchWindow.ALL_TIME,
        custom_lookback: int | None = None,
    ) -> ContinuousResearchSnapshot:
        with self._lock:
            key = self._key(window, custom_lookback)
            if key not in self._snapshots:
                self._snapshots[key] = self._calculate(window, custom_lookback)
            return self._snapshots[key]

    def clear(self) -> None:
        """Clear process-local research state; intended for tests and administration."""

        with self._lock:
            self._records.clear()
            self._snapshots.clear()

    @property
    def record_count(self) -> int:
        with self._lock:
            return len(self._records)

    def _build_snapshot(
        self, window: ResearchWindow, custom_lookback: int | None
    ) -> ContinuousResearchSnapshot:
        key = self._key(window, custom_lookback)
        snapshot = self._calculate(window, custom_lookback)
        self._snapshots[key] = snapshot
        return snapshot

    def _calculate(
        self, window: ResearchWindow, custom_lookback: int | None
    ) -> ContinuousResearchSnapshot:
        records = self._window_records(window, custom_lookback)
        updated = self._clock().astimezone(timezone.utc).isoformat()
        lab = build_research_lab(
            records,
            management_results=(),
            entry_timing_summary=None,
            execution_sensitivity_summary=None,
        )
        dimension_groups = _dimension_groups(records)
        rankings: list[DimensionRanking] = []
        best_by_dimension: dict[str, ContinuousResearchPerformance | None] = {}
        insufficient: list[str] = []
        for dimension, groups in dimension_groups.items():
            rows = [
                _continuous(
                    dimension,
                    calculate_research_performance(category, category_records),
                    updated,
                )
                for category, category_records in sorted(groups.items())
            ]
            active = [row for row in rows if row.executed_trades]
            strongest = tuple(sorted(active, key=_rank_key, reverse=True)[:10])
            weakest = tuple(sorted(active, key=_rank_key)[:10])
            rankings.append(DimensionRanking(dimension, strongest, weakest))
            best_by_dimension[dimension] = strongest[0] if strongest else None
            insufficient.extend(
                f"{dimension} {row.category} has only {row.executed_trades} closed trades."
                for row in active
                if row.sample_quality in {"insufficient", "low"}
            )

        combinations = _combinations(records, updated)
        active_combinations = [
            item for item in combinations if item.performance.executed_trades
        ]
        best_combinations = tuple(
            sorted(active_combinations, key=lambda item: _rank_key(item.performance), reverse=True)[:10]
        )
        weakest_combinations = tuple(
            sorted(active_combinations, key=lambda item: _rank_key(item.performance))[:10]
        )
        best_combo = best_combinations[0] if best_combinations else None
        setup_regime = _best_pair(records, "setup + regime", _setup, _regime, updated)
        symbol_setup = _best_pair(records, "symbol + setup", _symbol, _setup, updated)
        timeframe_setup = _best_pair(
            records, "timeframe + setup", _timeframe, _setup, updated
        )
        status = ContinuousResearchStatus(
            window=window,
            custom_lookback=custom_lookback,
            records_seen=len(records),
            executed_trades=sum(_closed(item) for item in records),
            best_symbol=_category(best_by_dimension.get("symbol")),
            best_timeframe=_category(best_by_dimension.get("timeframe")),
            best_setup=_category(best_by_dimension.get("setup")),
            best_strategy=_category(best_by_dimension.get("strategy")),
            best_market_regime=_category(best_by_dimension.get("market_regime")),
            best_confidence_bucket=_category(
                best_by_dimension.get("confidence_bucket")
            ),
            best_hour_of_day=_category(best_by_dimension.get("hour_of_day")),
            best_day_of_week=_category(best_by_dimension.get("day_of_week")),
            best_setup_regime_combination=_category(setup_regime),
            best_symbol_setup_combination=_category(symbol_setup),
            best_timeframe_setup_combination=_category(timeframe_setup),
            insufficient_sample_warnings=tuple(insufficient[:50]),
            overfitting_warnings=lab.research_statistics.possible_overfitting,
            latest_research_status_statement=_status_statement(best_combo),
            last_updated=updated,
        )
        return ContinuousResearchSnapshot(
            status=status,
            rankings=ContinuousResearchRankings(
                window=window,
                custom_lookback=custom_lookback,
                rankings=tuple(rankings),
                last_updated=updated,
            ),
            best_combinations=best_combinations,
            weakest_combinations=weakest_combinations,
        )

    def _window_records(
        self, window: ResearchWindow, custom_lookback: int | None
    ) -> list[BacktestTrade]:
        if window is ResearchWindow.ALL_TIME:
            return list(self._records)
        limits = {
            ResearchWindow.LAST_250: 250,
            ResearchWindow.LAST_500: 500,
            ResearchWindow.LAST_1000: 1000,
            ResearchWindow.CUSTOM: custom_lookback or 1,
        }
        closed = [item for item in self._records if _closed(item)]
        return closed[-limits[window] :]

    @staticmethod
    def _key(
        window: ResearchWindow, custom_lookback: int | None
    ) -> tuple[ResearchWindow, int | None]:
        if window is ResearchWindow.CUSTOM and custom_lookback is None:
            raise ValueError("custom_lookback is required for custom research windows")
        return window, custom_lookback if window is ResearchWindow.CUSTOM else None


_GLOBAL_RESEARCH_ENGINE = ResearchEngine()


def get_global_research_engine() -> ResearchEngine:
    return _GLOBAL_RESEARCH_ENGINE


def _dimension_groups(
    records: list[BacktestTrade],
) -> dict[str, dict[str, list[BacktestTrade]]]:
    keys = {
        "symbol": _symbol,
        "timeframe": _timeframe,
        "setup": _setup,
        "strategy": _strategy,
        "market_regime": _regime,
        "confidence_bucket": _confidence_bucket,
        "hour_of_day": _hour,
        "day_of_week": _day,
    }
    dimensions: dict[str, dict[str, list[BacktestTrade]]] = {}
    for dimension, key in keys.items():
        groups: dict[str, list[BacktestTrade]] = {}
        for record in records:
            groups.setdefault(key(record), []).append(record)
        dimensions[dimension] = groups
    return dimensions


def _combinations(
    records: list[BacktestTrade], updated: str
) -> list[ResearchCombination]:
    groups: dict[tuple[str, ...], list[BacktestTrade]] = {}
    for record in records:
        key = (
            _symbol(record),
            _timeframe(record),
            _setup(record),
            _strategy(record),
            _regime(record),
            _confidence_bucket(record),
            _hour(record),
            _day(record),
        )
        groups.setdefault(key, []).append(record)
    results: list[ResearchCombination] = []
    for key, group in sorted(groups.items()):
        category = " | ".join(key)
        results.append(
            ResearchCombination(
                symbol=key[0],
                timeframe=key[1],
                setup=key[2],
                strategy=key[3],
                market_regime=key[4],
                confidence_bucket=key[5],
                hour_of_day=key[6],
                day_of_week=key[7],
                performance=_continuous(
                    "full_combination",
                    calculate_research_performance(category, group),
                    updated,
                ),
            )
        )
    return results


def _best_pair(
    records: list[BacktestTrade],
    dimension: str,
    left,
    right,
    updated: str,
) -> ContinuousResearchPerformance | None:
    groups: dict[str, list[BacktestTrade]] = {}
    for record in records:
        category = f"{left(record)} + {right(record)}"
        groups.setdefault(category, []).append(record)
    rows = [
        _continuous(
            dimension,
            calculate_research_performance(category, group),
            updated,
        )
        for category, group in groups.items()
    ]
    active = [item for item in rows if item.executed_trades]
    return max(active, key=_rank_key) if active else None


def _continuous(
    dimension: str, row: ResearchPerformance, updated: str
) -> ContinuousResearchPerformance:
    return ContinuousResearchPerformance(
        dimension=dimension,
        category=row.category,
        records_seen=row.records_seen,
        executed_trades=row.executed_trades,
        wins=row.wins,
        losses=row.losses,
        win_rate=row.win_rate,
        average_r=row.average_r,
        total_r=row.total_r,
        expectancy=row.expectancy,
        profit_factor=row.profit_factor,
        max_drawdown=row.max_drawdown,
        average_mfe=row.average_mfe,
        average_mae=row.average_mae,
        confidence_interval=row.confidence_interval,
        sample_quality=row.sample_quality,
        last_updated=updated,
    )


def _rank_key(item: ContinuousResearchPerformance) -> tuple[float, int, float]:
    return item.expectancy, item.executed_trades, -item.max_drawdown


def _status_statement(combination: ResearchCombination | None) -> str:
    if combination is None:
        return "StructureIQ has no completed trades available for continuous research yet."
    performance = combination.performance
    return (
        f"StructureIQ currently performs best on {combination.symbol} "
        f"{combination.timeframe} using {combination.setup.replace('_', ' ')} "
        f"during {combination.market_regime.replace('_', ' ')} conditions, with "
        f"confidence {combination.confidence_bucket}, near {combination.hour_of_day}, "
        f"producing {performance.expectancy:.2f}R expectancy over "
        f"{performance.executed_trades} trades."
    )


def _symbol(item: BacktestTrade) -> str:
    return item.symbol


def _timeframe(item: BacktestTrade) -> str:
    return item.timeframe or "unknown"


def _setup(item: BacktestTrade) -> str:
    return item.setup_type


def _strategy(item: BacktestTrade) -> str:
    return item.strategy_type


def _regime(item: BacktestTrade) -> str:
    return (
        item.market_regime.market_regime.value
        if item.market_regime is not None else "unknown"
    )


def _confidence_bucket(item: BacktestTrade) -> str:
    if item.decision_diagnostics is None:
        return "unknown"
    confidence = item.decision_diagnostics.final_confidence
    lower = int(confidence // 10) * 10
    lower = max(0, min(90, lower))
    upper = 100 if lower == 90 else lower + 9
    return f"{lower}-{upper}"


def _eastern(item: BacktestTrade) -> datetime:
    utc_value = datetime.fromtimestamp(item.timestamp, tz=timezone.utc)
    offset = -4 if _is_us_eastern_daylight_time(utc_value) else -5
    return utc_value.astimezone(timezone(timedelta(hours=offset), name="ET"))


def _is_us_eastern_daylight_time(value: datetime) -> bool:
    """Apply current US Eastern DST rules without an optional tzdata package."""

    year = value.year
    march_first = datetime(year, 3, 1, tzinfo=timezone.utc)
    first_sunday_march = 1 + (6 - march_first.weekday()) % 7
    second_sunday_march = first_sunday_march + 7
    november_first = datetime(year, 11, 1, tzinfo=timezone.utc)
    first_sunday_november = 1 + (6 - november_first.weekday()) % 7
    # US transitions occur at 02:00 local: 07:00 UTC in March and
    # 06:00 UTC in November.
    starts = datetime(year, 3, second_sunday_march, 7, tzinfo=timezone.utc)
    ends = datetime(year, 11, first_sunday_november, 6, tzinfo=timezone.utc)
    return starts <= value < ends


def _hour(item: BacktestTrade) -> str:
    return f"{_eastern(item).hour:02d}:00 ET"


def _day(item: BacktestTrade) -> str:
    return _eastern(item).strftime("%A")


def _closed(item: BacktestTrade) -> bool:
    return item.outcome in {
        TradeOutcome.WIN,
        TradeOutcome.LOSS,
        TradeOutcome.BREAKEVEN,
    }


def _category(
    item: ContinuousResearchPerformance | None,
) -> str | None:
    return item.category if item is not None else None
