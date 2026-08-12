from expense.budget import total
from expense.reporting import by_category


EXPENSES = [
    {"category": "food", "amount": 10.0},
    {"category": "travel", "amount": 20.0},
]


def test_budget_total_happy_path():
    assert total(EXPENSES) == 30.0


def test_reporting_by_category_happy_path():
    assert by_category(EXPENSES) == {"food": 10.0, "travel": 20.0}
