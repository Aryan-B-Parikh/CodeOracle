"""Budget logic — the high-complexity module of the Python benchmark.

Nested branches, multiple conditions per branch, and a custom exception
give the test generator plenty of uncovered paths to target.
"""


class BudgetError(ValueError):
    pass


def category_total(expenses: list[dict], category: str) -> float:
    return sum(e["amount"] for e in expenses if e["category"] == category)


def total(expenses: list[dict]) -> float:
    return sum(e["amount"] for e in expenses)


def status(spent: float, cap: float) -> str:
    if cap <= 0:
        raise BudgetError("cap must be positive")
    if spent > cap:
        return "OVER_BUDGET"
    if spent > cap * 0.8:
        return "WARNING"
    return "OK"


def allows(expense: dict, expenses: list[dict], monthly_cap: float, category_cap: float) -> bool:
    if category_total(expenses, expense["category"]) + expense["amount"] > category_cap:
        return False
    if total(expenses) + expense["amount"] > monthly_cap:
        return False
    return expense["amount"] > 0


def remaining(expenses: list[dict], cap: float) -> float:
    return max(0.0, cap - total(expenses))
