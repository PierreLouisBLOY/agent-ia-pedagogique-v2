from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime

import pytest

from backend.agent_runtime.agents.generation import (
    GenerationCandidateMaterializationCode,
    GenerationCandidateMaterializationError,
    GenerationCoordinator,
    GenerationOperation,
    GenerationPortError,
    GenerationPortErrorCode,
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

NOW = Instant(datetime(2026, 8, 25, 20, 0, tzinfo=UTC))
LATER = Instant(datetime(2026, 8, 25, 20, 1, tzinfo=UTC))
G01 = CapabilityId("CAP-G01")
G02 = CapabilityId("CAP-G02")
G03 = CapabilityId("CAP-G03")


def _canonical(
    *,
    suffix: str = "1",
    target_ref: str | None = None,
    production_kind: str = "lesson_plan",
) -> ProductionRequest:
    return ProductionRequest(
        meta=ContractMeta(
            schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
            run_id=f"run-agent-{suffix}",
            step_id=f"step-agent-{suffix}",
            parent_step_id=None,
            correlation_id=CorrelationId(f"corr-agent-{suffix}"),
            created_at=NOW,
            actor=ActorRef(ActorKind.AGENT, AgentId.AG_03.value),
            status=InvocationStatus.PLANNED,
        ),
        production_kind=production_kind,
        brief="Prepare a grounded lesson plan",
        output_format="markdown",
        pedagogical_context={"audience": {"level": "beginner"}},
        constraints={"sections": 3},
        evidence_refs=("evidence:one", "evidence:two"),
        target_ref=target_ref,
        expected_sections=("Objectives", "Activities"),
    )


def _meta(
    canonical: ProductionRequest,
    status: AgentResultStatus = AgentResultStatus.SUCCEEDED,
    *,
    run_id: str | None = None,
    step_id: str | None = None,
    correlation_id: str | None = None,
    actor: ActorRef | None = None,
) -> ContractMeta[AgentResultStatus]:
    return ContractMeta(
        schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
        run_id=run_id or canonical.meta.run_id,
        step_id=step_id or canonical.meta.step_id,
        parent_step_id=None,
        correlation_id=CorrelationId(
            correlation_id or canonical.meta.correlation_id.value
        ),
        created_at=LATER,
        actor=actor or ActorRef(ActorKind.AGENT, AgentId.AG_03.value),
        status=status,
    )


def _technical(
    operation: GenerationOperation = GenerationOperation.GENERATE,
    *,
    source_step_id: str = "step-agent-1",
    status: GenerationPortResultStatus = GenerationPortResultStatus.SUCCEEDED,
    content: str | None = "Generated lesson content.",
    structured_payload: dict[str, object] | None = None,
    evidence_refs_used: tuple[str, ...] = ("evidence:one",),
    warnings: tuple[dict[str, object], ...] = (),
    uncertainties: tuple[dict[str, object], ...] = (),
    execution_metadata: dict[str, object] | None = None,
) -> GenerationPortResult:
    if status in {
        GenerationPortResultStatus.REFUSED,
        GenerationPortResultStatus.INSUFFICIENT_EVIDENCE,
    }:
        content = None
        structured_payload = {}
        warnings = warnings or ({"code": status.value},)
    if status is GenerationPortResultStatus.PARTIAL:
        warnings = warnings or ({"code": "PARTIAL_LIMIT"},)
    return GenerationPortResult(
        source_step_id=source_step_id,
        operation=operation,
        status=status,
        content=content,
        structured_payload=structured_payload or {},
        evidence_refs_used=evidence_refs_used,
        warnings=warnings,
        uncertainties=uncertainties,
        execution_metadata=execution_metadata or {},
    )


class RecordingGenerationPort:
    def __init__(self, response: GenerationPortResult | GenerationPortError) -> None:
        self.response = response
        self.calls: list[GenerationPortRequest] = []

    def generate(self, *, request: GenerationPortRequest) -> GenerationPortResult:
        self.calls.append(request)
        if isinstance(self.response, GenerationPortError):
            raise self.response
        return self.response


class CountingCoordinator(GenerationCoordinator):
    __slots__ = ("execute_calls", "prepare_calls")

    def __init__(self, port: RecordingGenerationPort) -> None:
        super().__init__(port)
        self.prepare_calls: list[GenerationPreparationRequest] = []
        self.execute_calls: list[PreparedGenerationCall] = []

    def prepare(
        self,
        *,
        request: GenerationPreparationRequest,
    ) -> PreparedGenerationCall:
        self.prepare_calls.append(request)
        return super().prepare(request=request)

    def execute(
        self,
        *,
        prepared: PreparedGenerationCall,
    ) -> GenerationPortResult:
        self.execute_calls.append(prepared)
        return super().execute(prepared=prepared)


def _preparation(
    capability: CapabilityId = G01,
    *,
    canonical: ProductionRequest | None = None,
) -> GenerationPreparationRequest:
    return GenerationPreparationRequest(
        capability,
        canonical or _canonical(),
        resolved_inputs={"authorized": "resolved"},
        output_contract={"type": "lesson_plan"},
    )


def _prepared(
    capability: CapabilityId = G01,
    *,
    canonical: ProductionRequest | None = None,
) -> PreparedGenerationCall:
    request = _preparation(capability, canonical=canonical)
    return GenerationCoordinator(RecordingGenerationPort(_technical())).prepare(
        request=request
    )


def _build_request(
    *,
    canonical: ProductionRequest | None = None,
    prepared: PreparedGenerationCall | None = None,
    technical: GenerationPortResult | None = None,
    meta: ContractMeta[AgentResultStatus] | None = None,
    production_id: str = "production:new",
) -> ProductionCandidateBuildRequest:
    canonical_value = canonical or _canonical()
    prepared_value = prepared or _prepared(canonical=canonical_value)
    technical_value = technical or _technical(
        operation=prepared_value.port_request.operation,
        source_step_id=canonical_value.meta.step_id,
    )
    return ProductionCandidateBuildRequest(
        canonical_request=canonical_value,
        prepared=prepared_value,
        technical_result=technical_value,
        result_meta=meta or _meta(canonical_value),
        production_id=production_id,
    )


def _agent(
    response: GenerationPortResult | GenerationPortError | None = None,
) -> tuple[GeneratorAgent, CountingCoordinator, RecordingGenerationPort]:
    port = RecordingGenerationPort(response or _technical())
    coordinator = CountingCoordinator(port)
    return GeneratorAgent(coordinator), coordinator, port


def _forge_build(
    valid: ProductionCandidateBuildRequest,
    **overrides: object,
) -> ProductionCandidateBuildRequest:
    forged = object.__new__(ProductionCandidateBuildRequest)
    for field_name in (
        "canonical_request",
        "prepared",
        "technical_result",
        "result_meta",
        "production_id",
    ):
        object.__setattr__(
            forged,
            field_name,
            overrides.get(field_name, getattr(valid, field_name)),
        )
    return forged


def test_materialization_error_codes_are_closed_and_minimal() -> None:
    assert tuple(item.value for item in GenerationCandidateMaterializationCode) == (
        "UNSUPPORTED_CAPABILITY",
        "PREPARED_LINEAGE_MISMATCH",
        "TECHNICAL_RESULT_MISMATCH",
        "RESULT_META_MISMATCH",
        "NO_CANDIDATE_FOR_STATUS",
    )


def test_generator_agent_requires_generation_coordinator() -> None:
    with pytest.raises(TypeError, match="GenerationCoordinator"):
        GeneratorAgent(object())  # type: ignore[arg-type]


def test_generate_production_accepts_only_g01_and_returns_exact_objects() -> None:
    expected = _technical()
    agent, coordinator, _ = _agent(expected)
    request = _preparation()
    prepared, result = agent.generate_production(request=request)
    assert result is expected
    assert prepared is coordinator.execute_calls[0]
    assert coordinator.prepare_calls == [request]
    assert len(coordinator.execute_calls) == 1


@pytest.mark.parametrize("capability", (G02, G03, CapabilityId("CAP-E01")))
def test_generate_production_rejects_non_g01_capability(
    capability: CapabilityId,
) -> None:
    agent, coordinator, port = _agent()
    with pytest.raises(GenerationCandidateMaterializationError) as raised:
        agent.generate_production(request=_preparation(capability))
    assert raised.value.code is GenerationCandidateMaterializationCode.UNSUPPORTED_CAPABILITY
    assert coordinator.prepare_calls == []
    assert coordinator.execute_calls == []
    assert port.calls == []


def test_transform_production_accepts_only_g02_and_returns_exact_objects() -> None:
    canonical = _canonical(target_ref="production:target:v1")
    expected = _technical(GenerationOperation.TRANSFORM)
    agent, coordinator, _ = _agent(expected)
    request = _preparation(G02, canonical=canonical)
    prepared, result = agent.transform_production(request=request)
    assert result is expected
    assert prepared is coordinator.execute_calls[0]
    assert coordinator.prepare_calls == [request]
    assert len(coordinator.execute_calls) == 1


@pytest.mark.parametrize("capability", (G01, G03, CapabilityId("CAP-E01")))
def test_transform_production_rejects_non_g02_capability(
    capability: CapabilityId,
) -> None:
    agent, coordinator, port = _agent()
    with pytest.raises(GenerationCandidateMaterializationError) as raised:
        agent.transform_production(request=_preparation(capability))
    assert raised.value.code is GenerationCandidateMaterializationCode.UNSUPPORTED_CAPABILITY
    assert coordinator.prepare_calls == []
    assert coordinator.execute_calls == []
    assert port.calls == []


def test_generation_port_error_propagates_without_retry() -> None:
    error = GenerationPortError(
        GenerationPortErrorCode.UNAVAILABLE,
        "Generation mechanism unavailable",
    )
    agent, coordinator, port = _agent(error)
    with pytest.raises(GenerationPortError) as raised:
        agent.generate_production(request=_preparation())
    assert raised.value is error
    assert len(coordinator.prepare_calls) == 1
    assert len(coordinator.execute_calls) == 1
    assert len(port.calls) == 1


def test_candidate_build_request_is_frozen_and_slotted() -> None:
    request = _build_request()
    with pytest.raises(FrozenInstanceError):
        request.production_id = "changed"  # type: ignore[misc]
    assert not hasattr(request, "__dict__")


def test_candidate_build_request_rejects_empty_production_id() -> None:
    with pytest.raises(ValueError, match="production_id"):
        _build_request(production_id=" ")


def test_build_g01_succeeded_candidate_maps_exact_content_and_identity() -> None:
    technical = _technical(
        content="Exact generated content.",
        evidence_refs_used=("evidence:two",),
    )
    request = _build_request(technical=technical, production_id="production:g01:new")
    candidate = _agent()[0].build_candidate(request=request)
    assert candidate.meta is request.result_meta
    assert candidate.production_id == "production:g01:new"
    assert candidate.production_kind == request.canonical_request.production_kind
    assert candidate.content == "Exact generated content."
    assert candidate.evidence_refs_used == ("evidence:two",)
    assert candidate.validation_state is ProductionValidationState.CANDIDATE


def test_build_g02_succeeded_candidate_keeps_target_and_new_id() -> None:
    canonical = _canonical(target_ref="production:target:v1")
    prepared = _prepared(G02, canonical=canonical)
    technical = _technical(
        GenerationOperation.TRANSFORM,
        source_step_id=canonical.meta.step_id,
    )
    request = _build_request(
        canonical=canonical,
        prepared=prepared,
        technical=technical,
        production_id="production:transformed:new",
    )
    candidate = _agent()[0].build_candidate(request=request)
    assert candidate.production_id == "production:transformed:new"
    assert candidate.production_id != canonical.target_ref
    assert candidate.lineage["target_ref"] == canonical.target_ref
    assert "parent_production_ref" not in candidate.lineage


def test_partial_materializes_partial_candidate_with_exact_limits() -> None:
    technical = _technical(
        status=GenerationPortResultStatus.PARTIAL,
        warnings=({"code": "TRUNCATED", "details": {"sections": ["Assessment"]}},),
        uncertainties=({"code": "EVIDENCE_LIMIT"},),
    )
    canonical = _canonical()
    request = _build_request(
        canonical=canonical,
        technical=technical,
        meta=_meta(canonical, AgentResultStatus.PARTIAL),
    )
    candidate = _agent()[0].build_candidate(request=request)
    assert candidate.meta.status is AgentResultStatus.PARTIAL
    assert candidate.warnings == technical.warnings
    assert candidate.uncertainties == technical.uncertainties
    assert candidate.validation_state is ProductionValidationState.CANDIDATE


@pytest.mark.parametrize(
    "status",
    (
        GenerationPortResultStatus.REFUSED,
        GenerationPortResultStatus.INSUFFICIENT_EVIDENCE,
    ),
)
def test_non_candidate_technical_status_is_rejected(
    status: GenerationPortResultStatus,
) -> None:
    with pytest.raises(GenerationCandidateMaterializationError) as raised:
        _build_request(technical=_technical(status=status))
    assert raised.value.code is GenerationCandidateMaterializationCode.NO_CANDIDATE_FOR_STATUS


@pytest.mark.parametrize(
    ("technical_status", "meta_status"),
    (
        (GenerationPortResultStatus.PARTIAL, AgentResultStatus.SUCCEEDED),
        (GenerationPortResultStatus.SUCCEEDED, AgentResultStatus.PARTIAL),
    ),
)
def test_result_meta_status_must_match_technical_status(
    technical_status: GenerationPortResultStatus,
    meta_status: AgentResultStatus,
) -> None:
    canonical = _canonical()
    with pytest.raises(GenerationCandidateMaterializationError) as raised:
        _build_request(
            canonical=canonical,
            technical=_technical(status=technical_status),
            meta=_meta(canonical, meta_status),
        )
    assert raised.value.code is GenerationCandidateMaterializationCode.RESULT_META_MISMATCH


@pytest.mark.parametrize(
    "meta",
    (
        _meta(_canonical(), run_id="other-run"),
        _meta(_canonical(), step_id="other-step"),
        _meta(_canonical(), correlation_id="other-correlation"),
        _meta(
            _canonical(),
            actor=ActorRef(ActorKind.AGENT, AgentId.AG_02.value),
        ),
        _meta(
            _canonical(),
            actor=ActorRef(ActorKind.APPLICATION, "application"),
        ),
    ),
)
def test_result_meta_lineage_and_actor_must_match_ag03(
    meta: ContractMeta[AgentResultStatus],
) -> None:
    with pytest.raises(GenerationCandidateMaterializationError) as raised:
        _build_request(meta=meta)
    assert raised.value.code is GenerationCandidateMaterializationCode.RESULT_META_MISMATCH


def test_prepared_canonical_request_must_match_build_request() -> None:
    canonical = _canonical()
    foreign = _canonical(suffix="foreign", production_kind="quiz")
    with pytest.raises(GenerationCandidateMaterializationError) as raised:
        _build_request(canonical=canonical, prepared=_prepared(canonical=foreign))
    assert raised.value.code is GenerationCandidateMaterializationCode.PREPARED_LINEAGE_MISMATCH


def test_forged_prepared_operation_is_rejected() -> None:
    prepared = _prepared()
    forged = object.__new__(PreparedGenerationCall)
    object.__setattr__(forged, "capability_id", prepared.capability_id)
    object.__setattr__(forged, "canonical_request", prepared.canonical_request)
    object.__setattr__(
        forged,
        "port_request",
        replace(prepared.port_request, operation=GenerationOperation.TRANSFORM),
    )
    with pytest.raises(GenerationCandidateMaterializationError) as raised:
        _build_request(prepared=forged)
    assert raised.value.code is GenerationCandidateMaterializationCode.PREPARED_LINEAGE_MISMATCH


@pytest.mark.parametrize(
    "technical",
    (
        _technical(source_step_id="forged-step"),
        _technical(operation=GenerationOperation.TRANSFORM),
        _technical(evidence_refs_used=("evidence:foreign",)),
        _technical(evidence_refs_used=("evidence:one", "evidence:one")),
    ),
)
def test_technical_result_lineage_mismatch_is_rejected(
    technical: GenerationPortResult,
) -> None:
    with pytest.raises(GenerationCandidateMaterializationError) as raised:
        _build_request(technical=technical)
    assert raised.value.code is GenerationCandidateMaterializationCode.TECHNICAL_RESULT_MISMATCH


def test_candidate_structured_payload_and_limits_remain_deeply_immutable() -> None:
    technical = _technical(
        content=None,
        structured_payload={"sections": [{"title": "Objectives"}]},
        warnings=({"details": {"codes": ["ONE"]}},),
        uncertainties=({"basis": {"refs": ["evidence:one"]}},),
    )
    candidate = _agent()[0].build_candidate(
        request=_build_request(technical=technical)
    )
    assert candidate.structured_payload == {
        "sections": ({"title": "Objectives"},)
    }
    assert candidate.warnings == technical.warnings
    assert candidate.uncertainties == technical.uncertainties
    with pytest.raises(TypeError):
        candidate.structured_payload["sections"] = ()  # type: ignore[index]
    with pytest.raises(TypeError):
        candidate.warnings[0]["details"] = {}  # type: ignore[index]
    with pytest.raises(TypeError):
        candidate.uncertainties[0]["basis"] = {}  # type: ignore[index]


def test_candidate_g01_lineage_is_minimal_and_contains_no_target() -> None:
    request = _build_request()
    candidate = _agent()[0].build_candidate(request=request)
    assert candidate.lineage == {
        "source_run_id": request.canonical_request.meta.run_id,
        "source_step_id": request.canonical_request.meta.step_id,
        "source_correlation_id": request.canonical_request.meta.correlation_id.value,
        "source_request_schema_version": "1.0",
        "capability_id": "CAP-G01",
        "generation_operation": "GENERATE",
    }
    assert "target_ref" not in candidate.lineage
    assert "parent_production_ref" not in candidate.lineage


def test_candidate_generation_metadata_is_factual_and_authority_free() -> None:
    technical = _technical(
        execution_metadata={
            "finish_reason": "stop",
            "operation": "FORGED",
            "technical_status": "FORGED",
        }
    )
    candidate = _agent()[0].build_candidate(
        request=_build_request(technical=technical)
    )
    assert candidate.generation_metadata == {
        "finish_reason": "stop",
        "operation": "GENERATE",
        "technical_status": "SUCCEEDED",
    }
    assert set(candidate.generation_metadata).isdisjoint(
        {"approved", "promoted", "safe", "trusted", "validated", "quality_score"}
    )


def test_build_candidate_revalidates_forged_build_request() -> None:
    valid = _build_request()
    forged = _forge_build(
        valid,
        technical_result=_technical(source_step_id="forged-step"),
    )
    with pytest.raises(GenerationCandidateMaterializationError) as raised:
        _agent()[0].build_candidate(request=forged)
    assert raised.value.code is GenerationCandidateMaterializationCode.TECHNICAL_RESULT_MISMATCH


def test_build_candidate_rejects_wrong_request_type() -> None:
    with pytest.raises(TypeError, match="ProductionCandidateBuildRequest"):
        _agent()[0].build_candidate(request=object())  # type: ignore[arg-type]


def test_materialization_error_requires_safe_reason_and_valid_code() -> None:
    with pytest.raises(ValueError, match="safe_reason"):
        GenerationCandidateMaterializationError(
            GenerationCandidateMaterializationCode.RESULT_META_MISMATCH,
            " ",
        )
    with pytest.raises(TypeError, match="code"):
        GenerationCandidateMaterializationError("BAD", "Safe")  # type: ignore[arg-type]
