"""Unit tests for provider-agnostic LLM gateway (T-09)."""

import json
from unittest.mock import MagicMock

import httpx
import pytest

from app.config import Settings
from app.llm import (
    AnthropicProvider,
    LLMAuthenticationError,
    LLMError,
    LLMGateway,
    LLMResponse,
    LLMRetryableError,
    MockLLMProvider,
    OpenAIProvider,
    TokenBudgetExceededError,
    estimate_tokens,
    fit_to_budget,
    get_llm_gateway,
)


def test_token_estimation() -> None:
    assert estimate_tokens("") == 0
    assert estimate_tokens("abc") == 1
    assert estimate_tokens("12345678") >= 1


def test_code_token_estimation_density() -> None:
    code_text = "def very_long_function_name(arg_one: int, arg_two: str) -> None:"
    tokens = estimate_tokens(code_text)
    assert tokens >= 12


def test_fit_to_budget_normal() -> None:
    prompt = "Explain this function"
    system = "You are a helpful assistant"
    fitted, truncated = fit_to_budget(prompt, system, budget=1000, reserve_completion_tokens=100)
    assert fitted == prompt
    assert not truncated


def test_fit_to_budget_truncation() -> None:
    system = "System prompt"
    large_prompt = "x" * 4000
    fitted, truncated = fit_to_budget(
        large_prompt, system, budget=500, reserve_completion_tokens=100
    )
    assert truncated
    assert fitted.endswith("... [truncated due to token budget]")
    assert len(fitted) < len(large_prompt)


def test_fit_to_budget_system_exceeds_budget() -> None:
    system = "x" * 2000
    prompt = "Hello"
    with pytest.raises(TokenBudgetExceededError):
        fit_to_budget(prompt, system, budget=200, reserve_completion_tokens=100)


def test_mock_provider_basic() -> None:
    provider = MockLLMProvider(
        model="mock-model",
        default_response="Default mock answer",
        canned_responses=["First answer", "Second answer"],
    )

    resp1 = provider.complete("Prompt 1", system="System 1")
    assert isinstance(resp1, LLMResponse)
    assert resp1.content == "First answer"
    assert resp1.provider == "mock"
    assert resp1.model == "mock-model"
    assert resp1.total_tokens > 0

    resp2 = provider.complete("Prompt 2")
    assert resp2.content == "Second answer"

    resp3 = provider.complete("Prompt 3")
    assert resp3.content == "Default mock answer"

    assert len(provider.history) == 3
    assert provider.history[0]["prompt"] == "Prompt 1"


def test_mock_provider_retry_simulation() -> None:
    provider = MockLLMProvider(fail_attempts=2, default_response="Success after retries")

    # First attempt fails
    with pytest.raises(LLMRetryableError):
        provider.complete("Test prompt")

    # Second attempt fails
    with pytest.raises(LLMRetryableError):
        provider.complete("Test prompt")

    # Third attempt succeeds
    resp = provider.complete("Test prompt")
    assert resp.content == "Success after retries"
    assert provider.attempts_made == 3


def test_llm_gateway_complete_and_budget_integration() -> None:
    mock_provider = MockLLMProvider(default_response="Gateway result")
    gateway = LLMGateway(provider=mock_provider, token_budget=1000, max_tokens=100)

    resp = gateway.complete("Test prompt", system="System message")
    assert resp.content == "Gateway result"
    assert len(mock_provider.history) == 1


def test_llm_gateway_complete_json() -> None:
    canned = [
        '{"status": "ok", "value": 42}',
        'Here is your JSON:\n```json\n{"items": [1, 2, 3]}\n```',
        'Some text before {"result": true} and after',
        "Not a JSON string at all",
    ]
    mock_provider = MockLLMProvider(canned_responses=canned)
    gateway = LLMGateway(provider=mock_provider)

    res1 = gateway.complete_json("Prompt 1")
    assert res1 == {"status": "ok", "value": 42}

    res2 = gateway.complete_json("Prompt 2")
    assert res2 == {"items": [1, 2, 3]}

    res3 = gateway.complete_json("Prompt 3")
    assert res3 == {"result": True}

    with pytest.raises(LLMError, match="Failed to parse LLM response as JSON"):
        gateway.complete_json("Prompt 4")


def test_get_llm_gateway_defaults_to_mock() -> None:
    settings = Settings(llm_provider="mock", llm_model="mock-test")
    gateway = get_llm_gateway(settings)
    assert isinstance(gateway.provider, MockLLMProvider)

    # Empty key defaults to mock even if provider is openai
    settings_no_key = Settings(llm_provider="openai", llm_api_key="", llm_model="gpt-4o")
    gateway_no_key = get_llm_gateway(settings_no_key)
    assert isinstance(gateway_no_key.provider, MockLLMProvider)


def test_get_llm_gateway_openai() -> None:
    settings = Settings(llm_provider="openai", llm_api_key="sk-test-key", llm_model="gpt-4o-mini")
    gateway = get_llm_gateway(settings)
    assert isinstance(gateway.provider, OpenAIProvider)
    assert gateway.provider.api_key == "sk-test-key"
    assert gateway.provider.model == "gpt-4o-mini"


def test_get_llm_gateway_anthropic() -> None:
    settings = Settings(
        llm_provider="anthropic",
        llm_api_key="sk-ant-key",
        llm_model="claude-3-5-sonnet-20241022",
    )
    gateway = get_llm_gateway(settings)
    assert isinstance(gateway.provider, AnthropicProvider)
    assert gateway.provider.api_key == "sk-ant-key"


def test_openai_provider_success() -> None:
    mock_client = MagicMock(spec=httpx.Client)
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "model": "gpt-4o-mini",
        "choices": [{"message": {"content": "OpenAI generated text"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 15, "completion_tokens": 5, "total_tokens": 20},
    }
    mock_client.post.return_value = mock_response

    provider = OpenAIProvider(api_key="sk-test", model="gpt-4o-mini", client=mock_client)
    resp = provider.complete("Hello OpenAI", system="System message")

    assert resp.content == "OpenAI generated text"
    assert resp.provider == "openai"
    assert resp.prompt_tokens == 15
    assert resp.completion_tokens == 5
    assert resp.total_tokens == 20
    assert resp.finish_reason == "stop"


def test_openai_provider_retry_success() -> None:
    mock_client = MagicMock(spec=httpx.Client)
    fail_response = MagicMock()
    fail_response.status_code = 500
    fail_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "500 Internal Error", request=MagicMock(), response=fail_response
    )

    success_response = MagicMock()
    success_response.status_code = 200
    success_response.json.return_value = {
        "choices": [{"message": {"content": "Retried successfully"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14},
    }

    mock_client.post.side_effect = [fail_response, success_response]

    provider = OpenAIProvider(api_key="sk-test", retries=2, client=mock_client)
    resp = provider.complete("Retry prompt")

    assert resp.content == "Retried successfully"
    assert mock_client.post.call_count == 2


def test_openai_provider_auth_error_no_retry() -> None:
    mock_client = MagicMock(spec=httpx.Client)
    auth_response = MagicMock()
    auth_response.status_code = 401
    auth_response.text = "Unauthorized key"
    mock_client.post.return_value = auth_response

    provider = OpenAIProvider(api_key="invalid-key", retries=3, client=mock_client)
    with pytest.raises(LLMAuthenticationError):
        provider.complete("Prompt")

    # Should fail immediately on 401 without retrying 3 times
    assert mock_client.post.call_count == 1


def test_anthropic_provider_success() -> None:
    mock_client = MagicMock(spec=httpx.Client)
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "model": "claude-3-5-sonnet-20241022",
        "content": [{"type": "text", "text": "Anthropic response"}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 25, "output_tokens": 8},
    }
    mock_client.post.return_value = mock_response

    provider = AnthropicProvider(api_key="sk-ant-test", client=mock_client)
    resp = provider.complete("Hello Claude", system="You are Claude")

    assert resp.content == "Anthropic response"
    assert resp.provider == "anthropic"
    assert resp.prompt_tokens == 25
    assert resp.completion_tokens == 8
    assert resp.total_tokens == 33
    assert resp.finish_reason == "end_turn"
