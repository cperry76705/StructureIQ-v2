from pathlib import Path

from core.journal import JournalEntry, JournalStore, TradeOutcome


def _entry(
    entry_id: str,
    *,
    symbol: str = "BTC-USD",
    timeframe: str = "5m",
    outcome: TradeOutcome = TradeOutcome.UNKNOWN,
    realized_r: float | None = None,
) -> JournalEntry:
    return JournalEntry(
        id=entry_id,
        timestamp="2026-06-27T12:00:00+00:00",
        symbol=symbol,
        timeframe=timeframe,
        higher_timeframe="1h",
        action="wait",
        confidence=65.0,
        decision_action="wait",
        setup_type="bullish_pullback_continuation",
        setup_status="developing",
        strategy_type="pullback_continuation",
        entry_zone="100-101",
        stop_loss="98",
        target="105",
        estimated_risk_reward=2.0,
        outcome=outcome,
        realized_r_multiple=realized_r,
        notes=("Synthetic journal entry.",),
        raw_analysis_snapshot={"symbol": symbol},
    )


def test_append_journal_entry(tmp_path: Path) -> None:
    store = JournalStore(tmp_path / "journal" / "trades.jsonl")

    saved = store.append_entry(_entry("one"))

    assert saved.id == "one"
    assert store.path.exists()


def test_list_journal_entries(tmp_path: Path) -> None:
    store = JournalStore(tmp_path / "trades.jsonl")
    store.append_entry(_entry("one"))
    store.append_entry(_entry("two"))

    assert [entry.id for entry in store.list_entries()] == ["one", "two"]


def test_summarize_journal_entries(tmp_path: Path) -> None:
    store = JournalStore(tmp_path / "trades.jsonl")
    store.append_entry(_entry("win", outcome=TradeOutcome.WIN, realized_r=2.0))
    store.append_entry(_entry("loss", outcome=TradeOutcome.LOSS, realized_r=-1.0))
    store.append_entry(
        _entry("breakeven", outcome=TradeOutcome.BREAKEVEN, realized_r=0.0)
    )
    store.append_entry(_entry("skip", outcome=TradeOutcome.SKIPPED))

    summary = store.summarize_entries()

    assert summary.total_entries == 4
    assert summary.wins == 1
    assert summary.losses == 1
    assert summary.breakeven == 1
    assert summary.skipped == 1
    assert summary.win_rate == 33.33
    assert summary.total_r == 1.0


def test_filter_journal_by_symbol(tmp_path: Path) -> None:
    store = JournalStore(tmp_path / "trades.jsonl")
    store.append_entry(_entry("btc"))
    store.append_entry(_entry("eur", symbol="EURUSD"))

    assert [entry.id for entry in store.list_entries(symbol="eurusd")] == ["eur"]


def test_filter_journal_by_timeframe(tmp_path: Path) -> None:
    store = JournalStore(tmp_path / "trades.jsonl")
    store.append_entry(_entry("fast", timeframe="5m"))
    store.append_entry(_entry("slow", timeframe="1h"))

    assert [entry.id for entry in store.list_entries(timeframe="1h")] == ["slow"]


def test_filter_journal_by_outcome(tmp_path: Path) -> None:
    store = JournalStore(tmp_path / "trades.jsonl")
    store.append_entry(_entry("win", outcome=TradeOutcome.WIN, realized_r=2.0))
    store.append_entry(_entry("loss", outcome=TradeOutcome.LOSS, realized_r=-1.0))

    assert [entry.id for entry in store.list_entries(outcome="win")] == ["win"]


def test_missing_journal_file_does_not_crash(tmp_path: Path) -> None:
    store = JournalStore(tmp_path / "missing" / "trades.jsonl")

    assert store.list_entries() == []
    assert store.summarize_entries().total_entries == 0


def test_journal_directory_is_created(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "journal" / "trades.jsonl"

    JournalStore(path)

    assert path.parent.is_dir()
