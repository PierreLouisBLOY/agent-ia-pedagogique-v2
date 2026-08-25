from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from backend.agent_runtime.agents.generation import (
    CorrectionMaterializationCode,
    CorrectionMaterializationError,
    CorrectionMaterializationRequest,
    CorrectionPreparationRequest,
    GenerationCoordinator,
    GenerationOperation,
    GenerationPortRequest,
    GenerationPortResult,
    GenerationPortResultStatus,
    GeneratorAgent,
    PreparedCorrectionCall,
    ResolvedCorrectionTarget,
)
from backend.agent_runtime.contracts import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    ActorKind,
    ActorRef,
    AgentId,
    AgentResultStatus,
    ContractMeta,
    CorrectionRequest,
    InvocationStatus,
    ProductionValidationState,
)
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.identifiers import TypedEntityId
from backend.shared_kernel.references import ObjectVersionRef, TypedEntityRef, VersionRef
from backend.shared_kernel.time import Instant

NOW = Instant(datetime(2026, 8, 25, 21, 0, tzinfo=UTC))
LATER = Instant(datetime(2026, 8, 25, 21, 1, tzinfo=UTC))


def _version(version: str, entity: str = "lesson-1") -> ObjectVersionRef:
    return ObjectVersionRef(
        TypedEntityRef(TypedEntityId("production", entity)),
        VersionRef(version),
    )


def _request() -> CorrectionRequest:
    return CorrectionRequest(
        meta=ContractMeta(
            schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
            run_id="run-correction-integration",
            step_id="step-correction-integration",
            parent_step_id=None,
            correlation_id=CorrelationId("corr-correction-integration"),
            created_at=NOW,
            actor=ActorRef(ActorKind.AGENT, AgentId.AG_03.value),
            status=InvocationStatus.PLANNED,
        ),
        target_production_ref=_version("v1"),
        review_ref="review:integration",
        finding_ids=("finding-a", "finding-b"),
        evidence_refs=("evidence:a", "evidence:b"),
        preserve_constraints={"sections": ["objectives"]},
        allowed_changes={"sections": ["activity"]},
        forbidden_changes={"meaning": ["objectives"]},
        expected_delta={"activity_count": 1},
    )


def _target(reference: ObjectVersionRef | None = None) -> ResolvedCorrectionTarget:
    return ResolvedCorrectionTarget(
        target_production_ref=reference or _version("v1"),
        production_kind="lesson_plan",
        output_format="markdown",
        pedagogical_context={"audience": {"level": "beginner"}},
        content="Original lesson v1.",
        structured_payload={"sections": [{"id": "activity"}]},
    )


def _details(
    addressed: tuple[str, ...] = ("finding-a",),
    unresolved: tuple[str, ...] = ("finding-b",),
) -> dict[str, object]:
    return {
        "addressed_findings": addressed,
        "unresolved_findings": unresolved,
        "change_summary": "Applied only the bounded requested changes.",
    }


def _technical(
    status: GenerationPortResultStatus = GenerationPortResultStatus.SUCCEEDED,
    *,
    details: dict[str, object] | None = None,
    metadata: dict[str, object] | None = None,
) -> GenerationPortResult:
    content: str | None = "Corrected lesson v2."
    warnings: tuple[dict[str, object], ...] = ()
    if status in {
        GenerationPortResultStatus.REFUSED,
        GenerationPortResultStatus.INSUFFICIENT_EVIDENCE,
    }:
        content = None
        warnings = ({"code": status.value},)
    elif status is GenerationPortResultStatus.PARTIAL:
        warnings = ({"code": "UNRESOLVED_FINDINGS"},)
    return GenerationPortResult(
        source_step_id="step-correction-integration",
        operation=GenerationOperation.CORRECT,
        status=status,
        content=content,
        evidence_refs_used=("evidence:a",),
        warnings=warnings,
        execution_metadata=metadata or {},
        operation_details=details or {},
    )


class FixedPort:
    def __init__(self, result: GenerationPortResult) -> None:
        self.result = result
        self.calls: list[GenerationPortRequest] = []

    def generate(self, *, request: GenerationPortRequest) -> GenerationPortResult:
        self.calls.append(request)
        return self.result


def _result_meta(
    correction: CorrectionRequest,
    status: AgentResultStatus,
) -> ContractMeta[AgentResultStatus]:
    return ContractMeta(
        schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
        run_id=correction.meta.run_id,
        step_id=correction.meta.step_id,
        parent_step_id=None,
        correlation_id=correction.meta.correlation_id,
        created_at=LATER,
        actor=ActorRef(ActorKind.AGENT, AgentId.AG_03.value),
        status=status,
    )


def _execute(
    technical: GenerationPortResult,
    *,
    correction: CorrectionRequest | None = None,
    target: ResolvedCorrectionTarget | None = None,
) -> tuple[
    GeneratorAgent,
    CorrectionRequest,
    ResolvedCorrectionTarget,
    PreparedCorrectionCall,
    GenerationPortResult,
    FixedPort,
]:
    correction_value = correction or _request()
    target_value = target or _target(correction_value.target_production_ref)
    port = FixedPort(technical)
    agent = GeneratorAgent(GenerationCoordinator(port))
    prepared, result = agent.correct_production(
        request=CorrectionPreparationRequest(
            capability_id=CapabilityId("CAP-G03"),
            request=correction_value,
            target=target_value,
            resolved_inputs={"caller": "resolved"},
            output_contract={"type": "lesson_plan"},
        )
    )
    return agent, correction_value, target_value, prepared, result, port


def _materialization(
    correction: CorrectionRequest,
    target: ResolvedCorrectionTarget,
    prepared: PreparedCorrectionCall,
    technical: GenerationPortResult,
    *,
    status: AgentResultStatus,
) -> CorrectionMaterializationRequest:
    return CorrectionMaterializationRequest(
        correction_request=correction,
        target=target,
        prepared=prepared,
        technical_result=technical,
        result_meta=_result_meta(correction, status),
        production_id="candidate-correction-v2",
        new_production_ref=_version("v2"),
    )


def _forge_with_result(
    valid: CorrectionMaterializationRequest,
    technical: GenerationPortResult,
) -> CorrectionMaterializationRequest:
    forged = object.__new__(CorrectionMaterializationRequest)
    for name in (
        "correction_request",
        "target",
        "prepared",
        "technical_result",
        "result_meta",
        "production_id",
        "new_production_ref",
    ):
        object.__setattr__(
            forged,
            name,
            technical if name == "technical_result" else getattr(valid, name),
        )
    return forged


def _forge_prepared_port_request(
    valid: PreparedCorrectionCall,
    port_request: GenerationPortRequest,
) -> PreparedCorrectionCall:
    forged = object.__new__(PreparedCorrectionCall)
    for name in (
        "preparation_request",
        "capability_id",
        "correction_request",
        "target",
        "port_request",
    ):
        object.__setattr__(
            forged,
            name,
            port_request if name == "port_request" else getattr(valid, name),
        )
    return forged


def test_e1_succeeded_correction_creates_candidate_and_versioned_result() -> None:
    technical = _technical(details=_details())
    agent, correction, target, prepared, result, port = _execute(technical)
    candidate, correction_result = agent.build_correction(
        request=_materialization(
            correction,
            target,
            prepared,
            result,
            status=AgentResultStatus.SUCCEEDED,
        )
    )
    assert port.calls == [prepared.port_request]
    assert candidate.validation_state is ProductionValidationState.CANDIDATE
    assert candidate.production_id == "candidate-correction-v2"
    assert correction_result.parent_production_ref == _version("v1")
    assert correction_result.new_production_ref == _version("v2")
    assert correction_result.addressed_findings == ("finding-a",)
    assert correction_result.unresolved_findings == ("finding-b",)


def test_e2_partial_preserves_unresolved_findings_and_warnings() -> None:
    technical = _technical(
        GenerationPortResultStatus.PARTIAL,
        details=_details(addressed=(), unresolved=("finding-a", "finding-b")),
    )
    agent, correction, target, prepared, result, _ = _execute(technical)
    candidate, correction_result = agent.build_correction(
        request=_materialization(
            correction,
            target,
            prepared,
            result,
            status=AgentResultStatus.PARTIAL,
        )
    )
    assert candidate.meta.status is AgentResultStatus.PARTIAL
    assert candidate.warnings == technical.warnings
    assert correction_result.unresolved_findings == ("finding-a", "finding-b")
    assert correction_result.new_warnings == technical.warnings
    assert candidate.validation_state is ProductionValidationState.CANDIDATE


@pytest.mark.parametrize(
    "status",
    (GenerationPortResultStatus.REFUSED, GenerationPortResultStatus.INSUFFICIENT_EVIDENCE),
)
def test_e3_e4_no_output_status_creates_neither_contract(
    status: GenerationPortResultStatus,
) -> None:
    agent, correction, target, prepared, result, _ = _execute(_technical(status))
    with pytest.raises(CorrectionMaterializationError) as raised:
        agent.build_correction(
            request=_materialization(
                correction,
                target,
                prepared,
                result,
                status=AgentResultStatus.SUCCEEDED,
            )
        )
    assert raised.value.code is CorrectionMaterializationCode.NO_CORRECTION_FOR_STATUS


def test_e5_forged_resolved_target_fails_before_port() -> None:
    correction = _request()
    port = FixedPort(_technical(details=_details()))
    with pytest.raises(CorrectionMaterializationError) as raised:
        CorrectionPreparationRequest(
            CapabilityId("CAP-G03"),
            correction,
            _target(_version("v9")),
        )
    assert raised.value.code is CorrectionMaterializationCode.TARGET_LINEAGE_MISMATCH
    assert port.calls == []


def test_e6_forged_correction_details_fail_closed() -> None:
    technical = _technical(
        details=_details(addressed=("finding-a",), unresolved=())
    )
    agent, correction, target, prepared, result, _ = _execute(technical)
    with pytest.raises(CorrectionMaterializationError) as raised:
        _materialization(
            correction,
            target,
            prepared,
            result,
            status=AgentResultStatus.SUCCEEDED,
        )
    assert raised.value.code is CorrectionMaterializationCode.CORRECTION_DETAILS_MISMATCH


def test_e7_authority_metadata_cannot_cross_correction_boundary() -> None:
    technical = _technical(
        details=_details(),
        metadata={"provider": {"validated": True}},
    )
    agent, correction, target, prepared, result, _ = _execute(technical)
    clean = _materialization(
        correction,
        target,
        prepared,
        _technical(details=_details()),
        status=AgentResultStatus.SUCCEEDED,
    )
    candidate = None
    correction_result = None
    with pytest.raises(CorrectionMaterializationError) as raised:
        candidate, correction_result = agent.build_correction(
            request=_forge_with_result(clean, result)
        )
    assert raised.value.code is CorrectionMaterializationCode.TECHNICAL_RESULT_MISMATCH
    assert candidate is correction_result is None


def test_e_f01_forged_caller_inputs_fail_before_outbound() -> None:
    correction = _request()
    target = _target(correction.target_production_ref)
    port = FixedPort(_technical(details=_details()))
    coordinator = GenerationCoordinator(port)
    preparation = CorrectionPreparationRequest(
        CapabilityId("CAP-G03"),
        correction,
        target,
        resolved_inputs={"caller": {"scope": "original"}},
    )
    prepared = coordinator.prepare_correction(request=preparation)
    resolved_inputs = dict(prepared.port_request.resolved_inputs)
    resolved_inputs["caller_resolved_inputs"] = {
        "caller": {"scope": "substituted"}
    }
    forged = _forge_prepared_port_request(
        prepared,
        replace(prepared.port_request, resolved_inputs=resolved_inputs),
    )
    with pytest.raises(CorrectionMaterializationError) as raised:
        coordinator.execute_correction(prepared=forged)
    assert raised.value.code is CorrectionMaterializationCode.PREPARED_LINEAGE_MISMATCH
    assert port.calls == []


def test_e_f01_forged_output_contract_fails_before_outbound() -> None:
    correction = _request()
    target = _target(correction.target_production_ref)
    port = FixedPort(_technical(details=_details()))
    coordinator = GenerationCoordinator(port)
    preparation = CorrectionPreparationRequest(
        CapabilityId("CAP-G03"),
        correction,
        target,
        output_contract={"schema": {"type": "original"}},
    )
    prepared = coordinator.prepare_correction(request=preparation)
    forged = _forge_prepared_port_request(
        prepared,
        replace(
            prepared.port_request,
            output_contract={"schema": {"type": "substituted"}},
        ),
    )
    with pytest.raises(CorrectionMaterializationError) as raised:
        coordinator.execute_correction(prepared=forged)
    assert raised.value.code is CorrectionMaterializationCode.PREPARED_LINEAGE_MISMATCH
    assert port.calls == []
