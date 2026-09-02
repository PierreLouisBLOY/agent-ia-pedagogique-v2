from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class DocumentType(StrEnum):
    OTHER = "OTHER"


class DocumentLanguageCode(StrEnum):
    FR = "fr"


class DocumentStatus(StrEnum):
    ACTIVE = "ACTIVE"


@dataclass(frozen=True, slots=True)
class DocumentPersistenceValues:
    """M02-owned closed vocabulary for one persisted document."""

    document_type: DocumentType
    language_code: DocumentLanguageCode
    status: DocumentStatus

    def __post_init__(self) -> None:
        if not isinstance(self.document_type, DocumentType):
            raise TypeError("document_type must be a DocumentType")
        if not isinstance(self.language_code, DocumentLanguageCode):
            raise TypeError("language_code must be a DocumentLanguageCode")
        if not isinstance(self.status, DocumentStatus):
            raise TypeError("status must be a DocumentStatus")
