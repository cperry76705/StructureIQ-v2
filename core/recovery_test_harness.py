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


@dataclass(frozen=True)
class RecoveryTestSnapshot:
    snapshot_status: str
    snapshot_id: str
    campaign_id: str | None
    snapshot_at: str
    pending_orders: int
    open_trades: int
    closed_trades: int
    ready_for_restart: bool
    fixtures: tuple[dict[str, Any], ...]
    human_readable_summary: str


@dataclass(frozen=True)
class RecoveryTestDifference:
    fixture_id: str
    field: str
    expected: Any
    actual: Any
    severity: str
    message: str


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


@dataclass(frozen=True)
class RecoveryTestCleanupResult:
    status: str
    fixtures_archived: int
    active_test_fixtures_remaining: int
    cleanup_status: str
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
        self.history_path = self.reports_dir / "recovery_test_history.jsonl"

    def create_pending_order(self, request: RecoveryTestFixtureRequest | None = None) -> RecoveryTestFixture:
        self._assert_paper_only()
        req = request or RecoveryTestFixtureRequest()
        campaign = self.campaigns.recovery_test_campaign()
        fixture_id = _fixture_id("pending", req.symbol, req.action)
        levels = _levels(req.action)
        metadata = _metadata(fixture_id, "PENDING_ORDER", campaign.campaign_id)
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
        fixture = _fixture_from_order(order, campaign.campaign_id, fixture_id)
        self._history({"test_id": fixture_id, "campaign_id": campaign.campaign_id, "created_at": fixture.created_at, "status": "CREATED", "fixtures_expected": 1})
        return fixture

    def create_open_trade(self, request: RecoveryTestFixtureRequest | None = None) -> RecoveryTestFixture:
        self._assert_paper_only()
        req = request or RecoveryTestFixtureRequest()
        campaign = self.campaigns.recovery_test_campaign()
        fixture_id = _fixture_id("open", req.symbol, req.action)
        trade = self._open_fixture_trade(fixture_id, "OPEN_TRADE", campaign.campaign_id, req.symbol, req.action)
        self.lifecycle.register_recovery_test_open_trade(trade)
        fixture = _fixture_from_trade(trade, campaign.campaign_id, fixture_id, "OPEN_TRADE")
        self._history({"test_id": fixture_id, "campaign_id": campaign.campaign_id, "created_at": fixture.created_at, "status": "CREATED", "fixtures_expected": 1})
        return fixture

    def create_closed_trade(self, request: RecoveryTestFixtureRequest | None = None) -> RecoveryTestFixture:
        self._assert_paper_only()
        req = request or RecoveryTestFixtureRequest()
        campaign = self.campaigns.recovery_test_campaign()
        fixture_id = _fixture_id("closed", req.symbol, req.action)
        trade = self._open_fixture_trade(fixture_id, "CLOSED_TRADE", campaign.campaign_id, req.symbol, req.action)
        self.lifecycle.register_recovery_test_open_trade(trade)
        exit_price = trade.target
        closed = self.broker.close_position(trade.trade_id, exit_price)
        self.lifecycle.register_recovery_test_open_trade(closed)
        fixture = _fixture_from_trade(closed, campaign.campaign_id, fixture_id, "CLOSED_TRADE")
        self._history({"test_id": fixture_id, "campaign_id": campaign.campaign_id, "created_at": fixture.created_at, "status": "CREATED", "fixtures_expected": 1})
        return fixture

    def status(self) -> RecoveryTestStatus:
        fixtures = self._fixtures()
        pending = [item for item in fixtures if item["fixture_type"] == "PENDING_ORDER"]
        open_trades = [item for item in fixtures if item["fixture_type"] == "OPEN_TRADE"]
        closed = [item for item in fixtures if item["fixture_type"] == "CLOSED_TRADE"]
        campaign_id = fixtures[0]["campaign_id"] if fixtures else None
        ready = bool(pending or open_trades)
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
        )

    def snapshot(self) -> RecoveryTestSnapshot:
        fixtures = tuple(self._fixtures())
        snapshot_id = hashlib.sha256(f"recovery-snapshot:{_now()}:{len(fixtures)}".encode()).hexdigest()[:24]
        campaign_id = fixtures[0]["campaign_id"] if fixtures else None
        snapshot = RecoveryTestSnapshot(
            snapshot_status="PASS" if fixtures else "WATCHLIST",
            snapshot_id=snapshot_id,
            campaign_id=campaign_id,
            snapshot_at=_now(),
            pending_orders=sum(item["fixture_type"] == "PENDING_ORDER" for item in fixtures),
            open_trades=sum(item["fixture_type"] == "OPEN_TRADE" for item in fixtures),
            closed_trades=sum(item["fixture_type"] == "CLOSED_TRADE" for item in fixtures),
            ready_for_restart=any(item["fixture_type"] in {"PENDING_ORDER", "OPEN_TRADE"} for item in fixtures),
            fixtures=fixtures,
            human_readable_summary="Recovery test snapshot captured durable synthetic paper state.",
        )
        self.snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        self.snapshot_path.write_text(json.dumps(jsonable_encoder(snapshot), indent=2), encoding="utf-8")
        self._history({"test_id": snapshot_id, "campaign_id": campaign_id, "snapshot_at": snapshot.snapshot_at, "status": snapshot.snapshot_status, "fixtures_expected": len(fixtures)})
        return snapshot

    def verify_after_restart(self) -> RecoveryTestVerification:
        self.broker.recover_from_storage()
        self.lifecycle.recover_from_storage()
        self.recovery.run(persist_reconciliation=False)
        expected = self._load_snapshot()
        actual = {item["fixture_id"]: item for item in self._fixtures()}
        differences: list[RecoveryTestDifference] = []
        for row in expected:
            fixture_id = str(row["fixture_id"])
            observed = actual.get(fixture_id)
            if observed is None:
                differences.append(_diff(fixture_id, "fixture", "present", "missing", "critical", "Expected fixture was not recovered."))
                continue
            for field in ("campaign_id", "order_id", "trade_id", "symbol", "status", "entry_price", "stop_loss", "target", "risk_amount", "position_size"):
                if not _same(row.get(field), observed.get(field)):
                    differences.append(_diff(fixture_id, field, row.get(field), observed.get(field), "critical", f"Recovered fixture field {field} did not match the snapshot."))
            if row.get("lifecycle_event_count", 0) and not observed.get("lifecycle_event_count", 0):
                differences.append(_diff(fixture_id, "lifecycle_state", row.get("lifecycle_event_count"), observed.get("lifecycle_event_count"), "critical", "Recovered fixture is missing lifecycle state."))
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
        )
        self._history({"test_id": getattr(self._snapshot(), "snapshot_id", None), "campaign_id": campaign_id, "verified_at": _now(), "status": result.status, "fixtures_expected": len(expected), "fixtures_recovered": len(actual), "differences": jsonable_encoder(result.differences), "reconciliation_status": reconciliation_status})
        return result

    def cleanup(self) -> RecoveryTestCleanupResult:
        before = len(self._fixtures())
        lifecycle_removed = self.lifecycle.remove_recovery_test_fixtures()
        broker_removed = self.broker.remove_recovery_test_fixtures()
        after = len(self._fixtures())
        status = "PASS" if after == 0 else "WATCHLIST"
        result = RecoveryTestCleanupResult(
            status=status,
            fixtures_archived=before,
            active_test_fixtures_remaining=after,
            cleanup_status=status,
            human_readable_summary=f"Archived {before} synthetic recovery fixtures; {after} active test fixtures remain.",
        )
        self._history({"test_id": f"cleanup_{_hash(_now())}", "campaign_id": self.status().active_test_campaign_id, "status": status, "cleanup_status": status, "fixtures_recovered": broker_removed + lifecycle_removed, "fixtures_expected": before})
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

    def _open_fixture_trade(self, fixture_id: str, fixture_type: str, campaign_id: str, symbol: str, action: str) -> PaperTrade:
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
            metadata=_metadata(fixture_id, fixture_type, campaign_id),
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

    def _snapshot(self) -> RecoveryTestSnapshot | None:
        if not self.snapshot_path.exists():
            return None
        try:
            return RecoveryTestSnapshot(**json.loads(self.snapshot_path.read_text(encoding="utf-8")))
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


def _metadata(fixture_id: str, fixture_type: str, campaign_id: str) -> dict[str, Any]:
    return {
        "fixture_id": fixture_id,
        "fixture_type": fixture_type,
        "campaign_id": campaign_id,
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


def _fixture_from_order(order: PendingPaperOrder, campaign_id: str, fixture_id: str) -> RecoveryTestFixture:
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
    )


def _fixture_from_trade(trade: PaperTrade, campaign_id: str, fixture_id: str, fixture_type: str) -> RecoveryTestFixture:
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
    )


def _fixture_dict_from_order(order: PendingPaperOrder) -> dict[str, Any]:
    campaign_id = str((order.metadata or {}).get("campaign_id"))
    fixture_id = str((order.metadata or {}).get("fixture_id") or order.source_event_id)
    return jsonable_encoder(_fixture_from_order(order, campaign_id, fixture_id))


def _fixture_dict_from_trade(trade: PaperTrade) -> dict[str, Any]:
    metadata = trade.metadata or {}
    return jsonable_encoder(_fixture_from_trade(
        trade,
        str(metadata.get("campaign_id")),
        str(metadata.get("fixture_id") or trade.source_event_id or trade.trade_id),
        str(metadata.get("fixture_type") or ("CLOSED_TRADE" if trade.status == "closed" else "OPEN_TRADE")),
    ))


def _diff(fixture_id: str, field: str, expected: Any, actual: Any, severity: str, message: str) -> RecoveryTestDifference:
    return RecoveryTestDifference(fixture_id=fixture_id, field=field, expected=expected, actual=actual, severity=severity, message=message)


def _same(left: Any, right: Any) -> bool:
    if isinstance(left, float) or isinstance(right, float):
        try:
            return abs(float(left) - float(right)) <= 1e-9
        except (TypeError, ValueError):
            return False
    return left == right


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
