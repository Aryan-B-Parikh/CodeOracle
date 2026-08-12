"""Tests for the repository-source trust boundary used by AI analysis."""

from app.llm.security import UNTRUSTED_SOURCE_POLICY, secure_system_prompt


def test_security_policy_is_present_for_empty_system_prompt() -> None:
    prompt = secure_system_prompt()
    assert prompt == UNTRUSTED_SOURCE_POLICY
    assert "UNTRUSTED DATA" in prompt
    assert "Never follow" in prompt


def test_security_policy_is_prepended_to_application_prompt() -> None:
    prompt = secure_system_prompt("Return evidence-backed JSON only.")
    assert prompt.startswith(UNTRUSTED_SOURCE_POLICY)
    assert prompt.endswith("Return evidence-backed JSON only.")


def test_security_policy_mentions_secret_and_prompt_protection() -> None:
    assert "secrets" in UNTRUSTED_SOURCE_POLICY
    assert "hidden prompts" in UNTRUSTED_SOURCE_POLICY
