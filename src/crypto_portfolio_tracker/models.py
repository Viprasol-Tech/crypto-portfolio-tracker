"""Core types for the crypto portfolio tracker.

Part of Crypto Portfolio Tracker by Viprasol Tech Private Limited (https://viprasol.com).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Side(str, Enum):
    """Transaction side."""

    BUY = "buy"
    SELL = "sell"


class CostBasisMethod(str, Enum):
    """Supported cost-basis accounting methods.

    * ``AVERAGE`` — weighted-average cost across all open units.
    * ``FIFO`` — first-in, first-out lot matching (the IRS default in the US).
    * ``LIFO`` — last-in, first-out lot matching.
    """

    AVERAGE = "average"
    FIFO = "fifo"
    LIFO = "lifo"


@dataclass(slots=True, frozen=True)
class Transaction:
    """A single buy or sell of one asset.

    Attributes:
        asset: Ticker symbol, e.g. ``"BTC"``.
        side: Whether this transaction is a buy or a sell.
        quantity: Number of units transacted (always positive).
        price: Price per unit in the quote currency.
        fee: Flat fee in the quote currency charged for this transaction.
        timestamp: When the transaction occurred. Used to order tax lots and to
            compute time-weighted returns. ``None`` means "unknown / unordered".
    """

    asset: str
    side: Side
    quantity: float
    price: float
    fee: float = 0.0
    timestamp: datetime | None = None


@dataclass(slots=True, frozen=True)
class Position:
    """A snapshot of holdings and PnL for a single asset.

    Attributes:
        asset: Ticker symbol.
        quantity: Units currently held.
        avg_cost: Average cost basis per unit (includes buy fees).
        cost_basis: Total cost of the units currently held (``quantity * avg_cost``).
        realized_pnl: Cumulative realized profit/loss from sells so far.
    """

    asset: str
    quantity: float
    avg_cost: float
    cost_basis: float
    realized_pnl: float

    def unrealized_pnl(self, mark_price: float) -> float:
        """Return unrealized PnL of the open position at ``mark_price``.

        Args:
            mark_price: Current market price per unit.

        Returns:
            ``quantity * mark_price - cost_basis``.
        """
        return self.quantity * mark_price - self.cost_basis

    def market_value(self, mark_price: float) -> float:
        """Return the market value of the open position at ``mark_price``.

        Args:
            mark_price: Current market price per unit.

        Returns:
            ``quantity * mark_price``.
        """
        return self.quantity * mark_price


@dataclass(slots=True, frozen=True)
class RealizedSale:
    """A realized disposal produced when units are sold under FIFO/LIFO matching.

    Each sale may consume several open lots; one :class:`RealizedSale` is emitted
    per consumed lot so it maps cleanly onto a tax-lot report row.

    Attributes:
        asset: Ticker symbol.
        quantity: Units disposed from the matched lot.
        proceeds: Sale proceeds attributable to this slice (net of a pro-rated
            share of the sell fee).
        cost_basis: Cost basis of the matched units (includes the original buy
            fee, pro-rated).
        acquired: Timestamp the matched lot was acquired (``None`` if unknown).
        disposed: Timestamp of the sale (``None`` if unknown).
    """

    asset: str
    quantity: float
    proceeds: float
    cost_basis: float
    acquired: datetime | None = None
    disposed: datetime | None = None

    @property
    def gain(self) -> float:
        """Realized gain/loss for this slice (``proceeds - cost_basis``)."""
        return self.proceeds - self.cost_basis

    @property
    def holding_days(self) -> int | None:
        """Days held between acquisition and disposal, or ``None`` if unknown."""
        if self.acquired is None or self.disposed is None:
            return None
        return (self.disposed - self.acquired).days

    @property
    def long_term(self) -> bool | None:
        """``True`` if held > 365 days (US long-term), ``None`` if unknown."""
        days = self.holding_days
        if days is None:
            return None
        return days > 365


@dataclass(slots=True, frozen=True)
class AllocationSlice:
    """One asset's share of total portfolio market value.

    Attributes:
        asset: Ticker symbol.
        market_value: Current market value of the position.
        weight: Fraction of total portfolio value in [0, 1].
    """

    asset: str
    market_value: float
    weight: float


@dataclass(slots=True, frozen=True)
class RebalanceAction:
    """A suggested trade to move toward a target allocation.

    Attributes:
        asset: Ticker symbol.
        side: ``BUY`` to add exposure, ``SELL`` to trim.
        amount: Quote-currency notional to trade (always positive).
        current_weight: Current weight in [0, 1].
        target_weight: Target weight in [0, 1].
    """

    asset: str
    side: Side
    amount: float
    current_weight: float
    target_weight: float


@dataclass(slots=True, frozen=True)
class PerformanceSnapshot:
    """Aggregate performance metrics for an equity curve.

    Attributes:
        twr: Time-weighted return as a fraction (0.10 == +10%).
        max_drawdown: Worst peak-to-trough decline as a negative fraction.
        peak_value: Highest equity value observed.
        trough_value: Lowest equity value at the deepest drawdown.
        start_value: First equity value in the curve.
        end_value: Last equity value in the curve.
    """

    twr: float
    max_drawdown: float
    peak_value: float
    trough_value: float
    start_value: float
    end_value: float
