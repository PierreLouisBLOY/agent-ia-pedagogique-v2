from __future__ import annotations

import hashlib
import math

from backend.adapters.outbound.semantic import (
    EmbeddingBatchRequest,
    EmbeddingBatchResponse,
    EmbeddingTransport,
)
from backend.infrastructure.config.secrets.provider import ProviderSecretValue


class RecordingEmbeddingTransport:
    def __init__(
        self,
        *,
        dimension: int = 4,
        response: EmbeddingBatchResponse | None = None,
        responses: list[EmbeddingBatchResponse] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.dimension = dimension
        self.response = response
        self.responses = list(responses or ())
        self.error = error
        self.calls: list[EmbeddingBatchRequest] = []

    def embed(self, *, request: EmbeddingBatchRequest) -> EmbeddingBatchResponse:
        self.calls.append(request)
        if self.error is not None:
            raise self.error
        if self.responses:
            return self.responses.pop(0)
        if self.response is not None:
            return self.response
        return EmbeddingBatchResponse(
            model_code=request.model_code,
            vectors=tuple(
                _deterministic_vector(value, self.dimension)
                for value in request.inputs
            ),
            input_tokens=sum(len(value.encode("utf-8")) for value in request.inputs),
        )


class RecordingEmbeddingTransportFactory:
    def __init__(self, transport: EmbeddingTransport) -> None:
        self.transport = transport
        self.build_calls: list[tuple[str, float]] = []

    def build(
        self,
        *,
        secret: ProviderSecretValue,
        timeout_seconds: float,
    ) -> EmbeddingTransport:
        self.build_calls.append((repr(secret), timeout_seconds))
        return self.transport


def _deterministic_vector(value: str, dimension: int) -> tuple[float, ...]:
    digest = hashlib.shake_256(value.encode("utf-8")).digest(dimension * 2)
    values = tuple(
        float(int.from_bytes(digest[index : index + 2], "little") - 32_768)
        for index in range(0, len(digest), 2)
    )
    norm = math.sqrt(sum(item * item for item in values))
    return tuple(item / norm for item in values)
