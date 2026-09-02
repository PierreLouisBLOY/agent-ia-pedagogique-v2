"""One-shot Anthropic transport against an injected client, with no SDK import."""

from __future__ import annotations

from backend.infrastructure.config.secrets.provider import ProviderSecretValue
from calibration_tooling.adapters.anthropic.contracts import (
    AnthropicClientError,
    AnthropicClientHttpError,
    AnthropicClientTimeout,
    AnthropicMessageResponse,
    AnthropicMessagesClient,
    AnthropicScoringRequest,
    AnthropicTransportError,
    AnthropicTransportErrorCode,
)


class AnthropicMessagesTransport:
    """Perform exactly one injected client call; retry remains impossible here."""

    __slots__ = ("_client", "_secret", "_timeout_seconds")

    def __init__(
        self,
        *,
        client: AnthropicMessagesClient,
        secret: ProviderSecretValue | None,
        timeout_milliseconds: int,
    ) -> None:
        if secret is not None and type(secret) is not ProviderSecretValue:
            raise TypeError("secret must be ProviderSecretValue or None")
        if (
            type(timeout_milliseconds) is not int
            or not 1 <= timeout_milliseconds <= 600_000
        ):
            raise ValueError("timeout_milliseconds is outside the adapter limit")
        self._client = client
        self._secret = secret
        self._timeout_seconds = timeout_milliseconds / 1_000.0

    def __repr__(self) -> str:
        return "AnthropicMessagesTransport([REDACTED])"

    def create(self, *, request: AnthropicScoringRequest) -> AnthropicMessageResponse:
        if type(request) is not AnthropicScoringRequest:
            raise TypeError("request must be AnthropicScoringRequest")
        if self._secret is None:
            raise AnthropicTransportError(
                AnthropicTransportErrorCode.CREDENTIAL_UNAVAILABLE
            ) from None
        try:
            response = self._client.create(
                api_key=self._secret.reveal_for_transport(),
                timeout_seconds=self._timeout_seconds,
                request=request,
            )
        except AnthropicClientHttpError as error:
            raise AnthropicTransportError(
                AnthropicTransportErrorCode.HTTP_ERROR,
                http_status=error.status_code,
                response_received=True,
            ) from None
        except (AnthropicClientTimeout, TimeoutError):
            raise AnthropicTransportError(AnthropicTransportErrorCode.TIMEOUT) from None
        except AnthropicClientError:
            raise AnthropicTransportError(
                AnthropicTransportErrorCode.UNAVAILABLE
            ) from None
        except Exception:
            raise AnthropicTransportError(
                AnthropicTransportErrorCode.UNAVAILABLE
            ) from None
        if type(response) is not AnthropicMessageResponse:
            raise AnthropicTransportError(
                AnthropicTransportErrorCode.RESPONSE_INVALID,
                response_received=True,
            ) from None
        return response
