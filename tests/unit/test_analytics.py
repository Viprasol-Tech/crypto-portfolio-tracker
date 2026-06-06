"""Tests for allocation, rebalancing, and performance metrics."""

from __future__ import annotations

import math

import pytest

from crypto_portfolio_tracker.analytics import (
    allocation,
    max_drawdown,
    performance,
    rebalance,
    time_weighted_return,
)
from crypto_portfolio_tracker.models import Side
from crypto_portfolio_tracker.portfolio import Portfolio


def _two_asset_portfolio() -> Portfolio:
    pf = Portfolio()
    pf.buy("BTC", 1.0, 20_000.0)
    pf.buy("ETH", 10.0, 1_000.0)
    return pf


def test_allocation_weights_sum_to_one() -> None:
    pf = _two_asset_portfolio()
    slices = allocation(pf, {"BTC": 30_000.0, "ETH": 2_000.0})
    # BTC value 30k, ETH value 20k, total 50k
    assert math.isclose(sum(s.weight for s in slices), 1.0)
    assert slices[0].asset == "BTC"  # sorted by descending weight
    assert math.isclose(slices[0].weight, 0.6)
    assert math.isclose(slices[1].weight, 0.4)


def test_allocation_empty_portfolio() -> None:
    assert allocation(Portfolio(), {}) == []


def test_allocation_missing_price_raises() -> None:
    pf = _two_asset_portfolio()
    with pytest.raises(KeyError):
        allocation(pf, {"BTC": 30_000.0})


def test_rebalance_suggests_buy_and_sell() -> None:
    pf = _two_asset_portfolio()
    prices = {"BTC": 30_000.0, "ETH": 2_000.0}  # BTC 60%, ETH 40%, total 50k
    actions = rebalance(pf, prices, {"BTC": 0.5, "ETH": 0.5})
    by_asset = {a.asset: a for a in actions}
    assert by_asset["BTC"].side is Side.SELL
    assert math.isclose(by_asset["BTC"].amount, 5_000.0)
    assert by_asset["ETH"].side is Side.BUY
    assert math.isclose(by_asset["ETH"].amount, 5_000.0)


def test_rebalance_already_balanced_returns_empty() -> None:
    pf = _two_asset_portfolio()
    prices = {"BTC": 30_000.0, "ETH": 2_000.0}
    actions = rebalance(pf, prices, {"BTC": 0.6, "ETH": 0.4})
    assert actions == []


def test_rebalance_min_trade_filters_small_actions() -> None:
    pf = _two_asset_portfolio()
    prices = {"BTC": 30_000.0, "ETH": 2_000.0}
    actions = rebalance(pf, prices, {"BTC": 0.59, "ETH": 0.41}, min_trade=1_000.0)
    assert actions == []


def test_rebalance_rejects_bad_target_sum() -> None:
    pf = _two_asset_portfolio()
    with pytest.raises(ValueError, match=r"sum to 1\.0"):
        rebalance(pf, {"BTC": 30_000.0, "ETH": 2_000.0}, {"BTC": 0.5, "ETH": 0.4})


def test_rebalance_rejects_negative_weight() -> None:
    pf = _two_asset_portfolio()
    with pytest.raises(ValueError, match="non-negative"):
        rebalance(pf, {"BTC": 30_000.0, "ETH": 2_000.0}, {"BTC": 1.5, "ETH": -0.5})


def test_rebalance_into_new_asset() -> None:
    pf = Portfolio()
    pf.buy("BTC", 1.0, 100.0)
    actions = rebalance(pf, {"BTC": 100.0, "ETH": 50.0}, {"BTC": 0.5, "ETH": 0.5})
    eth = next(a for a in actions if a.asset == "ETH")
    assert eth.side is Side.BUY
    assert math.isclose(eth.amount, 50.0)


def test_twr_simple_growth() -> None:
    assert math.isclose(time_weighted_return([100.0, 110.0]), 0.10)


def test_twr_chains_subperiods() -> None:
    # +10% then -50% -> 1.1 * 0.5 = 0.55 -> -45%
    assert math.isclose(time_weighted_return([100.0, 110.0, 55.0]), -0.45)


def test_twr_neutralizes_cash_flow() -> None:
    # Start 100, deposit 50 at period start, end 165 -> (165-50)/100 - 1 = 0.15
    assert math.isclose(time_weighted_return([100.0, 165.0], [50.0]), 0.15)


def test_twr_requires_two_values() -> None:
    with pytest.raises(ValueError, match="two equity values"):
        time_weighted_return([100.0])


def test_twr_bad_flow_length() -> None:
    with pytest.raises(ValueError, match="length"):
        time_weighted_return([100.0, 110.0], [0.0, 0.0])


def test_twr_zero_start_raises() -> None:
    with pytest.raises(ValueError, match="positive"):
        time_weighted_return([0.0, 100.0])


def test_max_drawdown_basic() -> None:
    dd, peak, trough = max_drawdown([100.0, 120.0, 90.0, 110.0])
    assert math.isclose(dd, 90.0 / 120.0 - 1.0)
    assert math.isclose(peak, 120.0)
    assert math.isclose(trough, 90.0)


def test_max_drawdown_monotonic_is_zero() -> None:
    dd, _, _ = max_drawdown([100.0, 110.0, 120.0])
    assert dd == 0.0


def test_max_drawdown_empty_raises() -> None:
    with pytest.raises(ValueError):
        max_drawdown([])


def test_performance_snapshot_bundles_metrics() -> None:
    snap = performance([100.0, 120.0, 90.0, 108.0])
    assert math.isclose(snap.end_value, 108.0)
    assert math.isclose(snap.start_value, 100.0)
    assert snap.max_drawdown < 0
    assert math.isclose(snap.twr, 108.0 / 100.0 - 1.0)
