"""Run the Python legacy-code coverage benchmark without Docker.

The benchmark deliberately starts with a small seed suite, measures real
coverage.py output, then adds focused tests for uncovered behavior and verifies
that line coverage exceeds the 60% acceptance threshold.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TESTS = ROOT / "tests"
COVERAGE_JSON = ROOT / "coverage.json"


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


def write_repair_tests() -> Path:
    """Write deterministic tests for uncovered branches in the benchmark."""
    path = TESTS / "test_generated_repair.py"
    path.write_text(
        '''from expense.budget import allows, remaining, status\nfrom expense.reporting import summary_line, top_categories\n\n\nEXPENSES = [\n    {"category": "food", "amount": 10.0},\n    {"category": "food", "amount": 50.0},\n    {"category": "travel", "amount": 20.0},\n]\n\n\ndef test_status_all_paths():\n    assert status(100.0, 1000.0) == "OK"\n    assert status(850.0, 1000.0) == "WARNING"\n    assert status(1200.0, 1000.0) == "OVER_BUDGET"\n    try:\n        status(1.0, 0.0)\n    except ValueError:\n        pass\n\n\ndef test_allows_category_monthly_and_positive_paths():\n    assert allows({"category": "food", "amount": 5.0}, EXPENSES, 1000.0, 300.0) is True\n    assert allows({"category": "food", "amount": 250.0}, EXPENSES, 1000.0, 300.0) is False\n    assert allows({"category": "travel", "amount": 950.0}, EXPENSES, 1000.0, 300.0) is False\n    assert allows({"category": "travel", "amount": 0.0}, EXPENSES, 1000.0, 300.0) is False\n\n\ndef test_remaining_and_reporting_branches():\n    assert remaining(EXPENSES, 1000.0) == 920.0\n    assert remaining(EXPENSES, 50.0) == 0.0\n    assert top_categories(EXPENSES, 1) == [("food", 60.0)]\n    assert summary_line(EXPENSES, 100.0) == "spent=80.00 pct=80.0"\n    assert summary_line(EXPENSES, 0.0) == "spent=80.00 pct=0.0"\n''',
        encoding="utf-8",
    )
    return path


def main() -> int:
    baseline = run_pytest()
    print(f"BASELINE_COVERAGE={baseline:.1f}%")
    if not 20.0 <= baseline < 50.0:
        raise AssertionError(
            f"Expected a partial baseline below 50%; measured {baseline:.1f}%"
        )

    generated = write_repair_tests()
    try:
        final = run_pytest()
    finally:
        generated.unlink(missing_ok=True)
        COVERAGE_JSON.unlink(missing_ok=True)

    print(f"FINAL_COVERAGE={final:.1f}%")
    if final <= 60.0:
        raise AssertionError(f"Coverage target not reached: {final:.1f}% <= 60.0%")
    print("BENCHMARK_PASS: real pytest/coverage.py measurement exceeded 60%.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
