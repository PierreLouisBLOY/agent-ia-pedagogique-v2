"""Explicit pinned local capture configuration; no external network/provider."""

from collections.abc import Mapping

from backend.adapters.inbound.application.organization_evidence import OrganizationEvidenceInbound
from backend.adapters.outbound.resource_library.organization_capture import (
    LocalOrganizationCaptures,
)
from backend.modules.resource_library.application.queries.organization_evidence import (
    ReadOrganizationEvidence,
)
from backend.modules.resource_library.contracts.dto.organization_evidence import (
    OrganizationEvidence,
)


def organization_capture_reader(descriptor: Mapping[str, object]) -> OrganizationEvidenceInbound:
    from backend.infrastructure.composition.factories.p0_normal_profile import read_descriptor

    data = read_descriptor(descriptor)
    if (
        not isinstance(data, dict)
        or not ((set(data) == {"schema", "records"} and data["schema"] == "LOCAL-ORGANIZATION-CAPTURES-1.0")
                or (set(data) == {"schema", "records", "index"} and data["schema"] == "LOCAL-ORGANIZATION-CAPTURES-2.0"))
    ):
        raise ValueError("P0_ORGANIZATION_CAPTURE_FIELDS")
    records = data["records"]
    if (
        not isinstance(records, list)
        or not 1 <= len(records) <= 16
        or any(not isinstance(r, dict) for r in records)
    ):
        raise ValueError("P0_ORGANIZATION_CAPTURE_BOUND")
    index = data.get("index", [])
    if not isinstance(index, list):
        raise ValueError("P0_ORGANIZATION_SEARCH_INDEX_BOUND")
    captures = LocalOrganizationCaptures(tuple(OrganizationEvidence(row) for row in records), index=tuple(index))
    inbound = OrganizationEvidenceInbound(ReadOrganizationEvidence(captures))
    from backend.modules.resource_library.application.queries.search_organizations import (
        SearchOrganizations,
    )
    inbound.search_query = SearchOrganizations(captures)
    return inbound
