"""Dedicated price-action market structure engine.

The engine uses confirmed fractal swings. A swing needs ``window`` closed candles on
both sides, so results intentionally lag the newest candles by that confirmation
window and never depend on the market-data provider.
"""

from dataclasses import dataclass
from typing import Literal

from core.market_data import Candle
from core.structure import SwingPoint, find_swings


Trend = Literal["bullish", "bearish", "ranging", "unclear"]
Phase = Literal["impulse", "pullback", "range", "reversal_attempt", "unclear"]
StructureEventType = Literal[
    "higher_high",
    "higher_low",
    "lower_high",
    "lower_low",
    "bullish_bos",
    "bearish_bos",
    "bullish_choch",
    "bearish_choch",
    "liquidity_sweep_high",
    "liquidity_sweep_low",
    "pullback",
    "trend_continuation",
]


@dataclass(frozen=True)
class StructureEvent:
    """A timestamped, explainable observation produced by the structure engine."""

    index: int
    timestamp: int
    type: StructureEventType
    price: float
    description: str
    reference_swing: SwingPoint | None = None


@dataclass(frozen=True)
class MarketStructureResult:
    """Complete v0.2 structural snapshot for one chronological candle series."""

    trend: Trend
    phase: Phase
    latest_swing_high: SwingPoint | None
    latest_swing_low: SwingPoint | None
    structure_events: list[str]
    liquidity_sweep_detected: bool
    confidence_modifier: float
    human_readable_summary: str
    swing_highs: tuple[SwingPoint, ...] = ()
    swing_lows: tuple[SwingPoint, ...] = ()
    events: tuple[StructureEvent, ...] = ()


class MarketStructureEngine:
    """Classify swings, structural breaks, reversals, sweeps, and market phase."""

    def __init__(self, swing_window: int = 2) -> None:
        if swing_window < 1:
            raise ValueError("swing_window must be at least 1")
        self.swing_window = swing_window

    def analyze(self, candles: list[Candle]) -> MarketStructureResult:
        if len(candles) < self.swing_window * 2 + 1:
            return self._unclear_result()

        highs, lows = find_swings(candles, self.swing_window)
        trend = _classify_trend(highs, lows)
        events = _relationship_events(candles, highs, lows)
        events.extend(
            _price_action_events(candles, highs, lows, self.swing_window)
        )

        phase = _classify_phase(candles, trend, events)
        phase_event: StructureEventType = (
            "pullback" if phase == "pullback" else "trend_continuation"
        )
        if trend in {"bullish", "bearish"} and phase in {"impulse", "pullback"}:
            last = candles[-1]
            events.append(
                StructureEvent(
                    index=len(candles) - 1,
                    timestamp=last.timestamp,
                    type=phase_event,
                    price=last.close,
                    description=(
                        f"Price is in a {phase} phase within the {trend} structure."
                    ),
                )
            )

        recent_events = _latest_unique_events(events)
        swept = any(event.startswith("liquidity_sweep_") for event in recent_events)
        modifier = _confidence_modifier(trend, phase, recent_events, swept)
        latest_high = highs[-1] if highs else None
        latest_low = lows[-1] if lows else None

        return MarketStructureResult(
            trend=trend,
            phase=phase,
            latest_swing_high=latest_high,
            latest_swing_low=latest_low,
            structure_events=recent_events,
            liquidity_sweep_detected=swept,
            confidence_modifier=modifier,
            human_readable_summary=_build_summary(
                trend, phase, latest_high, latest_low, recent_events
            ),
            swing_highs=tuple(highs),
            swing_lows=tuple(lows),
            events=tuple(sorted(events, key=lambda event: (event.index, event.type))),
        )

    @staticmethod
    def _unclear_result() -> MarketStructureResult:
        return MarketStructureResult(
            trend="unclear",
            phase="unclear",
            latest_swing_high=None,
            latest_swing_low=None,
            structure_events=[],
            liquidity_sweep_detected=False,
            confidence_modifier=-1.0,
            human_readable_summary="There are not enough confirmed candles to determine structure.",
        )


def _classify_trend(highs: list[SwingPoint], lows: list[SwingPoint]) -> Trend:
    if len(highs) < 2 or len(lows) < 2:
        return "unclear"
    highs_rising = highs[-1].price > highs[-2].price
    highs_falling = highs[-1].price < highs[-2].price
    lows_rising = lows[-1].price > lows[-2].price
    lows_falling = lows[-1].price < lows[-2].price
    if highs_rising and lows_rising:
        return "bullish"
    if highs_falling and lows_falling:
        return "bearish"
    return "ranging"


def _relationship_events(
    candles: list[Candle], highs: list[SwingPoint], lows: list[SwingPoint]
) -> list[StructureEvent]:
    events: list[StructureEvent] = []
    for point in [*highs, *lows]:
        if point.label is None:
            continue
        label = point.label.replace("_", " ")
        events.append(
            StructureEvent(
                index=point.index,
                timestamp=candles[point.index].timestamp,
                type=point.label,
                price=point.price,
                description=f"Confirmed {label} at {point.price:.2f}.",
                reference_swing=point,
            )
        )
    return events


def _price_action_events(
    candles: list[Candle],
    highs: list[SwingPoint],
    lows: list[SwingPoint],
    swing_window: int,
) -> list[StructureEvent]:
    events: list[StructureEvent] = []
    broken_highs: set[int] = set()
    broken_lows: set[int] = set()
    swept_highs: set[int] = set()
    swept_lows: set[int] = set()

    for index in range(1, len(candles)):
        prior_highs = [
            point
            for point in highs
            if (point.confirmed_index or point.index + swing_window) < index
        ]
        prior_lows = [
            point
            for point in lows
            if (point.confirmed_index or point.index + swing_window) < index
        ]
        latest_high = prior_highs[-1] if prior_highs else None
        latest_low = prior_lows[-1] if prior_lows else None
        candle = candles[index]
        previous_close = candles[index - 1].close
        trend_before_break = _classify_trend(prior_highs, prior_lows)

        if latest_high is not None:
            if (
                latest_high.index not in broken_highs
                and candle.close > latest_high.price
                and previous_close <= latest_high.price
            ):
                name: StructureEventType = (
                    "bullish_choch"
                    if trend_before_break == "bearish"
                    else "bullish_bos"
                )
                events.append(
                    _break_event(candle, index, name, latest_high)
                )
                broken_highs.add(latest_high.index)
            elif (
                latest_high.index not in swept_highs
                and candle.high > latest_high.price
                and candle.close <= latest_high.price
            ):
                events.append(
                    _sweep_event(candle, index, "liquidity_sweep_high", latest_high)
                )
                swept_highs.add(latest_high.index)

        if latest_low is not None:
            if (
                latest_low.index not in broken_lows
                and candle.close < latest_low.price
                and previous_close >= latest_low.price
            ):
                name = (
                    "bearish_choch"
                    if trend_before_break == "bullish"
                    else "bearish_bos"
                )
                events.append(
                    _break_event(candle, index, name, latest_low)
                )
                broken_lows.add(latest_low.index)
            elif (
                latest_low.index not in swept_lows
                and candle.low < latest_low.price
                and candle.close >= latest_low.price
            ):
                events.append(
                    _sweep_event(candle, index, "liquidity_sweep_low", latest_low)
                )
                swept_lows.add(latest_low.index)

    return events


def _break_event(
    candle: Candle,
    index: int,
    event_type: StructureEventType,
    reference: SwingPoint,
) -> StructureEvent:
    direction = "above" if event_type.startswith("bullish") else "below"
    label = event_type.replace("_", " ")
    return StructureEvent(
        index=index,
        timestamp=candle.timestamp,
        type=event_type,
        price=candle.close,
        description=(
            f"{label.title()}: candle closed {direction} the confirmed swing at "
            f"{reference.price:.2f}."
        ),
        reference_swing=reference,
    )


def _sweep_event(
    candle: Candle,
    index: int,
    event_type: StructureEventType,
    reference: SwingPoint,
) -> StructureEvent:
    side = "high" if event_type.endswith("high") else "low"
    excursion = candle.high if side == "high" else candle.low
    return StructureEvent(
        index=index,
        timestamp=candle.timestamp,
        type=event_type,
        price=excursion,
        description=(
            f"Liquidity sweep {side}: price traded through {reference.price:.2f} "
            "and closed back inside the level."
        ),
        reference_swing=reference,
    )


def _classify_phase(
    candles: list[Candle], trend: Trend, events: list[StructureEvent]
) -> Phase:
    breaks = [
        event
        for event in events
        if event.type.endswith("_bos") or event.type.endswith("_choch")
    ]
    if breaks and max(breaks, key=lambda event: event.index).type.endswith("_choch"):
        return "reversal_attempt"
    if trend == "ranging":
        return "range"
    if trend == "unclear":
        return "unclear"

    comparison_index = max(0, len(candles) - 3)
    recent_move = candles[-1].close - candles[comparison_index].close
    moving_against_trend = (trend == "bullish" and recent_move < 0) or (
        trend == "bearish" and recent_move > 0
    )
    return "pullback" if moving_against_trend else "impulse"


def _latest_unique_events(events: list[StructureEvent]) -> list[str]:
    latest_by_name: dict[str, int] = {}
    for event in events:
        latest_by_name[event.type] = max(
            event.index, latest_by_name.get(event.type, -1)
        )
    return [name for name, _ in sorted(latest_by_name.items(), key=lambda item: (item[1], item[0]))]


def _confidence_modifier(
    trend: Trend, phase: Phase, events: list[str], liquidity_sweep: bool
) -> float:
    modifier = 1.0 if trend in {"bullish", "bearish"} else -0.75
    if trend == "unclear":
        modifier = -1.0
    if any(event.endswith("_bos") for event in events):
        modifier += 0.5
    if any(event.endswith("_choch") for event in events):
        modifier -= 0.25
    if liquidity_sweep:
        modifier -= 0.25
    if phase == "impulse":
        modifier += 0.25
    return round(max(-2.0, min(2.0, modifier)), 2)


def _build_summary(
    trend: Trend,
    phase: Phase,
    latest_high: SwingPoint | None,
    latest_low: SwingPoint | None,
    events: list[str],
) -> str:
    summary = f"Market structure is {trend} and currently in a {phase} phase."
    if latest_high and latest_low:
        summary += (
            f" Latest confirmed swing high is {latest_high.price:.2f};"
            f" latest confirmed swing low is {latest_low.price:.2f}."
        )
    relationships = [
        event
        for event in events
        if event in {"higher_high", "higher_low", "lower_high", "lower_low"}
    ]
    if relationships:
        labels = " and ".join(
            event.replace("_", " ") for event in relationships[-2:]
        )
        summary += f" Latest swing sequence includes {labels}."
    important = [
        event
        for event in events
        if event.endswith("_bos")
        or event.endswith("_choch")
        or event.startswith("liquidity_sweep_")
    ]
    if important:
        labels = ", ".join(event.replace("_", " ") for event in important[-3:])
        summary += f" Recent structure signals: {labels}."
    return summary
