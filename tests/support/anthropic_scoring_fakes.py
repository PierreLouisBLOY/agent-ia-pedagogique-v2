from __future__ import annotations

from backend.infrastructure.config.secrets.provider import ProviderSecretValue
from tests.providers.anthropic.contracts import (
    AnthropicScoringRequest,
    AnthropicScoringResponse,
    AnthropicScoringTransport,
    AnthropicTransportError,
)


class RecordingAnthropicScoringTransport:
    def __init__(
        self,
        *,
        response: AnthropicScoringResponse | None = None,
        error: AnthropicTransportError | None = None,
    ) -> None:
        self.response = response
        self.error = error
        self.calls: list[AnthropicScoringRequest] = []

    def create(self, *, request: AnthropicScoringRequest) -> AnthropicScoringResponse:
        self.calls.append(request)
        if self.error is not None:
            raise self.error
        if self.response is None:
            raise AssertionError("fake transport requires a response or error")
        return self.response


class RecordingAnthropicScoringTransportFactory:
    def __init__(self, transport: AnthropicScoringTransport) -> None:
        self.transport = transport
        self.build_calls: list[tuple[str, float]] = []

    def build(
        self,
        *,
        secret: ProviderSecretValue,
        timeout_seconds: float,
    ) -> AnthropicScoringTransport:
        self.build_calls.append((repr(secret), timeout_seconds))
        return self.transport
