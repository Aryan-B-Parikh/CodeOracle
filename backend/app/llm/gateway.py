"""Provider-agnostic LLM gateway (T-09).

- ``LLM_PROVIDER`` env-driven: ``mock`` (default for dev/tests), ``openai``, ``anthropic``.
- ``LLM_MODEL`` env-driven: model name passed to the provider.
- Token budget calculation and prompt truncation.
- Exponential backoff retries for network/transient provider errors.
- Structured JSON output helper.
"""

from __future__ import annotations

import json
import logging
import math
import re
import time
from typing import Any, Protocol

import httpx
from pydantic import BaseModel, Field

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


class LLMResponse(BaseModel):
    """Structured response returned by any LLM provider."""

    content: str
    model: str
    provider: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    finish_reason: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class LLMError(Exception):
    """Base exception for LLM gateway errors."""


class LLMRetryableError(LLMError):
    """Transient error suitable for retry (e.g. rate limit, 5xx error, timeout)."""


class LLMAuthenticationError(LLMError):
    """Authentication or authorization failure (non-retryable)."""


class TokenBudgetExceededError(LLMError):
    """Raised when prompt + system instructions exceed token budget even after truncation."""


_CODE_TOKEN_RE = re.compile(
    r"[A-Z]+(?=[A-Z][a-z]|[0-9]|$)|[A-Z]?[a-z]+|[0-9]+|[_\W]"
)


def _heuristic_token_count(text: str) -> int:
    """Code-dense token heuristic recognizing punctuation, symbols, and identifier boundaries."""
    if not text:
        return 0
    tokens = _CODE_TOKEN_RE.findall(text)
    if not tokens:
        return max(1, math.ceil(len(text) / 4.0))
    count = 0
    for tok in tokens:
        if tok.isspace():
            continue
        count += max(1, math.ceil(len(tok) / 4.0))
    return max(1, count)


def estimate_tokens(text: str, model: str = "") -> int:
    """Provider/model tokenizer when available (tiktoken), or code-aware fallback."""
    if not text:
        return 0

    if model:
        try:
            import tiktoken

            try:
                encoding = tiktoken.encoding_for_model(model)
            except KeyError:
                encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))
        except Exception:
            # Import or network failures (encoding download) fall back to the
            # code-aware heuristic so token estimation never blocks a call.
            pass

    return _heuristic_token_count(text)


def fit_to_budget(
    prompt: str,
    system: str = "",
    budget: int = 8192,
    reserve_completion_tokens: int = 2048,
    model: str = "",
) -> tuple[str, bool]:
    """Ensure system + prompt fits within total token budget.

    Truncates user prompt if needed while preserving system instructions.
    Returns (processed_prompt, was_truncated).
    """
    system_tokens = estimate_tokens(system, model=model)
    available_input_tokens = budget - reserve_completion_tokens - system_tokens

    if available_input_tokens <= 0:
        raise TokenBudgetExceededError(
            f"System prompt ({system_tokens} tokens) exceeds available budget "
            f"({budget - reserve_completion_tokens} input tokens)."
        )

    prompt_tokens = estimate_tokens(prompt, model=model)
    if prompt_tokens <= available_input_tokens:
        return prompt, False

    # Truncate prompt from the end (or tail context)
    allowed_chars = available_input_tokens * 4 - 50  # buffer for truncation marker
    if allowed_chars <= 0:
        raise TokenBudgetExceededError("Prompt budget too small to retain meaningful input.")

    truncated_prompt = prompt[:allowed_chars] + "\n... [truncated due to token budget]"
    return truncated_prompt, True


class LLMProvider(Protocol):
    """Protocol for LLM provider implementations."""

    def complete(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.0,
    ) -> LLMResponse: ...

    def count_tokens(self, text: str) -> int: ...


class MockLLMProvider:
    """Mock LLM provider for hermetic testing and offline development."""

    def __init__(
        self,
        model: str = "mock-v1",
        default_response: str = "Mock response content",
        canned_responses: list[str] | None = None,
        fail_attempts: int = 0,
        custom_error: Exception | None = None,
    ) -> None:
        self.model = model
        self.provider_name = "mock"
        self.default_response = default_response
        self.canned_responses = list(canned_responses) if canned_responses else []
        self.fail_attempts = fail_attempts
        self.attempts_made = 0
        self.custom_error = custom_error or LLMRetryableError("Mock transient failure")
        self.history: list[dict[str, Any]] = []

    def count_tokens(self, text: str) -> int:
        return estimate_tokens(text)

    def complete(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.0,
    ) -> LLMResponse:
        self.attempts_made += 1
        if self.attempts_made <= self.fail_attempts:
            raise self.custom_error

        self.history.append(
            {
                "prompt": prompt,
                "system": system,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
        )

        if self.canned_responses:
            response_text = self.canned_responses.pop(0)
        else:
            response_text = self.default_response

        prompt_tok = self.count_tokens((system or "") + prompt)
        comp_tok = self.count_tokens(response_text)

        return LLMResponse(
            content=response_text,
            model=self.model,
            provider=self.provider_name,
            prompt_tokens=prompt_tok,
            completion_tokens=comp_tok,
            total_tokens=prompt_tok + comp_tok,
            finish_reason="stop",
            raw={"mock": True, "call_index": len(self.history)},
        )


class OpenAIProvider:
    """OpenAI-compatible chat completions client with retries and backoff."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str = "https://api.openai.com/v1",
        retries: int = 3,
        timeout_seconds: float = 60.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.retries = retries
        self.timeout_seconds = timeout_seconds
        self._external_client = client
        self.provider_name = "openai"

    def count_tokens(self, text: str) -> int:
        return estimate_tokens(text, model=self.model)

    def _get_client(self) -> httpx.Client:
        if self._external_client is not None:
            return self._external_client
        return httpx.Client(timeout=self.timeout_seconds)

    def complete(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.0,
    ) -> LLMResponse:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        last_exc: Exception | None = None
        client = self._get_client()

        for attempt in range(self.retries + 1):
            try:
                response = client.post(url, headers=headers, json=payload)
                if response.status_code == 401 or response.status_code == 403:
                    raise LLMAuthenticationError(f"Authentication failed: {response.text}")
                response.raise_for_status()

                data = response.json()
                choice = data["choices"][0]
                content = choice["message"]["content"] or ""
                usage = data.get("usage", {})

                return LLMResponse(
                    content=content,
                    model=data.get("model", self.model),
                    provider="openai",
                    prompt_tokens=usage.get("prompt_tokens", self.count_tokens(prompt)),
                    completion_tokens=usage.get("completion_tokens", self.count_tokens(content)),
                    total_tokens=usage.get("total_tokens", 0),
                    finish_reason=choice.get("finish_reason"),
                    raw=data,
                )
            except (httpx.HTTPStatusError, httpx.RequestError, KeyError, ValueError) as exc:
                last_exc = exc
                if isinstance(exc, LLMAuthenticationError):
                    raise
                if attempt < self.retries:
                    time.sleep(0.2 * (2**attempt))
                else:
                    logger.warning("OpenAI API call failed after %d retries: %s", self.retries, exc)

        raise LLMRetryableError(
            f"OpenAI completion request failed after {self.retries + 1} attempts: {last_exc}"
        ) from last_exc


class OpenRouterProvider(OpenAIProvider):
    """OpenRouter API provider supporting Gemini, Claude, Llama, DeepSeek, and OpenAI models."""

    def __init__(
        self,
        api_key: str,
        model: str = "google/gemini-2.0-flash-lite-001",
        base_url: str = "https://openrouter.ai/api/v1",
        retries: int = 3,
        timeout_seconds: float = 60.0,
        client: httpx.Client | None = None,
    ) -> None:
        super().__init__(
            api_key=api_key,
            model=model or "google/gemini-2.0-flash-lite-001",
            base_url=base_url or "https://openrouter.ai/api/v1",
            retries=retries,
            timeout_seconds=timeout_seconds,
            client=client,
        )
        self.provider_name = "openrouter"

    def complete(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.0,
    ) -> LLMResponse:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://codeoracle.dev",
            "X-Title": "CodeOracle",
        }

        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        last_exc: Exception | None = None
        client = self._get_client()

        for attempt in range(self.retries + 1):
            try:
                response = client.post(url, headers=headers, json=payload)
                if response.status_code == 401 or response.status_code == 403:
                    raise LLMAuthenticationError(f"Authentication failed: {response.text}")
                response.raise_for_status()

                data = response.json()
                choice = data["choices"][0]
                content = choice["message"]["content"] or ""
                usage = data.get("usage", {})

                return LLMResponse(
                    content=content,
                    model=data.get("model", self.model),
                    provider="openrouter",
                    prompt_tokens=usage.get("prompt_tokens", self.count_tokens(prompt)),
                    completion_tokens=usage.get("completion_tokens", self.count_tokens(content)),
                    total_tokens=usage.get("total_tokens", 0),
                    finish_reason=choice.get("finish_reason"),
                    raw=data,
                )
            except (httpx.HTTPStatusError, httpx.RequestError, KeyError, ValueError) as exc:
                last_exc = exc
                if isinstance(exc, LLMAuthenticationError):
                    raise
                if attempt < self.retries:
                    time.sleep(0.2 * (2**attempt))
                else:
                    logger.warning("OpenRouter API call failed after %d retries: %s", self.retries, exc)

        raise LLMRetryableError(
            f"OpenRouter completion request failed after {self.retries + 1} attempts: {last_exc}"
        ) from last_exc


class AnthropicProvider:
    """Anthropic Messages API client with retries and backoff."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-3-5-sonnet-20241022",
        base_url: str = "https://api.anthropic.com/v1",
        retries: int = 3,
        timeout_seconds: float = 60.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.retries = retries
        self.timeout_seconds = timeout_seconds
        self._external_client = client
        self.provider_name = "anthropic"

    def count_tokens(self, text: str) -> int:
        return estimate_tokens(text, model=self.model)

    def _get_client(self) -> httpx.Client:
        if self._external_client is not None:
            return self._external_client
        return httpx.Client(timeout=self.timeout_seconds)

    def complete(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.0,
    ) -> LLMResponse:
        url = f"{self.base_url}/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens or 2048,
            "temperature": temperature,
        }
        if system:
            payload["system"] = system

        last_exc: Exception | None = None
        client = self._get_client()

        for attempt in range(self.retries + 1):
            try:
                response = client.post(url, headers=headers, json=payload)
                if response.status_code in (401, 403):
                    raise LLMAuthenticationError(f"Authentication failed: {response.text}")
                response.raise_for_status()

                data = response.json()
                content_blocks = data.get("content", [])
                text_content = "".join(
                    block.get("text", "") for block in content_blocks if block.get("type") == "text"
                )

                usage = data.get("usage", {})
                prompt_tok = usage.get("input_tokens", self.count_tokens(prompt))
                comp_tok = usage.get("output_tokens", self.count_tokens(text_content))

                return LLMResponse(
                    content=text_content,
                    model=data.get("model", self.model),
                    provider="anthropic",
                    prompt_tokens=prompt_tok,
                    completion_tokens=comp_tok,
                    total_tokens=prompt_tok + comp_tok,
                    finish_reason=data.get("stop_reason"),
                    raw=data,
                )
            except (httpx.HTTPStatusError, httpx.RequestError, KeyError, ValueError) as exc:
                last_exc = exc
                if isinstance(exc, LLMAuthenticationError):
                    raise
                if attempt < self.retries:
                    time.sleep(0.2 * (2**attempt))
                else:
                    logger.warning(
                        "Anthropic API call failed after %d retries: %s", self.retries, exc
                    )

        raise LLMRetryableError(
            f"Anthropic completion request failed after {self.retries + 1} attempts: {last_exc}"
        ) from last_exc


class LLMGateway:
    """High-level LLM gateway wrapping token budget management and provider calls."""

    def __init__(
        self,
        provider: LLMProvider,
        token_budget: int = 8192,
        max_tokens: int = 2048,
    ) -> None:
        self.provider = provider
        self.token_budget = token_budget
        self.max_tokens = max_tokens

    def complete(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.0,
    ) -> LLMResponse:
        effective_max_tokens = max_tokens if max_tokens is not None else self.max_tokens
        model_name = getattr(self.provider, "model", "")
        fitted_prompt, was_truncated = fit_to_budget(
            prompt=prompt,
            system=system or "",
            budget=self.token_budget,
            reserve_completion_tokens=effective_max_tokens,
            model=model_name,
        )
        if was_truncated:
            logger.info("Prompt was truncated to fit token budget (%d)", self.token_budget)

        return self.provider.complete(
            prompt=fitted_prompt,
            system=system,
            max_tokens=effective_max_tokens,
            temperature=temperature,
        )

    def complete_json(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        """Call LLM and parse response as JSON, with fallback extraction for ```json blocks."""
        response = self.complete(
            prompt=prompt,
            system=system,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        text = response.content.strip()

        # Try direct parse
        try:
            return json.loads(text)  # type: ignore[no-any-return]
        except json.JSONDecodeError:
            pass

        # Try markdown code block extraction
        match = re.search(r"```(?:json)?\s*(\{.*\}|\[.*\])\s*```", text, re.DOTALL)
        if match:
            extracted = match.group(1)
            try:
                return json.loads(extracted)  # type: ignore[no-any-return]
            except json.JSONDecodeError:
                pass

        # Try finding raw JSON object
        obj_match = re.search(r"(\{.*\})", text, re.DOTALL)
        if obj_match:
            try:
                return json.loads(obj_match.group(1))  # type: ignore[no-any-return]
            except json.JSONDecodeError:
                pass

        raise LLMError(f"Failed to parse LLM response as JSON: {text[:200]}")


def get_llm_gateway(settings: Settings | None = None) -> LLMGateway:
    """Factory function creating an LLMGateway instance from application settings."""
    if settings is None:
        settings = get_settings()

    provider_type = settings.llm_provider.lower().strip()
    model = settings.llm_model.strip()

    provider: LLMProvider

    openrouter_key = (
        getattr(settings, "openrouter_api_key", "")
        or (settings.llm_api_key if settings.llm_api_key.startswith("sk-or-") else "")
    )

    if provider_type == "openrouter" or (provider_type == "openai" and openrouter_key):
        active_key = openrouter_key or settings.llm_api_key
        if not active_key:
            logger.warning(
                "LLM_PROVIDER is 'openrouter' but no API key provided; falling back to MockLLMProvider"
            )
            provider = MockLLMProvider(model=model or "mock-openrouter")
        else:
            base_url = (
                settings.llm_base_url
                if "openrouter.ai" in settings.llm_base_url
                else "https://openrouter.ai/api/v1"
            )
            provider = OpenRouterProvider(
                api_key=active_key,
                model=model or "google/gemini-2.0-flash-lite-001",
                base_url=base_url,
                retries=settings.llm_retries,
                timeout_seconds=settings.llm_timeout_seconds,
            )
    elif provider_type == "openai":
        if not settings.llm_api_key:
            logger.warning(
                "LLM_PROVIDER is 'openai' but LLM_API_KEY is empty; falling back to MockLLMProvider"
            )
            provider = MockLLMProvider(model=model or "mock-openai")
        else:
            provider = OpenAIProvider(
                api_key=settings.llm_api_key,
                model=model or "gpt-4o-mini",
                base_url=settings.llm_base_url,
                retries=settings.llm_retries,
                timeout_seconds=settings.llm_timeout_seconds,
            )
    elif provider_type == "anthropic":
        if not settings.llm_api_key:
            logger.warning(
                "LLM_PROVIDER is 'anthropic' but LLM_API_KEY is empty; "
                "falling back to MockLLMProvider"
            )
            provider = MockLLMProvider(model=model or "mock-anthropic")
        else:
            provider = AnthropicProvider(
                api_key=settings.llm_api_key,
                model=model or "claude-3-5-sonnet-20241022",
                base_url=settings.llm_base_url,
                retries=settings.llm_retries,
                timeout_seconds=settings.llm_timeout_seconds,
            )
    elif provider_type == "mock":
        provider = MockLLMProvider(model=model or "mock-v1")
    else:
        logger.warning("Unknown LLM_PROVIDER '%s'; falling back to MockLLMProvider", provider_type)
        provider = MockLLMProvider(model=model or "mock-v1")

    return LLMGateway(
        provider=provider,
        token_budget=settings.llm_token_budget,
        max_tokens=settings.llm_max_tokens,
    )
