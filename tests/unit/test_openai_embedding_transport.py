from __future__ import annotations

from types import SimpleNamespace

import pytest

import backend.adapters.outbound.semantic.openai as openai_adapter
from backend.adapters.outbound.semantic import (
    EmbeddingBatchRequest,
    EmbeddingTransportError,
    EmbeddingTransportErrorCode,
    OpenAISDKEmbeddingTransport,
)
from backend.infrastructure.config.secrets.provider import ProviderSecretValue


class _Embeddings:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[dict[str, object]] = []

    def create(self, **parameters: object) -> object:
        self.calls.append(parameters)
        if self.error is not None:
            raise self.error
        return SimpleNamespace(
            model="text-embedding-3-small",
            data=(
                SimpleNamespace(index=1, embedding=(0.0, 1.0)),
                SimpleNamespace(index=0, embedding=(1.0, 0.0)),
            ),
            usage=SimpleNamespace(prompt_tokens=7),
        )


class _Client:
    def __init__(self, embeddings: _Embeddings) -> None:
        self.embeddings = embeddings


def test_openai_transport_uses_embedding_endpoint_and_orders_vectors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    embeddings = _Embeddings()
    client_parameters: list[dict[str, object]] = []

    def build_client(**parameters: object) -> _Client:
        client_parameters.append(parameters)
        return _Client(embeddings)

    monkeypatch.setattr(openai_adapter, "OpenAI", build_client)
    transport = OpenAISDKEmbeddingTransport(
        secret=ProviderSecretValue("synthetic-secret-never-rendered"),
        timeout_seconds=12.5,
    )

    response = transport.embed(
        request=EmbeddingBatchRequest(
            "text-embedding-3-small",
            ("alpha", "beta"),
            256,
        )
    )

    assert response.vectors == ((1.0, 0.0), (0.0, 1.0))
    assert response.input_tokens == 7
    assert embeddings.calls == [
        {
            "dimensions": 256,
            "encoding_format": "float",
            "input": ["alpha", "beta"],
            "model": "text-embedding-3-small",
        }
    ]
    assert client_parameters[0]["max_retries"] == 0
    assert client_parameters[0]["timeout"] == 12.5
    assert "synthetic-secret-never-rendered" not in repr(transport)


@pytest.mark.parametrize(
    ("raised_name", "expected"),
    [
        ("AuthenticationError", EmbeddingTransportErrorCode.AUTHENTICATION),
        ("RateLimitError", EmbeddingTransportErrorCode.RATE_LIMIT),
        ("APITimeoutError", EmbeddingTransportErrorCode.TIMEOUT),
    ],
)
def test_openai_transport_maps_provider_failures_to_closed_codes(
    monkeypatch: pytest.MonkeyPatch,
    raised_name: str,
    expected: EmbeddingTransportErrorCode,
) -> None:
    error_types = {
        name: type(f"Synthetic{name}", (Exception,), {})
        for name in (
            "AuthenticationError",
            "PermissionDeniedError",
            "RateLimitError",
            "APITimeoutError",
            "APIConnectionError",
            "InternalServerError",
            "APIStatusError",
            "APIError",
        )
    }
    for name, error_type in error_types.items():
        monkeypatch.setattr(openai_adapter.openai, name, error_type)
    embeddings = _Embeddings(error=error_types[raised_name]())
    monkeypatch.setattr(
        openai_adapter,
        "OpenAI",
        lambda **_parameters: _Client(embeddings),
    )
    transport = OpenAISDKEmbeddingTransport(
        secret=ProviderSecretValue("synthetic"),
        timeout_seconds=10.0,
    )

    with pytest.raises(EmbeddingTransportError) as raised:
        transport.embed(
            request=EmbeddingBatchRequest(
                "text-embedding-3-small",
                ("query",),
            )
        )
    assert raised.value.code is expected
    assert str(raised.value) == expected.value
