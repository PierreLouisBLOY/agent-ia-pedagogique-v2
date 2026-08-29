from __future__ import annotations

import math

import pytest

from backend.adapters.outbound.semantic import (
    ConfiguredEmbeddingService,
    EmbeddingBatchResponse,
)
from backend.infrastructure.config.schemas.provider import (
    EmbeddingProfileConfig,
    ModelCode,
    ModelProfileId,
    ProviderCode,
    ProviderProfileConfig,
    ProviderProfileId,
)
from backend.infrastructure.config.secrets.provider import (
    EnvironmentProviderSecretResolver,
    ProviderCredentialRef,
)
from tests.support.semantic_embedding_fakes import (
    RecordingEmbeddingTransport,
    RecordingEmbeddingTransportFactory,
)


def _service(
    transport: RecordingEmbeddingTransport,
    *,
    dimensions: int | None = 4,
    per_item: int = 8_192,
    per_batch: int = 300_000,
) -> ConfiguredEmbeddingService:
    return ConfiguredEmbeddingService(
        provider_profile=ProviderProfileConfig(
            ProviderProfileId("openai-embedding"),
            ProviderCode("openai"),
            ProviderCredentialRef("OPENAI_API_KEY"),
        ),
        embedding_profile=EmbeddingProfileConfig(
            ModelProfileId("embedding-model"),
            ProviderProfileId("openai-embedding"),
            ModelCode("text-embedding-3-small"),
            per_item,
            per_batch,
            30_000,
            dimensions,
        ),
        secret_resolver=EnvironmentProviderSecretResolver(
            {"OPENAI_API_KEY": "synthetic-secret-never-rendered"}
        ),
        transport_factory=RecordingEmbeddingTransportFactory(transport),
    )


def test_service_batches_by_count_and_conservative_utf8_bound() -> None:
    service = _service(
        RecordingEmbeddingTransport(),
        per_item=4,
        per_batch=6,
    )

    assert service.batches(("aa", "bbb", "c", "dd")) == (
        ("aa", "bbb", "c"),
        ("dd",),
    )


@pytest.mark.parametrize("inputs", [(), ("",), ("12345",)])
def test_service_rejects_empty_or_oversized_inputs(inputs: tuple[str, ...]) -> None:
    service = _service(
        RecordingEmbeddingTransport(),
        per_item=4,
        per_batch=8,
    )

    with pytest.raises(ValueError):
        service.embed(inputs)


def test_service_rejects_response_dimension_or_count_mismatch() -> None:
    wrong_dimension = _service(
        RecordingEmbeddingTransport(
            response=EmbeddingBatchResponse(
                "text-embedding-3-small",
                ((1.0, 0.0, 0.0),),
                1,
            )
        )
    )
    with pytest.raises(ValueError, match="dimension"):
        wrong_dimension.embed(("query",))

    wrong_count = _service(
        RecordingEmbeddingTransport(
            response=EmbeddingBatchResponse(
                "text-embedding-3-small",
                ((1.0, 0.0, 0.0, 0.0), (0.0, 1.0, 0.0, 0.0)),
                1,
            )
        )
    )
    with pytest.raises(ValueError, match="count"):
        wrong_count.embed(("query",))


@pytest.mark.parametrize(
    "vectors",
    [
        ((1.0, 0.0), (1.0,)),
        ((math.inf, 0.0),),
        ((0.0, 0.0),),
    ],
)
def test_embedding_response_rejects_malformed_vectors(
    vectors: tuple[tuple[float, ...], ...],
) -> None:
    with pytest.raises(ValueError):
        EmbeddingBatchResponse("model", vectors, 1)


def test_secret_is_redacted_across_service_and_factory() -> None:
    transport = RecordingEmbeddingTransport()
    factory = RecordingEmbeddingTransportFactory(transport)
    service = ConfiguredEmbeddingService(
        provider_profile=ProviderProfileConfig(
            ProviderProfileId("provider"),
            ProviderCode("openai"),
            ProviderCredentialRef("OPENAI_API_KEY"),
        ),
        embedding_profile=EmbeddingProfileConfig(
            ModelProfileId("embedding"),
            ProviderProfileId("provider"),
            ModelCode("text-embedding-3-small"),
            8_192,
            300_000,
            20_000,
            4,
        ),
        secret_resolver=EnvironmentProviderSecretResolver(
            {"OPENAI_API_KEY": "synthetic-secret-never-rendered"}
        ),
        transport_factory=factory,
    )

    assert "synthetic-secret-never-rendered" not in repr(service)
    assert factory.build_calls == [("ProviderSecretValue([REDACTED])", 20.0)]
