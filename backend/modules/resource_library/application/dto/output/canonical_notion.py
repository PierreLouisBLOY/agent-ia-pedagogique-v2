from __future__ import annotations

from dataclasses import dataclass

from backend.modules.resource_library.ports.outbound.canonical_notion_catalog import (
    CanonicalNotionIdentityRecord,
)


@dataclass(frozen=True, slots=True)
class CanonicalNotionIdentity:
    notion_id: str
    canonical_label: str
    identity_status: str
    level_applicability: tuple[str, ...]
    method_refs: tuple[str, ...]

    @classmethod
    def from_record(cls, record: CanonicalNotionIdentityRecord) -> CanonicalNotionIdentity:
        return cls(
            record.notion_id,
            record.canonical_label,
            record.identity_status,
            record.level_applicability,
            record.method_refs,
        )
