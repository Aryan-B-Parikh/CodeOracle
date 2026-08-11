from auth import login
from legacy_payment import PaymentProcessor
from utils import transaction_count


def main():
    processor = PaymentProcessor("checkout")
    processor.balance = 5000
    token = login("admin", "s3cret")
    print(token, processor.charge(999, 1, "IN"), transaction_count())


if __name__ == "__main__":
    main()
