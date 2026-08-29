from __future__ import annotations

from types import SimpleNamespace

import anthropic
import httpx2
import pytest

from backend.infrastructure.config.secrets.provider import ProviderSecretValue
from tests.providers.anthropic import (
    AnthropicScoringRequest,
    AnthropicSDKScoringTransport,
    AnthropicTransportError,
    AnthropicTransportErrorCode,
)
from tests.providers.anthropic.transport import (
    _anthropic_status_code,
    transform_anthropic_provider_schema,
)

_SECRET = "synthetic-anthropic-sdk-secret"


class _FakeMessages:
    def __init__(self, response: object = None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response


def _request() -> AnthropicScoringRequest:
    return AnthropicScoringRequest(
        model="claude-sonnet-5",
        system="Bounded scorer instruction",
        input_json='{"observations":[]}',
        output_schema={"type": "object"},
        max_tokens=512,
    )


def test_sdk_transport_is_one_structured_non_streaming_call_without_controls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    messages = _FakeMessages(
        SimpleNamespace(
            stop_reason="end_turn",
            content=[SimpleNamespace(type="text", text='{"status":"SCORED"}')],
        )
    )
    constructor: dict[str, object] = {}

    def fake_anthropic(**kwargs: object) -> object:
        constructor.update(kwargs)
        return SimpleNamespace(messages=messages)

    monkeypatch.setattr(
        "tests.providers.anthropic.transport.Anthropic",
        fake_anthropic,
    )
    transport = AnthropicSDKScoringTransport(
        secret=ProviderSecretValue(_SECRET),
        timeout_seconds=12.5,
    )
    response = transport.create(request=_request())

    assert constructor == {"api_key": _SECRET, "timeout": 12.5, "max_retries": 0}
    assert response.output_text == '{"status":"SCORED"}'
    assert len(messages.calls) == 1
    call = messages.calls[0]
    assert call == {
        "model": "claude-sonnet-5",
        "max_tokens": 512,
        "system": "Bounded scorer instruction",
        "messages": [{"role": "user", "content": '{"observations":[]}'}],
        "output_config": {
            "format": {
                "type": "json_schema",
                "schema": {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
            }
        },
        "stream": False,
    }
    assert all(
        key not in call
        for key in ("tools", "thinking", "temperature", "top_p", "top_k")
    )
    assert _SECRET not in repr(transport)


def test_sdk_timeout_and_refusal_are_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    timeout = anthropic.APITimeoutError(
        request=httpx2.Request("POST", "https://example.invalid/v1/messages")
    )
    messages = _FakeMessages(error=timeout)
    monkeypatch.setattr(
        "tests.providers.anthropic.transport.Anthropic",
        lambda **_: SimpleNamespace(messages=messages),
    )
    transport = AnthropicSDKScoringTransport(
        secret=ProviderSecretValue(_SECRET),
        timeout_seconds=1.0,
    )
    with pytest.raises(AnthropicTransportError) as raised:
        transport.create(request=_request())
    assert raised.value.code is AnthropicTransportErrorCode.TIMEOUT

    refusal_messages = _FakeMessages(SimpleNamespace(stop_reason="refusal", content=[]))
    monkeypatch.setattr(
        "tests.providers.anthropic.transport.Anthropic",
        lambda **_: SimpleNamespace(messages=refusal_messages),
    )
    refused = AnthropicSDKScoringTransport(
        secret=ProviderSecretValue(_SECRET),
        timeout_seconds=1.0,
    )
    with pytest.raises(AnthropicTransportError) as refusal:
        refused.create(request=_request())
    assert refusal.value.code is AnthropicTransportErrorCode.REFUSED


@pytest.mark.parametrize(
    ("status_code", "expected"),
    (
        (400, AnthropicTransportErrorCode.INVALID_REQUEST),
        (401, AnthropicTransportErrorCode.AUTHENTICATION),
        (402, AnthropicTransportErrorCode.BILLING),
        (403, AnthropicTransportErrorCode.PERMISSION),
        (404, AnthropicTransportErrorCode.NOT_FOUND),
        (429, AnthropicTransportErrorCode.RATE_LIMIT),
        (529, AnthropicTransportErrorCode.SERVER),
        (418, AnthropicTransportErrorCode.UNAVAILABLE),
    ),
)
def test_sdk_status_codes_map_to_closed_categories(
    status_code: int,
    expected: AnthropicTransportErrorCode,
) -> None:
    assert _anthropic_status_code(status_code) is expected


def test_schema_transform_is_deterministic_non_mutating_and_removes_minimum() -> None:
    source = {
        "type": "object",
        "properties": {"score": {"type": "integer", "minimum": 0}},
        "required": ["score"],
        "additionalProperties": False,
    }
    snapshot = {
        "type": "object",
        "properties": {"score": {"type": "integer", "minimum": 0}},
        "required": ["score"],
        "additionalProperties": False,
    }
    first = transform_anthropic_provider_schema(source)
    second = transform_anthropic_provider_schema(source)
    assert first == second
    assert source == snapshot
    properties = first["properties"]
    assert type(properties) is dict
    assert "minimum" not in properties["score"]  # type: ignore[operator]
    assert first["required"] == ["score"]
    assert first["additionalProperties"] is False


def test_schema_transform_failure_stops_before_messages_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    messages = _FakeMessages(SimpleNamespace())
    monkeypatch.setattr(
        "tests.providers.anthropic.transport.Anthropic",
        lambda **_: SimpleNamespace(messages=messages),
    )

    def fail_transform(_: object) -> object:
        raise ValueError("closed")

    monkeypatch.setattr(
        "tests.providers.anthropic.transport.anthropic.transform_schema",
        fail_transform,
    )
    transport = AnthropicSDKScoringTransport(
        secret=ProviderSecretValue(_SECRET),
        timeout_seconds=1.0,
    )
    with pytest.raises(AnthropicTransportError) as raised:
        transport.create(request=_request())
    assert raised.value.code is AnthropicTransportErrorCode.INVALID_REQUEST
    assert messages.calls == []
