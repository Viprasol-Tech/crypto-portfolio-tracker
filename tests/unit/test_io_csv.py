"""Tests for CSV import/export round-tripping."""

from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path

import pytest

from crypto_portfolio_tracker.io_csv import (
    dump_transactions,
    load_transactions,
    parse_transactions,
    save_transactions,
)
from crypto_portfolio_tracker.models import Side, Transaction
from crypto_portfolio_tracker.portfolio import Portfolio

_CSV = """timestamp,asset,side,quantity,price,fee
2024-01-01T00:00:00,BTC,buy,1,20000,10
2024-03-01T00:00:00,BTC,buy,1,30000,10
2025-06-01T00:00:00,BTC,sell,1,40000,10
"""


def test_parse_basic_csv() -> None:
    txns = parse_transactions(_CSV.splitlines())
    assert len(txns) == 3
    assert txns[0].asset == "BTC"
    assert txns[0].side is Side.BUY
    assert math.isclose(txns[0].price, 20_000.0)
    assert txns[0].timestamp == datetime(2024, 1, 1)
    assert txns[2].side is Side.SELL


def test_parse_normalizes_asset_and_side_case() -> None:
    txns = parse_transactions(["asset,side,quantity,price", "btc,BUY,1,100"])
    assert txns[0].asset == "BTC"
    assert txns[0].side is Side.BUY


def test_parse_optional_fee_defaults_zero() -> None:
    txns = parse_transactions(["asset,side,quantity,price", "ETH,buy,2,1000"])
    assert txns[0].fee == 0.0


def test_parse_missing_columns_raises() -> None:
    with pytest.raises(ValueError, match="missing required columns"):
        parse_transactions(["asset,side,quantity", "BTC,buy,1"])


def test_parse_bad_side_raises() -> None:
    with pytest.raises(ValueError, match="invalid side"):
        parse_transactions(["asset,side,quantity,price", "BTC,hodl,1,100"])


def test_parse_bad_number_raises() -> None:
    with pytest.raises(ValueError, match="invalid number"):
        parse_transactions(["asset,side,quantity,price", "BTC,buy,x,100"])


def test_parse_bad_timestamp_raises() -> None:
    with pytest.raises(ValueError, match="timestamp"):
        parse_transactions(["timestamp,asset,side,quantity,price", "nope,BTC,buy,1,100"])


def test_round_trip_preserves_transactions() -> None:
    original = [
        Transaction("BTC", Side.BUY, 1.0, 20_000.0, 10.0, datetime(2024, 1, 1)),
        Transaction("ETH", Side.SELL, 2.0, 1_500.0, 0.0, None),
    ]
    text = dump_transactions(original)
    restored = parse_transactions(text.splitlines())
    assert len(restored) == 2
    assert restored[0].asset == "BTC"
    assert restored[0].timestamp == datetime(2024, 1, 1)
    assert restored[1].timestamp is None
    assert math.isclose(restored[0].fee, 10.0)


def test_file_save_and_load(tmp_path: Path) -> None:
    txns = parse_transactions(_CSV.splitlines())
    out = tmp_path / "ledger.csv"
    save_transactions(txns, out)
    reloaded = load_transactions(out)
    assert len(reloaded) == 3
    pf = Portfolio.from_transactions(reloaded)
    # avg basis (20010 + 30010) / 2 = 25010; proceeds 40000 - 10 = 39990.
    assert math.isclose(pf.realized_pnl(), 39_990.0 - 25_010.0)


def test_empty_input_returns_empty_list() -> None:
    assert parse_transactions([]) == []
