from core.adaptive_strategy_router import AdaptiveStrategyRouterEngine
from core.symbol_profile_engine import SymbolCategoryRanking, SymbolProfile


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
