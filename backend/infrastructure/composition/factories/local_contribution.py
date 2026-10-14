"""Default OFF owner composition; exact memory proof before any store/reference call."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping

from backend.adapters.inbound.application.local_contribution import LocalContributionInbound
from backend.modules.documents_provenance.contracts.dto.local_contribution_provenance import (
    LocalContributionProvenance,
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


def build_local_contribution_application(*, authority: LocalContributionAuthority,
        provenance: LocalContributionProvenance, owner_operation_evidence: bytes,
        expected_scope_sha256: str, expected_candidate_commit: str, expected_package_sha256: str,
        expected_plan_sha256: str, expected_prior_review_sha256: str,
        store: LocalContributionStorePort, reference_reader: Callable[[str], Mapping[str, object]],
        enabled: bool = False) -> LocalContributionInbound:
    if type(enabled) is not bool:
        raise ValueError("LOCAL_CONTRIBUTION_ENABLED_BOOL")
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
