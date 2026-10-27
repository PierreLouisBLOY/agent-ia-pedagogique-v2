"""Exact local discovery criteria, independent of canonical source admission."""

from collections.abc import Mapping
from dataclasses import dataclass

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import nonempty, object_data
from backend.shared_kernel._safe_data import freeze_safe_mapping

TYPES = frozenset({"ENTERPRISE", "ASSOCIATION", "ADMINISTRATION", "COOPERATIVE"})


@dataclass(frozen=True, slots=True)
class OrganizationSearch:
    notion_ref: str
    sector: str
    organization_type: str

    def __post_init__(self) -> None:
        if not nonempty(self.notion_ref, 256).startswith("notion:"):
            raise ValueError("P0_ORGANIZATION_SEARCH_NOTION")
        nonempty(self.sector, 200)
        if self.organization_type not in TYPES:
            raise ValueError("P0_ORGANIZATION_SEARCH_TYPE")

    @classmethod
    def parse(cls, value: Mapping[str, object]) -> "OrganizationSearch":
        row = object_data(value, {"notion_ref", "sector", "organization_type"})
        if any(not isinstance(v, str) for v in row.values()):
            raise ValueError("P0_ORGANIZATION_SEARCH_FIELDS")
        return cls(str(row["notion_ref"]), str(row["sector"]), str(row["organization_type"]))


def selection_row(value: object) -> Mapping[str, object]:
    row = object_data(value, {"organization_id", "capture_sha256", "notion_refs", "sector",
                              "organization_type", "selection_analysis"})
    nonempty(row["organization_id"], 200)
    if not isinstance(row["sector"], str) or not isinstance(row["organization_type"], str):
        raise ValueError("P0_ORGANIZATION_SEARCH_FIELDS")
    import re
    if not isinstance(row["capture_sha256"], str) or re.fullmatch("[0-9a-f]{64}", row["capture_sha256"]) is None:
        raise ValueError("P0_ORGANIZATION_SEARCH_CAPTURE_IDENTITY")
    refs = row["notion_refs"]
    if not isinstance(refs, (tuple, list)) or not 1 <= len(refs) <= 16 or any(not isinstance(r, str) for r in refs):
        raise ValueError("P0_ORGANIZATION_SEARCH_NOTIONS")
    if len(set(refs)) != len(refs):
        raise ValueError("P0_ORGANIZATION_SEARCH_NOTIONS")
    for ref in refs:
        OrganizationSearch(str(ref), str(row["sector"]), str(row["organization_type"]))
    analysis = object_data(row["selection_analysis"], {"kind", "text", "source_url", "retrieved_on"})
    if analysis["kind"] != "LOCAL_ANALYSIS_NOT_CANONICAL_RELATION":
        raise ValueError("P0_ORGANIZATION_SEARCH_CLASSIFICATION")
    nonempty(analysis["text"], 2000)
    return freeze_safe_mapping(row)
