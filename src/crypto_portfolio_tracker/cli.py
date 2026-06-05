"""Command-line interface for Crypto Portfolio Tracker.

``crypto-portfolio-tracker demo`` records a few sample transactions and prints a
PnL summary (holdings, cost basis, realized and unrealized PnL) — all in memory,
no accounts or API keys.

Part of Crypto Portfolio Tracker by Viprasol Tech Private Limited (https://viprasol.com).
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from crypto_portfolio_tracker import __version__
from crypto_portfolio_tracker.portfolio import Portfolio

app = typer.Typer(add_completion=False, help="Crypto Portfolio Tracker — by Viprasol Tech.")
console = Console()


@app.command()
def version() -> None:
    """Print the installed version."""
    console.print(f"crypto-portfolio-tracker [bold cyan]{__version__}[/] - by Viprasol Tech")


@app.command()
def demo() -> None:
    """Record sample transactions and print a portfolio PnL summary."""
    pf = Portfolio()

    # Two BTC buys at different prices -> average cost basis of 25,000.
    pf.buy("BTC", 1.0, 20_000.0)
    pf.buy("BTC", 1.0, 30_000.0)
    # Partial sell of 1 BTC at 40,000 -> realized PnL of 15,000.
    realized = pf.sell("BTC", 1.0, 40_000.0)
    # An ETH buy we will mark to market.
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


if __name__ == "__main__":
    app()
