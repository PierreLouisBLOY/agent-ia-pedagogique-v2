from __future__ import annotations

from types import SimpleNamespace

import anthropic
import httpx2
import pytest

from backend.infrastructure.config.secrets.provider import ProviderSecretValue
from tests.providers.anthropic import (
    AnthropicProviderErrorType,
    AnthropicScoringRequest,
    AnthropicSDKScoringTransport,
    AnthropicStopReason,
    AnthropicTransportError,
    AnthropicTransportErrorCode,
)
from tests.providers.anthropic.transport import (
    _anthropic_error_code,
    _anthropic_status_code,
    _closed_anthropic_error,
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
    assert response.stop_reason is AnthropicStopReason.END_TURN
    assert response.text_block_count == 1
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
        (409, AnthropicTransportErrorCode.CONFLICT),
        (413, AnthropicTransportErrorCode.REQUEST_TOO_LARGE),
        (429, AnthropicTransportErrorCode.RATE_LIMIT),
        (500, AnthropicTransportErrorCode.SERVER),
        (529, AnthropicTransportErrorCode.OVERLOADED),
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


def test_overloaded_sdk_error_is_distinct_and_retry_free(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = httpx2.Request("POST", "https://example.invalid/v1/messages")
    overloaded = anthropic.OverloadedError(
        "sensitive-provider-message",
        response=httpx2.Response(529, request=request),
        body={"error": "sensitive-provider-body"},
    )
    messages = _FakeMessages(error=overloaded)
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

    assert raised.value.code is AnthropicTransportErrorCode.OVERLOADED
    assert raised.value.http_status == 529
    assert raised.value.provider_error_type is AnthropicProviderErrorType.OVERLOADED_ERROR
    assert raised.value.response_received is True
    assert _anthropic_error_code(overloaded) is AnthropicTransportErrorCode.OVERLOADED


def test_empty_success_is_closed_with_safe_usage_and_response_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = SimpleNamespace(
        stop_reason="end_turn",
        content=[],
        usage=SimpleNamespace(
            input_tokens=19,
            cache_read_input_tokens=3,
            output_tokens=4,
        ),
    )
    messages = _FakeMessages(response)
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

    error = raised.value
    assert error.code is AnthropicTransportErrorCode.EMPTY_RESPONSE
    assert error.provider_error_type is AnthropicProviderErrorType.EMPTY_RESPONSE
    assert error.response_received is True
    assert error.stop_reason is AnthropicStopReason.END_TURN
    assert error.text_block_count == 0
    assert (error.input_tokens, error.cached_input_tokens, error.output_tokens) == (19, 3, 4)
    assert error.total_tokens == 26


def test_unmapped_sdk_error_and_status_details_are_closed_and_raw_free() -> None:
    request = httpx2.Request("POST", "https://example.invalid/v1/messages")
    response = httpx2.Response(
        409,
        request=request,
        headers={"request-id": "sensitive-request-id"},
    )
    provider_error = anthropic.APIStatusError(
        "sensitive-provider-message",
        response=response,
        body={"error": "sensitive-provider-body"},
    )
    closed = _closed_anthropic_error(provider_error)
    rendered = f"{closed!s} {closed!r}"

    assert closed.code is AnthropicTransportErrorCode.CONFLICT
    assert closed.http_status == 409
    assert closed.provider_error_type is AnthropicProviderErrorType.API_STATUS_ERROR
    assert closed.response_received is True
    assert "sensitive" not in rendered
    assert "request-id" not in rendered
    assert "header" not in rendered
    assert "body" not in rendered

    unmapped = _closed_anthropic_error(anthropic.AnthropicError("opaque-raw-message"))
    assert unmapped.code is AnthropicTransportErrorCode.UNAVAILABLE
    assert unmapped.provider_error_type is AnthropicProviderErrorType.UNMAPPED_SDK_ERROR
    assert "opaque-raw-message" not in f"{unmapped!s} {unmapped!r}"


def test_connection_and_server_mappings_remain_closed() -> None:
    request = httpx2.Request("POST", "https://example.invalid/v1/messages")
    connection = _closed_anthropic_error(
        anthropic.APIConnectionError(
            message="sensitive-connection-detail",
            request=request,
        )
    )
    server = _closed_anthropic_error(
        anthropic.InternalServerError(
            "sensitive-server-detail",
            response=httpx2.Response(500, request=request),
            body={"error": "sensitive-server-body"},
        )
    )

    assert connection.code is AnthropicTransportErrorCode.CONNECTION
    assert connection.response_received is False
    assert server.code is AnthropicTransportErrorCode.SERVER
    assert server.http_status == 500
    assert server.response_received is True
    assert "sensitive" not in f"{connection!s} {connection!r} {server!s} {server!r}"
