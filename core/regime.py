"""Deterministic market-regime classification from existing StructureIQ evidence."""

from dataclasses import dataclass
from enum import Enum

from core.instruments import average_true_range
from core.market_data import Candle
from core.market_structure import MarketStructureResult
from core.multi_timeframe import MultiTimeframeResult, TimeframeAlignment
from core.setup_engine import approximate_compression


class MarketRegime(str, Enum):
    STRONG_BULL_TREND = "strong_bull_trend"
    WEAK_BULL_TREND = "weak_bull_trend"
    STRONG_BEAR_TREND = "strong_bear_trend"
    WEAK_BEAR_TREND = "weak_bear_trend"
    RANGE = "range"
    COMPRESSION = "compression"
    EXPANSION = "expansion"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    TRANSITION = "transition"
    UNKNOWN = "unknown"


class RegimeClassifierMode(str, Enum):
    LEGACY = "legacy"
    TUNED = "tuned"
    COMPARE = "compare"


@dataclass(frozen=True)
class RegimeResult:
    market_regime: MarketRegime
    regime_confidence: float
    regime_reasons: tuple[str, ...]
    human_readable_summary: str


class MarketRegimeEngine:
    """Classify one exclusive research regime without changing analysis decisions."""

    def classify(
        self,
        *,
        candles: list[Candle],
        market_structure: MarketStructureResult,
        multi_timeframe: MultiTimeframeResult,
    ) -> RegimeResult:
        if len(candles) < 5:
            return _result(
                MarketRegime.UNKNOWN,
                10.0,
                ("Too few candles are available for regime classification.",),
            )

        events = set(market_structure.structure_events)
        atr = average_true_range(candles) or 0.0
        price = abs(candles[-1].close) or 1.0
        normalized_atr = atr / price
        range_ratio = _recent_range_ratio(candles)
        momentum = _momentum_in_atr(candles, atr)

        if (
            market_structure.phase == "reversal_attempt"
            or "bullish_choch" in events
            or "bearish_choch" in events
            or multi_timeframe.alignment is TimeframeAlignment.CONFLICTING
        ):
            reasons = ["Structure is attempting a transition or change of character."]
            if multi_timeframe.alignment is TimeframeAlignment.CONFLICTING:
                reasons.append("Higher and current timeframe directions conflict.")
            return _result(MarketRegime.TRANSITION, 88.0, tuple(reasons))

        if approximate_compression(candles):
            return _result(
                MarketRegime.COMPRESSION,
                86.0,
                (
                    "Recent candle ranges contracted materially below their baseline.",
                    f"Recent-to-baseline range ratio is {range_ratio:.2f}.",
                ),
            )

        if range_ratio >= 1.6:
            return _result(
                MarketRegime.EXPANSION,
                min(95.0, 72.0 + 10.0 * (range_ratio - 1.0)),
                (
                    "Recent candle ranges expanded materially above their baseline.",
                    f"Recent-to-baseline range ratio is {range_ratio:.2f}.",
                ),
            )

        if market_structure.trend == "ranging" or market_structure.phase == "range":
            return _result(
                MarketRegime.RANGE,
                82.0 if market_structure.trend == "ranging" else 70.0,
                (
                    "Swing highs and lows do not establish a directional sequence.",
                    "Market Structure Engine classifies the market as range-bound.",
                ),
            )

        if normalized_atr >= 0.02 or range_ratio >= 1.3:
            return _result(
                MarketRegime.HIGH_VOLATILITY,
                78.0,
                (
                    f"ATR is {normalized_atr:.2%} of price.",
                    f"Recent-to-baseline range ratio is {range_ratio:.2f}.",
                ),
            )
        if normalized_atr <= 0.0005 or range_ratio <= 0.7:
            return _result(
                MarketRegime.LOW_VOLATILITY,
                76.0,
                (
                    f"ATR is only {normalized_atr:.2%} of price.",
                    f"Recent-to-baseline range ratio is {range_ratio:.2f}.",
                ),
            )

        if market_structure.trend in {"bullish", "bearish"}:
            bullish = market_structure.trend == "bullish"
            aligned = multi_timeframe.alignment is (
                TimeframeAlignment.ALIGNED_BULLISH
                if bullish else TimeframeAlignment.ALIGNED_BEARISH
            )
            bos = "bullish_bos" in events if bullish else "bearish_bos" in events
            momentum_supports = momentum >= 0.5 if bullish else momentum <= -0.5
            strong_score = sum(
                (
                    25 if aligned else 0,
                    20 if market_structure.phase == "impulse" else 0,
                    20 if bos else 0,
                    15 if momentum_supports else 0,
                    10 if multi_timeframe.alignment_score >= 70 else 0,
                )
            )
            strong = strong_score >= 55
            regime = (
                MarketRegime.STRONG_BULL_TREND
                if bullish and strong
                else MarketRegime.WEAK_BULL_TREND
                if bullish
                else MarketRegime.STRONG_BEAR_TREND
                if strong
                else MarketRegime.WEAK_BEAR_TREND
            )
            reasons = [f"Confirmed swing structure is {market_structure.trend}."]
            reasons.append(
                "Multi-timeframe structure is directionally aligned."
                if aligned else "Timeframe evidence is mixed or only partially aligned."
            )
            if bos:
                reasons.append("A recent break of structure supports the trend.")
            reasons.append(f"Recent momentum measures {momentum:.2f} ATR units.")
            confidence = min(95.0, 58.0 + strong_score * 0.45)
            return _result(regime, confidence, tuple(reasons))

        return _result(
            MarketRegime.UNKNOWN,
            25.0,
            ("Existing structure and volatility evidence does not define a regime.",),
        )


class TunedMarketRegimeEngine:
    """Research classifier that favors current structure over stale transition events."""

    _RECENT_EVENT_BARS = 6

    def classify(
        self,
        *,
        candles: list[Candle],
        market_structure: MarketStructureResult,
        multi_timeframe: MultiTimeframeResult,
    ) -> RegimeResult:
        if len(candles) < 5:
            return _result(
                MarketRegime.UNKNOWN,
                10.0,
                ("Too few candles are available for tuned regime classification.",),
            )

        atr = average_true_range(candles) or 0.0
        price = abs(candles[-1].close) or 1.0
        normalized_atr = atr / price
        range_ratio = _recent_range_ratio(candles)
        momentum = _momentum_in_atr(candles, atr)

        # Preserve the established non-directional market-state rules. Unlike the
        # legacy classifier, stale CHOCH cannot preempt these current conditions.
        if approximate_compression(candles):
            return _result(
                MarketRegime.COMPRESSION,
                86.0,
                (
                    "Recent candle ranges contracted materially below their baseline.",
                    f"Recent-to-baseline range ratio is {range_ratio:.2f}.",
                ),
            )
        if range_ratio >= 1.6:
            return _result(
                MarketRegime.EXPANSION,
                min(95.0, 72.0 + 10.0 * (range_ratio - 1.0)),
                (
                    "Recent candle ranges expanded materially above their baseline.",
                    f"Recent-to-baseline range ratio is {range_ratio:.2f}.",
                ),
            )
        if market_structure.trend == "ranging" or market_structure.phase == "range":
            return _result(
                MarketRegime.RANGE,
                82.0 if market_structure.trend == "ranging" else 70.0,
                (
                    "Swing highs and lows do not establish a directional sequence.",
                    "Market Structure Engine classifies the market as range-bound.",
                ),
            )

        trend = market_structure.trend
        if trend in {"bullish", "bearish"}:
            trend_score, transition_score, evidence = self._directional_scores(
                candles=candles,
                market_structure=market_structure,
                multi_timeframe=multi_timeframe,
                momentum=momentum,
            )
            if transition_score >= 60 and transition_score > trend_score + 10:
                return _result(
                    MarketRegime.TRANSITION,
                    min(95.0, transition_score),
                    tuple(
                        ["Recent transition evidence outweighs current directional structure."]
                        + evidence
                    ),
                )
            strong = trend_score >= 65
            regime = _trend_regime(trend, strong)
            return _result(
                regime,
                min(95.0, 50.0 + trend_score * 0.45),
                tuple(
                    [
                        f"Current directional swing structure is {trend} and "
                        "receives primary weight."
                    ]
                    + evidence
                ),
            )

        recent = self._recent_event_types(candles, market_structure)
        if (
            market_structure.phase == "reversal_attempt"
            or recent & {"bullish_choch", "bearish_choch"}
            or multi_timeframe.alignment is TimeframeAlignment.CONFLICTING
        ):
            return _result(
                MarketRegime.TRANSITION,
                78.0,
                (
                    "Current evidence shows a recent transition without "
                    "directional swing structure.",
                ),
            )
        if normalized_atr >= 0.02 or range_ratio >= 1.3:
            return _result(
                MarketRegime.HIGH_VOLATILITY,
                78.0,
                (
                    f"ATR is {normalized_atr:.2%} of price.",
                    f"Recent-to-baseline range ratio is {range_ratio:.2f}.",
                ),
            )
        if normalized_atr <= 0.0005 or range_ratio <= 0.7:
            return _result(
                MarketRegime.LOW_VOLATILITY,
                76.0,
                (
                    f"ATR is only {normalized_atr:.2%} of price.",
                    f"Recent-to-baseline range ratio is {range_ratio:.2f}.",
                ),
            )
        return _result(
            MarketRegime.UNKNOWN,
            25.0,
            ("Current structure and volatility evidence does not define a tuned regime.",),
        )

    def _directional_scores(
        self,
        *,
        candles: list[Candle],
        market_structure: MarketStructureResult,
        multi_timeframe: MultiTimeframeResult,
        momentum: float,
    ) -> tuple[float, float, list[str]]:
        trend = market_structure.trend
        bullish = trend == "bullish"
        aligned = multi_timeframe.alignment is (
            TimeframeAlignment.ALIGNED_BULLISH
            if bullish else TimeframeAlignment.ALIGNED_BEARISH
        )
        mixed_support = (
            multi_timeframe.alignment is TimeframeAlignment.MIXED
            and multi_timeframe.directional_bias == trend
        )
        recent = self._recent_event_types(candles, market_structure)
        directional_bos = "bullish_bos" if bullish else "bearish_bos"
        opposite_bos = "bearish_bos" if bullish else "bullish_bos"
        recent_bos = directional_bos in recent
        recent_choch = bool(recent & {"bullish_choch", "bearish_choch"})
        momentum_supports = momentum >= 0.5 if bullish else momentum <= -0.5

        trend_score = 45.0
        trend_score += (
            15.0 if market_structure.phase == "impulse"
            else 10.0 if market_structure.phase == "pullback"
            else 0.0
        )
        trend_score += 20.0 if recent_bos else 0.0
        trend_score += 15.0 if aligned else 8.0 if mixed_support else 0.0
        trend_score += 5.0 if multi_timeframe.alignment_score >= 70 else 0.0
        trend_score += 10.0 if momentum_supports else 0.0

        transition_score = 0.0
        transition_score += 40.0 if recent_choch else 0.0
        transition_score += (
            35.0
            if multi_timeframe.alignment is TimeframeAlignment.CONFLICTING
            else 0.0
        )
        transition_score += (
            20.0 if market_structure.phase == "reversal_attempt" else 0.0
        )
        transition_score += 20.0 if opposite_bos in recent else 0.0

        evidence = [
            f"Directional evidence scores {trend_score:.0f}; transition evidence "
            f"scores {transition_score:.0f}."
        ]
        if recent_bos:
            evidence.append(
                "A recent break of structure confirms the current trend direction."
            )
        if aligned:
            evidence.append("Higher-timeframe alignment supports the current trend direction.")
        elif mixed_support:
            evidence.append("Mixed timeframe evidence still supports the current directional bias.")
        if recent_choch:
            evidence.append("A recent CHOCH remains active transition evidence.")
        else:
            evidence.append("No recent CHOCH overrides the current directional swing sequence.")
        return trend_score, transition_score, evidence

    def _recent_event_types(
        self, candles: list[Candle], market_structure: MarketStructureResult
    ) -> set[str]:
        cutoff = max(0, len(candles) - self._RECENT_EVENT_BARS)
        return {
            event.type
            for event in market_structure.events
            if event.index >= cutoff
        }


def _trend_regime(trend: str, strong: bool) -> MarketRegime:
    if trend == "bullish":
        return MarketRegime.STRONG_BULL_TREND if strong else MarketRegime.WEAK_BULL_TREND
    return MarketRegime.STRONG_BEAR_TREND if strong else MarketRegime.WEAK_BEAR_TREND


def _recent_range_ratio(candles: list[Candle]) -> float:
    ranges = [max(0.0, candle.high - candle.low) for candle in candles]
    if len(ranges) < 8:
        return 1.0
    recent = ranges[-4:]
    baseline = ranges[-12:-4] if len(ranges) >= 12 else ranges[:-4]
    baseline_average = sum(baseline) / len(baseline) if baseline else 0.0
    return (sum(recent) / len(recent)) / baseline_average if baseline_average else 1.0


def _momentum_in_atr(candles: list[Candle], atr: float) -> float:
    start = candles[max(0, len(candles) - 5)].close
    return (candles[-1].close - start) / atr if atr > 0 else 0.0


def _result(
    regime: MarketRegime, confidence: float, reasons: tuple[str, ...]
) -> RegimeResult:
    value = round(max(0.0, min(100.0, confidence)), 1)
    return RegimeResult(
        market_regime=regime,
        regime_confidence=value,
        regime_reasons=reasons,
        human_readable_summary=(
            f"Market regime is {regime.value.replace('_', ' ')} with "
            f"{value:.0f}/100 confidence. {reasons[0]}"
        ),
    )
