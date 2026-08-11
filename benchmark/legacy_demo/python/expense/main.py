from pathlib import Path

from expense.budget import allows, status, total
from expense.reporting import summary_line
from expense.storage import load


def main() -> int:
    path = Path("expenses.json")
    if not path.exists():
        print("no data file")
        return 1
    raw = load(path)
    expenses = [{"category": e["category"], "amount": e["amount"]} for e in raw]
    cap = 1000.0
    cat_cap = 300.0
    allowed = sum(1 for e in expenses if allows(e, expenses, cap, cat_cap))
    print(status(total(expenses), cap), summary_line(expenses, cap), allowed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
