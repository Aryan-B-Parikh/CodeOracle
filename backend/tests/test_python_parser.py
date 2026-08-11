"""Python AST analyzer tests (T-04)."""

from pathlib import Path

from app.analyzers.python_parser import ImportRef, parse_python

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _source(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _parsed(name: str):
    return parse_python(_source(name), name)


def _entity(parsed, name: str):
    return next(e for e in parsed.entities if e.name == name)


def test_billing_entities_kinds_and_lines() -> None:
    parsed = _parsed("python_basic/billing.py")
    assert {e.name for e in parsed.entities} == {
        "InvoiceError",
        "apply_discount",
        "calculate_subtotal",
        "describe_invoice",
        "calculate_invoice",
    }

    cls = _entity(parsed, "InvoiceError")
    assert cls.kind == "class"
    assert cls.line_start == 14
    assert cls.line_end == 15

    fn = _entity(parsed, "apply_discount")
    assert fn.kind == "function"
    assert fn.parent is None
    assert fn.line_start == 18
    assert fn.line_end == 23
    assert fn.signature == "apply_discount(subtotal: float, customer_record: dict) -> float"
    assert fn.is_public is True
    assert fn.complexity == 3


def test_signatures_and_return_type() -> None:
    parsed = _parsed("python_basic/billing.py")
    fn = _entity(parsed, "calculate_invoice")
    assert "exempt: bool=False" in fn.signature
    assert "-> dict" in fn.signature
    assert fn.return_type == "dict"
    assert fn.arguments == ["customer_id", "items", "region", "exempt"]


def test_radon_complexity_matches_manual_counts() -> None:
    billing = _parsed("python_basic/billing.py")
    tax = _parsed("python_basic/tax.py")
    reports = _parsed("python_basic/reports.py")
    legacy = _parsed("python_legacy/legacy_payment.py")

    assert _entity(billing, "calculate_invoice").complexity == 1
    assert _entity(billing, "describe_invoice").complexity == 1
    assert _entity(tax, "get_tax_rate").complexity == 2
    assert _entity(tax, "calculate_tax").complexity == 2
    assert _entity(reports, "monthly_summary").complexity == 2
    assert _entity(reports, "legacy_summary").complexity == 3

    proc = _entity(legacy, "PaymentProcessor")
    assert proc.kind == "class"
    assert proc.complexity == 5
    assert _entity(legacy, "__init__").complexity == 1
    assert _entity(legacy, "charge").complexity == 8
    assert _entity(legacy, "refund").complexity == 3


def test_methods_have_parent_class() -> None:
    legacy = _parsed("python_legacy/legacy_payment.py")
    charge = _entity(legacy, "charge")
    assert charge.kind == "method"
    assert charge.parent == "PaymentProcessor"
    assert charge.arguments == ["self", "amount", "customer_id", "region"]
    assert charge.is_public is True
    assert _entity(legacy, "__init__").is_public is False
    assert _entity(legacy, "refund").parent == "PaymentProcessor"


def test_calls_resolved_locally() -> None:
    parsed = _parsed("python_basic/billing.py")
    calls = {c.name: c.resolved for c in _entity(parsed, "calculate_invoice").calls}

    assert calls["calculate_subtotal"] is True
    assert calls["apply_discount"] is True
    assert calls["customer.load_customer"] is False
    assert calls["tax.calculate_tax"] is False
    assert calls["database.fetch_all"] is False
    assert calls["database.insert"] is False
    assert any(c.line == 43 for c in _entity(parsed, "calculate_invoice").calls if c.name == "calculate_subtotal")


def test_module_imports() -> None:
    parsed = _parsed("python_basic/billing.py")
    modules = {i.module for i in parsed.imports}
    assert modules == {"database", "customer", "tax"}


def test_function_level_imports() -> None:
    parsed = _parsed("python_basic/database.py")
    imports = _entity(parsed, "resolve_invoice").imports
    assert ImportRef(module="billing", local_name="describe_invoice", line=52) in imports


def test_globals_used() -> None:
    tax = _parsed("python_basic/tax.py")
    assert _entity(tax, "get_tax_rate").globals_used == ["TAX_RATES", "UnknownRegionError"]

    legacy = _parsed("python_legacy/legacy_payment.py")
    globals_used = _entity(legacy, "charge").globals_used
    assert "TRANSACTIONS" in globals_used
    assert "FAILED_ATTEMPTS" in globals_used


def test_module_calls_at_top_level() -> None:
    parsed = _parsed("python_basic/app.py")
    names = {c.name: c.resolved for c in parsed.module_calls}
    assert names["main"] is True
