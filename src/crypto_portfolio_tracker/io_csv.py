"""CSV import/export for transactions.

The CSV schema is a stable, human-friendly columnar format::

    timestamp,asset,side,quantity,price,fee

``timestamp`` is ISO-8601 (e.g. ``2024-01-15T00:00:00``) and may be blank.
``side`` is ``buy`` or ``sell`` (case-insensitive). ``fee`` is optional and
defaults to ``0``.

Functions here are pure with respect to I/O boundaries: parsing works on any
iterable of lines / file-like object, so they are easy to unit test without
touching the filesystem.

Part of Crypto Portfolio Tracker by Viprasol Tech Private Limited (https://viprasol.com).
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

from crypto_portfolio_tracker.models import Side, Transaction

FIELDNAMES = ["timestamp", "asset", "side", "quantity", "price", "fee"]


def _parse_timestamp(raw: str) -> datetime | None:
    raw = raw.strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(f"invalid ISO-8601 timestamp: {raw!r}") from exc


def parse_transactions(lines: Iterable[str]) -> list[Transaction]:
    """Parse CSV ``lines`` into a list of :class:`Transaction`.

    Args:
        lines: Any iterable of CSV text lines (including a header row).

    Returns:
        Parsed transactions in file order.

    Raises:
        ValueError: On a missing required column, an unknown ``side``, or a
            malformed number/timestamp.
    """
    reader = csv.DictReader(lines)
    if reader.fieldnames is None:
        return []
    missing = {"asset", "side", "quantity", "price"} - set(reader.fieldnames)
    if missing:
        raise ValueError(f"CSV missing required columns: {sorted(missing)}")

    transactions: list[Transaction] = []
    for row_num, row in enumerate(reader, start=2):
        try:
            side = Side(row["side"].strip().lower())
        except ValueError as exc:
            raise ValueError(f"row {row_num}: invalid side {row['side']!r}") from exc
        try:
            quantity = float(row["quantity"])
            price = float(row["price"])
            fee = float(row["fee"]) if row.get("fee", "").strip() else 0.0
        except ValueError as exc:
            raise ValueError(f"row {row_num}: invalid number ({exc})") from exc
        transactions.append(
            Transaction(
                asset=row["asset"].strip().upper(),
                side=side,
                quantity=quantity,
                price=price,
                fee=fee,
                timestamp=_parse_timestamp(row.get("timestamp", "")),
            )
        )
    return transactions


def load_transactions(path: str | Path) -> list[Transaction]:
    """Read transactions from a CSV file at ``path``.

    Args:
        path: Path to a CSV file with the standard schema.

    Returns:
        Parsed transactions in file order.
    """
    text = Path(path).read_text(encoding="utf-8")
    return parse_transactions(text.splitlines())


def dump_transactions(transactions: Iterable[Transaction]) -> str:
    """Serialize ``transactions`` to a CSV string with a header row.

    Args:
        transactions: Transactions to serialize.

    Returns:
        The CSV document as a string (LF line endings, trailing newline).
    """
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=FIELDNAMES, lineterminator="\n")
    writer.writeheader()
    for txn in transactions:
        writer.writerow(
            {
                "timestamp": txn.timestamp.isoformat() if txn.timestamp else "",
                "asset": txn.asset,
                "side": txn.side.value,
                "quantity": txn.quantity,
                "price": txn.price,
                "fee": txn.fee,
            }
        )
    return buffer.getvalue()


def save_transactions(transactions: Iterable[Transaction], path: str | Path) -> None:
    """Write ``transactions`` to a CSV file at ``path``.

    Args:
        transactions: Transactions to serialize.
        path: Destination file path. Parent directories must already exist.
    """
    Path(path).write_text(dump_transactions(transactions), encoding="utf-8")
