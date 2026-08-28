"""Official OpenAI Python SDK transport for the Responses API."""

from __future__ import annotations

from typing import cast

import openai
from openai import OpenAI
from openai.types.responses.response import Response
from openai.types.responses.response_create_params import ResponseCreateParamsNonStreaming

from backend.adapters.outbound.generation.openai.contracts import (
    OpenAIResponsesRequest,
    OpenAIResponsesResponse,
    OpenAIResponseStatus,
    OpenAIResponsesTransport,
    OpenAIResponseUsage,
    OpenAITransportError,
    OpenAITransportErrorCode,
)
from backend.infrastructure.config.secrets.provider import ProviderSecretValue


class OpenAISDKResponsesTransport:
    """One-shot Responses transport; retry and fallback remain external concerns."""

    __slots__ = ("__client",)

    def __init__(self, *, secret: ProviderSecretValue, timeout_seconds: float) -> None:
        if type(secret) is not ProviderSecretValue:
            raise TypeError("secret must be a ProviderSecretValue")
        if not isinstance(timeout_seconds, float) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be a positive float")
        self.__client = OpenAI(
            api_key=secret.reveal_for_transport(),
            timeout=timeout_seconds,
            max_retries=0,
        )

    def __repr__(self) -> str:
        return "OpenAISDKResponsesTransport([REDACTED])"

    def create(self, *, request: OpenAIResponsesRequest) -> OpenAIResponsesResponse:
        parameters = cast(
            ResponseCreateParamsNonStreaming,
            {
                "background": False,
                "input": request.input_json,
                "instructions": request.instructions,
                "max_output_tokens": request.max_output_tokens,
                "model": request.model,
                "store": False,
                "stream": False,
                "text": {
                    "format": {
                        "name": "pedagogical_generation",
                        "schema": request.output_schema,
                        "strict": True,
                        "type": "json_schema",
                    }
                },
                "tool_choice": "none",
                "tools": [],
            },
        )
        try:
            raw_response = self.__client.responses.create(**parameters)
        except (openai.AuthenticationError, openai.PermissionDeniedError):
            raise OpenAITransportError(OpenAITransportErrorCode.AUTHENTICATION) from None
        except openai.RateLimitError:
            raise OpenAITransportError(OpenAITransportErrorCode.RATE_LIMIT) from None
        except openai.APITimeoutError:
            raise OpenAITransportError(OpenAITransportErrorCode.TIMEOUT) from None
        except openai.APIConnectionError:
            raise OpenAITransportError(OpenAITransportErrorCode.CONNECTION) from None
        except openai.InternalServerError:
            raise OpenAITransportError(OpenAITransportErrorCode.SERVER) from None
        except (openai.APIStatusError, openai.APIError):
            raise OpenAITransportError(OpenAITransportErrorCode.UNAVAILABLE) from None
        return _normalized_response(raw_response)


class OpenAISDKResponsesTransportFactory:
    def build(
        self,
        *,
        secret: ProviderSecretValue,
        timeout_seconds: float,
    ) -> OpenAIResponsesTransport:
        return OpenAISDKResponsesTransport(
            secret=secret,
            timeout_seconds=timeout_seconds,
        )


def _normalized_response(response: Response) -> OpenAIResponsesResponse:
    status = _response_status(response)
    usage = response.usage
    normalized_usage = OpenAIResponseUsage()
    if usage is not None:
        normalized_usage = OpenAIResponseUsage(
            input_tokens=usage.input_tokens,
            cached_input_tokens=usage.input_tokens_details.cached_tokens,
            output_tokens=usage.output_tokens,
            total_tokens=usage.total_tokens,
        )
    return OpenAIResponsesResponse(
        status=status,
        output_text=response.output_text or None,
        usage=normalized_usage,
    )


def _response_status(response: Response) -> OpenAIResponseStatus:
    if _contains_refusal(response):
        return OpenAIResponseStatus.REFUSED
    if response.status == "completed":
        return OpenAIResponseStatus.COMPLETED
    if response.status == "incomplete":
        return OpenAIResponseStatus.INCOMPLETE
    return OpenAIResponseStatus.FAILED


def _contains_refusal(response: Response) -> bool:
    for item in response.output:
        content_items = getattr(item, "content", ())
        for content in content_items:
            if getattr(content, "type", None) == "refusal":
                return True
    return False
