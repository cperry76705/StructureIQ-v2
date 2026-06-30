"""Orchestrate the focused analysis modules into one API result."""

from core.decision_engine import DecisionAction, DecisionEngine
from core.explanation_engine import ExplanationEngine
from core.indicators import calculate_rsi
from core.market_data import Candle, MarketDataProvider
from core.market_structure import MarketStructureEngine
from core.multi_timeframe import MultiTimeframeEngine
from core.risk import build_numeric_risk_levels, format_risk_levels
from core.score_engine import ScoreEngine
from core.execution_intelligence import ExecutionIntelligenceEngine
from core.confidence_calibration_engine import ConfidenceCalibrationEngine
from core.strategy_rating_engine import StrategyRatingEngine
from core.risk import diagnose_risk_reward
from core.regime import MarketRegimeEngine, TunedMarketRegimeEngine
from core.regime_tuning import build_regime_tuning_evidence
from core.setup_engine import (
    SetupEngine,
    approximate_compression,
    compression_breakout_direction,
)
from core.strategy_engine import StrategyEngine
from core.structure import find_swings
from core.support_resistance import detect_zones
from models.schemas import AnalysisRequest, AnalysisResponse


def _bullish_candle(candle: Candle) -> bool:
    return candle.close > candle.open


class AnalysisEngine:
    """Analysis orchestrator with an injected, provider-agnostic data source."""

    def __init__(
        self,
        market_data: MarketDataProvider,
        structure_engine: MarketStructureEngine | None = None,
        multi_timeframe_engine: MultiTimeframeEngine | None = None,
        decision_engine: DecisionEngine | None = None,
        setup_engine: SetupEngine | None = None,
        strategy_engine: StrategyEngine | None = None,
        explanation_engine: ExplanationEngine | None = None,
        regime_engine: MarketRegimeEngine | None = None,
        tuned_regime_engine: TunedMarketRegimeEngine | None = None,
        score_engine: ScoreEngine | None = None,
        execution_intelligence_engine: ExecutionIntelligenceEngine | None = None,
        confidence_calibration_engine: ConfidenceCalibrationEngine | None = None,
        strategy_rating_engine: StrategyRatingEngine | None = None,
    ) -> None:
        self._market_data = market_data
        self._structure_engine = structure_engine or MarketStructureEngine()
        self._multi_timeframe_engine = (
            multi_timeframe_engine or MultiTimeframeEngine()
        )
        self._decision_engine = decision_engine or DecisionEngine()
        self._setup_engine = setup_engine or SetupEngine()
        self._strategy_engine = strategy_engine or StrategyEngine()
        self._explanation_engine = explanation_engine or ExplanationEngine()
        self._regime_engine = regime_engine or MarketRegimeEngine()
        self._tuned_regime_engine = tuned_regime_engine or TunedMarketRegimeEngine()
        self._score_engine = score_engine or ScoreEngine()
        self._execution_intelligence_engine = (
            execution_intelligence_engine or ExecutionIntelligenceEngine()
        )
        self._confidence_calibration_engine = (
            confidence_calibration_engine or ConfidenceCalibrationEngine()
        )
        self._strategy_rating_engine = strategy_rating_engine or StrategyRatingEngine()

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
            self._setup_engine,
            self._strategy_engine,
            self._explanation_engine,
            self._regime_engine,
            self._tuned_regime_engine,
            self._score_engine,
            self._execution_intelligence_engine,
            self._confidence_calibration_engine,
            self._strategy_rating_engine,
        )


def _build_analysis(
    request: AnalysisRequest,
    entry_candles: list[Candle],
    higher_candles: list[Candle],
    structure_engine: MarketStructureEngine,
    multi_timeframe_engine: MultiTimeframeEngine,
    decision_engine: DecisionEngine,
    setup_engine: SetupEngine,
    strategy_engine: StrategyEngine,
    explanation_engine: ExplanationEngine,
    regime_engine: MarketRegimeEngine,
    tuned_regime_engine: TunedMarketRegimeEngine,
    score_engine: ScoreEngine,
    execution_intelligence_engine: ExecutionIntelligenceEngine,
    confidence_calibration_engine: ConfidenceCalibrationEngine,
    strategy_rating_engine: StrategyRatingEngine,
) -> AnalysisResponse:
    higher_structure = structure_engine.analyze(higher_candles)
    entry_structure = structure_engine.analyze(entry_candles)
    multi_timeframe = multi_timeframe_engine.analyze(
        request.higher_timeframe,
        request.timeframe,
        higher_structure,
        entry_structure,
    )
    market_regime = regime_engine.classify(
        candles=entry_candles,
        market_structure=entry_structure,
        multi_timeframe=multi_timeframe,
    )
    tuned_market_regime = tuned_regime_engine.classify(
        candles=entry_candles,
        market_structure=entry_structure,
        multi_timeframe=multi_timeframe,
    )
    regime_tuning_evidence = build_regime_tuning_evidence(
        candles=entry_candles,
        market_structure=entry_structure,
        multi_timeframe=multi_timeframe,
        production_regime=market_regime,
    )
    entry_highs, entry_lows = find_swings(entry_candles)
    # The public API has historically exposed three bias values. Internally, the
    # richer engine keeps "unclear" distinct; the API maps it to the safest option.
    bias = higher_structure.trend if higher_structure.trend != "unclear" else "ranging"
    structure = entry_structure.phase
    support, resistance = detect_zones(
        entry_candles,
        entry_highs,
        entry_lows,
        request.symbol,
    )

    price = entry_candles[-1].close
    relevant_zone = support if bias == "bullish" else resistance
    tolerance = price * 0.005
    near_support = support[0] - tolerance <= price <= support[1] + tolerance
    near_resistance = (
        resistance[0] - tolerance <= price <= resistance[1] + tolerance
    )
    near_level = relevant_zone[0] - tolerance <= price <= relevant_zone[1] + tolerance
    bullish_confirmation = _bullish_candle(entry_candles[-1])
    confirmed = bullish_confirmation if bias == "bullish" else not bullish_confirmation
    rsi = calculate_rsi(entry_candles)
    rsi_supportive = 40 <= rsi <= 65 if bias == "bullish" else 35 <= rsi <= 60

    numeric_risk_levels = build_numeric_risk_levels(
        bias,
        support,
        resistance,
    )
    risk_reward_ratio = numeric_risk_levels.estimated_r
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
    entry_zone, stop_loss, target = format_risk_levels(
        numeric_risk_levels,
        request.symbol,
    )
    compression_detected = approximate_compression(entry_candles[:-1])
    breakout_direction = (
        compression_breakout_direction(entry_candles)
        if compression_detected
        else None
    )
    setup_plan = setup_engine.analyze(
        decision=decision,
        market_structure=entry_structure,
        multi_timeframe=multi_timeframe,
        current_price=price,
        support_zone=support,
        resistance_zone=resistance,
        current_timeframe_confirmed=confirmed,
        estimated_risk_reward=risk_reward_ratio,
        entry_zone=entry_zone,
        stop_loss=stop_loss,
        target=target,
        compression_detected=compression_detected,
        compression_breakout_direction=breakout_direction,
        symbol=request.symbol,
    )
    setup = setup_plan.setup_type.value
    strategy = strategy_engine.analyze(
        decision=decision,
        market_structure=entry_structure,
        multi_timeframe=multi_timeframe,
        setup_plan=setup_plan,
        price_near_support=near_support,
        price_near_resistance=near_resistance,
        indicator_supportive=rsi_supportive,
    )
    score_summary = score_engine.score(
        market_structure=entry_structure,
        multi_timeframe=multi_timeframe,
        market_regime=market_regime,
        decision=decision,
        setup_plan=setup_plan,
        strategy=strategy,
        risk_reward_ratio=risk_reward_ratio,
    )
    execution_intelligence = execution_intelligence_engine.analyze(
        action=action,
        setup_plan=setup_plan,
        strategy=strategy,
        risk_reward_diagnostics=diagnose_risk_reward(
            direction=setup_plan.direction,
            entry_zone=setup_plan.entry_zone,
            stop_loss=setup_plan.stop_loss,
            target=setup_plan.target,
        ),
    )
    confidence_calibration = confidence_calibration_engine.calibrate(
        decision.confidence
    )
    current_strategy_rating = strategy_rating_engine.unavailable(
        strategy.preferred_strategy.value
    )
    current_setup_rating = strategy_rating_engine.unavailable(
        setup_plan.setup_type.value
    )
    trader_analysis = explanation_engine.analyze(
        symbol=request.symbol,
        market_structure=entry_structure,
        multi_timeframe=multi_timeframe,
        decision=decision,
        setup_plan=setup_plan,
        strategy=strategy,
    )

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
        setup_plan=setup_plan,
        strategy=strategy,
        trader_analysis=trader_analysis,
        market_regime=market_regime,
        tuned_market_regime=tuned_market_regime,
        regime_tuning_evidence=regime_tuning_evidence,
        score_summary=score_summary,
        execution_intelligence=execution_intelligence,
        confidence_calibration=confidence_calibration,
        current_strategy_rating=current_strategy_rating,
        current_setup_rating=current_setup_rating,
    )
