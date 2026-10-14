"""Bound local overlay port, never filesystem or provider authority for callers."""
from __future__ import annotations

from collections.abc import Mapping
from contextlib import AbstractContextManager
from typing import Protocol

from backend.modules.resource_library.contracts.dto.local_contribution import (
    LocalContributionRead,
    LocalContributionRecord,
)


class LocalContributionPersistenceError(RuntimeError):
    def __init__(self, code: str, *, uncertain: bool = False) -> None:
        self.code, self.uncertain = code, uncertain
        super().__init__(code)


class LocalContributionStorePort(Protocol):
    def attest(self) -> Mapping[str, object]: ...
    def session(self, *, create: bool = False) -> AbstractContextManager[None]: ...
    def inspect_operation(self, operation_key: str, binding_sha256: str) -> Mapping[str, object]: ...
    def append(self, record: LocalContributionRecord, intention: Mapping[str, object]) -> LocalContributionRecord: ...
    def read_exact(self, request: LocalContributionRead) -> LocalContributionRecord: ...
