from core.strategy_router import route_strategy


def test_mixed_alignment_waits_without_current_direction_confirmation() -> None:
    action, _ = route_strategy(
        "bullish",
        "pullback",
        True,
        True,
        alignment="mixed",
        current_trend="ranging",
    )

    assert action == "wait"


def test_mixed_alignment_can_act_when_current_direction_confirms() -> None:
    action, _ = route_strategy(
        "bullish",
        "pullback",
        True,
        True,
        alignment="mixed",
        current_trend="bullish",
    )

    assert action == "buy"
