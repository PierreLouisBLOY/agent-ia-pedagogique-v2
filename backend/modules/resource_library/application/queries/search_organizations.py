"""Read local indexed proposals; no admission, generation or mutation."""

from typing import Protocol

from backend.modules.resource_library.contracts.dto.organization_search import OrganizationSearch


class OrganizationSearchPort(Protocol):
    def search(self, *, criteria: OrganizationSearch) -> tuple[dict[str, object], ...]: ...


class SearchOrganizations:
    def __init__(self, provider: OrganizationSearchPort) -> None:
        self.provider = provider

    def execute(self, criteria: OrganizationSearch) -> dict[str, object]:
        rows = self.provider.search(criteria=criteria)
        if len(rows) > 16:
            raise ValueError("P0_ORGANIZATION_SEARCH_BOUND")
        return {"schema": "LOCAL-ORGANIZATION-SEARCH-1.0", "criteria": {
            "notion_ref": criteria.notion_ref, "sector": criteria.sector,
            "organization_type": criteria.organization_type}, "items": list(rows),
            "matching": "EXACT_DECLARED_LOCAL_CLASSIFICATION", "canonical_admission": "NOT_GRANTED",
            "institutional_relation_admission": "NOT_GRANTED", "provider_generation_calls": 0}
