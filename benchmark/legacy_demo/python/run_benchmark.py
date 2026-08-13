"""Run the Python legacy-code coverage benchmark (demo-repo sanity check).

Measures, with real pytest + coverage.py output, that the committed seed suite
starts at a low baseline and that three focused repair test additions take the
demo repo's line coverage above the 60% acceptance threshold.

This verifies the demo repo's coverage contract (baseline low -> >60%). The
CodeOracle pipeline's own repair loop (LLM generation + sandbox execution +
iteration) is exercised by backend/tests/test_repair.py and the CI Docker job.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TESTS = ROOT / "tests"
COVERAGE_JSON = ROOT / "coverage.json"
REPAIR_TEST = TESTS / "test_generated_repair.py"


def run_pytest() -> float:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        str(TESTS),
        "--cov=expense.budget",
        "--cov=expense.reporting",
        "--cov-report=json:" + str(COVERAGE_JSON),
        "--cov-report=term-missing",
        "-q",
    ]
    result = subprocess.run(cmd, cwd=ROOT, check=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)
    payload = json.loads(COVERAGE_JSON.read_text(encoding="utf-8"))
    return float(payload["totals"]["percent_covered"])


REPAIR_ITERATIONS = [
    '''from expense.budget import status\n\n\ndef test_status_branches():\n    assert status(100.0, 1000.0) == "OK"\n    assert status(850.0, 1000.0) == "WARNING"\n    assert status(1200.0, 1000.0) == "OVER_BUDGET"\n''',
    '''from expense.budget import allows, remaining\n\n\nEXPENSES = [\n    {"category": "food", "amount": 10.0},\n    {"category": "food", "amount": 50.0},\n    {"category": "travel", "amount": 20.0},\n]\n\n\ndef test_allows_paths():\n    assert allows({"category": "food", "amount": 5.0}, EXPENSES, 1000.0, 300.0) is True\n    assert allows({"category": "food", "amount": 250.0}, EXPENSES, 1000.0, 300.0) is False\n    assert allows({"category": "travel", "amount": 950.0}, EXPENSES, 1000.0, 300.0) is False\n    assert allows({"category": "travel", "amount": 0.0}, EXPENSES, 1000.0, 300.0) is False\n\n\ndef test_remaining_paths():\n    assert remaining(EXPENSES, 1000.0) == 920.0\n    assert remaining(EXPENSES, 50.0) == 0.0\n''',
    '''from expense.reporting import summary_line, top_categories\n\n\nEXPENSES = [\n    {"category": "food", "amount": 10.0},\n    {"category": "food", "amount": 50.0},\n    {"category": "travel", "amount": 20.0},\n]\n\n\ndef test_reporting_branches():\n    assert top_categories(EXPENSES, 1) == [("food", 60.0)]\n    assert summary_line(EXPENSES, 100.0) == "spent=80.00 pct=80.0"\n    assert summary_line(EXPENSES, 0.0) == "spent=80.00 pct=0.0"\n''',
]


def main() -> int:
    baseline = run_pytest()
    print(f"BASELINE_COVERAGE={baseline:.1f}%")
    if not 25.0 <= baseline < 55.0:
        raise AssertionError(
            f"Expected a partial baseline between 25-55%; measured {baseline:.1f}%"
        )

    try:
        for iteration, test_code in enumerate(REPAIR_ITERATIONS, start=1):
            mode = "w" if iteration == 1 else "a"
            with REPAIR_TEST.open(mode, encoding="utf-8") as handle:
                handle.write("\n" + test_code)
            coverage = run_pytest()
            print(f"REPAIR_ITERATION_{iteration}_COVERAGE={coverage:.1f}%")

        final = run_pytest()
    finally:
        REPAIR_TEST.unlink(missing_ok=True)
        COVERAGE_JSON.unlink(missing_ok=True)

    print(f"FINAL_COVERAGE={final:.1f}%")
    if final <= 60.0:
        raise AssertionError(f"Coverage target not reached: {final:.1f}% <= 60.0%")
    print("BENCHMARK_PASS: real pytest/coverage.py measurement exceeded 60%.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
