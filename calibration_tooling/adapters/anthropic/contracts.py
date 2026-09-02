"""Private typed seam for the injected Anthropic Messages client."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Final, Protocol

from calibration_tooling.contracts.models import CallRef

_SAFE_MODEL_CODE: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_MAX_MESSAGE_BYTES: Final = 262_144
_MAX_OUTPUT_TOKENS: Final = 65_536
_MAX_TIMEOUT_MILLISECONDS: Final = 600_000
_MAX_USAGE_TOKENS: Final = 10**12
_MAX_PRICE_PER_MILLION_USD: Final = Decimal("1000000")


class AnthropicThinkingMode(StrEnum):
    ADAPTIVE = "adaptive"


class AnthropicEffort(StrEnum):
    LOW = "low"


class AnthropicMessageRole(StrEnum):
    USER = "user"


class AnthropicStopReason(StrEnum):
    END_TURN = "end_turn"
    MAX_TOKENS = "max_tokens"
    STOP_SEQUENCE = "stop_sequence"
    TOOL_USE = "tool_use"
    PAUSE_TURN = "pause_turn"
    REFUSAL = "refusal"
    UNKNOWN = "unknown"


class AnthropicTransportErrorCode(StrEnum):
    CREDENTIAL_UNAVAILABLE = "CREDENTIAL_UNAVAILABLE"
    TIMEOUT = "TIMEOUT"
    HTTP_ERROR = "HTTP_ERROR"
    RESPONSE_INVALID = "RESPONSE_INVALID"
    UNAVAILABLE = "UNAVAILABLE"


class AnthropicTransportError(RuntimeError):
    """Closed failure that never retains request, response, or secret content."""

    code: AnthropicTransportErrorCode
    http_status: int | None
    response_received: bool

    def __init__(
        self,
        code: AnthropicTransportErrorCode,
        *,
        http_status: int | None = None,
        response_received: bool = False,
    ) -> None:
        if not isinstance(code, AnthropicTransportErrorCode):
            raise TypeError("code must be an AnthropicTransportErrorCode")
        if http_status is not None and (
            type(http_status) is not int or not 100 <= http_status <= 599
        ):
            raise ValueError("http_status must be between 100 and 599")
        if type(response_received) is not bool:
            raise TypeError("response_received must be a bool")
        self.code = code
        self.http_status = http_status
        self.response_received = response_received
        super().__init__(code.value)


class AnthropicClientError(RuntimeError):
    """Base signal emitted by an injected client without raw provider details."""

    def __init__(self) -> None:
        super().__init__("ANTHROPIC_CLIENT_ERROR")


class AnthropicClientTimeout(AnthropicClientError):
    def __init__(self) -> None:
        super().__init__()


class AnthropicClientHttpError(AnthropicClientError):
    status_code: int

    def __init__(self, status_code: int) -> None:
        if (
            type(status_code) is not int
            or not 100 <= status_code <= 599
            or 200 <= status_code <= 299
        ):
            raise ValueError("status_code must be an HTTP non-success status")
        self.status_code = status_code
        super().__init__()


@dataclass(frozen=True, slots=True)
class AnthropicTokenPricing:
    uncached_input_per_million_usd: Decimal
    cache_creation_input_per_million_usd: Decimal
    cache_read_input_per_million_usd: Decimal
    output_per_million_usd: Decimal

    def __post_init__(self) -> None:
        for value in (
            self.uncached_input_per_million_usd,
            self.cache_creation_input_per_million_usd,
            self.cache_read_input_per_million_usd,
            self.output_per_million_usd,
        ):
            _require_price(value)


@dataclass(frozen=True, slots=True)
class ResolvedAnthropicConfiguration:
    model: str
    max_tokens: int
    timeout_milliseconds: int
    pricing: AnthropicTokenPricing
    thinking_mode: AnthropicThinkingMode | None = None
    effort: AnthropicEffort | None = None
    retry_count: int = 0
    retain_raw_response: bool = False

    def __post_init__(self) -> None:
        if type(self.model) is not str or _SAFE_MODEL_CODE.fullmatch(self.model) is None:
            raise ValueError("model must be a bounded opaque code")
        if type(self.max_tokens) is not int or not 1 <= self.max_tokens <= _MAX_OUTPUT_TOKENS:
            raise ValueError("max_tokens is outside the adapter limit")
        if (
            type(self.timeout_milliseconds) is not int
            or not 1 <= self.timeout_milliseconds <= _MAX_TIMEOUT_MILLISECONDS
        ):
            raise ValueError("timeout_milliseconds is outside the adapter limit")
        if type(self.pricing) is not AnthropicTokenPricing:
            raise TypeError("pricing must be AnthropicTokenPricing")
        if self.thinking_mode is None and self.effort is not None:
            raise ValueError("effort requires explicit adaptive thinking")
        if self.thinking_mode is not None and (
            self.thinking_mode is not AnthropicThinkingMode.ADAPTIVE
            or self.effort is not AnthropicEffort.LOW
        ):
            raise ValueError("only explicit adaptive thinking at low effort is supported")
        if type(self.retry_count) is not int or self.retry_count != 0:
            raise ValueError("retry and rerun are forbidden")
        if self.retain_raw_response is not False:
            raise ValueError("raw provider response retention is forbidden")


@dataclass(frozen=True, slots=True)
class AnthropicProjectionPayload:
    call_ref: CallRef
    input_json: str = field(repr=False)

    def __post_init__(self) -> None:
        if type(self.call_ref) is not CallRef:
            raise TypeError("call_ref must be a CallRef")
        _require_bounded_text(self.input_json, "input_json")


class AnthropicProjectionSource(Protocol):
    def load(self, call_ref: CallRef) -> AnthropicProjectionPayload: ...


@dataclass(frozen=True, slots=True)
class AnthropicMessage:
    role: AnthropicMessageRole
    content: str = field(repr=False)

    def __post_init__(self) -> None:
        if self.role is not AnthropicMessageRole.USER:
            raise ValueError("only one user data message is supported")
        _require_bounded_text(self.content, "message content")


@dataclass(frozen=True, slots=True)
class AnthropicScoringRequest:
    model: str
    system: str = field(repr=False)
    messages: tuple[AnthropicMessage, ...] = field(repr=False)
    output_schema: dict[str, object] = field(repr=False)
    max_tokens: int
    thinking_mode: AnthropicThinkingMode | None = None
    effort: AnthropicEffort | None = None

    def __post_init__(self) -> None:
        if type(self.model) is not str or _SAFE_MODEL_CODE.fullmatch(self.model) is None:
            raise ValueError("model must be a bounded opaque code")
        _require_bounded_text(self.system, "system")
        if (
            type(self.messages) is not tuple
            or len(self.messages) != 1
            or type(self.messages[0]) is not AnthropicMessage
        ):
            raise ValueError("request requires exactly one typed user message")
        if type(self.output_schema) is not dict or not self.output_schema:
            raise TypeError("output_schema must be a non-empty dictionary")
        if type(self.max_tokens) is not int or not 1 <= self.max_tokens <= _MAX_OUTPUT_TOKENS:
            raise ValueError("max_tokens is outside the adapter limit")
        if self.thinking_mode is None and self.effort is not None:
            raise ValueError("effort requires explicit adaptive thinking")
        if self.thinking_mode is not None and (
            self.thinking_mode is not AnthropicThinkingMode.ADAPTIVE
            or self.effort is not AnthropicEffort.LOW
        ):
            raise ValueError("only explicit adaptive thinking at low effort is supported")


@dataclass(frozen=True, slots=True)
class AnthropicUsage:
    uncached_input_tokens: int
    cache_creation_input_tokens: int
    cache_read_input_tokens: int
    output_tokens: int

    def __post_init__(self) -> None:
        for value in (
            self.uncached_input_tokens,
            self.cache_creation_input_tokens,
            self.cache_read_input_tokens,
            self.output_tokens,
        ):
            if type(value) is not int or not 0 <= value <= _MAX_USAGE_TOKENS:
                raise ValueError("usage tokens must be bounded non-negative integers")

    @property
    def total_tokens(self) -> int:
        return (
            self.uncached_input_tokens
            + self.cache_creation_input_tokens
            + self.cache_read_input_tokens
            + self.output_tokens
        )


@dataclass(frozen=True, slots=True)
class AnthropicMessageResponse:
    text_blocks: tuple[str, ...] = field(repr=False)
    stop_reason: AnthropicStopReason
    usage: AnthropicUsage
    thinking_block_count: int = 0

    def __post_init__(self) -> None:
        if type(self.text_blocks) is not tuple or any(
            type(block) is not str for block in self.text_blocks
        ):
            raise TypeError("text_blocks must be a tuple of strings")
        if len(self.text_blocks) > 100:
            raise ValueError("too many text blocks")
        if not isinstance(self.stop_reason, AnthropicStopReason):
            raise TypeError("stop_reason must be closed")
        if type(self.usage) is not AnthropicUsage:
            raise TypeError("usage must be AnthropicUsage")
        if (
            type(self.thinking_block_count) is not int
            or not 0 <= self.thinking_block_count <= 100
        ):
            raise ValueError("thinking_block_count must be between 0 and 100")


class AnthropicMessagesClient(Protocol):
    def create(
        self,
        *,
        api_key: str,
        timeout_seconds: float,
        request: AnthropicScoringRequest,
    ) -> AnthropicMessageResponse: ...


class AnthropicScoringTransport(Protocol):
    def create(self, *, request: AnthropicScoringRequest) -> AnthropicMessageResponse: ...


def _require_bounded_text(value: str, field_name: str) -> None:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    if len(value.encode("utf-8")) > _MAX_MESSAGE_BYTES:
        raise ValueError(f"{field_name} exceeds the adapter limit")


def _require_price(value: Decimal) -> None:
    if type(value) is not Decimal or not value.is_finite():
        raise TypeError("prices must be finite Decimal values")
    if not Decimal("0") <= value <= _MAX_PRICE_PER_MILLION_USD:
        raise ValueError("price is outside the adapter limit")
