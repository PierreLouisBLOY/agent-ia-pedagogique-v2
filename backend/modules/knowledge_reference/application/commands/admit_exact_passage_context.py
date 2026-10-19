"""Admit one local relation after independent passage and owner checks."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from datetime import UTC, datetime

from backend.modules.knowledge_reference.contracts.dto.exact_passage_context import (
    selection_sha256,
    validate_control,
    validate_current_window,
    validate_decision,
    validate_request,
)
from backend.modules.knowledge_reference.ports.outbound.exact_passage_context import (
    ExactPassageContextPort,
    PassageEvidencePort,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import fingerprint


class AdmitExactPassageContext:
    def __init__(self, port: ExactPassageContextPort, evidence: PassageEvidencePort, *,
                 expected_owner_sha256: str, expected_channel_sha256: str,
                 expected_source_sha256: str, expected_destination: str,
                 expected_source_native_identity_sha256: str,
                 expected_destination_parent_native_identity_sha256: str) -> None:
        self.port = port
        self.evidence = evidence
        self.expected_owner_sha256 = expected_owner_sha256
        self.expected_channel_sha256 = expected_channel_sha256
        self.expected_source_sha256 = expected_source_sha256
        self.expected_destination = expected_destination
        self.expected_source_native_identity_sha256 = expected_source_native_identity_sha256
        self.expected_destination_parent_native_identity_sha256 = expected_destination_parent_native_identity_sha256

    def execute(self, request: Mapping[str, object], decision: Mapping[str, object],
                control: Mapping[str, object], *, now: datetime | None = None) -> dict[str, object]:
        checked = validate_request(request)
        approved = validate_decision(decision, checked)
        checked_control = validate_control(control, checked, approved,
                                           expected_owner_sha256=self.expected_owner_sha256,
                                           expected_channel_sha256=self.expected_channel_sha256)
        validate_current_window(checked, approved, now or datetime.now(UTC))
        for key, expected in (
            ("source_candidate_sha256", self.expected_source_sha256),
            ("fresh_destination", self.expected_destination),
            ("source_native_identity_sha256", self.expected_source_native_identity_sha256),
            ("destination_parent_native_identity_sha256", self.expected_destination_parent_native_identity_sha256),
        ):
            if checked[key] != expected:
                raise ValueError("EXACT_PASSAGE_TARGET_CHANGED")
        passage = self.evidence.read_passage(str(checked["object_ref"]), str(checked["passage_ref"]))
        if (passage is None or passage.version_or_checksum != checked["version_or_checksum"]
                or passage.provenance_sha256 != checked["provenance_sha256"]
                or not passage.usage_permitted or passage.sensitive
                or passage.available_authority != "UNKNOWN"
                or not 0 < len(passage.excerpt_bytes) <= 1024 * 1024
                or hashlib.sha256(passage.excerpt_bytes).hexdigest() != checked["excerpt_sha256"]):
            raise ValueError("EXACT_PASSAGE_SOURCE_INELIGIBLE")
        self.port.validate_scope(checked)
        selection = selection_sha256(checked)
        owner = fingerprint(approved)
        row_sha = self.port.add_one(checked, selection_sha256=selection,
                                    owner_decision_sha256=owner)
        try:
            row = self.port.read_exact(checked, selection_sha256=selection)
        except Exception:
            row = None
        readback_verified = (row is not None and row.get("owner_decision_sha256") == owner
                             and row.get("row_sha256") == row_sha)
        return {
            "contract_id": "PASSAGE-CONTEXT-ADMISSION-RECEIPT-1.0",
            "request_sha256": fingerprint(checked),
            "owner_decision_sha256": owner,
            "decision_control_sha256": fingerprint(checked_control),
            "source_candidate_sha256": checked["source_candidate_sha256"],
            "fresh_destination_sha256": fingerprint(checked["fresh_destination"]),
            "source_native_identity_sha256": checked["source_native_identity_sha256"],
            "destination_parent_native_identity_sha256": checked["destination_parent_native_identity_sha256"],
            "selection_sha256": selection,
            "relation_sha256": row_sha,
            "relations_added": 1,
            "readback_verified": readback_verified,
            "available_authority": "UNKNOWN",
            "original_modified": False,
            "provider_calls": 0,
            "status": ("SYNTHETIC_COPY_RELATION_READ_BACK_NOT_ACTIVATED" if readback_verified
                       else "SYNTHETIC_COMMITTED_READBACK_UNVERIFIED_STOP"),
            "teaching_acceptance": "NOT_PERFORMED",
        }
