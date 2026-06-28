"""Derive and diagnose illustrative risk levels without placing orders."""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Literal

from core.instruments import format_price


RiskDirection = Literal["bullish", "bearish", "neutral", "unclear"]


@dataclass(frozen=True)
class NumericRiskLevels:
    entry_zone: tuple[float, float]
    entry_price: float
    stop_loss: float
    target: float
    risk: float
    reward: float
    estimated_r: float | None


class RiskRewardFailureReason(str, Enum):
    ENTRY_MISSING = "entry_missing"
    STOP_MISSING = "stop_missing"
    TARGET_MISSING = "target_missing"
    INVALID_DIRECTION = "invalid_direction"
    INVALID_PRICE_GEOMETRY = "invalid_price_geometry"
    STOP_TOO_WIDE = "stop_too_wide"
    TARGET_TOO_CLOSE = "target_too_close"
    BELOW_MINIMUM_R = "below_minimum_r"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class RiskRewardDiagnostics:
    has_entry: bool
    has_stop: bool
    has_target: bool
    direction: RiskDirection
    entry_price: float | None
    stop_loss: float | None
    target: float | None
    risk: float | None
    reward: float | None
    estimated_r: float | None
    minimum_required_r: float
    passed: bool
    failure_reason: RiskRewardFailureReason | None
    human_readable_summary: str


def diagnose_risk_reward(
    *,
    direction: str,
    entry_zone: str | None,
    stop_loss: str | None,
    target: str | None,
    minimum_required_r: float = 1.5,
) -> RiskRewardDiagnostics:
    """Validate level availability, directional geometry, and reward-to-risk."""

    normalized_direction = _normalize_direction(direction)
    entry = parse_risk_level(entry_zone, midpoint=True)
    stop = parse_risk_level(stop_loss)
    objective = parse_risk_level(target)
    base = {
        "has_entry": entry is not None,
        "has_stop": stop is not None,
        "has_target": objective is not None,
        "direction": normalized_direction,
        "entry_price": entry,
        "stop_loss": stop,
        "target": objective,
        "risk": None,
        "reward": None,
        "estimated_r": None,
        "minimum_required_r": minimum_required_r,
    }
    if entry is None:
        return _failed_risk(base, RiskRewardFailureReason.ENTRY_MISSING, "Entry is unavailable.")
    if stop is None:
        return _failed_risk(base, RiskRewardFailureReason.STOP_MISSING, "Stop loss is unavailable.")
    if objective is None:
        return _failed_risk(base, RiskRewardFailureReason.TARGET_MISSING, "Target is unavailable.")
    if normalized_direction not in {"bullish", "bearish"}:
        return _failed_risk(
            base,
            RiskRewardFailureReason.INVALID_DIRECTION,
            "A bullish or bearish direction is required to validate price geometry.",
        )

    valid_geometry = (
        stop < entry < objective
        if normalized_direction == "bullish"
        else objective < entry < stop
    )
    if not valid_geometry:
        return _failed_risk(
            base,
            RiskRewardFailureReason.INVALID_PRICE_GEOMETRY,
            f"{normalized_direction.title()} levels are not ordered correctly.",
        )

    risk = abs(entry - stop)
    reward = abs(objective - entry)
    if risk <= 0 or reward <= 0:
        return _failed_risk(
            base,
            RiskRewardFailureReason.INVALID_PRICE_GEOMETRY,
            "Risk and reward distances must both be positive.",
        )
    estimated_r = round(reward / risk, 3)
    measured = base | {"risk": risk, "reward": reward, "estimated_r": estimated_r}
    if estimated_r >= minimum_required_r:
        return RiskRewardDiagnostics(
            **measured,
            passed=True,
            failure_reason=None,
            human_readable_summary=(
                f"{normalized_direction.title()} geometry provides {estimated_r:.2f}R, "
                f"meeting the {minimum_required_r:.2f}R minimum."
            ),
        )

    # When the stop is farther from entry than the target, excessive risk distance
    # is the clearest defect. Otherwise the target lacks enough extension for 1.5R.
    reason = (
        RiskRewardFailureReason.STOP_TOO_WIDE
        if risk > reward
        else RiskRewardFailureReason.TARGET_TOO_CLOSE
    )
    return _failed_risk(
        measured,
        reason,
        (
            f"{estimated_r:.2f}R is below the {minimum_required_r:.2f}R minimum; "
            f"the {'stop distance exceeds reward' if reason is RiskRewardFailureReason.STOP_TOO_WIDE else 'target lacks required extension'}."
        ),
    )


def parse_risk_level(value: str | None, *, midpoint: bool = False) -> float | None:
    if value is None:
        return None
    text = value.strip().replace(",", "")
    range_match = re.fullmatch(
        r"\s*(-?\d+(?:\.\d+)?)\s*-\s*(-?\d+(?:\.\d+)?)\s*", text
    )
    if range_match:
        first, second = (float(number) for number in range_match.groups())
        return (first + second) / 2 if midpoint else first
    try:
        return float(text)
    except ValueError:
        return None


def _normalize_direction(direction: str) -> RiskDirection:
    normalized = direction.strip().lower()
    if normalized in {"bullish", "buy"}:
        return "bullish"
    if normalized in {"bearish", "sell"}:
        return "bearish"
    if normalized == "neutral":
        return "neutral"
    return "unclear"


def _failed_risk(
    values: dict[str, object],
    reason: RiskRewardFailureReason,
    summary: str,
) -> RiskRewardDiagnostics:
    return RiskRewardDiagnostics(
        **values,  # type: ignore[arg-type]
        passed=False,
        failure_reason=reason,
        human_readable_summary=summary,
    )


def build_numeric_risk_levels(
    bias: str,
    support: tuple[float, float],
    resistance: tuple[float, float],
) -> NumericRiskLevels:
    if bias == "bearish":
        entry = resistance
        stop = resistance[1] + (resistance[1] - resistance[0])
        target = support[1]
    else:
        entry = support
        stop = support[0] - (support[1] - support[0])
        target = resistance[0]
    entry_price = sum(entry) / 2.0
    risk = abs(entry_price - stop)
    reward = abs(target - entry_price)
    valid_geometry = (
        stop < entry_price < target
        if bias == "bullish"
        else target < entry_price < stop
        if bias == "bearish"
        else False
    )
    estimated_r = round(reward / risk, 6) if valid_geometry and risk > 0 else None
    return NumericRiskLevels(
        entry_zone=entry,
        entry_price=entry_price,
        stop_loss=stop,
        target=target,
        risk=risk,
        reward=reward,
        estimated_r=estimated_r,
    )


def format_risk_levels(
    levels: NumericRiskLevels,
    symbol: str = "",
) -> tuple[str, str, str]:
    entry = levels.entry_zone
    return (
        f"{format_price(entry[0], symbol)}-{format_price(entry[1], symbol)}",
        format_price(levels.stop_loss, symbol),
        format_price(levels.target, symbol),
    )


def build_risk_levels(
    bias: str,
    support: tuple[float, float],
    resistance: tuple[float, float],
    symbol: str = "",
) -> tuple[str, str, str]:
    return format_risk_levels(
        build_numeric_risk_levels(bias, support, resistance),
        symbol,
    )
