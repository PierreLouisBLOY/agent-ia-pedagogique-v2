"""Framework-neutral, fail-closed configuration for the future local HTTP host."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

DEFAULT_HTTP_BIND_HOST: Final = "127.0.0.1"
LOCAL_HTTP_BIND_HOSTS: Final = ("127.0.0.1", "::1")
LOCAL_HTTP_ALLOWED_HOSTS: Final = ("localhost", "127.0.0.1", "::1")
DEFAULT_CORS_METHODS: Final = ("GET",)
DEFAULT_CORS_HEADERS: Final = ("x-correlation-id",)

_METHOD = re.compile(r"^[A-Z]{3,10}$")
_HEADER = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
_FORBIDDEN_CORS_HEADERS: Final = frozenset(
    {"authorization", "cookie", "proxy-authorization"}
)


class LocalHttpConfigurationErrorCode(StrEnum):
    INVALID_PORT = "INVALID_PORT"
    NON_LOOPBACK_BIND = "NON_LOOPBACK_BIND"
    INVALID_ALLOWED_HOST = "INVALID_ALLOWED_HOST"
    INVALID_CORS_ORIGIN = "INVALID_CORS_ORIGIN"
    WILDCARD_CORS_FORBIDDEN = "WILDCARD_CORS_FORBIDDEN"
    CORS_CREDENTIALS_FORBIDDEN = "CORS_CREDENTIALS_FORBIDDEN"
    INVALID_CORS_METHOD = "INVALID_CORS_METHOD"
    INVALID_CORS_HEADER = "INVALID_CORS_HEADER"
    DEBUG_FORBIDDEN = "DEBUG_FORBIDDEN"
    RELOAD_FORBIDDEN = "RELOAD_FORBIDDEN"
    DOCS_FORBIDDEN = "DOCS_FORBIDDEN"
    STATEFUL_SESSION_FORBIDDEN = "STATEFUL_SESSION_FORBIDDEN"


class LocalHttpConfigurationError(ValueError):
    """Closed configuration failure that never repeats an untrusted value."""

    def __init__(self, code: LocalHttpConfigurationErrorCode) -> None:
        if not isinstance(code, LocalHttpConfigurationErrorCode):
            raise TypeError("code must be a LocalHttpConfigurationErrorCode")
        self.code = code
        super().__init__(f"local HTTP configuration rejected: {code.value}")


@dataclass(frozen=True, slots=True)
class LocalBrowserHttpConfiguration:
    """Pure configuration contract; it does not create or start a server."""

    port: int
    bind_host: str = DEFAULT_HTTP_BIND_HOST
    allowed_hosts: tuple[str, ...] = LOCAL_HTTP_ALLOWED_HOSTS
    cors_allowed_origins: tuple[str, ...] = ()
    cors_allowed_methods: tuple[str, ...] = DEFAULT_CORS_METHODS
    cors_allowed_headers: tuple[str, ...] = DEFAULT_CORS_HEADERS
    cors_allow_credentials: bool = False
    debug: bool = False
    reload: bool = False
    docs_enabled: bool = False
    stateful_sessions: bool = False

    def __post_init__(self) -> None:
        if type(self.port) is not int or not 1 <= self.port <= 65_535:
            _fail(LocalHttpConfigurationErrorCode.INVALID_PORT)
        if type(self.bind_host) is not str or self.bind_host not in LOCAL_HTTP_BIND_HOSTS:
            _fail(LocalHttpConfigurationErrorCode.NON_LOOPBACK_BIND)
        allowed_hosts = _closed_tuple(self.allowed_hosts)
        if not allowed_hosts or any(
            host not in LOCAL_HTTP_ALLOWED_HOSTS for host in allowed_hosts
        ):
            _fail(LocalHttpConfigurationErrorCode.INVALID_ALLOWED_HOST)
        object.__setattr__(self, "allowed_hosts", allowed_hosts)

        origins = _closed_tuple(self.cors_allowed_origins)
        if "*" in origins:
            _fail(LocalHttpConfigurationErrorCode.WILDCARD_CORS_FORBIDDEN)
        canonical_origins = frozenset(self.local_origins)
        if any(origin not in canonical_origins for origin in origins):
            _fail(LocalHttpConfigurationErrorCode.INVALID_CORS_ORIGIN)
        object.__setattr__(self, "cors_allowed_origins", origins)

        methods = _closed_tuple(self.cors_allowed_methods)
        if not methods or any(
            _METHOD.fullmatch(method) is None or method not in {"GET", "HEAD"}
            for method in methods
        ):
            _fail(LocalHttpConfigurationErrorCode.INVALID_CORS_METHOD)
        object.__setattr__(self, "cors_allowed_methods", methods)

        headers = _closed_tuple(self.cors_allowed_headers)
        if any(
            _HEADER.fullmatch(header) is None or header in _FORBIDDEN_CORS_HEADERS
            for header in headers
        ):
            _fail(LocalHttpConfigurationErrorCode.INVALID_CORS_HEADER)
        object.__setattr__(self, "cors_allowed_headers", headers)

        for value, code in (
            (self.cors_allow_credentials, LocalHttpConfigurationErrorCode.CORS_CREDENTIALS_FORBIDDEN),
            (self.debug, LocalHttpConfigurationErrorCode.DEBUG_FORBIDDEN),
            (self.reload, LocalHttpConfigurationErrorCode.RELOAD_FORBIDDEN),
            (self.docs_enabled, LocalHttpConfigurationErrorCode.DOCS_FORBIDDEN),
            (self.stateful_sessions, LocalHttpConfigurationErrorCode.STATEFUL_SESSION_FORBIDDEN),
        ):
            if type(value) is not bool or value:
                _fail(code)

    @property
    def cors_enabled(self) -> bool:
        return bool(self.cors_allowed_origins)

    @property
    def local_origins(self) -> tuple[str, ...]:
        return tuple(_local_origin(host, self.port) for host in self.allowed_hosts)

    @property
    def public_summary(self) -> MappingProxyType[str, object]:
        return MappingProxyType(
            {
                "execution_mode": "LOCAL_BROWSER",
                "bind_policy": "LOOPBACK_ONLY",
                "port_policy": "EXPLICIT_REQUIRED",
                "cors_policy": "STRICT_LOCAL_ALLOWLIST"
                if self.cors_enabled
                else "SAME_ORIGIN_ONLY",
                "debug": False,
                "reload": False,
                "docs": False,
                "stateful_sessions": False,
            }
        )


def _closed_tuple(values: tuple[str, ...]) -> tuple[str, ...]:
    if type(values) is not tuple or any(type(value) is not str for value in values):
        _fail(LocalHttpConfigurationErrorCode.INVALID_ALLOWED_HOST)
    if len(values) != len(set(values)):
        _fail(LocalHttpConfigurationErrorCode.INVALID_ALLOWED_HOST)
    return values


def _fail(code: LocalHttpConfigurationErrorCode) -> None:
    raise LocalHttpConfigurationError(code)


def _local_origin(host: str, port: int) -> str:
    authority = f"[{host}]" if host == "::1" else host
    suffix = "" if port == 80 else f":{port}"
    return f"http://{authority}{suffix}"
