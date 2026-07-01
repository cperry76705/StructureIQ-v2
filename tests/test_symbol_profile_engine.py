from datetime import datetime, timezone
from math import sin
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app, get_market_data_provider, get_symbol_profile_engine
from core.backtesting import (
    BacktestRequest,
    BacktestResult,
    BacktestTrade,
    calculate_backtest_metrics,
)
from core.calibration import CalibrationEngine, CalibrationRequest
from core.decision_engine import DecisionDiagnostics
from core.journal import TradeOutcome
from core.market_data import Candle
from core.regime import MarketRegime, RegimeResult
from core.strategy_rating_engine import StrategyRatingEngine
from core.symbol_profile_engine import SymbolProfileEngine


NOW = datetime(2026, 6, 30, 12, tzinfo=timezone.utc)


def _trade(
    index: int,
    *,
    symbol="BTC-USD",
    outcome=TradeOutcome.WIN,
    realized_r=1.0,
    strategy="liquidity_sweep_reversal",
    setup="bearish_bos_retest",
    regime=MarketRegime.STRONG_BEAR_TREND,
):
    return SimpleNamespace(
        timestamp=index,
        symbol=symbol,
        outcome=outcome,
        realized_r=realized_r,
        strategy_type=strategy,
        setup_type=setup,
        decision_diagnostics=SimpleNamespace(final_confidence=80.0),
        market_regime=SimpleNamespace(market_regime=regime),
    )


def _history(count=30, **overrides):
    return [
        _trade(
            index,
            outcome=TradeOutcome.WIN if index % 3 else TradeOutcome.LOSS,
            realized_r=2.0 if index % 3 else -1.0,
            **overrides,
        )
        for index in range(count)
    ]


def _engine(path):
    return SymbolProfileEngine(path, clock=lambda: NOW)


def test_profile_creation_market_character_and_preferred_categories(tmp_path) -> None:
    engine = _engine(tmp_path / "profiles.json")
    summary = engine.update(_history())
    profile = engine.get_profile("BTC-USD")

    assert summary.updated_symbols == ("BTC-USD",)
    assert profile is not None
    assert profile.total_trades == 30
    assert profile.wins == 20
    assert profile.losses == 10
    assert profile.expectancy == 1.0
    assert profile.market_character == "trending"
    assert profile.preferred_strategy == "liquidity_sweep_reversal"
    assert profile.preferred_setup == "bearish_bos_retest"
    assert profile.strategy_grade is not None
    assert profile.setup_grade is not None
    assert profile.last_updated == NOW.isoformat()


def test_profile_persists_and_merges_across_engine_instances(tmp_path) -> None:
    path = tmp_path / "profiles.json"
    first = _engine(path)
    first.update(_history(15))
    reloaded = _engine(path)
    assert reloaded.get_profile("BTC-USD").total_trades == 15

    reloaded.update(_history(15))
    final = _engine(path).get_profile("BTC-USD")
    assert final is not None
    assert final.total_trades == 30
    assert len(final.strategy_rankings) == 1


def test_insufficient_history_and_unsafe_preference_are_suppressed(tmp_path) -> None:
    engine = _engine(tmp_path / "profiles.json")
    losing = _history(
        10,
        strategy="breakout_continuation",
        setup="compression_breakout_short",
    )
    losing = [
        _trade(
            index,
            outcome=TradeOutcome.LOSS,
            realized_r=-1.0,
            strategy="breakout_continuation",
            setup="compression_breakout_short",
        )
        for index in range(10)
    ]
    engine.update(losing)
    profile = engine.get_profile("BTC-USD")
    view = engine.get_view("BTC-USD")

    assert profile.market_character == "insufficient_data"
    assert profile.preferred_strategy is None
    assert profile.preferred_setup is None
    assert view.status == "unavailable"
    assert view.warning == "Not enough historical calibration data."


def test_symbol_engine_reuses_strategy_rating_engine(monkeypatch, tmp_path) -> None:
    called = 0
    original = StrategyRatingEngine.rate

    def wrapped(self, **kwargs):
        nonlocal called
        called += 1
        return original(self, **kwargs)

    monkeypatch.setattr(StrategyRatingEngine, "rate", wrapped)
    engine = _engine(tmp_path / "profiles.json")
    engine.update(_history())
    engine.get_profile("BTC-USD")

    assert called >= 1


class _Provider:
    def get_candles(self, symbol: str, timeframe: str, lookback: int) -> list[Candle]:
        del symbol, timeframe
        candles = []
        for index in range(320):
            close = 100 + index * 0.08 + sin(index * 0.7) * 2
            candles.append(
                Candle(index, close - 0.2, close + 0.8, close - 0.8, close, 100)
            )
        return candles[-lookback:]


def test_analysis_reads_available_profile_without_changing_action(tmp_path) -> None:
    profiles = _engine(tmp_path / "profiles.json")
    profiles.update(_history())
    app.dependency_overrides[get_market_data_provider] = lambda: _Provider()
    app.dependency_overrides[get_symbol_profile_engine] = lambda: profiles
    request = {
        "symbol": "BTC-USD",
        "timeframe": "5m",
        "higher_timeframe": "1h",
        "lookback": 200,
    }
    try:
        client = TestClient(app)
        first = client.post("/analysis", json=request)
        second = client.post("/analysis", json=request)
    finally:
        app.dependency_overrides.clear()

    assert first.status_code == second.status_code == 200
    profile = first.json()["symbol_profile"]
    assert profile["status"] == "available"
    assert profile["market_character"] == "trending"
    assert profile["preferred_strategy"] == "liquidity_sweep_reversal"
    assert first.json()["action"] == second.json()["action"]


def _backtest_trade() -> BacktestTrade:
    return BacktestTrade(
        timestamp=1,
        symbol="BTC-USD",
        action="sell",
        setup_type="bearish_bos_retest",
        strategy_type="liquidity_sweep_reversal",
        entry=100.0,
        stop_loss=101.0,
        target=98.0,
        estimated_risk_reward=2.0,
        outcome=TradeOutcome.WIN,
        realized_r=2.0,
        reason="Synthetic profile trade.",
        decision_diagnostics=DecisionDiagnostics(
            raw_score=80,
            final_confidence=80,
            intended_direction="bearish",
            confidence_band="tradable",
            blocked_by=(),
            gate_results=(),
            human_readable_summary="Synthetic.",
        ),
        market_regime=RegimeResult(
            MarketRegime.STRONG_BEAR_TREND,
            80,
            ("Synthetic",),
            "Synthetic",
        ),
    )


class _Runner:
    def run(self, request: BacktestRequest) -> BacktestResult:
        trade = _backtest_trade()
        return BacktestResult(
            request=request,
            trades=(trade,),
            metrics=calculate_backtest_metrics([trade]),
            human_readable_summary="Synthetic.",
            limitations=(),
        )


def test_calibration_updates_profile_and_returns_summary(tmp_path) -> None:
    profiles = _engine(tmp_path / "profiles.json")
    engine = CalibrationEngine(
        _Provider(),
        backtesting_engine_factory=lambda provider: _Runner(),
        symbol_profile_engine=profiles,
    )
    result = engine.run(
        CalibrationRequest(
            symbols=["BTC-USD"],
            timeframes=["5m"],
            higher_timeframes=["1h"],
            lookback=100,
            max_trades_per_run=5,
        )
    )

    assert result.symbol_profile_summary is not None
    assert result.aggregate_adaptive_strategy_router_summary is not None
    assert result.symbol_profile_summary.updated_symbols == ("BTC-USD",)
    assert profiles.get_profile("BTC-USD").total_trades == 1
    assert result.aggregate_metrics.total_trades == 1
