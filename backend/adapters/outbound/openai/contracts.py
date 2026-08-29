"""Private provider-specific contracts for the shared OpenAI transport."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from backend.infrastructure.config.secrets.provider import ProviderSecretValue


class OpenAIResponseStatus(StrEnum):
    COMPLETED = "completed"
    INCOMPLETE = "incomplete"
    FAILED = "failed"
    REFUSED = "refused"


class OpenAIIncompleteReason(StrEnum):
    NONE = "none"
    MAX_OUTPUT_TOKENS = "max_output_tokens"
    CONTENT_FILTER = "content_filter"
    OTHER = "other"


class OpenAIReasoningEffort(StrEnum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    XHIGH = "xhigh"
    MAX = "max"


class OpenAITransportErrorCode(StrEnum):
    INVALID_REQUEST = "INVALID_REQUEST"
    AUTHENTICATION = "AUTHENTICATION"
    PERMISSION = "PERMISSION"
    BILLING = "BILLING"
    RATE_LIMIT = "RATE_LIMIT"
    NOT_FOUND = "NOT_FOUND"
    TIMEOUT = "TIMEOUT"
    CONNECTION = "CONNECTION"
    SERVER = "SERVER"
    REFUSED = "REFUSED"
    UNAVAILABLE = "UNAVAILABLE"


class OpenAITransportError(RuntimeError):
    """Closed transport failure that never exposes an SDK exception."""

    code: OpenAITransportErrorCode

    def __init__(self, code: OpenAITransportErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True, slots=True)
class OpenAIResponsesRequest:
    model: str
    instructions: str
    input_json: str
    output_schema: dict[str, object]
    max_output_tokens: int
    schema_name: str
    reasoning_effort: OpenAIReasoningEffort | None = None


@dataclass(frozen=True, slots=True)
class OpenAIResponseUsage:
    input_tokens: int | None = None
    cached_input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    reasoning_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class OpenAIResponsesResponse:
    status: OpenAIResponseStatus
    output_text: str | None = None
    usage: OpenAIResponseUsage = OpenAIResponseUsage()
    incomplete_reason: OpenAIIncompleteReason = OpenAIIncompleteReason.NONE


class OpenAIResponsesTransport(Protocol):
    def create(self, *, request: OpenAIResponsesRequest) -> OpenAIResponsesResponse: ...


class OpenAIResponsesTransportFactory(Protocol):
    def build(
        self,
        *,
        secret: ProviderSecretValue,
        timeout_seconds: float,
    ) -> OpenAIResponsesTransport: ...
