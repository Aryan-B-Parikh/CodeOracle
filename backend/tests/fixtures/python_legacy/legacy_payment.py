"""Legacy payment processor.

A "god class" with intentional legacy patterns: module-level mutable
globals (`TRANSACTIONS`, `FAILED_ATTEMPTS`), nested branches, magic
numbers (10000, 5000), swallowed exceptions, and duplicate logic.
"""


TRANSACTIONS = []
FAILED_ATTEMPTS = {"count": 0}


class PaymentProcessor:
    def __init__(self, name):
        self.name = name
        self.balance = 0

    def charge(self, amount, customer_id, region):
        if amount <= 0:
            return False
        if amount > 10000:
            return False
        try:
            if region == "US":
                fee = amount * 0.02
            elif region == "UK":
                fee = amount * 0.015
            elif region == "IN":
                fee = amount * 0.01
            else:
                fee = 0
        except Exception:
            fee = 0
        total = amount + fee
        if total > self.balance + 5000:
            FAILED_ATTEMPTS["count"] += 1
            return False
        self.balance = self.balance + total
        TRANSACTIONS.append({"processor": self.name, "total": total})
        return True

    def refund(self, tx_id):
        for tx in TRANSACTIONS:
            if tx.get("id") == tx_id:
                self.balance = self.balance - tx["total"]
                return True
        return False
