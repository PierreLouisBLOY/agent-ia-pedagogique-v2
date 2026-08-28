"""Official Anthropic SDK transport used only by offline calibration tests."""

from __future__ import annotations

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
        try:
            response = self.__client.messages.create(
                model=request.model,
                max_tokens=request.max_tokens,
                system=request.system,
                messages=[{"role": "user", "content": request.input_json}],
                output_config={
                    "format": {
                        "type": "json_schema",
                        "schema": request.output_schema,
                    }
                },
                stream=False,
            )
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError):
            raise AnthropicTransportError(
                AnthropicTransportErrorCode.AUTHENTICATION
            ) from None
        except anthropic.RateLimitError:
            raise AnthropicTransportError(AnthropicTransportErrorCode.RATE_LIMIT) from None
        except (anthropic.APITimeoutError, anthropic.DeadlineExceededError):
            raise AnthropicTransportError(AnthropicTransportErrorCode.TIMEOUT) from None
        except anthropic.APIConnectionError:
            raise AnthropicTransportError(AnthropicTransportErrorCode.CONNECTION) from None
        except (
            anthropic.InternalServerError,
            anthropic.OverloadedError,
            anthropic.ServiceUnavailableError,
        ):
            raise AnthropicTransportError(AnthropicTransportErrorCode.SERVER) from None
        except (anthropic.APIStatusError, anthropic.APIError):
            raise AnthropicTransportError(AnthropicTransportErrorCode.UNAVAILABLE) from None
        if getattr(response, "stop_reason", None) == "refusal":
            raise AnthropicTransportError(AnthropicTransportErrorCode.REFUSED)
        text = "".join(
            cast(str, block.text)
            for block in response.content
            if getattr(block, "type", None) == "text"
        )
        if not text:
            raise AnthropicTransportError(AnthropicTransportErrorCode.UNAVAILABLE)
        return AnthropicScoringResponse(output_text=text)


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
