# Golden Fixtures

Deterministic, committed sample repositories used to prove CodeOracle's parsers,
graph builder, test loop, and refactor/safety engine. **Keep them small and
stable** — tests assert golden outputs against them.

## Layout

```
python_basic/    clean-ish Python app   (billing system)
python_legacy/   messy legacy Python    (payment processor, auth, utils)
java_basic/      clean-ish Java Maven   (billing system)
java_legacy/     messy legacy Java      (payment service, audit log)
```

## Intentional features (per fixture)

| Feature | python_basic | python_legacy | java_basic | java_legacy |
|---|---|---|---|---|
| functions/methods | yes | yes | yes | yes |
| classes | no | god class `PaymentProcessor` | yes | yes |
| imports | yes (module + lazy) | yes (module + lazy) | yes | yes |
| cross-module calls | yes | yes | yes | yes |
| circular dependency | billing ↔ database (lazy import) | legacy_payment ↔ utils (lazy import) | — | PaymentService ↔ AuditLog |
| high complexity | `calculate_invoice` | `charge` | `Invoice.discount`+`total` | `charge` |
| exceptions | `DatabaseError`, `UnknownRegionError`, `InvoiceError` | swallowed `except Exception` | `IllegalArgumentException` | swallowed `catch (Exception)` |
| branches | tax/discount/subtotal | nested region branches | tax/discount | nested region branches |
| global state | `_connection`, `CUSTOMER_CACHE` | `TRANSACTIONS`, `FAILED_ATTEMPTS`, `SESSIONS` | static `TABLES`, `connected` | static `TRANSACTIONS`, `failedAttempts` |
| legacy patterns | magic numbers, `legacy_summary` | single-letter vars, magic numbers, `System.out.println`-style prints | magic numbers | `System.out.println`, catch-all, magic numbers |
| refactor candidates | `apply_discount`, `legacy_summary` | `legacy_calc`, `charge` | `discount` | `legacyCalc`, `charge` |
| test candidates | `tax.calculate_tax` etc. | `utils.parse_amount` | `TaxCalculator` | `Utils.legacyCalc` |
| committed tests | `tests/test_billing.py` | none (coverage starts low) | `TaxCalculatorTest` | none (coverage starts low) |

## Usage rules

- Golden fixtures are committed and read-only for test purposes.
- Never add dependencies, secrets, or large files to a fixture.
- To add a feature case, extend an existing fixture or add a new one; update this
  table and re-record golden outputs.
