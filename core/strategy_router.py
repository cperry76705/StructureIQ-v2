"""Select a basic setup and proposed action from structure context."""


def route_strategy(bias: str, structure: str, price_near_level: bool, confirmed: bool) -> tuple[str, str]:
    if bias == "ranging":
        return "no_trade", "range_no_edge"

    side = "bullish" if bias == "bullish" else "bearish"
    level = "support" if bias == "bullish" else "resistance"
    setup = f"{side}_pullback_to_{level}" if structure == "pullback" else f"{side}_continuation"

    if not price_near_level or structure != "pullback":
        return "wait", setup
    if not confirmed:
        return "wait", setup
    return ("buy" if bias == "bullish" else "sell"), setup
