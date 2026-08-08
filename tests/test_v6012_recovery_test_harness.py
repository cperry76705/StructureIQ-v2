from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

import start
from app.main import app
from core.market_data import Candle
from core.paper_brokerage import PaperAccountConfig, PaperBrokerageEngine, PaperOpenRequest
from core.paper_recovery import PaperRecoveryEngine
from core.paper_state_reconciliation import PaperStateReconciliationEngine
from core.paper_trade_journal import PaperTradeJournal
from core.recovery_test_harness import RecoveryTestFixtureRequest, RecoveryTestHarness
from core.trade_lifecycle_manager import LifecycleConfig, TradeLifecycleManager
from core.validation_campaigns import ValidationCampaignManager


class _Provider:
    provider_name = "recovery-test"

    def get_candles(self, symbol, timeframe, lookback):
        del symbol, timeframe
        return [Candle(i, 100, 101, 99, 100, 1000) for i in range(lookback)]


class _Monitor:
    def find_event(self, event_id): return None
    def events(self): return ()
    def status(self): return SimpleNamespace(last_error=None)
    def mark_paper_trade_created(self, event_id): return None


class _Reports:
    def latest(self): return None


class _Orchestrator:
    def status(self): return SimpleNamespace(cycle_count=0)
    def recent_actions(self, limit=None): return ()


def _stack(tmp_path: Path):
    broker = PaperBrokerageEngine(PaperAccountConfig(durable_state=True, persistence_dir=str(tmp_path / "research")))
    lifecycle = TradeLifecycleManager(
        _Provider(),
        _Monitor(),
        broker,
        LifecycleConfig(durable_state=True, persistence_path=str(tmp_path / "research" / "lifecycle_state.json")),
    )
    journal = PaperTradeJournal(broker, lifecycle, tmp_path / "research" / "paper_trade_journal.jsonl")
    campaigns = ValidationCampaignManager(tmp_path / "validation_campaigns", journal)
    reconciliation = PaperStateReconciliationEngine(
        broker=broker,
        lifecycle=lifecycle,
        journal=journal,
        reports=_Reports(),
        orchestrator=_Orchestrator(),
        campaigns=campaigns,
        history_path=tmp_path / "reports" / "paper_reconciliation_history.jsonl",
    )
    recovery = PaperRecoveryEngine(
        broker=broker,
        lifecycle=lifecycle,
        journal=journal,
        reconciliation=reconciliation,
        orphan_path=tmp_path / "research" / "paper_orphans.json",
    )
    harness = RecoveryTestHarness(
        broker=broker,
        lifecycle=lifecycle,
        campaigns=campaigns,
        reconciliation=reconciliation,
        recovery=recovery,
        reports_dir=tmp_path / "reports",
    )
    return broker, lifecycle, journal, campaigns, reconciliation, recovery, harness


def test_recovery_test_creates_valid_buy_and_sell_fixtures(tmp_path: Path):
    _, _, _, _, _, _, harness = _stack(tmp_path)

    buy = harness.create_pending_order(RecoveryTestFixtureRequest(symbol="GBP-USD", action="buy"))
    sell = harness.create_open_trade(RecoveryTestFixtureRequest(symbol="EUR-USD", action="sell"))

    assert buy.test_fixture is True
    assert buy.synthetic_recovery_test is True
    assert buy.stop_loss < buy.entry_price < buy.target
    assert sell.target < sell.entry_price < sell.stop_loss
    assert buy.campaign_id.startswith("recovery_test_")
    assert sell.exclude_from_performance is True
    status = harness.status()
    assert status.pending_fixture_count == 1
    assert status.open_fixture_count == 1
    assert status.ready_for_restart_test is True


def test_recovery_test_snapshot_and_simulated_restart_verify_exact_state(tmp_path: Path):
    _, _, _, _, _, _, harness = _stack(tmp_path)
    pending = harness.create_pending_order()
    opened = harness.create_open_trade()
    snapshot = harness.snapshot()

    _, _, _, _, _, _, restored = _stack(tmp_path)
    result = restored.verify_after_restart()

    assert snapshot.snapshot_status == "PASS"
    assert result.status == "PASS"
    assert result.pending_orders_expected == 1
    assert result.pending_orders_recovered == 1
    assert result.open_trades_expected == 1
    assert result.open_trades_recovered == 1
    assert result.order_ids_match is True
    assert result.trade_ids_match is True
    recovered = restored.status()
    assert pending.fixture_id in recovered.fixture_ids
    assert opened.fixture_id in recovered.fixture_ids


def test_recovery_test_verify_fails_when_price_geometry_changes(tmp_path: Path):
    _, _, _, _, _, _, harness = _stack(tmp_path)
    harness.create_open_trade()
    harness.snapshot()

    research = tmp_path / "research" / "paper_open_positions.json"
    raw = research.read_text(encoding="utf-8")
    research.write_text(raw.replace('"stop_loss": 99.0', '"stop_loss": 98.5'), encoding="utf-8")

    _, _, _, _, _, _, restored = _stack(tmp_path)
    result = restored.verify_after_restart()

    assert result.status == "FAIL"
    assert any(item.field == "stop_loss" for item in result.differences)


def test_closed_fixture_is_excluded_from_performance_journal_and_campaign(tmp_path: Path):
    broker, _, journal, campaigns, _, _, harness = _stack(tmp_path)

    fixture = harness.create_closed_trade()
    real = broker.open_position(PaperOpenRequest(
        source_event_id="real",
        symbol="AUD-USD",
        timeframe="5m",
        higher_timeframe="1h",
        action="buy",
        setup="real_setup",
        strategy="real_strategy",
        entry_price=100,
        stop_loss=99,
        target=102,
        allow_duplicate=True,
    ))
    broker.close_position(real.trade_id, 102)

    performance = broker.performance()
    summary = journal.summary()
    campaign_summary = campaigns.summary(fixture.campaign_id)

    assert performance.closed_trades == 1
    assert performance.total_r == 2.0
    assert summary.synthetic_test_trades >= 1
    assert summary.total_r == 2.0
    assert campaign_summary.trades == 0
    assert campaign_summary.total_r == 0.0


def test_recovery_test_cleanup_only_removes_tagged_fixtures(tmp_path: Path):
    broker, lifecycle, _, _, _, _, harness = _stack(tmp_path)
    harness.create_pending_order()
    harness.create_open_trade()
    real = broker.open_position(PaperOpenRequest(
        source_event_id="real",
        symbol="NZD-USD",
        timeframe="5m",
        higher_timeframe="1h",
        action="buy",
        setup="real_setup",
        strategy="real_strategy",
        entry_price=100,
        stop_loss=99,
        target=102,
        allow_duplicate=True,
    ))

    result = harness.cleanup()

    assert result.status == "PASS"
    assert result.active_test_fixtures_remaining == 0
    assert broker.open_positions()[0].trade_id == real.trade_id
    assert lifecycle.pending_orders() == ()
    assert harness.history()


def test_recovery_test_api_and_cli_helpers(tmp_path: Path):
    _, _, _, _, _, _, harness = _stack(tmp_path)
    client = TestClient(app)
    paths = client.get("/openapi.json").json()["paths"]
    assert "/recovery-test/create-pending-order" in paths
    assert "/recovery-test/verify-after-restart" in paths

    calls = []

    def api(path, **kwargs):
        calls.append((path, kwargs.get("method", "GET")))
        if path == "/health": return {"status": "ok"}
        if path == "/recovery-test/create-pending-order": return {"order_id": "test_order_123"}
        if path == "/recovery-test/create-open-trade": return {"trade_id": "test_trade_456"}
        if path == "/recovery-test/snapshot": return {"snapshot_status": "PASS", "campaign_id": "recovery_test_123"}
        if path == "/paper-recovery/run": return {"status": "PASS"}
        if path == "/paper-reconciliation/run": return {"status": "PASS"}
        if path == "/recovery-test/verify-after-restart":
            return {
                "status": "PASS",
                "pending_orders_expected": 1,
                "pending_orders_recovered": 1,
                "open_trades_expected": 1,
                "open_trades_recovered": 1,
                "order_ids_match": True,
                "trade_ids_match": True,
                "price_geometry_match": True,
                "lifecycle_state_match": True,
                "human_readable_summary": "All restored.",
            }
        if path == "/recovery-test/cleanup":
            return {"status": "PASS", "fixtures_archived": 2, "active_test_fixtures_remaining": 0, "human_readable_summary": "Clean."}
        return {}

    process = lambda *a, **k: SimpleNamespace(poll=lambda: 0, terminate=lambda: None, wait=lambda timeout=None: 0, kill=lambda: None)
    assert start.run_recovery_test_mode("create", process_factory=process, api_call=api, sleep=lambda _: None, port_available=lambda: False) == 0
    assert start.run_recovery_test_mode("verify", process_factory=process, api_call=api, sleep=lambda _: None, port_available=lambda: False) == 0
    assert start.run_recovery_test_mode("cleanup", process_factory=process, api_call=api, sleep=lambda _: None, port_available=lambda: False) == 0
    assert harness.writable() is True
