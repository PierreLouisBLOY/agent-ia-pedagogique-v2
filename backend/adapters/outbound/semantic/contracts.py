"""Private technical contracts for embedding transport and semantic hits."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable

from backend.infrastructure.config.secrets.provider import ProviderSecretValue


class EmbeddingTransportErrorCode(StrEnum):
    AUTHENTICATION = "AUTHENTICATION"
    RATE_LIMIT = "RATE_LIMIT"
    TIMEOUT = "TIMEOUT"
    CONNECTION = "CONNECTION"
    SERVER = "SERVER"
    UNAVAILABLE = "UNAVAILABLE"


class EmbeddingTransportError(RuntimeError):
    """Closed provider failure which never carries an SDK exception or secret."""

    code: EmbeddingTransportErrorCode

    def __init__(self, code: EmbeddingTransportErrorCode) -> None:
        if type(code) is not EmbeddingTransportErrorCode:
            raise TypeError("code must be an EmbeddingTransportErrorCode")
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True, slots=True)
class EmbeddingBatchRequest:
    model_code: str
    inputs: tuple[str, ...]
    dimensions: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.model_code, str) or not self.model_code.strip():
            raise ValueError("model_code must be a non-empty string")
        if type(self.inputs) is not tuple or not self.inputs:
            raise ValueError("inputs must be a non-empty tuple")
        if any(not isinstance(item, str) or not item.strip() for item in self.inputs):
            raise ValueError("embedding inputs must be non-empty strings")
        if self.dimensions is not None and (
            type(self.dimensions) is not int or self.dimensions <= 0
        ):
            raise ValueError("dimensions must be a positive integer or None")


@dataclass(frozen=True, slots=True)
class EmbeddingBatchResponse:
    model_code: str
    vectors: tuple[tuple[float, ...], ...]
    input_tokens: int

    def __post_init__(self) -> None:
        if not isinstance(self.model_code, str) or not self.model_code.strip():
            raise ValueError("model_code must be a non-empty string")
        if type(self.vectors) is not tuple or not self.vectors:
            raise ValueError("vectors must be a non-empty tuple")
        dimension = len(self.vectors[0])
        if dimension <= 0:
            raise ValueError("embedding vectors must not be empty")
        for vector in self.vectors:
            if type(vector) is not tuple or len(vector) != dimension:
                raise ValueError("embedding vectors must share one dimension")
            if any(type(value) is not float or not math.isfinite(value) for value in vector):
                raise ValueError("embedding vectors must contain finite floats")
            if math.sqrt(sum(value * value for value in vector)) == 0:
                raise ValueError("embedding vectors must have a non-zero norm")
        if type(self.input_tokens) is not int or self.input_tokens < 0:
            raise ValueError("input_tokens must be a non-negative integer")

    @property
    def dimension(self) -> int:
        return len(self.vectors[0])


@runtime_checkable
class EmbeddingTransport(Protocol):
    def embed(self, *, request: EmbeddingBatchRequest) -> EmbeddingBatchResponse: ...


@runtime_checkable
class EmbeddingTransportFactory(Protocol):
    def build(
        self,
        *,
        secret: ProviderSecretValue,
        timeout_seconds: float,
    ) -> EmbeddingTransport: ...


@dataclass(frozen=True, slots=True)
class SemanticPassage:
    canonical_object_ref: str
    passage_ref: str
    version_or_checksum: str
    object_type: str
    chunk_type: str
    text: str
    semantic_aliases: tuple[str, ...] = ()
    semantic_context: str | None = None
    semantic_rollup_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in (
            "canonical_object_ref",
            "passage_ref",
            "version_or_checksum",
            "object_type",
            "chunk_type",
            "text",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be a non-empty string")
        if self.semantic_context is not None and (
            not isinstance(self.semantic_context, str)
            or not self.semantic_context.strip()
        ):
            raise ValueError("semantic_context must be a non-empty string or None")
        if type(self.semantic_aliases) is not tuple or any(
            not isinstance(item, str) or not item.strip()
            for item in self.semantic_aliases
        ):
            raise ValueError("semantic_aliases must contain non-empty strings")
        if len(self.semantic_aliases) != len(set(self.semantic_aliases)):
            raise ValueError("semantic_aliases must be unique")
        if type(self.semantic_rollup_refs) is not tuple or any(
            not isinstance(item, str) or not item.strip()
            for item in self.semantic_rollup_refs
        ):
            raise ValueError("semantic_rollup_refs must contain non-empty strings")
        if len(self.semantic_rollup_refs) != len(set(self.semantic_rollup_refs)):
            raise ValueError("semantic_rollup_refs must be unique")


@dataclass(frozen=True, slots=True)
class SemanticHit:
    canonical_object_ref: str
    passage_ref: str
    version_or_checksum: str
    object_type: str
    chunk_type: str
    score: float
    matched_passage_ref: str | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "canonical_object_ref",
            "passage_ref",
            "version_or_checksum",
            "object_type",
            "chunk_type",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be a non-empty string")
        if type(self.score) is not float or not math.isfinite(self.score):
            raise ValueError("score must be a finite float")
        if not -1.0 <= self.score <= 1.0:
            raise ValueError("score must be bounded to [-1, 1]")
        if self.matched_passage_ref is not None and (
            not isinstance(self.matched_passage_ref, str)
            or not self.matched_passage_ref.strip()
        ):
            raise ValueError("matched_passage_ref must be a non-empty string or None")


@runtime_checkable
class SemanticSearchBackend(Protocol):
    def search(self, *, text: str, limit: int) -> tuple[SemanticHit, ...]: ...


class SemanticBackendUnavailable(RuntimeError):
    reason_code: str

    def __init__(self, reason_code: str) -> None:
        if not isinstance(reason_code, str) or not reason_code.strip():
            raise ValueError("reason_code must be a non-empty string")
        self.reason_code = reason_code
        super().__init__(reason_code)
