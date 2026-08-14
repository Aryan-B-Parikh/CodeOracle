"""Reference-based explanation evaluation (pure, deterministic).

Ground truth facts -> CodeOracle explanation -> evaluator -> score -> evidence.

Two INDEPENDENT evaluators score the same explanation with different rubrics:

- Evaluator A ("semantic-token"): token-overlap scoring. Each fact category
  is satisfied when a required fraction of the ground-truth semantic tokens
  appears in the corresponding explanation field (prefix-tolerant, stopwords
  removed). Clarity A is a structural rubric (fields present, no placeholders,
  sane lengths).
- Evaluator B ("anchor-pattern"): anchor-term scoring. Each category is
  satisfied when any of a small set of canonical anchors (exception names,
  operators, formula names, numeric literals) appears in the field. Clarity B
  is a specificity rubric (concrete formulas, exception names, numbers,
  citations).

Both are fixed rubrics producing structured JSON. Their agreement is reported
so judges can see how much the score depends on the evaluation strategy.

The deterministic evidence validator (explanation.py::validate_evidence_items)
remains the grounding gate — evaluation never replaces it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.schemas.explanation import ExplanationFields

STOPWORDS = frozenset(
    {
        "a", "an", "the", "after", "before", "for", "to", "of", "on", "with",
        "and", "or", "at", "by", "from", "in", "when", "then", "as", "is",
        "are", "be", "this", "that", "per", "value", "model",
    }
)

_PLACEHOLDER_MARKERS = (
    "none detected",
    "standard control flow",
    "see evidence",
    "per source lines",
    "low risk",
    "propagates exceptions to the caller",
    "relies on callee error semantics",
)

_FACT_NAMES = ("purpose", "inputs", "outputs", "errors", "rules", "branches")


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9<=._]+", " ", text.lower()).strip()


def _tokens(text: str) -> set[str]:
    return set(_normalize(text).split())


def _prefix_matches(token: str, words: set[str]) -> bool:
    if len(token) <= 4:
        return token in words
    root = token[:4]
    return token in words or any(w.startswith(root) for w in words)


def _category_tokens(facts: dict[str, list[str]], category: str) -> set[str]:
    items = facts.get(category, [])
    if isinstance(items, str):
        items = [items]
    raw = set()
    for item in items:
        raw |= _tokens(str(item))
    return raw - STOPWORDS


def _cover_ratio(expected: set[str], text: str) -> float:
    if not expected:
        return 1.0
    words = _tokens(text)
    matched = sum(1 for t in expected if _prefix_matches(t, words))
    return matched / len(expected)


def _has_any(text: str, anchors: list[str]) -> bool:
    normalized = _normalize(text)
    return any(a in normalized for a in anchors)


class _Anchors:
    """Independent anchor sets (Evaluator B) per fact category."""

    PURPOSE = ["transaction", "net", "fee"]
    INPUTS = ["amount", "fee_rate"]
    OUTPUTS = ["round", "net", "float"]
    ERRORS = ["valueerror", "exception", "raise"]
    RULES = ["fee", "net", "="]
    BRANCHES = ["amount", "<=", "if "]


@dataclass(frozen=True)
class DimensionScores:
    accuracy: float
    completeness: float
    clarity: float
    facts_covered: int = 0
    facts_total: int = 6
    category_notes: dict[str, bool] = field(default_factory=dict)

    @property
    def overall(self) -> float:
        return round((self.accuracy + self.completeness + self.clarity) / 3.0, 2)


_COMPLETENESS_CURVE = {0: 0.0, 1: 0.8, 2: 1.7, 3: 2.5, 4: 3.3, 5: 4.2, 6: 5.0}


def _facts_present(facts: dict[str, list[str]], text_map: dict[str, str]) -> dict[str, bool]:
    """Which of the 6 required facts are covered somewhere in the explanation."""
    present: dict[str, bool] = {}
    for name in _FACT_NAMES:
        text = text_map.get(name, "")
        expected = _category_tokens(facts, name)
        present[name] = _cover_ratio(expected, text) >= 0.5
    return present


def _field_map(explanation: ExplanationFields) -> dict[str, str]:
    return {
        "purpose": explanation.purpose,
        "inputs": explanation.inputs,
        "outputs": explanation.outputs,
        "errors": explanation.error_handling,
        "rules": explanation.business_rules,
        "branches": explanation.control_flow,
    }


def evaluate_a(
    explanation: ExplanationFields, facts: dict[str, list[str]]
) -> DimensionScores:
    """Evaluator A: semantic-token coverage + structural clarity rubric."""
    text_map = _field_map(explanation)
    notes: dict[str, bool] = {}
    matched = 0
    for name in _FACT_NAMES:
        expected = _category_tokens(facts, name)
        ratio = _cover_ratio(expected, text_map[name])
        ok = ratio >= 0.5
        notes[name] = ok
        matched += 1 if ok else 0
    accuracy = round(5.0 * matched / 6.0, 2)

    present = _facts_present(facts, text_map)
    completeness = float(_COMPLETENESS_CURVE[sum(present.values())])

    clarity = 5.0
    lowered = {k: v.lower() for k, v in text_map.items()}
    if not explanation.purpose or not explanation.inputs or not explanation.outputs:
        clarity -= 1.0
    if not explanation.error_handling or not explanation.business_rules:
        clarity -= 1.0
    clarity -= 1.0 * sum(1 for v in lowered.values() if any(m in v for m in _PLACEHOLDER_MARKERS))
    purpose_len = len(explanation.purpose)
    if purpose_len < 15 or purpose_len > 300:
        clarity -= 1.0
    clarity = max(1.0, min(5.0, round(clarity, 1)))

    return DimensionScores(
        accuracy=accuracy,
        completeness=completeness,
        clarity=clarity,
        facts_covered=sum(present.values()),
        category_notes=notes,
    )


def evaluate_b(
    explanation: ExplanationFields, facts: dict[str, list[str]]
) -> DimensionScores:
    """Evaluator B: anchor-pattern matching + specificity clarity rubric."""
    text_map = _field_map(explanation)
    anchors = {
        "purpose": _Anchors.PURPOSE,
        "inputs": _Anchors.INPUTS,
        "outputs": _Anchors.OUTPUTS,
        "errors": _Anchors.ERRORS,
        "rules": _Anchors.RULES,
        "branches": _Anchors.BRANCHES,
    }
    notes: dict[str, bool] = {}
    matched = 0
    for name in _FACT_NAMES:
        ok = _has_any(text_map[name], anchors[name])
        notes[name] = ok
        matched += 1 if ok else 0
    accuracy = round(5.0 * matched / 6.0, 2)

    present = _facts_present(facts, text_map)
    completeness = float(_COMPLETENESS_CURVE[sum(present.values())])

    clarity = 3.0
    if _has_any(explanation.business_rules, ["="]):
        clarity += 1.0
    if _has_any(explanation.error_handling, ["valueerror", "exception"]):
        clarity += 1.0
    if _has_any(explanation.outputs, ["round", "2", "net"]):
        clarity += 0.5
    clarity = max(1.0, min(5.0, round(clarity, 1)))

    return DimensionScores(
        accuracy=accuracy,
        completeness=completeness,
        clarity=clarity,
        facts_covered=sum(present.values()),
        category_notes=notes,
    )


def evaluate_pair(
    explanation: ExplanationFields, facts: dict[str, list[str]]
) -> dict:
    """Run both independent evaluators and return structured results + agreement."""
    a = evaluate_a(explanation, facts)
    b = evaluate_b(explanation, facts)
    overall_diff = abs(a.overall - b.overall)
    dimension_diffs = {
        dim: abs(getattr(a, dim) - getattr(b, dim))
        for dim in ("accuracy", "completeness", "clarity")
    }
    return {
        "evaluatorA": {
            "name": "semantic-token-v1",
            "accuracy": a.accuracy,
            "completeness": a.completeness,
            "clarity": a.clarity,
            "overall": a.overall,
            "factsCovered": a.facts_covered,
            "categoryMatch": a.category_notes,
        },
        "evaluatorB": {
            "name": "anchor-pattern-v1",
            "accuracy": b.accuracy,
            "completeness": b.completeness,
            "clarity": b.clarity,
            "overall": b.overall,
            "factsCovered": b.facts_covered,
            "categoryMatch": b.category_notes,
        },
        "agreement": {
            "overallDiff": round(overall_diff, 2),
            "withinOne": overall_diff <= 1.0,
            "dimensionDiffs": {
                dim: round(diff, 2) for dim, diff in dimension_diffs.items()
            },
        },
    }
