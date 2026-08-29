"""Official OpenAI SDK transport for embeddings with retries disabled."""

from __future__ import annotations

from typing import Any

import openai
from openai import OpenAI

from backend.adapters.outbound.semantic.contracts import (
    EmbeddingBatchRequest,
    EmbeddingBatchResponse,
    EmbeddingTransport,
    EmbeddingTransportError,
    EmbeddingTransportErrorCode,
)
from backend.infrastructure.config.secrets.provider import ProviderSecretValue


class OpenAISDKEmbeddingTransport:
    __slots__ = ("__client",)

    def __init__(self, *, secret: ProviderSecretValue, timeout_seconds: float) -> None:
        if type(secret) is not ProviderSecretValue:
            raise TypeError("secret must be a ProviderSecretValue")
        if type(timeout_seconds) is not float or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be a positive float")
        self.__client = OpenAI(
            api_key=secret.reveal_for_transport(),
            timeout=timeout_seconds,
            max_retries=0,
        )

    def __repr__(self) -> str:
        return "OpenAISDKEmbeddingTransport([REDACTED])"

    def embed(self, *, request: EmbeddingBatchRequest) -> EmbeddingBatchResponse:
        parameters: dict[str, Any] = {
            "encoding_format": "float",
            "input": list(request.inputs),
            "model": request.model_code,
        }
        if request.dimensions is not None:
            parameters["dimensions"] = request.dimensions
        try:
            raw = self.__client.embeddings.create(**parameters)
        except (openai.AuthenticationError, openai.PermissionDeniedError):
            raise EmbeddingTransportError(
                EmbeddingTransportErrorCode.AUTHENTICATION
            ) from None
        except openai.RateLimitError:
            raise EmbeddingTransportError(EmbeddingTransportErrorCode.RATE_LIMIT) from None
        except openai.APITimeoutError:
            raise EmbeddingTransportError(EmbeddingTransportErrorCode.TIMEOUT) from None
        except openai.APIConnectionError:
            raise EmbeddingTransportError(EmbeddingTransportErrorCode.CONNECTION) from None
        except openai.InternalServerError:
            raise EmbeddingTransportError(EmbeddingTransportErrorCode.SERVER) from None
        except (openai.APIStatusError, openai.APIError):
            raise EmbeddingTransportError(EmbeddingTransportErrorCode.UNAVAILABLE) from None
        ordered = tuple(sorted(raw.data, key=lambda item: item.index))
        return EmbeddingBatchResponse(
            model_code=raw.model,
            vectors=tuple(
                tuple(float(value) for value in item.embedding) for item in ordered
            ),
            input_tokens=raw.usage.prompt_tokens,
        )


class OpenAISDKEmbeddingTransportFactory:
    def build(
        self,
        *,
        secret: ProviderSecretValue,
        timeout_seconds: float,
    ) -> EmbeddingTransport:
        return OpenAISDKEmbeddingTransport(
            secret=secret,
            timeout_seconds=timeout_seconds,
        )
