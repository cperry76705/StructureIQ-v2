from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app, get_research_engine
from core.backtesting import BacktestTrade, TradeOutcomeDiagnostics
from core.decision_engine import DecisionDiagnostics
from core.journal import TradeOutcome
from core.regime import MarketRegime, RegimeResult
from core.research_engine import ResearchEngine, ResearchWindow
from core.research_scheduler import ResearchScheduler


NOW = datetime(2026, 6, 29, 18, tzinfo=timezone.utc)


def _trade(
    symbol: str,
    realized_r: float,
    *,
    setup: str = "bearish_bos_retest",
    strategy: str = "breakout_continuation",
    timeframe: str = "5m",
    confidence: float = 78.0,
    hour: int = 14,
) -> BacktestTrade:
    outcome = TradeOutcome.WIN if realized_r > 0 else TradeOutcome.LOSS
    return BacktestTrade(
        timestamp=int(datetime(2026, 6, 29, hour, tzinfo=timezone.utc).timestamp()),
        symbol=symbol,
        timeframe=timeframe,
        higher_timeframe="1h",
        action="sell",
        setup_type=setup,
        strategy_type=strategy,
        entry=100.0,
        stop_loss=101.0,
        target=98.0,
        estimated_risk_reward=2.0,
        outcome=outcome,
        realized_r=realized_r,
        reason="Synthetic continuous research trade.",
        decision_diagnostics=DecisionDiagnostics(
            raw_score=confidence,
            final_confidence=confidence,
            intended_direction="bearish",
            confidence_band="tradable",
            blocked_by=(),
            gate_results=(),
            human_readable_summary="Synthetic diagnostics.",
        ),
        market_regime=RegimeResult(
            MarketRegime.STRONG_BEAR_TREND,
            82.0,
            ("Synthetic bearish regime.",),
            "Synthetic bearish regime.",
        ),
        outcome_diagnostics=TradeOutcomeDiagnostics(
            outcome=outcome,
            realized_r=realized_r,
            entry_price=100.0,
            stop_loss=101.0,
            target=98.0,
            first_touch="target" if outcome is TradeOutcome.WIN else "stop",
            bars_to_outcome=3,
            max_favorable_excursion_r=max(realized_r, 0.4),
            max_adverse_excursion_r=0.3 if outcome is TradeOutcome.WIN else 1.0,
            direction_was_correct_initially=outcome is TradeOutcome.WIN,
            loss_reason=None if outcome is TradeOutcome.WIN else "no_follow_through",
            human_readable_summary="Synthetic outcome.",
        ),
    )


def _engine() -> ResearchEngine:
    return ResearchEngine(clock=lambda: NOW)


def test_research_status_and_rankings_refresh_from_completed_records() -> None:
    engine = _engine()
    engine.ingest([_trade("BTC-USD", 1.0), _trade("EUR-USD", 3.0)])

    status = engine.snapshot().status
    rankings = engine.snapshot().rankings

    assert status.best_symbol == "EUR-USD"
    assert status.best_setup == "bearish_bos_retest"
    assert status.best_market_regime == "strong_bear_trend"
    assert "EUR-USD 5m" in status.latest_research_status_statement
    assert any(item.dimension == "symbol" for item in rankings.rankings)


def test_rankings_update_and_weak_combinations_are_identified() -> None:
    engine = _engine()
    engine.ingest([_trade("BTC-USD", 1.0), _trade("EUR-USD", -1.0)])
    first = engine.snapshot()
    engine.ingest([_trade("EUR-USD", 5.0)])
    second = engine.snapshot()

    assert first.status.best_symbol == "BTC-USD"
    assert second.status.best_symbol == "EUR-USD"
    assert second.weakest_combinations
    assert second.weakest_combinations[0].performance.expectancy <= (
        second.best_combinations[0].performance.expectancy
    )


def test_small_samples_emit_warnings_and_scheduler_is_disabled_by_default() -> None:
    engine = _engine()
    engine.ingest([_trade("BTC-USD", 2.0)])
    scheduler = ResearchScheduler(engine)

    assert engine.snapshot().status.insufficient_sample_warnings
    assert scheduler.is_running is False
    assert scheduler.refresh_count == 0


def test_rolling_and_custom_windows_use_latest_completed_trades() -> None:
    engine = _engine()
    engine.ingest(
        [_trade("BTC-USD", 1.0) for _ in range(60)]
        + [_trade("EUR-USD", -1.0) for _ in range(250)]
    )

    latest_250 = engine.snapshot(ResearchWindow.LAST_250)
    latest_40 = engine.snapshot(ResearchWindow.CUSTOM, 40)

    assert latest_250.status.records_seen == 250
    assert latest_250.status.best_symbol == "EUR-USD"
    assert latest_40.status.records_seen == 40
    assert latest_40.status.custom_lookback == 40


def test_research_endpoints_return_expected_structures() -> None:
    engine = _engine()
    engine.ingest([_trade("EUR-USD", 2.0), _trade("GBP-USD", -1.0)])
    app.dependency_overrides[get_research_engine] = lambda: engine
    try:
        client = TestClient(app)
        status = client.get("/research/status")
        rankings = client.get("/research/rankings")
        best = client.get("/research/best-combinations")
        weakest = client.get("/research/weakest-combinations")
        refresh = client.post(
            "/research/refresh",
            json={"window": "custom", "custom_lookback": 1},
        )
    finally:
        app.dependency_overrides.clear()

    assert status.status_code == rankings.status_code == 200
    assert best.status_code == weakest.status_code == refresh.status_code == 200
    assert "latest_research_status_statement" in status.json()
    assert "rankings" in rankings.json()
    assert best.json()[0]["performance"]["last_updated"]
    assert weakest.json()
    assert refresh.json()["records_seen"] == 1


def test_refresh_is_read_only_and_invalid_custom_query_is_useful() -> None:
    trade = _trade("BTC-USD", 2.0)
    engine = _engine()
    engine.ingest([trade])
    before = trade
    engine.refresh()

    app.dependency_overrides[get_research_engine] = lambda: engine
    try:
        response = TestClient(app).get("/research/status?window=custom")
    finally:
        app.dependency_overrides.clear()

    assert trade == before
    assert response.status_code == 422
    assert "custom_lookback" in response.json()["detail"]
