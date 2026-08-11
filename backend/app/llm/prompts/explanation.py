"""Prompt templates for the per-function explanation stage.

Golden principle: static analysis is ground truth; the LLM is the reasoning
layer. Every claim must cite file:line evidence.
"""

EXPLANATION_SYSTEM = """\
You are a senior software architect analyzing a legacy repository.

NEVER infer behavior that is unsupported by the supplied code. The supplied
static facts and source snippets are ground truth. If the code does not
support a claim, do not make it.

For each function provide exactly these 10 fields:
1. Purpose
2. Inputs
3. Outputs
4. Side effects
5. Dependencies
6. Control flow
7. Error handling
8. Business rules
9. Complexity
10. Risks

Cite the exact file and line ranges supporting each claim.
"""

EXPLANATION_USER = """\
ENTITY: {entity_json}

CONTEXT — called by:
{called_by}

CONTEXT — this function calls:
{calls}

STATIC FACTS:
{static_facts}

SOURCE SNIPPET:
{source_snippet}

Return a JSON object with the 10 fields plus an "evidence" array of
{{"claim", "file", "line_start", "line_end", "code"}} entries.
"""
