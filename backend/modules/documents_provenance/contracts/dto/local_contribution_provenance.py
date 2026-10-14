"""Local draft provenance; no official or transmission authority."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import as_plain, object_data
from backend.shared_kernel._safe_data import freeze_safe_mapping

FIELDS = {"contract_id", "origin_kind", "author", "draft_created_at", "draft_origin_sha256",
    "local_admission_decision_sha256", "operation_authorization_sha256", "local_context_sha256",
    "authority", "official_reference", "transmission_admission", "teacher_acceptance"}


def digest(value: object) -> str:
    if type(value) is not str or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError("LOCAL_CONTRIBUTION_HASH")
    return value


@dataclass(frozen=True, slots=True)
class LocalContributionProvenance:
    data: Mapping[str, object]

    def __post_init__(self) -> None:
        data = object_data(as_plain(self.data), FIELDS)
        if (data["contract_id"] != "LOCAL-CONTRIBUTION-PROVENANCE-1.0"
                or data["origin_kind"] != "LOCAL_DRAFT" or data["authority"] != "UNKNOWN"
                or data["official_reference"] is not False
                or data["transmission_admission"] != "NOT_ADOPTED"
                or data["teacher_acceptance"] != "NOT_PERFORMED"):
            raise ValueError("LOCAL_CONTRIBUTION_PROVENANCE")
        if type(data["author"]) is not str or not 1 <= len(data["author"]) <= 200:
            raise ValueError("LOCAL_CONTRIBUTION_AUTHOR")
        if type(data["draft_created_at"]) is not str:
            raise ValueError("LOCAL_CONTRIBUTION_DATE")
        try:
            stamp = datetime.fromisoformat(data["draft_created_at"])
        except ValueError as error:
            raise ValueError("LOCAL_CONTRIBUTION_DATE") from error
        if stamp.tzinfo is None:
            raise ValueError("LOCAL_CONTRIBUTION_DATE")
        for key in ("draft_origin_sha256", "local_admission_decision_sha256",
                "operation_authorization_sha256", "local_context_sha256"):
            digest(data[key])
        object.__setattr__(self, "data", freeze_safe_mapping(data))

    def as_dict(self) -> dict[str, object]:
        return object_data(as_plain(self.data))
