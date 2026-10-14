"""Exact local overlay companion; no fallback to a canonical passage or provider."""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from backend.adapters.inbound.application.local_contribution import LocalContributionInbound
from backend.adapters.inbound.application.stmg_local_activity import STMGLocalActivityInbound
from backend.infrastructure.composition.factories.stmg_local_activity import (
    build_stmg_local_activity_application,
)
from backend.modules.pedagogical_context.contracts.dto.stmg_local_activity import (
    LocalActivityOwnerScope,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    fingerprint,
    object_data,
)
from backend.modules.resource_library.contracts.dto.local_contribution import LocalContributionRead


def build_stmg_local_contribution_application(*, contributions: LocalContributionInbound,
        choices: Sequence[Mapping[str, object]], exact_reads: Mapping[str, Mapping[str, object]],
        owner_scope: LocalActivityOwnerScope, expected_owner_scope_sha256: str,
        owner_decision_evidence: bytes, expected_owner_decision_sha256: str,
        basis_reader: Callable[[str], Mapping[str, object]], enabled: bool = False) -> STMGLocalActivityInbound:
    reads = {key: LocalContributionRead(value) for key, value in exact_reads.items()}
    def source_reader(identity: Mapping[str, object]) -> Mapping[str, object]:
        request = reads.get(fingerprint(identity))
        if request is None:
            raise ValueError("LOCAL_CONTRIBUTION_NOT_IN_EXACT_READ_SCOPE")
        observed = object_data(contributions.read(request.data))
        return object_data(observed["source_snapshot"])
    return build_stmg_local_activity_application(choices=choices, owner_scope=owner_scope,
        expected_owner_scope_sha256=expected_owner_scope_sha256,
        owner_decision_evidence=owner_decision_evidence, expected_owner_decision_sha256=expected_owner_decision_sha256,
        basis_reader=basis_reader, source_reader=source_reader, enabled=enabled)
