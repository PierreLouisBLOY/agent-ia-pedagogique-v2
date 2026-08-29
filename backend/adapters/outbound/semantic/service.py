"""Configured embedding service with bounded input and closed validation."""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.adapters.outbound.semantic.contracts import (
    EmbeddingBatchRequest,
    EmbeddingBatchResponse,
    EmbeddingTransport,
    EmbeddingTransportFactory,
)
from backend.infrastructure.config.schemas.provider import (
    EmbeddingProfileConfig,
    ProviderProfileConfig,
)
from backend.infrastructure.config.secrets.provider import ProviderSecretResolver

_MAX_INPUTS_PER_REQUEST = 2_048


@dataclass(frozen=True, slots=True)
class ConfiguredEmbeddingService:
    provider_profile: ProviderProfileConfig
    embedding_profile: EmbeddingProfileConfig
    secret_resolver: ProviderSecretResolver
    transport_factory: EmbeddingTransportFactory
    _transport: EmbeddingTransport = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if type(self.provider_profile) is not ProviderProfileConfig:
            raise TypeError("provider_profile must be a ProviderProfileConfig")
        if type(self.embedding_profile) is not EmbeddingProfileConfig:
            raise TypeError("embedding_profile must be an EmbeddingProfileConfig")
        if not isinstance(self.secret_resolver, ProviderSecretResolver):
            raise TypeError("secret_resolver must satisfy ProviderSecretResolver")
        if not isinstance(self.transport_factory, EmbeddingTransportFactory):
            raise TypeError("transport_factory must satisfy EmbeddingTransportFactory")
        if (
            self.embedding_profile.provider_profile_id
            != self.provider_profile.profile_id
        ):
            raise ValueError("embedding and provider profile references must match")
        secret = self.secret_resolver.resolve(self.provider_profile.credential_ref)
        object.__setattr__(
            self,
            "_transport",
            self.transport_factory.build(
                secret=secret,
                timeout_seconds=(
                    self.embedding_profile.call_timeout_milliseconds / 1_000.0
                ),
            ),
        )

    def embed(self, inputs: tuple[str, ...]) -> EmbeddingBatchResponse:
        if type(inputs) is not tuple or not inputs:
            raise ValueError("inputs must be a non-empty tuple")
        if len(inputs) > _MAX_INPUTS_PER_REQUEST:
            raise ValueError("embedding request contains too many inputs")
        conservative_tokens = tuple(len(item.encode("utf-8")) for item in inputs)
        if any(value <= 0 for value in conservative_tokens):
            raise ValueError("embedding inputs must be non-empty")
        if any(
            value > self.embedding_profile.max_input_tokens_per_item
            for value in conservative_tokens
        ):
            raise ValueError("embedding input exceeds configured per-item limit")
        if sum(conservative_tokens) > self.embedding_profile.max_batch_input_tokens:
            raise ValueError("embedding request exceeds configured batch limit")
        response = self._transport.embed(
            request=EmbeddingBatchRequest(
                model_code=self.embedding_profile.model_code.value,
                inputs=inputs,
                dimensions=self.embedding_profile.requested_dimensions,
            )
        )
        if response.model_code != self.embedding_profile.model_code.value:
            raise ValueError("embedding response model does not match configuration")
        if len(response.vectors) != len(inputs):
            raise ValueError("embedding response count does not match request")
        requested = self.embedding_profile.requested_dimensions
        if requested is not None and response.dimension != requested:
            raise ValueError("embedding response dimension does not match configuration")
        return response

    def batches(self, inputs: tuple[str, ...]) -> tuple[tuple[str, ...], ...]:
        if type(inputs) is not tuple:
            raise TypeError("inputs must be a tuple")
        batches: list[tuple[str, ...]] = []
        current: list[str] = []
        current_bound = 0
        for item in inputs:
            item_bound = len(item.encode("utf-8"))
            if item_bound <= 0 or (
                item_bound > self.embedding_profile.max_input_tokens_per_item
            ):
                raise ValueError("embedding input exceeds configured per-item limit")
            if current and (
                len(current) >= _MAX_INPUTS_PER_REQUEST
                or current_bound + item_bound
                > self.embedding_profile.max_batch_input_tokens
            ):
                batches.append(tuple(current))
                current = []
                current_bound = 0
            current.append(item)
            current_bound += item_bound
        if current:
            batches.append(tuple(current))
        return tuple(batches)
