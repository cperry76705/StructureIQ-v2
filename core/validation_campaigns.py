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
        entries = self.journal.entries() if self.journal is not None else ()
        filtered = [
            item for item in entries
            if getattr(item, "campaign_id", None) in {campaign_id, None if campaign.legacy_import else campaign_id}
            and (campaign.legacy_import or getattr(item, "campaign_id", None) == campaign_id)
        ]
        if campaign.legacy_import:
            filtered = list(entries)
        closed = [item for item in filtered if item.status == "closed" and item.realized_r is not None]
        returns = [float(item.realized_r) for item in closed]
        wins = sum(value > 0 for value in returns)
        losses = sum(value < 0 for value in returns)
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
        )

    def journal_rows(self, campaign_id: str) -> tuple[dict[str, Any], ...]:
        campaign = self.get(campaign_id)
        if campaign is None or self.journal is None:
            return ()
        entries = self.journal.entries()
        if campaign.legacy_import:
            selected = entries
        else:
            selected = tuple(item for item in entries if getattr(item, "campaign_id", None) == campaign_id)
        return tuple(jsonable_encoder(item) for item in selected)

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
