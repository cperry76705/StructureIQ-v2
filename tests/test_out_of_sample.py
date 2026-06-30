from fastapi.testclient import TestClient

from app.main import app, get_market_data_provider
from core.market_data import Candle
from core.out_of_sample import (
    ValidationMeasurements,
    ValidationMethod,
    build_generalization_summary,
    build_overfitting_summary,
    build_validation_splits,
)


def test_chronological_split_preserves_order() -> None:
    splits = build_validation_splits(
        100,
        method=ValidationMethod.CHRONOLOGICAL,
        training_percent=70,
        validation_percent=30,
        folds=5,
    )

    assert len(splits) == 1
    assert splits[0].training_start == 0
    assert splits[0].training_end == 70
    assert splits[0].validation_start == 70
    assert splits[0].validation_end == 100


def test_walk_forward_expands_training_across_consistent_folds() -> None:
    splits = build_validation_splits(
        100,
        method=ValidationMethod.WALK_FORWARD,
        training_percent=70,
        validation_percent=30,
        folds=5,
    )

    assert len(splits) == 5
    assert [item.training_end for item in splits] == [70, 76, 82, 88, 94]
    assert [item.validation_start for item in splits] == [70, 76, 82, 88, 94]
    assert all(item.training_start == 0 for item in splits)
    assert all(item.training_end <= item.validation_start for item in splits)


def test_rolling_expanding_and_anchored_splits_are_deterministic() -> None:
    rolling = build_validation_splits(
        100,
        method=ValidationMethod.ROLLING_WINDOW,
        training_percent=70,
        validation_percent=30,
        folds=5,
    )
    expanding = build_validation_splits(
        100,
        method=ValidationMethod.EXPANDING_WINDOW,
        training_percent=70,
        validation_percent=30,
        folds=5,
    )
    anchored = build_validation_splits(
        100,
        method=ValidationMethod.ANCHORED,
        training_percent=70,
        validation_percent=30,
        folds=5,
    )

    assert rolling == build_validation_splits(
        100,
        method=ValidationMethod.ROLLING_WINDOW,
        training_percent=70,
        validation_percent=30,
        folds=5,
    )
    assert [item.training_start for item in rolling] == [0, 6, 12, 18, 24]
    assert all(item.training_start == 0 for item in expanding)
    assert all(item.training_end == 70 for item in anchored)
    assert [item.validation_start for item in anchored] == [70, 76, 82, 88, 94]


def _measurements(
    *,
    average_r: float,
    win_rate: float,
    drawdown: float,
    confidence: float,
    setup: str,
    strategy: str,
    regime: str,
) -> ValidationMeasurements:
    return ValidationMeasurements(
        records=100,
        trades=20,
        win_rate=win_rate,
        average_r=average_r,
        total_r=average_r * 20,
        profit_factor=2.0 if average_r > 0 else 0.5,
        maximum_drawdown=drawdown,
        expectancy=average_r,
        average_mfe=1.5,
        average_mae=0.8,
        average_trade_duration=5.0,
        skipped_records=80,
        confidence_distribution={"80-89": 100},
        average_confidence=confidence,
        setup_distribution={setup: 100},
        strategy_distribution={strategy: 100},
        regime_distribution={regime: 100},
        execution_degradation=0.1,
        trade_management_sensitivity={"none": average_r * 20},
    )


def test_generalization_metrics_and_overfitting_detection() -> None:
    training = _measurements(
        average_r=1.0,
        win_rate=60.0,
        drawdown=1.0,
        confidence=85.0,
        setup="bearish_bos_retest",
        strategy="trend_continuation",
        regime="strong_bear_trend",
    )
    validation = _measurements(
        average_r=-0.2,
        win_rate=30.0,
        drawdown=4.0,
        confidence=60.0,
        setup="range_reversal_short",
        strategy="range_reversal",
        regime="range",
    )

    generalization = build_generalization_summary(
        training, validation, [0.8, -0.5, 0.3, -0.4]
    )
    overfitting = build_overfitting_summary(
        generalization,
        symbol_summaries=(),
        timeframe_summaries=(),
    )

    assert generalization.performance_decay_percent == 120.0
    assert generalization.expectancy_decay_percent == 120.0
    assert generalization.strategy_drift == 100.0
    assert generalization.setup_drift == 100.0
    assert generalization.regime_drift == 100.0
    assert generalization.generalization_score < 50
    assert overfitting.performance_collapse is True
    assert overfitting.confidence_collapse is True
    assert overfitting.risk_instability is True
    assert overfitting.risk_level in {"HIGH", "OVERFIT_RISK"}


class _Provider:
    def get_candles(self, symbol: str, timeframe: str, lookback: int) -> list[Candle]:
        del symbol, timeframe
        candles = [
            Candle(
                index,
                100 + index * 0.1,
                100.3 + index * 0.1,
                99.7 + index * 0.1,
                100 + index * 0.1,
                100,
            )
            for index in range(320)
        ]
        return candles[-lookback:]


def _payload(enabled: bool) -> dict[str, object]:
    return {
        "symbols": ["BTC-USD"],
        "timeframes": ["5m"],
        "higher_timeframes": ["1h"],
        "lookback": 100,
        "max_trades_per_run": 5,
        "out_of_sample_validation": enabled,
        "validation_method": "walk_forward",
        "training_percent": 70,
        "validation_percent": 30,
        "validation_folds": 5,
    }


def test_api_out_of_sample_is_additive_deterministic_and_regression_safe() -> None:
    app.dependency_overrides[get_market_data_provider] = lambda: _Provider()
    try:
        client = TestClient(app)
        baseline = client.post("/calibrate", json=_payload(False))
        first = client.post("/calibrate", json=_payload(True))
        second = client.post("/calibrate", json=_payload(True))
        analysis = client.post(
            "/analysis",
            json={
                "symbol": "BTC-USD",
                "timeframe": "5m",
                "higher_timeframe": "1h",
                "lookback": 100,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert baseline.status_code == first.status_code == second.status_code == 200
    assert baseline.json()["out_of_sample_summary"] is None
    assert first.json()["out_of_sample_summary"] is not None
    assert len(first.json()["validation_fold_results"]) == 5
    assert first.json()["symbol_validation_summary"][0]["name"] == "BTC-USD"
    assert first.json()["timeframe_validation_summary"][0]["name"] == "5m"
    assert first.json()["aggregate_metrics"] == baseline.json()["aggregate_metrics"]
    assert first.json()["aggregate_skip_diagnostics"] == baseline.json()["aggregate_skip_diagnostics"]
    assert first.json()["out_of_sample_summary"] == second.json()["out_of_sample_summary"]
    assert first.json()["generalization_summary"] == second.json()["generalization_summary"]
    assert analysis.status_code == 200
    assert "out_of_sample_summary" not in analysis.json()


def test_exact_300_candle_request_serializes_all_oos_sections() -> None:
    request = {
        "symbols": ["BTC-USD"],
        "timeframes": ["5m"],
        "higher_timeframes": ["1h"],
        "lookback": 300,
        "max_trades_per_run": 50,
        "risk_per_trade_percent": 1,
        "starting_balance": 10000,
        "out_of_sample_validation": True,
        "validation_method": "walk_forward",
        "training_percent": 70,
        "validation_percent": 30,
        "validation_folds": 3,
    }
    app.dependency_overrides[get_market_data_provider] = lambda: _Provider()
    try:
        client = TestClient(app)
        response = client.post("/calibrate", json=request)
        openapi = client.get("/openapi.json").json()
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    for field in (
        "out_of_sample_summary",
        "validation_fold_results",
        "generalization_summary",
        "overfitting_summary",
        "stability_summary",
        "symbol_validation_summary",
        "timeframe_validation_summary",
        "research_recommendations",
    ):
        assert field in payload
        assert payload[field] is not None
    assert len(payload["validation_fold_results"]) == 3

    request_properties = openapi["components"]["schemas"]["CalibrationRequest"]["properties"]
    result_properties = openapi["components"]["schemas"]["CalibrationResult"]["properties"]
    for field in (
        "out_of_sample_validation",
        "validation_method",
        "training_percent",
        "validation_percent",
        "validation_folds",
    ):
        assert field in request_properties
    for field in (
        "out_of_sample_summary",
        "validation_fold_results",
        "generalization_summary",
        "overfitting_summary",
        "stability_summary",
    ):
        assert field in result_properties
