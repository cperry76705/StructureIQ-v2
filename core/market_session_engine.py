"""Market session awareness for deciding which configured symbols to analyze.

This module is intentionally a pre-analysis gate. It never changes strategy,
scoring, setup detection, risk, lifecycle, brokerage, or execution behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from enum import Enum
from typing import Iterable


class AssetClass(str, Enum):
    CRYPTO = "CRYPTO"
    FOREX = "FOREX"
    US_EQUITY = "US_EQUITY"
    ETF = "ETF"
    INDEX = "INDEX"
    FUTURES = "FUTURES"
    UNKNOWN = "UNKNOWN"


class MarketSessionStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    PRE_MARKET = "PRE_MARKET"
    POST_MARKET = "POST_MARKET"
    HOLIDAY = "HOLIDAY"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class MarketSession:
    asset_class: AssetClass
    status: MarketSessionStatus
    as_of: str
    next_open: str | None
    next_close: str | None
    human_readable_summary: str


@dataclass(frozen=True)
class SymbolSession:
    symbol: str
    asset_class: AssetClass
    status: MarketSessionStatus
    active: bool
    skipped: bool
    reason: str | None
    next_open: str | None


@dataclass(frozen=True)
class ActiveWatchlist:
    configured_symbols: tuple[str, ...]
    active_symbols: tuple[str, ...]
    skipped_symbols: tuple[str, ...]
    reasons: dict[str, str]
    symbol_sessions: tuple[SymbolSession, ...]
    markets_configured: int
    markets_open: int
    markets_closed: int
    markets_skipped: int
    human_readable_summary: str


CRYPTO_BASES = {"BTC", "ETH", "SOL", "XRP", "ADA", "DOGE", "LTC", "BCH", "AVAX", "LINK", "DOT", "MATIC"}
FOREX_BASES = {"EUR", "GBP", "USD", "JPY", "CHF", "CAD", "AUD", "NZD"}
ETF_SYMBOLS = {"SPY", "QQQ", "IWM", "DIA", "TLT", "GLD", "SLV", "USO"}
INDEX_SYMBOLS = {"^GSPC", "^DJI", "^IXIC", "^RUT", "SPX", "NDX", "DJI"}


def classify_symbol(symbol: str) -> AssetClass:
    """Classify a configured market symbol into one supported asset class."""

    normalized = symbol.strip().upper()
    if not normalized:
        return AssetClass.UNKNOWN
    if normalized in INDEX_SYMBOLS:
        return AssetClass.INDEX
    if normalized in ETF_SYMBOLS:
        return AssetClass.ETF
    if normalized.endswith("=F") or normalized.startswith(("/", "M")) and len(normalized) >= 3:
        return AssetClass.FUTURES
    if "-" in normalized:
        base, quote = normalized.split("-", 1)
        if base in CRYPTO_BASES and quote in {"USD", "USDT", "USDC"}:
            return AssetClass.CRYPTO
        if base in FOREX_BASES and quote in FOREX_BASES:
            return AssetClass.FOREX
    if normalized.endswith("USD") and normalized[:-3] in CRYPTO_BASES:
        return AssetClass.CRYPTO
    if len(normalized) == 6 and normalized[:3] in FOREX_BASES and normalized[3:] in FOREX_BASES:
        return AssetClass.FOREX
    if normalized.isalpha() and 1 <= len(normalized) <= 5:
        return AssetClass.US_EQUITY
    return AssetClass.UNKNOWN


class MarketSessionEngine:
    """Compute tradability for configured symbols using timezone-safe clocks."""

    def __init__(self, *, clock=None) -> None:
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def sessions(self, as_of: datetime | None = None) -> dict[str, MarketSession]:
        now = _utc(as_of or self.clock())
        return {
            "crypto": self.session_for_asset_class(AssetClass.CRYPTO, now),
            "forex": self.session_for_asset_class(AssetClass.FOREX, now),
        }

    def session_for_asset_class(self, asset_class: AssetClass, as_of: datetime | None = None) -> MarketSession:
        now = _utc(as_of or self.clock())
        if asset_class == AssetClass.CRYPTO:
            return MarketSession(
                asset_class=asset_class,
                status=MarketSessionStatus.OPEN,
                as_of=now.isoformat(),
                next_open=None,
                next_close=None,
                human_readable_summary="Crypto markets are treated as open 24/7.",
            )
        if asset_class == AssetClass.FOREX:
            return self._forex_session(now)
        return MarketSession(
            asset_class=asset_class,
            status=MarketSessionStatus.UNKNOWN,
            as_of=now.isoformat(),
            next_open=None,
            next_close=None,
            human_readable_summary=f"{asset_class.value} session rules are not configured yet.",
        )

    def active_watchlist(
        self,
        symbols: Iterable[str],
        *,
        auto_market_sessions: bool = True,
        ignore_market_sessions: bool = False,
        as_of: datetime | None = None,
    ) -> ActiveWatchlist:
        configured = tuple(symbol.strip().upper() for symbol in symbols if symbol and symbol.strip())
        if ignore_market_sessions or not auto_market_sessions:
            sessions = tuple(
                SymbolSession(symbol=symbol, asset_class=classify_symbol(symbol), status=MarketSessionStatus.OPEN, active=True, skipped=False, reason=None, next_open=None)
                for symbol in configured
            )
        else:
            now = _utc(as_of or self.clock())
            rows: list[SymbolSession] = []
            for symbol in configured:
                asset_class = classify_symbol(symbol)
                session = self.session_for_asset_class(asset_class, now)
                active = session.status in {MarketSessionStatus.OPEN, MarketSessionStatus.PRE_MARKET}
                reason = None if active else _skip_reason(asset_class, session.status)
                rows.append(SymbolSession(
                    symbol=symbol,
                    asset_class=asset_class,
                    status=session.status,
                    active=active,
                    skipped=not active,
                    reason=reason,
                    next_open=session.next_open,
                ))
            sessions = tuple(rows)
        active_symbols = tuple(item.symbol for item in sessions if item.active)
        skipped_symbols = tuple(item.symbol for item in sessions if item.skipped)
        return ActiveWatchlist(
            configured_symbols=configured,
            active_symbols=active_symbols,
            skipped_symbols=skipped_symbols,
            reasons={item.symbol: str(item.reason) for item in sessions if item.reason},
            symbol_sessions=sessions,
            markets_configured=len(configured),
            markets_open=len(active_symbols),
            markets_closed=len(skipped_symbols),
            markets_skipped=len(skipped_symbols),
            human_readable_summary=f"{len(active_symbols)} of {len(configured)} configured markets are currently open for analysis.",
        )

    def _forex_session(self, now_utc: datetime) -> MarketSession:
        local = _central_from_utc(now_utc)
        open_now = _forex_open_local(local)
        next_open_local = _next_forex_open(local)
        next_close_local = _next_forex_close(local) if open_now else None
        status = MarketSessionStatus.OPEN if open_now else MarketSessionStatus.CLOSED
        return MarketSession(
            asset_class=AssetClass.FOREX,
            status=status,
            as_of=now_utc.isoformat(),
            next_open=_central_local_to_utc(next_open_local).isoformat() if next_open_local else None,
            next_close=_central_local_to_utc(next_close_local).isoformat() if next_close_local else None,
            human_readable_summary=(
                "Forex is open from Sunday 5 PM Central through Friday 4 PM Central."
                if open_now
                else "Forex is closed until the next Sunday 5 PM Central open."
            ),
        )


def _forex_open_local(local: datetime) -> bool:
    weekday = local.weekday()  # Monday=0, Sunday=6
    current = local.time()
    if weekday in {0, 1, 2, 3}:
        return True
    if weekday == 4:
        return current < time(16, 0)
    if weekday == 6:
        return current >= time(17, 0)
    return False


def _next_forex_open(local: datetime) -> datetime:
    if _forex_open_local(local):
        return local
    weekday = local.weekday()
    if weekday == 6 and local.time() < time(17, 0):
        days_ahead = 0
    else:
        days_ahead = (6 - weekday) % 7
        if days_ahead == 0:
            days_ahead = 7
    target = (local + timedelta(days=days_ahead)).date()
    return datetime.combine(target, time(17, 0))


def _next_forex_close(local: datetime) -> datetime:
    days_ahead = (4 - local.weekday()) % 7
    target = (local + timedelta(days=days_ahead)).date()
    close = datetime.combine(target, time(16, 0))
    if close <= local.replace(tzinfo=None):
        close += timedelta(days=7)
    return close


def _central_from_utc(value: datetime) -> datetime:
    utc = _utc(value)
    local_standard = (utc + timedelta(hours=-6)).replace(tzinfo=None)
    local_daylight = (utc + timedelta(hours=-5)).replace(tzinfo=None)
    local = local_daylight if _is_central_dst_local(local_daylight) else local_standard
    return local


def _central_local_to_utc(local: datetime) -> datetime:
    naive = local.replace(tzinfo=None)
    offset = -5 if _is_central_dst_local(naive) else -6
    return naive.replace(tzinfo=timezone(timedelta(hours=offset))).astimezone(timezone.utc)


def _is_central_dst_local(local: datetime) -> bool:
    """US Central daylight time: second Sunday in March through first Sunday in November."""

    year = local.year
    start = datetime.combine(_nth_weekday(year, 3, 6, 2), time(2, 0))
    end = datetime.combine(_nth_weekday(year, 11, 6, 1), time(2, 0))
    return start <= local < end


def _nth_weekday(year: int, month: int, weekday: int, n: int):
    from datetime import date
    first = date(year, month, 1)
    days = (weekday - first.weekday()) % 7 + (n - 1) * 7
    return first + timedelta(days=days)


def _skip_reason(asset_class: AssetClass, status: MarketSessionStatus) -> str:
    if asset_class == AssetClass.FOREX and status == MarketSessionStatus.CLOSED:
        return "Forex Market Closed"
    if status == MarketSessionStatus.CLOSED:
        return "Market Closed"
    return f"Market Session {status.value}"


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


_GLOBAL_MARKET_SESSION_ENGINE: MarketSessionEngine | None = None


def get_global_market_session_engine() -> MarketSessionEngine:
    global _GLOBAL_MARKET_SESSION_ENGINE
    if _GLOBAL_MARKET_SESSION_ENGINE is None:
        _GLOBAL_MARKET_SESSION_ENGINE = MarketSessionEngine()
    return _GLOBAL_MARKET_SESSION_ENGINE
