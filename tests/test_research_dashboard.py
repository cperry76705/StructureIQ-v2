"""Tests for compact read-only research dashboard endpoints."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import (
    app,
    get_market_data_provider,
    get_research_engine,
    get_symbol_profile_engine,
)
from core.market_data import Candle
from core.research_dashboard import clear_dashboard_state
from core.research_engine import ResearchEngine
from core.symbol_profile_engine import SymbolProfileEngine


class _DashboardProvider:
    provider_name = "dashboard-test"

    def get_candles(self, symbol: str, timeframe: str, lookback: int) -> list[Candle]:
        del symbol, timeframe
        candles: list[Candle] = []
        price = 100.0
        for index in range(max(lookback, 120)):
            wave = (index % 12) - 6
            close = price + 0.4 + wave * 0.08
            candles.append(
                Candle(
                    timestamp=index,
                    open=price,
                    high=max(price, close) + 1.2,
                    low=min(price, close) - 1.2,
                    close=close,
                    volume=1_000 + index,
                )
            )
            price = close
        return candles


def _client(tmp_path: Path):
    clear_dashboard_state()
    research = ResearchEngine()
    profiles = SymbolProfileEngine(path=tmp_path / "symbol_profiles.json")
    app.dependency_overrides[get_market_data_provider] = lambda: _DashboardProvider()
    app.dependency_overrides[get_symbol_profile_engine] = lambda: profiles
    app.dependency_overrides[get_research_engine] = lambda: research
    return TestClient(app), profiles, research


def _cleanup() -> None:
    app.dependency_overrides.clear()
    clear_dashboard_state()


def _calibration_payload(**extra):
    payload = {
        "symbols": ["BTC-USD"],
        "timeframes": ["5m"],
        "higher_timeframes": ["1h"],
        "lookback": 120,
        "max_trades_per_run": 20,
        "risk_per_trade_percent": 1,
        "starting_balance": 10000,
    }
    payload.update(extra)
    return payload


def test_dashboard_endpoints_exist_in_openapi(tmp_path: Path) -> None:
    client, _, _ = _client(tmp_path)
    try:
        paths = client.get("/openapi.json").json()["paths"]
    finally:
        _cleanup()

    for path in (
        "/dashboard/overview",
        "/dashboard/symbols",
        "/dashboard/strategies",
        "/dashboard/setups",
        "/dashboard/readiness",
        "/dashboard/risks",
        "/dashboard/recommendations",
    ):
        assert path in paths
        assert "get" in paths[path]
        assert "dashboard" in paths[path]["get"]["tags"]


def test_dashboard_overview_returns_unavailable_without_prior_calibration(
    tmp_path: Path,
) -> None:
    client, _, _ = _client(tmp_path)
    try:
        response = client.get("/dashboard/overview")
    finally:
        _cleanup()

    assert response.status_code == 200
    payload = response.json()
    assert payload["app_version"] == "6.0.0"
    assert payload["paper_trading_readiness"] == "UNAVAILABLE"
    assert payload["aggregate_win_rate"] is None
    assert "unavailable" in payload["human_readable_summary"].lower()


def test_calibrate_stores_latest_dashboard_snapshot(tmp_path: Path) -> None:
    client, _, _ = _client(tmp_path)
    try:
        calibration = client.post("/calibrate", json=_calibration_payload())
        overview = client.get("/dashboard/overview")
    finally:
        _cleanup()

    assert calibration.status_code == 200
    assert overview.status_code == 200
    calibration_payload = calibration.json()
    overview_payload = overview.json()
    assert overview_payload["aggregate_win_rate"] == calibration_payload["aggregate_metrics"]["win_rate"]
    assert overview_payload["aggregate_total_r"] == calibration_payload["aggregate_metrics"]["total_r"]
    assert overview_payload["paper_trading_readiness"] == "UNAVAILABLE"


def test_dashboard_symbols_reads_persisted_symbol_profiles(tmp_path: Path) -> None:
    path = tmp_path / "symbol_profiles.json"
    observations = [
        {
            "timestamp": index,
            "symbol": "EUR-USD",
            "outcome": "win" if index % 3 else "loss",
            "realized_r": 1.5 if index % 3 else -1.0,
            "confidence": 76,
            "strategy": "liquidity_sweep_reversal",
            "setup": "liquidity_sweep_reversal_short",
            "regime": "strong_bear_trend",
        }
        for index in range(35)
    ]
    path.write_text(json.dumps({"observations": observations}), encoding="utf-8")
    client, _, _ = _client(tmp_path)
    try:
        response = client.get("/dashboard/symbols")
    finally:
        _cleanup()

    assert response.status_code == 200
    symbols = response.json()["symbols"]
    assert symbols
    assert symbols[0]["symbol"] == "EUR-USD"
    assert symbols[0]["sample_size"] == 35
    assert symbols[0]["status"] == "available"


def test_dashboard_strategies_and_setups_use_latest_rating_summaries(
    tmp_path: Path,
) -> None:
    client, _, _ = _client(tmp_path)
    try:
        calibration = client.post("/calibrate", json=_calibration_payload())
        strategies = client.get("/dashboard/strategies")
        setups = client.get("/dashboard/setups")
    finally:
        _cleanup()

    assert calibration.status_code == 200
    assert strategies.status_code == 200
    assert setups.status_code == 200
    assert "strategies" in strategies.json()
    assert "setups" in setups.json()
    assert isinstance(strategies.json()["strategies"], list)
    assert isinstance(setups.json()["setups"], list)


def test_dashboard_readiness_never_ready_below_100_validation_trades(
    tmp_path: Path,
) -> None:
    client, _, _ = _client(tmp_path)
    try:
        calibration = client.post(
            "/calibrate",
            json=_calibration_payload(
                out_of_sample_validation=True,
                validation_method="walk_forward",
                validation_folds=3,
                training_percent=70,
                validation_percent=30,
            ),
        )
        readiness = client.get("/dashboard/readiness")
    finally:
        _cleanup()

    assert calibration.status_code == 200
    assert readiness.status_code == 200
    assert readiness.json()["paper_trading_status"] != "READY_FOR_PAPER_TRADING"
    assert "100" in " ".join(readiness.json()["minimum_data_requirements"])


def test_dashboard_risks_surfaces_low_sample_and_provider_warnings(
    tmp_path: Path,
) -> None:
    client, _, _ = _client(tmp_path)
    try:
        client.post("/calibrate", json=_calibration_payload())
        risks = client.get("/dashboard/risks")
    finally:
        _cleanup()

    assert risks.status_code == 200
    payload = risks.json()
    assert "risk_grade" in payload
    assert "low_sample_warnings" in payload
    assert isinstance(payload["top_risks"], list)


def test_dashboard_recommendations_returns_prioritized_action_items(
    tmp_path: Path,
) -> None:
    client, _, _ = _client(tmp_path)
    try:
        client.post(
            "/calibrate",
            json=_calibration_payload(statistical_validation_analysis=True),
        )
        response = client.get("/dashboard/recommendations")
    finally:
        _cleanup()

    assert response.status_code == 200
    payload = response.json()
    assert "recommendations" in payload
    for item in payload["recommendations"]:
        assert item["production_safe"] is True
        assert item["priority"] >= 1


def test_dashboard_endpoints_do_not_mutate_calibration_metrics(tmp_path: Path) -> None:
    client, _, _ = _client(tmp_path)
    try:
        calibration = client.post("/calibrate", json=_calibration_payload()).json()
        before = calibration["aggregate_metrics"]
        client.get("/dashboard/overview")
        client.get("/dashboard/risks")
        after = client.get("/dashboard/overview").json()
    finally:
        _cleanup()

    assert after["aggregate_win_rate"] == before["win_rate"]
    assert after["aggregate_total_r"] == before["total_r"]


def test_restart_no_snapshot_returns_controlled_unavailable_with_profiles(
    tmp_path: Path,
) -> None:
    path = tmp_path / "symbol_profiles.json"
    path.write_text(
        json.dumps(
            {
                "observations": [
                    {
                        "timestamp": index,
                        "symbol": "GBP-USD",
                        "outcome": "win",
                        "realized_r": 1.2,
                        "confidence": 72,
                        "strategy": "trend_continuation",
                        "setup": "bearish_bos_retest",
                        "regime": "weak_bear_trend",
                    }
                    for index in range(21)
                ]
            }
        ),
        encoding="utf-8",
    )
    client, _, _ = _client(tmp_path)
    clear_dashboard_state()
    try:
        overview = client.get("/dashboard/overview").json()
        symbols = client.get("/dashboard/symbols").json()
    finally:
        _cleanup()

    assert overview["aggregate_win_rate"] is None
    assert overview["total_symbols_profiled"] == 1
    assert symbols["symbols"][0]["symbol"] == "GBP-USD"
