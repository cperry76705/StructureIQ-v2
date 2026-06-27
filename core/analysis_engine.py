"""Orchestrate the focused analysis modules into one API result."""

from core.decision_engine import DecisionAction, DecisionEngine
from core.indicators import calculate_rsi
from core.market_data import Candle, MarketDataProvider
from core.market_structure import MarketStructureEngine
from core.multi_timeframe import MultiTimeframeEngine
from core.risk import build_risk_levels
from core.strategy_router import route_strategy
from core.structure import find_swings
from core.support_resistance import detect_zones
from models.schemas import AnalysisRequest, AnalysisResponse


def _bullish_candle(candle: Candle) -> bool:
    return candle.close > candle.open


def _risk_reward_ratio(
    bias: str,
    price: float,
    support: tuple[float, float],
    resistance: tuple[float, float],
) -> float | None:
    if bias == "bullish":
        risk = price - support[0]
        reward = resistance[0] - price
    elif bias == "bearish":
        risk = resistance[1] - price
        reward = price - support[1]
    else:
        return None
    if risk <= 0 or reward <= 0:
        return None
    return round(reward / risk, 2)


class AnalysisEngine:
    """Analysis orchestrator with an injected, provider-agnostic data source."""

    def __init__(
        self,
        market_data: MarketDataProvider,
        structure_engine: MarketStructureEngine | None = None,
        multi_timeframe_engine: MultiTimeframeEngine | None = None,
        decision_engine: DecisionEngine | None = None,
    ) -> None:
        self._market_data = market_data
        self._structure_engine = structure_engine or MarketStructureEngine()
        self._multi_timeframe_engine = (
            multi_timeframe_engine or MultiTimeframeEngine()
        )
        self._decision_engine = decision_engine or DecisionEngine()

    def analyze(self, request: AnalysisRequest) -> AnalysisResponse:
        entry_candles = self._market_data.get_candles(
            request.symbol, request.timeframe, request.lookback
        )
        higher_candles = self._market_data.get_candles(
            request.symbol, request.higher_timeframe, request.lookback
        )

        return _build_analysis(
            request,
            entry_candles,
            higher_candles,
            self._structure_engine,
            self._multi_timeframe_engine,
            self._decision_engine,
        )


def _build_analysis(
    request: AnalysisRequest,
    entry_candles: list[Candle],
    higher_candles: list[Candle],
    structure_engine: MarketStructureEngine,
    multi_timeframe_engine: MultiTimeframeEngine,
    decision_engine: DecisionEngine,
) -> AnalysisResponse:
    higher_structure = structure_engine.analyze(higher_candles)
    entry_structure = structure_engine.analyze(entry_candles)
    multi_timeframe = multi_timeframe_engine.analyze(
        request.higher_timeframe,
        request.timeframe,
        higher_structure,
        entry_structure,
    )
    entry_highs, entry_lows = find_swings(entry_candles)
    # The public API has historically exposed three bias values. Internally, the
    # richer engine keeps "unclear" distinct; the API maps it to the safest option.
    bias = higher_structure.trend if higher_structure.trend != "unclear" else "ranging"
    structure = entry_structure.phase
    support, resistance = detect_zones(entry_candles, entry_highs, entry_lows)

    price = entry_candles[-1].close
    relevant_zone = support if bias == "bullish" else resistance
    tolerance = price * 0.005
    near_level = relevant_zone[0] - tolerance <= price <= relevant_zone[1] + tolerance
    bullish_confirmation = _bullish_candle(entry_candles[-1])
    confirmed = bullish_confirmation if bias == "bullish" else not bullish_confirmation
    rsi = calculate_rsi(entry_candles)
    rsi_supportive = 40 <= rsi <= 65 if bias == "bullish" else 35 <= rsi <= 60

    _, setup = route_strategy(
        bias,
        structure,
        near_level,
        confirmed,
        alignment=multi_timeframe.alignment.value,
        current_trend=entry_structure.trend,
    )
    risk_reward_ratio = _risk_reward_ratio(
        bias, price, support, resistance
    )
    decision = decision_engine.analyze(
        market_structure=entry_structure,
        multi_timeframe=multi_timeframe,
        price_near_level=near_level,
        indicator_supportive=rsi_supportive,
        current_timeframe_confirmed=confirmed,
        risk_reward_ratio=risk_reward_ratio,
        volatility_adequate=None,
    )
    action = (
        "no_trade"
        if decision.action is DecisionAction.AVOID
        else decision.action.value
    )
    confidence = round(decision.confidence / 10.0, 1)
    entry_zone, stop_loss, target = build_risk_levels(bias, support, resistance)

    reasons = [
        decision.human_readable_summary,
        f"Higher timeframe is {bias}",
        multi_timeframe.human_readable_summary,
        entry_structure.human_readable_summary,
        f"RSI is {rsi:.1f}",
        "Price is near a key level" if near_level else "Price is not yet at a key level",
        "Entry candle is confirmed" if confirmed else "No confirming entry candle yet",
    ]
    return AnalysisResponse(
        symbol=request.symbol,
        timeframe=request.timeframe,
        higher_timeframe_bias=bias,
        current_structure=structure,
        action=action,
        setup=setup,
        confidence=confidence,
        entry_zone=entry_zone,
        stop_loss=stop_loss,
        target=target,
        reasons=reasons,
        multi_timeframe=multi_timeframe,
        decision=decision,
    )
