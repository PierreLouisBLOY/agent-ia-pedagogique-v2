"""Immutable local public captures; never fetches, writes or admits a source."""

from typing import cast

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    fingerprint,
    object_data,
)
from backend.modules.resource_library.contracts.dto.organization_evidence import (
    OrganizationEvidence,
)
from backend.modules.resource_library.contracts.dto.organization_search import (
    OrganizationSearch,
    selection_row,
)


class LocalOrganizationCaptures:
    def __init__(self, records: tuple[OrganizationEvidence, ...], *, index: tuple[object, ...] = ()) -> None:
        if not 1 <= len(records) <= 16 or any(type(r) is not OrganizationEvidence for r in records):
            raise ValueError("P0_ORGANIZATION_CAPTURE_BOUND")
        identities = [
            (r.data["organization_id"], r.data["source_url"], r.data["retrieved_on"])
            for r in records
        ]
        if len(set(identities)) != len(identities):
            raise ValueError("P0_ORGANIZATION_CAPTURE_DUPLICATE")
        self.records = records
        if len(index) > 16:
            raise ValueError("P0_ORGANIZATION_SEARCH_INDEX_BOUND")
        self.index = tuple(selection_row(r) for r in index)
        keys = []
        for row in self.index:
            matches = [r for r in records if r.data["organization_id"] == row["organization_id"]
                       and fingerprint(r.data) == row["capture_sha256"]]
            if len(matches) != 1:
                raise ValueError("P0_ORGANIZATION_SEARCH_CAPTURE_CHANGED")
            analysis = object_data(row["selection_analysis"])
            if any(analysis[k] != matches[0].data[k] for k in ("source_url", "retrieved_on")):
                raise ValueError("P0_ORGANIZATION_SEARCH_PROVENANCE")
            keys.append(row["capture_sha256"])
        if len(keys) != len(set(keys)):
            raise ValueError("P0_ORGANIZATION_SEARCH_DUPLICATE")

    def find(self, *, organization_id: str) -> tuple[OrganizationEvidence, ...]:
        result = tuple(r for r in self.records if r.data["organization_id"] == organization_id)
        if not result:
            raise ValueError("P0_ORGANIZATION_CAPTURE_NOT_FOUND")
        return result

    def search(self, *, criteria: OrganizationSearch) -> tuple[dict[str, object], ...]:
        if not self.index:
            raise ValueError("P0_ORGANIZATION_SEARCH_INDEX_NOT_CONFIGURED")
        found: list[dict[str, object]] = []
        for row in self.index:
            if (criteria.notion_ref not in cast(tuple[str, ...], row["notion_refs"]) or criteria.sector != row["sector"]
                    or criteria.organization_type != row["organization_type"]):
                continue
            capture = next(r for r in self.records if fingerprint(r.data) == row["capture_sha256"])
            found.append({"documented_facts": [dict(capture.data)],
                          "local_analysis": [object_data(row["selection_analysis"])], "fiction": [],
                          "selection": {k: row[k] for k in ("notion_refs", "sector", "organization_type", "capture_sha256")}})
        return tuple(found)
