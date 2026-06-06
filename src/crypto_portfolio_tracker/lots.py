"""Tax-lot accounting engine for FIFO and LIFO cost-basis methods.

A :class:`LotBook` tracks individual open *lots* (a quantity acquired at a given
unit cost and time) for a single asset. When units are sold it matches them
against open lots in FIFO or LIFO order, emitting a :class:`RealizedSale` per
consumed lot so the disposals map directly onto a tax-lot report.

Cost-basis convention (consistent with the average-cost engine):

* A buy lot's *unit cost* folds in the buy fee, i.e. ``(qty * price + fee) / qty``.
* A sell's fee is pro-rated across the matched lots by quantity and subtracted
  from the proceeds attributed to each slice.

Part of Crypto Portfolio Tracker by Viprasol Tech Private Limited (https://viprasol.com).
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime

from crypto_portfolio_tracker.models import CostBasisMethod, RealizedSale

_EPS = 1e-12


@dataclass(slots=True)
class _OpenLot:
    """A single open acquisition lot for one asset."""

    quantity: float
    unit_cost: float  # cost per unit, fee included
    acquired: datetime | None


@dataclass(slots=True)
class LotBook:
    """FIFO/LIFO open-lot ledger for a single asset.

    Args:
        method: :class:`~crypto_portfolio_tracker.models.CostBasisMethod` to use
            for matching. Must be ``FIFO`` or ``LIFO``.
    """

    method: CostBasisMethod
    _lots: deque[_OpenLot] = field(default_factory=deque)
    realized_pnl: float = 0.0

    def __post_init__(self) -> None:
        if self.method not in (CostBasisMethod.FIFO, CostBasisMethod.LIFO):
            raise ValueError(f"LotBook supports FIFO/LIFO only, not {self.method!r}")

    @property
    def quantity(self) -> float:
        """Total open quantity across all lots."""
        return sum(lot.quantity for lot in self._lots)

    @property
    def cost_basis(self) -> float:
        """Total cost basis of all open lots."""
        return sum(lot.quantity * lot.unit_cost for lot in self._lots)

    @property
    def avg_cost(self) -> float:
        """Quantity-weighted average unit cost of open lots (0.0 if empty)."""
        qty = self.quantity
        return self.cost_basis / qty if qty > _EPS else 0.0

    def add_buy(self, quantity: float, price: float, fee: float, when: datetime | None) -> None:
        """Append a new acquisition lot.

        Args:
            quantity: Units bought (must be positive).
            price: Price per unit.
            fee: Flat buy fee folded into the lot's unit cost.
            when: Acquisition timestamp (may be ``None``).
        """
        unit_cost = (quantity * price + fee) / quantity
        self._lots.append(_OpenLot(quantity=quantity, unit_cost=unit_cost, acquired=when))

    def add_sell(
        self,
        quantity: float,
        price: float,
        fee: float,
        when: datetime | None,
    ) -> list[RealizedSale]:
        """Match a sell against open lots and return the realized slices.

        Args:
            quantity: Units sold (must be <= open quantity).
            price: Sale price per unit.
            fee: Flat sell fee, pro-rated across matched lots by quantity.
            when: Disposal timestamp (may be ``None``).

        Returns:
            One :class:`RealizedSale` per consumed lot, in match order.

        Raises:
            ValueError: If selling more than the open quantity.
        """
        if quantity > self.quantity + _EPS:
            raise ValueError(f"cannot sell {quantity}: only {self.quantity} held")

        fee_per_unit = fee / quantity if quantity > 0 else 0.0
        remaining = quantity
        sales: list[RealizedSale] = []

        while remaining > _EPS:
            lot = self._lots[0] if self.method is CostBasisMethod.FIFO else self._lots[-1]
            take = min(lot.quantity, remaining)
            proceeds = take * (price - fee_per_unit)
            cost_basis = take * lot.unit_cost
            sales.append(
                RealizedSale(
                    asset="",  # filled in by the caller, which knows the symbol
                    quantity=take,
                    proceeds=proceeds,
                    cost_basis=cost_basis,
                    acquired=lot.acquired,
                    disposed=when,
                )
            )
            self.realized_pnl += proceeds - cost_basis
            lot.quantity -= take
            remaining -= take
            if lot.quantity <= _EPS:
                if self.method is CostBasisMethod.FIFO:
                    self._lots.popleft()
                else:
                    self._lots.pop()

        return sales

    def open_lots(self) -> list[_OpenLot]:
        """Return a copy of the open lots in storage order (oldest first)."""
        return list(self._lots)
