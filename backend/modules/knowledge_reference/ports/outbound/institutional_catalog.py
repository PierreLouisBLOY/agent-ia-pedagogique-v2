from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class InstitutionalTableSchema:
    table: str
    columns: tuple[str, ...]
    rows: int
    definition: str | None = None


class InstitutionalSchemaPort(Protocol):
    def inspect_institutional_schema(self) -> tuple[InstitutionalTableSchema, ...]: ...

    def read_institutional_catalog(self) -> Mapping[str, object]: ...

    def read_reference_contexts(self, object_ref: str) -> tuple[Mapping[str, object], ...]: ...

    def read_exact_passage_contexts(self, object_kind: str, object_ref: str,
                                    passage_ref: str, version_or_checksum: str,
                                    excerpt_sha256: str, context_ref: str,
                                    selection_sha256: str) -> tuple[Mapping[str, object], ...]: ...
