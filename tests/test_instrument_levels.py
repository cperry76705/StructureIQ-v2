"""Instrument-aware zone width, precision, and numeric risk geometry."""

import re

import pytest

from core.instruments import (
    decimal_precision,
    infer_asset_class,
    instrument_metadata,
    pip_size,
    tick_size,
)
from core.market_data import Candle
from core.risk import (
    build_numeric_risk_levels,
    build_risk_levels,
    diagnose_risk_reward,
)
from core.setup_engine import MINIMUM_ACCEPTABLE_RISK_REWARD
from core.support_resistance import detect_zones


def _forex_candles() -> list[Candle]:
    return [
        Candle(index, 1.1000, 1.1003, 1.0997, 1.1000, 100)
        for index in range(30)
    ]


def test_forex_zone_is_not_widened_by_twenty_five_points() -> None:
    support, resistance = detect_zones(
        _forex_candles(), [], [], "EUR-USD"
    )

    assert (support[1] - support[0]) / 2 < 0.01
    assert (resistance[1] - resistance[0]) / 2 < 0.01


@pytest.mark.parametrize("symbol", ["EUR-USD", "GBP-USD"])
def test_forex_levels_retain_five_decimal_precision(symbol: str) -> None:
    entry, stop, target = build_risk_levels(
        "bullish",
        (1.08495, 1.08505),
        (1.08650, 1.08660),
        symbol,
    )

    assert decimal_precision(symbol) == 5
    assert re.fullmatch(r"\d+\.\d{5}-\d+\.\d{5}", entry)
    assert re.fullmatch(r"\d+\.\d{5}", stop)
    assert re.fullmatch(r"\d+\.\d{5}", target)


@pytest.mark.parametrize("symbol", ["BTC-USD", "ETH-USD"])
def test_crypto_levels_retain_two_decimal_precision(symbol: str) -> None:
    entry, stop, target = build_risk_levels(
        "bullish",
        (3000.125, 3001.375),
        (3010.625, 3011.875),
        symbol,
    )

    assert decimal_precision(symbol) == 2
    assert re.fullmatch(r"\d+\.\d{2}-\d+\.\d{2}", entry)
    assert re.fullmatch(r"\d+\.\d{2}", stop)
    assert re.fullmatch(r"\d+\.\d{2}", target)


def test_valid_bullish_and_bearish_geometry_survives_formatting() -> None:
    bullish = build_risk_levels(
        "bullish", (1.08495, 1.08505), (1.08650, 1.08660), "EUR-USD"
    )
    bearish = build_risk_levels(
        "bearish", (1.08350, 1.08360), (1.08495, 1.08505), "EUR-USD"
    )

    bullish_diagnostics = diagnose_risk_reward(
        direction="bullish", entry_zone=bullish[0], stop_loss=bullish[1], target=bullish[2]
    )
    bearish_diagnostics = diagnose_risk_reward(
        direction="bearish", entry_zone=bearish[0], stop_loss=bearish[1], target=bearish[2]
    )
    assert bullish_diagnostics.passed is True
    assert bearish_diagnostics.passed is True


def test_calculated_r_uses_numeric_geometry_before_formatting() -> None:
    levels = build_numeric_risk_levels(
        "bullish",
        (1.00001, 1.10003),
        (1.70007, 1.80009),
    )

    assert levels.estimated_r == round(levels.reward / levels.risk, 6)
    assert levels.entry_price == pytest.approx(1.05002)


def test_metadata_exposes_asset_class_tick_and_pip_without_changing_gate() -> None:
    assert infer_asset_class("EUR-USD") == "forex"
    assert infer_asset_class("BTC-USD") == "crypto"
    assert tick_size("EUR-USD") == 0.00001
    assert pip_size("EUR-USD") == 0.0001
    assert instrument_metadata("ETH-USD").minimum_zone_width == 0.05
    assert MINIMUM_ACCEPTABLE_RISK_REWARD == 1.5
