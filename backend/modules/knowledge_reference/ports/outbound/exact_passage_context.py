"""Application ports for a single owner-approved exact passage relation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class PassageEvidence:
    version_or_checksum: str
    excerpt_bytes: bytes
    provenance_sha256: str
    usage_permitted: bool
    sensitive: bool
    available_authority: str


class PassageEvidencePort(Protocol):
    def read_passage(self, object_ref: str, passage_ref: str) -> PassageEvidence | None: ...


class ExactPassageContextPort(Protocol):
    def validate_scope(self, request: Mapping[str, object]) -> None: ...

    def add_one(self, request: Mapping[str, object], *, selection_sha256: str,
                owner_decision_sha256: str) -> str: ...

    def read_exact(self, request: Mapping[str, object], *, selection_sha256: str) -> Mapping[str, object] | None: ...
