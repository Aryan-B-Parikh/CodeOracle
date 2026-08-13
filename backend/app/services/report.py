"""Executive Report Generator service (T-21).

Compiles repository statistics, architecture layers, risk warnings, test coverage,
and modernization safety scores into a comprehensive Markdown document.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.db.models.repository import Repository
from app.db.models.test_run import TestRun
from app.services.summary import generate_repository_summary

logger = logging.getLogger(__name__)


def generate_executive_report(db: Session, repository: Repository) -> str:
    """Generate a readable Markdown report for a repository."""
    summary_payload = generate_repository_summary(db, repository)
    summary_data = summary_payload.summary

    # Query latest test run if available
    latest_test_run = (
        db.query(TestRun)
        .filter(TestRun.repository_id == repository.id)
        .order_by(TestRun.created_at.desc())
        .first()
    )

    lines: list[str] = [
        f"# Executive Architecture & Safety Report: {repository.name}",
        "",
        f"**Repository ID:** `{repository.id}`  ",
        f"**Source Type:** {repository.source_type.upper()}  ",
        f"**Status:** {repository.status.upper()}  ",
        "",
        "---",
        "",
        "## 1. Repository Overview",
        "",
        "| Metric | Value |",
        "| :--- | :--- |",
        f"| **Lines of Code (LOC)** | {repository.loc:,} |",
        f"| **Total File Count** | {repository.file_count:,} |",
        f"| **Parsed Entities** | {repository.entity_count:,} |",
        "",
        "### Primary Languages",
    ]

    if repository.language_counts:
        for lang, count in repository.language_counts.items():
            lines.append(f"- **{lang.capitalize()}**: {count} file(s)")
    else:
        lines.append("- *No language breakdown recorded*")

    lines.extend([
        "",
        "---",
        "",
        "## 2. Architectural Layer Structure",
        "",
    ])

    if summary_data.architecture:
        for layer in summary_data.architecture:
            lines.append(f"### Layer: {layer.layer}")
            lines.append(f"- **Module Count:** {len(layer.modules)}")
            if layer.modules:
                mod_str = ", ".join(f"`{m}`" for m in layer.modules[:10])
                lines.append(f"- **Key Modules:** {mod_str}")
            lines.append("")
    else:
        lines.append("*No architectural layers identified.*")
        lines.append("")

    lines.extend([
        "---",
        "",
        "## 3. High-Risk & Architectural Warnings",
        "",
    ])

    if summary_data.issues:
        lines.append("| Severity | Kind | Description |")
        lines.append("| :---: | :--- | :--- |")
        for issue in summary_data.issues:
            severity_badge = f"**{issue.severity.upper()}**"
            lines.append(
                f"| {severity_badge} | {issue.kind} | {issue.detail} |"
            )
        lines.append("")
    else:
        lines.append("✓ **No high-risk architectural issues detected.**")
        lines.append("")

    lines.extend([
        "---",
        "",
        "## 4. Test Coverage & Quality Gates",
        "",
    ])

    if latest_test_run:
        status_symbol = "✓ PASSED" if latest_test_run.status == "passed" else "❌ FAILED"
        lines.extend([
            f"**Latest Test Execution Status:** `{status_symbol}`  ",
            f"**Line Coverage:** `{latest_test_run.line_coverage:.1f}%` "
            f"(Target: `{latest_test_run.target:.1f}%`)  ",
            f"**Branch Coverage:** `{latest_test_run.branch_coverage:.1f}%`  ",
            f"**Tests Generated:** {latest_test_run.tests_generated} | "
            f"**Passed:** {latest_test_run.tests_passed} | "
            f"**Failed:** {latest_test_run.tests_failed}",
            "",
        ])
    else:
        lines.extend([
            "*No automated test suite runs recorded for this repository yet.*",
            "",
        ])

    lines.extend([
        "---",
        "",
        "## 5. High-Risk Code Entities",
        "",
    ])

    if summary_payload.high_risk_entities:
        lines.append("| Entity | Path | Complexity (CCN) | Fan-In |")
        lines.append("| :--- | :--- | :---: | :---: |")
        for hre in summary_payload.high_risk_entities[:10]:
            lines.append(
                f"| `{hre.name}` | `{hre.file}` | {hre.complexity} | "
                f"{hre.callers} |"
            )
        lines.append("")
    else:
        lines.append("✓ **No high-risk code entities flagged.**")
        lines.append("")

    lines.extend([
        "---",
        "",
        "*Report generated automatically by CodeOracle Engine.*",
    ])

    return "\n".join(lines)
