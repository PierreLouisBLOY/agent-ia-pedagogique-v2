"""Private transport seam for the offline Anthropic scorer."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from backend.infrastructure.config.secrets.provider import ProviderSecretValue


class AnthropicTransportErrorCode(StrEnum):
    INVALID_REQUEST = "INVALID_REQUEST"
    AUTHENTICATION = "AUTHENTICATION"
    PERMISSION = "PERMISSION"
    BILLING = "BILLING"
    RATE_LIMIT = "RATE_LIMIT"
    NOT_FOUND = "NOT_FOUND"
    TIMEOUT = "TIMEOUT"
    CONNECTION = "CONNECTION"
    SERVER = "SERVER"
    CONFLICT = "CONFLICT"
    REQUEST_TOO_LARGE = "REQUEST_TOO_LARGE"
    OVERLOADED = "OVERLOADED"
    EMPTY_RESPONSE = "EMPTY_RESPONSE"
    REFUSED = "REFUSED"
    UNAVAILABLE = "UNAVAILABLE"


class AnthropicProviderErrorType(StrEnum):
    TIMEOUT_ERROR = "TIMEOUT_ERROR"
    CONNECTION_ERROR = "CONNECTION_ERROR"
    BAD_REQUEST_ERROR = "BAD_REQUEST_ERROR"
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    PERMISSION_DENIED_ERROR = "PERMISSION_DENIED_ERROR"
    NOT_FOUND_ERROR = "NOT_FOUND_ERROR"
    RATE_LIMIT_ERROR = "RATE_LIMIT_ERROR"
    INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"
    SERVICE_UNAVAILABLE_ERROR = "SERVICE_UNAVAILABLE_ERROR"
    OVERLOADED_ERROR = "OVERLOADED_ERROR"
    API_STATUS_ERROR = "API_STATUS_ERROR"
    UNMAPPED_SDK_ERROR = "UNMAPPED_SDK_ERROR"
    EMPTY_RESPONSE = "EMPTY_RESPONSE"
    REFUSAL = "REFUSAL"


class AnthropicStopReason(StrEnum):
    END_TURN = "end_turn"
    MAX_TOKENS = "max_tokens"
    STOP_SEQUENCE = "stop_sequence"
    TOOL_USE = "tool_use"
    PAUSE_TURN = "pause_turn"
    REFUSAL = "refusal"
    UNKNOWN = "unknown"


class AnthropicTransportError(RuntimeError):
    """Closed provider failure with no raw SDK payload or message."""

    code: AnthropicTransportErrorCode
    http_status: int | None
    provider_error_type: AnthropicProviderErrorType | None
    response_received: bool
    stop_reason: AnthropicStopReason | None
    text_block_count: int | None
    input_tokens: int | None
    cached_input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None

    def __init__(
        self,
        code: AnthropicTransportErrorCode,
        *,
        http_status: int | None = None,
        provider_error_type: AnthropicProviderErrorType | None = None,
        response_received: bool = False,
        stop_reason: AnthropicStopReason | None = None,
        text_block_count: int | None = None,
        input_tokens: int | None = None,
        cached_input_tokens: int | None = None,
        output_tokens: int | None = None,
        total_tokens: int | None = None,
    ) -> None:
        if type(code) is not AnthropicTransportErrorCode:
            raise TypeError("code must be an AnthropicTransportErrorCode")
        if http_status is not None and (
            type(http_status) is not int or not 100 <= http_status <= 599
        ):
            raise ValueError("http_status must be between 100 and 599")
        if provider_error_type is not None and (
            type(provider_error_type) is not AnthropicProviderErrorType
        ):
            raise TypeError("provider_error_type must be closed")
        if type(response_received) is not bool:
            raise TypeError("response_received must be a bool")
        if stop_reason is not None and type(stop_reason) is not AnthropicStopReason:
            raise TypeError("stop_reason must be closed")
        if text_block_count is not None and (
            type(text_block_count) is not int or not 0 <= text_block_count <= 100
        ):
            raise ValueError("text_block_count must be between 0 and 100")
        usage_values = (
            input_tokens,
            cached_input_tokens,
            output_tokens,
            total_tokens,
        )
        if any(
            value is not None and (type(value) is not int or value < 0)
            for value in usage_values
        ):
            raise ValueError("usage values must be non-negative integers")
        self.code = code
        self.http_status = http_status
        self.provider_error_type = provider_error_type
        self.response_received = response_received
        self.stop_reason = stop_reason
        self.text_block_count = text_block_count
        self.input_tokens = input_tokens
        self.cached_input_tokens = cached_input_tokens
        self.output_tokens = output_tokens
        self.total_tokens = total_tokens
        super().__init__(code.value)

    def __repr__(self) -> str:
        return (
            "AnthropicTransportError("
            f"code={self.code.value!r}, http_status={self.http_status!r}, "
            f"provider_error_type={_enum_value(self.provider_error_type)!r}, "
            f"response_received={self.response_received!r}, "
            f"stop_reason={_enum_value(self.stop_reason)!r}, "
            f"text_block_count={self.text_block_count!r}, "
            f"input_tokens={self.input_tokens!r}, "
            f"cached_input_tokens={self.cached_input_tokens!r}, "
            f"output_tokens={self.output_tokens!r}, "
            f"total_tokens={self.total_tokens!r})"
        )


def _enum_value(value: StrEnum | None) -> str | None:
    return value.value if value is not None else None


@dataclass(frozen=True, slots=True)
class AnthropicScoringRequest:
    model: str
    system: str
    input_json: str
    output_schema: dict[str, object]
    max_tokens: int


@dataclass(frozen=True, slots=True)
class AnthropicScoringResponse:
    output_text: str
    input_tokens: int | None = None
    cached_input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    stop_reason: AnthropicStopReason | None = None
    text_block_count: int | None = None


class AnthropicScoringTransport(Protocol):
    def create(self, *, request: AnthropicScoringRequest) -> AnthropicScoringResponse: ...


class AnthropicScoringTransportFactory(Protocol):
    def build(
        self,
        *,
        secret: ProviderSecretValue,
        timeout_seconds: float,
    ) -> AnthropicScoringTransport: ...
