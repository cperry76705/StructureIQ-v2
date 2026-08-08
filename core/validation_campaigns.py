"""Durable validation-campaign registry for paper trading research runs."""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi.encoders import jsonable_encoder

from app.config import APP_VERSION


@dataclass(frozen=True)
class ValidationCampaign:
    campaign_id: str
    name: str
    status: str
    started_at: str
    ended_at: str | None
    duration_seconds: float | None
    cli: str | None
    runtime: str
    strategy_version: str
    engine_version: str
    commit_hash: str | None
    paper_settings: dict[str, Any]
    legacy_import: bool
    trades: int
    wins: int
    losses: int
    total_r: float
    metadata_path: str
    human_readable_summary: str


@dataclass(frozen=True)
class CampaignSummary:
    campaign_id: str
    status: str
    started_at: str
    ended_at: str | None
    duration_seconds: float | None
    trades: int
    win_rate: float
    loss_rate: float
    total_r: float
    drawdown: float
    legacy_import: bool
    human_readable_summary: str
    open_trades: int = 0
    closed_trades: int = 0
    wins: int = 0
    losses: int = 0
    breakeven: int = 0
    realized_r: float = 0.0
    unrealized_r: float = 0.0


@dataclass(frozen=True)
class LegacyCampaignAuditRow:
    trade_id: str
    campaign_id: str | None
    journal_status: str
    included_in_legacy_campaign: bool
    excluded_from_legacy_campaign: bool
    exclusion_reason: str | None
    realized_r: float | None
    opened_at: str | None
    closed_at: str | None


@dataclass(frozen=True)
class LegacyCampaignAudit:
    journal_record_count: int
    legacy_campaign_trade_count: int
    journal_closed_count: int
    journal_open_count: int
    journal_total_r: float
    legacy_campaign_total_r: float
    count_difference: int
    r_difference: float
    unassigned_trade_count: int
    post_import_trade_count: int
    mismatched_trade_ids: tuple[str, ...]
    rows: tuple[LegacyCampaignAuditRow, ...]
    human_readable_summary: str


@dataclass(frozen=True)
class CampaignSummaryRefreshResult:
    campaign_id: str
    refreshed_at: str
    before: CampaignSummary
    after: CampaignSummary
    human_readable_summary: str


class ValidationCampaignManager:
    """Create and read isolated campaign folders without changing trading logic."""

    def __init__(self, root: str | Path = "validation_campaigns", journal: Any | None = None) -> None:
        self.root = Path(root)
        self.journal = journal
        self.root.mkdir(parents=True, exist_ok=True)
        self._current_id_path = self.root / "current_campaign.txt"
        self._migrate_legacy_if_needed()

    def current(self) -> ValidationCampaign | None:
        if not self._current_id_path.exists():
            return None
        return self.get(self._current_id_path.read_text(encoding="utf-8").strip())

    def list_campaigns(self) -> tuple[ValidationCampaign, ...]:
        campaigns = []
        for path in sorted(self.root.glob("*/metadata.json")):
            campaign = self._load_campaign(path.parent)
            if campaign is not None:
                campaigns.append(campaign)
        return tuple(campaigns)

    def get(self, campaign_id: str) -> ValidationCampaign | None:
        return self._load_campaign(self.root / campaign_id)

    def start(self, name: str | None = None, *, cli: str | None = None, paper_settings: dict[str, Any] | None = None) -> ValidationCampaign:
        now = _now()
        campaign_id = _campaign_id(name or "Validation Campaign", now)
        path = self.root / campaign_id
        path.mkdir(parents=True, exist_ok=False)
        campaign = ValidationCampaign(
            campaign_id=campaign_id,
            name=name or campaign_id,
            status="running",
            started_at=now,
            ended_at=None,
            duration_seconds=None,
            cli=cli,
            runtime="paper",
            strategy_version=APP_VERSION,
            engine_version=APP_VERSION,
            commit_hash=_commit_hash(),
            paper_settings=paper_settings or {},
            legacy_import=False,
            trades=0,
            wins=0,
            losses=0,
            total_r=0.0,
            metadata_path=str(path / "metadata.json"),
            human_readable_summary=f"Campaign {name or campaign_id} is running.",
        )
        self._write_campaign(campaign)
        self._write_default_files(path)
        self._current_id_path.write_text(campaign_id, encoding="utf-8")
        return campaign

    def recovery_test_campaign(self) -> ValidationCampaign:
        """Return or create the dedicated synthetic recovery infrastructure campaign."""

        current = self.current()
        if current and current.paper_settings.get("infrastructure_test") and current.paper_settings.get("synthetic"):
            return current
        for campaign in self.list_campaigns():
            if campaign.status == "running" and campaign.paper_settings.get("infrastructure_test") and campaign.paper_settings.get("synthetic"):
                self._current_id_path.write_text(campaign.campaign_id, encoding="utf-8")
                return campaign
        now = _now()
        suffix = hashlib.sha256(f"recovery-test:{now}".encode()).hexdigest()[:8]
        campaign_id = f"recovery_test_{now[:10].replace('-', '_')}_{suffix}"
        path = self.root / campaign_id
        path.mkdir(parents=True, exist_ok=False)
        campaign = ValidationCampaign(
            campaign_id=campaign_id,
            name="Recovery Infrastructure Test",
            status="running",
            started_at=now,
            ended_at=None,
            duration_seconds=None,
            cli=None,
            runtime="paper",
            strategy_version=APP_VERSION,
            engine_version=APP_VERSION,
            commit_hash=_commit_hash(),
            paper_settings={
                "infrastructure_test": True,
                "synthetic": True,
                "exclude_from_performance": True,
            },
            legacy_import=False,
            trades=0,
            wins=0,
            losses=0,
            total_r=0.0,
            metadata_path=str(path / "metadata.json"),
            human_readable_summary="Synthetic recovery infrastructure test campaign is running.",
        )
        self._write_campaign(campaign)
        self._write_default_files(path)
        self._current_id_path.write_text(campaign_id, encoding="utf-8")
        return campaign

    def finish(self, campaign_id: str, *, status: str = "completed", results: dict[str, Any] | None = None) -> ValidationCampaign | None:
        campaign = self.get(campaign_id)
        if campaign is None:
            return None
        now = _now()
        started = datetime.fromisoformat(campaign.started_at)
        duration = max(0.0, (datetime.fromisoformat(now) - started).total_seconds())
        summary = self.summary(campaign_id)
        updated = ValidationCampaign(
            **{
                **campaign.__dict__,
                "status": status,
                "ended_at": now,
                "duration_seconds": round(duration, 3),
                "trades": summary.trades,
                "wins": int(round(summary.trades * summary.win_rate / 100)),
                "losses": int(round(summary.trades * summary.loss_rate / 100)),
                "total_r": summary.total_r,
                "human_readable_summary": f"Campaign {campaign.name} {status} after {duration:.0f} seconds.",
            }
        )
        self._write_campaign(updated)
        if results is not None:
            self._write_json(self.root / campaign_id / "results.json", results)
        return updated

    def summary(self, campaign_id: str) -> CampaignSummary:
        campaign = self.get(campaign_id)
        if campaign is None:
            raise KeyError("campaign was not found")
        filtered = [
            item for item in self._campaign_entries(campaign)
            if not getattr(item, "exclude_from_campaign_metrics", False)
        ]
        closed = [item for item in filtered if item.status == "closed" and item.realized_r is not None]
        open_trades = [item for item in filtered if item.status == "open"]
        returns = [float(item.realized_r) for item in closed]
        wins = sum(value > 0 for value in returns)
        losses = sum(value < 0 for value in returns)
        breakeven = len(returns) - wins - losses
        drawdown = _max_drawdown(returns)
        return CampaignSummary(
            campaign_id=campaign_id,
            status=campaign.status,
            started_at=campaign.started_at,
            ended_at=campaign.ended_at,
            duration_seconds=campaign.duration_seconds,
            trades=len(closed),
            win_rate=round(wins / len(closed) * 100, 6) if closed else 0.0,
            loss_rate=round(losses / len(closed) * 100, 6) if closed else 0.0,
            total_r=round(sum(returns), 6),
            drawdown=drawdown,
            legacy_import=campaign.legacy_import,
            human_readable_summary=f"Campaign {campaign.name} has {len(closed)} closed journal trades and {sum(returns):+.2f}R.",
            open_trades=len(open_trades),
            closed_trades=len(closed),
            wins=wins,
            losses=losses,
            breakeven=breakeven,
            realized_r=round(sum(returns), 6),
            unrealized_r=0.0,
        )

    def journal_rows(self, campaign_id: str) -> tuple[dict[str, Any], ...]:
        campaign = self.get(campaign_id)
        if campaign is None or self.journal is None:
            return ()
        selected = tuple(
            item for item in self._campaign_entries(campaign)
            if not getattr(item, "exclude_from_campaign_metrics", False)
        )
        return tuple(jsonable_encoder(item) for item in selected)

    def legacy_audit(self) -> LegacyCampaignAudit:
        campaign = self.get("legacy_campaign")
        if campaign is None:
            raise KeyError("legacy campaign was not found")
        current = tuple(self.journal.entries()) if self.journal is not None else ()
        imported = tuple(self._campaign_entries(campaign))
        imported_ids = {getattr(item, "trade_id", None) for item in imported}
        rows: list[LegacyCampaignAuditRow] = []
        mismatches: list[str] = []
        for entry in current:
            included = getattr(entry, "trade_id", None) in imported_ids
            reason = None
            if not included:
                if getattr(entry, "campaign_id", None) not in {None, "legacy_campaign"}:
                    reason = "record belongs to a post-import validation campaign"
                elif getattr(entry, "status", None) not in {"open", "closed"}:
                    reason = "record is a lifecycle-only non-trade journal row"
                else:
                    reason = "record was created after the legacy import snapshot"
                mismatches.append(str(getattr(entry, "trade_id", "")))
            rows.append(LegacyCampaignAuditRow(
                trade_id=str(getattr(entry, "trade_id", "")),
                campaign_id=getattr(entry, "campaign_id", None),
                journal_status=str(getattr(entry, "status", "")),
                included_in_legacy_campaign=included,
                excluded_from_legacy_campaign=not included,
                exclusion_reason=reason,
                realized_r=getattr(entry, "realized_r", None),
                opened_at=getattr(entry, "opened_at", None),
                closed_at=getattr(entry, "closed_at", None),
            ))
        current_closed = [item for item in current if getattr(item, "status", None) == "closed" and getattr(item, "realized_r", None) is not None]
        imported_closed = [item for item in imported if getattr(item, "status", None) == "closed" and getattr(item, "realized_r", None) is not None]
        journal_total = round(sum(float(item.realized_r or 0) for item in current_closed), 6)
        legacy_total = round(sum(float(item.realized_r or 0) for item in imported_closed), 6)
        return LegacyCampaignAudit(
            journal_record_count=len(current),
            legacy_campaign_trade_count=len(imported_closed),
            journal_closed_count=len(current_closed),
            journal_open_count=sum(getattr(item, "status", None) == "open" for item in current),
            journal_total_r=journal_total,
            legacy_campaign_total_r=legacy_total,
            count_difference=len(current) - len(imported_closed),
            r_difference=round(journal_total - legacy_total, 6),
            unassigned_trade_count=sum(getattr(item, "campaign_id", None) is None for item in current),
            post_import_trade_count=sum(getattr(item, "campaign_id", None) not in {None, "legacy_campaign"} for item in current),
            mismatched_trade_ids=tuple(mismatches),
            rows=tuple(rows),
            human_readable_summary=(
                f"Legacy campaign snapshot contains {len(imported_closed)} closed trades for {legacy_total:+.2f}R; "
                f"the current journal contains {len(current)} records and {journal_total:+.2f}R. "
                "Differences are listed per trade without mutating journal history."
            ),
        )

    def refresh_summary(self, campaign_id: str) -> CampaignSummaryRefreshResult:
        before = self.summary(campaign_id)
        campaign = self.get(campaign_id)
        if campaign is None:
            raise KeyError("campaign was not found")
        refreshed = self.summary(campaign_id)
        self._write_json(self.root / campaign_id / "summary.json", refreshed)
        self._write_json(self.root / campaign_id / "metrics.json", {"refreshed_at": _now(), **jsonable_encoder(refreshed)})
        return CampaignSummaryRefreshResult(
            campaign_id=campaign_id,
            refreshed_at=_now(),
            before=before,
            after=refreshed,
            human_readable_summary=f"Campaign {campaign_id} summary was refreshed from campaign-scoped journal data.",
        )

    def writable(self) -> bool:
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            probe = self.root / ".campaign-probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            return True
        except OSError:
            return False

    def _migrate_legacy_if_needed(self) -> None:
        if any(self.root.glob("*/metadata.json")):
            return
        entries = self.journal.entries() if self.journal is not None else ()
        if not entries:
            return
        now = _now()
        campaign_id = "legacy_campaign"
        path = self.root / campaign_id
        path.mkdir(parents=True, exist_ok=True)
        closed = [item for item in entries if item.status == "closed" and item.realized_r is not None]
        returns = [float(item.realized_r) for item in closed]
        campaign = ValidationCampaign(
            campaign_id=campaign_id,
            name="Legacy Campaign",
            status="completed",
            started_at=now,
            ended_at=now,
            duration_seconds=0.0,
            cli=None,
            runtime="paper",
            strategy_version=APP_VERSION,
            engine_version=APP_VERSION,
            commit_hash=_commit_hash(),
            paper_settings={},
            legacy_import=True,
            trades=len(closed),
            wins=sum(value > 0 for value in returns),
            losses=sum(value < 0 for value in returns),
            total_r=round(sum(returns), 6),
            metadata_path=str(path / "metadata.json"),
            human_readable_summary="Legacy journal history was imported without changing trades.",
        )
        self._write_campaign(campaign)
        self._write_default_files(path)
        with (path / "journal.jsonl").open("a", encoding="utf-8") as handle:
            for entry in entries:
                handle.write(json.dumps(jsonable_encoder(entry), separators=(",", ":")) + "\n")

    def _load_campaign(self, path: Path) -> ValidationCampaign | None:
        try:
            raw = json.loads((path / "metadata.json").read_text(encoding="utf-8"))
            return ValidationCampaign(**raw)
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            return None

    def _write_campaign(self, campaign: ValidationCampaign) -> None:
        path = self.root / campaign.campaign_id
        path.mkdir(parents=True, exist_ok=True)
        self._write_json(path / "metadata.json", campaign)
        self._write_json(path / "summary.json", self.summary(campaign.campaign_id).__dict__ if (path / "metadata.json").exists() and self.get(campaign.campaign_id) else {
            "campaign_id": campaign.campaign_id,
            "status": campaign.status,
            "trades": campaign.trades,
            "total_r": campaign.total_r,
        })

    def _write_default_files(self, path: Path) -> None:
        for name, default in (
            ("daily_report.json", {}),
            ("metrics.json", {}),
            ("validation.json", {}),
            ("reconciliation.json", {}),
        ):
            target = path / name
            if not target.exists():
                self._write_json(target, default)
        journal = path / "journal.jsonl"
        if not journal.exists():
            journal.write_text("", encoding="utf-8")

    def _write_json(self, path: Path, value: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(jsonable_encoder(value), indent=2), encoding="utf-8")

    def _campaign_entries(self, campaign: ValidationCampaign) -> tuple[Any, ...]:
        if campaign.legacy_import:
            imported = self._journal_snapshot(campaign.campaign_id)
            if imported:
                return imported
        entries = self.journal.entries() if self.journal is not None else ()
        if campaign.legacy_import:
            return tuple(item for item in entries if getattr(item, "campaign_id", None) in {None, "legacy_campaign"})
        return tuple(item for item in entries if getattr(item, "campaign_id", None) == campaign.campaign_id)

    def _journal_snapshot(self, campaign_id: str) -> tuple[Any, ...]:
        path = self.root / campaign_id / "journal.jsonl"
        if not path.exists():
            return ()
        rows = []
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                raw = json.loads(line)
                if isinstance(raw, dict) and "entry" in raw:
                    raw = raw["entry"]
                rows.append(_SnapshotEntry(raw))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return ()
        return tuple(rows)


class _SnapshotEntry:
    def __init__(self, raw: dict[str, Any]) -> None:
        self.__dict__.update(raw)


def _campaign_id(name: str, now: str) -> str:
    safe = "".join(ch.lower() if ch.isalnum() else "_" for ch in name).strip("_") or "campaign"
    day = now[:10].replace("-", "_")
    suffix = hashlib.sha256(f"{name}:{now}".encode()).hexdigest()[:8]
    return f"campaign_{day}_{safe[:36]}_{suffix}"


def _commit_hash() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return None


def _max_drawdown(values: list[float]) -> float:
    equity = peak = worst = 0.0
    for value in values:
        equity += value
        peak = max(peak, equity)
        worst = max(worst, peak - equity)
    return round(worst, 6)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


_GLOBAL_CAMPAIGN_MANAGER: ValidationCampaignManager | None = None


def get_global_validation_campaign_manager(journal: Any | None = None) -> ValidationCampaignManager:
    global _GLOBAL_CAMPAIGN_MANAGER
    if _GLOBAL_CAMPAIGN_MANAGER is None or (journal is not None and _GLOBAL_CAMPAIGN_MANAGER.journal is not journal):
        _GLOBAL_CAMPAIGN_MANAGER = ValidationCampaignManager(journal=journal)
    return _GLOBAL_CAMPAIGN_MANAGER
