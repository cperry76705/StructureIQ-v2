"""Local JSONL journal persistence for StructureIQ analysis records."""

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from threading import RLock
from typing import Any, Iterable
from uuid import uuid4


class TradeOutcome(str, Enum):
    WIN = "win"
    LOSS = "loss"
    BREAKEVEN = "breakeven"
    SKIPPED = "skipped"
    OPEN = "open"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class JournalEntry:
    id: str
    timestamp: str
    symbol: str
    timeframe: str
    higher_timeframe: str
    action: str
    confidence: float | None
    decision_action: str
    setup_type: str
    setup_status: str
    strategy_type: str
    entry_zone: str | None
    stop_loss: str | None
    target: str | None
    estimated_risk_reward: float | None
    outcome: TradeOutcome
    realized_r_multiple: float | None
    notes: tuple[str, ...]
    raw_analysis_snapshot: dict[str, Any]

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "JournalEntry":
        """Build an entry from explicit fields or a complete analysis response."""

        embedded = payload.get("raw_analysis_snapshot")
        if isinstance(embedded, dict):
            snapshot = embedded
        elif any(key in payload for key in ("decision", "setup_plan", "strategy")):
            snapshot = dict(payload)
        else:
            snapshot = {}

        decision = _mapping(snapshot.get("decision"))
        setup = _mapping(snapshot.get("setup_plan"))
        strategy = _mapping(snapshot.get("strategy"))
        notes = payload.get("notes", ())
        if isinstance(notes, str):
            notes = (notes,)

        return cls(
            id=str(payload.get("id") or uuid4()),
            timestamp=str(
                payload.get("timestamp")
                or datetime.now(timezone.utc).isoformat()
            ),
            symbol=str(payload.get("symbol") or snapshot.get("symbol") or "UNKNOWN").upper(),
            timeframe=str(payload.get("timeframe") or snapshot.get("timeframe") or "unknown"),
            higher_timeframe=str(
                payload.get("higher_timeframe")
                or _mapping(snapshot.get("multi_timeframe")).get("higher_timeframe")
                or "unknown"
            ),
            action=str(payload.get("action") or snapshot.get("action") or "unknown"),
            confidence=_optional_float(
                payload.get("confidence", decision.get("confidence", snapshot.get("confidence")))
            ),
            decision_action=str(
                payload.get("decision_action") or decision.get("action") or "unknown"
            ),
            setup_type=str(
                payload.get("setup_type") or setup.get("setup_type") or "no_valid_setup"
            ),
            setup_status=str(
                payload.get("setup_status") or setup.get("setup_status") or "no_setup"
            ),
            strategy_type=str(
                payload.get("strategy_type")
                or strategy.get("preferred_strategy")
                or "no_strategy"
            ),
            entry_zone=_optional_string(
                payload.get("entry_zone", setup.get("entry_zone"))
            ),
            stop_loss=_optional_string(
                payload.get("stop_loss", setup.get("stop_loss"))
            ),
            target=_optional_string(payload.get("target", setup.get("target"))),
            estimated_risk_reward=_optional_float(
                payload.get(
                    "estimated_risk_reward",
                    setup.get("estimated_risk_reward"),
                )
            ),
            outcome=_outcome(payload.get("outcome", TradeOutcome.UNKNOWN)),
            realized_r_multiple=_optional_float(payload.get("realized_r_multiple")),
            notes=tuple(str(note) for note in notes),
            raw_analysis_snapshot=snapshot,
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["outcome"] = self.outcome.value
        data["notes"] = list(self.notes)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "JournalEntry":
        notes = data.get("notes", ())
        if isinstance(notes, str):
            notes = (notes,)
        return cls(
            id=str(data["id"]),
            timestamp=str(data["timestamp"]),
            symbol=str(data.get("symbol", "UNKNOWN")),
            timeframe=str(data.get("timeframe", "unknown")),
            higher_timeframe=str(data.get("higher_timeframe", "unknown")),
            action=str(data.get("action", "unknown")),
            confidence=_optional_float(data.get("confidence")),
            decision_action=str(data.get("decision_action", "unknown")),
            setup_type=str(data.get("setup_type", "no_valid_setup")),
            setup_status=str(data.get("setup_status", "no_setup")),
            strategy_type=str(data.get("strategy_type", "no_strategy")),
            entry_zone=_optional_string(data.get("entry_zone")),
            stop_loss=_optional_string(data.get("stop_loss")),
            target=_optional_string(data.get("target")),
            estimated_risk_reward=_optional_float(data.get("estimated_risk_reward")),
            outcome=_outcome(data.get("outcome", TradeOutcome.UNKNOWN)),
            realized_r_multiple=_optional_float(data.get("realized_r_multiple")),
            notes=tuple(str(note) for note in notes),
            raw_analysis_snapshot=_mapping(data.get("raw_analysis_snapshot")),
        )


@dataclass(frozen=True)
class JournalSummary:
    total_entries: int
    wins: int
    losses: int
    breakeven: int
    skipped: int
    open: int
    unknown: int
    win_rate: float
    average_r: float
    total_r: float
    best_trade_r: float | None
    worst_trade_r: float | None


class JournalStore:
    """Append-only JSONL journal with deterministic local summaries."""

    def __init__(
        self, path: str | Path = Path("journal") / "trade_journal.jsonl"
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()

    def append_entry(self, entry: JournalEntry) -> JournalEntry:
        with self._lock:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry.to_dict(), default=str, sort_keys=True))
                handle.write("\n")
        return entry

    def list_entries(
        self,
        *,
        symbol: str | None = None,
        timeframe: str | None = None,
        outcome: TradeOutcome | str | None = None,
    ) -> list[JournalEntry]:
        if not self.path.exists():
            return []
        expected_outcome = _outcome(outcome) if outcome is not None else None
        entries: list[JournalEntry] = []
        with self._lock:
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    entry = JournalEntry.from_dict(json.loads(line))
                except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                    continue
                if symbol and entry.symbol.upper() != symbol.upper():
                    continue
                if timeframe and entry.timeframe != timeframe:
                    continue
                if expected_outcome and entry.outcome is not expected_outcome:
                    continue
                entries.append(entry)
        return entries

    def summarize_entries(
        self, entries: Iterable[JournalEntry] | None = None
    ) -> JournalSummary:
        selected = list(entries) if entries is not None else self.list_entries()
        counts = {outcome: 0 for outcome in TradeOutcome}
        for entry in selected:
            counts[entry.outcome] += 1
        realized = [
            entry.realized_r_multiple
            for entry in selected
            if entry.realized_r_multiple is not None
        ]
        closed = (
            counts[TradeOutcome.WIN]
            + counts[TradeOutcome.LOSS]
            + counts[TradeOutcome.BREAKEVEN]
        )
        total_r = sum(realized)
        return JournalSummary(
            total_entries=len(selected),
            wins=counts[TradeOutcome.WIN],
            losses=counts[TradeOutcome.LOSS],
            breakeven=counts[TradeOutcome.BREAKEVEN],
            skipped=counts[TradeOutcome.SKIPPED],
            open=counts[TradeOutcome.OPEN],
            unknown=counts[TradeOutcome.UNKNOWN],
            win_rate=round(100.0 * counts[TradeOutcome.WIN] / closed, 2)
            if closed
            else 0.0,
            average_r=round(total_r / len(realized), 3) if realized else 0.0,
            total_r=round(total_r, 3),
            best_trade_r=max(realized) if realized else None,
            worst_trade_r=min(realized) if realized else None,
        )


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_string(value: Any) -> str | None:
    return None if value is None or value == "" else str(value)


def _outcome(value: TradeOutcome | str | Any) -> TradeOutcome:
    if isinstance(value, TradeOutcome):
        return value
    try:
        return TradeOutcome(str(value).lower())
    except ValueError:
        return TradeOutcome.UNKNOWN
