from core.backtesting import BacktestTrade, calculate_setup_coverage_summary
from core.journal import TradeOutcome
from core.setup_engine import SetupCandidateDiagnostics


def _candidate(
    setup_type: str,
    *,
    selected: bool = False,
    blocker: str | None = None,
    estimated_r: float | None = 2.0,
    entry: bool = True,
    stop: bool = True,
    target: bool = True,
    valid: bool = True,
) -> SetupCandidateDiagnostics:
    executable = blocker is None
    return SetupCandidateDiagnostics(
        candidate_setup_type=setup_type,
        direction="bullish",
        was_selected=selected,
        candidate_status="confirmed" if executable else "waiting_for_confirmation",
        has_entry=entry,
        has_stop=stop,
        has_target=target,
        has_valid_geometry=valid,
        estimated_r=estimated_r,
        meets_minimum_r=estimated_r is not None and estimated_r >= 1.5,
        blocking_reason=blocker,
        quality_score=90.0 if executable else 60.0,
        human_readable_summary="Synthetic candidate.",
    )


def _trade(*candidates: SetupCandidateDiagnostics) -> BacktestTrade:
    return BacktestTrade(
        timestamp=1,
        symbol="EUR-USD",
        action="buy",
        setup_type="bullish_bos_retest",
        strategy_type="breakout_continuation",
        entry=None,
        stop_loss=None,
        target=None,
        estimated_risk_reward=None,
        outcome=TradeOutcome.SKIPPED,
        realized_r=None,
        reason="Synthetic.",
        setup_candidate_diagnostics=tuple(candidates),
    )


def test_selected_and_missed_executable_candidates_are_counted() -> None:
    summary = calculate_setup_coverage_summary([
        _trade(
            _candidate("bullish_bos_retest", selected=True),
            _candidate("bullish_pullback_continuation"),
        )
    ])

    assert summary.selected_setup_counts == {"bullish_bos_retest": 1}
    assert summary.selected_executable_count == 1
    assert summary.missed_executable_candidate_count == 1
    assert summary.executable_candidate_counts["bullish_pullback_continuation"] == 1


def test_candidate_blockers_are_grouped_without_becoming_executable() -> None:
    summary = calculate_setup_coverage_summary([
        _trade(
            _candidate("bullish_bos_retest", blocker="entry_missing", entry=False),
            _candidate("range_reversal_long", blocker="invalid_geometry", valid=False),
            _candidate(
                "bullish_pullback_continuation",
                blocker="risk_reward_below_minimum",
                estimated_r=1.2,
            ),
        )
    ])

    assert summary.selected_executable_count == 0
    assert summary.missed_executable_candidate_count == 0
    assert summary.executable_candidate_counts == {}
    blockers = {item.setup_type: item.most_common_blocking_reason for item in summary.by_setup_type}
    assert blockers["bullish_bos_retest"] == "entry_missing"
    assert blockers["range_reversal_long"] == "invalid_geometry"
    assert blockers["bullish_pullback_continuation"] == "risk_reward_below_minimum"


def test_candidate_counts_are_aggregated_by_setup_type() -> None:
    summary = calculate_setup_coverage_summary([
        _trade(_candidate("liquidity_sweep_reversal_short")),
        _trade(_candidate("liquidity_sweep_reversal_short", selected=True)),
    ])

    item = summary.by_setup_type[0]
    assert item.candidates_seen == 2
    assert item.selected_count == 1
    assert item.executable_count == 2
    assert item.missed_executable_count == 1
    assert "Only liquidity sweep reversal short" in summary.human_readable_summary
