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
