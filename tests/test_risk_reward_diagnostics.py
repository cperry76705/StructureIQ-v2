"""Focused risk/reward geometry and distribution diagnostics."""

from core.backtesting import (
    BacktestTrade,
    calculate_risk_reward_summary,
    calculate_setup_level_summary,
)
from core.calibration import _risk_and_level_recommendations
from core.journal import TradeOutcome
from core.risk import (
    RiskRewardFailureReason,
    diagnose_risk_reward,
)


def _diagnose(
    direction: str = "bullish",
    entry: str | None = "100",
    stop: str | None = "95",
    target: str | None = "108",
):
    return diagnose_risk_reward(
        direction=direction,
        entry_zone=entry,
        stop_loss=stop,
        target=target,
    )


def _trade(diagnostics) -> BacktestTrade:
    return BacktestTrade(
        timestamp=1,
        symbol="BTC-USD",
        action="wait",
        setup_type="bullish_pullback_continuation",
        strategy_type="pullback_continuation",
        entry=None,
        stop_loss=None,
        target=None,
        estimated_risk_reward=diagnostics.estimated_r,
        outcome=TradeOutcome.SKIPPED,
        realized_r=None,
        reason="Synthetic diagnostic record.",
        risk_reward_diagnostics=diagnostics,
    )


def test_complete_bullish_risk_reward_passes() -> None:
    result = _diagnose()

    assert result.passed is True
    assert result.risk == 5
    assert result.reward == 8
    assert result.estimated_r == 1.6


def test_complete_bearish_risk_reward_passes() -> None:
    result = _diagnose("bearish", "100", "105", "92")

    assert result.passed is True
    assert result.estimated_r == 1.6


def test_missing_levels_are_classified_individually() -> None:
    assert _diagnose(entry=None).failure_reason is RiskRewardFailureReason.ENTRY_MISSING
    assert _diagnose(stop=None).failure_reason is RiskRewardFailureReason.STOP_MISSING
    assert _diagnose(target=None).failure_reason is RiskRewardFailureReason.TARGET_MISSING


def test_target_too_close_is_classified() -> None:
    result = _diagnose(target="106")

    assert result.estimated_r == 1.2
    assert result.failure_reason is RiskRewardFailureReason.TARGET_TOO_CLOSE


def test_stop_too_wide_is_classified() -> None:
    result = _diagnose(stop="90", target="108")

    assert result.estimated_r == 0.8
    assert result.failure_reason is RiskRewardFailureReason.STOP_TOO_WIDE


def test_invalid_bullish_and_bearish_geometry_are_classified() -> None:
    bullish = _diagnose("bullish", "100", "105", "110")
    bearish = _diagnose("bearish", "100", "95", "90")

    assert bullish.failure_reason is RiskRewardFailureReason.INVALID_PRICE_GEOMETRY
    assert bearish.failure_reason is RiskRewardFailureReason.INVALID_PRICE_GEOMETRY


def test_summary_counts_below_minimum_and_near_threshold_records() -> None:
    trades = [
        _trade(_diagnose(target="106")),
        _trade(_diagnose(target="107")),
        _trade(_diagnose(target="110")),
    ]

    summary = calculate_risk_reward_summary(trades)

    assert summary.below_minimum_r_count == 2
    assert summary.records_near_threshold_1_2_to_1_5 == 2
    assert summary.records_above_1_5 == 1
    assert summary.most_common_failure_reason == "target_too_close"


def test_target_and_near_threshold_failures_produce_specific_recommendations() -> None:
    trades = [
        _trade(_diagnose(target="106")),
        _trade(_diagnose(target="106.5")),
        _trade(_diagnose(target="107")),
    ]

    recommendations = _risk_and_level_recommendations(
        calculate_risk_reward_summary(trades),
        calculate_setup_level_summary(trades),
    )

    assert any("Target distance is too close" in item.message for item in recommendations)
    assert any("1.2R and 1.5R" in item.message for item in recommendations)
