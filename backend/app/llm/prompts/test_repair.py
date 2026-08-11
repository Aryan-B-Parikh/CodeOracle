"""Prompt templates for the coverage repair loop (iteration > 1)."""

TEST_REPAIR_SYSTEM = """\
You are improving an existing test suite for legacy code.

The coverage report below is ground truth: it shows lines and branches not yet
executed. Target is >60% line coverage. Do not modify the source. Do not weaken
or duplicate existing tests.
"""

TEST_REPAIR_USER = """\
CURRENT COVERAGE: line={line_coverage}% branch={branch_coverage}%

UNCOVERED LINES:
{uncovered}

TARGET FUNCTION FACTS:
{functions}

EXISTING TESTS:
{existing_tests}

Generate additional tests that target exactly the uncovered lines/branches
listed above. Output only runnable test code.
"""
