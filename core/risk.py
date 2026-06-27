"""Derive illustrative levels; no order sizing or execution occurs here."""


def build_risk_levels(
    bias: str, support: tuple[float, float], resistance: tuple[float, float]
) -> tuple[str, str, str]:
    if bias == "bearish":
        entry = resistance
        stop = resistance[1] + (resistance[1] - resistance[0])
        target = support[1]
    else:
        entry = support
        stop = support[0] - (support[1] - support[0])
        target = resistance[0]
    return f"{entry[0]:.0f}-{entry[1]:.0f}", f"{stop:.0f}", f"{target:.0f}"
