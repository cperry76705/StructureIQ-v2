from core.scoring import score_confidence


def test_full_confluence_scores_ten() -> None:
    assert score_confidence(
        aligned_bias=True, at_key_level=True, rsi_supportive=True, candle_confirmed=True
    ) == 10.0


def test_base_score_without_confluence() -> None:
    assert score_confidence(
        aligned_bias=False, at_key_level=False, rsi_supportive=False, candle_confirmed=False
    ) == 2.0


def test_partial_confluence_is_additive() -> None:
    assert score_confidence(
        aligned_bias=True, at_key_level=True, rsi_supportive=False, candle_confirmed=False
    ) == 6.5


def test_strong_timeframe_alignment_increases_confidence() -> None:
    score = score_confidence(
        aligned_bias=False,
        at_key_level=False,
        rsi_supportive=False,
        candle_confirmed=False,
        alignment_score=95,
    )

    assert score == 4.2


def test_conflicting_timeframes_decrease_confidence() -> None:
    score = score_confidence(
        aligned_bias=True,
        at_key_level=False,
        rsi_supportive=False,
        candle_confirmed=False,
        alignment_score=20,
    )

    assert score == 0.5
