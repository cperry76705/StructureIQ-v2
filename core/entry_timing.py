"""Deterministic alternative entry timing for calibration research only."""

from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from core.market_data import Candle


class EntryModel(str, Enum):
    IMMEDIATE = "immediate"
    NEXT_BAR_OPEN = "next_bar_open"
    SIGNAL_CLOSE = "signal_close"
    MIDPOINT_ENTRY_STOP = "midpoint_between_entry_and_stop"
    MIDPOINT_ENTRY_TARGET = "midpoint_between_entry_and_target"
    QUARTER_PULLBACK_STOP = "quarter_pullback_from_entry_to_stop"
    QUARTER_PULLBACK_TARGET = "quarter_pullback_from_entry_to_target"
    RETEST_ENTRY = "retest_entry"
    CONSERVATIVE_LIMIT = "conservative_limit"


class EntryTimingProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=500)
    entry_model: EntryModel
    allow_missed_entries: bool = True
    max_wait_bars: int = Field(default=5, ge=1, le=100)
    require_touch: bool = False
    random_seed: int | None = None


@dataclass(frozen=True)
class PreparedEntryTiming:
    production_entry: float
    adjusted_entry: float | None
    evaluation_candles: tuple[Candle, ...]
    filled: bool
    missed: bool
    delay_bars: int
    fallback_used: bool
    entry_model_used: str
    human_readable_summary: str


@dataclass(frozen=True)
class EntryTimingDiagnostics:
    profile_name: str
    production_entry: float
    adjusted_entry: float | None
    filled: bool
    missed: bool
    delay_bars: int
    entry_improvement_r: float
    missed_opportunity_r: float
    fallback_used: bool
    human_readable_summary: str


class EntryTimingEngine:
    def __init__(self, profile: EntryTimingProfile) -> None:
        self.profile = profile

    def prepare(
        self,
        *,
        action: str,
        production_entry: float,
        stop_loss: float,
        target: float,
        signal_close: float | None,
        nearest_support: float | None,
        nearest_resistance: float | None,
        future_candles: list[Candle],
    ) -> PreparedEntryTiming:
        adjusted, fallback = self._desired_entry(
            action=action,
            entry=production_entry,
            stop=stop_loss,
            target=target,
            signal_close=signal_close,
            support=nearest_support,
            resistance=nearest_resistance,
        )
        if self.profile.entry_model is EntryModel.NEXT_BAR_OPEN:
            if future_candles:
                return self._filled(
                    production_entry,
                    future_candles[0].open,
                    future_candles,
                    delay=1,
                    fallback=fallback,
                )
            return self._miss_or_fallback(production_entry, future_candles, fallback)

        touch_required = self.profile.require_touch and self.profile.entry_model not in {
            EntryModel.IMMEDIATE,
            EntryModel.SIGNAL_CLOSE,
        }
        if not touch_required:
            return self._filled(
                production_entry,
                adjusted,
                future_candles,
                delay=0,
                fallback=fallback,
            )

        for index, candle in enumerate(future_candles[: self.profile.max_wait_bars]):
            if candle.low <= adjusted <= candle.high:
                return self._filled(
                    production_entry,
                    adjusted,
                    future_candles[index:],
                    delay=index + 1,
                    fallback=fallback,
                )
        return self._miss_or_fallback(production_entry, future_candles, fallback)

    def _desired_entry(
        self,
        *,
        action: str,
        entry: float,
        stop: float,
        target: float,
        signal_close: float | None,
        support: float | None,
        resistance: float | None,
    ) -> tuple[float, bool]:
        model = self.profile.entry_model
        if model in {EntryModel.IMMEDIATE, EntryModel.NEXT_BAR_OPEN}:
            return entry, False
        if model is EntryModel.SIGNAL_CLOSE:
            return (signal_close, False) if signal_close is not None else (entry, True)
        if model is EntryModel.MIDPOINT_ENTRY_STOP:
            return entry + 0.5 * (stop - entry), False
        if model is EntryModel.MIDPOINT_ENTRY_TARGET:
            return entry + 0.5 * (target - entry), False
        if model is EntryModel.QUARTER_PULLBACK_STOP:
            return entry + 0.25 * (stop - entry), False
        if model is EntryModel.QUARTER_PULLBACK_TARGET:
            return entry + 0.25 * (target - entry), False
        relevant = support if action == "buy" else resistance
        if model is EntryModel.RETEST_ENTRY:
            return (relevant, False) if relevant is not None else (entry, True)

        # Conservative limit prefers an improvement inside the original risk range.
        proposed = relevant
        if action == "buy":
            if proposed is None or not stop < proposed < entry:
                proposed = entry + 0.25 * (stop - entry)
        elif proposed is None or not entry < proposed < stop:
            proposed = entry + 0.25 * (stop - entry)
        return proposed, relevant is None

    def _filled(
        self,
        production_entry: float,
        adjusted_entry: float,
        candles: list[Candle],
        *,
        delay: int,
        fallback: bool,
    ) -> PreparedEntryTiming:
        return PreparedEntryTiming(
            production_entry=production_entry,
            adjusted_entry=adjusted_entry,
            evaluation_candles=tuple(candles),
            filled=True,
            missed=False,
            delay_bars=delay,
            fallback_used=fallback,
            entry_model_used=self.profile.entry_model.value,
            human_readable_summary=(
                f"{self.profile.name} filled at {adjusted_entry:.6f} after {delay} bars"
                + (" using the production-entry fallback." if fallback else ".")
            ),
        )

    def _miss_or_fallback(
        self,
        production_entry: float,
        future_candles: list[Candle],
        fallback: bool,
    ) -> PreparedEntryTiming:
        if not self.profile.allow_missed_entries:
            return self._filled(
                production_entry,
                production_entry,
                future_candles,
                delay=0,
                fallback=True,
            )
        return PreparedEntryTiming(
            production_entry=production_entry,
            adjusted_entry=None,
            evaluation_candles=(),
            filled=False,
            missed=True,
            delay_bars=self.profile.max_wait_bars,
            fallback_used=fallback,
            entry_model_used=self.profile.entry_model.value,
            human_readable_summary=(
                f"{self.profile.name} was not touched within "
                f"{self.profile.max_wait_bars} bars."
            ),
        )


def immediate_entry_timing_profile() -> EntryTimingProfile:
    return EntryTimingProfile(
        name="immediate",
        description="Existing production entry and timing.",
        entry_model=EntryModel.IMMEDIATE,
        allow_missed_entries=False,
        require_touch=False,
    )


def default_entry_timing_profiles() -> tuple[EntryTimingProfile, ...]:
    return (
        immediate_entry_timing_profile(),
        EntryTimingProfile(name="next_bar_open", description="Enter at the next candle open.", entry_model=EntryModel.NEXT_BAR_OPEN, allow_missed_entries=False),
        EntryTimingProfile(name="signal_close", description="Enter at the signal candle close.", entry_model=EntryModel.SIGNAL_CLOSE, allow_missed_entries=False),
        EntryTimingProfile(name="midpoint_entry_stop", description="Wait halfway toward the stop.", entry_model=EntryModel.MIDPOINT_ENTRY_STOP, require_touch=True),
        EntryTimingProfile(name="midpoint_entry_target", description="Enter halfway toward the target.", entry_model=EntryModel.MIDPOINT_ENTRY_TARGET, require_touch=True),
        EntryTimingProfile(name="quarter_pullback_stop", description="Wait 25% toward the stop.", entry_model=EntryModel.QUARTER_PULLBACK_STOP, require_touch=True),
        EntryTimingProfile(name="quarter_pullback_target", description="Enter 25% toward the target.", entry_model=EntryModel.QUARTER_PULLBACK_TARGET, require_touch=True),
        EntryTimingProfile(name="retest_entry", description="Use nearest relevant structural level.", entry_model=EntryModel.RETEST_ENTRY, require_touch=True),
        EntryTimingProfile(name="conservative_limit", description="Prefer an improved limit entry.", entry_model=EntryModel.CONSERVATIVE_LIMIT, require_touch=True),
    )
