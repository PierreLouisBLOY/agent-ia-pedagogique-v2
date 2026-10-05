from typing import Protocol

from backend.modules.knowledge_reference.contracts.dto.institutional_qualification import (
    InstitutionalQualification,
)


class InstitutionalQualificationPort(Protocol):
    def publish_qualification(self, qualification: InstitutionalQualification) -> None: ...
