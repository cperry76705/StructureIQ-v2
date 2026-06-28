"""Legacy setup router retained for compatibility.

The primary analysis path uses :mod:`core.setup_engine` for typed setup
qualification and no longer uses this helper to plan setups.
"""


def route_strategy(
    bias: str,
    structure: str,
    price_near_level: bool,
    confirmed: bool,
    *,
    alignment: str | None = None,
    current_trend: str | None = None,
) -> tuple[str, str]:
    if bias == "ranging":
        return "no_trade", "range_no_edge"

    side = "bullish" if bias == "bullish" else "bearish"
    level = "support" if bias == "bullish" else "resistance"
    setup = f"{side}_pullback_to_{level}" if structure == "pullback" else f"{side}_continuation"

    if alignment in {"conflicting", "unclear"}:
        return "wait", setup
    if alignment == "mixed" and current_trend != bias:
        return "wait", setup
    if not price_near_level or structure != "pullback":
        return "wait", setup
    if not confirmed:
        return "wait", setup
    return ("buy" if bias == "bullish" else "sell"), setup
