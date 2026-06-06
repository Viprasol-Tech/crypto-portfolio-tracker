"""Smoke tests for the Typer CLI."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from crypto_portfolio_tracker import __version__
from crypto_portfolio_tracker.cli import app

runner = CliRunner()


def test_version_command() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_demo_command_runs() -> None:
    result = runner.invoke(app, ["demo"])
    assert result.exit_code == 0
    assert "Portfolio Summary" in result.stdout


def test_export_then_summary_and_taxlots(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.csv"
    export = runner.invoke(app, ["export-sample", str(ledger)])
    assert export.exit_code == 0
    assert ledger.exists()

    summary = runner.invoke(
        app, ["summary", str(ledger), "--method", "fifo", "--price", "BTC=45000"]
    )
    assert summary.exit_code == 0
    assert "Summary" in summary.stdout

    taxlots = runner.invoke(app, ["taxlots", str(ledger), "--method", "fifo"])
    assert taxlots.exit_code == 0
    assert "Tax-Lot Report" in taxlots.stdout


def test_allocation_and_rebalance(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.csv"
    runner.invoke(app, ["export-sample", str(ledger)])

    alloc = runner.invoke(app, ["allocation", str(ledger), "-p", "BTC=45000", "-p", "ETH=2000"])
    assert alloc.exit_code == 0
    assert "Allocation" in alloc.stdout

    reb = runner.invoke(
        app,
        [
            "rebalance",
            str(ledger),
            "-t",
            "BTC=0.5",
            "-t",
            "ETH=0.5",
            "-p",
            "BTC=45000",
            "-p",
            "ETH=2000",
        ],
    )
    assert reb.exit_code == 0


def test_performance_command() -> None:
    result = runner.invoke(app, ["performance", "100", "120", "90", "110"])
    assert result.exit_code == 0
    assert "Performance" in result.stdout


def test_bad_price_pair_errors(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.csv"
    runner.invoke(app, ["export-sample", str(ledger)])
    result = runner.invoke(app, ["allocation", str(ledger), "-p", "BTC"])
    assert result.exit_code != 0
