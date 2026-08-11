"""Prompt templates for breaking-change detection between original and refactored APIs."""

BREAKING_CHANGE_SYSTEM = """\
You detect breaking changes between an original and a refactored API.

Compare function signatures, return types, raised exceptions, and side
effects. Classify impact as HIGH, MEDIUM, or LOW. List every affected caller
as file:line. Base all judgments on the static facts provided.
"""

BREAKING_CHANGE_USER = """\
ENTITY: {entity}

ORIGINAL CODE:
{original_code}

PROPOSED CODE:
{proposed_code}

CALLERS (static facts):
{callers}

Return JSON: {{"breaking_changes": [{{"entity", "impact", "reason",
"affected_callers": ["file:line"]}}]}}.
"""
