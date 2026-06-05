"""Portfolio with average-cost-basis PnL accounting.

The :class:`Portfolio` records buy/sell transactions per asset, maintains a
running *average* cost basis, computes *realized* PnL when units are sold and
*unrealized* PnL against a set of current mark prices.

Accounting model (average cost basis):

* A **buy** of ``q`` units at price ``p`` with fee ``f`` increases the held
  quantity by ``q`` and the total cost basis by ``q * p + f``. The average cost
  is the new total cost basis divided by the new quantity.
* A **sell** of ``q`` units leaves the average cost unchanged. It reduces the
  quantity by ``q`` and the cost basis by ``q * avg_cost``. Realized PnL for the
  sell is ``q * sell_price - q * avg_cost - fee``.
* Selling more than is held raises :class:`ValueError`.

Part of Crypto Portfolio Tracker by Viprasol Tech Private Limited (https://viprasol.com).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from crypto_portfolio_tracker.models import Position, Side, Transaction


@dataclass(slots=True)
class _Lot:
    """Internal mutable per-asset accumulator (average cost basis)."""

    quantity: float = 0.0
    cost_basis: float = 0.0
    realized_pnl: float = 0.0

    @property
    def avg_cost(self) -> float:
        """Average cost per held unit, or ``0.0`` when nothing is held."""
        return self.cost_basis / self.quantity if self.quantity > 0 else 0.0


@dataclass(slots=True)
class Portfolio:
    """Track holdings and PnL across multiple assets using average cost basis.

    Example:
        >>> pf = Portfolio()
        >>> pf.buy("BTC", 1.0, 20_000.0)
        >>> pf.buy("BTC", 1.0, 30_000.0)
        >>> pf.position("BTC").avg_cost
        25000.0
        >>> pf.sell("BTC", 1.0, 40_000.0)
        15000.0
    """

    _lots: dict[str, _Lot] = field(default_factory=dict)
    transactions: list[Transaction] = field(default_factory=list)

    def _lot(self, asset: str) -> _Lot:
        return self._lots.setdefault(asset, _Lot())

    def record(self, txn: Transaction) -> float:
        """Apply a transaction and return realized PnL (0.0 for buys).

        Args:
            txn: The transaction to apply.

        Returns:
            Realized PnL booked by this transaction. Buys always return ``0.0``.

        Raises:
            ValueError: If quantity/price is non-positive, or a sell exceeds the
                quantity currently held.
        """
        if txn.quantity <= 0:
            raise ValueError("quantity must be positive")
        if txn.price < 0:
            raise ValueError("price must be non-negative")
        if txn.fee < 0:
            raise ValueError("fee must be non-negative")

        lot = self._lot(txn.asset)
        if txn.side is Side.BUY:
            lot.quantity += txn.quantity
            lot.cost_basis += txn.quantity * txn.price + txn.fee
            self.transactions.append(txn)
            return 0.0

        # Sell.
        if txn.quantity > lot.quantity + 1e-12:
            raise ValueError(f"cannot sell {txn.quantity} {txn.asset}: only {lot.quantity} held")
        avg_cost = lot.avg_cost
        proceeds = txn.quantity * txn.price - txn.fee
        cost_removed = txn.quantity * avg_cost
        realized = proceeds - cost_removed
        lot.quantity -= txn.quantity
        lot.cost_basis -= cost_removed
        if lot.quantity <= 1e-12:
            # Avoid leaving a tiny residual cost basis from float error.
            lot.quantity = 0.0
            lot.cost_basis = 0.0
        lot.realized_pnl += realized
        self.transactions.append(txn)
        return realized

    def buy(self, asset: str, quantity: float, price: float, fee: float = 0.0) -> None:
        """Record a buy of ``quantity`` units of ``asset`` at ``price``.

        Args:
            asset: Ticker symbol.
            quantity: Units bought (must be positive).
            price: Price per unit in the quote currency.
            fee: Flat fee in the quote currency.
        """
        self.record(Transaction(asset, Side.BUY, quantity, price, fee))

    def sell(self, asset: str, quantity: float, price: float, fee: float = 0.0) -> float:
        """Record a sell and return the realized PnL booked.

        Args:
            asset: Ticker symbol.
            quantity: Units sold (must be positive and <= units held).
            price: Price per unit in the quote currency.
            fee: Flat fee in the quote currency.

        Returns:
            Realized PnL for this sell.

        Raises:
            ValueError: If selling more than is held.
        """
        return self.record(Transaction(asset, Side.SELL, quantity, price, fee))

    def position(self, asset: str) -> Position:
        """Return the current :class:`Position` snapshot for ``asset``.

        Args:
            asset: Ticker symbol.

        Returns:
            A :class:`Position` (zeroed if the asset was never traded).
        """
        lot = self._lots.get(asset, _Lot())
        return Position(
            asset=asset,
            quantity=lot.quantity,
            avg_cost=lot.avg_cost,
            cost_basis=lot.cost_basis,
            realized_pnl=lot.realized_pnl,
        )

    def holdings(self) -> dict[str, float]:
        """Return a mapping of asset -> quantity for assets currently held.

        Returns:
            Only assets with a strictly positive quantity are included.
        """
        return {a: lot.quantity for a, lot in self._lots.items() if lot.quantity > 0}

    def realized_pnl(self) -> float:
        """Return the total realized PnL across all assets."""
        return sum(lot.realized_pnl for lot in self._lots.values())

    def unrealized_pnl(self, prices: Mapping[str, float]) -> float:
        """Return total unrealized PnL of open positions given ``prices``.

        Args:
            prices: Mapping of asset -> current mark price. Assets missing from
                the mapping are valued at their cost basis (contribute ``0.0``).

        Returns:
            Sum of per-asset unrealized PnL.
        """
        total = 0.0
        for asset, lot in self._lots.items():
            if lot.quantity <= 0:
                continue
            mark = prices.get(asset)
            if mark is None:
                continue
            total += lot.quantity * mark - lot.cost_basis
        return total

    def total_value(self, prices: Mapping[str, float]) -> float:
        """Return the market value of all open positions given ``prices``.

        Args:
            prices: Mapping of asset -> current mark price. Held assets missing a
                price are valued at their cost basis.

        Returns:
            Total market value of the portfolio.
        """
        total = 0.0
        for asset, lot in self._lots.items():
            if lot.quantity <= 0:
                continue
            mark = prices.get(asset)
            total += lot.quantity * mark if mark is not None else lot.cost_basis
        return total
