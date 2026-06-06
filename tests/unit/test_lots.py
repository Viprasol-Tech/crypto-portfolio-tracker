"""Tests for FIFO/LIFO lot accounting via the portfolio and LotBook."""

from __future__ import annotations

import math
from datetime import datetime

import pytest

from crypto_portfolio_tracker.lots import LotBook
from crypto_portfolio_tracker.models import CostBasisMethod
from crypto_portfolio_tracker.portfolio import Portfolio


def test_fifo_matches_oldest_lot_first() -> None:
    pf = Portfolio(method=CostBasisMethod.FIFO)
    pf.buy("BTC", 1.0, 20_000.0)
    pf.buy("BTC", 1.0, 30_000.0)
    realized = pf.sell("BTC", 1.0, 40_000.0)  # consumes the 20k lot
    assert math.isclose(realized, 20_000.0)
    pos = pf.position("BTC")
    assert math.isclose(pos.quantity, 1.0)
    assert math.isclose(pos.cost_basis, 30_000.0)  # the 30k lot remains


def test_lifo_matches_newest_lot_first() -> None:
    pf = Portfolio(method=CostBasisMethod.LIFO)
    pf.buy("BTC", 1.0, 20_000.0)
    pf.buy("BTC", 1.0, 30_000.0)
    realized = pf.sell("BTC", 1.0, 40_000.0)  # consumes the 30k lot
    assert math.isclose(realized, 10_000.0)
    pos = pf.position("BTC")
    assert math.isclose(pos.cost_basis, 20_000.0)  # the 20k lot remains


def test_fifo_sell_spanning_two_lots() -> None:
    pf = Portfolio(method=CostBasisMethod.FIFO)
    pf.buy("ETH", 2.0, 1_000.0)
    pf.buy("ETH", 2.0, 2_000.0)
    realized = pf.sell("ETH", 3.0, 2_500.0)
    # 2 @ basis 1000 -> gain 2*(2500-1000)=3000; 1 @ basis 2000 -> 500. Total 3500.
    assert math.isclose(realized, 3_500.0)
    assert math.isclose(pf.position("ETH").quantity, 1.0)
    assert math.isclose(pf.position("ETH").cost_basis, 2_000.0)


def test_fifo_tax_lot_report_has_row_per_consumed_lot() -> None:
    pf = Portfolio(method=CostBasisMethod.FIFO)
    pf.buy("ETH", 2.0, 1_000.0)
    pf.buy("ETH", 2.0, 2_000.0)
    pf.sell("ETH", 3.0, 2_500.0)
    report = pf.tax_lot_report()
    assert len(report) == 2
    assert all(r.asset == "ETH" for r in report)
    assert math.isclose(sum(r.gain for r in report), 3_500.0)


def test_fifo_buy_fee_folds_into_basis() -> None:
    pf = Portfolio(method=CostBasisMethod.FIFO)
    pf.buy("BTC", 1.0, 100.0, fee=10.0)  # unit cost 110
    realized = pf.sell("BTC", 1.0, 200.0, fee=5.0)  # proceeds 195, basis 110
    assert math.isclose(realized, 85.0)


def test_holding_period_classification() -> None:
    pf = Portfolio(method=CostBasisMethod.FIFO)
    pf.buy("BTC", 1.0, 100.0, timestamp=datetime(2023, 1, 1))
    pf.sell("BTC", 1.0, 200.0, timestamp=datetime(2024, 6, 1))
    sale = pf.tax_lot_report()[0]
    assert sale.holding_days is not None and sale.holding_days > 365
    assert sale.long_term is True


def test_short_term_classification() -> None:
    pf = Portfolio(method=CostBasisMethod.FIFO)
    pf.buy("BTC", 1.0, 100.0, timestamp=datetime(2024, 1, 1))
    pf.sell("BTC", 1.0, 200.0, timestamp=datetime(2024, 3, 1))
    sale = pf.tax_lot_report()[0]
    assert sale.long_term is False


def test_holding_days_none_without_timestamps() -> None:
    pf = Portfolio(method=CostBasisMethod.FIFO)
    pf.buy("BTC", 1.0, 100.0)
    pf.sell("BTC", 1.0, 200.0)
    sale = pf.tax_lot_report()[0]
    assert sale.holding_days is None
    assert sale.long_term is None


def test_fifo_oversell_raises() -> None:
    pf = Portfolio(method=CostBasisMethod.FIFO)
    pf.buy("BTC", 1.0, 100.0)
    with pytest.raises(ValueError, match="cannot sell"):
        pf.sell("BTC", 2.0, 200.0)


def test_lotbook_rejects_average_method() -> None:
    with pytest.raises(ValueError, match="FIFO/LIFO only"):
        LotBook(CostBasisMethod.AVERAGE)


def test_lotbook_avg_cost_empty_is_zero() -> None:
    book = LotBook(CostBasisMethod.FIFO)
    assert book.avg_cost == 0.0
    assert book.quantity == 0.0
