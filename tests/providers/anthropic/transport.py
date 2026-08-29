"""Official Anthropic SDK transport used only by offline calibration tests."""

from __future__ import annotations

from copy import deepcopy
from typing import cast

import anthropic
from anthropic import Anthropic

from backend.infrastructure.config.secrets.provider import ProviderSecretValue
from tests.providers.anthropic.contracts import (
    AnthropicScoringRequest,
    AnthropicScoringResponse,
    AnthropicScoringTransport,
    AnthropicTransportError,
    AnthropicTransportErrorCode,
)


class AnthropicSDKScoringTransport:
    """One non-streaming, tool-free Messages call with SDK retries disabled."""

    __slots__ = ("__client",)

    def __init__(self, *, secret: ProviderSecretValue, timeout_seconds: float) -> None:
        if type(secret) is not ProviderSecretValue:
            raise TypeError("secret must be a ProviderSecretValue")
        if type(timeout_seconds) is not float or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be a positive float")
        self.__client = Anthropic(
            api_key=secret.reveal_for_transport(),
            timeout=timeout_seconds,
            max_retries=0,
        )

    def __repr__(self) -> str:
        return "AnthropicSDKScoringTransport([REDACTED])"

    def create(self, *, request: AnthropicScoringRequest) -> AnthropicScoringResponse:
        provider_schema = transform_anthropic_provider_schema(request.output_schema)
        try:
            response = self.__client.messages.create(
                model=request.model,
                max_tokens=request.max_tokens,
                system=request.system,
                messages=[{"role": "user", "content": request.input_json}],
                output_config={
                    "format": {
                        "type": "json_schema",
                        "schema": provider_schema,
                    }
                },
                stream=False,
            )
        except anthropic.AnthropicError as error:
            raise AnthropicTransportError(_anthropic_error_code(error)) from None
        if getattr(response, "stop_reason", None) == "refusal":
            raise AnthropicTransportError(AnthropicTransportErrorCode.REFUSED)
        text = "".join(
            cast(str, block.text)
            for block in response.content
            if getattr(block, "type", None) == "text"
        )
        if not text:
            raise AnthropicTransportError(AnthropicTransportErrorCode.UNAVAILABLE)
        usage = getattr(response, "usage", None)
        input_tokens = _optional_non_negative_int(
            getattr(usage, "input_tokens", None)
        )
        cached_input_tokens = _optional_non_negative_int(
            getattr(usage, "cache_read_input_tokens", None)
        )
        output_tokens = _optional_non_negative_int(
            getattr(usage, "output_tokens", None)
        )
        total_tokens = None
        if input_tokens is not None and output_tokens is not None:
            total_tokens = input_tokens + (cached_input_tokens or 0) + output_tokens
        return AnthropicScoringResponse(
            output_text=text,
            input_tokens=input_tokens,
            cached_input_tokens=cached_input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )


class AnthropicSDKScoringTransportFactory:
    def build(
        self,
        *,
        secret: ProviderSecretValue,
        timeout_seconds: float,
    ) -> AnthropicScoringTransport:
        return AnthropicSDKScoringTransport(
            secret=secret,
            timeout_seconds=timeout_seconds,
        )


def _optional_non_negative_int(value: object) -> int | None:
    return value if type(value) is int and value >= 0 else None


def transform_anthropic_provider_schema(
    source_schema: dict[str, object],
) -> dict[str, object]:
    """Transform a defensive copy while preserving the canonical V2 schema."""

    try:
        transformed = anthropic.transform_schema(deepcopy(source_schema))
    except (TypeError, ValueError):
        raise AnthropicTransportError(AnthropicTransportErrorCode.INVALID_REQUEST) from None
    if type(transformed) is not dict:
        raise AnthropicTransportError(AnthropicTransportErrorCode.INVALID_REQUEST)
    return cast(dict[str, object], transformed)


def _anthropic_error_code(error: anthropic.AnthropicError) -> AnthropicTransportErrorCode:
    if isinstance(error, (anthropic.APITimeoutError, anthropic.DeadlineExceededError)):
        return AnthropicTransportErrorCode.TIMEOUT
    if isinstance(error, anthropic.APIConnectionError):
        return AnthropicTransportErrorCode.CONNECTION
    if isinstance(error, anthropic.BadRequestError):
        return AnthropicTransportErrorCode.INVALID_REQUEST
    if isinstance(error, anthropic.AuthenticationError):
        return AnthropicTransportErrorCode.AUTHENTICATION
    if isinstance(error, anthropic.PermissionDeniedError):
        return AnthropicTransportErrorCode.PERMISSION
    if isinstance(error, anthropic.NotFoundError):
        return AnthropicTransportErrorCode.NOT_FOUND
    if isinstance(error, anthropic.RateLimitError):
        return AnthropicTransportErrorCode.RATE_LIMIT
    if isinstance(
        error,
        (
            anthropic.InternalServerError,
            anthropic.OverloadedError,
            anthropic.ServiceUnavailableError,
        ),
    ):
        return AnthropicTransportErrorCode.SERVER
    if isinstance(error, anthropic.APIStatusError):
        return _anthropic_status_code(error.status_code)
    return AnthropicTransportErrorCode.UNAVAILABLE


def _anthropic_status_code(status_code: int) -> AnthropicTransportErrorCode:
    mapping = {
        400: AnthropicTransportErrorCode.INVALID_REQUEST,
        401: AnthropicTransportErrorCode.AUTHENTICATION,
        402: AnthropicTransportErrorCode.BILLING,
        403: AnthropicTransportErrorCode.PERMISSION,
        404: AnthropicTransportErrorCode.NOT_FOUND,
        429: AnthropicTransportErrorCode.RATE_LIMIT,
    }
    if status_code >= 500:
        return AnthropicTransportErrorCode.SERVER
    return mapping.get(status_code, AnthropicTransportErrorCode.UNAVAILABLE)
