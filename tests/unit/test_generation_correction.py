from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime

import pytest

from backend.agent_runtime.agents.generation import (
    CorrectionMaterializationCode,
    CorrectionMaterializationError,
    CorrectionMaterializationRequest,
    CorrectionPreparationRequest,
    GenerationCoordinator,
    GenerationOperation,
    GenerationPortError,
    GenerationPortErrorCode,
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
from backend.shared_kernel.references import (
    ObjectVersionRef,
    TypedEntityRef,
    VersionRef,
)
from backend.shared_kernel.time import Instant

NOW = Instant(datetime(2026, 8, 25, 20, 0, tzinfo=UTC))
LATER = Instant(datetime(2026, 8, 25, 20, 1, tzinfo=UTC))
G03 = CapabilityId("CAP-G03")


def _version(version: str = "v1", *, entity: str = "production-1") -> ObjectVersionRef:
    return ObjectVersionRef(
        TypedEntityRef(TypedEntityId("production", entity)),
        VersionRef(version),
    )


def _correction(
    *,
    target_ref: ObjectVersionRef | None = None,
) -> CorrectionRequest:
    return CorrectionRequest(
        meta=ContractMeta(
            schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
            run_id="run-correction-1",
            step_id="step-correction-1",
            parent_step_id=None,
            correlation_id=CorrelationId("corr-correction-1"),
            created_at=NOW,
            actor=ActorRef(ActorKind.AGENT, AgentId.AG_03.value),
            status=InvocationStatus.PLANNED,
        ),
        target_production_ref=target_ref or _version(),
        review_ref="review:1",
        finding_ids=("finding-1", "finding-2"),
        evidence_refs=("evidence:one", "evidence:two"),
        preserve_constraints={"keep": ["objectives"]},
        allowed_changes={"sections": ["activities"]},
        forbidden_changes={"sections": ["objectives"]},
        expected_delta={"activity_count": 1},
    )


def _target(
    *,
    target_ref: ObjectVersionRef | None = None,
    content: str | None = "Original production content.",
    structured_payload: dict[str, object] | None = None,
) -> ResolvedCorrectionTarget:
    return ResolvedCorrectionTarget(
        target_production_ref=target_ref or _version(),
        production_kind="lesson_plan",
        output_format="markdown",
        pedagogical_context={"audience": {"level": "beginner"}},
        content=content,
        structured_payload=structured_payload or {},
    )


def _details(
    *,
    addressed: object = ("finding-1",),
    unresolved: object = ("finding-2",),
    change_summary: object = "Updated the bounded activity section.",
) -> dict[str, object]:
    return {
        "addressed_findings": addressed,
        "unresolved_findings": unresolved,
        "change_summary": change_summary,
    }


def _technical(
    *,
    status: GenerationPortResultStatus = GenerationPortResultStatus.SUCCEEDED,
    source_step_id: str = "step-correction-1",
    operation: GenerationOperation = GenerationOperation.CORRECT,
    evidence_refs_used: tuple[str, ...] = ("evidence:one",),
    operation_details: dict[str, object] | None = None,
    execution_metadata: dict[str, object] | None = None,
    warnings: tuple[dict[str, object], ...] = (),
) -> GenerationPortResult:
    content: str | None = "Corrected production content."
    if status in {
        GenerationPortResultStatus.REFUSED,
        GenerationPortResultStatus.INSUFFICIENT_EVIDENCE,
    }:
        content = None
        warnings = warnings or ({"code": status.value},)
    elif status is GenerationPortResultStatus.PARTIAL:
        warnings = warnings or ({"code": "PARTIAL_CORRECTION"},)
    return GenerationPortResult(
        source_step_id=source_step_id,
        operation=operation,
        status=status,
        content=content,
        structured_payload={},
        evidence_refs_used=evidence_refs_used,
        warnings=warnings,
        uncertainties=(),
        execution_metadata=execution_metadata or {},
        operation_details=operation_details if operation_details is not None else _details(),
    )


class RecordingPort:
    def __init__(self, response: GenerationPortResult | GenerationPortError) -> None:
        self.response = response
        self.calls: list[GenerationPortRequest] = []

    def generate(self, *, request: GenerationPortRequest) -> GenerationPortResult:
        self.calls.append(request)
        if isinstance(self.response, GenerationPortError):
            raise self.response
        return self.response


class CountingCoordinator(GenerationCoordinator):
    __slots__ = ("execute_correction_calls", "prepare_correction_calls")

    def __init__(self, port: RecordingPort) -> None:
        super().__init__(port)
        self.prepare_correction_calls: list[CorrectionPreparationRequest] = []
        self.execute_correction_calls: list[PreparedCorrectionCall] = []

    def prepare_correction(
        self,
        *,
        request: CorrectionPreparationRequest,
    ) -> PreparedCorrectionCall:
        self.prepare_correction_calls.append(request)
        return super().prepare_correction(request=request)

    def execute_correction(
        self,
        *,
        prepared: PreparedCorrectionCall,
    ) -> GenerationPortResult:
        self.execute_correction_calls.append(prepared)
        return super().execute_correction(prepared=prepared)


def _preparation(
    *,
    correction: CorrectionRequest | None = None,
    target: ResolvedCorrectionTarget | None = None,
) -> CorrectionPreparationRequest:
    correction_value = correction or _correction()
    return CorrectionPreparationRequest(
        capability_id=G03,
        request=correction_value,
        target=target or _target(target_ref=correction_value.target_production_ref),
        resolved_inputs={"caller": {"scope": "bounded"}},
        output_contract={"type": "lesson_plan"},
    )


def _prepared(
    *,
    correction: CorrectionRequest | None = None,
    target: ResolvedCorrectionTarget | None = None,
) -> PreparedCorrectionCall:
    return GenerationCoordinator(RecordingPort(_technical())).prepare_correction(
        request=_preparation(correction=correction, target=target)
    )


def _meta(
    correction: CorrectionRequest,
    status: AgentResultStatus = AgentResultStatus.SUCCEEDED,
    *,
    run_id: str | None = None,
    step_id: str | None = None,
    correlation_id: str | None = None,
    actor: ActorRef | None = None,
) -> ContractMeta[AgentResultStatus]:
    return ContractMeta(
        schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
        run_id=run_id or correction.meta.run_id,
        step_id=step_id or correction.meta.step_id,
        parent_step_id=None,
        correlation_id=CorrelationId(
            correlation_id or correction.meta.correlation_id.value
        ),
        created_at=LATER,
        actor=actor or ActorRef(ActorKind.AGENT, AgentId.AG_03.value),
        status=status,
    )


def _materialization(
    *,
    correction: CorrectionRequest | None = None,
    target: ResolvedCorrectionTarget | None = None,
    prepared: PreparedCorrectionCall | None = None,
    technical: GenerationPortResult | None = None,
    meta: ContractMeta[AgentResultStatus] | None = None,
    production_id: str = "candidate-corrected-1",
    new_ref: ObjectVersionRef | None = None,
) -> CorrectionMaterializationRequest:
    correction_value = correction or _correction()
    target_value = target or _target(
        target_ref=correction_value.target_production_ref
    )
    prepared_value = prepared or _prepared(
        correction=correction_value,
        target=target_value,
    )
    technical_value = technical or _technical()
    return CorrectionMaterializationRequest(
        correction_request=correction_value,
        target=target_value,
        prepared=prepared_value,
        technical_result=technical_value,
        result_meta=meta or _meta(correction_value),
        production_id=production_id,
        new_production_ref=new_ref or _version("v2"),
    )


def _forge_preparation(
    valid: CorrectionPreparationRequest,
    capability: CapabilityId,
) -> CorrectionPreparationRequest:
    forged = object.__new__(CorrectionPreparationRequest)
    for name in ("capability_id", "request", "target", "resolved_inputs", "output_contract"):
        object.__setattr__(forged, name, capability if name == "capability_id" else getattr(valid, name))
    return forged


def _forge_prepared(
    valid: PreparedCorrectionCall,
    **overrides: object,
) -> PreparedCorrectionCall:
    forged = object.__new__(PreparedCorrectionCall)
    for name in (
        "preparation_request",
        "capability_id",
        "correction_request",
        "target",
        "port_request",
    ):
        object.__setattr__(forged, name, overrides.get(name, getattr(valid, name)))
    return forged


def _forge_materialization(
    valid: CorrectionMaterializationRequest,
    **overrides: object,
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
        object.__setattr__(forged, name, overrides.get(name, getattr(valid, name)))
    return forged


def test_resolved_target_is_frozen_and_slotted() -> None:
    target = _target()
    with pytest.raises(FrozenInstanceError):
        target.content = "changed"  # type: ignore[misc]
    assert not hasattr(target, "__dict__")


def test_resolved_target_requires_exact_version_ref_type() -> None:
    with pytest.raises(TypeError, match="ObjectVersionRef"):
        ResolvedCorrectionTarget(object(), "lesson", "markdown", content="x")  # type: ignore[arg-type]


def test_resolved_target_requires_content_or_payload() -> None:
    with pytest.raises(ValueError, match="content or structured_payload"):
        _target(content=None)
    assert _target(content=None, structured_payload={"sections": ["one"]}).content is None


def test_resolved_target_context_and_payload_are_deeply_immutable() -> None:
    target = _target(structured_payload={"sections": [{"id": "one"}]})
    assert target.structured_payload == {"sections": ({"id": "one"},)}
    with pytest.raises(TypeError):
        target.pedagogical_context["audience"] = {}  # type: ignore[index]
    with pytest.raises(TypeError):
        target.structured_payload["sections"] = ()  # type: ignore[index]


@pytest.mark.parametrize("capability", (CapabilityId("CAP-G01"), CapabilityId("CAP-G02"), CapabilityId("CAP-E01")))
def test_correction_preparation_requires_g03(capability: CapabilityId) -> None:
    valid = _preparation()
    with pytest.raises(CorrectionMaterializationError) as raised:
        CorrectionPreparationRequest(capability, valid.request, valid.target)
    assert raised.value.code is CorrectionMaterializationCode.UNSUPPORTED_CAPABILITY


def test_correction_preparation_requires_exact_target_lineage() -> None:
    with pytest.raises(CorrectionMaterializationError) as raised:
        _preparation(target=_target(target_ref=_version("v9")))
    assert raised.value.code is CorrectionMaterializationCode.TARGET_LINEAGE_MISMATCH


def test_prepare_correction_maps_c11_target_and_closed_inputs_exactly() -> None:
    preparation = _preparation()
    prepared = GenerationCoordinator(RecordingPort(_technical())).prepare_correction(
        request=preparation
    )
    technical = prepared.port_request
    correction = preparation.request
    assert technical.operation is GenerationOperation.CORRECT
    assert technical.source_step_id == correction.meta.step_id
    assert technical.production_kind == preparation.target.production_kind
    assert technical.objective == "apply_bounded_correction_request"
    assert technical.output_format == preparation.target.output_format
    assert technical.pedagogical_context == preparation.target.pedagogical_context
    assert technical.target_ref is None
    assert technical.target_version_ref is correction.target_production_ref
    assert technical.evidence_refs == correction.evidence_refs
    assert technical.expected_sections == ()
    assert technical.resolved_inputs == {
        "target_content": preparation.target.content,
        "target_structured_payload": preparation.target.structured_payload,
        "caller_resolved_inputs": preparation.resolved_inputs,
    }
    assert technical.constraints == {
        "review_ref": correction.review_ref,
        "finding_ids": correction.finding_ids,
        "preserve_constraints": correction.preserve_constraints,
        "allowed_changes": correction.allowed_changes,
        "forbidden_changes": correction.forbidden_changes,
        "expected_delta": correction.expected_delta,
    }
    assert prepared.preparation_request is preparation
    assert technical.resolved_inputs["caller_resolved_inputs"] == preparation.resolved_inputs
    assert technical.output_contract == preparation.output_contract


@pytest.mark.parametrize("snapshot_field", ("capability", "request", "target"))
def test_execute_correction_rejects_snapshot_field_divergence_before_port(
    snapshot_field: str,
) -> None:
    valid_preparation = _preparation()
    valid_prepared = GenerationCoordinator(RecordingPort(_technical())).prepare_correction(
        request=valid_preparation
    )
    if snapshot_field == "capability":
        snapshot = _forge_preparation(
            valid_preparation,
            CapabilityId("CAP-G01"),
        )
    elif snapshot_field == "request":
        foreign_correction = _correction(target_ref=_version("foreign-v1"))
        snapshot = _preparation(
            correction=foreign_correction,
            target=_target(target_ref=foreign_correction.target_production_ref),
        )
    else:
        snapshot = _preparation(
            correction=valid_preparation.request,
            target=ResolvedCorrectionTarget(
                target_production_ref=valid_preparation.request.target_production_ref,
                production_kind="different_kind",
                output_format="markdown",
                content="Different resolved target.",
            ),
        )
    forged = _forge_prepared(valid_prepared, preparation_request=snapshot)
    port = RecordingPort(_technical())
    with pytest.raises(CorrectionMaterializationError) as raised:
        GenerationCoordinator(port).execute_correction(prepared=forged)
    assert raised.value.code is CorrectionMaterializationCode.PREPARED_LINEAGE_MISMATCH
    assert port.calls == []


@pytest.mark.parametrize(
    "caller_inputs",
    (
        {"caller": "substituted"},
        {"caller": {"scope": "substituted-nested"}},
    ),
)
def test_execute_correction_rejects_forged_caller_inputs_before_port(
    caller_inputs: dict[str, object],
) -> None:
    valid = _prepared()
    resolved_inputs = dict(valid.port_request.resolved_inputs)
    resolved_inputs["caller_resolved_inputs"] = caller_inputs
    forged = _forge_prepared(
        valid,
        port_request=replace(valid.port_request, resolved_inputs=resolved_inputs),
    )
    port = RecordingPort(_technical())
    with pytest.raises(CorrectionMaterializationError) as raised:
        GenerationCoordinator(port).execute_correction(prepared=forged)
    assert raised.value.code is CorrectionMaterializationCode.PREPARED_LINEAGE_MISMATCH
    assert port.calls == []


@pytest.mark.parametrize(
    "output_contract",
    (
        {"type": "substituted"},
        {"type": "lesson_plan", "schema": {"nested": "substituted"}},
    ),
)
def test_execute_correction_rejects_forged_output_contract_before_port(
    output_contract: dict[str, object],
) -> None:
    valid = _prepared()
    forged = _forge_prepared(
        valid,
        port_request=replace(
            valid.port_request,
            output_contract=output_contract,
        ),
    )
    port = RecordingPort(_technical())
    with pytest.raises(CorrectionMaterializationError) as raised:
        GenerationCoordinator(port).execute_correction(prepared=forged)
    assert raised.value.code is CorrectionMaterializationCode.PREPARED_LINEAGE_MISMATCH
    assert port.calls == []


def test_execute_correction_calls_generation_port_once() -> None:
    expected = _technical()
    port = RecordingPort(expected)
    coordinator = GenerationCoordinator(port)
    prepared = coordinator.prepare_correction(request=_preparation())
    assert coordinator.execute_correction(prepared=prepared) is expected
    assert port.calls == [prepared.port_request]


def test_execute_correction_propagates_port_error_without_retry() -> None:
    error = GenerationPortError(GenerationPortErrorCode.UNAVAILABLE, "Unavailable")
    port = RecordingPort(error)
    coordinator = GenerationCoordinator(port)
    prepared = coordinator.prepare_correction(request=_preparation())
    with pytest.raises(GenerationPortError) as raised:
        coordinator.execute_correction(prepared=prepared)
    assert raised.value is error
    assert port.calls == [prepared.port_request]


@pytest.mark.parametrize(
    "technical",
    (
        _technical(source_step_id="wrong-step"),
        _technical(operation=GenerationOperation.GENERATE),
        _technical(evidence_refs_used=("evidence:foreign",)),
        _technical(evidence_refs_used=("evidence:one", "evidence:one")),
    ),
)
def test_execute_correction_rejects_forged_result_lineage(
    technical: GenerationPortResult,
) -> None:
    port = RecordingPort(technical)
    coordinator = GenerationCoordinator(port)
    prepared = coordinator.prepare_correction(request=_preparation())
    with pytest.raises((CorrectionMaterializationError, ValueError)):
        coordinator.execute_correction(prepared=prepared)
    assert port.calls == [prepared.port_request]


@pytest.mark.parametrize(
    "details",
    (
        {**_details(), "foreign": True},
        _details(addressed=("finding-1", "finding-1")),
        _details(unresolved=("finding-2", "finding-2")),
        _details(addressed=("finding-1",), unresolved=("finding-1", "finding-2")),
        _details(addressed=("finding-1",), unresolved=()),
        _details(addressed=("finding-1", "finding-foreign")),
        _details(change_summary=" "),
    ),
)
def test_correction_details_fail_closed(details: dict[str, object]) -> None:
    with pytest.raises(CorrectionMaterializationError) as raised:
        _materialization(technical=_technical(operation_details=details))
    assert raised.value.code is CorrectionMaterializationCode.CORRECTION_DETAILS_MISMATCH


def test_correct_production_accepts_g03_with_one_prepare_and_execute() -> None:
    port = RecordingPort(_technical())
    coordinator = CountingCoordinator(port)
    agent = GeneratorAgent(coordinator)
    request = _preparation()
    prepared, result = agent.correct_production(request=request)
    assert prepared is coordinator.execute_correction_calls[0]
    assert result is port.response
    assert coordinator.prepare_correction_calls == [request]
    assert len(coordinator.execute_correction_calls) == len(port.calls) == 1


@pytest.mark.parametrize("capability", (CapabilityId("CAP-G01"), CapabilityId("CAP-G02"), CapabilityId("CAP-E01")))
def test_correct_production_rejects_every_non_g03_capability(
    capability: CapabilityId,
) -> None:
    port = RecordingPort(_technical())
    coordinator = CountingCoordinator(port)
    agent = GeneratorAgent(coordinator)
    forged = _forge_preparation(_preparation(), capability)
    with pytest.raises(CorrectionMaterializationError) as raised:
        agent.correct_production(request=forged)
    assert raised.value.code is CorrectionMaterializationCode.UNSUPPORTED_CAPABILITY
    assert coordinator.prepare_correction_calls == []
    assert port.calls == []


def test_succeeded_materializes_candidate_and_correction_result_exactly() -> None:
    request = _materialization()
    candidate, result = GeneratorAgent(GenerationCoordinator(RecordingPort(_technical()))).build_correction(
        request=request
    )
    assert candidate.meta is request.result_meta
    assert candidate.production_id == request.production_id
    assert candidate.content == request.technical_result.content
    assert candidate.validation_state is ProductionValidationState.CANDIDATE
    assert result.request is request.correction_request
    assert result.parent_production_ref is request.correction_request.target_production_ref
    assert result.new_production_ref is request.new_production_ref
    assert result.addressed_findings == ("finding-1",)
    assert result.unresolved_findings == ("finding-2",)


def test_partial_materializes_both_outputs_with_warnings_and_partial_meta() -> None:
    correction = _correction()
    technical = _technical(status=GenerationPortResultStatus.PARTIAL)
    request = _materialization(
        correction=correction,
        technical=technical,
        meta=_meta(correction, AgentResultStatus.PARTIAL),
    )
    candidate, result = GeneratorAgent(GenerationCoordinator(RecordingPort(technical))).build_correction(
        request=request
    )
    assert candidate.meta.status is AgentResultStatus.PARTIAL
    assert candidate.warnings == technical.warnings
    assert result.new_warnings == technical.warnings
    assert candidate.validation_state is ProductionValidationState.CANDIDATE


@pytest.mark.parametrize(
    "status",
    (GenerationPortResultStatus.REFUSED, GenerationPortResultStatus.INSUFFICIENT_EVIDENCE),
)
def test_non_output_status_materializes_nothing(status: GenerationPortResultStatus) -> None:
    with pytest.raises(CorrectionMaterializationError) as raised:
        _materialization(technical=_technical(status=status, operation_details={}))
    assert raised.value.code is CorrectionMaterializationCode.NO_CORRECTION_FOR_STATUS


@pytest.mark.parametrize(
    "meta",
    (
        _meta(_correction(), run_id="wrong-run"),
        _meta(_correction(), step_id="wrong-step"),
        _meta(_correction(), correlation_id="wrong-correlation"),
        _meta(_correction(), actor=ActorRef(ActorKind.AGENT, AgentId.AG_02.value)),
    ),
)
def test_correction_result_meta_must_match_c11_and_ag03(
    meta: ContractMeta[AgentResultStatus],
) -> None:
    with pytest.raises(CorrectionMaterializationError) as raised:
        _materialization(meta=meta)
    assert raised.value.code is CorrectionMaterializationCode.RESULT_META_MISMATCH


@pytest.mark.parametrize(
    ("new_ref", "message"),
    ((_version("v1"), "differ"), (_version("v2", entity="other"), "identity")),
)
def test_correction_result_contract_rejects_invalid_new_version(
    new_ref: ObjectVersionRef,
    message: str,
) -> None:
    request = _materialization(new_ref=new_ref)
    with pytest.raises(ValueError, match=message):
        GeneratorAgent(GenerationCoordinator(RecordingPort(_technical()))).build_correction(
            request=request
        )


def test_candidate_correction_lineage_uses_public_exact_target_mapping() -> None:
    candidate, result = GeneratorAgent(GenerationCoordinator(RecordingPort(_technical()))).build_correction(
        request=_materialization(production_id="candidate-caller-id")
    )
    assert candidate.lineage == {
        "source_run_id": "run-correction-1",
        "source_step_id": "step-correction-1",
        "source_correlation_id": "corr-correction-1",
        "capability_id": "CAP-G03",
        "generation_operation": "CORRECT",
        "review_ref": "review:1",
        "finding_ids": ("finding-1", "finding-2"),
        "correction_target": {
            "entity_type": "production",
            "entity_id": "production-1",
            "version": "v1",
        },
    }
    assert result.lineage["production_candidate_id"] == "candidate-caller-id"
    assert result.lineage["parent"] == candidate.lineage["correction_target"]
    assert result.lineage["new_version"] == {
        "entity_type": "production",
        "entity_id": "production-1",
        "version": "v2",
    }


def test_correction_materialization_rejects_authority_metadata_smuggling() -> None:
    valid = _materialization()
    forged = _forge_materialization(
        valid,
        technical_result=_technical(
            execution_metadata={"provider": {"validated": True}}
        ),
    )
    with pytest.raises(CorrectionMaterializationError) as raised:
        GeneratorAgent(GenerationCoordinator(RecordingPort(_technical()))).build_correction(
            request=forged
        )
    assert raised.value.code is CorrectionMaterializationCode.TECHNICAL_RESULT_MISMATCH


def test_correction_uses_only_caller_supplied_identity_version_and_meta() -> None:
    request = _materialization(
        production_id="caller-production-id",
        new_ref=_version("caller-v9"),
    )
    candidate, result = GeneratorAgent(GenerationCoordinator(RecordingPort(_technical()))).build_correction(
        request=request
    )
    assert candidate.production_id == "caller-production-id"
    assert candidate.meta is request.result_meta
    assert result.new_production_ref.version_ref.value == "caller-v9"
