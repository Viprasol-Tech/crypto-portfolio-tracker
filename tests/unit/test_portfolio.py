"""Tests for the average-cost-basis portfolio PnL accounting."""

from __future__ import annotations

import math

import pytest

from crypto_portfolio_tracker.portfolio import Portfolio


def test_average_cost_basis_after_multiple_buys() -> None:
    pf = Portfolio()
    pf.buy("BTC", 1.0, 20_000.0)
    pf.buy("BTC", 3.0, 30_000.0)  # weighted avg = (20000 + 90000) / 4 = 27500
    pos = pf.position("BTC")
    assert math.isclose(pos.quantity, 4.0)
    assert math.isclose(pos.avg_cost, 27_500.0)
    assert math.isclose(pos.cost_basis, 110_000.0)


def test_buy_fee_is_included_in_cost_basis() -> None:
    pf = Portfolio()
    pf.buy("ETH", 2.0, 1_000.0, fee=50.0)  # cost basis = 2050, avg = 1025
    pos = pf.position("ETH")
    assert math.isclose(pos.cost_basis, 2_050.0)
    assert math.isclose(pos.avg_cost, 1_025.0)


def test_realized_pnl_on_partial_sell() -> None:
    pf = Portfolio()
    pf.buy("BTC", 1.0, 20_000.0)
    pf.buy("BTC", 1.0, 30_000.0)  # avg cost = 25,000
    realized = pf.sell("BTC", 1.0, 40_000.0)  # (40000 - 25000) * 1 = 15000
    assert math.isclose(realized, 15_000.0)
    assert math.isclose(pf.realized_pnl(), 15_000.0)

    # Avg cost is unchanged by a sell; 1 unit remains.
    pos = pf.position("BTC")
    assert math.isclose(pos.quantity, 1.0)
    assert math.isclose(pos.avg_cost, 25_000.0)
    assert math.isclose(pos.cost_basis, 25_000.0)


def test_realized_pnl_accounts_for_sell_fee() -> None:
    pf = Portfolio()
    pf.buy("BTC", 1.0, 100.0)
    realized = pf.sell("BTC", 1.0, 150.0, fee=10.0)  # 150 - 100 - 10 = 40
    assert math.isclose(realized, 40.0)


def test_unrealized_pnl_given_mark_price() -> None:
    pf = Portfolio()
    pf.buy("BTC", 2.0, 10_000.0)  # cost basis 20,000
    # Mark at 12,000 -> value 24,000 -> unrealized 4,000.
    assert math.isclose(pf.unrealized_pnl({"BTC": 12_000.0}), 4_000.0)
    pos = pf.position("BTC")
    assert math.isclose(pos.unrealized_pnl(12_000.0), 4_000.0)
    assert math.isclose(pos.market_value(12_000.0), 24_000.0)


def test_total_value_sums_positions() -> None:
    pf = Portfolio()
    pf.buy("BTC", 1.0, 20_000.0)
    pf.buy("ETH", 10.0, 1_500.0)
    value = pf.total_value({"BTC": 25_000.0, "ETH": 2_000.0})
    assert math.isclose(value, 25_000.0 + 20_000.0)


def test_holdings_excludes_fully_sold_assets() -> None:
    pf = Portfolio()
    pf.buy("BTC", 1.0, 20_000.0)
    pf.sell("BTC", 1.0, 25_000.0)
    assert "BTC" not in pf.holdings()
    pos = pf.position("BTC")
    assert math.isclose(pos.quantity, 0.0)
    assert math.isclose(pos.realized_pnl, 5_000.0)


def test_selling_more_than_held_raises() -> None:
    pf = Portfolio()
    pf.buy("BTC", 1.0, 20_000.0)
    with pytest.raises(ValueError):
        pf.sell("BTC", 2.0, 25_000.0)


def test_negative_quantity_raises() -> None:
    pf = Portfolio()
    with pytest.raises(ValueError):
        pf.buy("BTC", -1.0, 20_000.0)
