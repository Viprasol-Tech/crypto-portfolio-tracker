"""Command-line interface for Crypto Portfolio Tracker.

Subcommands:

* ``demo`` — record sample transactions and print a PnL summary.
* ``summary`` — import a CSV ledger and print holdings + PnL under a chosen
  cost-basis method.
* ``taxlots`` — print a realized tax-lot report from a CSV ledger.
* ``allocation`` — print current allocation weights given mark prices.
* ``rebalance`` — suggest trades to reach a target allocation.
* ``performance`` — TWR and max-drawdown over an equity curve.
* ``export-sample`` — write a sample CSV ledger you can edit.
* ``version`` — print the installed version.

Prices are passed as ``ASSET=PRICE`` pairs, e.g. ``--price BTC=45000``.

Part of Crypto Portfolio Tracker by Viprasol Tech Private Limited (https://viprasol.com).
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from crypto_portfolio_tracker import __version__
from crypto_portfolio_tracker.analytics import allocation, performance, rebalance
from crypto_portfolio_tracker.io_csv import dump_transactions, load_transactions
from crypto_portfolio_tracker.models import CostBasisMethod, Side, Transaction
from crypto_portfolio_tracker.portfolio import Portfolio

app = typer.Typer(add_completion=False, help="Crypto Portfolio Tracker - by Viprasol Tech.")
console = Console()


def _parse_prices(pairs: list[str]) -> dict[str, float]:
    """Parse ``ASSET=PRICE`` strings into a price map."""
    prices: dict[str, float] = {}
    for pair in pairs:
        if "=" not in pair:
            raise typer.BadParameter(f"expected ASSET=PRICE, got {pair!r}")
        asset, _, raw = pair.partition("=")
        try:
            prices[asset.strip().upper()] = float(raw)
        except ValueError as exc:
            raise typer.BadParameter(f"invalid price in {pair!r}") from exc
    return prices


def _load(csv_path: Path, method: CostBasisMethod) -> Portfolio:
    txns = load_transactions(csv_path)
    return Portfolio.from_transactions(txns, method=method)


@app.command()
def version() -> None:
    """Print the installed version."""
    console.print(f"crypto-portfolio-tracker [bold cyan]{__version__}[/] - by Viprasol Tech")


@app.command()
def demo() -> None:
    """Record sample transactions and print a portfolio PnL summary."""
    pf = Portfolio()
    pf.buy("BTC", 1.0, 20_000.0)
    pf.buy("BTC", 1.0, 30_000.0)
    realized = pf.sell("BTC", 1.0, 40_000.0)
    pf.buy("ETH", 10.0, 1_500.0)

    prices = {"BTC": 45_000.0, "ETH": 2_000.0}

    table = Table(title="Portfolio Summary", header_style="bold cyan")
    table.add_column("Asset")
    table.add_column("Qty", justify="right")
    table.add_column("Avg cost", justify="right")
    table.add_column("Mark", justify="right")
    table.add_column("Unrealized PnL", justify="right")
    table.add_column("Realized PnL", justify="right")

    for asset in sorted(pf.holdings()):
        pos = pf.position(asset)
        mark = prices[asset]
        table.add_row(
            asset,
            f"{pos.quantity:,.4f}",
            f"${pos.avg_cost:,.2f}",
            f"${mark:,.2f}",
            f"${pos.unrealized_pnl(mark):,.2f}",
            f"${pos.realized_pnl:,.2f}",
        )

    console.print(table)
    console.print(f"Last sell realized: [bold green]${realized:,.2f}[/]")
    console.print(f"Total realized PnL:   [bold green]${pf.realized_pnl():,.2f}[/]")
    console.print(f"Total unrealized PnL: [bold green]${pf.unrealized_pnl(prices):,.2f}[/]")
    console.print(f"Total market value:   [bold]${pf.total_value(prices):,.2f}[/]")


@app.command()
def summary(
    csv: Path = typer.Argument(..., help="Path to a transactions CSV."),
    method: CostBasisMethod = typer.Option(
        CostBasisMethod.AVERAGE, "--method", "-m", help="Cost-basis method."
    ),
    price: list[str] = typer.Option(
        [], "--price", "-p", help="Mark price as ASSET=PRICE (repeatable)."
    ),
) -> None:
    """Import a CSV ledger and print holdings + realized/unrealized PnL."""
    pf = _load(csv, method)
    prices = _parse_prices(price)

    table = Table(title=f"Summary ({method.value})", header_style="bold cyan")
    table.add_column("Asset")
    table.add_column("Qty", justify="right")
    table.add_column("Avg cost", justify="right")
    table.add_column("Cost basis", justify="right")
    table.add_column("Realized PnL", justify="right")
    for asset in sorted(pf.holdings()):
        pos = pf.position(asset)
        table.add_row(
            asset,
            f"{pos.quantity:,.6f}",
            f"${pos.avg_cost:,.2f}",
            f"${pos.cost_basis:,.2f}",
            f"${pos.realized_pnl:,.2f}",
        )
    console.print(table)
    console.print(f"Total realized PnL:   [bold green]${pf.realized_pnl():,.2f}[/]")
    if prices:
        console.print(f"Total unrealized PnL: [bold green]${pf.unrealized_pnl(prices):,.2f}[/]")
        console.print(f"Total market value:   [bold]${pf.total_value(prices):,.2f}[/]")


@app.command()
def taxlots(
    csv: Path = typer.Argument(..., help="Path to a transactions CSV."),
    method: CostBasisMethod = typer.Option(
        CostBasisMethod.FIFO, "--method", "-m", help="Cost-basis method."
    ),
) -> None:
    """Print a realized tax-lot report (one row per matched disposal)."""
    pf = _load(csv, method)
    report = pf.tax_lot_report()
    if not report:
        console.print("[yellow]No realized disposals.[/]")
        return

    table = Table(title=f"Tax-Lot Report ({method.value})", header_style="bold cyan")
    table.add_column("Asset")
    table.add_column("Qty", justify="right")
    table.add_column("Proceeds", justify="right")
    table.add_column("Cost basis", justify="right")
    table.add_column("Gain/Loss", justify="right")
    table.add_column("Held (days)", justify="right")
    table.add_column("Term")

    total_gain = 0.0
    for sale in report:
        total_gain += sale.gain
        days = sale.holding_days
        term = "" if sale.long_term is None else ("long" if sale.long_term else "short")
        color = "green" if sale.gain >= 0 else "red"
        table.add_row(
            sale.asset,
            f"{sale.quantity:,.6f}",
            f"${sale.proceeds:,.2f}",
            f"${sale.cost_basis:,.2f}",
            f"[{color}]${sale.gain:,.2f}[/]",
            "-" if days is None else str(days),
            term,
        )
    console.print(table)
    console.print(f"Total realized gain/loss: [bold]${total_gain:,.2f}[/]")


@app.command(name="allocation")
def allocation_cmd(
    csv: Path = typer.Argument(..., help="Path to a transactions CSV."),
    price: list[str] = typer.Option(
        [], "--price", "-p", help="Mark price as ASSET=PRICE (repeatable)."
    ),
) -> None:
    """Print the current allocation by market-value weight."""
    pf = _load(csv, CostBasisMethod.AVERAGE)
    prices = _parse_prices(price)
    slices = allocation(pf, prices)
    if not slices:
        console.print("[yellow]Portfolio has no market value.[/]")
        return
    table = Table(title="Allocation", header_style="bold cyan")
    table.add_column("Asset")
    table.add_column("Market value", justify="right")
    table.add_column("Weight", justify="right")
    for s in slices:
        table.add_row(s.asset, f"${s.market_value:,.2f}", f"{s.weight:.1%}")
    console.print(table)


@app.command(name="rebalance")
def rebalance_cmd(
    csv: Path = typer.Argument(..., help="Path to a transactions CSV."),
    target: list[str] = typer.Option(
        ..., "--target", "-t", help="Target weight as ASSET=WEIGHT (repeatable)."
    ),
    price: list[str] = typer.Option(
        [], "--price", "-p", help="Mark price as ASSET=PRICE (repeatable)."
    ),
) -> None:
    """Suggest trades to move the portfolio toward a target allocation."""
    pf = _load(csv, CostBasisMethod.AVERAGE)
    prices = _parse_prices(price)
    targets = _parse_prices(target)
    actions = rebalance(pf, prices, targets)
    if not actions:
        console.print("[green]Already balanced.[/]")
        return
    table = Table(title="Rebalance Suggestions", header_style="bold cyan")
    table.add_column("Asset")
    table.add_column("Action")
    table.add_column("Notional", justify="right")
    table.add_column("Now", justify="right")
    table.add_column("Target", justify="right")
    for a in actions:
        color = "green" if a.side is Side.BUY else "red"
        table.add_row(
            a.asset,
            f"[{color}]{a.side.value.upper()}[/]",
            f"${a.amount:,.2f}",
            f"{a.current_weight:.1%}",
            f"{a.target_weight:.1%}",
        )
    console.print(table)


@app.command(name="performance")
def performance_cmd(
    values: list[float] = typer.Argument(
        ..., help="Equity curve values in chronological order (>= 2)."
    ),
) -> None:
    """Compute time-weighted return and max drawdown over an equity curve."""
    snap = performance(values)
    table = Table(title="Performance", header_style="bold cyan")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("Time-weighted return", f"{snap.twr:.2%}")
    table.add_row("Max drawdown", f"{snap.max_drawdown:.2%}")
    table.add_row("Peak value", f"${snap.peak_value:,.2f}")
    table.add_row("Trough value", f"${snap.trough_value:,.2f}")
    table.add_row("Start -> End", f"${snap.start_value:,.2f} -> ${snap.end_value:,.2f}")
    console.print(table)


@app.command()
def export_sample(
    out: Path = typer.Argument(..., help="Destination CSV path."),
) -> None:
    """Write a sample transactions CSV you can edit and re-import."""
    from datetime import datetime

    sample = [
        Transaction("BTC", Side.BUY, 1.0, 20_000.0, 10.0, datetime(2024, 1, 1)),
        Transaction("BTC", Side.BUY, 1.0, 30_000.0, 10.0, datetime(2024, 3, 1)),
        Transaction("BTC", Side.SELL, 1.0, 40_000.0, 10.0, datetime(2025, 6, 1)),
        Transaction("ETH", Side.BUY, 10.0, 1_500.0, 5.0, datetime(2024, 2, 1)),
    ]
    out.write_text(dump_transactions(sample), encoding="utf-8")
    console.print(f"Wrote sample ledger to [bold cyan]{out}[/] ({len(sample)} rows).")


if __name__ == "__main__":
    app()
