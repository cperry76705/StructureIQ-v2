"""Deterministic paper-only recovery fixtures for infrastructure validation.

The harness creates explicitly tagged synthetic paper state through the same
brokerage and lifecycle persistence used by normal paper trades. It is not part
of strategy routing, scoring, candidate generation, or performance analytics.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict

from core.paper_brokerage import PaperBrokerageEngine, PaperOpenRequest, PaperTrade
from core.paper_recovery import PaperRecoveryEngine
from core.paper_state_reconciliation import PaperStateReconciliationEngine
from core.trade_lifecycle_manager import OrderType, PendingPaperOrder, TradeLifecycleManager
from core.validation_campaigns import ValidationCampaignManager


FixtureType = Literal["PENDING_ORDER", "OPEN_TRADE", "CLOSED_TRADE"]
RecoveryTestRunState = Literal[
    "CREATING",
    "FIXTURES_CREATED",
    "SNAPSHOT_PENDING",
    "SNAPSHOT_READY",
    "VERIFYING",
    "VERIFIED_PASS",
    "VERIFIED_FAIL",
    "INCOMPLETE",
    "CLEANED",
    "ABORTED",
]
DifferenceType = Literal["RECOVERY_DIFFERENCE", "HARNESS_STATE_DIFFERENCE", "SNAPSHOT_DIFFERENCE", "RUN_STATE_DIFFERENCE"]


class RecoveryTestFixtureRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str = "GBP-USD"
    action: Literal["buy", "sell"] = "buy"


@dataclass(frozen=True)
class RecoveryTestFixture:
    fixture_id: str
    fixture_type: str
    campaign_id: str
    created_at: str
    status: str
    symbol: str
    timeframe: str
    higher_timeframe: str
    action: str
    strategy: str
    setup: str
    order_id: str | None
    trade_id: str | None
    entry_price: float
    stop_loss: float
    target: float
    target_r: float
    risk_amount: float
    risk_per_trade_percent: float
    position_size: float
    test_fixture: bool = True
    synthetic_recovery_test: bool = True
    exclude_from_performance: bool = True
    exclude_from_calibration: bool = True
    exclude_from_campaign_metrics: bool = True
    exclude_from_daily_reports: bool = True
    exclude_from_research: bool = True
    recovery_test_run_id: str | None = None


@dataclass(frozen=True)
class RecoveryTestStatus:
    active_test_campaign_id: str | None
    pending_fixture_count: int
    open_fixture_count: int
    closed_fixture_count: int
    fixture_ids: tuple[str, ...]
    expected_recovery_objects: dict[str, int]
    ready_for_restart_test: bool
    human_readable_summary: str
    current_run_id: str | None = None
    current_run_state: str | None = None
    snapshot_id: str | None = None
    snapshot_status: str | None = None
    ready_for_verification: bool = False
    ambiguous_run_count: int = 0
    incomplete_run_count: int = 0
    active_fixture_count: int = 0


@dataclass(frozen=True)
class RecoveryTestSnapshot:
    snapshot_status: str
    snapshot_id: str
    recovery_test_run_id: str | None = None
    campaign_id: str | None = None
    snapshot_at: str = ""
    pending_orders: int = 0
    open_trades: int = 0
    closed_trades: int = 0
    ready_for_restart: bool = False
    fixtures: tuple[dict[str, Any], ...] = ()
    human_readable_summary: str = ""
    created_at: str | None = None
    fixture_ids: tuple[str, ...] = ()
    order_ids: tuple[str, ...] = ()
    trade_ids: tuple[str, ...] = ()
    fixture_count: int = 0
    pending_order_count: int = 0
    open_trade_count: int = 0


@dataclass(frozen=True)
class RecoveryTestDifference:
    fixture_id: str
    field: str
    expected: Any
    actual: Any
    severity: str
    message: str
    difference_type: str = "RECOVERY_DIFFERENCE"


@dataclass(frozen=True)
class RecoveryTestVerification:
    status: str
    campaign_id_match: bool
    pending_orders_expected: int
    pending_orders_recovered: int
    open_trades_expected: int
    open_trades_recovered: int
    order_ids_match: bool
    trade_ids_match: bool
    price_geometry_match: bool
    lifecycle_state_match: bool
    reconciliation_status: str
    differences: tuple[RecoveryTestDifference, ...]
    human_readable_summary: str
    recovery_test_run_id: str | None = None
    snapshot_id: str | None = None
    expected_fixture_ids: tuple[str, ...] = ()
    recovered_fixture_ids: tuple[str, ...] = ()
    recovery_failure: bool = False
    harness_precondition_failure: bool = False


@dataclass(frozen=True)
class RecoveryTestCleanupResult:
    status: str
    fixtures_archived: int
    active_test_fixtures_remaining: int
    cleanup_status: str
    human_readable_summary: str
    recovery_test_run_id: str | None = None
    run_state: str | None = None


@dataclass(frozen=True)
class RecoveryTestRun:
    recovery_test_run_id: str
    state: str
    created_at: str
    updated_at: str
    campaign_id: str | None = None
    fixture_ids: tuple[str, ...] = ()
    order_ids: tuple[str, ...] = ()
    trade_ids: tuple[str, ...] = ()
    snapshot_id: str | None = None
    snapshot_status: str | None = None
    note: str | None = None
    active_fixture_count: int = 0
    recommended_action: str | None = None


@dataclass(frozen=True)
class RecoveryTestCreateResult:
    status: str
    recovery_test_run_id: str
    campaign_id: str | None
    pending_fixture: RecoveryTestFixture | None
    open_trade_fixture: RecoveryTestFixture | None
    snapshot: RecoveryTestSnapshot | None
    run_state: str
    human_readable_summary: str


class RecoveryTestHarness:
    """Create, snapshot, verify, and clean up paper-only recovery fixtures."""

    def __init__(
        self,
        *,
        broker: PaperBrokerageEngine,
        lifecycle: TradeLifecycleManager,
        campaigns: ValidationCampaignManager,
        reconciliation: PaperStateReconciliationEngine,
        recovery: PaperRecoveryEngine,
        reports_dir: str | Path = "reports",
    ) -> None:
        self.broker = broker
        self.lifecycle = lifecycle
        self.campaigns = campaigns
        self.reconciliation = reconciliation
        self.recovery = recovery
        self.reports_dir = Path(reports_dir)
        self.snapshot_path = self.reports_dir / "recovery_test_snapshot.json"
        self.snapshots_dir = self.reports_dir / "recovery_test_snapshots"
        self.history_path = self.reports_dir / "recovery_test_history.jsonl"
        self.runs_path = self.reports_dir / "recovery_test_runs.jsonl"
        self._implicit_run_id: str | None = None

    def create_recovery_test_run(self, request: RecoveryTestFixtureRequest | None = None) -> RecoveryTestCreateResult:
        """Create fixtures and snapshot them under one durable run identity."""

        run_id = _recovery_run_id()
        run = self._transition(run_id, "CREATING", note="Recovery test run started.")
        pending = open_fixture = None
        snapshot = None
        try:
            pending = self.create_pending_order(request, recovery_test_run_id=run_id)
            open_fixture = self.create_open_trade(request, recovery_test_run_id=run_id)
            run = self._transition(
                run_id,
                "FIXTURES_CREATED",
                campaign_id=pending.campaign_id,
                fixture_ids=(pending.fixture_id, open_fixture.fixture_id),
                order_ids=tuple(item for item in (pending.order_id,) if item),
                trade_ids=tuple(item for item in (open_fixture.trade_id,) if item),
                note="Recovery test fixtures created.",
            )
            self._transition(run_id, "SNAPSHOT_PENDING", note="Snapshot creation started.")
            snapshot = self.snapshot(run_id)
            if snapshot.snapshot_status != "PASS":
                run = self._transition(run_id, "INCOMPLETE", snapshot_id=snapshot.snapshot_id, snapshot_status=snapshot.snapshot_status, note="Snapshot did not pass validation.")
                return RecoveryTestCreateResult("INCOMPLETE", run_id, pending.campaign_id, pending, open_fixture, snapshot, run.state, "Recovery fixtures were created but snapshot validation did not pass.")
            run = self._transition(run_id, "SNAPSHOT_READY", snapshot_id=snapshot.snapshot_id, snapshot_status=snapshot.snapshot_status, note="Recovery test snapshot ready.")
            return RecoveryTestCreateResult("PASS", run_id, pending.campaign_id, pending, open_fixture, snapshot, run.state, "Recovery test run is SNAPSHOT_READY.")
        except Exception as exc:
            self._transition(run_id, "INCOMPLETE", note=f"Create flow failed: {exc}")
            raise

    def runs(self) -> tuple[RecoveryTestRun, ...]:
        rows = self._run_events()
        latest: dict[str, dict[str, Any]] = {}
        for row in rows:
            run_id = row.get("recovery_test_run_id")
            if not run_id:
                continue
            existing = latest.get(str(run_id), {})
            merged = {**existing, **row}
            latest[str(run_id)] = merged
        active_counts = self._active_fixture_counts_by_run()
        result = []
        for run_id, row in latest.items():
            result.append(_run_from_row({**row, "active_fixture_count": active_counts.get(run_id, 0)}))
        return tuple(sorted(result, key=lambda item: item.created_at))

    def run(self, recovery_test_run_id: str) -> RecoveryTestRun | None:
        return next((item for item in self.runs() if item.recovery_test_run_id == recovery_test_run_id), None)

    def incomplete_runs(self) -> tuple[RecoveryTestRun, ...]:
        return tuple(item for item in self.runs() if item.state == "INCOMPLETE")

    def current_run(self) -> RecoveryTestRun | None:
        resolved, _ = self._resolve_run(None)
        return resolved

    def create_pending_order(self, request: RecoveryTestFixtureRequest | None = None, *, recovery_test_run_id: str | None = None) -> RecoveryTestFixture:
        self._assert_paper_only()
        req = request or RecoveryTestFixtureRequest()
        campaign = self.campaigns.recovery_test_campaign()
        fixture_id = _fixture_id("pending", req.symbol, req.action)
        levels = _levels(req.action)
        run_id = recovery_test_run_id or self._ensure_implicit_run()
        metadata = _metadata(fixture_id, "PENDING_ORDER", campaign.campaign_id, run_id)
        order = self.lifecycle.create_recovery_test_pending_order(
            fixture_id=fixture_id,
            campaign_id=campaign.campaign_id,
            symbol=req.symbol,
            timeframe="5m",
            higher_timeframe="1h",
            action=req.action,
            setup="synthetic_recovery_fixture",
            strategy="recovery_test_harness",
            order_type=OrderType.LIMIT_RETEST,
            entry_price=levels["entry"],
            stop_loss=levels["stop"],
            target=levels["target"],
            risk_per_trade_percent=1.0,
            metadata=metadata,
        )
        fixture = _fixture_from_order(order, campaign.campaign_id, fixture_id, run_id)
        self._history({"test_id": fixture_id, "recovery_test_run_id": run_id, "campaign_id": campaign.campaign_id, "created_at": fixture.created_at, "status": "CREATED", "run_state": "CREATING", "fixtures_expected": 1})
        return fixture

    def create_open_trade(self, request: RecoveryTestFixtureRequest | None = None, *, recovery_test_run_id: str | None = None) -> RecoveryTestFixture:
        self._assert_paper_only()
        req = request or RecoveryTestFixtureRequest()
        campaign = self.campaigns.recovery_test_campaign()
        fixture_id = _fixture_id("open", req.symbol, req.action)
        run_id = recovery_test_run_id or self._ensure_implicit_run()
        trade = self._open_fixture_trade(fixture_id, "OPEN_TRADE", campaign.campaign_id, req.symbol, req.action, run_id)
        self.lifecycle.register_recovery_test_open_trade(trade)
        fixture = _fixture_from_trade(trade, campaign.campaign_id, fixture_id, "OPEN_TRADE", run_id)
        self._history({"test_id": fixture_id, "recovery_test_run_id": run_id, "campaign_id": campaign.campaign_id, "created_at": fixture.created_at, "status": "CREATED", "run_state": "CREATING", "fixtures_expected": 1})
        return fixture

    def create_closed_trade(self, request: RecoveryTestFixtureRequest | None = None) -> RecoveryTestFixture:
        self._assert_paper_only()
        req = request or RecoveryTestFixtureRequest()
        campaign = self.campaigns.recovery_test_campaign()
        fixture_id = _fixture_id("closed", req.symbol, req.action)
        run_id = self._ensure_implicit_run()
        trade = self._open_fixture_trade(fixture_id, "CLOSED_TRADE", campaign.campaign_id, req.symbol, req.action, run_id)
        self.lifecycle.register_recovery_test_open_trade(trade)
        exit_price = trade.target
        closed = self.broker.close_position(trade.trade_id, exit_price)
        self.lifecycle.register_recovery_test_open_trade(closed)
        fixture = _fixture_from_trade(closed, campaign.campaign_id, fixture_id, "CLOSED_TRADE", run_id)
        self._history({"test_id": fixture_id, "recovery_test_run_id": run_id, "campaign_id": campaign.campaign_id, "created_at": fixture.created_at, "status": "CREATED", "run_state": "CREATING", "fixtures_expected": 1})
        return fixture

    def status(self, recovery_test_run_id: str | None = None) -> RecoveryTestStatus:
        fixtures = self._fixtures()
        if recovery_test_run_id:
            fixtures = [item for item in fixtures if item.get("recovery_test_run_id") == recovery_test_run_id]
        pending = [item for item in fixtures if item["fixture_type"] == "PENDING_ORDER"]
        open_trades = [item for item in fixtures if item["fixture_type"] == "OPEN_TRADE"]
        closed = [item for item in fixtures if item["fixture_type"] == "CLOSED_TRADE"]
        campaign_id = fixtures[0]["campaign_id"] if fixtures else None
        ready = bool(pending or open_trades)
        current, resolution = self._resolve_run(recovery_test_run_id)
        snapshot = self._snapshot(current.recovery_test_run_id) if current else None
        incomplete = self.incomplete_runs()
        summary = (
            "Recovery test state contains one pending order and one open trade and is ready for restart validation."
            if pending and open_trades
            else f"Recovery test state contains {len(pending)} pending, {len(open_trades)} open, and {len(closed)} closed fixtures."
        )
        return RecoveryTestStatus(
            active_test_campaign_id=campaign_id,
            pending_fixture_count=len(pending),
            open_fixture_count=len(open_trades),
            closed_fixture_count=len(closed),
            fixture_ids=tuple(str(item["fixture_id"]) for item in fixtures),
            expected_recovery_objects={"pending_orders": len(pending), "open_trades": len(open_trades), "closed_trades": len(closed)},
            ready_for_restart_test=ready,
            human_readable_summary=summary,
            current_run_id=getattr(current, "recovery_test_run_id", None),
            current_run_state=getattr(current, "state", resolution),
            snapshot_id=getattr(snapshot, "snapshot_id", None),
            snapshot_status=getattr(snapshot, "snapshot_status", None),
            ready_for_verification=bool(current and current.state == "SNAPSHOT_READY" and snapshot and snapshot.snapshot_status == "PASS"),
            ambiguous_run_count=len([item for item in self.runs() if item.state == "SNAPSHOT_READY"]),
            incomplete_run_count=len(incomplete),
            active_fixture_count=len(fixtures),
        )

    def snapshot(self, recovery_test_run_id: str | None = None) -> RecoveryTestSnapshot:
        run_id = recovery_test_run_id or self._implicit_run_id or getattr(self.current_run(), "recovery_test_run_id", None) or _recovery_run_id()
        run = self.run(run_id)
        if run and run.state not in {"FIXTURES_CREATED", "SNAPSHOT_PENDING", "INCOMPLETE", "CREATING"}:
            return RecoveryTestSnapshot(
                snapshot_status="FAIL",
                snapshot_id=_snapshot_id(run_id),
                recovery_test_run_id=run_id,
                campaign_id=run.campaign_id,
                snapshot_at=_now(),
                human_readable_summary=f"Snapshot retry is not allowed from run state {run.state}.",
            )
        fixtures = tuple(item for item in self._fixtures() if item.get("recovery_test_run_id") == run_id)
        snapshot_id = hashlib.sha256(f"recovery-snapshot:{_now()}:{len(fixtures)}".encode()).hexdigest()[:24]
        campaign_id = fixtures[0]["campaign_id"] if fixtures else None
        status = "PASS" if fixtures else "FAIL"
        snapshot = RecoveryTestSnapshot(
            snapshot_status=status,
            snapshot_id=snapshot_id,
            recovery_test_run_id=run_id,
            campaign_id=campaign_id,
            snapshot_at=_now(),
            pending_orders=sum(item["fixture_type"] == "PENDING_ORDER" for item in fixtures),
            open_trades=sum(item["fixture_type"] == "OPEN_TRADE" for item in fixtures),
            closed_trades=sum(item["fixture_type"] == "CLOSED_TRADE" for item in fixtures),
            ready_for_restart=any(item["fixture_type"] in {"PENDING_ORDER", "OPEN_TRADE"} for item in fixtures),
            fixtures=fixtures,
            human_readable_summary="Recovery test snapshot captured durable synthetic paper state." if status == "PASS" else "Recovery test snapshot is missing required fixtures.",
            created_at=_now(),
            fixture_ids=tuple(str(item["fixture_id"]) for item in fixtures),
            order_ids=tuple(str(item["order_id"]) for item in fixtures if item.get("order_id")),
            trade_ids=tuple(str(item["trade_id"]) for item in fixtures if item.get("trade_id")),
            fixture_count=len(fixtures),
            pending_order_count=sum(item["fixture_type"] == "PENDING_ORDER" for item in fixtures),
            open_trade_count=sum(item["fixture_type"] == "OPEN_TRADE" for item in fixtures),
        )
        self.snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        (self.snapshots_dir / f"{run_id}.json").write_text(json.dumps(jsonable_encoder(snapshot), indent=2), encoding="utf-8")
        self.snapshot_path.write_text(json.dumps(jsonable_encoder(snapshot), indent=2), encoding="utf-8")
        self._history({"test_id": snapshot_id, "snapshot_id": snapshot_id, "recovery_test_run_id": run_id, "campaign_id": campaign_id, "snapshot_at": snapshot.snapshot_at, "status": snapshot.snapshot_status, "run_state": "SNAPSHOT_READY" if status == "PASS" else "INCOMPLETE", "fixtures_expected": len(fixtures)})
        self._transition(run_id, "SNAPSHOT_READY" if status == "PASS" else "INCOMPLETE", campaign_id=campaign_id, fixture_ids=snapshot.fixture_ids, order_ids=snapshot.order_ids, trade_ids=snapshot.trade_ids, snapshot_id=snapshot.snapshot_id, snapshot_status=snapshot.snapshot_status, note=snapshot.human_readable_summary)
        return snapshot

    def verify_after_restart(self, recovery_test_run_id: str | None = None) -> RecoveryTestVerification:
        run, resolution = self._resolve_run(recovery_test_run_id)
        if run is None:
            return _not_ready_verification(resolution, recovery_test_run_id)
        if run.state != "SNAPSHOT_READY":
            return _blocked_verification(run, "RUN_STATE_DIFFERENCE", f"Run is {run.state} and cannot be verified.")
        snapshot = self._snapshot(run.recovery_test_run_id)
        if snapshot is None or snapshot.snapshot_status != "PASS":
            return _blocked_verification(run, "SNAPSHOT_DIFFERENCE", "No PASS snapshot is bound to this recovery test run.")
        self._transition(run.recovery_test_run_id, "VERIFYING", snapshot_id=snapshot.snapshot_id, snapshot_status=snapshot.snapshot_status, note="Recovery test verification started.")
        self.broker.recover_from_storage()
        self.lifecycle.recover_from_storage()
        self.recovery.run(persist_reconciliation=False)
        expected = tuple(snapshot.fixtures)
        actual = {item["fixture_id"]: item for item in self._fixtures() if item.get("recovery_test_run_id") == run.recovery_test_run_id}
        differences: list[RecoveryTestDifference] = []
        for row in expected:
            fixture_id = str(row["fixture_id"])
            observed = actual.get(fixture_id)
            if observed is None:
                differences.append(_diff(fixture_id, "fixture", "present", "missing", "critical", "Expected fixture was not recovered.", "RECOVERY_DIFFERENCE"))
                continue
            for field in ("campaign_id", "order_id", "trade_id", "symbol", "status", "entry_price", "stop_loss", "target", "risk_amount", "position_size"):
                if not _same(row.get(field), observed.get(field)):
                    differences.append(_diff(fixture_id, field, row.get(field), observed.get(field), "critical", f"Recovered fixture field {field} did not match the snapshot.", "RECOVERY_DIFFERENCE"))
            if row.get("lifecycle_event_count", 0) and not observed.get("lifecycle_event_count", 0):
                differences.append(_diff(fixture_id, "lifecycle_state", row.get("lifecycle_event_count"), observed.get("lifecycle_event_count"), "critical", "Recovered fixture is missing lifecycle state.", "RECOVERY_DIFFERENCE"))
        campaign_ids = {item.get("campaign_id") for item in expected if item.get("campaign_id")}
        actual_campaign_ids = {item.get("campaign_id") for item in actual.values() if item.get("campaign_id")}
        reconciliation_status = "PASS"
        campaign_id = next(iter(campaign_ids), None)
        if campaign_id:
            try:
                reconciliation_status = self.reconciliation.run(persist=False, scope="campaign", campaign_id=str(campaign_id)).status
            except Exception:
                reconciliation_status = "WATCHLIST"
        status = "PASS" if not differences and reconciliation_status == "PASS" else "FAIL" if any(item.severity == "critical" for item in differences) else "WATCHLIST"
        result = RecoveryTestVerification(
            status=status,
            campaign_id_match=campaign_ids.issubset(actual_campaign_ids),
            pending_orders_expected=sum(item["fixture_type"] == "PENDING_ORDER" for item in expected),
            pending_orders_recovered=sum(item["fixture_type"] == "PENDING_ORDER" for item in actual.values()),
            open_trades_expected=sum(item["fixture_type"] == "OPEN_TRADE" for item in expected),
            open_trades_recovered=sum(item["fixture_type"] == "OPEN_TRADE" for item in actual.values()),
            order_ids_match=not any(item.field == "order_id" for item in differences),
            trade_ids_match=not any(item.field == "trade_id" for item in differences),
            price_geometry_match=not any(item.field in {"entry_price", "stop_loss", "target"} for item in differences),
            lifecycle_state_match=not any(item.field == "lifecycle_state" for item in differences),
            reconciliation_status=reconciliation_status,
            differences=tuple(differences),
            human_readable_summary=(
                "All deterministic paper recovery fixtures were restored exactly after restart."
                if status == "PASS"
                else f"Recovery fixture verification found {len(differences)} differences."
            ),
            recovery_test_run_id=run.recovery_test_run_id,
            snapshot_id=snapshot.snapshot_id,
            expected_fixture_ids=tuple(str(item["fixture_id"]) for item in expected),
            recovered_fixture_ids=tuple(sorted(actual)),
            recovery_failure=any(item.difference_type == "RECOVERY_DIFFERENCE" for item in differences),
            harness_precondition_failure=False,
        )
        run_state = "VERIFIED_PASS" if result.status == "PASS" else "VERIFIED_FAIL" if result.status == "FAIL" else result.status
        self._transition(run.recovery_test_run_id, run_state, snapshot_id=snapshot.snapshot_id, snapshot_status=snapshot.snapshot_status, note=result.human_readable_summary)
        self._history({"test_id": snapshot.snapshot_id, "snapshot_id": snapshot.snapshot_id, "recovery_test_run_id": run.recovery_test_run_id, "campaign_id": campaign_id, "verified_at": _now(), "status": result.status, "run_state": run_state, "fixtures_expected": len(expected), "fixtures_recovered": len(actual), "differences": jsonable_encoder(result.differences), "reconciliation_status": reconciliation_status})
        return result

    def cleanup(self, recovery_test_run_id: str | None = None) -> RecoveryTestCleanupResult:
        run, resolution = self._resolve_run(recovery_test_run_id, cleanup=True)
        if run is None:
            return RecoveryTestCleanupResult("NOT_READY", 0, len(self._fixtures()), "NOT_READY", f"No cleanup target is available: {resolution}.", recovery_test_run_id, resolution)
        before = len([item for item in self._fixtures() if item.get("recovery_test_run_id") == run.recovery_test_run_id])
        if run.state == "CLEANED":
            return RecoveryTestCleanupResult("PASS", 0, before, "PASS", "Recovery test run was already cleaned.", run.recovery_test_run_id, "CLEANED")
        lifecycle_removed = self.lifecycle.remove_recovery_test_fixtures(run.recovery_test_run_id)
        broker_removed = self.broker.remove_recovery_test_fixtures(run.recovery_test_run_id)
        after = len([item for item in self._fixtures() if item.get("recovery_test_run_id") == run.recovery_test_run_id])
        status = "PASS" if after == 0 else "WATCHLIST"
        cleaned = self._transition(run.recovery_test_run_id, "CLEANED" if status == "PASS" else run.state, note=f"Cleanup removed {before - after} active fixtures.")
        result = RecoveryTestCleanupResult(
            status=status,
            fixtures_archived=before,
            active_test_fixtures_remaining=after,
            cleanup_status=status,
            human_readable_summary=f"Archived {before} synthetic recovery fixtures; {after} active test fixtures remain.",
            recovery_test_run_id=run.recovery_test_run_id,
            run_state=cleaned.state,
        )
        self._history({"test_id": f"cleanup_{_hash(_now())}", "recovery_test_run_id": run.recovery_test_run_id, "campaign_id": run.campaign_id, "status": status, "run_state": cleaned.state, "cleanup_status": status, "fixtures_recovered": broker_removed + lifecycle_removed, "fixtures_expected": before})
        return result

    def history(self, limit: int = 100) -> tuple[dict[str, Any], ...]:
        if not self.history_path.exists():
            return ()
        rows = []
        for line in self.history_path.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return tuple(rows[-limit:])

    def writable(self) -> bool:
        try:
            self.reports_dir.mkdir(parents=True, exist_ok=True)
            probe = self.reports_dir / ".recovery-test-probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            return True
        except OSError:
            return False

    def _transition(
        self,
        recovery_test_run_id: str,
        state: str,
        *,
        campaign_id: str | None = None,
        fixture_ids: tuple[str, ...] = (),
        order_ids: tuple[str, ...] = (),
        trade_ids: tuple[str, ...] = (),
        snapshot_id: str | None = None,
        snapshot_status: str | None = None,
        note: str | None = None,
    ) -> RecoveryTestRun:
        previous = self.run(recovery_test_run_id)
        now = _now()
        row = {
            "recovery_test_run_id": recovery_test_run_id,
            "state": state,
            "created_at": getattr(previous, "created_at", now),
            "updated_at": now,
            "campaign_id": campaign_id or getattr(previous, "campaign_id", None),
            "fixture_ids": fixture_ids or getattr(previous, "fixture_ids", ()),
            "order_ids": order_ids or getattr(previous, "order_ids", ()),
            "trade_ids": trade_ids or getattr(previous, "trade_ids", ()),
            "snapshot_id": snapshot_id or getattr(previous, "snapshot_id", None),
            "snapshot_status": snapshot_status or getattr(previous, "snapshot_status", None),
            "note": note,
        }
        self.runs_path.parent.mkdir(parents=True, exist_ok=True)
        with self.runs_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(jsonable_encoder(row), separators=(",", ":")))
            stream.write("\n")
        self._history({
            "test_id": recovery_test_run_id,
            "recovery_test_run_id": recovery_test_run_id,
            "campaign_id": row["campaign_id"],
            "status": state,
            "run_state": state,
            "snapshot_id": row["snapshot_id"],
        })
        return _run_from_row(row)

    def _ensure_implicit_run(self) -> str:
        if self._implicit_run_id and self.run(self._implicit_run_id) is not None:
            return self._implicit_run_id
        run_id = _recovery_run_id()
        self._implicit_run_id = run_id
        self._transition(run_id, "CREATING", note="Implicit compatibility recovery-test run started.")
        return run_id

    def _run_events(self) -> tuple[dict[str, Any], ...]:
        if not self.runs_path.exists():
            return ()
        rows = []
        for line in self.runs_path.read_text(encoding="utf-8").splitlines():
            try:
                value = json.loads(line)
                if isinstance(value, dict):
                    rows.append(value)
            except json.JSONDecodeError:
                continue
        return tuple(rows)

    def _resolve_run(self, recovery_test_run_id: str | None, *, cleanup: bool = False) -> tuple[RecoveryTestRun | None, str]:
        runs = self.runs()
        if recovery_test_run_id:
            found = next((item for item in runs if item.recovery_test_run_id == recovery_test_run_id), None)
            return (found, "NOT_FOUND" if found is None else found.state)
        if cleanup:
            candidates = [item for item in runs if item.state in {"CREATING", "FIXTURES_CREATED", "SNAPSHOT_PENDING", "SNAPSHOT_READY", "VERIFIED_PASS", "VERIFIED_FAIL", "INCOMPLETE", "CLEANED"}]
        else:
            candidates = [item for item in runs if item.state == "SNAPSHOT_READY" and item.snapshot_status == "PASS"]
        if not candidates:
            latest = runs[-1].state if runs else "NO_RUN"
            return None, "NOT_READY" if latest == "NO_RUN" else latest
        if len(candidates) > 1:
            return None, "AMBIGUOUS"
        return candidates[0], candidates[0].state

    def _active_fixture_counts_by_run(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for fixture in self._fixtures():
            run_id = fixture.get("recovery_test_run_id")
            if run_id:
                counts[str(run_id)] = counts.get(str(run_id), 0) + 1
        return counts

    def _open_fixture_trade(self, fixture_id: str, fixture_type: str, campaign_id: str, symbol: str, action: str, recovery_test_run_id: str | None) -> PaperTrade:
        levels = _levels(action)
        return self.broker.open_position(PaperOpenRequest(
            source_event_id=fixture_id,
            symbol=symbol,
            timeframe="5m",
            higher_timeframe="1h",
            action=action,
            setup="synthetic_recovery_fixture",
            strategy="recovery_test_harness",
            entry_price=levels["entry"],
            stop_loss=levels["stop"],
            target=levels["target"],
            risk_per_trade_percent=1.0,
            allow_duplicate=True,
            metadata=_metadata(fixture_id, fixture_type, campaign_id, recovery_test_run_id),
        ))

    def _fixtures(self) -> list[dict[str, Any]]:
        events_by_source = {}
        for event in self.lifecycle.events():
            if (event.metadata or {}).get("test_fixture"):
                key = event.source_event_id or event.trade_id or event.metadata.get("fixture_id")
                events_by_source.setdefault(key, 0)
                events_by_source[key] += 1
        fixtures: list[dict[str, Any]] = []
        for order in self.lifecycle.pending_orders():
            if (order.metadata or {}).get("test_fixture"):
                row = _fixture_dict_from_order(order)
                row["lifecycle_event_count"] = events_by_source.get(order.source_event_id, 0)
                fixtures.append(row)
        for trade in (*self.broker.open_positions(), *self.broker.closed_trades()):
            if (trade.metadata or {}).get("test_fixture"):
                row = _fixture_dict_from_trade(trade)
                row["lifecycle_event_count"] = events_by_source.get(trade.source_event_id, 0) or events_by_source.get(trade.trade_id, 0)
                fixtures.append(row)
        return sorted(fixtures, key=lambda item: (item["fixture_type"], item["fixture_id"]))

    def _snapshot(self, recovery_test_run_id: str | None = None) -> RecoveryTestSnapshot | None:
        path = self.snapshots_dir / f"{recovery_test_run_id}.json" if recovery_test_run_id else self.snapshot_path
        if not path.exists():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if recovery_test_run_id and raw.get("recovery_test_run_id") != recovery_test_run_id:
                return None
            return RecoveryTestSnapshot(**raw)
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            return None

    def _load_snapshot(self) -> tuple[dict[str, Any], ...]:
        snapshot = self._snapshot()
        return tuple(snapshot.fixtures) if snapshot is not None else ()

    def _history(self, payload: dict[str, Any]) -> None:
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "created_at": _now(),
            "snapshot_at": None,
            "verified_at": None,
            "fixtures_expected": 0,
            "fixtures_recovered": 0,
            "differences": (),
            "reconciliation_status": None,
            "cleanup_status": None,
            **payload,
        }
        with self.history_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(jsonable_encoder(row), separators=(",", ":")))
            stream.write("\n")

    def _assert_paper_only(self) -> None:
        account = self.broker.account()
        if not getattr(account, "advisory_only", True):
            raise ValueError("recovery fixtures require advisory paper-only brokerage state")
        if getattr(account, "paper_trading_enabled", False):
            raise ValueError("recovery fixtures refuse enabled live/paper execution state")


def _metadata(fixture_id: str, fixture_type: str, campaign_id: str, recovery_test_run_id: str | None = None) -> dict[str, Any]:
    return {
        "fixture_id": fixture_id,
        "fixture_type": fixture_type,
        "campaign_id": campaign_id,
        "recovery_test_run_id": recovery_test_run_id,
        "source_event_id": fixture_id,
        "test_fixture": True,
        "synthetic_recovery_test": True,
        "exclude_from_performance": True,
        "exclude_from_calibration": True,
        "exclude_from_campaign_metrics": True,
        "exclude_from_daily_reports": True,
        "exclude_from_research": True,
        "paper_only": True,
        "live_trading_enabled": False,
        "broker_connections_enabled": False,
    }


def _levels(action: str) -> dict[str, float]:
    if action == "sell":
        return {"entry": 100.0, "stop": 101.0, "target": 97.0}
    return {"entry": 100.0, "stop": 99.0, "target": 103.0}


def _fixture_from_order(order: PendingPaperOrder, campaign_id: str, fixture_id: str, recovery_test_run_id: str | None = None) -> RecoveryTestFixture:
    risk = abs(order.entry_price - order.stop_loss)
    risk_amount = 100.0
    return RecoveryTestFixture(
        fixture_id=fixture_id,
        fixture_type="PENDING_ORDER",
        campaign_id=campaign_id,
        created_at=order.created_at,
        status=order.status,
        symbol=order.symbol,
        timeframe=order.timeframe,
        higher_timeframe=order.higher_timeframe,
        action=order.action,
        strategy=order.strategy,
        setup=order.setup,
        order_id=order.order_id,
        trade_id=order.trade_id,
        entry_price=order.entry_price,
        stop_loss=order.stop_loss,
        target=order.target,
        target_r=round(abs(order.target - order.entry_price) / risk, 6),
        risk_amount=risk_amount,
        risk_per_trade_percent=float(order.risk_per_trade_percent or 1.0),
        position_size=round(risk_amount / risk, 8),
        recovery_test_run_id=recovery_test_run_id or (order.metadata or {}).get("recovery_test_run_id"),
    )


def _fixture_from_trade(trade: PaperTrade, campaign_id: str, fixture_id: str, fixture_type: str, recovery_test_run_id: str | None = None) -> RecoveryTestFixture:
    return RecoveryTestFixture(
        fixture_id=fixture_id,
        fixture_type=fixture_type,
        campaign_id=campaign_id,
        created_at=trade.opened_at,
        status=trade.status,
        symbol=trade.symbol,
        timeframe=trade.timeframe,
        higher_timeframe=trade.higher_timeframe,
        action=trade.action,
        strategy=trade.strategy,
        setup=trade.setup,
        order_id=None,
        trade_id=trade.trade_id,
        entry_price=trade.entry_price,
        stop_loss=trade.stop_loss,
        target=trade.target,
        target_r=trade.target_r,
        risk_amount=trade.risk_amount,
        risk_per_trade_percent=trade.risk_per_trade_percent,
        position_size=trade.position_size,
        recovery_test_run_id=recovery_test_run_id or (trade.metadata or {}).get("recovery_test_run_id"),
    )


def _fixture_dict_from_order(order: PendingPaperOrder) -> dict[str, Any]:
    campaign_id = str((order.metadata or {}).get("campaign_id"))
    fixture_id = str((order.metadata or {}).get("fixture_id") or order.source_event_id)
    return jsonable_encoder(_fixture_from_order(order, campaign_id, fixture_id, (order.metadata or {}).get("recovery_test_run_id")))


def _fixture_dict_from_trade(trade: PaperTrade) -> dict[str, Any]:
    metadata = trade.metadata or {}
    return jsonable_encoder(_fixture_from_trade(
        trade,
        str(metadata.get("campaign_id")),
        str(metadata.get("fixture_id") or trade.source_event_id or trade.trade_id),
        str(metadata.get("fixture_type") or ("CLOSED_TRADE" if trade.status == "closed" else "OPEN_TRADE")),
        metadata.get("recovery_test_run_id"),
    ))


def _diff(fixture_id: str, field: str, expected: Any, actual: Any, severity: str, message: str, difference_type: str = "RECOVERY_DIFFERENCE") -> RecoveryTestDifference:
    return RecoveryTestDifference(fixture_id=fixture_id, field=field, expected=expected, actual=actual, severity=severity, message=message, difference_type=difference_type)


def _same(left: Any, right: Any) -> bool:
    if isinstance(left, float) or isinstance(right, float):
        try:
            return abs(float(left) - float(right)) <= 1e-9
        except (TypeError, ValueError):
            return False
    return left == right


def _not_ready_verification(reason: str, recovery_test_run_id: str | None = None) -> RecoveryTestVerification:
    status = "AMBIGUOUS" if reason == "AMBIGUOUS" else "NOT_READY"
    diff = _diff(
        recovery_test_run_id or "recovery_test_run",
        "run_state",
        "SNAPSHOT_READY",
        reason,
        "blocking",
        "No valid SNAPSHOT_READY recovery test run exists for verification." if status == "NOT_READY" else "Multiple SNAPSHOT_READY runs exist; provide an explicit recovery_test_run_id.",
        "RUN_STATE_DIFFERENCE",
    )
    return RecoveryTestVerification(
        status=status,
        campaign_id_match=False,
        pending_orders_expected=0,
        pending_orders_recovered=0,
        open_trades_expected=0,
        open_trades_recovered=0,
        order_ids_match=False,
        trade_ids_match=False,
        price_geometry_match=False,
        lifecycle_state_match=False,
        reconciliation_status="NOT_RUN",
        differences=(diff,),
        human_readable_summary=diff.message,
        recovery_test_run_id=recovery_test_run_id,
        recovery_failure=False,
        harness_precondition_failure=True,
    )


def _blocked_verification(run: RecoveryTestRun, difference_type: str, message: str) -> RecoveryTestVerification:
    diff = _diff(run.recovery_test_run_id, "run_state", "SNAPSHOT_READY", run.state, "blocking", message, difference_type)
    return RecoveryTestVerification(
        status="NOT_READY",
        campaign_id_match=False,
        pending_orders_expected=0,
        pending_orders_recovered=0,
        open_trades_expected=0,
        open_trades_recovered=0,
        order_ids_match=False,
        trade_ids_match=False,
        price_geometry_match=False,
        lifecycle_state_match=False,
        reconciliation_status="NOT_RUN",
        differences=(diff,),
        human_readable_summary=message,
        recovery_test_run_id=run.recovery_test_run_id,
        snapshot_id=run.snapshot_id,
        recovery_failure=False,
        harness_precondition_failure=True,
    )


def _run_from_row(row: dict[str, Any]) -> RecoveryTestRun:
    state = str(row.get("state") or "INCOMPLETE")
    return RecoveryTestRun(
        recovery_test_run_id=str(row.get("recovery_test_run_id")),
        state=state,
        created_at=str(row.get("created_at") or row.get("updated_at") or _now()),
        updated_at=str(row.get("updated_at") or row.get("created_at") or _now()),
        campaign_id=row.get("campaign_id"),
        fixture_ids=tuple(row.get("fixture_ids") or ()),
        order_ids=tuple(row.get("order_ids") or ()),
        trade_ids=tuple(row.get("trade_ids") or ()),
        snapshot_id=row.get("snapshot_id"),
        snapshot_status=row.get("snapshot_status"),
        note=row.get("note"),
        active_fixture_count=int(row.get("active_fixture_count", 0) or 0),
        recommended_action=_recommended_run_action(state),
    )


def _recommended_run_action(state: str) -> str:
    if state == "INCOMPLETE":
        return "Retry snapshot for this run if fixtures remain active, or clean up the run explicitly."
    if state == "SNAPSHOT_READY":
        return "Restart StructureIQ and verify this run by recovery_test_run_id."
    if state in {"VERIFIED_PASS", "VERIFIED_FAIL"}:
        return "Clean up this run explicitly."
    if state == "CLEANED":
        return "No action required."
    return "Continue the transactional recovery-test flow."


def _recovery_run_id() -> str:
    return f"recovery_run_{datetime.now(timezone.utc).strftime('%Y_%m_%d')}_{_hash(_now())}"


def _snapshot_id(recovery_test_run_id: str) -> str:
    return f"snapshot_{_hash(recovery_test_run_id + ':' + _now())}"


def _fixture_id(kind: str, symbol: str, action: str) -> str:
    return f"fixture_{_hash(f'{kind}:{symbol}:{action}:{_now()}')}"


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:12]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


_GLOBAL_RECOVERY_TEST_HARNESS: RecoveryTestHarness | None = None


def get_global_recovery_test_harness(
    broker: PaperBrokerageEngine,
    lifecycle: TradeLifecycleManager,
    campaigns: ValidationCampaignManager,
    reconciliation: PaperStateReconciliationEngine,
    recovery: PaperRecoveryEngine,
) -> RecoveryTestHarness:
    global _GLOBAL_RECOVERY_TEST_HARNESS
    if (
        _GLOBAL_RECOVERY_TEST_HARNESS is None
        or _GLOBAL_RECOVERY_TEST_HARNESS.broker is not broker
        or _GLOBAL_RECOVERY_TEST_HARNESS.lifecycle is not lifecycle
    ):
        _GLOBAL_RECOVERY_TEST_HARNESS = RecoveryTestHarness(
            broker=broker,
            lifecycle=lifecycle,
            campaigns=campaigns,
            reconciliation=reconciliation,
            recovery=recovery,
        )
    return _GLOBAL_RECOVERY_TEST_HARNESS


def latest_recovery_test_status() -> RecoveryTestStatus | None:
    return _GLOBAL_RECOVERY_TEST_HARNESS.status() if _GLOBAL_RECOVERY_TEST_HARNESS is not None else None
