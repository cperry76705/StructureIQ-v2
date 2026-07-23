from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app, get_paper_recovery_engine, get_validation_campaign_manager
from core.live_market_monitor import MonitorEvent
from core.paper_brokerage import PaperAccountConfig, PaperBrokerageEngine, PaperOpenRequest
from core.paper_recovery import PaperRecoveryEngine
from core.paper_state_reconciliation import PaperStateReconciliationEngine
from core.paper_trade_journal import PaperTradeJournal
from core.trade_lifecycle_manager import ApproveCandidateRequest, LifecycleConfig, TradeLifecycleManager
from core.validation_campaigns import ValidationCampaignManager


class _Provider:
    provider_name = "synthetic"
    def get_candles(self, symbol, timeframe, lookback):
        return []


class _Monitor:
    def __init__(self, event=None):
        self.event = event
    def find_event(self, event_id):
        return self.event if self.event and self.event.event_id == event_id else None
    def events(self, limit=None):
        return (self.event,) if self.event else ()
    def mark_paper_trade_created(self, event_id):
        return self.event
    def status(self):
        return SimpleNamespace(signal_count=0, error_count=0, last_error=None, running=False)


class _Reports:
    def latest(self):
        return None


class _Orchestrator:
    def status(self):
        return SimpleNamespace(cycle_count=0)
    def recent_actions(self, limit=None):
        return ()


def _event() -> MonitorEvent:
    return MonitorEvent(
        event_id="event-1", timestamp="2026-07-23T00:00:00+00:00",
        symbol="BTC-USD", timeframe="5m", higher_timeframe="1h",
        candle_timestamp=1, action="buy", setup="test_setup",
        strategy="test_strategy", confidence=8.0,
        setup_quality={"score": 90, "grade": "A"},
        score_summary=None, execution_intelligence={"execution_blockers": []},
        confidence_calibration=None, symbol_profile=None,
        adaptive_strategy_router=None, strategy_rating=None, setup_rating=None,
        entry_zone="100", stop_loss="99", target="103", reasons=("test",),
    )


def _stack(tmp_path: Path, *, durable=True):
    broker = PaperBrokerageEngine(PaperAccountConfig(durable_state=durable, persistence_dir=str(tmp_path / "research")))
    monitor = _Monitor(_event())
    lifecycle = TradeLifecycleManager(
        _Provider(), monitor, broker,
        LifecycleConfig(durable_state=durable, persistence_path=str(tmp_path / "research" / "lifecycle_state.json")),
    )
    journal = PaperTradeJournal(broker, lifecycle, tmp_path / "research" / "paper_trade_journal.jsonl")
    reconciliation = PaperStateReconciliationEngine(
        broker=broker, lifecycle=lifecycle, journal=journal,
        reports=_Reports(), orchestrator=_Orchestrator(),
        history_path=tmp_path / "reports" / "paper_reconciliation_history.jsonl",
    )
    recovery = PaperRecoveryEngine(
        broker=broker, lifecycle=lifecycle, journal=journal,
        reconciliation=reconciliation, orphan_path=tmp_path / "research" / "paper_orphans.json",
    )
    return broker, lifecycle, journal, reconciliation, recovery


def test_durable_brokerage_restores_open_and_closed_trades(tmp_path) -> None:
    broker, *_ = _stack(tmp_path)
    opened = broker.open_position(PaperOpenRequest(
        symbol="BTC-USD", timeframe="5m", higher_timeframe="1h",
        action="buy", setup="setup_a", strategy="strategy_a",
        entry_price=100, stop_loss=99, target=103,
    ))
    broker.close_position(opened.trade_id, 103)

    restored = PaperBrokerageEngine(PaperAccountConfig(durable_state=True, persistence_dir=str(tmp_path / "research")))

    assert restored.account().balance == 10300
    assert len(restored.closed_trades()) == 1
    assert restored.performance().total_r == 3
    assert (tmp_path / "research" / "paper_account.json").exists()
    assert (tmp_path / "research" / "paper_open_positions.json").exists()
    assert (tmp_path / "research" / "paper_closed_trades.json").exists()


def test_durable_lifecycle_restores_pending_orders(tmp_path) -> None:
    broker, lifecycle, *_ = _stack(tmp_path)
    order = lifecycle.approve_candidate(ApproveCandidateRequest(event_id="event-1"))

    restored_broker = PaperBrokerageEngine(PaperAccountConfig(durable_state=True, persistence_dir=str(tmp_path / "research")))
    restored_lifecycle = TradeLifecycleManager(
        _Provider(), _Monitor(_event()), restored_broker,
        LifecycleConfig(durable_state=True, persistence_path=str(tmp_path / "research" / "lifecycle_state.json")),
    )

    assert restored_lifecycle.pending_orders()[0].order_id == order.order_id
    assert len(restored_lifecycle.events()) >= 1


def test_recovery_after_restart_reconciles_restored_state(tmp_path) -> None:
    broker, lifecycle, journal, reconciliation, recovery = _stack(tmp_path)
    broker.open_position(PaperOpenRequest(
        symbol="ETH-USD", timeframe="5m", higher_timeframe="1h",
        action="sell", setup="setup_b", strategy="strategy_b",
        entry_price=100, stop_loss=101, target=97,
    ))

    restored_broker = PaperBrokerageEngine(PaperAccountConfig(durable_state=True, persistence_dir=str(tmp_path / "research")))
    restored_lifecycle = TradeLifecycleManager(
        _Provider(), _Monitor(_event()), restored_broker,
        LifecycleConfig(durable_state=True, persistence_path=str(tmp_path / "research" / "lifecycle_state.json")),
    )
    restored_journal = PaperTradeJournal(restored_broker, restored_lifecycle, tmp_path / "research" / "paper_trade_journal.jsonl")
    restored_reconciliation = PaperStateReconciliationEngine(
        broker=restored_broker, lifecycle=restored_lifecycle, journal=restored_journal,
        reports=_Reports(), orchestrator=_Orchestrator(),
        history_path=tmp_path / "reports" / "paper_reconciliation_history.jsonl",
    )
    restored_recovery = PaperRecoveryEngine(
        broker=restored_broker, lifecycle=restored_lifecycle, journal=restored_journal,
        reconciliation=restored_reconciliation, orphan_path=tmp_path / "research" / "paper_orphans.json",
    )

    result = restored_recovery.run()

    assert result.summary.recovered_open_positions == 1
    assert result.summary.reconciliation_status in {"PASS", "WATCHLIST"}
    assert (tmp_path / "research" / "paper_orphans.json").exists()


def test_orphan_creation_when_journal_trade_unmatched(tmp_path) -> None:
    broker, lifecycle, journal, reconciliation, recovery = _stack(tmp_path)
    trade = broker.open_position(PaperOpenRequest(
        symbol="BTC-USD", timeframe="5m", higher_timeframe="1h",
        action="buy", setup="setup_c", strategy="strategy_c",
        entry_price=100, stop_loss=99, target=103,
    ))
    empty_broker = PaperBrokerageEngine(PaperAccountConfig(durable_state=False))
    empty_lifecycle = TradeLifecycleManager(_Provider(), _Monitor(), empty_broker)
    orphan_reconciliation = PaperStateReconciliationEngine(
        broker=empty_broker, lifecycle=empty_lifecycle, journal=journal,
        reports=_Reports(), orchestrator=_Orchestrator(), history_path=tmp_path / "reports" / "r.jsonl",
    )
    orphan_recovery = PaperRecoveryEngine(
        broker=empty_broker, lifecycle=empty_lifecycle, journal=journal,
        reconciliation=orphan_reconciliation, orphan_path=tmp_path / "research" / "paper_orphans.json",
    )

    result = orphan_recovery.run()

    assert result.summary.orphaned_trades == 1
    assert result.orphans[0].trade_id == trade.trade_id


def test_campaign_creation_isolation_and_legacy_migration(tmp_path) -> None:
    broker, lifecycle, journal, *_ = _stack(tmp_path)
    broker.open_position(PaperOpenRequest(
        symbol="BTC-USD", timeframe="5m", higher_timeframe="1h",
        action="buy", setup="setup_d", strategy="strategy_d",
        entry_price=100, stop_loss=99, target=103,
    ))

    manager = ValidationCampaignManager(tmp_path / "validation_campaigns", journal)
    campaigns = manager.list_campaigns()
    assert campaigns and campaigns[0].legacy_import is True

    new_campaign = manager.start("Recovery Test", paper_settings={"auto_approve_candidates": False})
    assert manager.current().campaign_id == new_campaign.campaign_id
    assert (tmp_path / "validation_campaigns" / new_campaign.campaign_id / "summary.json").exists()
    assert (tmp_path / "validation_campaigns" / new_campaign.campaign_id / "journal.jsonl").exists()
    assert manager.summary(new_campaign.campaign_id).campaign_id == new_campaign.campaign_id


def test_recovery_and_campaign_api_endpoints(monkeypatch, tmp_path) -> None:
    _, _, journal, _, recovery = _stack(tmp_path)
    manager = ValidationCampaignManager(tmp_path / "validation_campaigns", journal)
    campaign = manager.start("API Campaign")

    app.dependency_overrides[get_paper_recovery_engine] = lambda: recovery
    app.dependency_overrides[get_validation_campaign_manager] = lambda: manager
    try:
        with TestClient(app) as client:
            paths = client.get("/openapi.json").json()["paths"]
            for path in (
                "/paper-recovery/status", "/paper-recovery/summary", "/paper-recovery/run",
                "/campaigns", "/campaigns/current", "/campaigns/{campaign_id}",
                "/campaigns/{campaign_id}/summary", "/campaigns/{campaign_id}/journal",
            ):
                assert path in paths
            assert client.get("/paper-recovery/status").json()["status"] in {"PASS", "WATCHLIST", "FAIL"}
            assert client.post("/paper-recovery/run").json()["paper_only"] is True
            assert client.get("/campaigns/current").json()["campaign_id"] == campaign.campaign_id
            assert client.get(f"/campaigns/{campaign.campaign_id}/summary").json()["campaign_id"] == campaign.campaign_id
            overview = client.get("/dashboard/overview").json()
            assert "current_campaign_id" in overview
            assert "recovery_status" in overview
    finally:
        app.dependency_overrides.clear()
