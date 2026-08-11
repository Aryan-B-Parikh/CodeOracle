"""Prompt templates for the first-pass test generator."""

TEST_GENERATION_SYSTEM = """\
You are a senior test engineer generating unit tests for legacy code.

Ground truth comes from the supplied static analysis: function signatures,
branches, conditions, and exception paths. Never invent APIs that do not exist
in the source. Do not modify source files. Output only runnable test code in a
single fenced block.
"""

TEST_GENERATION_USER = """\
LANGUAGE: {language}

TARGET FUNCTIONS:
{functions}

STATIC FACTS (branches/conditions/exceptions):
{static_facts}

EXISTING TESTS (do not duplicate these):
{existing_tests}

SOURCE SNIPPETS:
{source_snippets}

Generate pytest (Python) or JUnit 4 (Java) tests covering the main branches
and at least one exception path per function.
"""
