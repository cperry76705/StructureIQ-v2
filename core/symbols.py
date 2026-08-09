"""Compatibility wrappers for provider-specific symbol normalization."""

from core.symbol_registry import get_symbol_registry


def normalize_yahoo_symbol(symbol: str) -> str:
    """Return Yahoo's symbol while safely passing unknown symbols through."""

    return get_symbol_registry().provider_symbol(symbol, "yahoo")


def normalize_symbol(symbol: str, provider: str = "yahoo") -> str:
    """Normalize for a named provider without changing unsupported providers."""

    if provider.strip().lower() == "yahoo":
        return normalize_yahoo_symbol(symbol)
    return symbol.strip().upper()
