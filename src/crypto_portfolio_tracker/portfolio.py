"""Portfolio with pluggable cost-basis PnL accounting.

The :class:`Portfolio` records buy/sell transactions per asset, maintains cost
basis under a chosen :class:`~crypto_portfolio_tracker.models.CostBasisMethod`
(``AVERAGE``, ``FIFO`` or ``LIFO``), computes *realized* PnL when units are sold
and *unrealized* PnL against a set of current mark prices.

Accounting model:

* **Average** — a buy of ``q`` units at price ``p`` with fee ``f`` increases the
  held quantity by ``q`` and the total cost basis by ``q * p + f``; the average
  cost is the new total cost basis over the new quantity. A sell leaves the
  average cost unchanged and books ``q * sell_price - q * avg_cost - fee``.
* **FIFO / LIFO** — buys create discrete lots; sells consume open lots in
  first-in or last-in order and emit per-lot :class:`RealizedSale` rows suitable
  for a tax-lot report.

Selling more than is held raises :class:`ValueError` under every method.

Part of Crypto Portfolio Tracker by Viprasol Tech Private Limited (https://viprasol.com).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from crypto_portfolio_tracker.lots import LotBook
from crypto_portfolio_tracker.models import (
    CostBasisMethod,
    Position,
    RealizedSale,
    Side,
    Transaction,
)

_EPS = 1e-12


@dataclass(slots=True)
class _AvgLot:
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
    """Track holdings and PnL across multiple assets.

    Args:
        method: Cost-basis method to use for all assets. Defaults to ``AVERAGE``.

    Example:
        >>> pf = Portfolio()
        >>> pf.buy("BTC", 1.0, 20_000.0)
        >>> pf.buy("BTC", 1.0, 30_000.0)
        >>> pf.position("BTC").avg_cost
        25000.0
        >>> pf.sell("BTC", 1.0, 40_000.0)
        15000.0
    """

    method: CostBasisMethod = CostBasisMethod.AVERAGE
    _avg_lots: dict[str, _AvgLot] = field(default_factory=dict)
    _lot_books: dict[str, LotBook] = field(default_factory=dict)
    transactions: list[Transaction] = field(default_factory=list)
    realized_sales: list[RealizedSale] = field(default_factory=list)

    @classmethod
    def from_transactions(
        cls,
        transactions: list[Transaction],
        method: CostBasisMethod = CostBasisMethod.AVERAGE,
    ) -> Portfolio:
        """Build a portfolio by replaying ``transactions`` in order.

        Args:
            transactions: Transactions to apply, oldest first.
            method: Cost-basis method to use.

        Returns:
            A populated :class:`Portfolio`.
        """
        pf = cls(method=method)
        for txn in transactions:
            pf.record(txn)
        return pf

    # -- internal lookups ------------------------------------------------

    def _avg(self, asset: str) -> _AvgLot:
        return self._avg_lots.setdefault(asset, _AvgLot())

    def _book(self, asset: str) -> LotBook:
        return self._lot_books.setdefault(asset, LotBook(self.method))

    # -- recording -------------------------------------------------------

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

        if self.method is CostBasisMethod.AVERAGE:
            realized = self._record_average(txn)
        else:
            realized = self._record_lots(txn)
        self.transactions.append(txn)
        return realized

    def _record_average(self, txn: Transaction) -> float:
        lot = self._avg(txn.asset)
        if txn.side is Side.BUY:
            lot.quantity += txn.quantity
            lot.cost_basis += txn.quantity * txn.price + txn.fee
            return 0.0

        if txn.quantity > lot.quantity + _EPS:
            raise ValueError(f"cannot sell {txn.quantity} {txn.asset}: only {lot.quantity} held")
        avg_cost = lot.avg_cost
        proceeds = txn.quantity * txn.price - txn.fee
        cost_removed = txn.quantity * avg_cost
        realized = proceeds - cost_removed
        lot.quantity -= txn.quantity
        lot.cost_basis -= cost_removed
        if lot.quantity <= _EPS:
            lot.quantity = 0.0
            lot.cost_basis = 0.0
        lot.realized_pnl += realized
        self.realized_sales.append(
            RealizedSale(
                asset=txn.asset,
                quantity=txn.quantity,
                proceeds=proceeds,
                cost_basis=cost_removed,
                acquired=None,
                disposed=txn.timestamp,
            )
        )
        return realized

    def _record_lots(self, txn: Transaction) -> float:
        book = self._book(txn.asset)
        if txn.side is Side.BUY:
            book.add_buy(txn.quantity, txn.price, txn.fee, txn.timestamp)
            return 0.0

        try:
            sales = book.add_sell(txn.quantity, txn.price, txn.fee, txn.timestamp)
        except ValueError as exc:
            raise ValueError(f"cannot sell {txn.quantity} {txn.asset}: {exc}") from exc
        realized = 0.0
        for sale in sales:
            stamped = RealizedSale(
                asset=txn.asset,
                quantity=sale.quantity,
                proceeds=sale.proceeds,
                cost_basis=sale.cost_basis,
                acquired=sale.acquired,
                disposed=sale.disposed,
            )
            self.realized_sales.append(stamped)
            realized += stamped.gain
        return realized

    def buy(
        self,
        asset: str,
        quantity: float,
        price: float,
        fee: float = 0.0,
        timestamp: object = None,
    ) -> None:
        """Record a buy of ``quantity`` units of ``asset`` at ``price``."""
        from datetime import datetime

        ts = timestamp if isinstance(timestamp, datetime) else None
        self.record(Transaction(asset, Side.BUY, quantity, price, fee, ts))

    def sell(
        self,
        asset: str,
        quantity: float,
        price: float,
        fee: float = 0.0,
        timestamp: object = None,
    ) -> float:
        """Record a sell and return the realized PnL booked."""
        from datetime import datetime

        ts = timestamp if isinstance(timestamp, datetime) else None
        return self.record(Transaction(asset, Side.SELL, quantity, price, fee, ts))

    # -- snapshots -------------------------------------------------------

    def _qty_cost(self, asset: str) -> tuple[float, float, float]:
        """Return ``(quantity, cost_basis, realized_pnl)`` for an asset."""
        if self.method is CostBasisMethod.AVERAGE:
            lot = self._avg_lots.get(asset)
            if lot is None:
                return 0.0, 0.0, 0.0
            return lot.quantity, lot.cost_basis, lot.realized_pnl
        book = self._lot_books.get(asset)
        if book is None:
            return 0.0, 0.0, 0.0
        return book.quantity, book.cost_basis, book.realized_pnl

    def position(self, asset: str) -> Position:
        """Return the current :class:`Position` snapshot for ``asset``."""
        quantity, cost_basis, realized = self._qty_cost(asset)
        avg_cost = cost_basis / quantity if quantity > _EPS else 0.0
        return Position(
            asset=asset,
            quantity=quantity,
            avg_cost=avg_cost,
            cost_basis=cost_basis,
            realized_pnl=realized,
        )

    def assets(self) -> list[str]:
        """Return every asset ever traded, sorted alphabetically."""
        keys = set(self._avg_lots) | set(self._lot_books)
        return sorted(keys)

    def holdings(self) -> dict[str, float]:
        """Return a mapping of asset -> quantity for assets currently held.

        Only assets with a strictly positive quantity are included.
        """
        result: dict[str, float] = {}
        for asset in self.assets():
            qty, _, _ = self._qty_cost(asset)
            if qty > _EPS:
                result[asset] = qty
        return result

    def realized_pnl(self) -> float:
        """Return the total realized PnL across all assets."""
        if self.method is CostBasisMethod.AVERAGE:
            return sum(lot.realized_pnl for lot in self._avg_lots.values())
        return sum(book.realized_pnl for book in self._lot_books.values())

    def tax_lot_report(self) -> list[RealizedSale]:
        """Return every realized disposal recorded so far (a tax-lot report).

        For FIFO/LIFO there is one row per consumed lot, carrying acquisition and
        disposal timestamps and holding-period classification. For AVERAGE there
        is one row per sell with no acquisition date.
        """
        return list(self.realized_sales)

    def unrealized_pnl(self, prices: Mapping[str, float]) -> float:
        """Return total unrealized PnL of open positions given ``prices``.

        Assets missing from ``prices`` contribute ``0.0``.
        """
        total = 0.0
        for asset in self.assets():
            qty, cost_basis, _ = self._qty_cost(asset)
            if qty <= _EPS:
                continue
            mark = prices.get(asset)
            if mark is None:
                continue
            total += qty * mark - cost_basis
        return total

    def total_value(self, prices: Mapping[str, float]) -> float:
        """Return the market value of all open positions given ``prices``.

        Held assets missing a price are valued at their cost basis.
        """
        total = 0.0
        for asset in self.assets():
            qty, cost_basis, _ = self._qty_cost(asset)
            if qty <= _EPS:
                continue
            mark = prices.get(asset)
            total += qty * mark if mark is not None else cost_basis
        return total
