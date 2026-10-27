from typing import Protocol

from backend.modules.resource_library.contracts.dto.organization_evidence import (
    OrganizationEvidence,
)


class OrganizationEvidencePort(Protocol):
    def find(self, *, organization_id: str) -> tuple[OrganizationEvidence, ...]: ...
