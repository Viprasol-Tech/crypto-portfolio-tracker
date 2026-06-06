"""Portfolio analytics: allocation, rebalancing, and performance metrics.

Pure functions over a :class:`~crypto_portfolio_tracker.portfolio.Portfolio` and
mark prices. Nothing here mutates the portfolio.

* :func:`allocation` — current market-value weights per asset.
* :func:`rebalance` — trades to move from current to a target allocation.
* :func:`time_weighted_return` — TWR over an equity curve with external flows.
* :func:`max_drawdown` — worst peak-to-trough decline of an equity curve.
* :func:`performance` — bundles TWR + drawdown into a snapshot.

Part of Crypto Portfolio Tracker by Viprasol Tech Private Limited (https://viprasol.com).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from crypto_portfolio_tracker.models import (
    AllocationSlice,
    PerformanceSnapshot,
    RebalanceAction,
    Side,
)
from crypto_portfolio_tracker.portfolio import Portfolio

_EPS = 1e-12


def allocation(pf: Portfolio, prices: Mapping[str, float]) -> list[AllocationSlice]:
    """Return the current allocation of ``pf`` by market-value weight.

    Args:
        pf: The portfolio to inspect.
        prices: Mapping of asset -> current mark price.

    Returns:
        One :class:`AllocationSlice` per held asset, sorted by descending weight.
        Returns an empty list when the portfolio has no market value.

    Raises:
        KeyError: If a held asset is missing from ``prices``.
    """
    values: dict[str, float] = {}
    for asset, qty in pf.holdings().items():
        values[asset] = qty * prices[asset]
    total = sum(values.values())
    if total <= _EPS:
        return []
    slices = [AllocationSlice(asset=a, market_value=v, weight=v / total) for a, v in values.items()]
    slices.sort(key=lambda s: (-s.weight, s.asset))
    return slices


def rebalance(
    pf: Portfolio,
    prices: Mapping[str, float],
    targets: Mapping[str, float],
    *,
    min_trade: float = 0.0,
) -> list[RebalanceAction]:
    """Suggest trades to move ``pf`` toward ``targets``.

    Args:
        pf: The portfolio to rebalance.
        prices: Mapping of asset -> current mark price (must cover held + target
            assets).
        targets: Mapping of asset -> desired weight. Weights must be
            non-negative and sum to approximately 1.0.
        min_trade: Suppress suggested trades whose notional is below this amount.

    Returns:
        One :class:`RebalanceAction` per asset needing a trade, sorted by
        descending notional. Assets already at target are omitted.

    Raises:
        ValueError: If any target weight is negative or the weights do not sum
            to ~1.0.
        KeyError: If a held or target asset is missing from ``prices``.
    """
    if any(w < 0 for w in targets.values()):
        raise ValueError("target weights must be non-negative")
    weight_sum = sum(targets.values())
    if targets and abs(weight_sum - 1.0) > 1e-6:
        raise ValueError(f"target weights must sum to 1.0, got {weight_sum}")

    held = pf.holdings()
    values = {a: held[a] * prices[a] for a in held}
    total = sum(values.values())
    if total <= _EPS:
        return []

    universe = set(values) | set(targets)
    actions: list[RebalanceAction] = []
    for asset in universe:
        current_value = values.get(asset, 0.0)
        current_weight = current_value / total
        target_weight = targets.get(asset, 0.0)
        delta = target_weight * total - current_value
        if abs(delta) <= max(min_trade, _EPS):
            continue
        actions.append(
            RebalanceAction(
                asset=asset,
                side=Side.BUY if delta > 0 else Side.SELL,
                amount=abs(delta),
                current_weight=current_weight,
                target_weight=target_weight,
            )
        )
    actions.sort(key=lambda a: (-a.amount, a.asset))
    return actions


def time_weighted_return(
    values: Sequence[float],
    flows: Sequence[float] | None = None,
) -> float:
    """Return the time-weighted return (TWR) of an equity curve.

    TWR neutralizes the timing and size of external cash flows, isolating
    investment performance. Each sub-period return is
    ``(value_end - flow) / value_start - 1`` where ``flow`` is the deposit
    (positive) or withdrawal (negative) made at the *start* of the period; the
    chained product of ``(1 + r)`` minus one is the TWR.

    Args:
        values: Equity values sampled at period boundaries (length >= 2).
        flows: External flows aligned to ``values[1:]`` (deposit at the start of
            each sub-period). Defaults to all zeros. Must be one shorter than
            ``values``.

    Returns:
        TWR as a fraction (0.10 == +10%).

    Raises:
        ValueError: If fewer than two values are given, ``flows`` has the wrong
            length, or a sub-period starts from a non-positive value.
    """
    if len(values) < 2:
        raise ValueError("need at least two equity values")
    if flows is None:
        flows = [0.0] * (len(values) - 1)
    if len(flows) != len(values) - 1:
        raise ValueError("flows must have length len(values) - 1")

    growth = 1.0
    for i in range(1, len(values)):
        start = values[i - 1]
        if start <= _EPS:
            raise ValueError("sub-period start value must be positive")
        period_return = (values[i] - flows[i - 1]) / start
        growth *= period_return
    return growth - 1.0


def max_drawdown(values: Sequence[float]) -> tuple[float, float, float]:
    """Return the worst peak-to-trough decline of an equity curve.

    Args:
        values: Equity values in chronological order (length >= 1).

    Returns:
        A tuple ``(drawdown, peak, trough)`` where ``drawdown`` is a negative
        fraction (e.g. ``-0.25`` for a 25% decline), ``peak`` is the running
        high before the worst trough, and ``trough`` is that trough value. A
        monotonically rising curve yields ``(0.0, peak, peak)``.

    Raises:
        ValueError: If ``values`` is empty.
    """
    if not values:
        raise ValueError("values must be non-empty")
    peak = values[0]
    worst = 0.0
    worst_peak = values[0]
    worst_trough = values[0]
    for v in values:
        if v > peak:
            peak = v
        if peak > _EPS:
            dd = v / peak - 1.0
            if dd < worst:
                worst = dd
                worst_peak = peak
                worst_trough = v
    return worst, worst_peak, worst_trough


def performance(
    values: Sequence[float],
    flows: Sequence[float] | None = None,
) -> PerformanceSnapshot:
    """Bundle TWR and max drawdown into a :class:`PerformanceSnapshot`.

    Args:
        values: Equity curve (length >= 2).
        flows: Optional external flows passed through to
            :func:`time_weighted_return`.

    Returns:
        A populated :class:`PerformanceSnapshot`.
    """
    twr = time_weighted_return(values, flows)
    dd, peak, trough = max_drawdown(values)
    return PerformanceSnapshot(
        twr=twr,
        max_drawdown=dd,
        peak_value=peak,
        trough_value=trough,
        start_value=values[0],
        end_value=values[-1],
    )
