# Benchmark — legacy_demo

The single, repeatable judging demo. Upload this repo, run the pipeline, and
the coverage loop must take line coverage from a low baseline to **> 60%**.

## Coverage contract (the acceptance gate)

| Metric | Value |
|---|---|
| Baseline coverage (first generation pass) | ~30–40% |
| Target | **> 60%** line coverage |
| Maximum repair iterations | 3 |
| Expected final | **> 60%** |

The repo intentionally ships **without committed tests** so the baseline is low
and the Test → Coverage → Repair loop has clear headroom. Do not add committed
tests here — that would defeat the demo.

## Contents

```
legacy_demo/
├── python/     mini expense-tracker package (~5 modules, no tests)
└── java/       mini expense-tracking Maven project (no tests)
```

Both halves share the same domain (expenses, budgets, reports) so one demo
narrative works for either language.

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
