"""Optional approved external source, bounded identity query and explicit gap."""

import re

from backend.modules.resource_library.contracts.dto.organization_evidence import (
    OrganizationEvidence,
)
from backend.modules.resource_library.ports.outbound.organization_evidence import (
    OrganizationEvidencePort,
)


class ReadOrganizationEvidence:
    def __init__(self, provider: OrganizationEvidencePort | None = None) -> None:
        self.provider = provider

    def execute(self, organization_id: str) -> tuple[OrganizationEvidence, ...]:
        if re.fullmatch(r"siren:[0-9]{9}", organization_id) is None:
            raise ValueError("P0_EXTERNAL_ORGANIZATION_IDENTITY")
        if self.provider is None:
            raise ValueError("BLOCKED_EXTERNAL_SOURCE_PROVIDER")
        result = self.provider.find(organization_id=organization_id)
        if (
            not isinstance(result, tuple)
            or not 1 <= len(result) <= 8
            or any(
                type(row) is not OrganizationEvidence
                or row.data["organization_id"] != organization_id
                for row in result
            )
        ):
            raise ValueError("P0_EXTERNAL_EVIDENCE_MEMBERSHIP")
        return result
