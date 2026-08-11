"""Reporting helpers.

`legacy_summary` is intentionally written in legacy style: single-letter
variables, no types, and a magic threshold of 100.
"""


def monthly_summary(invoices: list[dict]) -> dict:
    revenue = 0.0
    for inv in invoices:
        revenue += inv["total"]
    return {"revenue": round(revenue, 2), "count": len(invoices)}


def legacy_summary(rows):
    t = 0
    for r in rows:
        x = r.get("total", 0)
        if x > 100:
            x = x * 0.9
        t = t + x
    return t
