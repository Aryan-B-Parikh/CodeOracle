"""Prompt templates for the Refactor Safety Score."""

SAFETY_SCORE_SYSTEM = """\
You score a refactor proposal 0-100 based on static facts.

Sub-scores (each 0-100): api_compatibility, test_compatibility,
dependency_impact, behavioral_risk. Derive the total from the sub-scores.
Justify every sub-score against the supplied facts. Output JSON only.
"""

SAFETY_SCORE_USER = """\
ENTITY: {entity}

BREAKING CHANGES: {breaking_changes}

TEST RESULTS: {test_results}

IMPACT ANALYSIS: {impact}

Return JSON: {{"total": 0-100, "api_compatibility": 0-100,
"test_compatibility": 0-100, "dependency_impact": 0-100,
"behavioral_risk": 0-100, "risk_level": "low|medium|high"}}.
"""
