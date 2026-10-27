"""Default OFF owner composition; exact memory proof before any store/reference call."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping

from backend.adapters.inbound.application.local_contribution import LocalContributionInbound
from backend.modules.documents_provenance.contracts.dto.local_contribution_provenance import (
    LocalContributionProvenance,
    LocalContributionProvenanceV2,
    digest,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    fingerprint,
    object_data,
)
from backend.modules.resource_library.application.commands.register_local_contribution import (
    RegisterLocalContribution,
)
from backend.modules.resource_library.application.queries.read_local_contribution import (
    ReadLocalContribution,
)
from backend.modules.resource_library.contracts.dto.local_contribution import (
    LocalContributionAuthority,
    text_identity,
)
from backend.modules.resource_library.ports.outbound.local_contribution_store import (
    LocalContributionStorePort,
)


def contribution_adoption_scope(authority: Mapping[str, object], provenance: Mapping[str, object]) -> str:
    return fingerprint({"authority": {k: v for k, v in authority.items() if k != "operation_authorization_sha256"},
        "provenance": {k: v for k, v in provenance.items() if k != "operation_authorization_sha256"}})


def strict_proof(raw: bytes) -> dict[str, object]:
    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("LOCAL_CONTRIBUTION_PROOF_DUPLICATE")
            result[key] = value
        return result
    def nonfinite(_: str) -> None:
        raise ValueError("LOCAL_CONTRIBUTION_PROOF_NONFINITE")
    if type(raw) is not bytes or not 1 <= len(raw) <= 65536:
        raise ValueError("LOCAL_CONTRIBUTION_PROOF")
    return object_data(json.loads(raw, object_pairs_hook=unique, parse_constant=nonfinite),
        {"schema", "approved", "scope_sha256", "candidate_commit", "package_sha256", "plan_sha256", "prior_review_sha256"})


def _original_proposal_object(raw: bytes) -> dict[str, object]:
    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("LOCAL_CONTRIBUTION_ORIGINAL_PROPOSAL_DUPLICATE")
            result[key] = value
        return result
    def nonfinite(_: str) -> None:
        raise ValueError("LOCAL_CONTRIBUTION_ORIGINAL_PROPOSAL_NONFINITE")
    if type(raw) is not bytes or not 1 <= len(raw) <= 65536:
        raise ValueError("LOCAL_CONTRIBUTION_ORIGINAL_PROPOSAL")
    try:
        return object_data(json.loads(raw.decode("utf-8", errors="strict"), object_pairs_hook=unique, parse_constant=nonfinite))
    except UnicodeError as error:
        raise ValueError("LOCAL_CONTRIBUTION_ORIGINAL_PROPOSAL") from error


def _check_original_proposal(*, authority: LocalContributionAuthority,
        provenance: LocalContributionProvenance, evidence: bytes | None, expected_sha256: str | None) -> None:
    if type(provenance) is LocalContributionProvenance:
        if evidence is not None or expected_sha256 is not None:
            raise ValueError("LOCAL_CONTRIBUTION_UNUSED_ORIGINAL_PROPOSAL")
        return
    if type(provenance) is not LocalContributionProvenanceV2:
        raise ValueError("LOCAL_CONTRIBUTION_PROVENANCE_TYPE")
    if (type(evidence) is not bytes or expected_sha256 is None
            or hashlib.sha256(evidence).hexdigest() != digest(expected_sha256)
            or expected_sha256 != provenance.data["original_proposal_receipt_sha256"]):
        raise ValueError("LOCAL_CONTRIBUTION_ORIGINAL_PROPOSAL_BINDING")
    original = _original_proposal_object(evidence)
    if (original.get("schema") != "LU-M02-LOCAL-COMPLEMENT-PROPOSAL-NON-ADOPTE-1.0"
            or original.get("status") != "NON_ADOPTE" or original.get("contribution_kind") != "LOCAL_PEDAGOGICAL_DRAFT"
            or original.get("author") != provenance.data["author"]
            or original.get("timestamp_utc") != provenance.data["draft_recorded_at"]
            or original.get("authority") != "UNKNOWN" or original.get("official_reference") is not False
            or original.get("transmission_admission") != "NOT_ADOPTED"):
        raise ValueError("LOCAL_CONTRIBUTION_ORIGINAL_PROPOSAL_FIELDS")
    text_identity(original.get("proposed_local_text"), original.get("proposed_local_text_utf8_bytes"), original.get("proposed_local_text_sha256"))
    if (original.get("proposed_local_text_utf8_bytes") != authority.data["utf8_bytes"]
            or original.get("proposed_local_text_sha256") != authority.data["text_sha256"]):
        raise ValueError("LOCAL_CONTRIBUTION_ORIGINAL_PROPOSAL_TEXT")


def build_local_contribution_application(*, authority: LocalContributionAuthority,
        provenance: LocalContributionProvenance, owner_operation_evidence: bytes,
        expected_scope_sha256: str, expected_candidate_commit: str, expected_package_sha256: str,
        expected_plan_sha256: str, expected_prior_review_sha256: str,
        store: LocalContributionStorePort, reference_reader: Callable[[str], Mapping[str, object]],
        original_proposal_receipt_evidence: bytes | None = None,
        expected_original_proposal_receipt_sha256: str | None = None,
        enabled: bool = False) -> LocalContributionInbound:
    if type(enabled) is not bool:
        raise ValueError("LOCAL_CONTRIBUTION_ENABLED_BOOL")
    _check_original_proposal(authority=authority, provenance=provenance,
        evidence=original_proposal_receipt_evidence, expected_sha256=expected_original_proposal_receipt_sha256)
    if type(owner_operation_evidence) is not bytes:
        raise ValueError("LOCAL_CONTRIBUTION_OPERATION_EVIDENCE")
    if hashlib.sha256(owner_operation_evidence).hexdigest() != authority.data["operation_authorization_sha256"]:
        raise ValueError("LOCAL_CONTRIBUTION_OPERATION_EVIDENCE")
    proof = strict_proof(owner_operation_evidence)
    scope = contribution_adoption_scope(authority.data, provenance.data)
    if (proof["schema"] != "LOCAL-CONTRIBUTION-OWNER-OPERATION-PROOF-1.0" or proof["approved"] is not True
            or proof["scope_sha256"] != scope or scope != digest(expected_scope_sha256)
            or type(expected_candidate_commit) is not str or len(expected_candidate_commit) != 40 or any(c not in "0123456789abcdef" for c in expected_candidate_commit)
            or proof["candidate_commit"] != expected_candidate_commit
            or proof["package_sha256"] != digest(expected_package_sha256)
            or proof["plan_sha256"] != digest(expected_plan_sha256)
            or proof["prior_review_sha256"] != digest(expected_prior_review_sha256)):
        raise ValueError("LOCAL_CONTRIBUTION_ADOPTION_BINDING")
    return LocalContributionInbound(RegisterLocalContribution(store, authority=authority,
        provenance=provenance, reference_reader=reference_reader, enabled=enabled),
        ReadLocalContribution(store, authority=authority, provenance=provenance, enabled=enabled))
