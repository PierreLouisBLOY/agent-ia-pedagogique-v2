"""Private, provider-specific transport contracts for the OpenAI adapter."""

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


class OpenAITransportErrorCode(StrEnum):
    AUTHENTICATION = "AUTHENTICATION"
    RATE_LIMIT = "RATE_LIMIT"
    TIMEOUT = "TIMEOUT"
    CONNECTION = "CONNECTION"
    SERVER = "SERVER"
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


@dataclass(frozen=True, slots=True)
class OpenAIResponseUsage:
    input_tokens: int | None = None
    cached_input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class OpenAIResponsesResponse:
    status: OpenAIResponseStatus
    output_text: str | None = None
    usage: OpenAIResponseUsage = OpenAIResponseUsage()


class OpenAIResponsesTransport(Protocol):
    def create(self, *, request: OpenAIResponsesRequest) -> OpenAIResponsesResponse: ...


class OpenAIResponsesTransportFactory(Protocol):
    def build(
        self,
        *,
        secret: ProviderSecretValue,
        timeout_seconds: float,
    ) -> OpenAIResponsesTransport: ...
