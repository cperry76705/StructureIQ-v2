"""In-memory, advisory-only paper brokerage and account simulation."""

from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from core.backtesting import parse_price_level


class PaperBrokerageError(ValueError):
    """A paper order failed deterministic validation or account risk checks."""


class PaperAccountConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    starting_balance: float = Field(default=10_000.0, gt=0)
    risk_per_trade_percent: float = Field(default=1.0, gt=0)
    max_risk_per_trade_percent: float = Field(default=2.0, gt=0)
    max_daily_loss_percent: float = Field(default=5.0, gt=0)
    max_daily_profit_lock_percent: float = Field(default=8.0, gt=0)
    max_open_positions: int = Field(default=3, ge=1)
    allow_duplicate_symbol_positions: bool = False
    allow_duplicate_setup_positions: bool = False
    persistence_path: str | None = None
    durable_state: bool = False
    persistence_dir: str = "research"

    @model_validator(mode="after")
    def validate_default_risk(self) -> "PaperAccountConfig":
        if self.risk_per_trade_percent > self.max_risk_per_trade_percent:
            raise ValueError("risk_per_trade_percent cannot exceed its maximum")
        return self


class PaperOpenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str | None = None
    source_event_id: str | None = None
    symbol: str | None = None
    timeframe: str | None = None
    higher_timeframe: str | None = None
    action: Literal["buy", "sell"] | None = None
    setup: str | None = None
    strategy: str | None = None
    entry_price: float | None = None
    stop_loss: float | None = None
    target: float | None = None
    risk_per_trade_percent: float | None = Field(default=None, gt=0)
    allow_duplicate: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_source(self) -> "PaperOpenRequest":
        explicit = (
            self.symbol, self.timeframe, self.higher_timeframe, self.action,
            self.setup, self.strategy, self.entry_price, self.stop_loss, self.target,
        )
        if self.event_id:
            if any(item is not None for item in explicit):
                raise ValueError("event_id cannot be combined with explicit trade fields")
            return self
        if any(item is None for item in explicit):
            raise ValueError("explicit paper trades require symbol, timeframes, action, setup, strategy, entry, stop, and target")
        return self


class PaperCloseRequest(BaseModel):
    trade_id: str
    exit_price: float = Field(gt=0)


@dataclass(frozen=True)
class PaperTrade:
    trade_id: str
    source_event_id: str | None
    symbol: str
    timeframe: str
    higher_timeframe: str
    action: str
    setup: str
    strategy: str
    entry_price: float
    stop_loss: float
    target: float
    target_r: float
    risk_amount: float
    risk_per_trade_percent: float
    position_size: float
    status: str
    opened_at: str
    closed_at: str | None
    exit_price: float | None
    realized_r: float | None
    realized_pl: float | None
    unrealized_r: float
    unrealized_pl: float
    metadata: dict[str, Any]


@dataclass(frozen=True)
class PaperAccount:
    starting_balance: float
    balance: float
    equity: float
    unrealized_pl: float
    realized_pl: float
    open_positions_count: int
    closed_trades_count: int
    available_risk_capacity: int
    daily_realized_pl: float
    daily_return_percent: float
    paper_total_r: float
    paper_win_rate: float
    paper_max_drawdown: float
    risk_status: str
    paper_trading_enabled: bool
    advisory_only: bool
    config: PaperAccountConfig
    updated_at: str


@dataclass(frozen=True)
class PaperPerformance:
    closed_trades: int
    wins: int
    losses: int
    breakeven: int
    win_rate: float
    total_r: float
    average_r: float
    realized_pl: float
    profit_factor: float | None
    max_drawdown: float
    human_readable_summary: str


class PaperBrokerageEngine:
    """Maintain paper positions without any live-broker or automatic-trading path."""

    def __init__(self, config: PaperAccountConfig | None = None) -> None:
        self.config = config or PaperAccountConfig()
        self._lock = threading.RLock()
        self._listeners: list[Any] = []
        if self.config.durable_state:
            self._load_or_initialize()
        else:
            self.reset(self.config)

    def add_listener(self, listener: Any) -> None:
        """Register an advisory observer without transferring account authority."""
        with self._lock:
            if listener not in self._listeners:
                self._listeners.append(listener)

    def reset(self, config: PaperAccountConfig | None = None) -> PaperAccount:
        with self._lock:
            if config is not None:
                self.config = config
            self._balance = self.config.starting_balance
            self._open: dict[str, PaperTrade] = {}
            self._closed: list[PaperTrade] = []
            self._daily_date = date.today()
            self._daily_realized_pl = 0.0
            self._peak_balance = self._balance
            self._max_drawdown = 0.0
            self._persist()
            return self.account()

    def recover_from_storage(self) -> PaperAccount:
        """Reload durable paper state from disk without notifying observers."""
        with self._lock:
            if self.config.durable_state:
                self._load_or_initialize()
            return self.account()

    def open_position(self, request: PaperOpenRequest) -> PaperTrade:
        if request.event_id:
            raise PaperBrokerageError("event_id must be resolved through the monitor-aware API")
        return self._open_explicit(request)

    def open_monitor_event(
        self, event: Any, *, risk_per_trade_percent: float | None = None,
        allow_duplicate: bool = False,
    ) -> PaperTrade:
        entry = parse_price_level(getattr(event, "entry_zone", None), midpoint=True)
        stop = parse_price_level(getattr(event, "stop_loss", None))
        target = parse_price_level(getattr(event, "target", None))
        if entry is None or stop is None or target is None:
            raise PaperBrokerageError("monitor event entry, stop, or target could not be parsed")
        metadata = {
            "confidence": getattr(event, "confidence", None),
            "setup_quality": getattr(event, "setup_quality", None),
            "score_summary": getattr(event, "score_summary", None),
            "execution_intelligence": getattr(event, "execution_intelligence", None),
            "confidence_calibration": getattr(event, "confidence_calibration", None),
            "symbol_profile": getattr(event, "symbol_profile", None),
            "adaptive_strategy_router": getattr(event, "adaptive_strategy_router", None),
            "strategy_rating": getattr(event, "strategy_rating", None),
            "setup_rating": getattr(event, "setup_rating", None),
        }
        return self._open_explicit(PaperOpenRequest(
            source_event_id=event.event_id, symbol=event.symbol,
            timeframe=event.timeframe, higher_timeframe=event.higher_timeframe,
            action=event.action, setup=event.setup, strategy=event.strategy,
            entry_price=entry, stop_loss=stop, target=target,
            risk_per_trade_percent=risk_per_trade_percent,
            allow_duplicate=allow_duplicate, metadata=metadata,
        ))

    def _open_explicit(self, request: PaperOpenRequest) -> PaperTrade:
        with self._lock:
            self._roll_daily_state()
            risk_percent = request.risk_per_trade_percent or self.config.risk_per_trade_percent
            self._validate_risk_limits(request, risk_percent)
            entry, stop, target = float(request.entry_price), float(request.stop_loss), float(request.target)
            risk_per_unit, reward_per_unit = _geometry(request.action, entry, stop, target)
            risk_amount = self._balance * risk_percent / 100.0
            position_size = risk_amount / risk_per_unit
            now = _now()
            identity = f"{request.source_event_id}:{request.symbol}:{request.timeframe}:{request.setup}:{now}"
            trade = PaperTrade(
                trade_id=hashlib.sha256(identity.encode()).hexdigest()[:24],
                source_event_id=request.source_event_id,
                symbol=str(request.symbol), timeframe=str(request.timeframe),
                higher_timeframe=str(request.higher_timeframe), action=str(request.action),
                setup=str(request.setup), strategy=str(request.strategy),
                entry_price=entry, stop_loss=stop, target=target,
                target_r=round(reward_per_unit / risk_per_unit, 6),
                risk_amount=round(risk_amount, 6),
                risk_per_trade_percent=round(risk_percent, 6),
                position_size=round(position_size, 8), status="open",
                opened_at=now, closed_at=None, exit_price=None,
                realized_r=None, realized_pl=None, unrealized_r=0.0,
                unrealized_pl=0.0, metadata=dict(request.metadata),
            )
            self._open[trade.trade_id] = trade
            self._persist()
            self._notify("paper_trade_opened", trade)
            return trade

    def close_position(self, trade_id: str, exit_price: float) -> PaperTrade:
        with self._lock:
            self._roll_daily_state()
            trade = self._open.get(trade_id)
            if trade is None:
                raise PaperBrokerageError("open paper trade was not found")
            risk_per_unit = abs(trade.entry_price - trade.stop_loss)
            movement = exit_price - trade.entry_price if trade.action == "buy" else trade.entry_price - exit_price
            realized_r = movement / risk_per_unit
            realized_pl = movement * trade.position_size
            closed = replace(
                trade, status="closed", closed_at=_now(), exit_price=float(exit_price),
                realized_r=round(realized_r, 6), realized_pl=round(realized_pl, 6),
                unrealized_r=0.0, unrealized_pl=0.0,
            )
            del self._open[trade_id]
            self._closed.append(closed)
            self._balance += realized_pl
            self._daily_realized_pl += realized_pl
            self._peak_balance = max(self._peak_balance, self._balance)
            self._max_drawdown = max(self._max_drawdown, self._peak_balance - self._balance)
            self._persist()
            self._notify("paper_trade_closed", closed)
            return closed

    def account(self, latest_prices: dict[str, float] | None = None) -> PaperAccount:
        with self._lock:
            self._mark_to_market(latest_prices or {})
            unrealized = sum(item.unrealized_pl for item in self._open.values())
            performance = self.performance()
            daily_percent = self._daily_realized_pl / self.config.starting_balance * 100
            return PaperAccount(
                starting_balance=self.config.starting_balance,
                balance=round(self._balance, 6), equity=round(self._balance + unrealized, 6),
                unrealized_pl=round(unrealized, 6),
                realized_pl=round(self._balance - self.config.starting_balance, 6),
                open_positions_count=len(self._open), closed_trades_count=len(self._closed),
                available_risk_capacity=max(0, self.config.max_open_positions - len(self._open)),
                daily_realized_pl=round(self._daily_realized_pl, 6),
                daily_return_percent=round(daily_percent, 6),
                paper_total_r=performance.total_r, paper_win_rate=performance.win_rate,
                paper_max_drawdown=round(self._max_drawdown, 6),
                risk_status=self._risk_status(), paper_trading_enabled=False,
                advisory_only=True, config=self.config, updated_at=_now(),
            )

    def open_positions(self, latest_prices: dict[str, float] | None = None) -> tuple[PaperTrade, ...]:
        with self._lock:
            self._mark_to_market(latest_prices or {})
            return tuple(self._open.values())

    def closed_trades(self) -> tuple[PaperTrade, ...]:
        with self._lock:
            return tuple(self._closed)

    def performance(self) -> PaperPerformance:
        with self._lock:
            returns = [item.realized_r or 0.0 for item in self._closed]
            wins = sum(value > 0 for value in returns); losses = sum(value < 0 for value in returns)
            breakeven = len(returns) - wins - losses
            positives = sum(value for value in returns if value > 0); negatives = abs(sum(value for value in returns if value < 0))
            return PaperPerformance(
                closed_trades=len(returns), wins=wins, losses=losses, breakeven=breakeven,
                win_rate=round(wins / len(returns) * 100, 6) if returns else 0.0,
                total_r=round(sum(returns), 6),
                average_r=round(sum(returns) / len(returns), 6) if returns else 0.0,
                realized_pl=round(self._balance - self.config.starting_balance, 6),
                profit_factor=round(positives / negatives, 6) if negatives else None,
                max_drawdown=round(self._max_drawdown, 6),
                human_readable_summary=f"Paper account has {len(returns)} closed trades and {sum(returns):.2f}R total performance.",
            )

    def _validate_risk_limits(self, request: PaperOpenRequest, risk_percent: float) -> None:
        if request.action not in {"buy", "sell"}:
            raise PaperBrokerageError("paper action must be buy or sell")
        if risk_percent > self.config.max_risk_per_trade_percent:
            raise PaperBrokerageError("risk per trade exceeds the configured maximum")
        if len(self._open) >= self.config.max_open_positions:
            raise PaperBrokerageError("maximum open paper positions reached")
        if self._risk_status() != "available":
            raise PaperBrokerageError(f"new paper trades blocked: {self._risk_status()}")
        if not request.allow_duplicate:
            if not self.config.allow_duplicate_symbol_positions and any(item.symbol == request.symbol for item in self._open.values()):
                raise PaperBrokerageError("duplicate open symbol positions are disabled")
            if not self.config.allow_duplicate_setup_positions and any(item.symbol == request.symbol and item.timeframe == request.timeframe and item.setup == request.setup for item in self._open.values()):
                raise PaperBrokerageError("duplicate open setup positions are disabled")

    def _risk_status(self) -> str:
        daily_percent = self._daily_realized_pl / self.config.starting_balance * 100
        if daily_percent <= -self.config.max_daily_loss_percent:
            return "daily_loss_limit_reached"
        if daily_percent >= self.config.max_daily_profit_lock_percent:
            return "daily_profit_lock_reached"
        if len(self._open) >= self.config.max_open_positions:
            return "max_positions_reached"
        return "available"

    def _mark_to_market(self, latest_prices: dict[str, float]) -> None:
        for trade_id, trade in tuple(self._open.items()):
            if trade.symbol not in latest_prices:
                continue
            price = float(latest_prices[trade.symbol])
            movement = price - trade.entry_price if trade.action == "buy" else trade.entry_price - price
            risk = abs(trade.entry_price - trade.stop_loss)
            self._open[trade_id] = replace(
                trade, unrealized_r=round(movement / risk, 6),
                unrealized_pl=round(movement * trade.position_size, 6),
            )

    def _roll_daily_state(self) -> None:
        if date.today() != self._daily_date:
            self._daily_date = date.today()
            self._daily_realized_pl = 0.0

    def _persist(self) -> None:
        payload = {
            "balance": self._balance,
            "equity": self._balance + sum(item.unrealized_pl for item in self._open.values()),
            "realized_pl": self._balance - self.config.starting_balance,
            "unrealized_pl": sum(item.unrealized_pl for item in self._open.values()),
            "total_r": sum(item.realized_r or 0.0 for item in self._closed),
            "risk_per_trade": self.config.risk_per_trade_percent,
            "account_settings": self.config.model_dump(),
            "open_positions": [asdict(item) for item in self._open.values()],
            "closed_trades": [asdict(item) for item in self._closed],
            "daily_date": self._daily_date.isoformat(),
            "daily_realized_pl": self._daily_realized_pl,
            "peak_balance": self._peak_balance,
            "max_drawdown": self._max_drawdown,
            "updated_at": _now(),
        }
        if self.config.persistence_path:
            path = Path(self.config.persistence_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
        if self.config.durable_state:
            root = Path(self.config.persistence_dir)
            root.mkdir(parents=True, exist_ok=True)
            (root / "paper_account.json").write_text(
                json.dumps({k: v for k, v in payload.items() if k not in {"open_positions", "closed_trades"}}, indent=2),
                encoding="utf-8",
            )
            (root / "paper_open_positions.json").write_text(
                json.dumps(payload["open_positions"], indent=2),
                encoding="utf-8",
            )
            (root / "paper_closed_trades.json").write_text(
                json.dumps(payload["closed_trades"], indent=2),
                encoding="utf-8",
            )

    def _load_or_initialize(self) -> None:
        root = Path(self.config.persistence_dir)
        account_path = root / "paper_account.json"
        open_path = root / "paper_open_positions.json"
        closed_path = root / "paper_closed_trades.json"
        root.mkdir(parents=True, exist_ok=True)
        if not account_path.exists():
            self._balance = self.config.starting_balance
            self._open = {}
            self._closed = []
            self._daily_date = date.today()
            self._daily_realized_pl = 0.0
            self._peak_balance = self._balance
            self._max_drawdown = 0.0
            self._persist()
            return
        try:
            account = json.loads(account_path.read_text(encoding="utf-8"))
            raw_open = json.loads(open_path.read_text(encoding="utf-8")) if open_path.exists() else []
            raw_closed = json.loads(closed_path.read_text(encoding="utf-8")) if closed_path.exists() else []
            self._balance = float(account.get("balance", self.config.starting_balance))
            self._open = {
                item["trade_id"]: PaperTrade(**item)
                for item in raw_open
                if isinstance(item, dict) and item.get("trade_id")
            }
            self._closed = [
                PaperTrade(**item)
                for item in raw_closed
                if isinstance(item, dict) and item.get("trade_id")
            ]
            self._daily_date = date.fromisoformat(account.get("daily_date", date.today().isoformat()))
            self._daily_realized_pl = float(account.get("daily_realized_pl", 0.0))
            self._peak_balance = float(account.get("peak_balance", max(self._balance, self.config.starting_balance)))
            self._max_drawdown = float(account.get("max_drawdown", 0.0))
        except (OSError, TypeError, ValueError, KeyError, json.JSONDecodeError):
            self._balance = self.config.starting_balance
            self._open = {}
            self._closed = []
            self._daily_date = date.today()
            self._daily_realized_pl = 0.0
            self._peak_balance = self._balance
            self._max_drawdown = 0.0
            self._persist()

    def _notify(self, event_type: str, trade: PaperTrade) -> None:
        for listener in tuple(self._listeners):
            try:
                listener(event_type, trade, self.account())
            except Exception:
                # Journaling is advisory and must never roll back a valid paper action.
                continue


def _geometry(action: str, entry: float, stop: float, target: float) -> tuple[float, float]:
    if min(entry, stop, target) <= 0:
        raise PaperBrokerageError("entry, stop, and target must be positive")
    if action == "buy":
        if not stop < entry < target:
            raise PaperBrokerageError("buy geometry requires stop < entry < target")
        return entry - stop, target - entry
    if action == "sell":
        if not target < entry < stop:
            raise PaperBrokerageError("sell geometry requires target < entry < stop")
        return stop - entry, entry - target
    raise PaperBrokerageError("paper action must be buy or sell")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


_GLOBAL_PAPER_BROKER: PaperBrokerageEngine | None = None
_GLOBAL_LOCK = threading.RLock()


def get_global_paper_brokerage() -> PaperBrokerageEngine:
    global _GLOBAL_PAPER_BROKER
    with _GLOBAL_LOCK:
        if _GLOBAL_PAPER_BROKER is None:
            _GLOBAL_PAPER_BROKER = PaperBrokerageEngine(PaperAccountConfig(durable_state=True))
        return _GLOBAL_PAPER_BROKER


def current_paper_brokerage() -> PaperBrokerageEngine | None:
    with _GLOBAL_LOCK:
        return _GLOBAL_PAPER_BROKER


def reset_global_paper_brokerage() -> None:
    global _GLOBAL_PAPER_BROKER
    with _GLOBAL_LOCK:
        _GLOBAL_PAPER_BROKER = None
