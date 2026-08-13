"""Additional resilience coverage for the provider gateway (T-09)."""

from unittest.mock import MagicMock

import httpx
import pytest
from app.llm import (
    AnthropicProvider,
    LLMAuthenticationError,
    LLMRetryableError,
    OpenAIProvider,
)


def _response(status_code: int, body: str = "error") -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.text = body
    response.raise_for_status.side_effect = httpx.HTTPStatusError(
        f"HTTP {status_code}", request=MagicMock(), response=response
    )
    return response


def test_openai_rate_limit_retries_then_fails() -> None:
    client = MagicMock(spec=httpx.Client)
    client.post.side_effect = [_response(429), _response(429), _response(429)]
    provider = OpenAIProvider(api_key="test", retries=2, client=client)

    with pytest.raises(LLMRetryableError):
        provider.complete("prompt")

    assert client.post.call_count == 3


def test_openai_server_error_retries_then_succeeds() -> None:
    client = MagicMock(spec=httpx.Client)
    success = MagicMock()
    success.status_code = 200
    success.json.return_value = {
        "model": "test-model",
        "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }
    client.post.side_effect = [_response(500), success]
    provider = OpenAIProvider(api_key="test", retries=2, client=client)

    result = provider.complete("prompt")

    assert result.content == "ok"
    assert client.post.call_count == 2


def test_anthropic_rate_limit_retries_then_succeeds() -> None:
    client = MagicMock(spec=httpx.Client)
    success = MagicMock()
    success.status_code = 200
    success.json.return_value = {
        "model": "test-model",
        "content": [{"type": "text", "text": "ok"}],
        "usage": {"input_tokens": 1, "output_tokens": 1},
        "stop_reason": "end_turn",
    }
    client.post.side_effect = [_response(429), success]
    provider = AnthropicProvider(api_key="test", retries=2, client=client)

    result = provider.complete("prompt")

    assert result.content == "ok"
    assert client.post.call_count == 2


def test_anthropic_forbidden_is_not_retried() -> None:
    client = MagicMock(spec=httpx.Client)
    client.post.return_value = _response(403, "forbidden")
    provider = AnthropicProvider(api_key="test", retries=3, client=client)

    with pytest.raises(LLMAuthenticationError):
        provider.complete("prompt")

    assert client.post.call_count == 1
