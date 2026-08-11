"""Java parser tests (T-05) — tree-sitter-java extraction + manual CCN."""

from pathlib import Path

from app.analyzers.java_parser import parse_java

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _source(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _parsed(name: str):
    return parse_java(_source(name), name)


def _entity(parsed, name: str, kind: str | None = None):
    return next(
        e for e in parsed.entities if e.name == name and (kind is None or e.kind == kind)
    )


def test_tax_calculator_entities_and_lines() -> None:
    parsed = _parsed(
        "java_basic/src/main/java/com/example/billing/TaxCalculator.java"
    )
    kinds = {(e.name, e.kind) for e in parsed.entities}
    assert ("TaxCalculator", "class") in kinds
    assert ("rateFor", "method") in kinds
    assert ("calculateTax", "method") in kinds
    assert ("round2", "method") in kinds

    cls = _entity(parsed, "TaxCalculator", "class")
    assert cls.line_start == 5
    assert cls.complexity == 2

    rate = _entity(parsed, "rateFor")
    assert rate.parent == "TaxCalculator"
    assert rate.signature == "rateFor(String region) -> double"
    assert rate.arguments == ["region"]
    assert rate.is_public is True


def test_complexity_matches_manual_counts() -> None:
    tax = _parsed("java_basic/src/main/java/com/example/billing/TaxCalculator.java")
    customer = _parsed("java_basic/src/main/java/com/example/billing/Customer.java")
    invoice = _parsed("java_basic/src/main/java/com/example/billing/Invoice.java")
    utils = _parsed("java_legacy/src/main/java/com/example/legacy/Utils.java")
    payment = _parsed("java_legacy/src/main/java/com/example/legacy/PaymentService.java")

    assert _entity(tax, "rateFor").complexity == 2
    assert _entity(tax, "calculateTax").complexity == 2
    assert _entity(tax, "round2").complexity == 1
    assert _entity(customer, "isVip").complexity == 2
    assert _entity(invoice, "subtotal").complexity == 2
    assert _entity(invoice, "discount").complexity == 3
    assert _entity(invoice, "total").complexity == 1
    assert _entity(invoice, "Invoice", "class").complexity == 3

    assert _entity(utils, "legacyCalc").complexity == 2
    assert _entity(utils, "parseAmount").complexity == 3
    assert _entity(payment, "charge").complexity == 8
    assert _entity(payment, "refund").complexity == 3
    assert _entity(payment, "PaymentService", "class").complexity == 8


def test_constructor_is_private_method() -> None:
    parsed = _parsed("java_basic/src/main/java/com/example/billing/TaxCalculator.java")
    ctor = _entity(parsed, "TaxCalculator", "method")
    assert ctor.kind == "method"
    assert ctor.parent == "TaxCalculator"
    assert ctor.is_public is False


def test_calls_resolved_locally() -> None:
    invoice = _parsed("java_basic/src/main/java/com/example/billing/Invoice.java")
    total_calls = {c.name: c.resolved for c in _entity(invoice, "total").calls}
    assert total_calls["discount"] is True
    assert total_calls["TaxCalculator.calculateTax"] is False
    assert total_calls["TaxCalculator.round2"] is False

    tax = _parsed("java_basic/src/main/java/com/example/billing/TaxCalculator.java")
    calc_calls = {c.name: c.resolved for c in _entity(tax, "calculateTax").calls}
    assert calc_calls["round2"] is True
    assert calc_calls["rateFor"] is True


def test_imports_extracted() -> None:
    invoice = _parsed("java_basic/src/main/java/com/example/billing/Invoice.java")
    modules = {i.module for i in invoice.imports}
    assert modules == {"java.util.List", "java.util.Map"}
    assert all(i.line > 0 for i in invoice.imports)


def test_fields_used_as_globals() -> None:
    payment = _parsed("java_legacy/src/main/java/com/example/legacy/PaymentService.java")
    used = _entity(payment, "charge").globals_used
    assert "balance" in used
    assert "TRANSACTIONS" in used
    assert "failedAttempts" in used
