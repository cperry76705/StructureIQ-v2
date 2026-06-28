"""User-facing to provider-specific symbol normalization."""


_YAHOO_SYMBOLS = {
    "EUR-USD": "EURUSD=X",
    "GBP-USD": "GBPUSD=X",
    "USD-JPY": "USDJPY=X",
    "AUD-USD": "AUDUSD=X",
    "USD-CAD": "USDCAD=X",
    "USD-CHF": "USDCHF=X",
    "NZD-USD": "NZDUSD=X",
}


def normalize_yahoo_symbol(symbol: str) -> str:
    """Return Yahoo's symbol while safely passing unknown symbols through."""

    normalized = symbol.strip().upper()
    return _YAHOO_SYMBOLS.get(normalized, normalized)


def normalize_symbol(symbol: str, provider: str = "yahoo") -> str:
    """Normalize for a named provider without changing unsupported providers."""

    if provider.strip().lower() == "yahoo":
        return normalize_yahoo_symbol(symbol)
    return symbol.strip().upper()
