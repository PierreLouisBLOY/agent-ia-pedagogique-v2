"""Private transport seam for the offline Anthropic scorer."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from backend.infrastructure.config.secrets.provider import ProviderSecretValue


class AnthropicTransportErrorCode(StrEnum):
    AUTHENTICATION = "AUTHENTICATION"
    RATE_LIMIT = "RATE_LIMIT"
    TIMEOUT = "TIMEOUT"
    CONNECTION = "CONNECTION"
    SERVER = "SERVER"
    REFUSED = "REFUSED"
    UNAVAILABLE = "UNAVAILABLE"


class AnthropicTransportError(RuntimeError):
    """Closed provider failure with no raw SDK payload or message."""

    code: AnthropicTransportErrorCode

    def __init__(self, code: AnthropicTransportErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


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


class AnthropicScoringTransport(Protocol):
    def create(self, *, request: AnthropicScoringRequest) -> AnthropicScoringResponse: ...


class AnthropicScoringTransportFactory(Protocol):
    def build(
        self,
        *,
        secret: ProviderSecretValue,
        timeout_seconds: float,
    ) -> AnthropicScoringTransport: ...
