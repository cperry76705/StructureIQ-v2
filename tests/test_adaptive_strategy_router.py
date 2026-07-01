from fastapi.testclient import TestClient

from app.main import app, get_market_data_provider, get_symbol_profile_engine
from core.adaptive_strategy_router import AdaptiveStrategyRouterEngine
from core.market_data import Candle
from core.symbol_profile_engine import SymbolCategoryRanking, SymbolProfile
from core.symbol_profile_engine import SymbolProfileEngine


def _row(name: str, sample_size: int = 30, score: float = 78.0) -> SymbolCategoryRanking:
    return SymbolCategoryRanking(
        name=name,
        grade="A",
        rating_score=score,
        sample_size=sample_size,
        win_rate=60.0,
        expectancy=1.2,
        average_r=1.2,
        total_r=36.0,
        profit_factor=2.0,
        max_drawdown=4.0,
    )


def _profile(sample_size: int = 30) -> SymbolProfile:
    return SymbolProfile(
        symbol="BTC-USD",
        total_trades=sample_size,
        wins=18,
        losses=12,
        win_rate=60.0,
        expectancy=1.2,
        average_r=1.2,
        total_r=36.0,
        profit_factor=2.0,
        max_drawdown=4.0,
        confidence=82.0,
        sample_size=sample_size,
        market_character="trending",
        preferred_strategy="trend_continuation",
        preferred_setup="bearish_bos_retest",
        strategy_grade="A",
        setup_grade="A",
        last_updated="2026-06-30T00:00:00+00:00",
        strategy_rankings=(_row("trend_continuation", sample_size),),
        setup_rankings=(_row("bearish_bos_retest", sample_size),),
    )


def _analyze(**overrides):
    values = {
        "symbol": "BTC-USD",
        "production_setup": "bearish_bos_retest",
        "production_strategy": "trend_continuation",
        "action": "sell",
        "symbol_profile": _profile(),
    }
    values.update(overrides)
    return AdaptiveStrategyRouterEngine().analyze(**values)


def test_missing_profile_is_unavailable() -> None:
    result = _analyze(symbol_profile=None)
    assert result.status == "unavailable"
    assert result.routing_alignment == "unavailable"


def test_no_trade_never_suggests_execution() -> None:
    result = _analyze(action="no_trade")
    assert result.status == "no_trade"
    assert result.routing_alignment == "unavailable"
    assert "No execution route is suggested" in result.warnings[0]


def test_matching_strategy_is_aligned() -> None:
    result = _analyze()
    assert result.status == "available"
    assert result.routing_alignment == "aligned"


def test_matching_setup_with_different_strategy_is_partially_aligned() -> None:
    result = _analyze(production_strategy="range_reversal")
    assert result.routing_alignment == "partially_aligned"


def test_different_route_with_sufficient_sample_is_misaligned() -> None:
    result = _analyze(
        production_strategy="range_reversal",
        production_setup="range_reversal_short",
    )
    assert result.routing_alignment == "misaligned"
    assert result.production_strategy == "range_reversal"


def test_low_sample_preferred_route_is_flagged() -> None:
    result = _analyze(symbol_profile=_profile(19))
    assert result.status == "insufficient_sample"
    assert result.routing_alignment == "unavailable"
    assert "fewer than 20" in result.warnings[0]


def test_aggregate_summary_counts_alignment_and_misalignment() -> None:
    engine = AdaptiveStrategyRouterEngine()
    results = (
        _analyze(),
        _analyze(production_strategy="range_reversal"),
        _analyze(
            production_strategy="range_reversal",
            production_setup="range_reversal_short",
        ),
        _analyze(symbol_profile=None),
    )
    summary = engine.summarize(results)
    assert summary.aligned_count == 1
    assert summary.partially_aligned_count == 1
    assert summary.misaligned_count == 1
    assert summary.unavailable_count == 1
    assert summary.strongest_profile_preferred_strategy == "trend_continuation"


class _HttpProvider:
    def get_candles(self, symbol: str, timeframe: str, lookback: int) -> list[Candle]:
        del symbol, timeframe
        return [
            Candle(index, 100.0, 101.0, 99.0, 100.0, 100.0)
            for index in range(60)
        ][-lookback:]


def _http_client() -> TestClient:
    profiles = SymbolProfileEngine(path=None)
    app.dependency_overrides[get_market_data_provider] = lambda: _HttpProvider()
    app.dependency_overrides[get_symbol_profile_engine] = lambda: profiles
    return TestClient(app)


def test_analysis_http_response_serializes_unavailable_router() -> None:
    client = _http_client()
    try:
        response = client.post(
            "/analysis",
            json={
                "symbol": "BTC-USD",
                "timeframe": "5m",
                "higher_timeframe": "1h",
                "lookback": 60,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert "adaptive_strategy_router" in payload
    assert payload["adaptive_strategy_router"] is not None
    assert payload["adaptive_strategy_router"]["status"] == "unavailable"
    assert payload["adaptive_strategy_router"]["routing_alignment"] == "unavailable"


def test_calibration_http_response_serializes_aggregate_router_summary() -> None:
    client = _http_client()
    try:
        response = client.post(
            "/calibrate",
            json={
                "symbols": ["BTC-USD"],
                "timeframes": ["5m"],
                "higher_timeframes": ["1h"],
                "lookback": 60,
                "max_trades_per_run": 1,
                "risk_per_trade_percent": 1,
                "starting_balance": 10000,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert "aggregate_adaptive_strategy_router_summary" in payload
    summary = payload["aggregate_adaptive_strategy_router_summary"]
    assert summary is not None
    assert summary["unavailable_count"] == 1
    assert "Production routing was not changed" in summary["human_readable_summary"]


def test_openapi_exposes_both_adaptive_router_fields() -> None:
    schemas = TestClient(app).get("/openapi.json").json()["components"]["schemas"]
    assert "adaptive_strategy_router" in schemas["AnalysisResponse"]["properties"]
    assert (
        "aggregate_adaptive_strategy_router_summary"
        in schemas["CalibrationResult"]["properties"]
    )
