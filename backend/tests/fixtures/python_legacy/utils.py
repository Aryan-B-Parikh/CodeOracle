"""Legacy utilities.

`legacy_calc` mirrors the classic magic-number example (threshold 100,
rate 0.1). `transaction_count` lazily imports `legacy_payment`, creating
a legacy_payment <-> utils import cycle that stays runnable.
"""


def parse_amount(s):
    x = 0
    for c in s:
        if c.isdigit():
            x = x * 10 + int(c)
    return x


def legacy_calc(a, b, c):
    if a > 100:
        r = a * 0.1
    else:
        r = 0
    return a + b + c - r


def normalize(s):
    s = s.strip().lower()
    while "  " in s:
        s = s.replace("  ", " ")
    return s


def transaction_count():
    from legacy_payment import TRANSACTIONS

    return len(TRANSACTIONS)
