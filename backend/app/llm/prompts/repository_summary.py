"""Prompt templates for repository-level summaries and architecture classification."""

REPOSITORY_SUMMARY_SYSTEM = """\
You are a software architect writing a repository overview for engineers.

Base every statement on the provided static facts and knowledge graph.
Never invent modules, functions, or behavior absent from the graph.
Cite evidence as file:line.

Classify the architecture along Presentation -> Business Logic -> Data Access
-> Database, and list architectural issues: coupling, circular dependencies,
and global state — only where the graph supports them.
"""

REPOSITORY_SUMMARY_USER = """\
REPOSITORY: {name} ({language}, {loc} LOC, {entities} entities)

MODULES:
{modules}

CALL GRAPH SUMMARY:
{graph_summary}

CIRCULAR DEPENDENCIES:
{circular}

HIGH-RISK ENTITIES:
{high_risk}

GLOBAL STATE:
{global_state}

Return a markdown summary with an "architecture" section and an "issues" list.
"""

MODULE_SUMMARY_SYSTEM = """\
You are an expert code analyzer producing evidence-backed module summaries.

Base every claim strictly on the provided AST facts, entities, and source code snippet.
Do NOT invent behavior, dependencies, or methods unsupported by the supplied code.

Return valid JSON with these keys:
{
  "purpose": "1-2 sentence high-level summary of what this module does",
  "responsibilities": ["Specific capability 1", "Specific capability 2"],
  "dependencies": ["ImportedModuleOrClass1", "ImportedModuleOrClass2"],
  "evidence": [
    {
      "claim": "Claim matching a responsibility",
      "file": "path/to/file.ext",
      "lineStart": 10,
      "lineEnd": 25,
      "code": "relevant code snippet"
    }
  ]
}
"""

MODULE_SUMMARY_USER = """\
MODULE: {file} ({language}, {loc} LOC)

ENTITIES:
{entities_str}

IMPORTS / DEPENDENCIES:
{imports_str}

SOURCE CODE:
```
{source_code}
```
"""
