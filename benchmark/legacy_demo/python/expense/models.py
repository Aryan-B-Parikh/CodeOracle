from dataclasses import dataclass


@dataclass
class Expense:
    category: str
    amount: float
    note: str = ""

    def is_valid(self) -> bool:
        return self.amount > 0 and bool(self.category.strip())

    def to_dict(self) -> dict:
        return {"category": self.category, "amount": self.amount, "note": self.note}
