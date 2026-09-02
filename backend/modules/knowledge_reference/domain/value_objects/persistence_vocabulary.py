from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class KnowledgeLanguageCode(StrEnum):
    """Languages explicitly supported by the knowledge-reference owner."""

    FR = "fr"


class NotionIdentityStatus(StrEnum):
    """Canonical notion identity states accepted by the authenticated DDL."""

    CANONICAL = "CANONICAL"
    MERGED = "MERGED"
    DEPRECATED = "DEPRECATED"
    ARCHIVED = "ARCHIVED"


@dataclass(frozen=True, slots=True)
class NotionPersistenceValues:
    """M01-owned values supplied to the notion persistence adapter."""

    language_code: KnowledgeLanguageCode
    identity_status: NotionIdentityStatus

    def __post_init__(self) -> None:
        if not isinstance(self.language_code, KnowledgeLanguageCode):
            raise TypeError("language_code must be a KnowledgeLanguageCode")
        if not isinstance(self.identity_status, NotionIdentityStatus):
            raise TypeError("identity_status must be a NotionIdentityStatus")
