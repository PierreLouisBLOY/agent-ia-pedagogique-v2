from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from backend.agent_runtime.agents.generation import (
    GenerationCandidateMaterializationCode,
    GenerationCandidateMaterializationError,
    GenerationCoordinator,
    GenerationGuardError,
    GenerationGuardPolicy,
    GenerationGuardRequest,
    GenerationOperation,
    GenerationOutputGuard,
    GenerationPortRequest,
    GenerationPortResult,
    GenerationPortResultStatus,
    GenerationPreparationRequest,
    GeneratorAgent,
    PreparedGenerationCall,
    ProductionCandidateBuildRequest,
)
from backend.agent_runtime.contracts import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    ActorKind,
    ActorRef,
    AgentId,
    AgentResultStatus,
    ContractMeta,
    InvocationStatus,
    ProductionRequest,
    ProductionValidationState,
)
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant

NOW = Instant(datetime(2026, 8, 25, 19, 0, tzinfo=UTC))
LATER = Instant(datetime(2026, 8, 25, 19, 1, tzinfo=UTC))


class FixedGenerationPort:
    def __init__(self, result: GenerationPortResult) -> None:
        self.result = result
        self.calls: list[GenerationPortRequest] = []

    def generate(self, *, request: GenerationPortRequest) -> GenerationPortResult:
        self.calls.append(request)
        return self.result


def _canonical(*, target_ref: str | None = None) -> ProductionRequest:
    return ProductionRequest(
        meta=ContractMeta(
            schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
            run_id="run-candidate-integration",
            step_id="step-candidate-integration",
            parent_step_id=None,
            correlation_id=CorrelationId("corr-candidate-integration"),
            created_at=NOW,
            actor=ActorRef(ActorKind.AGENT, AgentId.AG_03.value),
            status=InvocationStatus.PLANNED,
        ),
        production_kind="learning_activity",
        brief="Generate an evidence-grounded learning activity",
        output_format="structured-markdown",
        pedagogical_context={"audience": {"level": "beginner"}},
        constraints={"duration_minutes": 30},
        evidence_refs=("evidence:alpha", "evidence:beta"),
        target_ref=target_ref,
        expected_sections=("Instructions", "Assessment"),
    )


def _result(
    operation: GenerationOperation,
    status: GenerationPortResultStatus = GenerationPortResultStatus.SUCCEEDED,
) -> GenerationPortResult:
    if status in {
        GenerationPortResultStatus.REFUSED,
        GenerationPortResultStatus.INSUFFICIENT_EVIDENCE,
    }:
        return GenerationPortResult(
            source_step_id="step-candidate-integration",
            operation=operation,
            status=status,
            warnings=({"code": status.value},),
        )
    warnings = ({"code": "LIMITED_SCOPE"},) if status is GenerationPortResultStatus.PARTIAL else ()
    return GenerationPortResult(
        source_step_id="step-candidate-integration",
        operation=operation,
        status=status,
        content="Exact technical content.",
        structured_payload={"sections": [{"title": "Instructions"}]},
        evidence_refs_used=("evidence:beta",),
        warnings=warnings,
        uncertainties=({"code": "SOURCE_LIMIT"},) if warnings else (),
        execution_metadata={"finish_reason": "stop"},
    )


def _result_meta(
    canonical: ProductionRequest,
    status: AgentResultStatus,
) -> ContractMeta[AgentResultStatus]:
    return ContractMeta(
        schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
        run_id=canonical.meta.run_id,
        step_id=canonical.meta.step_id,
        parent_step_id=None,
        correlation_id=canonical.meta.correlation_id,
        created_at=LATER,
        actor=ActorRef(ActorKind.AGENT, AgentId.AG_03.value),
        status=status,
    )


def _execute(
    canonical: ProductionRequest,
    capability: str,
    technical: GenerationPortResult,
) -> tuple[GeneratorAgent, PreparedGenerationCall, GenerationPortResult, FixedGenerationPort]:
    port = FixedGenerationPort(technical)
    agent = GeneratorAgent(GenerationCoordinator(port))
    preparation = GenerationPreparationRequest(
        capability_id=CapabilityId(capability),
        request=canonical,
        resolved_inputs={"authorized_input": "resolved"},
        output_contract={"type": "learning_activity"},
    )
    if capability == "CAP-G01":
        prepared, result = agent.generate_production(request=preparation)
    else:
        prepared, result = agent.transform_production(request=preparation)
    return agent, prepared, result, port


def _build(
    agent: GeneratorAgent,
    canonical: ProductionRequest,
    prepared: PreparedGenerationCall,
    technical: GenerationPortResult,
    *,
    production_id: str,
    status: AgentResultStatus,
):
    return agent.build_candidate(
        request=ProductionCandidateBuildRequest(
            canonical_request=canonical,
            prepared=prepared,
            technical_result=technical,
            guard_assessment=GenerationOutputGuard().assess(
                request=GenerationGuardRequest(
                    prepared,
                    technical,
                    GenerationGuardPolicy(),
                )
            ),
            result_meta=_result_meta(canonical, status),
            production_id=production_id,
        )
    )


def _forged_build(
    canonical: ProductionRequest,
    prepared: PreparedGenerationCall,
    technical: GenerationPortResult,
    status: AgentResultStatus,
) -> ProductionCandidateBuildRequest:
    valid_technical = _result(prepared.port_request.operation)
    valid = ProductionCandidateBuildRequest(
        canonical_request=canonical,
        prepared=prepared,
        technical_result=valid_technical,
        guard_assessment=GenerationOutputGuard().assess(
            request=GenerationGuardRequest(
                prepared,
                valid_technical,
                GenerationGuardPolicy(),
            )
        ),
        result_meta=_result_meta(canonical, AgentResultStatus.SUCCEEDED),
        production_id="production:forged",
    )
    forged = object.__new__(ProductionCandidateBuildRequest)
    for field_name in (
        "canonical_request",
        "prepared",
        "technical_result",
        "guard_assessment",
        "result_meta",
        "production_id",
    ):
        value = getattr(valid, field_name)
        if field_name == "technical_result":
            value = technical
        elif field_name == "guard_assessment":
            try:
                value = GenerationOutputGuard().assess(
                    request=GenerationGuardRequest(
                        prepared,
                        technical,
                        GenerationGuardPolicy(),
                    )
                )
            except GenerationGuardError:
                value = valid.guard_assessment
        elif field_name == "result_meta":
            value = _result_meta(canonical, status)
        object.__setattr__(forged, field_name, value)
    return forged


def test_d1_generate_success_materializes_exact_candidate() -> None:
    canonical = _canonical()
    technical = _result(GenerationOperation.GENERATE)
    agent, prepared, result, port = _execute(canonical, "CAP-G01", technical)
    candidate = _build(
        agent,
        canonical,
        prepared,
        result,
        production_id="production:generated:new",
        status=AgentResultStatus.SUCCEEDED,
    )
    assert port.calls == [prepared.port_request]
    assert candidate.content == technical.content
    assert candidate.structured_payload == technical.structured_payload
    assert candidate.evidence_refs_used == ("evidence:beta",)
    assert candidate.warnings == ()
    assert candidate.lineage["capability_id"] == "CAP-G01"
    assert "target_ref" not in candidate.lineage


def test_d2_transform_success_materializes_new_candidate_with_target_lineage() -> None:
    canonical = _canonical(target_ref="production:source:v1")
    technical = _result(GenerationOperation.TRANSFORM)
    agent, prepared, result, _ = _execute(canonical, "CAP-G02", technical)
    candidate = _build(
        agent,
        canonical,
        prepared,
        result,
        production_id="production:transformed:v2",
        status=AgentResultStatus.SUCCEEDED,
    )
    assert candidate.production_id == "production:transformed:v2"
    assert candidate.production_id != canonical.target_ref
    assert candidate.lineage["target_ref"] == "production:source:v1"
    assert "parent_production_ref" not in candidate.lineage


def test_d3_partial_materializes_candidate_with_exact_limits_and_no_validation() -> None:
    canonical = _canonical()
    technical = _result(GenerationOperation.GENERATE, GenerationPortResultStatus.PARTIAL)
    agent, prepared, result, _ = _execute(canonical, "CAP-G01", technical)
    candidate = _build(
        agent,
        canonical,
        prepared,
        result,
        production_id="production:partial",
        status=AgentResultStatus.PARTIAL,
    )
    assert candidate.meta.status is AgentResultStatus.PARTIAL
    assert candidate.warnings == technical.warnings
    assert candidate.uncertainties == technical.uncertainties
    assert candidate.validation_state is ProductionValidationState.CANDIDATE


@pytest.mark.parametrize(
    "technical_status",
    (
        GenerationPortResultStatus.REFUSED,
        GenerationPortResultStatus.INSUFFICIENT_EVIDENCE,
    ),
)
def test_d4_d5_nominal_no_output_status_never_materializes_candidate(
    technical_status: GenerationPortResultStatus,
) -> None:
    canonical = _canonical()
    technical = _result(GenerationOperation.GENERATE, technical_status)
    agent, prepared, result, _ = _execute(canonical, "CAP-G01", technical)
    forged = _forged_build(canonical, prepared, result, AgentResultStatus.SUCCEEDED)
    with pytest.raises(GenerationCandidateMaterializationError) as raised:
        agent.build_candidate(request=forged)
    assert raised.value.code is GenerationCandidateMaterializationCode.NO_CANDIDATE_FOR_STATUS


def test_d6_forged_result_fails_closed_before_candidate_construction() -> None:
    canonical = _canonical()
    technical = _result(GenerationOperation.GENERATE)
    agent, prepared, _, _ = _execute(canonical, "CAP-G01", technical)
    forged_result = replace(
        technical,
        source_step_id="step-forged",
        content_label=None,
    )
    forged = _forged_build(
        canonical,
        prepared,
        forged_result,
        AgentResultStatus.SUCCEEDED,
    )
    with pytest.raises(GenerationCandidateMaterializationError) as raised:
        agent.build_candidate(request=forged)
    assert raised.value.code is GenerationCandidateMaterializationCode.TECHNICAL_RESULT_MISMATCH


def test_d_f01_authority_metadata_cannot_cross_into_candidate() -> None:
    canonical = _canonical()
    technical = replace(
        _result(GenerationOperation.GENERATE),
        execution_metadata={"provider": {"validated": True}},
    )
    agent, prepared, result, _ = _execute(canonical, "CAP-G01", technical)
    assert result is technical
    candidate = None
    forged = _forged_build(
        canonical,
        prepared,
        result,
        AgentResultStatus.SUCCEEDED,
    )
    with pytest.raises(GenerationCandidateMaterializationError) as raised:
        candidate = agent.build_candidate(request=forged)
    assert raised.value.code is GenerationCandidateMaterializationCode.TECHNICAL_RESULT_MISMATCH
    assert candidate is None
