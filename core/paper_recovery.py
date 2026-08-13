"""Durable paper runtime recovery and orphan quarantine."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi.encoders import jsonable_encoder

from core.lifecycle_record_classification import (
    LifecycleRecordClassification,
    classify_lifecycle_record,
)


@dataclass(frozen=True)
class PaperOrphanRecord:
    trade_id: str
    symbol: str | None
    last_known_state: str
    reason: str
    timestamp: str
    recovery_recommendation: str
    campaign_id: str | None = None
    trade_status: str | None = None
    orphan_classification: str = "UNKNOWN"
    created_at: str | None = None
    updated_at: str | None = None
    source_presence: dict[str, bool] | None = None


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
    runtime_recovery_status: str = "PASS"
    active_campaign_recovery_status: str = "PASS"
    legacy_recovery_status: str = "PASS"
    global_reconciliation_status: str = "PASS"
    legacy_orphaned_trades: int = 0
    current_campaign_orphaned_trades: int = 0
    quarantined_recovery_excluded: int = 0
    excluded_quarantined: int = 0
    excluded_legacy: int = 0
    excluded_test_fixtures: int = 0
    pending_orders: int = 0
    expired_orders: int = 0
    open_trades: int = 0
    closed_trades: int = 0


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
        orphans, excluded, classifications = self._detect_orphans()
        self._persist_orphans(orphans)
        account = self.broker.account()
        performance = self.broker.performance()
        legacy_orphans = [item for item in orphans if item.orphan_classification == "LEGACY_PRE_PERSISTENCE"]
        active_campaign_id = getattr(getattr(reconciliation, "summary", None), "active_campaign_id", None)
        current_orphans = [item for item in orphans if active_campaign_id and item.campaign_id == active_campaign_id]
        runtime_orphans = [item for item in orphans if item.orphan_classification != "LEGACY_PRE_PERSISTENCE"]
        runtime_status = "WATCHLIST" if runtime_orphans else "PASS"
        active_status = self._scoped_reconciliation_status("active_campaign", "WATCHLIST" if current_orphans else "PASS")
        legacy_status = self._scoped_reconciliation_status("legacy", "WATCHLIST" if legacy_orphans else "PASS")
        global_status = reconciliation.status
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
                f"{len(self.lifecycle.events())} lifecycle histories; classified {classifications['EXPIRED_ORDER']} expired unfilled orders, "
                f"{classifications['OPEN_TRADE']} open trades, and {classifications['CLOSED_TRADE']} closed trades; "
                f"runtime recovery status {runtime_status}; overall status {status}."
            ),
            runtime_recovery_status=runtime_status,
            active_campaign_recovery_status=active_status,
            legacy_recovery_status=legacy_status,
            global_reconciliation_status=global_status,
            legacy_orphaned_trades=len(legacy_orphans),
            current_campaign_orphaned_trades=len(current_orphans),
            quarantined_recovery_excluded=excluded["quarantined"],
            excluded_quarantined=excluded["quarantined"],
            excluded_legacy=excluded["legacy"],
            excluded_test_fixtures=excluded["test_fixture"],
            pending_orders=classifications["PENDING_ORDER"],
            expired_orders=classifications["EXPIRED_ORDER"],
            open_trades=classifications["OPEN_TRADE"],
            closed_trades=classifications["CLOSED_TRADE"],
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

    def _scoped_reconciliation_status(self, scope: str, fallback: str) -> str:
        try:
            return str(self.reconciliation.run(persist=False, scope=scope).status)
        except (AttributeError, TypeError, ValueError):
            return fallback

    def writable(self) -> bool:
        try:
            self.orphan_path.parent.mkdir(parents=True, exist_ok=True)
            probe = self.orphan_path.parent / ".paper-recovery-probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            return True
        except OSError:
            return False

    def _detect_orphans(self) -> tuple[list[PaperOrphanRecord], dict[str, int], dict[str, int]]:
        eligibility_by_trade = {}
        excluded = {"quarantined": 0, "legacy": 0, "test_fixture": 0}
        try:
            from core.integrity_remediation import RemediationRegistry, eligibility_decision
            from core.journal_integrity import JournalIntegrityAuditor
            integrity = JournalIntegrityAuditor(journal=self.journal, broker=self.broker, lifecycle=self.lifecycle).summary()
            remediations = RemediationRegistry().latest_by_trade()
            eligibility_by_trade = {
                item.trade_id: eligibility_decision(item, remediation=remediations.get(str(item.trade_id)))
                for item in integrity.records
                if item.trade_id
            }
        except Exception:
            eligibility_by_trade = {}
        broker_ids = {item.trade_id for item in (*self.broker.open_positions(), *self.broker.closed_trades())}
        broker_open_ids = {item.trade_id for item in self.broker.open_positions()}
        broker_closed_ids = {item.trade_id for item in self.broker.closed_trades()}
        lifecycle_open_ids = {item.trade_id for item in self.lifecycle.open_trades() if item.trade_id}
        lifecycle_closed_ids = {item.trade_id for item in self.lifecycle.closed_trades() if item.trade_id}
        lifecycle_ids = lifecycle_open_ids | lifecycle_closed_ids
        event_ids = {item.trade_id for item in self.lifecycle.events() if getattr(item, "trade_id", None)}
        orphans: list[PaperOrphanRecord] = []
        classifications = {item.value: 0 for item in LifecycleRecordClassification}
        for entry in self.journal.entries():
            if getattr(entry, "test_fixture", False) or getattr(entry, "synthetic_recovery_test", False):
                excluded["test_fixture"] += 1
                continue
            decision = eligibility_by_trade.get(entry.trade_id)
            if decision is not None and not decision.runtime_eligible and any(
                reason in decision.reasons
                for reason in ("remediation_excluded", "corrupted", "duplicate", "synthetic", "test_fixture")
            ):
                if "remediation_excluded" in decision.reasons or "corrupted" in decision.reasons or "duplicate" in decision.reasons:
                    excluded["quarantined"] += 1
                if "test_fixture" in decision.reasons:
                    excluded["test_fixture"] += 1
                continue
            in_broker = entry.trade_id in broker_ids
            in_lifecycle = entry.trade_id in lifecycle_ids or entry.trade_id in event_ids
            semantic = classify_lifecycle_record(
                entry,
                in_brokerage_open=entry.trade_id in broker_open_ids,
                in_brokerage_closed=entry.trade_id in broker_closed_ids,
                in_lifecycle_open=entry.trade_id in lifecycle_open_ids,
                in_lifecycle_closed=entry.trade_id in lifecycle_closed_ids,
            )
            classifications[semantic.value] += 1
            if semantic in {LifecycleRecordClassification.PENDING_ORDER, LifecycleRecordClassification.EXPIRED_ORDER}:
                continue
            if in_broker or in_lifecycle:
                continue
            classification = _classification(entry, in_broker, in_lifecycle)
            orphans.append(PaperOrphanRecord(
                trade_id=entry.trade_id,
                campaign_id=getattr(entry, "campaign_id", None),
                symbol=entry.symbol,
                trade_status=entry.status,
                last_known_state=entry.status,
                orphan_classification=classification,
                reason="Journal trade could not be matched to restored brokerage or lifecycle state.",
                created_at=getattr(entry, "opened_at", None),
                updated_at=getattr(entry, "closed_at", None) or getattr(entry, "opened_at", None),
                timestamp=_now(),
                recovery_recommendation=_recommendation(classification),
                source_presence={
                    "journal": True,
                    "brokerage": in_broker,
                    "lifecycle": in_lifecycle,
                    "campaign": getattr(entry, "campaign_id", None) is not None,
                },
            ))
        return orphans, excluded, classifications

    def _persist_orphans(self, orphans: list[PaperOrphanRecord]) -> None:
        self.orphan_path.parent.mkdir(parents=True, exist_ok=True)
        self.orphan_path.write_text(json.dumps(jsonable_encoder(orphans), indent=2), encoding="utf-8")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_hash() -> str:
    import hashlib
    return hashlib.sha256(_now().encode()).hexdigest()[:12]


def _classification(entry: Any, in_brokerage: bool, in_lifecycle: bool) -> str:
    campaign_id = getattr(entry, "campaign_id", None)
    if campaign_id in {None, "legacy_campaign"}:
        return "LEGACY_PRE_PERSISTENCE"
    if not campaign_id:
        return "CAMPAIGN_ASSIGNMENT_MISSING"
    if not in_brokerage and not in_lifecycle:
        return "OPEN_TRADE_NOT_RECOVERED" if getattr(entry, "status", None) == "open" else "CLOSED_TRADE_NOT_RECOVERED"
    if not in_brokerage:
        return "LIFECYCLE_ONLY"
    if not in_lifecycle:
        return "BROKERAGE_ONLY"
    return "UNKNOWN"


def _recommendation(classification: str) -> str:
    if classification == "LEGACY_PRE_PERSISTENCE":
        return "Keep visible as historical legacy drift; do not treat as an active campaign recovery failure."
    if classification == "CAMPAIGN_ASSIGNMENT_MISSING":
        return "Audit the journal row and assign or quarantine the missing campaign context."
    return "Review durable paper state and lifecycle history for this campaign before relying on recovered runtime state."


_LATEST_RECOVERY: PaperRecoveryResult | None = None


def _set_latest(value: PaperRecoveryResult | None) -> None:
    global _LATEST_RECOVERY
    _LATEST_RECOVERY = value


def latest_paper_recovery() -> PaperRecoveryResult | None:
    return _LATEST_RECOVERY
