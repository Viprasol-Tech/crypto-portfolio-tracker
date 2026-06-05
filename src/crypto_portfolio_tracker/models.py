"""Core types for the crypto portfolio tracker.

Part of Crypto Portfolio Tracker by Viprasol Tech Private Limited (https://viprasol.com).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Side(str, Enum):
    """Transaction side."""

    BUY = "buy"
    SELL = "sell"


@dataclass(slots=True, frozen=True)
class Transaction:
    """A single buy or sell of one asset.

    Attributes:
        asset: Ticker symbol, e.g. ``"BTC"``.
        side: Whether this transaction is a buy or a sell.
        quantity: Number of units transacted (always positive).
        price: Price per unit in the quote currency.
        fee: Flat fee in the quote currency charged for this transaction.
    """

    asset: str
    side: Side
    quantity: float
    price: float
    fee: float = 0.0


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
