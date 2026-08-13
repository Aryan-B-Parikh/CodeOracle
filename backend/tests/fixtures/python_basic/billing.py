"""Invoice generation.

Deliberately contains legacy patterns for the fixture: magic numbers
in `apply_discount`, a module-level import of `database` that pairs
with database's lazy import of `billing` (import cycle), and a
high-complexity orchestrator (`calculate_invoice`).
"""

import customer
import database
import tax


class InvoiceError(Exception):
    pass


def apply_discount(subtotal: float, customer_record: dict) -> float:
    if subtotal > 10000:
        return subtotal * 0.10
    if customer_record.get("tier") == "vip":
        return subtotal * 0.05
    return 0.0


def calculate_subtotal(items: list[dict]) -> float:
    total = 0.0
    for item in items:
        total += item["price"] * item["quantity"]
    return total


def describe_invoice(record: dict) -> dict:
    return {
        "id": record["id"],
        "total": record["total"],
        "customer_id": record["customer_id"],
    }


def calculate_invoice(customer_id: int, items: list[dict], region: str, exempt: bool = False) -> dict:
    customer_record = customer.load_customer(customer_id)
    subtotal = calculate_subtotal(items)
    discount = apply_discount(subtotal, customer_record)
    tax_amount = tax.calculate_tax(subtotal - discount, region, exempt)
    total = subtotal - discount + tax_amount
    invoice = {
        "id": len(database.fetch_all("invoices")) + 1,
        "customer_id": customer_id,
        "subtotal": subtotal,
        "discount": discount,
        "tax": tax_amount,
        "total": total,
    }
    database.insert("invoices", invoice)
    return invoice
