"""Customer records.

Has intentional module-level global state (`CUSTOMER_CACHE`) and a
lazy import of `database` to keep every dependency explicit.
"""

CUSTOMER_CACHE: dict[int, dict] = {}


def load_customer(customer_id: int) -> dict:
    from database import find, insert

    cached = CUSTOMER_CACHE.get(customer_id)
    if cached is not None:
        return cached
    record = find("customers", "id", customer_id)
    if record is None:
        record = {"id": customer_id, "tier": "standard", "spend": 0}
        insert("customers", record)
    CUSTOMER_CACHE[customer_id] = record
    return record


def is_vip(customer: dict) -> bool:
    return customer.get("tier") == "vip" or customer.get("spend", 0) >= 10000
