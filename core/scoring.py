"""Transparent confidence score composed from independent signals."""


def score_confidence(
    *,
    aligned_bias: bool,
    at_key_level: bool,
    rsi_supportive: bool,
    candle_confirmed: bool,
    structure_modifier: float = 0.0,
    alignment_score: float | None = None,
) -> float:
    score = 2.0
    if alignment_score is None:
        score += 2.5 if aligned_bias else 0.0
    else:
        bounded_alignment = max(0.0, min(alignment_score, 100.0))
        score += ((bounded_alignment - 50.0) / 50.0) * 2.5
    score += 2.0 if at_key_level else 0.0
    score += 1.5 if rsi_supportive else 0.0
    score += 2.0 if candle_confirmed else 0.0
    score += structure_modifier
    return round(max(0.0, min(score, 10.0)), 1)
