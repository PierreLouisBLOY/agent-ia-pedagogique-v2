"""Official OpenAI Python SDK transport for the Responses API."""

from __future__ import annotations

from typing import cast

import openai
from openai import OpenAI
from openai.types.responses.response import Response
from openai.types.responses.response_create_params import ResponseCreateParamsNonStreaming

from backend.adapters.outbound.openai.contracts import (
    OpenAIResponsesRequest,
    OpenAIResponsesResponse,
    OpenAIResponseStatus,
    OpenAIResponsesTransport,
    OpenAIResponseUsage,
    OpenAITransportError,
    OpenAITransportErrorCode,
)
from backend.adapters.outbound.openai.schema import (
    OpenAIProviderSchemaError,
    validate_openai_strict_schema,
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
        try:
            validate_openai_strict_schema(request.output_schema)
        except OpenAIProviderSchemaError:
            raise OpenAITransportError(OpenAITransportErrorCode.INVALID_REQUEST) from None
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
                        "name": request.schema_name,
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
        except openai.OpenAIError as error:
            raise OpenAITransportError(_openai_error_code(error)) from None
        return _normalized_response(raw_response)


class OpenAISDKResponsesTransportFactory:
    def build(
        self,
        *,
        secret: ProviderSecretValue,
        timeout_seconds: float,
    ) -> OpenAIResponsesTransport:
        return OpenAISDKResponsesTransport(secret=secret, timeout_seconds=timeout_seconds)


def _normalized_response(response: Response) -> OpenAIResponsesResponse:
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
        status=_response_status(response),
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
    return any(
        getattr(content, "type", None) == "refusal"
        for item in response.output
        for content in getattr(item, "content", ())
    )


def _openai_error_code(error: openai.OpenAIError) -> OpenAITransportErrorCode:
    if isinstance(error, openai.APITimeoutError):
        return OpenAITransportErrorCode.TIMEOUT
    if isinstance(error, openai.APIConnectionError):
        return OpenAITransportErrorCode.CONNECTION
    if isinstance(error, openai.BadRequestError):
        return OpenAITransportErrorCode.INVALID_REQUEST
    if isinstance(error, openai.AuthenticationError):
        return OpenAITransportErrorCode.AUTHENTICATION
    if isinstance(error, openai.PermissionDeniedError):
        return OpenAITransportErrorCode.PERMISSION
    if isinstance(error, openai.NotFoundError):
        return OpenAITransportErrorCode.NOT_FOUND
    if isinstance(error, openai.RateLimitError):
        return OpenAITransportErrorCode.RATE_LIMIT
    if isinstance(error, openai.InternalServerError):
        return OpenAITransportErrorCode.SERVER
    if isinstance(error, openai.APIStatusError):
        return _openai_status_code(error.status_code)
    return OpenAITransportErrorCode.UNAVAILABLE


def _openai_status_code(status_code: int) -> OpenAITransportErrorCode:
    mapping = {
        400: OpenAITransportErrorCode.INVALID_REQUEST,
        401: OpenAITransportErrorCode.AUTHENTICATION,
        402: OpenAITransportErrorCode.BILLING,
        403: OpenAITransportErrorCode.PERMISSION,
        404: OpenAITransportErrorCode.NOT_FOUND,
        429: OpenAITransportErrorCode.RATE_LIMIT,
    }
    if status_code >= 500:
        return OpenAITransportErrorCode.SERVER
    return mapping.get(status_code, OpenAITransportErrorCode.UNAVAILABLE)
