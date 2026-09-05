"""Pure local-browser HTTP security contract with no server implementation."""

from __future__ import annotations

import hmac
import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Protocol

from backend.infrastructure.config.schemas.http import LocalBrowserHttpConfiguration

_HOST_V4 = re.compile(r"^(localhost|127\.0\.0\.1)(?::([1-9][0-9]{0,4}))?$", re.IGNORECASE)
_HOST_V6 = re.compile(r"^\[::1\](?::([1-9][0-9]{0,4}))?$", re.IGNORECASE)
_SAFE_CODE = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")


class LocalBrowserHttpDecisionCode(StrEnum):
    ALLOWED = "ALLOWED"
    HOST_REJECTED = "HOST_REJECTED"
    ORIGIN_REJECTED = "ORIGIN_REJECTED"
    METHOD_REJECTED = "METHOD_REJECTED"
    PREFLIGHT_REJECTED = "PREFLIGHT_REJECTED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class HttpObservabilityPort(Protocol):
    def correlation_id(self, incoming: str | None) -> str: ...

    def http_request(
        self,
        *,
        method: str,
        route_template: str,
        status_code: int,
        duration_ms: int,
        incoming_correlation_id: str | None,
    ) -> str: ...

    def validation_rejected(
        self,
        *,
        boundary: str,
        rule_code: str,
        field_code: str,
        correlation_id: str,
    ) -> None: ...

    def security_rejected(
        self,
        *,
        runtime_boundary: bool,
        boundary: str,
        policy_code: str,
        correlation_id: str | None = None,
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class LocalBrowserHttpDecision:
    allowed: bool
    code: LocalBrowserHttpDecisionCode
    correlation_id: str

    def __post_init__(self) -> None:
        if type(self.allowed) is not bool:
            raise TypeError("allowed must be a bool")
        if not isinstance(self.code, LocalBrowserHttpDecisionCode):
            raise TypeError("code must be a LocalBrowserHttpDecisionCode")
        if self.allowed is not (self.code is LocalBrowserHttpDecisionCode.ALLOWED):
            raise ValueError("decision code and allowed state disagree")
        if type(self.correlation_id) is not str or not self.correlation_id:
            raise ValueError("correlation_id must be non-empty")


@dataclass(frozen=True, slots=True)
class SanitizedHttpError:
    status_code: int
    error_code: LocalBrowserHttpDecisionCode
    correlation_id: str

    def __post_init__(self) -> None:
        if type(self.status_code) is not int or not 400 <= self.status_code <= 599:
            raise ValueError("status_code must be a client-visible error status")
        if not isinstance(self.error_code, LocalBrowserHttpDecisionCode):
            raise TypeError("error_code must be a LocalBrowserHttpDecisionCode")
        if type(self.correlation_id) is not str or not self.correlation_id:
            raise ValueError("correlation_id must be non-empty")

    def as_mapping(self) -> Mapping[str, object]:
        return MappingProxyType(
            {
                "status": self.status_code,
                "error_code": self.error_code.value,
                "correlation_id": self.correlation_id,
            }
        )


class LocalBrowserHttpSecurityContract:
    """Validate future request metadata and emit only B03-safe diagnostics."""

    def __init__(
        self,
        configuration: LocalBrowserHttpConfiguration,
        observability: HttpObservabilityPort,
    ) -> None:
        if type(configuration) is not LocalBrowserHttpConfiguration:
            raise TypeError("configuration must be a LocalBrowserHttpConfiguration")
        self._configuration = configuration
        self._observability = observability

    def authorize_request(
        self,
        *,
        method: str,
        host_header: str,
        origin: str | None,
        incoming_correlation_id: str | None,
        preflight_method: str | None = None,
        preflight_headers: tuple[str, ...] = (),
    ) -> LocalBrowserHttpDecision:
        correlation_id = self._observability.correlation_id(incoming_correlation_id)
        same_origin = self._same_origin(host_header)
        if same_origin is None:
            return self._reject(
                LocalBrowserHttpDecisionCode.HOST_REJECTED,
                correlation_id,
            )
        if type(method) is not str:
            return self._reject_method(correlation_id)
        normalized_method = method.upper()
        if normalized_method == "OPTIONS":
            if not self._valid_preflight(origin, preflight_method, preflight_headers):
                return self._reject(
                    LocalBrowserHttpDecisionCode.PREFLIGHT_REJECTED,
                    correlation_id,
                )
        elif normalized_method not in {"GET", "HEAD"}:
            return self._reject_method(correlation_id)
        if not self._origin_allowed(origin, same_origin):
            return self._reject(
                LocalBrowserHttpDecisionCode.ORIGIN_REJECTED,
                correlation_id,
            )
        return LocalBrowserHttpDecision(
            True,
            LocalBrowserHttpDecisionCode.ALLOWED,
            correlation_id,
        )

    def authorize_command(
        self, *, method: str, headers: Mapping[str, str], nonce: str,
    ) -> str | None:
        """Separate R2 metadata gate; the historical authorize_request is unchanged."""
        host = self._configuration.bind_host
        canonical = "[::1]" if host == "::1" else host
        if self._configuration.port != 80:
            canonical += ":" + str(self._configuration.port)
        if headers.get("host") != canonical:
            return "HOST_REJECTED"
        origin = headers.get("origin")
        if (method == "POST" or origin is not None) and origin != "http://" + canonical:
            return "ORIGIN_REJECTED"
        if headers.get("sec-fetch-site", "same-origin") != "same-origin":
            return "ORIGIN_REJECTED"
        if headers.get("x-local-intent") != "conversation-v1":
            return "LOCAL_INTENT_REJECTED"
        if method == "POST":
            supplied = headers.get("x-r2-nonce", "")
            if not supplied.isascii() or not hmac.compare_digest(supplied, nonce):
                return "LOCAL_INTENT_REJECTED"
        return None

    def record_completion(
        self,
        decision: LocalBrowserHttpDecision,
        *,
        method: str,
        route_template: str,
        status_code: int,
        duration_ms: int,
    ) -> str:
        if type(decision) is not LocalBrowserHttpDecision:
            raise TypeError("decision must be a LocalBrowserHttpDecision")
        return self._observability.http_request(
            method=method,
            route_template=route_template,
            status_code=status_code,
            duration_ms=duration_ms,
            incoming_correlation_id=decision.correlation_id,
        )

    def client_error(
        self,
        decision: LocalBrowserHttpDecision,
        *,
        status_code: int,
    ) -> SanitizedHttpError:
        if type(decision) is not LocalBrowserHttpDecision or decision.allowed:
            raise ValueError("client_error requires a rejected decision")
        return SanitizedHttpError(
            status_code,
            decision.code,
            decision.correlation_id,
        )

    def internal_error(self, *, correlation_id: str) -> SanitizedHttpError:
        if _SAFE_CODE.fullmatch("INTERNAL_ERROR") is None:
            raise AssertionError("closed internal error code is invalid")
        return SanitizedHttpError(
            500,
            LocalBrowserHttpDecisionCode.INTERNAL_ERROR,
            self._observability.correlation_id(correlation_id),
        )

    def _same_origin(self, host_header: str) -> str | None:
        if type(host_header) is not str or not host_header or len(host_header) > 253:
            return None
        ipv6 = _HOST_V6.fullmatch(host_header)
        if ipv6 is not None:
            host = "::1"
            port = ipv6.group(1)
            origin_host = "[::1]"
        else:
            ipv4 = _HOST_V4.fullmatch(host_header)
            if ipv4 is None:
                return None
            host = ipv4.group(1).lower()
            port = ipv4.group(2)
            origin_host = host
        if host not in self._configuration.allowed_hosts:
            return None
        if port is not None and int(port) != self._configuration.port:
            return None
        suffix = "" if self._configuration.port == 80 else f":{self._configuration.port}"
        return f"http://{origin_host}{suffix}"

    def _origin_allowed(self, origin: str | None, same_origin: str) -> bool:
        if origin is None:
            return True
        if type(origin) is not str or not origin or len(origin) > 256:
            return False
        normalized = origin.lower()
        if normalized == same_origin.lower():
            return True
        return normalized in self._configuration.cors_allowed_origins

    def _valid_preflight(
        self,
        origin: str | None,
        preflight_method: str | None,
        preflight_headers: tuple[str, ...],
    ) -> bool:
        if not self._configuration.cors_enabled or type(origin) is not str:
            return False
        if origin.lower() not in self._configuration.cors_allowed_origins:
            return False
        if type(preflight_method) is not str:
            return False
        if preflight_method.upper() not in self._configuration.cors_allowed_methods:
            return False
        if type(preflight_headers) is not tuple or any(
            type(header) is not str for header in preflight_headers
        ):
            return False
        requested = {header.lower() for header in preflight_headers}
        return requested <= set(self._configuration.cors_allowed_headers)

    def _reject(
        self,
        code: LocalBrowserHttpDecisionCode,
        correlation_id: str,
    ) -> LocalBrowserHttpDecision:
        self._observability.security_rejected(
            runtime_boundary=True,
            boundary="HTTP_LOCAL_BROWSER",
            policy_code=code.value,
            correlation_id=correlation_id,
        )
        return LocalBrowserHttpDecision(False, code, correlation_id)

    def _reject_method(self, correlation_id: str) -> LocalBrowserHttpDecision:
        self._observability.validation_rejected(
            boundary="HTTP",
            rule_code=LocalBrowserHttpDecisionCode.METHOD_REJECTED.value,
            field_code="method",
            correlation_id=correlation_id,
        )
        return LocalBrowserHttpDecision(
            False,
            LocalBrowserHttpDecisionCode.METHOD_REJECTED,
            correlation_id,
        )
