"""Agent-facing Application boundary: proposals, no canonical mutation/admission."""

from backend.modules.resource_library.application.queries.organization_evidence import (
    ReadOrganizationEvidence,
)
from backend.modules.resource_library.application.queries.search_organizations import (
    SearchOrganizations,
)
from backend.modules.resource_library.contracts.dto.organization_search import OrganizationSearch


class OrganizationEvidenceInbound:
    def __init__(self, query: ReadOrganizationEvidence) -> None:
        self.query = query
        self.search_query: SearchOrganizations | None = None

    def search(self, criteria: dict[str, object]) -> dict[str, object]:
        if self.search_query is None:
            raise ValueError("P0_ORGANIZATION_SEARCH_INDEX_NOT_CONFIGURED")
        return self.search_query.execute(OrganizationSearch.parse(criteria))

    def inspect(self, organization_id: str) -> dict[str, object]:
        rows = self.query.execute(organization_id)
        return {
            "schema": "ORGANIZATION-EVIDENCE-PROPOSAL-1.0",
            "organization_id": organization_id,
            "items": [dict(row.data) for row in rows],
            "canonical_admission": "NOT_GRANTED",
            "provider_generation_calls": 0,
        }
