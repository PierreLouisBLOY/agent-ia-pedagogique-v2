"""Official OpenAI Python SDK transport for the Responses API."""

from __future__ import annotations

import os
from pathlib import Path
from typing import cast

import openai
from openai import DefaultHttpxClient, OpenAI
from openai.types.responses.response import Response
from openai.types.responses.response_create_params import (
    ResponseCreateParamsNonStreaming,
)

from backend.adapters.outbound.openai.contracts import (
    OpenAIIncompleteReason,
    OpenAIResponsesRequest,
    OpenAIResponsesResponse,
    OpenAIResponseStatus,
    OpenAIResponsesTransport,
    OpenAIResponseUsage,
    OpenAITransportError,
    OpenAITransportErrorCode,
)
from backend.adapters.outbound.openai.parameters import response_parameters
from backend.adapters.outbound.openai.schema import (
    OpenAIProviderSchemaError,
    validate_openai_strict_schema,
)
from backend.infrastructure.config.secrets.provider import ProviderSecretValue


def openai_sdk_import_path() -> Path:
    """Private diagnostic metadata only; SDK ownership stays in this adapter."""
    return Path(openai.__file__).resolve()


def build_fixed_r2_client(*, secret: ProviderSecretValue, timeout_seconds: float,
                         environment_key_allowed: bool = False) -> OpenAI:
    """Explicit secret, official destination, and no ambient SDK configuration."""
    if type(secret) is not ProviderSecretValue or type(timeout_seconds) is not float or timeout_seconds <= 0:
        raise ValueError("fixed R2 client requires a valid opaque secret and timeout")
    if type(environment_key_allowed) is not bool:
        raise ValueError("environment_key_allowed must be a boolean")
    if any((name.startswith(("OPENAI_", "AZURE_OPENAI_")) and not
            (environment_key_allowed and name == "OPENAI_API_KEY"))
            or name.upper() in {"HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
                "NO_PROXY", "SSL_CERT_FILE", "SSL_CERT_DIR"} for name in os.environ):
        raise OpenAITransportError(OpenAITransportErrorCode.INVALID_REQUEST)
    return OpenAI(api_key=secret.reveal_for_transport(), timeout=timeout_seconds,
        max_retries=0, base_url="https://api.openai.com/v1", organization="", project="",
        admin_api_key="", webhook_secret="",
        http_client=DefaultHttpxClient(trust_env=False, follow_redirects=False))


class OpenAISDKResponsesTransport:
    """One-shot Responses transport; retry and fallback remain external concerns."""

    __slots__ = ("__client", "__r2")

    def __init__(self, *, secret: ProviderSecretValue, timeout_seconds: float,
                 r2_destination: bool = False,
                 environment_key_allowed: bool = False) -> None:
        if type(secret) is not ProviderSecretValue:
            raise TypeError("secret must be a ProviderSecretValue")
        if not isinstance(timeout_seconds, float) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be a positive float")
        self.__r2 = r2_destination
        if environment_key_allowed and not r2_destination:
            raise ValueError("explicit environment source requires fixed R2 destination")
        if r2_destination:
            self.__client = build_fixed_r2_client(secret=secret,
                timeout_seconds=timeout_seconds,
                environment_key_allowed=environment_key_allowed)
        else:
            self.__client = OpenAI(
                api_key=secret.reveal_for_transport(), timeout=timeout_seconds, max_retries=0,
            )

    def __repr__(self) -> str:
        return "OpenAISDKResponsesTransport([REDACTED])"

    def create(self, *, request: OpenAIResponsesRequest) -> OpenAIResponsesResponse:
        try:
            validate_openai_strict_schema(request.output_schema)
        except OpenAIProviderSchemaError:
            raise OpenAITransportError(OpenAITransportErrorCode.INVALID_REQUEST) from None
        parameters = cast(ResponseCreateParamsNonStreaming, response_parameters(request))
        if self.__r2 and request.service_tier != "default":
            raise OpenAITransportError(OpenAITransportErrorCode.INVALID_REQUEST)
        try:
            raw_response = self.__client.responses.create(**parameters)
        except openai.OpenAIError as error:
            # Closed metadata only: never retain the SDK message, body or key.
            import re

            diagnostic: dict[str, str | int] = {}
            if isinstance(error, openai.APIStatusError):
                diagnostic["http_status"] = error.status_code
                request_id = getattr(error, "request_id", None)
                if isinstance(request_id, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,120}", request_id):
                    diagnostic["request_id"] = request_id
            for name in ("code", "type", "param"):
                value = getattr(error, name, None)
                if isinstance(value, str) and not value.startswith("sk-") and re.fullmatch(r"[A-Za-z0-9_.\[\]-]{1,160}", value):
                    diagnostic[name] = value
            raise OpenAITransportError(_openai_error_code(error), diagnostic=diagnostic) from None
        finally:
            if self.__r2:
                self.__client.close()
        return _normalized_response(raw_response)


class OpenAISDKResponsesTransportFactory:
    def __init__(self, *, r2_destination: bool = False,
                 environment_key_allowed: bool = False) -> None:
        self.r2_destination = r2_destination
        self.environment_key_allowed = environment_key_allowed
        if environment_key_allowed and not r2_destination:
            raise ValueError("explicit environment source requires fixed R2 destination")

    def build(
        self,
        *,
        secret: ProviderSecretValue,
        timeout_seconds: float,
    ) -> OpenAIResponsesTransport:
        if self.r2_destination:
            return OpenAISDKResponsesTransport(secret=secret, timeout_seconds=timeout_seconds,
                r2_destination=True, environment_key_allowed=self.environment_key_allowed)
        return OpenAISDKResponsesTransport(secret=secret, timeout_seconds=timeout_seconds)


def _normalized_response(response: Response) -> OpenAIResponsesResponse:
    usage = response.usage
    normalized_usage = OpenAIResponseUsage()
    if usage is not None:
        output_details = getattr(usage, "output_tokens_details", None)
        normalized_usage = OpenAIResponseUsage(
            input_tokens=usage.input_tokens,
            cached_input_tokens=_optional_non_negative_int(
                getattr(getattr(usage, "input_tokens_details", None), "cached_tokens", None)),
            cache_write_input_tokens=_optional_non_negative_int(
                getattr(getattr(usage, "input_tokens_details", None), "cache_write_tokens", None)),
            output_tokens=usage.output_tokens,
            total_tokens=usage.total_tokens,
            reasoning_tokens=_optional_non_negative_int(
                getattr(output_details, "reasoning_tokens", None)
            ),
        )
    return OpenAIResponsesResponse(
        status=_response_status(response),
        output_text=response.output_text or None,
        usage=normalized_usage,
        service_tier=(response.service_tier if getattr(response, "service_tier", None) in {
            "default", "flex", "priority", "scale", "ultrafast"} else None),
        incomplete_reason=_incomplete_reason(response),
    )


def _incomplete_reason(response: Response) -> OpenAIIncompleteReason:
    details = getattr(response, "incomplete_details", None)
    reason = getattr(details, "reason", None)
    mapping = {
        "max_output_tokens": OpenAIIncompleteReason.MAX_OUTPUT_TOKENS,
        "content_filter": OpenAIIncompleteReason.CONTENT_FILTER,
    }
    if reason is None:
        return OpenAIIncompleteReason.NONE
    return mapping.get(reason, OpenAIIncompleteReason.OTHER)


def _optional_non_negative_int(value: object) -> int | None:
    return value if type(value) is int and value >= 0 else None


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
