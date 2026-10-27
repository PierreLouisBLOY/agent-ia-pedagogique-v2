"""Separate read-only capability; reading a confirmed result restores no permission."""
from collections.abc import Mapping
from typing import Protocol, runtime_checkable


@runtime_checkable
class P0ConfirmedGenerationRecoveryPort(Protocol):
    def confirmed_dispatch(self) -> Mapping[str, object] | None: ...

    def recover_confirmed(self, *, request: Mapping[str, object]) -> Mapping[str, object]: ...


@runtime_checkable
class P0ConfirmedGenerationsRecoveryPort(Protocol):
    """P1 read-only multi-scope companion; no authorization or dispatch method."""
    def confirmed_dispatches(self) -> tuple[Mapping[str, object], ...]: ...
    def recover_confirmed(self, *, request: Mapping[str, object]) -> Mapping[str, object]: ...
