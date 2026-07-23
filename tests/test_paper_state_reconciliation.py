from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app, get_paper_state_reconciliation_engine
from core.paper_brokerage import PaperBrokerageEngine, PaperOpenRequest
from core.paper_state_reconciliation import (
    PaperReconciliationResult,
    PaperReconciliationSummary,
    PaperStateDiscrepancy,
    PaperStateReconciliationEngine,
    ReconciledTradeRecord,
)
from core.paper_trade_journal import PaperTradeJournal, PaperTradeJournalEntry
from core.trade_lifecycle_manager import TradeLifecycleManager


class _Provider:
    provider_name = "test"

    def get_candles(self, symbol, timeframe, lookback):
        return []


class _Monitor:
    def __init__(self):
        self._events = {}

    def find_event(self, event_id):
        return self._events.get(event_id)

    def events(self, limit=None):
        return tuple(self._events.values())

    def status(self):
        return SimpleNamespace(signal_count=0, error_count=0, last_error=None, running=False)


class _Reports:
    def __init__(self, latest=None):
        self._latest = latest

    def latest(self):
        return self._latest


def _real_engine(tmp_path: Path) -> PaperStateReconciliationEngine:
    broker = PaperBrokerageEngine()
    monitor = _Monitor()
    lifecycle = TradeLifecycleManager(_Provider(), monitor, broker)
    journal = PaperTradeJournal(broker, lifecycle, tmp_path / "journal.jsonl")
    orchestrator = SimpleNamespace(
        status=lambda: SimpleNamespace(cycle_count=0),
        recent_actions=lambda limit=None: (),
    )
    return PaperStateReconciliationEngine(
        broker=broker, lifecycle=lifecycle, journal=journal,
        reports=_Reports(), orchestrator=orchestrator,
        history_path=tmp_path / "reconciliation.jsonl",
    )


def _entry(trade_id: str = "trade-1", *, status: str = "closed", realized_r: float | None = 1.0, realized_pl: float | None = 100.0) -> PaperTradeJournalEntry:
    return PaperTradeJournalEntry(
        journal_id=f"journal-{trade_id}", trade_id=trade_id, source_event_id="event-1",
        symbol="BTC-USD", timeframe="5m", higher_timeframe="1h", action="buy",
        setup="liquidity_sweep_reversal_long", strategy="liquidity_sweep_reversal",
        status=status, opened_at="2026-07-01T10:00:00+00:00",
        closed_at=("2026-07-01T10:05:00+00:00" if status == "closed" else None),
        planned_entry=100.0, actual_entry=100.0, stop_loss=99.0,
        target=103.0, planned_r=3.0, risk_amount=100.0,
        position_size=100.0, exit_price=101.0 if status == "closed" else None,
        realized_r=realized_r, realized_pl=realized_pl, close_reason="manual_close" if status == "closed" else None,
        account_balance_at_open=10_000.0, account_balance_at_close=10_100.0 if status == "closed" else None,
        setup_quality=None, score_summary=None, execution_intelligence=None,
        confidence_calibration=None, symbol_profile=None, adaptive_strategy_router=None,
        strategy_rating=None, setup_rating=None, lifecycle_events=(),
        warnings=(), rule_violations=(),
        human_readable_summary="Synthetic journal entry.",
    )


class _FakeBroker:
    def __init__(self, open_trades=(), closed_trades=(), total_r=0.0, realized_pl=0.0):
        self._open = tuple(open_trades)
        self._closed = tuple(closed_trades)
        self._performance = SimpleNamespace(total_r=total_r, realized_pl=realized_pl, closed_trades=len(self._closed))

    def open_positions(self):
        return self._open

    def closed_trades(self):
        return self._closed

    def performance(self):
        return self._performance


class _FakeLifecycle:
    def __init__(self, pending=(), open_trades=(), closed_trades=(), events=()):
        self._pending = tuple(pending)
        self._open = tuple(open_trades)
        self._closed = tuple(closed_trades)
        self._events = tuple(events)
        self.monitor = SimpleNamespace(find_event=lambda event_id: None)

    def pending_orders(self):
        return self._pending

    def open_trades(self):
        return self._open

    def closed_trades(self):
        return self._closed

    def events(self):
        return self._events


class _FakeJournal:
    def __init__(self, entries):
        self._entries = tuple(entries)

    def entries(self):
        return self._entries

    def summary(self):
        closed = [item for item in self._entries if item.status == "closed" and item.realized_r is not None]
        open_count = sum(item.status == "open" for item in self._entries)
        return SimpleNamespace(
            total_journaled_trades=len(self._entries),
            open_trades=open_count,
            closed_trades=len(closed),
            total_r=round(sum(item.realized_r or 0 for item in closed), 6),
            realized_pl=round(sum(item.realized_pl or 0 for item in closed), 6),
        )


class _FakeOrchestrator:
    def __init__(self, actions=(), cycle_count=0):
        self._actions = tuple(actions)
        self._status = SimpleNamespace(cycle_count=cycle_count)

    def status(self):
        return self._status

    def recent_actions(self, limit=None):
        return self._actions


def _fake_engine(tmp_path: Path, entries=(), broker=None, lifecycle=None, reports=None, orchestrator=None):
    return PaperStateReconciliationEngine(
        broker=broker or _FakeBroker(),
        lifecycle=lifecycle or _FakeLifecycle(),
        journal=_FakeJournal(entries),
        reports=reports or _Reports(),
        orchestrator=orchestrator or _FakeOrchestrator(),
        history_path=tmp_path / "history.jsonl",
    )


def test_empty_state_passes(tmp_path) -> None:
    result = _real_engine(tmp_path).run(persist=False)

    assert result.status == "PASS"
    assert result.summary.discrepancy_count == 0
    assert result.paper_only is True


def test_journal_only_state_is_watchlist_after_restart(tmp_path) -> None:
    engine = _fake_engine(tmp_path, entries=(_entry(status="open", realized_r=None, realized_pl=None),))
    result = engine.run(persist=False)

    assert result.status == "WATCHLIST"
    assert any("persisted journal" in item.message for item in result.discrepancies)
    assert result.summary.journal_open_trades == 1


def test_duplicate_trade_id_fails(tmp_path) -> None:
    result = _fake_engine(tmp_path, entries=(_entry("dup"), _entry("dup"))).run(persist=False)

    assert result.status == "FAIL"
    assert any(item.severity == "critical" and "Duplicate trade ID" in item.message for item in result.discrepancies)


def test_open_closed_contradiction_fails(tmp_path) -> None:
    contradictory = replace(_entry(status="open", realized_r=None, realized_pl=None), closed_at="2026-07-01T10:10:00+00:00")

    result = _fake_engine(tmp_path, entries=(contradictory,)).run(persist=False)

    assert result.status == "FAIL"
    assert any("marked open" in item.message for item in result.discrepancies)


def test_impossible_r_and_pl_math_fail(tmp_path) -> None:
    impossible = _entry("bad-r", realized_r=101.0, realized_pl=1.0)

    result = _fake_engine(tmp_path, entries=(impossible,)).run(persist=False)

    assert result.status == "FAIL"
    assert any("impossible realized R" in item.message for item in result.discrepancies)
    assert any("inconsistent" in item.message for item in result.discrepancies)


def test_daily_report_mismatch_is_watchlist(tmp_path) -> None:
    latest = SimpleNamespace(summary=SimpleNamespace(total_r=0.0))
    broker = _FakeBroker(closed_trades=(_entry(),), total_r=1.0, realized_pl=100.0)
    result = _fake_engine(tmp_path, entries=(_entry(),), broker=broker, reports=_Reports(latest)).run(persist=False)

    assert result.status == "WATCHLIST"
    assert any(item.component == "daily_report_engine" for item in result.discrepancies)


def test_recent_actions_missing_after_session_is_watchlist(tmp_path) -> None:
    broker = _FakeBroker(closed_trades=(_entry(),), total_r=1.0, realized_pl=100.0)
    result = _fake_engine(
        tmp_path,
        entries=(_entry(),),
        broker=broker,
        orchestrator=_FakeOrchestrator(cycle_count=3),
    ).run(persist=False)

    assert result.status == "WATCHLIST"
    assert any(item.component == "paper_trading_orchestrator" for item in result.discrepancies)


def test_pending_order_source_event_mismatch_is_watchlist(tmp_path) -> None:
    pending = SimpleNamespace(
        order_id="order-1", source_event_id="missing-event",
        candles_evaluated=0, expires_after_candles=3,
    )

    result = _fake_engine(tmp_path, lifecycle=_FakeLifecycle(pending=(pending,))).run(persist=False)

    assert result.status == "WATCHLIST"
    assert any("missing monitor source event" in item.message for item in result.discrepancies)


def test_reconciliation_history_persists_append_only(tmp_path) -> None:
    engine = _real_engine(tmp_path)

    engine.run()
    engine.run()

    lines = (tmp_path / "reconciliation.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2


def test_reconciliation_is_read_only(tmp_path) -> None:
    engine = _real_engine(tmp_path)
    broker = engine.broker
    broker.open_position(PaperOpenRequest(
        symbol="BTC-USD", timeframe="5m", higher_timeframe="1h",
        action="buy", setup="test_setup", strategy="test_strategy",
        entry_price=100, stop_loss=99, target=103,
    ))
    before = (
        len(broker.open_positions()),
        len(broker.closed_trades()),
        len(engine.lifecycle.pending_orders()),
        len(engine.lifecycle.events()),
        len(engine.journal.entries()),
    )

    engine.run(persist=False)

    after = (
        len(broker.open_positions()),
        len(broker.closed_trades()),
        len(engine.lifecycle.pending_orders()),
        len(engine.lifecycle.events()),
        len(engine.journal.entries()),
    )
    assert after == before


def test_reconciliation_api_endpoints_and_dashboard(monkeypatch) -> None:
    summary = PaperReconciliationSummary(
        status="WATCHLIST", brokerage_open_positions=0, brokerage_closed_trades=0,
        lifecycle_pending_orders=0, lifecycle_open_trades=0, lifecycle_closed_trades=0,
        journal_open_trades=1, journal_closed_trades=0, journal_total_r=0.0,
        daily_report_total_r=None, discrepancy_count=1, warning_count=1,
        critical_count=0, human_readable_summary="Synthetic watchlist reconciliation.",
    )
    result = PaperReconciliationResult(
        run_id="run-1", checked_at="2026-07-01T00:00:00+00:00",
        status="WATCHLIST", summary=summary,
        discrepancies=(PaperStateDiscrepancy("warning", "paper_journal", "trade-1", "Synthetic mismatch.", "Review state."),),
        trades=(ReconciledTradeRecord("trade-1", "BTC-USD", "5m", "open", False, False, False, False, True, "open", "event-1", None, None, 0, ()),),
        recommended_actions=("Review state.",), paper_only=True,
        human_readable_summary=summary.human_readable_summary,
    )

    class _Engine:
        def status(self): return summary
        def summary(self): return summary
        def discrepancies(self): return result.discrepancies
        def trades(self): return result.trades
        def run(self): return result

    import core.research_dashboard as dashboard_module

    app.dependency_overrides[get_paper_state_reconciliation_engine] = lambda: _Engine()
    monkeypatch.setattr(dashboard_module, "latest_paper_reconciliation", lambda: result)
    try:
        with TestClient(app) as client:
            paths = client.get("/openapi.json").json()["paths"]
            for path in (
                "/paper-reconciliation/status",
                "/paper-reconciliation/summary",
                "/paper-reconciliation/discrepancies",
                "/paper-reconciliation/trades",
                "/paper-reconciliation/run",
            ):
                assert path in paths
                assert "paper-reconciliation" in next(iter(paths[path].values()))["tags"]
            assert client.get("/paper-reconciliation/status").json()["status"] == "WATCHLIST"
            assert client.get("/paper-reconciliation/discrepancies").json()[0]["severity"] == "warning"
            assert client.get("/paper-reconciliation/trades").json()[0]["trade_id"] == "trade-1"
            assert client.post("/paper-reconciliation/run").json()["status"] == "WATCHLIST"
            overview = client.get("/dashboard/overview").json()
            assert overview["reconciliation_status"] == "WATCHLIST"
            assert overview["reconciliation_discrepancy_count"] == 1
            assert overview["reconciliation_recommended_actions"] == ["Review state."]
    finally:
        app.dependency_overrides.clear()
