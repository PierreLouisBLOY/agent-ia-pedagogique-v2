"""Bounded model GET through the product's fixed destination SDK constructor."""
from __future__ import annotations

import re

import openai

from backend.adapters.outbound.openai.contracts import OpenAITransportError
from backend.adapters.outbound.openai.transport import build_fixed_r2_client
from backend.infrastructure.config.secrets.provider import (
    ProviderCredentialRef,
    ProviderSecretError,
    ProviderSecretResolver,
)


class OpenAIModelMetadataReader:
    def __init__(self, resolver: ProviderSecretResolver,
                 credential_ref: ProviderCredentialRef, *, model: str) -> None:
        if model != "gpt-5.6-terra":
            raise ValueError("P0_AUTHENTICATION_MODEL_REJECTED")
        self.resolver, self.ref, self.model = resolver, credential_ref, model
        self._used = False

    def read(self) -> dict[str, object]:
        if self._used:
            raise ValueError("P0_AUTHENTICATION_DIAGNOSTIC_ALREADY_USED")
        self._used = True
        result: dict[str, object] = {"state": "LOCAL_CONFIGURATION_REJECTED",
            "model": self.model, "http_status": None, "request_id": None,
            "error_type": None, "error_code": None, "attempts": 0, "retries": 0}
        client = None
        try:
            secret = self.resolver.resolve(self.ref)
            client = build_fixed_r2_client(secret=secret, timeout_seconds=12.0,
                environment_key_allowed=True)
            result["attempts"] = 1
            model = client.models.retrieve(self.model)
            result.update(state="AUTHENTICATED" if model.id == self.model else "MODEL_MISMATCH",
                http_status=200, request_id=_label(getattr(model, "_request_id", None)))
        except openai.APIStatusError as error:
            result.update(state=("AUTHENTICATION_REJECTED" if error.status_code == 401 else
                "ACCESS_REJECTED" if error.status_code in {403, 404} else "HTTP_ERROR"),
                http_status=error.status_code, request_id=_label(error.request_id),
                error_type=type(error).__name__, error_code=_code(error.code))
        except openai.APIConnectionError as error:
            result.update(state="TRANSPORT_UNAVAILABLE", error_type=type(error).__name__)
        except (ProviderSecretError, OpenAITransportError, ValueError) as error:
            result.update(error_type=type(error).__name__)
        except Exception:  # noqa: BLE001 - only a closed error label crosses the transport boundary
            result.update(state="TRANSPORT_UNAVAILABLE", error_type="UnexpectedTransportError")
        finally:
            if client is not None:
                try:
                    client.close()
                except Exception:  # noqa: BLE001 - preserve the observed HTTP outcome after a cleanup failure
                    result["cleanup_error"] = True
        result.setdefault("cleanup_error", False)
        return result


def _label(value: object) -> str | None:
    return value if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value) else None


def _code(value: object) -> str | None:
    return value if isinstance(value, str) and value in {"invalid_api_key", "insufficient_quota", "model_not_found",
        "permission_denied", "rate_limit_exceeded", "invalid_request_error"} else None
