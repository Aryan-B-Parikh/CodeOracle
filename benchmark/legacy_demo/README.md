# Benchmark — legacy_demo

The single, repeatable judging demo. Upload this repo, run the pipeline, and
the coverage loop must take line coverage from a low baseline to **> 60%**.

## Coverage contract (the acceptance gate)

| Metric | Value |
|---|---|
| Baseline coverage (seed suite, committed) | ~40–50% (measured 45.7% with pytest + coverage.py) |
| Target | **> 60%** line coverage |
| Maximum repair iterations | 3 |
| Expected final | **> 60%** (measured 94.3%) |

The repo ships with a deliberately *partial* seed suite (`python/tests/`) so the
baseline is low and the Test → Coverage → Repair loop has clear headroom. The
seed suite is the baseline fixture; the benchmark's three repair additions are
not committed — they are written to `tests/test_generated_repair.py` by the
benchmark run and cleaned up afterwards.

## Contents

```
legacy_demo/
├── python/     mini expense-tracker package (~5 modules, no tests)
└── java/       mini expense-tracking Maven project (no tests)
```

Both halves share the same domain (expenses, budgets, reports) so one demo
narrative works for either language.

## Ready-made upload zips

For manual testing, pre-built zips live next to this README:

```
legacy_demo/
├── legacy_demo_python.zip   # python/ (expense package + seed suite)
└── legacy_demo_java.zip     # java/expenses Maven project
```

Upload either zip in the UI (or `POST /api/v1/repositories/upload`) without
having to zip anything yourself.

## How to run the benchmark

1. Upload `benchmark/legacy_demo/python` (or `.../java`) via ZIP or import.
2. Run analysis → confirm graph + explanations render.
3. Trigger test generation. Record baseline coverage (expect ~30–40%).
4. Run up to 3 repair iterations. Record each iteration's line/branch coverage.
5. PASS if line coverage `> 60%` within 3 iterations.

## Repeatability

- Deterministic input (committed files, no timestamps/secrets).
- Expected final coverage is stated above; if a pipeline change drops the
  benchmark below target, the change is a regression — fix it, don't relax the
  target.
