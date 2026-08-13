import pytest
from tax import UnknownRegionError, calculate_tax


def test_tax_us():
    assert calculate_tax(100, "US") == 8.0


def test_tax_exempt_is_zero():
    assert calculate_tax(100, "IN", exempt=True) == 0.0


def test_unknown_region_raises():
    with pytest.raises(UnknownRegionError):
        calculate_tax(100, "XX")
