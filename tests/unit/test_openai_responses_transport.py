from __future__ import annotations

from types import SimpleNamespace

import httpx2
import openai
import pytest

from backend.adapters.outbound.generation.openai import (
    OpenAIResponsesRequest,
    OpenAISDKResponsesTransport,
    OpenAITransportError,
    OpenAITransportErrorCode,
)
from backend.infrastructure.config.secrets.provider import ProviderSecretValue

_SYNTHETIC_SECRET = "synthetic-sdk-boundary-secret"


class _FakeResponses:
    def __init__(self, response: object = None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response


def _request() -> OpenAIResponsesRequest:
    return OpenAIResponsesRequest(
        model="gpt-5.6-terra",
        instructions="Bounded instructions",
        input_json='{"objective":"test"}',
        output_schema={"type": "object"},
        max_output_tokens=1_000,
        schema_name="pedagogical_generation",
    )


def test_sdk_transport_uses_one_non_stored_tool_free_non_streaming_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_response = SimpleNamespace(
        status="completed",
        output=(),
        output_text='{"ok":true}',
        usage=SimpleNamespace(
            input_tokens=10,
            input_tokens_details=SimpleNamespace(cached_tokens=2),
            output_tokens=5,
            total_tokens=15,
        ),
    )
    responses = _FakeResponses(raw_response)
    constructor: dict[str, object] = {}

    def fake_openai(**kwargs: object) -> object:
        constructor.update(kwargs)
        return SimpleNamespace(responses=responses)

    monkeypatch.setattr(
        "backend.adapters.outbound.openai.transport.OpenAI",
        fake_openai,
    )
    transport = OpenAISDKResponsesTransport(
        secret=ProviderSecretValue(_SYNTHETIC_SECRET),
        timeout_seconds=12.5,
    )

    result = transport.create(request=_request())

    assert constructor == {
        "api_key": _SYNTHETIC_SECRET,
        "timeout": 12.5,
        "max_retries": 0,
    }
    assert len(responses.calls) == 1
    call = responses.calls[0]
    assert call["model"] == "gpt-5.6-terra"
    assert call["input"] == '{"objective":"test"}'
    assert call["instructions"] == "Bounded instructions"
    assert call["max_output_tokens"] == 1_000
    assert call["store"] is False
    assert call["stream"] is False
    assert call["background"] is False
    assert call["tool_choice"] == "none"
    assert call["tools"] == []
    assert call["text"] == {
        "format": {
            "name": "pedagogical_generation",
            "schema": {"type": "object"},
            "strict": True,
            "type": "json_schema",
        }
    }
    assert result.usage.cached_input_tokens == 2
    assert _SYNTHETIC_SECRET not in repr(transport)
    assert _SYNTHETIC_SECRET not in repr(result)


def test_sdk_timeout_is_mapped_without_raw_exception_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error = openai.APITimeoutError(
        request=httpx2.Request("POST", "https://example.invalid/v1/responses")
    )
    responses = _FakeResponses(error=error)
    monkeypatch.setattr(
        "backend.adapters.outbound.openai.transport.OpenAI",
        lambda **_: SimpleNamespace(responses=responses),
    )
    transport = OpenAISDKResponsesTransport(
        secret=ProviderSecretValue(_SYNTHETIC_SECRET),
        timeout_seconds=1.0,
    )

    with pytest.raises(OpenAITransportError) as raised:
        transport.create(request=_request())

    assert raised.value.code is OpenAITransportErrorCode.TIMEOUT
    assert str(raised.value) == "TIMEOUT"
    assert _SYNTHETIC_SECRET not in str(raised.value)
