"""Rule-based setup qualification for StructureIQ v0.5."""

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Literal

from core.decision_engine import DecisionAction, DecisionResult
from core.market_data import Candle
from core.market_structure import MarketStructureResult
from core.multi_timeframe import MultiTimeframeResult, TimeframeAlignment
from core.risk import build_numeric_risk_levels, diagnose_risk_reward, format_risk_levels


MINIMUM_ACCEPTABLE_RISK_REWARD = 1.5


SetupDirection = Literal["bullish", "bearish", "neutral"]
ConditionImportance = Literal["required", "recommended", "optional"]
InvalidationSeverity = Literal["soft", "hard"]
CompressionDirection = Literal["bullish", "bearish"]
LevelQuality = Literal["complete", "partial", "missing", "invalid"]


class SetupType(str, Enum):
    BULLISH_BOS_RETEST = "bullish_bos_retest"
    BEARISH_BOS_RETEST = "bearish_bos_retest"
    BULLISH_PULLBACK_CONTINUATION = "bullish_pullback_continuation"
    BEARISH_PULLBACK_CONTINUATION = "bearish_pullback_continuation"
    RANGE_REVERSAL_LONG = "range_reversal_long"
    RANGE_REVERSAL_SHORT = "range_reversal_short"
    LIQUIDITY_SWEEP_REVERSAL_LONG = "liquidity_sweep_reversal_long"
    LIQUIDITY_SWEEP_REVERSAL_SHORT = "liquidity_sweep_reversal_short"
    COMPRESSION_BREAKOUT_LONG = "compression_breakout_long"
    COMPRESSION_BREAKOUT_SHORT = "compression_breakout_short"
    NO_VALID_SETUP = "no_valid_setup"


class SetupStatus(str, Enum):
    CONFIRMED = "confirmed"
    DEVELOPING = "developing"
    WAITING_FOR_CONFIRMATION = "waiting_for_confirmation"
    INVALID = "invalid"
    NO_SETUP = "no_setup"


@dataclass(frozen=True)
class EntryCondition:
    condition: str
    is_met: bool
    importance: ConditionImportance


@dataclass(frozen=True)
class InvalidationRule:
    rule: str
    trigger_level: str | None
    severity: InvalidationSeverity


@dataclass(frozen=True)
class SetupLevelDiagnostics:
    setup_type: str
    setup_status: str
    entry_zone_source: str
    stop_loss_source: str
    target_source: str
    latest_swing_high: float | None
    latest_swing_low: float | None
    nearest_support: float | None
    nearest_resistance: float | None
    level_quality: LevelQuality
    human_readable_summary: str


@dataclass(frozen=True)
class SetupCandidateDiagnostics:
    """Non-authoritative evaluation of one setup candidate."""

    candidate_setup_type: str
    direction: SetupDirection
    was_selected: bool
    candidate_status: str
    has_entry: bool
    has_stop: bool
    has_target: bool
    has_valid_geometry: bool
    estimated_r: float | None
    meets_minimum_r: bool
    blocking_reason: str | None
    quality_score: float
    human_readable_summary: str


@dataclass(frozen=True)
class SetupResult:
    setup_type: SetupType
    setup_status: SetupStatus
    direction: SetupDirection
    setup_quality_score: float
    entry_zone: str | None
    stop_loss: str | None
    target: str | None
    estimated_risk_reward: float | None
    entry_conditions: tuple[EntryCondition, ...]
    invalidation_rules: tuple[InvalidationRule, ...]
    supporting_evidence: tuple[str, ...]
    warning_notes: tuple[str, ...]
    human_readable_summary: str
    setup_level_diagnostics: SetupLevelDiagnostics = field(
        default_factory=lambda: _empty_setup_level_diagnostics()
    )
    setup_candidate_diagnostics: tuple[SetupCandidateDiagnostics, ...] = ()


@dataclass(frozen=True)
class _SetupCandidate:
    setup_type: SetupType
    direction: SetupDirection
    pattern_condition: str
    pattern_met: bool
    level_condition: str
    level_met: bool
    evidence: tuple[str, ...]
    breakout_confirmed: bool = False


class SetupEngine:
    """Interpret decision and structure output as a specific setup plan."""

    def analyze(
        self,
        *,
        decision: DecisionResult,
        market_structure: MarketStructureResult,
        multi_timeframe: MultiTimeframeResult,
        current_price: float,
        support_zone: tuple[float, float],
        resistance_zone: tuple[float, float],
        current_timeframe_confirmed: bool,
        estimated_risk_reward: float | None,
        entry_zone: str | None,
        stop_loss: str | None,
        target: str | None,
        compression_detected: bool = False,
        compression_breakout_direction: CompressionDirection | None = None,
        symbol: str = "",
    ) -> SetupResult:
        decision_direction = _decision_direction(decision, multi_timeframe)
        tolerance = max(abs(current_price) * 0.005, 1e-9)
        near_support = _near_zone(current_price, support_zone, tolerance)
        near_resistance = _near_zone(current_price, resistance_zone, tolerance)
        diagnostic_candidates = _diagnostic_candidate_pool(
            decision_direction=decision_direction,
            structure=market_structure,
            near_support=near_support,
            near_resistance=near_resistance,
            compression_detected=compression_detected,
            compression_breakout_direction=compression_breakout_direction,
        )
        preselection_diagnostics = _evaluate_candidate_pool(
            candidates=diagnostic_candidates,
            selected=None,
            decision=decision,
            structure=market_structure,
            multi_timeframe=multi_timeframe,
            current_timeframe_confirmed=current_timeframe_confirmed,
            current_price=current_price,
            support_zone=support_zone,
            resistance_zone=resistance_zone,
            symbol=symbol,
        )
        if decision.action is DecisionAction.AVOID:
            return _no_setup(
                "No valid setup is considered because the Decision Engine returned avoid.",
                warning="Decision confidence is insufficient for setup qualification.",
                setup_level_diagnostics=_build_setup_level_diagnostics(
                    setup_type=SetupType.NO_VALID_SETUP,
                    setup_status=SetupStatus.NO_SETUP,
                    direction=decision_direction,
                    structure=market_structure,
                    support_zone=support_zone,
                    resistance_zone=resistance_zone,
                    entry_zone=entry_zone,
                    stop_loss=stop_loss,
                    target=target,
                ),
                setup_candidate_diagnostics=preselection_diagnostics,
            )
        candidate = _select_candidate(
            decision_direction=decision_direction,
            structure=market_structure,
            current_price=current_price,
            support_zone=support_zone,
            resistance_zone=resistance_zone,
            near_support=near_support,
            near_resistance=near_resistance,
            compression_detected=compression_detected,
            compression_breakout_direction=compression_breakout_direction,
        )
        candidate = _compare_bearish_bos_and_sweep(
            selected=candidate,
            candidates=diagnostic_candidates,
            diagnostics=preselection_diagnostics,
            structure=market_structure,
            multi_timeframe=multi_timeframe,
            estimated_risk_reward=estimated_risk_reward,
            entry_zone=entry_zone,
            stop_loss=stop_loss,
            target=target,
        )
        if candidate is None:
            return _no_setup(
                "No valid setup matches the current decision, structure, and price location.",
                warning="Wait for price to reach a structural level or confirm a defined pattern.",
                setup_level_diagnostics=_build_setup_level_diagnostics(
                    setup_type=SetupType.NO_VALID_SETUP,
                    setup_status=SetupStatus.NO_SETUP,
                    direction=decision_direction,
                    structure=market_structure,
                    support_zone=support_zone,
                    resistance_zone=resistance_zone,
                    entry_zone=entry_zone,
                    stop_loss=stop_loss,
                    target=target,
                ),
                setup_candidate_diagnostics=preselection_diagnostics,
            )

        conditions = _build_conditions(
            candidate=candidate,
            decision=decision,
            structure=market_structure,
            multi_timeframe=multi_timeframe,
            current_timeframe_confirmed=current_timeframe_confirmed,
            estimated_risk_reward=estimated_risk_reward,
            current_price=current_price,
            risk_levels_available=all(
                level is not None and level.strip()
                for level in (entry_zone, stop_loss, target)
            ),
        )
        invalidations = _build_invalidations(
            candidate.direction, market_structure
        )
        status = _classify_status(
            decision,
            candidate,
            conditions,
            invalidations,
            current_price,
        )
        quality = _quality_score(conditions)
        warnings = _warning_notes(
            decision,
            multi_timeframe,
            conditions,
            estimated_risk_reward,
            candidate,
        )

        return SetupResult(
            setup_type=candidate.setup_type,
            setup_status=status,
            direction=candidate.direction,
            setup_quality_score=quality,
            entry_zone=entry_zone,
            stop_loss=stop_loss,
            target=target,
            estimated_risk_reward=estimated_risk_reward,
            entry_conditions=tuple(conditions),
            invalidation_rules=tuple(invalidations),
            supporting_evidence=candidate.evidence,
            warning_notes=tuple(warnings),
            human_readable_summary=_build_summary(candidate, status),
            setup_level_diagnostics=_build_setup_level_diagnostics(
                setup_type=candidate.setup_type,
                setup_status=status,
                direction=candidate.direction,
                structure=market_structure,
                support_zone=support_zone,
                resistance_zone=resistance_zone,
                entry_zone=entry_zone,
                stop_loss=stop_loss,
                target=target,
            ),
            setup_candidate_diagnostics=_evaluate_candidate_pool(
                candidates=diagnostic_candidates,
                selected=candidate.setup_type,
                decision=decision,
                structure=market_structure,
                multi_timeframe=multi_timeframe,
                current_timeframe_confirmed=current_timeframe_confirmed,
                current_price=current_price,
                support_zone=support_zone,
                resistance_zone=resistance_zone,
                symbol=symbol,
            ),
        )


def approximate_compression(
    candles: list[Candle], *, recent_window: int = 4, baseline_window: int = 8
) -> bool:
    """Detect range contraction without introducing a new indicator dependency."""

    required = recent_window + baseline_window
    if len(candles) < required:
        return False
    ranges = [candle.high - candle.low for candle in candles[-required:]]
    baseline = ranges[:baseline_window]
    recent = ranges[baseline_window:]
    baseline_average = sum(baseline) / len(baseline)
    recent_average = sum(recent) / len(recent)
    return baseline_average > 0 and recent_average <= baseline_average * 0.65


def compression_breakout_direction(
    candles: list[Candle], *, lookback: int = 4
) -> CompressionDirection | None:
    """Return close-confirmed direction beyond the preceding compression range."""

    if len(candles) <= lookback:
        return None
    reference = candles[-lookback - 1 : -1]
    close = candles[-1].close
    if close > max(candle.high for candle in reference):
        return "bullish"
    if close < min(candle.low for candle in reference):
        return "bearish"
    return None


def _near_zone(
    price: float, zone: tuple[float, float], tolerance: float
) -> bool:
    return zone[0] - tolerance <= price <= zone[1] + tolerance


def _decision_direction(
    decision: DecisionResult, multi_timeframe: MultiTimeframeResult
) -> SetupDirection:
    if decision.action is DecisionAction.BUY:
        return "bullish"
    if decision.action is DecisionAction.SELL:
        return "bearish"
    if multi_timeframe.directional_bias in {"bullish", "bearish"}:
        return multi_timeframe.directional_bias
    return "neutral"


def _diagnostic_candidate_pool(
    *,
    decision_direction: SetupDirection,
    structure: MarketStructureResult,
    near_support: bool,
    near_resistance: bool,
    compression_detected: bool,
    compression_breakout_direction: CompressionDirection | None,
) -> tuple[_SetupCandidate, ...]:
    """Enumerate plausible candidates without participating in selection."""

    events = structure.structure_events
    candidates: list[_SetupCandidate] = []
    if "liquidity_sweep_low" in events:
        candidates.append(_SetupCandidate(
            SetupType.LIQUIDITY_SWEEP_REVERSAL_LONG, "bullish",
            "Liquidity below a confirmed low is swept and reclaimed.", True,
            "Price remains near the reclaimed support context.", near_support,
            ("A confirmed liquidity sweep low supports a long reversal candidate.",),
        ))
    if "liquidity_sweep_high" in events:
        candidates.append(_SetupCandidate(
            SetupType.LIQUIDITY_SWEEP_REVERSAL_SHORT, "bearish",
            "Liquidity above a confirmed high is swept and rejected.", True,
            "Price remains near the rejected resistance context.", near_resistance,
            ("A confirmed liquidity sweep high supports a short reversal candidate.",),
        ))
    if structure.trend == "ranging":
        candidates.extend((
            _SetupCandidate(SetupType.RANGE_REVERSAL_LONG, "bullish",
                "A validated range remains intact.", True,
                "Price tests the range support zone.", near_support,
                ("Ranging structure permits a support reversal candidate.",)),
            _SetupCandidate(SetupType.RANGE_REVERSAL_SHORT, "bearish",
                "A validated range remains intact.", True,
                "Price tests the range resistance zone.", near_resistance,
                ("Ranging structure permits a resistance reversal candidate.",)),
        ))
    if "bullish_bos" in events:
        candidates.append(_SetupCandidate(
            SetupType.BULLISH_BOS_RETEST, "bullish",
            "A bullish break of structure is confirmed.", True,
            "Price retests broken structure as support.", near_support,
            ("Bullish BOS creates a potential retest candidate.",),
        ))
    if "bearish_bos" in events:
        candidates.append(_SetupCandidate(
            SetupType.BEARISH_BOS_RETEST, "bearish",
            "A bearish break of structure is confirmed.", True,
            "Price retests broken structure as resistance.", near_resistance,
            ("Bearish BOS creates a potential retest candidate.",),
        ))
    if structure.trend == "bullish" and structure.phase == "pullback":
        candidates.append(_SetupCandidate(
            SetupType.BULLISH_PULLBACK_CONTINUATION, "bullish",
            "Bullish structure is in a pullback phase.", True,
            "Price pulls back into relevant support.", near_support,
            ("Bullish trend and pullback structure support continuation.",),
        ))
    if structure.trend == "bearish" and structure.phase == "pullback":
        candidates.append(_SetupCandidate(
            SetupType.BEARISH_PULLBACK_CONTINUATION, "bearish",
            "Bearish structure is in a pullback phase.", True,
            "Price pulls back into relevant resistance.", near_resistance,
            ("Bearish trend and pullback structure support continuation.",),
        ))
    if compression_detected:
        directions: tuple[SetupDirection, ...]
        if compression_breakout_direction is not None:
            directions = (compression_breakout_direction,)
        elif decision_direction in {"bullish", "bearish"}:
            directions = (decision_direction,)
        else:
            directions = ("bullish", "bearish")
        for direction in directions:
            candidates.append(_SetupCandidate(
                SetupType.COMPRESSION_BREAKOUT_LONG if direction == "bullish"
                else SetupType.COMPRESSION_BREAKOUT_SHORT,
                direction,
                "Price range is compressed relative to its recent baseline.", True,
                f"Price closes beyond the compression in the {direction} direction.",
                compression_breakout_direction == direction,
                ("Recent candle ranges show measurable compression.",),
                breakout_confirmed=compression_breakout_direction == direction,
            ))
    # Preserve deterministic ordering and avoid duplicates from overlapping context.
    unique: dict[SetupType, _SetupCandidate] = {}
    for item in candidates:
        unique.setdefault(item.setup_type, item)
    return tuple(unique.values())


def _evaluate_candidate_pool(
    *,
    candidates: tuple[_SetupCandidate, ...],
    selected: SetupType | None,
    decision: DecisionResult,
    structure: MarketStructureResult,
    multi_timeframe: MultiTimeframeResult,
    current_timeframe_confirmed: bool,
    current_price: float,
    support_zone: tuple[float, float],
    resistance_zone: tuple[float, float],
    symbol: str,
) -> tuple[SetupCandidateDiagnostics, ...]:
    results: list[SetupCandidateDiagnostics] = []
    for candidate in candidates:
        numeric = build_numeric_risk_levels(candidate.direction, support_zone, resistance_zone)
        entry, stop, target = format_risk_levels(numeric, symbol)
        risk = diagnose_risk_reward(
            direction=candidate.direction,
            entry_zone=entry,
            stop_loss=stop,
            target=target,
            minimum_required_r=MINIMUM_ACCEPTABLE_RISK_REWARD,
        )
        conditions = _build_conditions(
            candidate=candidate,
            decision=decision,
            structure=structure,
            multi_timeframe=multi_timeframe,
            current_timeframe_confirmed=current_timeframe_confirmed,
            estimated_risk_reward=numeric.estimated_r,
            current_price=current_price,
            risk_levels_available=True,
        )
        invalidations = _build_invalidations(candidate.direction, structure)
        status = _classify_status(decision, candidate, conditions, invalidations, current_price)
        blocker: str | None = None
        if not risk.has_entry:
            blocker = "entry_missing"
        elif not risk.has_stop:
            blocker = "stop_missing"
        elif not risk.has_target:
            blocker = "target_missing"
        elif risk.failure_reason is not None and risk.failure_reason.value in {"invalid_direction", "invalid_price_geometry"}:
            blocker = "invalid_geometry"
        elif not risk.passed:
            blocker = "risk_reward_below_minimum"
        elif decision.action.value != ("buy" if candidate.direction == "bullish" else "sell"):
            blocker = "direction_mismatch"
        elif not candidate.level_met:
            blocker = "missing_retest_level" if "bos_retest" in candidate.setup_type.value else (
                "price_not_at_support" if candidate.direction == "bullish" else "price_not_at_resistance"
            )
        elif not current_timeframe_confirmed:
            blocker = "confirmation_missing"
        elif status is not SetupStatus.CONFIRMED:
            blocker = "setup_not_confirmed"
        elif selected is not None and candidate.setup_type is not selected:
            blocker = "stronger_candidate_selected"
        results.append(SetupCandidateDiagnostics(
            candidate_setup_type=candidate.setup_type.value,
            direction=candidate.direction,
            was_selected=candidate.setup_type is selected,
            candidate_status=status.value,
            has_entry=risk.has_entry,
            has_stop=risk.has_stop,
            has_target=risk.has_target,
            has_valid_geometry=risk.failure_reason is None or risk.failure_reason.value not in {"invalid_direction", "invalid_price_geometry"},
            estimated_r=risk.estimated_r,
            meets_minimum_r=risk.passed,
            blocking_reason=blocker,
            quality_score=_quality_score(conditions),
            human_readable_summary=(
                f"{candidate.setup_type.value.replace('_', ' ').title()} is "
                + ("executable under current setup gates." if blocker is None else f"blocked by {blocker.replace('_', ' ')}.")
            ),
        ))
    return tuple(results)


def _compare_bearish_bos_and_sweep(
    *,
    selected: _SetupCandidate | None,
    candidates: tuple[_SetupCandidate, ...],
    diagnostics: tuple[SetupCandidateDiagnostics, ...],
    structure: MarketStructureResult,
    multi_timeframe: MultiTimeframeResult,
    estimated_risk_reward: float | None,
    entry_zone: str | None,
    stop_loss: str | None,
    target: str | None,
) -> _SetupCandidate | None:
    """Resolve only the bearish BOS/sweep collision using existing hard gates."""

    if selected is None or selected.setup_type is not SetupType.LIQUIDITY_SWEEP_REVERSAL_SHORT:
        return selected
    bos = next(
        (item for item in candidates if item.setup_type is SetupType.BEARISH_BOS_RETEST),
        None,
    )
    if bos is None or structure.trend != "bearish" or not _bearish_alignment(multi_timeframe):
        return selected
    recent_events = structure.structure_events[-3:]
    if "bearish_bos" not in recent_events:
        return selected
    bos_diagnostic = next(
        (item for item in diagnostics if item.candidate_setup_type == SetupType.BEARISH_BOS_RETEST.value),
        None,
    )
    sweep_diagnostic = next(
        (item for item in diagnostics if item.candidate_setup_type == SetupType.LIQUIDITY_SWEEP_REVERSAL_SHORT.value),
        None,
    )
    production_risk = diagnose_risk_reward(
        direction="bearish",
        entry_zone=entry_zone,
        stop_loss=stop_loss,
        target=target,
        minimum_required_r=MINIMUM_ACCEPTABLE_RISK_REWARD,
    )
    if (
        bos_diagnostic is None
        or bos_diagnostic.blocking_reason is not None
        or not bos_diagnostic.has_valid_geometry
        or not bos_diagnostic.meets_minimum_r
        or estimated_risk_reward is None
        or estimated_risk_reward < MINIMUM_ACCEPTABLE_RISK_REWARD
        or not production_risk.passed
    ):
        return selected

    bos_score = _bearish_selection_score(
        bos_diagnostic,
        setup_type=SetupType.BEARISH_BOS_RETEST,
        structure=structure,
        multi_timeframe=multi_timeframe,
    )
    sweep_score = _bearish_selection_score(
        sweep_diagnostic,
        setup_type=SetupType.LIQUIDITY_SWEEP_REVERSAL_SHORT,
        structure=structure,
        multi_timeframe=multi_timeframe,
    )
    if bos_score <= sweep_score:
        return replace(
            selected,
            evidence=selected.evidence + (
                "Liquidity-sweep reversal retained because its current evidence score "
                "is at least as strong as the bearish BOS retest.",
            ),
        )
    return replace(
        bos,
        evidence=bos.evidence + (
            "Bearish structure and a recent bearish BOS support continuation.",
            "Price is retesting resistance with bearish or mixed-bearish timeframe alignment.",
            "Complete bearish levels meet the 1.5R execution-quality minimum.",
            "The bearish BOS retest outranked the competing liquidity-sweep reversal.",
        ),
    )


def _bearish_alignment(multi_timeframe: MultiTimeframeResult) -> bool:
    return (
        multi_timeframe.alignment is TimeframeAlignment.ALIGNED_BEARISH
        or (
            multi_timeframe.alignment is TimeframeAlignment.MIXED
            and multi_timeframe.directional_bias == "bearish"
        )
    )


def _bearish_selection_score(
    diagnostic: SetupCandidateDiagnostics | None,
    *,
    setup_type: SetupType,
    structure: MarketStructureResult,
    multi_timeframe: MultiTimeframeResult,
) -> float:
    if diagnostic is None or diagnostic.blocking_reason is not None:
        return -1.0
    score = diagnostic.quality_score
    latest_event = structure.structure_events[-1] if structure.structure_events else ""
    if setup_type is SetupType.BEARISH_BOS_RETEST:
        score += 12.0 if structure.trend == "bearish" else 0.0
        score += 6.0 if latest_event == "bearish_bos" else 2.0
        score += 8.0 if multi_timeframe.alignment is TimeframeAlignment.ALIGNED_BEARISH else 4.0
    else:
        score += 8.0
        score += 8.0 if latest_event == "liquidity_sweep_high" else 0.0
        score += 10.0 if structure.phase == "reversal_attempt" else 0.0
        score += 4.0 if _bearish_alignment(multi_timeframe) else 0.0
    return score


def _select_candidate(
    *,
    decision_direction: SetupDirection,
    structure: MarketStructureResult,
    current_price: float,
    support_zone: tuple[float, float],
    resistance_zone: tuple[float, float],
    near_support: bool,
    near_resistance: bool,
    compression_detected: bool,
    compression_breakout_direction: CompressionDirection | None,
) -> _SetupCandidate | None:
    events = structure.structure_events

    if "liquidity_sweep_low" in events and decision_direction in {"bullish", "neutral"}:
        return _SetupCandidate(
            SetupType.LIQUIDITY_SWEEP_REVERSAL_LONG,
            "bullish",
            "Liquidity below a confirmed low is swept and reclaimed.",
            True,
            "Price remains near the reclaimed support context.",
            near_support,
            ("A confirmed liquidity sweep low supports a long reversal candidate.",),
        )
    if "liquidity_sweep_high" in events and decision_direction in {"bearish", "neutral"}:
        return _SetupCandidate(
            SetupType.LIQUIDITY_SWEEP_REVERSAL_SHORT,
            "bearish",
            "Liquidity above a confirmed high is swept and rejected.",
            True,
            "Price remains near the rejected resistance context.",
            near_resistance,
            ("A confirmed liquidity sweep high supports a short reversal candidate.",),
        )

    if structure.trend == "ranging":
        if near_support and near_resistance:
            support_distance = abs(current_price - sum(support_zone) / 2)
            resistance_distance = abs(current_price - sum(resistance_zone) / 2)
            near_support = support_distance <= resistance_distance
            near_resistance = not near_support
        if near_support and decision_direction in {"bullish", "neutral"}:
            return _SetupCandidate(
                SetupType.RANGE_REVERSAL_LONG,
                "bullish",
                "A validated range remains intact.",
                True,
                "Price tests the range support zone.",
                True,
                ("Price is testing support within ranging structure.",),
            )
        if near_resistance and decision_direction in {"bearish", "neutral"}:
            return _SetupCandidate(
                SetupType.RANGE_REVERSAL_SHORT,
                "bearish",
                "A validated range remains intact.",
                True,
                "Price tests the range resistance zone.",
                True,
                ("Price is testing resistance within ranging structure.",),
            )
        return None

    if decision_direction == "bullish" and structure.trend == "bullish":
        if "bullish_bos" in events and near_support:
            return _SetupCandidate(
                SetupType.BULLISH_BOS_RETEST,
                "bullish",
                "A bullish break of structure is confirmed.",
                True,
                "Price retests broken structure as support.",
                True,
                ("Bullish BOS and support retest conditions are present.",),
            )
        if structure.phase == "pullback":
            return _SetupCandidate(
                SetupType.BULLISH_PULLBACK_CONTINUATION,
                "bullish",
                "Bullish structure is in a pullback phase.",
                True,
                "Price pulls back into relevant support.",
                near_support,
                ("Bullish trend and pullback structure support continuation.",),
            )

    if decision_direction == "bearish" and structure.trend == "bearish":
        if "bearish_bos" in events and near_resistance:
            return _SetupCandidate(
                SetupType.BEARISH_BOS_RETEST,
                "bearish",
                "A bearish break of structure is confirmed.",
                True,
                "Price retests broken structure as resistance.",
                True,
                ("Bearish BOS and resistance retest conditions are present.",),
            )
        if structure.phase == "pullback":
            return _SetupCandidate(
                SetupType.BEARISH_PULLBACK_CONTINUATION,
                "bearish",
                "Bearish structure is in a pullback phase.",
                True,
                "Price pulls back into relevant resistance.",
                near_resistance,
                ("Bearish trend and pullback structure support continuation.",),
            )

    if compression_detected:
        direction = compression_breakout_direction
        if direction is None and decision_direction in {"bullish", "bearish"}:
            direction = decision_direction
        if (
            direction is not None
            and decision_direction in {"bullish", "bearish"}
            and direction != decision_direction
        ):
            return None
        if direction is not None:
            return _SetupCandidate(
                SetupType.COMPRESSION_BREAKOUT_LONG
                if direction == "bullish"
                else SetupType.COMPRESSION_BREAKOUT_SHORT,
                direction,
                "Price range is compressed relative to its recent baseline.",
                True,
                f"Price closes beyond the compression in the {direction} direction.",
                compression_breakout_direction == direction,
                ("Recent candle ranges show measurable compression.",),
                breakout_confirmed=compression_breakout_direction == direction,
            )
    return None


def _build_conditions(
    *,
    candidate: _SetupCandidate,
    decision: DecisionResult,
    structure: MarketStructureResult,
    multi_timeframe: MultiTimeframeResult,
    current_timeframe_confirmed: bool,
    estimated_risk_reward: float | None,
    current_price: float,
    risk_levels_available: bool,
) -> list[EntryCondition]:
    directional_action = (
        decision.action is DecisionAction.BUY
        if candidate.direction == "bullish"
        else decision.action is DecisionAction.SELL
    )
    structural_level_holds = True
    if candidate.direction == "bullish" and structure.latest_swing_low is not None:
        structural_level_holds = current_price > structure.latest_swing_low.price
    if candidate.direction == "bearish" and structure.latest_swing_high is not None:
        structural_level_holds = current_price < structure.latest_swing_high.price

    return [
        EntryCondition(
            "Decision Engine direction permits this setup.",
            directional_action,
            "required",
        ),
        EntryCondition(candidate.pattern_condition, candidate.pattern_met, "required"),
        EntryCondition(candidate.level_condition, candidate.level_met, "required"),
        EntryCondition(
            f"{candidate.direction.title()} confirmation candle forms at the setup level.",
            current_timeframe_confirmed,
            "required",
        ),
        EntryCondition(
            "Entry, stop loss, and target levels are available.",
            risk_levels_available,
            "required",
        ),
        EntryCondition(
            "Estimated risk/reward is at least 1.5R.",
            estimated_risk_reward is not None
            and estimated_risk_reward >= MINIMUM_ACCEPTABLE_RISK_REWARD,
            "required",
        ),
        EntryCondition(
            "Price remains beyond the latest structural invalidation level.",
            structural_level_holds,
            "required",
        ),
        EntryCondition(
            "Timeframe alignment is not conflicting or unclear.",
            multi_timeframe.alignment
            not in {TimeframeAlignment.CONFLICTING, TimeframeAlignment.UNCLEAR},
            "recommended",
        ),
    ]


def _build_invalidations(
    direction: SetupDirection, structure: MarketStructureResult
) -> list[InvalidationRule]:
    if direction == "bullish" and structure.latest_swing_low is not None:
        level = f"{structure.latest_swing_low.price:.2f}"
        return [
            InvalidationRule(
                "Bullish setup invalidates if price closes below the latest confirmed swing low.",
                level,
                "hard",
            )
        ]
    if direction == "bearish" and structure.latest_swing_high is not None:
        level = f"{structure.latest_swing_high.price:.2f}"
        return [
            InvalidationRule(
                "Bearish setup invalidates if price closes above the latest confirmed swing high.",
                level,
                "hard",
            )
        ]
    return [
        InvalidationRule(
            "Setup cannot be confirmed until a structural invalidation level is available.",
            None,
            "soft",
        )
    ]


def _classify_status(
    decision: DecisionResult,
    candidate: _SetupCandidate,
    conditions: list[EntryCondition],
    invalidations: list[InvalidationRule],
    current_price: float,
) -> SetupStatus:
    hard_level = next(
        (
            float(rule.trigger_level)
            for rule in invalidations
            if rule.severity == "hard" and rule.trigger_level is not None
        ),
        None,
    )
    if hard_level is not None:
        breached = (
            candidate.direction == "bullish" and current_price <= hard_level
        ) or (
            candidate.direction == "bearish" and current_price >= hard_level
        )
        if breached:
            return SetupStatus.INVALID

    required = [condition for condition in conditions if condition.importance == "required"]
    if decision.action is DecisionAction.WAIT:
        return (
            SetupStatus.WAITING_FOR_CONFIRMATION
            if any(not condition.is_met for condition in required)
            else SetupStatus.DEVELOPING
        )
    if candidate.setup_type in {
        SetupType.COMPRESSION_BREAKOUT_LONG,
        SetupType.COMPRESSION_BREAKOUT_SHORT,
    } and not candidate.breakout_confirmed:
        return SetupStatus.DEVELOPING
    if all(condition.is_met for condition in required):
        return SetupStatus.CONFIRMED
    return SetupStatus.WAITING_FOR_CONFIRMATION


def _quality_score(conditions: list[EntryCondition]) -> float:
    weights = {"required": 3.0, "recommended": 2.0, "optional": 1.0}
    possible = sum(weights[condition.importance] for condition in conditions)
    earned = sum(
        weights[condition.importance] for condition in conditions if condition.is_met
    )
    return round(100.0 * earned / possible, 1) if possible else 0.0


def _warning_notes(
    decision: DecisionResult,
    multi_timeframe: MultiTimeframeResult,
    conditions: list[EntryCondition],
    estimated_risk_reward: float | None,
    candidate: _SetupCandidate,
) -> list[str]:
    warnings: list[str] = []
    if decision.action is DecisionAction.WAIT:
        warnings.append("Decision Engine remains on wait; this setup cannot be confirmed yet.")
    if multi_timeframe.alignment is TimeframeAlignment.CONFLICTING:
        warnings.append("Timeframes conflict and materially weaken setup quality.")
    if estimated_risk_reward is None:
        warnings.append("Estimated risk/reward is unavailable.")
    elif estimated_risk_reward < MINIMUM_ACCEPTABLE_RISK_REWARD:
        warnings.append("Estimated risk/reward is below the 1.5R setup threshold.")
    if candidate.setup_type in {
        SetupType.COMPRESSION_BREAKOUT_LONG,
        SetupType.COMPRESSION_BREAKOUT_SHORT,
    } and not candidate.breakout_confirmed:
        warnings.append("Compression is present, but a close-confirmed breakout is still pending.")
    if any(
        not condition.is_met and condition.importance == "required"
        for condition in conditions
    ):
        warnings.append("One or more required entry conditions remain unmet.")
    return warnings


def _build_summary(candidate: _SetupCandidate, status: SetupStatus) -> str:
    name = candidate.setup_type.value.replace("_", " ")
    if status is SetupStatus.CONFIRMED:
        return f"A {name} setup is confirmed under the current rules."
    if status is SetupStatus.INVALID:
        return f"The {name} setup is invalid because structural invalidation was breached."
    if status is SetupStatus.DEVELOPING:
        return f"A {name} setup is developing but is not yet entry-ready."
    return f"A {name} setup is waiting for required confirmation before entry."


def _build_setup_level_diagnostics(
    *,
    setup_type: SetupType,
    setup_status: SetupStatus,
    direction: SetupDirection,
    structure: MarketStructureResult,
    support_zone: tuple[float, float],
    resistance_zone: tuple[float, float],
    entry_zone: str | None,
    stop_loss: str | None,
    target: str | None,
) -> SetupLevelDiagnostics:
    available = sum(bool(level and level.strip()) for level in (entry_zone, stop_loss, target))
    risk_diagnostics = diagnose_risk_reward(
        direction=direction,
        entry_zone=entry_zone,
        stop_loss=stop_loss,
        target=target,
        minimum_required_r=MINIMUM_ACCEPTABLE_RISK_REWARD,
    )
    if available == 0:
        quality: LevelQuality = "missing"
    elif available < 3:
        quality = "partial"
    elif risk_diagnostics.failure_reason and risk_diagnostics.failure_reason.value in {
        "invalid_direction",
        "invalid_price_geometry",
    }:
        quality = "invalid"
    else:
        quality = "complete"

    if direction == "bullish":
        sources = ("support_zone", "support_zone_extension", "resistance_zone")
    elif direction == "bearish":
        sources = ("resistance_zone", "resistance_zone_extension", "support_zone")
    else:
        sources = ("unresolved_direction",) * 3
    sources = tuple(
        source if level and level.strip() else "unavailable"
        for source, level in zip(sources, (entry_zone, stop_loss, target))
    )
    return SetupLevelDiagnostics(
        setup_type=setup_type.value,
        setup_status=setup_status.value,
        entry_zone_source=sources[0],
        stop_loss_source=sources[1],
        target_source=sources[2],
        latest_swing_high=(
            structure.latest_swing_high.price
            if structure.latest_swing_high is not None
            else None
        ),
        latest_swing_low=(
            structure.latest_swing_low.price
            if structure.latest_swing_low is not None
            else None
        ),
        nearest_support=round(sum(support_zone) / 2.0, 6),
        nearest_resistance=round(sum(resistance_zone) / 2.0, 6),
        level_quality=quality,
        human_readable_summary=(
            f"{setup_type.value.replace('_', ' ').title()} levels are {quality}; "
            f"entry comes from {sources[0].replace('_', ' ')}, stop from "
            f"{sources[1].replace('_', ' ')}, and target from "
            f"{sources[2].replace('_', ' ')}."
        ),
    )


def _empty_setup_level_diagnostics() -> SetupLevelDiagnostics:
    return SetupLevelDiagnostics(
        setup_type=SetupType.NO_VALID_SETUP.value,
        setup_status=SetupStatus.NO_SETUP.value,
        entry_zone_source="unavailable",
        stop_loss_source="unavailable",
        target_source="unavailable",
        latest_swing_high=None,
        latest_swing_low=None,
        nearest_support=None,
        nearest_resistance=None,
        level_quality="missing",
        human_readable_summary="Setup level diagnostics were not supplied.",
    )


def _no_setup(
    message: str,
    *,
    warning: str,
    setup_level_diagnostics: SetupLevelDiagnostics | None = None,
    setup_candidate_diagnostics: tuple[SetupCandidateDiagnostics, ...] = (),
) -> SetupResult:
    return SetupResult(
        setup_type=SetupType.NO_VALID_SETUP,
        setup_status=SetupStatus.NO_SETUP,
        direction="neutral",
        setup_quality_score=0.0,
        entry_zone=None,
        stop_loss=None,
        target=None,
        estimated_risk_reward=None,
        entry_conditions=(),
        invalidation_rules=(),
        supporting_evidence=(),
        warning_notes=(warning,),
        human_readable_summary=message,
        setup_level_diagnostics=(
            setup_level_diagnostics or _empty_setup_level_diagnostics()
        ),
        setup_candidate_diagnostics=setup_candidate_diagnostics,
    )
