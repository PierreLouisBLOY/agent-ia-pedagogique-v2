"""Local STMG qualification contracts; no provider admission or business I/O."""
from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from backend.modules.knowledge_reference.contracts.dto.stmg_frames import STMG_FRAMES
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    as_plain,
    fingerprint,
    object_data,
)
from backend.shared_kernel._safe_data import freeze_safe_mapping

CHOICE_FIELDS = {"contract_id", "choice_ref", "resource_type", "question_mode", "role",
    "positioning", "programme_support_sha256", "source_identity", "source_snapshot_sha256",
    "owner_local_decision_sha256", "native_relationship_status", "support_status", "support_limits"}
POSITION_FIELDS = {"frame", "level", "discipline", "program_ref", "program_version",
    "document_ref", "document_sha256", "theme_ref", "question_ref", "capacity_refs"}
SOURCE_FIELDS = {"notion_ref", "object_ref", "object_kind", "passage_ref", "version_or_checksum",
    "excerpt_sha256", "utf8_bytes"}
OWNER_SCOPE_FIELDS = {"contract_id", "owner_local_decision_sha256", "owner_proposal_sha256",
    "decision_item", "choice_sha256s", "qualification_scope", "evidence_kind"}


def require_hash(value: object) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError("LOCAL_ACTIVITY_HASH_REQUIRED")
    return value


@dataclass(frozen=True, slots=True)
class LocalActivityChoice:
    data: Mapping[str, object]

    def __post_init__(self) -> None:
        data = object_data(as_plain(self.data), CHOICE_FIELDS)
        if (data["contract_id"] != "STMG-LOCAL-ACTIVITY-CHOICE-1.0"
                or data["resource_type"] != "QUESTION_SET"
                or data["question_mode"] not in {"QCM", "QUIZ", "OPEN_QUESTIONS"}
                or data["role"] not in {"PREPARATORY_READING", "REACTIVATION"}
                or data["native_relationship_status"] != "NOT_ADMITTED_FOR_POSITIONING"
                or data["support_status"] not in {"LIMITED_FOR_LOCAL_PREPARATION", "INSUFFICIENT_FOR_HISTORICAL_CONTENT"}):
            raise ValueError("LOCAL_ACTIVITY_SCOPE")
        if not isinstance(data["choice_ref"], str) or not str(data["choice_ref"]).startswith("local-choice:"):
            raise ValueError("LOCAL_ACTIVITY_ID")
        position = object_data(data["positioning"], POSITION_FIELDS)
        frame = STMG_FRAMES.get(str(position["frame"]))
        if frame is None or (position["level"], position["discipline"]) != (frame[0], frame[6]):
            raise ValueError("LOCAL_ACTIVITY_POSITIONING")
        for key in ("program_ref", "program_version", "document_ref"):
            if not isinstance(position[key], str) or not 1 <= len(str(position[key])) <= 200:
                raise ValueError("LOCAL_ACTIVITY_POSITIONING")
        require_hash(position["document_sha256"])
        for key in ("theme_ref", "question_ref"):
            if position[key] is not None and (not isinstance(position[key], str) or not 1 <= len(str(position[key])) <= 200):
                raise ValueError("LOCAL_ACTIVITY_POSITIONING")
        caps = position["capacity_refs"]
        if (not isinstance(caps, (list, tuple)) or len(caps) > 16
                or not all(isinstance(v, str) and 0 < len(v) <= 200 for v in caps)
                or len(set(caps)) != len(caps)):
            raise ValueError("LOCAL_ACTIVITY_POSITIONING")
        if (position["question_ref"] is None or not caps) and data["role"] != "REACTIVATION":
            raise ValueError("LOCAL_ACTIVITY_POSITIONING")
        source = object_data(data["source_identity"], SOURCE_FIELDS)
        if source["object_kind"] not in {"PEDAGOGICAL_CONTENT", "METHOD"}:
            raise ValueError("LOCAL_ACTIVITY_DISCIPLINARY_SOURCE")
        for key in ("notion_ref", "object_ref", "passage_ref", "version_or_checksum"):
            if not isinstance(source[key], str) or not 1 <= len(str(source[key])) <= 200:
                raise ValueError("LOCAL_ACTIVITY_SOURCE_ID")
        if type(source["utf8_bytes"]) is not int or not 1 <= source["utf8_bytes"] <= 16000:
            raise ValueError("LOCAL_ACTIVITY_SOURCE_TEXT")
        for key in ("programme_support_sha256", "source_snapshot_sha256", "owner_local_decision_sha256"):
            require_hash(data[key])
        require_hash(source["excerpt_sha256"])
        limits = data["support_limits"]
        if (not isinstance(limits, (list, tuple)) or not 1 <= len(limits) <= 16
                or not all(isinstance(v, str) and 0 < len(v) <= 2000 for v in limits)):
            raise ValueError("LOCAL_ACTIVITY_SUPPORT_LIMITS")
        object.__setattr__(self, "data", freeze_safe_mapping(data))

    @property
    def sha256(self) -> str:
        return fingerprint(self.data)


@dataclass(frozen=True, slots=True)
class LocalActivityOwnerScope:
    """Trusted composition input; never populated from an inbound request."""
    data: Mapping[str, object]

    def __post_init__(self) -> None:
        data = object_data(as_plain(self.data), OWNER_SCOPE_FIELDS)
        if (data["contract_id"] != "STMG-LOCAL-ACTIVITY-OWNER-SCOPE-1.0"
                or data["qualification_scope"] != "LOCAL_QUALIFICATION_ONLY"
                or data["evidence_kind"] != "TECHNICAL_TRANSCRIPTION_NOT_SIGNATURE"
                or type(data["decision_item"]) is not int or data["decision_item"] < 0):
            raise ValueError("LOCAL_ACTIVITY_OWNER_SCOPE")
        require_hash(data["owner_local_decision_sha256"])
        require_hash(data["owner_proposal_sha256"])
        hashes = data["choice_sha256s"]
        if (not isinstance(hashes, (list, tuple)) or not 1 <= len(hashes) <= 64
                or not all(isinstance(v, str) for v in hashes)
                or list(hashes) != sorted(set(hashes))):
            raise ValueError("LOCAL_ACTIVITY_OWNER_SCOPE")
        for value in hashes:
            require_hash(value)
        object.__setattr__(self, "data", freeze_safe_mapping(data))

    @property
    def sha256(self) -> str:
        return fingerprint(self.data)

    @property
    def choice_sha256s(self) -> tuple[str, ...]:
        hashes = self.data["choice_sha256s"]
        if not isinstance(hashes, (list, tuple)):
            raise ValueError("LOCAL_ACTIVITY_OWNER_SCOPE")
        return tuple(str(value) for value in hashes)


def project_local_capacities(question: Mapping[str, object], phrases: Sequence[str]) -> list[dict[str, object]]:
    """Derived local projection only; never allocates native institutional IDs."""
    if (not isinstance(phrases, (list, tuple)) or not 1 <= len(phrases) <= 16
            or not all(isinstance(phrase, str) and bool(phrase) for phrase in phrases)
            or len(set(phrases)) != len(phrases)):
        raise ValueError("LOCAL_CAPACITY_PHRASES")
    text = question.get("official_text")
    if not isinstance(text, str) or any(not phrase or phrase not in text for phrase in phrases):
        raise ValueError("LOCAL_CAPACITY_PARENT_TEXT")
    return [{"projection_kind": "LOCAL_EXTRACTED_FROM_ADMITTED_QUESTION", "native_capacity_ref": None,
        "local_capacity_ref": "local-capacity:" + fingerprint({"question_ref": question["id"],
            "program_version": question["version_ref"], "document_ref": question["document_ref"], "exact_text": phrase})[:32],
        "parent_question_ref": question["id"], "program_version": question["version_ref"],
        "document_ref": question["document_ref"], "page": question["page"], "page_end": question["page_end"],
        "exact_text": phrase, "text_sha256": hashlib.sha256(phrase.encode("utf-8")).hexdigest()}
        for phrase in phrases]
