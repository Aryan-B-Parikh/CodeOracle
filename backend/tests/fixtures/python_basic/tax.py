"""Region-based tax calculation.

Contains branching (`calculate_tax`), a custom exception
(`UnknownRegionError`), and a module-level rate table.
"""

TAX_RATES = {
    "US": 0.08,
    "UK": 0.20,
    "IN": 0.05,
}


class UnknownRegionError(ValueError):
    pass


def get_tax_rate(region: str) -> float:
    region = region.upper()
    if region in TAX_RATES:
        return TAX_RATES[region]
    raise UnknownRegionError(f"unknown region: {region}")


def calculate_tax(amount: float, region: str, exempt: bool = False) -> float:
    if exempt:
        return 0.0
    rate = get_tax_rate(region)
    return round(amount * rate, 2)
