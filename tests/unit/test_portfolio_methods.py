"""Tests for cost-basis method selection and portfolio helpers."""

from __future__ import annotations

import math

import pytest

from crypto_portfolio_tracker.models import CostBasisMethod, Side, Transaction
from crypto_portfolio_tracker.portfolio import Portfolio


def test_methods_agree_when_fully_liquidated() -> None:
    # Total realized PnL is method-independent once everything is sold.
    txns = [
        Transaction("BTC", Side.BUY, 1.0, 20_000.0),
        Transaction("BTC", Side.BUY, 1.0, 30_000.0),
        Transaction("BTC", Side.SELL, 2.0, 40_000.0),
    ]
    realized = {
        m: Portfolio.from_transactions(txns, method=m).realized_pnl() for m in CostBasisMethod
    }
    assert math.isclose(realized[CostBasisMethod.AVERAGE], 30_000.0)
    assert math.isclose(realized[CostBasisMethod.FIFO], 30_000.0)
    assert math.isclose(realized[CostBasisMethod.LIFO], 30_000.0)


def test_methods_differ_on_partial_sale() -> None:
    txns = [
        Transaction("BTC", Side.BUY, 1.0, 20_000.0),
        Transaction("BTC", Side.BUY, 1.0, 30_000.0),
        Transaction("BTC", Side.SELL, 1.0, 40_000.0),
    ]
    avg = Portfolio.from_transactions(txns, method=CostBasisMethod.AVERAGE)
    fifo = Portfolio.from_transactions(txns, method=CostBasisMethod.FIFO)
    lifo = Portfolio.from_transactions(txns, method=CostBasisMethod.LIFO)
    assert math.isclose(avg.realized_pnl(), 15_000.0)
    assert math.isclose(fifo.realized_pnl(), 20_000.0)
    assert math.isclose(lifo.realized_pnl(), 10_000.0)


def test_from_transactions_replays_in_order() -> None:
    pf = Portfolio.from_transactions(
        [
            Transaction("ETH", Side.BUY, 5.0, 1_000.0),
            Transaction("ETH", Side.SELL, 2.0, 1_500.0),
        ]
    )
    assert math.isclose(pf.position("ETH").quantity, 3.0)
    assert math.isclose(pf.realized_pnl(), 1_000.0)


def test_assets_lists_everything_traded() -> None:
    pf = Portfolio()
    pf.buy("BTC", 1.0, 100.0)
    pf.buy("ETH", 1.0, 50.0)
    pf.sell("BTC", 1.0, 200.0)
    assert pf.assets() == ["BTC", "ETH"]
    assert "BTC" not in pf.holdings()  # fully sold
    assert "ETH" in pf.holdings()


def test_average_tax_lot_report_one_row_per_sell() -> None:
    pf = Portfolio(method=CostBasisMethod.AVERAGE)
    pf.buy("BTC", 2.0, 100.0)
    pf.sell("BTC", 1.0, 200.0)
    report = pf.tax_lot_report()
    assert len(report) == 1
    assert math.isclose(report[0].gain, 100.0)
    assert report[0].acquired is None


def test_unrealized_pnl_ignores_unpriced_assets() -> None:
    pf = Portfolio()
    pf.buy("BTC", 1.0, 100.0)
    pf.buy("ETH", 1.0, 50.0)
    assert math.isclose(pf.unrealized_pnl({"BTC": 150.0}), 50.0)


def test_total_value_falls_back_to_cost_basis() -> None:
    pf = Portfolio()
    pf.buy("BTC", 1.0, 100.0)
    pf.buy("ETH", 1.0, 50.0)
    assert math.isclose(pf.total_value({"BTC": 150.0}), 150.0 + 50.0)


def test_fifo_oversell_message_mentions_asset() -> None:
    pf = Portfolio(method=CostBasisMethod.FIFO)
    pf.buy("BTC", 1.0, 100.0)
    with pytest.raises(ValueError, match="BTC"):
        pf.sell("BTC", 5.0, 200.0)
