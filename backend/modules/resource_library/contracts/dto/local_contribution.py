"""Full local contributions, distinct from bounded search passages."""
from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from backend.modules.documents_provenance.contracts.dto.local_contribution_provenance import (
    LocalContributionProvenance,
    digest,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    as_plain,
    fingerprint,
    object_data,
)
from backend.modules.resource_library.contracts.dto.search_source_status import SearchSourceStatus
from backend.shared_kernel._safe_data import freeze_safe_mapping

AUTHORITY_FIELDS = {"contract_id", "text_sha256", "utf8_bytes", "draft_origin_sha256",
    "local_admission_decision_sha256", "operation_authorization_sha256", "local_context_sha256",
    "target_ref", "target_binding_sha256", "operator_profile_sha256", "max_new_contributions"}
REQUEST_FIELDS = {"contract_id", "command_key", "text", "utf8_bytes", "text_sha256", "title",
    "notion_ref", "local_context_sha256"}
RECORD_FIELDS = {"contract_id", "object_ref", "version_ref", "passage_ref", "provenance_ref",
    "text", "utf8_bytes", "text_sha256", "title", "notion_ref", "operation_key", "binding_sha256",
    "target_binding_sha256", "created_at", "provenance", "reference_snapshot"}
READ_FIELDS = {"contract_id", "object_ref", "version_ref", "passage_ref", "record_sha256"}
REFERENCE_FIELDS = {"notion_ref", "identity_status", "local_context_sha256", "native_scope_status"}


def text_identity(text: object, size: object, sha: object) -> None:
    if type(text) is not str or type(size) is not int or not 1 <= size <= 16000:
        raise ValueError("LOCAL_CONTRIBUTION_TEXT")
    try:
        raw = text.encode("utf-8", errors="strict")
    except UnicodeError as error:
        raise ValueError("LOCAL_CONTRIBUTION_TEXT") from error
    if len(raw) != size or hashlib.sha256(raw).hexdigest() != digest(sha):
        raise ValueError("LOCAL_CONTRIBUTION_TEXT")


def local_id(value: object, prefix: str) -> str:
    if type(value) is not str or re.fullmatch(re.escape(prefix) + r":[0-9a-f]{32}", value) is None:
        raise ValueError("LOCAL_CONTRIBUTION_ID")
    return value


def reference_snapshot(data: object, notion: object, context: object) -> dict[str, object]:
    value = object_data(data, REFERENCE_FIELDS)
    if (value["notion_ref"] != notion or value["local_context_sha256"] != context
            or value["identity_status"] != "CANONICAL"
            or value["native_scope_status"] not in {"CONTENT_GAP", "RESOLVED_ADMITTED"}):
        raise ValueError("LOCAL_CONTRIBUTION_REFERENCE")
    return value


@dataclass(frozen=True, slots=True)
class LocalContributionAuthority:
    data: Mapping[str, object]

    def __post_init__(self) -> None:
        data = object_data(as_plain(self.data), AUTHORITY_FIELDS)
        if (data["contract_id"] != "LOCAL-CONTRIBUTION-AUTHORITY-1.0"
                or type(data["max_new_contributions"]) is not int or data["max_new_contributions"] != 1
                or type(data["utf8_bytes"]) is not int or not 1 <= data["utf8_bytes"] <= 16000
                or type(data["target_ref"]) is not str
                or re.fullmatch(r"local-target:[0-9a-f]{64}", data["target_ref"]) is None):
            raise ValueError("LOCAL_CONTRIBUTION_AUTHORITY")
        for key in AUTHORITY_FIELDS - {"contract_id", "max_new_contributions", "utf8_bytes", "target_ref"}:
            digest(data[key])
        object.__setattr__(self, "data", freeze_safe_mapping(data))

    @property
    def sha256(self) -> str:
        return fingerprint(self.data)


@dataclass(frozen=True, slots=True)
class LocalContributionRequest:
    data: Mapping[str, object]

    def __post_init__(self) -> None:
        data = object_data(as_plain(self.data), REQUEST_FIELDS)
        if data["contract_id"] != "LOCAL-CONTRIBUTION-REGISTER-1.0":
            raise ValueError("LOCAL_CONTRIBUTION_REQUEST")
        digest(data["command_key"])
        digest(data["local_context_sha256"])
        text_identity(data["text"], data["utf8_bytes"], data["text_sha256"])
        if (type(data["title"]) is not str or not 1 <= len(data["title"]) <= 200
                or type(data["notion_ref"]) is not str
                or re.fullmatch(r"notion:[a-zA-Z0-9._:-]{1,180}", data["notion_ref"]) is None):
            raise ValueError("LOCAL_CONTRIBUTION_REQUEST")
        object.__setattr__(self, "data", freeze_safe_mapping(data))

    @property
    def sha256(self) -> str:
        return fingerprint(self.data)


@dataclass(frozen=True, slots=True)
class LocalContributionRecord:
    data: Mapping[str, object]

    def __post_init__(self) -> None:
        data = object_data(as_plain(self.data), RECORD_FIELDS)
        if data["contract_id"] != "LOCAL-CONTRIBUTION-RECORD-1.0":
            raise ValueError("LOCAL_CONTRIBUTION_RECORD")
        for key, prefix in (("object_ref", "local-content"), ("version_ref", "local-version"),
                ("passage_ref", "local-passage"), ("provenance_ref", "local-provenance")):
            local_id(data[key], prefix)
        for key in ("operation_key", "binding_sha256", "target_binding_sha256"):
            digest(data[key])
        text_identity(data["text"], data["utf8_bytes"], data["text_sha256"])
        provenance = LocalContributionProvenance(object_data(data["provenance"]))
        reference_snapshot(data["reference_snapshot"], data["notion_ref"], provenance.data["local_context_sha256"])
        try:
            if type(data["created_at"]) is not str or datetime.fromisoformat(data["created_at"]).tzinfo is None:
                raise ValueError("LOCAL_CONTRIBUTION_DATE")
        except ValueError as error:
            raise ValueError("LOCAL_CONTRIBUTION_DATE") from error
        if type(data["title"]) is not str or not 1 <= len(data["title"]) <= 200:
            raise ValueError("LOCAL_CONTRIBUTION_TITLE")
        if type(data["notion_ref"]) is not str or re.fullmatch(r"notion:[a-zA-Z0-9._:-]{1,180}", data["notion_ref"]) is None:
            raise ValueError("LOCAL_CONTRIBUTION_REFERENCE")
        object.__setattr__(self, "data", freeze_safe_mapping(data))

    @property
    def sha256(self) -> str:
        return fingerprint(self.data)

    def as_dict(self) -> dict[str, object]:
        return object_data(as_plain(self.data))

    def source_snapshot(self) -> dict[str, object]:
        return {"notion_ref": self.data["notion_ref"], "object_ref": self.data["object_ref"],
            "object_kind": "PEDAGOGICAL_CONTENT", "passage_ref": self.data["passage_ref"],
            "version_or_checksum": self.data["version_ref"], "excerpt": self.data["text"],
            "excerpt_truncated": False, "authority": "UNKNOWN", "is_private_evidence": False,
            "is_oracle": False, "is_teacher_reference": False,
            "source_status": SearchSourceStatus("UNKNOWN").as_dict(),
            "provenance": {"contract_id": "LOCAL-CONTRIBUTION-PROJECTION-1.0",
                "source_kind": "LOCAL_CONTRIBUTION_OVERLAY", "association": "LOCAL_CONTEXT_ONLY",
                "record_sha256": self.sha256, "origin": as_plain(self.data["provenance"]),
                "reference_snapshot": as_plain(self.data["reference_snapshot"]),
                "native_relationship_status": "NOT_ADMITTED_FOR_POSITIONING",
                "transmission_admission": "NOT_ADOPTED"}}


@dataclass(frozen=True, slots=True)
class LocalContributionRead:
    data: Mapping[str, object]

    def __post_init__(self) -> None:
        data = object_data(as_plain(self.data), READ_FIELDS)
        if data["contract_id"] != "LOCAL-CONTRIBUTION-READ-1.0":
            raise ValueError("LOCAL_CONTRIBUTION_READ")
        for key, prefix in (("object_ref", "local-content"), ("version_ref", "local-version"), ("passage_ref", "local-passage")):
            local_id(data[key], prefix)
        digest(data["record_sha256"])
        object.__setattr__(self, "data", freeze_safe_mapping(data))
