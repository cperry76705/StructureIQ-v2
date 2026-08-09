"""Centralized trading-universe and provider-symbol registry.

The registry keeps canonical StructureIQ symbols stable internally while
allowing market-data providers to use their own symbol formats.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from core.market_session_engine import AssetClass


@dataclass(frozen=True)
class SymbolRegistryRecord:
    symbol: str
    asset_class: AssetClass
    base_currency: str
    quote_currency: str
    enabled: bool
    provider_symbol: str
    session_profile: str
    pip_precision: int | None
    price_precision: int


@dataclass(frozen=True)
class ProviderSymbolValidation:
    symbol: str
    asset_class: AssetClass
    provider_symbol: str | None
    supported: bool
    validation_status: str
    reason: str


DEFAULT_SYMBOL_RECORDS: tuple[SymbolRegistryRecord, ...] = (
    SymbolRegistryRecord("BTC-USD", AssetClass.CRYPTO, "BTC", "USD", True, "BTC-USD", "crypto_24_7", None, 2),
    SymbolRegistryRecord("ETH-USD", AssetClass.CRYPTO, "ETH", "USD", True, "ETH-USD", "crypto_24_7", None, 2),
    SymbolRegistryRecord("EUR-USD", AssetClass.FOREX, "EUR", "USD", True, "EURUSD=X", "forex_central", 4, 5),
    SymbolRegistryRecord("GBP-USD", AssetClass.FOREX, "GBP", "USD", True, "GBPUSD=X", "forex_central", 4, 5),
    SymbolRegistryRecord("USD-JPY", AssetClass.FOREX, "USD", "JPY", True, "USDJPY=X", "forex_central", 2, 3),
    SymbolRegistryRecord("USD-CHF", AssetClass.FOREX, "USD", "CHF", True, "USDCHF=X", "forex_central", 4, 5),
    SymbolRegistryRecord("USD-CAD", AssetClass.FOREX, "USD", "CAD", True, "USDCAD=X", "forex_central", 4, 5),
    SymbolRegistryRecord("AUD-USD", AssetClass.FOREX, "AUD", "USD", True, "AUDUSD=X", "forex_central", 4, 5),
    SymbolRegistryRecord("NZD-USD", AssetClass.FOREX, "NZD", "USD", True, "NZDUSD=X", "forex_central", 4, 5),
)


DEFAULT_SYMBOL_UNIVERSE: tuple[str, ...] = tuple(record.symbol for record in DEFAULT_SYMBOL_RECORDS if record.enabled)


class SymbolRegistry:
    """Read-only registry for default symbols and deterministic provider mappings."""

    def __init__(self, records: Iterable[SymbolRegistryRecord] = DEFAULT_SYMBOL_RECORDS) -> None:
        self._records = {record.symbol: record for record in records}

    def default_symbols(self) -> tuple[str, ...]:
        return tuple(record.symbol for record in self._records.values() if record.enabled)

    def get(self, symbol: str) -> SymbolRegistryRecord | None:
        return self._records.get(_canonical(symbol))

    def classify(self, symbol: str) -> AssetClass:
        record = self.get(symbol)
        return record.asset_class if record else AssetClass.UNKNOWN

    def provider_symbol(self, symbol: str, provider: str = "yahoo") -> str:
        normalized = _canonical(symbol)
        record = self.get(normalized)
        if provider.strip().lower() == "yahoo" and record is not None:
            return record.provider_symbol
        return normalized

    def validate_provider_symbol(self, symbol: str, provider: str = "yahoo") -> ProviderSymbolValidation:
        normalized = _canonical(symbol)
        record = self.get(normalized)
        if record is None:
            return ProviderSymbolValidation(
                symbol=normalized,
                asset_class=AssetClass.UNKNOWN,
                provider_symbol=None,
                supported=False,
                validation_status="UNKNOWN_SYMBOL",
                reason="Symbol is not registered in the StructureIQ symbol registry.",
            )
        provider_name = provider.strip().lower()
        if provider_name != "yahoo":
            return ProviderSymbolValidation(
                symbol=record.symbol,
                asset_class=record.asset_class,
                provider_symbol=record.symbol,
                supported=False,
                validation_status="FUTURE_PROVIDER",
                reason=f"{provider} provider mapping is reserved for future implementation.",
            )
        return ProviderSymbolValidation(
            symbol=record.symbol,
            asset_class=record.asset_class,
            provider_symbol=record.provider_symbol,
            supported=bool(record.provider_symbol),
            validation_status="SUPPORTED" if record.provider_symbol else "UNSUPPORTED",
            reason="Deterministic Yahoo Finance mapping is configured." if record.provider_symbol else "Provider symbol is missing.",
        )

    def validate_provider_symbols(
        self,
        symbols: Iterable[str] | None = None,
        provider: str = "yahoo",
    ) -> tuple[ProviderSymbolValidation, ...]:
        return tuple(self.validate_provider_symbol(symbol, provider) for symbol in (symbols or self.default_symbols()))


def get_symbol_registry() -> SymbolRegistry:
    return SymbolRegistry()


def _canonical(symbol: str) -> str:
    return str(symbol or "").strip().upper()

