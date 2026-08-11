from collections import OrderedDict


def by_category(expenses: list[dict]) -> dict:
    out: OrderedDict[str, float] = OrderedDict()
    for e in expenses:
        out[e["category"]] = out.get(e["category"], 0.0) + e["amount"]
    return dict(out)


def top_categories(expenses: list[dict], n: int = 3) -> list[tuple[str, float]]:
    rows = sorted(by_category(expenses).items(), key=lambda kv: kv[1], reverse=True)
    return rows[:n]


def summary_line(expenses: list[dict], cap: float) -> str:
    spent = sum(e["amount"] for e in expenses)
    pct = (spent / cap * 100.0) if cap > 0 else 0.0
    return f"spent={spent:.2f} pct={pct:.1f}"
