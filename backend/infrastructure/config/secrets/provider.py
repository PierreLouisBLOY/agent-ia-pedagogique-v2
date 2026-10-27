"""Explicit provider-secret resolution boundary with redacted values."""

from __future__ import annotations

import re
from collections.abc import Mapping
from enum import StrEnum
from typing import Protocol, runtime_checkable

_SAFE_CREDENTIAL_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_MAX_SECRET_LENGTH = 16_384
_REDACTED = "[REDACTED]"


class ProviderCredentialRef:
    """Value-semantic logical reference; it never contains credential material."""

    __slots__ = ("value",)

    value: str

    def __init__(self, value: str) -> None:
        if not isinstance(value, str):
            raise TypeError("provider credential reference must be a string")
        if _SAFE_CREDENTIAL_REF.fullmatch(value) is None:
            raise ValueError("provider credential reference has an invalid format")
        self.value = value

    def __repr__(self) -> str:
        return f"ProviderCredentialRef(value={self.value!r})"

    def __eq__(self, other: object) -> bool:
        return type(other) is ProviderCredentialRef and self.value == other.value

    def __hash__(self) -> int:
        return hash((ProviderCredentialRef, self.value))


class ProviderSecretErrorCode(StrEnum):
    MISSING_PROVIDER_SECRET = "MISSING_PROVIDER_SECRET"
    INVALID_PROVIDER_SECRET = "INVALID_PROVIDER_SECRET"


class ProviderSecretError(RuntimeError):
    """Closed secret-resolution error containing no source value."""

    code: ProviderSecretErrorCode

    def __init__(self, code: ProviderSecretErrorCode) -> None:
        if type(code) is not ProviderSecretErrorCode:
            raise TypeError("code must be a ProviderSecretErrorCode")
        self.code = code
        super().__init__(code.value)


class ProviderSecretValue:
    """Opaque credential material revealed only by an explicit transport call."""

    __slots__ = ("__raw_value",)

    def __init__(self, raw_value: str) -> None:
        if not isinstance(raw_value, str):
            raise TypeError("provider secret value must be a string")
        if not raw_value.strip() or len(raw_value) > _MAX_SECRET_LENGTH:
            raise ProviderSecretError(ProviderSecretErrorCode.INVALID_PROVIDER_SECRET)
        self.__raw_value = raw_value

    def __repr__(self) -> str:
        return f"ProviderSecretValue({_REDACTED})"

    def __str__(self) -> str:
        return _REDACTED

    def __hash__(self) -> int:
        raise TypeError("ProviderSecretValue is not hashable")

    def reveal_for_transport(self) -> str:
        """Return the raw value only to a concrete outbound transport adapter."""

        return self.__raw_value


@runtime_checkable
class ProviderSecretResolver(Protocol):
    def resolve(self, credential_ref: ProviderCredentialRef) -> ProviderSecretValue: ...


class EnvironmentProviderSecretResolver:
    """Explicit resolver over an injected environment snapshot; imports read nothing."""

    __slots__ = ("__environment",)

    def __init__(self, environment: Mapping[str, str]) -> None:
        if not isinstance(environment, Mapping):
            raise TypeError("environment must be a mapping")
        if any(not isinstance(key, str) or not isinstance(value, str) for key, value in environment.items()):
            raise TypeError("environment must contain string keys and values")
        self.__environment = dict(environment)

    def __repr__(self) -> str:
        return f"EnvironmentProviderSecretResolver(environment={_REDACTED})"

    def __str__(self) -> str:
        return "EnvironmentProviderSecretResolver"

    def close(self) -> None:
        """Drop the private environment snapshot when its composition closes."""
        self.__environment.clear()

    def resolve(self, credential_ref: ProviderCredentialRef) -> ProviderSecretValue:
        if type(credential_ref) is not ProviderCredentialRef:
            raise TypeError("credential_ref must be a ProviderCredentialRef")
        try:
            raw_value = self.__environment[credential_ref.value]
        except KeyError:
            raise ProviderSecretError(
                ProviderSecretErrorCode.MISSING_PROVIDER_SECRET
            ) from None
        return ProviderSecretValue(raw_value)
