"""In-memory data layer.

Contains intentional module-level global state: a connection singleton
plus a list of every connection ever opened. `resolve_invoice` uses a
lazy (function-level) import of `billing` so the import graph has a
billing <-> database cycle while the code still runs.
"""

from __future__ import annotations

from typing import Any

_connection: dict[str, Any] | None = None
_connections: list[dict[str, Any]] = []


class DatabaseError(Exception):
    pass


def connect(uri: str) -> dict[str, Any]:
    global _connection
    if _connection is not None:
        return _connection
    _connection = {"uri": uri, "tables": {}}
    _connections.append(_connection)
    return _connection


def get_connection() -> dict[str, Any]:
    if _connection is None:
        raise DatabaseError("database not connected")
    return _connection


def insert(table: str, record: dict[str, Any]) -> None:
    get_connection()["tables"].setdefault(table, []).append(record)


def find(table: str, key: str, value: Any) -> dict[str, Any] | None:
    for record in get_connection()["tables"].get(table, []):
        if record.get(key) == value:
            return record
    return None


def fetch_all(table: str) -> list[dict[str, Any]]:
    return list(get_connection()["tables"].get(table, []))


def resolve_invoice(invoice_id: int) -> dict[str, Any]:
    from billing import describe_invoice

    record = find("invoices", "id", invoice_id)
    if record is None:
        raise DatabaseError(f"no invoice with id {invoice_id}")
    return describe_invoice(record)
