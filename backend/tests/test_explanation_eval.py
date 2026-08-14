"""Unit tests for the reference-based explanation evaluators.

Prove the benchmark has teeth: a generic placeholder explanation must score
low while a factual explanation that states the ground-truth facts must score
high — under both independent evaluators.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.schemas.explanation import ExplanationFields
from app.services.explanation_eval import evaluate_a, evaluate_b, evaluate_pair

FACTS_FILE = Path(__file__).resolve().parent / "fixtures" / "explanation_benchmark_facts.json"


def _facts() -> dict[str, list[str]]:
    raw = json.loads(FACTS_FILE.read_text(encoding="utf-8"))
    return raw["functions"]["process_transaction_1"]


def _generic_explanation() -> ExplanationFields:
    """Placeholder text with no real semantics — must score low."""
    return ExplanationFields(
        purpose="Performs the function logic.",
        inputs="None",
        outputs="Any",
        side_effects="None detected from static analysis.",
        dependencies="None (leaf function)",
        control_flow="Standard control flow.",
        error_handling="Propagates exceptions.",
        business_rules="Applies business rules.",
        complexity=1,
        risks="Low risk.",
    )


def _factual_explanation() -> ExplanationFields:
    """States every ground-truth fact — must score high under both evaluators."""
    return ExplanationFields(
        purpose="Calculate net transaction value for transaction model 1.",
        inputs="amount, fee_rate",
        outputs="round(net, 2)",
        side_effects="fee = amount * fee_rate; net = amount - fee",
        dependencies="None (leaf function)",
        control_flow="if amount <= 0.0",
        error_handling="raises ValueError; triggered when amount <= 0.0",
        business_rules="fee = amount * fee_rate; net = amount - fee",
        complexity=2,
        risks="Behavior inferred from static analysis; verify against runtime semantics.",
    )


def test_generic_explanation_scores_low_under_both_evaluators() -> None:
    a = evaluate_a(_generic_explanation(), _facts())
    b = evaluate_b(_generic_explanation(), _facts())
    assert a.overall < 3.0, f"Evaluator A gave {a.overall} to a placeholder explanation"
    assert b.overall < 3.0, f"Evaluator B gave {b.overall} to a placeholder explanation"


def test_factual_explanation_scores_high_under_both_evaluators() -> None:
    a = evaluate_a(_factual_explanation(), _facts())
    b = evaluate_b(_factual_explanation(), _facts())
    assert a.overall >= 4.5, f"Evaluator A scored factual explanation {a.overall}"
    assert b.overall >= 4.5, f"Evaluator B scored factual explanation {b.overall}"
    assert a.facts_covered == 6 and b.facts_covered == 6


def test_evaluators_are_independent_and_agree() -> None:
    pair = evaluate_pair(_factual_explanation(), _facts())
    assert pair["evaluatorA"]["name"] != pair["evaluatorB"]["name"]
    assert pair["agreement"]["withinOne"] is True
    assert pair["agreement"]["overallDiff"] <= 1.0


def test_category_matches_are_recorded() -> None:
    a = evaluate_a(_factual_explanation(), _facts())
    assert a.category_notes == {
        "purpose": True,
        "inputs": True,
        "outputs": True,
        "errors": True,
        "rules": True,
        "branches": True,
    }
