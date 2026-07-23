"""Durable paper runtime recovery and orphan quarantine."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi.encoders import jsonable_encoder


@dataclass(frozen=True)
class PaperOrphanRecord:
    trade_id: str
    symbol: str | None
    last_known_state: str
    reason: str
    timestamp: str
    recovery_recommendation: str


@dataclass(frozen=True)
class PaperRecoverySummary:
    status: str
    recovered_open_positions: int
    recovered_closed_trades: int
    recovered_pending_orders: int
    recovered_lifecycle_histories: int
    recovered_account_balance: float
    recovered_total_r: float
    orphaned_trades: int
    reconciliation_status: str
    human_readable_summary: str


@dataclass(frozen=True)
class PaperRecoveryResult:
    run_id: str
    recovered_at: str
    summary: PaperRecoverySummary
    orphans: tuple[PaperOrphanRecord, ...]
    warnings: tuple[str, ...]
    paper_only: bool
    human_readable_summary: str


class PaperRecoveryEngine:
    """Restore durable paper state and quarantine unmatched journal records."""

    def __init__(
        self,
        *,
        broker: Any,
        lifecycle: Any,
        journal: Any,
        reconciliation: Any,
        orphan_path: str | Path = "research/paper_orphans.json",
    ) -> None:
        self.broker = broker
        self.lifecycle = lifecycle
        self.journal = journal
        self.reconciliation = reconciliation
        self.orphan_path = Path(orphan_path)
        self._latest: PaperRecoveryResult | None = None

    def status(self) -> PaperRecoverySummary:
        if self._latest is None:
            return self.run(persist_reconciliation=False).summary
        return self._latest.summary

    def summary(self) -> PaperRecoverySummary:
        return self.status()

    def run(self, *, persist_reconciliation: bool = True) -> PaperRecoveryResult:
        warnings: list[str] = []
        if hasattr(self.broker, "recover_from_storage"):
            self.broker.recover_from_storage()
        if hasattr(self.lifecycle, "recover_from_storage"):
            self.lifecycle.recover_from_storage()
        # Journal loads in its constructor; keep recovery read-only for journal contents.
        reconciliation = self.reconciliation.run(persist=persist_reconciliation)
        orphans = self._detect_orphans()
        self._persist_orphans(orphans)
        account = self.broker.account()
        performance = self.broker.performance()
        status = "FAIL" if reconciliation.status == "FAIL" else "WATCHLIST" if orphans or reconciliation.status == "WATCHLIST" else "PASS"
        if orphans:
            warnings.append("One or more journal trades could not be matched to restored paper/lifecycle state and were quarantined.")
        summary = PaperRecoverySummary(
            status=status,
            recovered_open_positions=len(self.broker.open_positions()),
            recovered_closed_trades=len(self.broker.closed_trades()),
            recovered_pending_orders=len(self.lifecycle.pending_orders()),
            recovered_lifecycle_histories=len(self.lifecycle.events()),
            recovered_account_balance=account.balance,
            recovered_total_r=performance.total_r,
            orphaned_trades=len(orphans),
            reconciliation_status=reconciliation.status,
            human_readable_summary=(
                f"Recovered {len(self.broker.open_positions())} open positions, "
                f"{len(self.lifecycle.pending_orders())} pending orders, "
                f"{len(self.lifecycle.events())} lifecycle histories; recovery status {status}."
            ),
        )
        result = PaperRecoveryResult(
            run_id=f"recovery_{_now_hash()}",
            recovered_at=_now(),
            summary=summary,
            orphans=tuple(orphans),
            warnings=tuple(warnings),
            paper_only=True,
            human_readable_summary=summary.human_readable_summary,
        )
        self._latest = result
        _set_latest(result)
        return result

    def writable(self) -> bool:
        try:
            self.orphan_path.parent.mkdir(parents=True, exist_ok=True)
            probe = self.orphan_path.parent / ".paper-recovery-probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            return True
        except OSError:
            return False

    def _detect_orphans(self) -> list[PaperOrphanRecord]:
        broker_ids = {item.trade_id for item in (*self.broker.open_positions(), *self.broker.closed_trades())}
        lifecycle_ids = {item.trade_id for item in (*self.lifecycle.open_trades(), *self.lifecycle.closed_trades()) if item.trade_id}
        event_ids = {item.trade_id for item in self.lifecycle.events() if getattr(item, "trade_id", None)}
        orphans: list[PaperOrphanRecord] = []
        for entry in self.journal.entries():
            if entry.status not in {"open", "closed"}:
                continue
            if entry.trade_id in broker_ids or entry.trade_id in lifecycle_ids or entry.trade_id in event_ids:
                continue
            orphans.append(PaperOrphanRecord(
                trade_id=entry.trade_id,
                symbol=entry.symbol,
                last_known_state=entry.status,
                reason="Journal trade could not be matched to restored brokerage or lifecycle state.",
                timestamp=_now(),
                recovery_recommendation="Review durable paper state; keep the journal record quarantined until manually reconciled.",
            ))
        return orphans

    def _persist_orphans(self, orphans: list[PaperOrphanRecord]) -> None:
        self.orphan_path.parent.mkdir(parents=True, exist_ok=True)
        self.orphan_path.write_text(json.dumps(jsonable_encoder(orphans), indent=2), encoding="utf-8")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_hash() -> str:
    import hashlib
    return hashlib.sha256(_now().encode()).hexdigest()[:12]


_LATEST_RECOVERY: PaperRecoveryResult | None = None


def _set_latest(value: PaperRecoveryResult | None) -> None:
    global _LATEST_RECOVERY
    _LATEST_RECOVERY = value


def latest_paper_recovery() -> PaperRecoveryResult | None:
    return _LATEST_RECOVERY
