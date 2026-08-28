from __future__ import annotations

from backend.adapters.outbound.openai.contracts import (
    OpenAIResponsesRequest,
    OpenAIResponsesResponse,
    OpenAIResponsesTransport,
    OpenAITransportError,
)
from backend.infrastructure.config.secrets.provider import ProviderSecretValue


class RecordingOpenAIResponsesTransport:
    def __init__(
        self,
        *,
        response: OpenAIResponsesResponse | None = None,
        error: OpenAITransportError | None = None,
    ) -> None:
        self.response = response
        self.error = error
        self.calls: list[OpenAIResponsesRequest] = []

    def create(self, *, request: OpenAIResponsesRequest) -> OpenAIResponsesResponse:
        self.calls.append(request)
        if self.error is not None:
            raise self.error
        if self.response is None:
            raise AssertionError("fake transport requires a response or error")
        return self.response


class RecordingOpenAITransportFactory:
    def __init__(self, transport: OpenAIResponsesTransport) -> None:
        self.transport = transport
        self.build_calls: list[tuple[str, float]] = []

    def build(
        self,
        *,
        secret: ProviderSecretValue,
        timeout_seconds: float,
    ) -> OpenAIResponsesTransport:
        self.build_calls.append((repr(secret), timeout_seconds))
        return self.transport
