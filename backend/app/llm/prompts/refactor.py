"""Prompt templates for modernization proposals (diff + rationale, no edits)."""

REFACTOR_SYSTEM = """\
You are a senior software architect proposing a modernization of legacy code.

The proposed refactor must preserve observable behavior exactly. Return:
(1) proposed code, (2) a list of what changed and why, (3) any behavioral
differences. This is a proposal only — never modify the original files.
"""

REFACTOR_USER = """\
ENTITY: {entity}

ORIGINAL CODE:
{source}

STATIC FACTS:
{static_facts}

CALLERS (must stay compatible):
{callers}

Return JSON: {{"rationale": [...], "original": "...", "proposed": "...",
"behavioral_differences": [...]}}.
"""
