"""Local draft provenance; no official or transmission authority."""
from __future__ import annotations

import re
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


V2_FIELDS = FIELDS | {"author_kind", "draft_creation_status", "draft_recorded_at", "recording_basis",
    "original_proposal_receipt_ref", "original_proposal_receipt_sha256"}


@dataclass(frozen=True, slots=True)
class LocalContributionProvenanceV2(LocalContributionProvenance):
    """Unknown draft creation; exact original proposal recording is a separate fact."""

    def __post_init__(self) -> None:
        data = object_data(as_plain(self.data), V2_FIELDS)
        if (data["contract_id"] != "LOCAL-CONTRIBUTION-PROVENANCE-2.0"
                or data["origin_kind"] != "LOCAL_DRAFT" or data["authority"] != "UNKNOWN"
                or data["official_reference"] is not False
                or data["transmission_admission"] != "NOT_ADOPTED"
                or data["teacher_acceptance"] != "NOT_PERFORMED"
                or data["draft_created_at"] is not None
                or data["draft_creation_status"] != "NOT_ESTABLISHED"
                or data["recording_basis"] != "ORIGINAL_PROPOSAL_RECEIPT"
                or data["author_kind"] != "SUBAGENT"):
            raise ValueError("LOCAL_CONTRIBUTION_PROVENANCE_V2")
        if (type(data["author"]) is not str
                or re.fullmatch(r"SUBAGENT_[a-zA-Z0-9_]{1,180}", data["author"]) is None):
            raise ValueError("LOCAL_CONTRIBUTION_AUTHOR")
        if (type(data["original_proposal_receipt_ref"]) is not str
                or re.fullmatch(r"local-draft-record:[A-Za-z0-9._:-]{1,180}", data["original_proposal_receipt_ref"]) is None):
            raise ValueError("LOCAL_CONTRIBUTION_RECORDING_BASIS")
        try:
            if type(data["draft_recorded_at"]) is not str or datetime.fromisoformat(data["draft_recorded_at"]).tzinfo is None:
                raise ValueError("LOCAL_CONTRIBUTION_DATE")
        except ValueError as error:
            raise ValueError("LOCAL_CONTRIBUTION_DATE") from error
        for key in ("draft_origin_sha256", "local_admission_decision_sha256", "operation_authorization_sha256",
                "local_context_sha256", "original_proposal_receipt_sha256"):
            digest(data[key])
        if data["draft_origin_sha256"] != data["original_proposal_receipt_sha256"]:
            raise ValueError("LOCAL_CONTRIBUTION_RECORDING_BASIS")
        object.__setattr__(self, "data", freeze_safe_mapping(data))


def parse_local_contribution_provenance(data: Mapping[str, object]) -> LocalContributionProvenance:
    contract = data.get("contract_id")
    if contract == "LOCAL-CONTRIBUTION-PROVENANCE-1.0":
        return LocalContributionProvenance(data)
    if contract == "LOCAL-CONTRIBUTION-PROVENANCE-2.0":
        return LocalContributionProvenanceV2(data)
    raise ValueError("LOCAL_CONTRIBUTION_PROVENANCE_CONTRACT")
