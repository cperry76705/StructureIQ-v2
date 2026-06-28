from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app, get_journal_store, get_market_data_provider
from core.journal import JournalEntry, JournalStore
from core.market_data import Candle


class _HistoricalProvider:
    def get_candles(self, symbol: str, timeframe: str, lookback: int) -> list[Candle]:
        del symbol, timeframe
        candles = [
            Candle(index, 100.0, 101.0, 99.0, 100.0, 100.0)
            for index in range(60)
        ]
        return candles[-lookback:]


def _journal_payload() -> dict:
    return {
        "id": "api-entry",
        "timestamp": "2026-06-27T12:00:00+00:00",
        "symbol": "BTC-USD",
        "timeframe": "5m",
        "higher_timeframe": "1h",
        "action": "wait",
        "confidence": 65,
        "decision_action": "wait",
        "setup_type": "bullish_pullback_continuation",
        "setup_status": "developing",
        "strategy_type": "pullback_continuation",
        "entry_zone": "100-101",
        "stop_loss": "98",
        "target": "105",
        "estimated_risk_reward": 2,
        "outcome": "unknown",
        "realized_r_multiple": None,
        "notes": ["API test"],
        "raw_analysis_snapshot": {},
    }


def test_post_journal_works(tmp_path: Path) -> None:
    store = JournalStore(tmp_path / "journal.jsonl")
    app.dependency_overrides[get_journal_store] = lambda: store
    try:
        response = TestClient(app).post("/journal", json=_journal_payload())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["id"] == "api-entry"
    assert store.path.exists()


def test_get_journal_works(tmp_path: Path) -> None:
    store = JournalStore(tmp_path / "journal.jsonl")
    store.append_entry(JournalEntry.from_payload(_journal_payload()))
    app.dependency_overrides[get_journal_store] = lambda: store
    try:
        response = TestClient(app).get("/journal", params={"symbol": "BTC-USD"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert [entry["id"] for entry in response.json()] == ["api-entry"]


def test_get_journal_summary_works(tmp_path: Path) -> None:
    store = JournalStore(tmp_path / "journal.jsonl")
    payload = _journal_payload() | {
        "id": "winner",
        "outcome": "win",
        "realized_r_multiple": 2.0,
    }
    store.append_entry(JournalEntry.from_payload(payload))
    app.dependency_overrides[get_journal_store] = lambda: store
    try:
        response = TestClient(app).get("/journal/summary")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["wins"] == 1
    assert response.json()["total_r"] == 2.0


def test_post_backtest_works() -> None:
    app.dependency_overrides[get_market_data_provider] = lambda: _HistoricalProvider()
    try:
        response = TestClient(app).post(
            "/backtest",
            json={
                "symbol": "BTC-USD",
                "timeframe": "5m",
                "higher_timeframe": "1h",
                "lookback": 60,
                "starting_balance": 10000,
                "risk_per_trade_percent": 1,
                "max_trades": 1,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert len(response.json()["trades"]) == 1
    assert response.json()["limitations"]
    assert response.json()["skip_diagnostics"]["total_skipped"] == 1
    assert response.json()["trades"][0]["skip_reason_code"]
    assert response.json()["trades"][0]["blocking_engine"]
