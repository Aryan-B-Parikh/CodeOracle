import database
from billing import calculate_invoice
from reports import monthly_summary


def main() -> None:
    database.connect("memory://demo")
    items = [
        {"price": 250.0, "quantity": 4},
        {"price": 120.0, "quantity": 2},
    ]
    invoice = calculate_invoice(1, items, "IN")
    print(monthly_summary([invoice]))


if __name__ == "__main__":
    main()
