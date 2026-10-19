"""Closed, owner-approved identity for one local passage/context relation."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime

from backend.modules.knowledge_reference.contracts.dto.institutional_qualification import sha
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    fingerprint,
    object_data,
)

REQUEST_SCHEMA = "PASSAGE-CONTEXT-ADMISSION-REQUEST-1.1"
DECISION_SCHEMA = "PASSAGE-CONTEXT-OWNER-DECISION-1.0"
CONTROL_SCHEMA = "PASSAGE-CONTEXT-DECISION-CONTROL-1.0"
REQUEST_FIELDS = {
    "schema", "source_candidate_sha256", "fresh_destination", "object_kind",
    "object_ref", "passage_ref", "version_or_checksum", "excerpt_sha256",
    "program_ref", "program_version_ref", "question_ref", "notion_ref", "depth",
    "capacity_refs", "context_ref", "role", "relation_status",
    "available_authority", "provenance_sha256", "issued_at_utc", "expires_at_utc",
    "source_native_identity_sha256", "destination_parent_native_identity_sha256",
}
DECISION_FIELDS = {
    "schema", "request_sha256", "source_candidate_sha256", "fresh_destination",
    "object_ref", "passage_ref", "version_or_checksum", "excerpt_sha256",
    "selection_sha256", "context_ref", "scope", "issued_at_utc", "expires_at_utc",
}
CONTROL_FIELDS = {
    "schema", "request_sha256", "owner_decision_sha256",
    "expected_owner_decision_sha256", "decision_channel_sha256",
}
DEPTHS = frozenset({"DISCOVERY", "APPLICATION", "ANALYSIS"})


def _name(value: object) -> str:
    if not isinstance(value, str) or not value or len(value) > 400:
        raise ValueError("EXACT_PASSAGE_IDENTITY")
    return value


def _instant(value: object) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("EXACT_PASSAGE_WINDOW")
    try:
        result = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise ValueError("EXACT_PASSAGE_WINDOW") from error
    offset = result.utcoffset()
    if result.tzinfo is None or offset is None or offset.total_seconds() != 0:
        raise ValueError("EXACT_PASSAGE_WINDOW")
    return result.astimezone(UTC)


def selection_sha256(request: Mapping[str, object]) -> str:
    """One canonical selection, including provenance and exactly one notion."""
    capacity_refs = request["capacity_refs"]
    assert isinstance(capacity_refs, list)
    return fingerprint({
        "program_ref": request["program_ref"],
        "program_version_ref": request["program_version_ref"],
        "question_ref": request["question_ref"],
        "notion_ref": request["notion_ref"],
        "depth": request["depth"],
        "capacity_refs": sorted(capacity_refs),
        "provenance_sha256": request["provenance_sha256"],
    })


def validate_request(value: object) -> dict[str, object]:
    data = object_data(value, REQUEST_FIELDS)
    if (data["schema"] != REQUEST_SCHEMA or data["object_kind"] != "PEDAGOGICAL_CONTENT"
            or data["role"] != "MAIN" or data["relation_status"] != "ADMITTED"
            or data["available_authority"] != "UNKNOWN" or data["depth"] not in DEPTHS):
        raise ValueError("EXACT_PASSAGE_REQUEST_SCOPE")
    for key in ("source_candidate_sha256", "excerpt_sha256", "provenance_sha256",
                "source_native_identity_sha256", "destination_parent_native_identity_sha256"):
        sha(data[key])
    for key in ("fresh_destination", "object_ref", "passage_ref", "version_or_checksum",
                "program_ref", "program_version_ref", "question_ref", "notion_ref", "context_ref"):
        _name(data[key])
    capacities = data["capacity_refs"]
    if (not isinstance(capacities, list) or not 1 <= len(capacities) <= 16
            or any(not isinstance(item, str) or not item or len(item) > 400 for item in capacities)
            or len(set(capacities)) != len(capacities)):
        raise ValueError("EXACT_PASSAGE_CAPACITY")
    data["capacity_refs"] = list(capacities)
    if _instant(data["issued_at_utc"]) >= _instant(data["expires_at_utc"]):
        raise ValueError("EXACT_PASSAGE_WINDOW")
    return data


def validate_decision(value: object, request: Mapping[str, object]) -> dict[str, object]:
    data = object_data(value, DECISION_FIELDS)
    if data["schema"] != DECISION_SCHEMA or data["scope"] != "ONE_LOCAL_EXACT_PASSAGE_RELATION":
        raise ValueError("EXACT_PASSAGE_DECISION_SCOPE")
    if data["request_sha256"] != fingerprint(request) or data["selection_sha256"] != selection_sha256(request):
        raise ValueError("EXACT_PASSAGE_DECISION_CHANGED")
    for key in ("source_candidate_sha256", "fresh_destination", "object_ref", "passage_ref",
                "version_or_checksum", "excerpt_sha256", "context_ref"):
        if data[key] != request[key]:
            raise ValueError("EXACT_PASSAGE_DECISION_CHANGED")
    if (_instant(data["issued_at_utc"]) >= _instant(data["expires_at_utc"])
            or _instant(data["expires_at_utc"]) > _instant(request["expires_at_utc"])):
        raise ValueError("EXACT_PASSAGE_DECISION_WINDOW")
    return data


def validate_control(value: object, request: Mapping[str, object], decision: Mapping[str, object],
                     *, expected_owner_sha256: str, expected_channel_sha256: str) -> dict[str, object]:
    data = object_data(value, CONTROL_FIELDS)
    if (data["schema"] != CONTROL_SCHEMA or data["request_sha256"] != fingerprint(request)
            or data["owner_decision_sha256"] != fingerprint(decision)
            or data["expected_owner_decision_sha256"] != sha(expected_owner_sha256)
            or data["owner_decision_sha256"] != expected_owner_sha256
            or data["decision_channel_sha256"] != sha(expected_channel_sha256)):
        raise ValueError("EXACT_PASSAGE_ADOPTION_REQUIRED")
    return data


def validate_current_window(request: Mapping[str, object], decision: Mapping[str, object], now: datetime) -> None:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("EXACT_PASSAGE_WINDOW")
    current = now.astimezone(UTC)
    if not (_instant(request["issued_at_utc"]) <= current < _instant(request["expires_at_utc"])
            and _instant(decision["issued_at_utc"]) <= current < _instant(decision["expires_at_utc"])):
        raise ValueError("EXACT_PASSAGE_WINDOW_EXPIRED")
