from dataclasses import fields, replace

import pytest

from backend.agent_runtime.agents.generation import (
    CorrectionMaterializationCode,
    CorrectionMaterializationError,
    CorrectionPreparationRequest,
    ResolvedCorrectionTarget,
)
from backend.agent_runtime.agents.review import CorrectionHandoffSignal
from backend.agent_runtime.contracts import AgentId, CorrectionRequest, InvocationStatus
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel.identifiers import TypedEntityId
from backend.shared_kernel.references import ObjectVersionRef, TypedEntityRef, VersionRef
from tests.support.multi_agent_security_fixtures import meta


def production_ref(version: str) -> ObjectVersionRef:
    return ObjectVersionRef(
        TypedEntityRef(TypedEntityId("production", "lesson-e")),
        VersionRef(version),
    )


def test_review_suggestions_return_to_ag01_and_are_never_executable_changes() -> None:
    handoff = CorrectionHandoffSignal(
        destination_agent_id=AgentId.AG_01,
        review_ref="review:e",
        review_id="review-e",
        target_production_ref=production_ref("v1"),
        finding_ids=("finding-e",),
        blocking_finding_ids=("finding-e",),
        evidence_refs=("evidence-e",),
        suggested_actions=(
            {
                "finding_id": "finding-e",
                "suggested_action": {"text": "Revise the exercise"},
            },
        ),
        limitations=(),
        warnings=(),
        security_signal_codes=(),
    )
    assert handoff.destination_agent_id is AgentId.AG_01
    assert "allowed_changes" not in {item.name for item in fields(handoff)}
    assert set(handoff.suggested_actions[0]) == {"finding_id", "suggested_action"}
    with pytest.raises(ValueError, match="destination"):
        replace(handoff, destination_agent_id=AgentId.AG_03)


def test_correction_preparation_refuses_lost_target_lineage() -> None:
    request = CorrectionRequest(
        meta=meta(InvocationStatus.PLANNED, AgentId.AG_01),
        target_production_ref=production_ref("v1"),
        review_ref="review:e",
        finding_ids=("finding-e",),
        evidence_refs=("evidence-e",),
        allowed_changes={"sections": ("exercise",)},
    )
    wrong_target = ResolvedCorrectionTarget(
        target_production_ref=production_ref("v2"),
        production_kind="lesson",
        output_format="markdown",
        content="Different version",
    )
    with pytest.raises(CorrectionMaterializationError) as raised:
        CorrectionPreparationRequest(
            capability_id=CapabilityId("CAP-G03"),
            request=request,
            target=wrong_target,
        )
    assert raised.value.code is CorrectionMaterializationCode.TARGET_LINEAGE_MISMATCH
