from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime

import pytest

from backend.agent_runtime.agents.generation import (
    GenerationCoordinationError,
    GenerationCoordinationErrorCode,
    GenerationCoordinator,
    GenerationOperation,
    GenerationPortError,
    GenerationPortErrorCode,
    GenerationPortRequest,
    GenerationPortResult,
    GenerationPortResultStatus,
    GenerationPreparationRequest,
    PreparedGenerationCall,
)
from backend.agent_runtime.contracts import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    ActorKind,
    ActorRef,
    AgentId,
    ContractMeta,
    InvocationStatus,
    ProductionRequest,
)
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant

NOW = Instant(datetime(2026, 8, 25, 18, 0, tzinfo=UTC))
G01 = CapabilityId("CAP-G01")
G02 = CapabilityId("CAP-G02")
G03 = CapabilityId("CAP-G03")


def _canonical(
    *,
    target_ref: str | None = None,
    pedagogical_context: dict[str, object] | None = None,
) -> ProductionRequest:
    return ProductionRequest(
        meta=ContractMeta(
            schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
            run_id="run-generation-c",
            step_id="step-generation-c",
            parent_step_id=None,
            correlation_id=CorrelationId("corr-generation-c"),
            created_at=NOW,
            actor=ActorRef(ActorKind.AGENT, AgentId.AG_03.value),
            status=InvocationStatus.PLANNED,
        ),
        production_kind="lesson_plan",
        brief="Prepare a grounded lesson plan",
        output_format="markdown",
        pedagogical_context=(
            {"audience": {"level": "beginner", "needs": ["scaffolding"]}}
            if pedagogical_context is None
            else pedagogical_context
        ),
        constraints={"max_sections": 4, "tone": "clear"},
        evidence_refs=("evidence:one", "evidence:two"),
        target_ref=target_ref,
        expected_sections=("Objectives", "Activities"),
    )


def _result(
    *,
    operation: GenerationOperation = GenerationOperation.GENERATE,
    source_step_id: str = "step-generation-c",
    status: GenerationPortResultStatus = GenerationPortResultStatus.SUCCEEDED,
    evidence_refs_used: tuple[str, ...] = ("evidence:one",),
) -> GenerationPortResult:
    if status in {
        GenerationPortResultStatus.REFUSED,
        GenerationPortResultStatus.INSUFFICIENT_EVIDENCE,
    }:
        return GenerationPortResult(
            source_step_id=source_step_id,
            operation=operation,
            status=status,
            content=None,
            evidence_refs_used=evidence_refs_used,
            warnings=({"code": status.value},),
        )
    return GenerationPortResult(
        source_step_id=source_step_id,
        operation=operation,
        status=status,
        content="Prepared technical output.",
        evidence_refs_used=evidence_refs_used,
        warnings=({"code": "PARTIAL_LIMIT"},) if status is GenerationPortResultStatus.PARTIAL else (),
    )


class RecordingGenerationPort:
    def __init__(self, response: GenerationPortResult | GenerationPortError | object) -> None:
        self.response = response
        self.calls: list[GenerationPortRequest] = []

    def generate(self, *, request: GenerationPortRequest) -> GenerationPortResult:
        self.calls.append(request)
        if isinstance(self.response, GenerationPortError):
            raise self.response
        return self.response  # type: ignore[return-value]


def _prepare(
    capability_id: CapabilityId = G01,
    *,
    canonical: ProductionRequest | None = None,
    resolved_inputs: dict[str, object] | None = None,
    output_contract: dict[str, object] | None = None,
    response: GenerationPortResult | GenerationPortError | object | None = None,
) -> tuple[GenerationCoordinator, RecordingGenerationPort, PreparedGenerationCall]:
    port = RecordingGenerationPort(response or _result())
    coordinator = GenerationCoordinator(port)
    prepared = coordinator.prepare(
        request=GenerationPreparationRequest(
            capability_id=capability_id,
            request=canonical or _canonical(),
            resolved_inputs=resolved_inputs or {"resolved": {"value": "caller"}},
            output_contract=output_contract or {"type": "lesson"},
        )
    )
    return coordinator, port, prepared


def _forge(
    prepared: PreparedGenerationCall,
    *,
    preparation_request: object | None = None,
    capability_id: CapabilityId | None = None,
    canonical_request: ProductionRequest | None = None,
    port_request: GenerationPortRequest | None = None,
) -> PreparedGenerationCall:
    forged = object.__new__(PreparedGenerationCall)
    object.__setattr__(
        forged,
        "preparation_request",
        (
            prepared.preparation_request
            if preparation_request is None
            else preparation_request
        ),
    )
    object.__setattr__(forged, "capability_id", capability_id or prepared.capability_id)
    object.__setattr__(
        forged,
        "canonical_request",
        canonical_request or prepared.canonical_request,
    )
    object.__setattr__(forged, "port_request", port_request or prepared.port_request)
    return forged


def test_coordination_error_codes_are_exactly_the_nine_closed_codes() -> None:
    assert tuple(item.value for item in GenerationCoordinationErrorCode) == (
        "UNSUPPORTED_CAPABILITY",
        "CAPABILITY_OPERATION_MISMATCH",
        "TARGET_FORBIDDEN_FOR_GENERATE",
        "TARGET_REQUIRED_FOR_TRANSFORM",
        "CORRECTION_REQUEST_REQUIRED",
        "SOURCE_STEP_MISMATCH",
        "OPERATION_MISMATCH",
        "EVIDENCE_REF_OUT_OF_SCOPE",
        "DUPLICATE_EVIDENCE_REF_USED",
    )


def test_coordination_error_codes_exclude_future_authority_and_resilience() -> None:
    assert {item.name for item in GenerationCoordinationErrorCode}.isdisjoint(
        {"RETRY", "PROVIDER_ERROR", "VALIDATION_ERROR", "PROMOTION_ERROR", "REVIEW_ERROR"}
    )


def test_prepare_maps_g01_to_generate() -> None:
    _, _, prepared = _prepare()
    assert prepared.capability_id == G01
    assert prepared.port_request.operation is GenerationOperation.GENERATE


def test_prepare_maps_g02_to_transform_with_required_target() -> None:
    target = "production:target:v1"
    _, _, prepared = _prepare(G02, canonical=_canonical(target_ref=target), response=_result(operation=GenerationOperation.TRANSFORM))
    assert prepared.port_request.operation is GenerationOperation.TRANSFORM
    assert prepared.port_request.target_ref == target


@pytest.mark.parametrize(
    ("capability_id", "target_ref"),
    ((G01, None), (G02, "production:target:v1")),
)
def test_prepare_keeps_exact_preparation_request_for_g01_and_g02(
    capability_id: CapabilityId,
    target_ref: str | None,
) -> None:
    preparation = GenerationPreparationRequest(
        capability_id,
        _canonical(target_ref=target_ref),
        resolved_inputs={"caller": {"scope": "exact"}},
        output_contract={"schema": {"type": "lesson"}},
    )
    prepared = GenerationCoordinator(RecordingGenerationPort(_result())).prepare(
        request=preparation
    )
    assert prepared.preparation_request is preparation


def test_prepare_rejects_g03_for_production_request() -> None:
    port = RecordingGenerationPort(_result())
    with pytest.raises(GenerationCoordinationError) as raised:
        GenerationCoordinator(port).prepare(
            request=GenerationPreparationRequest(G03, _canonical())
        )
    assert raised.value.code is GenerationCoordinationErrorCode.CORRECTION_REQUEST_REQUIRED
    assert port.calls == []


def test_prepare_rejects_foreign_capability() -> None:
    with pytest.raises(GenerationCoordinationError) as raised:
        GenerationCoordinator(RecordingGenerationPort(_result())).prepare(
            request=GenerationPreparationRequest(CapabilityId("CAP-E01"), _canonical())
        )
    assert raised.value.code is GenerationCoordinationErrorCode.UNSUPPORTED_CAPABILITY


def test_generate_rejects_target_reference() -> None:
    with pytest.raises(GenerationCoordinationError) as raised:
        _prepare(canonical=_canonical(target_ref="production:target:v1"))
    assert raised.value.code is GenerationCoordinationErrorCode.TARGET_FORBIDDEN_FOR_GENERATE


def test_transform_requires_target_reference() -> None:
    with pytest.raises(GenerationCoordinationError) as raised:
        _prepare(G02)
    assert raised.value.code is GenerationCoordinationErrorCode.TARGET_REQUIRED_FOR_TRANSFORM


def test_prepare_copies_canonical_fields_exactly() -> None:
    canonical = _canonical()
    _, _, prepared = _prepare(canonical=canonical)
    technical = prepared.port_request
    assert technical.source_step_id == canonical.meta.step_id
    assert technical.production_kind == canonical.production_kind
    assert technical.objective == canonical.brief
    assert technical.output_format == canonical.output_format
    assert technical.pedagogical_context == canonical.pedagogical_context
    assert technical.constraints == canonical.constraints
    assert technical.evidence_refs == canonical.evidence_refs
    assert technical.target_ref == canonical.target_ref
    assert technical.expected_sections == canonical.expected_sections


def test_prepare_injects_only_caller_supplied_resolved_inputs_and_output_contract() -> None:
    resolved = {"authorized": {"value": ["one"]}}
    contract = {"required": ["title", "body"]}
    _, _, prepared = _prepare(resolved_inputs=resolved, output_contract=contract)
    assert prepared.port_request.resolved_inputs == {"authorized": {"value": ("one",)}}
    assert prepared.port_request.output_contract == {"required": ("title", "body")}
    assert "audience" not in prepared.port_request.resolved_inputs
    assert prepared.port_request.pedagogical_context == {
        "audience": {"level": "beginner", "needs": ("scaffolding",)}
    }


def test_execute_accepts_exact_caller_inputs_and_output_contract() -> None:
    preparation = GenerationPreparationRequest(
        G01,
        _canonical(),
        resolved_inputs={"caller": {"items": ["one", "two"]}},
        output_contract={"schema": {"required": ["title", "body"]}},
    )
    port = RecordingGenerationPort(_result())
    coordinator = GenerationCoordinator(port)
    prepared = coordinator.prepare(request=preparation)
    assert prepared.port_request.resolved_inputs == preparation.resolved_inputs
    assert prepared.port_request.output_contract == preparation.output_contract
    coordinator.execute(prepared=prepared)
    assert port.calls == [prepared.port_request]


@pytest.mark.parametrize(
    ("capability_id", "target_ref", "operation", "forged_inputs"),
    (
        (G01, None, GenerationOperation.GENERATE, {"caller": "substituted"}),
        (
            G01,
            None,
            GenerationOperation.GENERATE,
            {"caller": {"scope": "substituted-nested"}},
        ),
        (
            G02,
            "production:target:v1",
            GenerationOperation.TRANSFORM,
            {"caller": "substituted-transform"},
        ),
    ),
)
def test_execute_rejects_forged_caller_inputs_before_port(
    capability_id: CapabilityId,
    target_ref: str | None,
    operation: GenerationOperation,
    forged_inputs: dict[str, object],
) -> None:
    preparation = GenerationPreparationRequest(
        capability_id,
        _canonical(target_ref=target_ref),
        resolved_inputs={"caller": {"scope": "original"}},
    )
    port = RecordingGenerationPort(_result(operation=operation))
    coordinator = GenerationCoordinator(port)
    prepared = coordinator.prepare(request=preparation)
    forged = _forge(
        prepared,
        port_request=replace(
            prepared.port_request,
            resolved_inputs=forged_inputs,
        ),
    )
    with pytest.raises(GenerationCoordinationError) as raised:
        coordinator.execute(prepared=forged)
    assert raised.value.code is GenerationCoordinationErrorCode.CAPABILITY_OPERATION_MISMATCH
    assert port.calls == []


@pytest.mark.parametrize(
    ("capability_id", "target_ref", "operation", "forged_contract"),
    (
        (G01, None, GenerationOperation.GENERATE, {"type": "substituted"}),
        (
            G01,
            None,
            GenerationOperation.GENERATE,
            {"schema": {"type": "substituted-nested"}},
        ),
        (
            G02,
            "production:target:v1",
            GenerationOperation.TRANSFORM,
            {"type": "substituted-transform"},
        ),
    ),
)
def test_execute_rejects_forged_output_contract_before_port(
    capability_id: CapabilityId,
    target_ref: str | None,
    operation: GenerationOperation,
    forged_contract: dict[str, object],
) -> None:
    preparation = GenerationPreparationRequest(
        capability_id,
        _canonical(target_ref=target_ref),
        output_contract={"schema": {"type": "original"}},
    )
    port = RecordingGenerationPort(_result(operation=operation))
    coordinator = GenerationCoordinator(port)
    prepared = coordinator.prepare(request=preparation)
    forged = _forge(
        prepared,
        port_request=replace(
            prepared.port_request,
            output_contract=forged_contract,
        ),
    )
    with pytest.raises(GenerationCoordinationError) as raised:
        coordinator.execute(prepared=forged)
    assert raised.value.code is GenerationCoordinationErrorCode.CAPABILITY_OPERATION_MISMATCH
    assert port.calls == []


def test_prepare_keeps_nested_pedagogical_context_deeply_immutable() -> None:
    context = {"audience": {"levels": ["beginner", "mixed"]}}
    _, _, prepared = _prepare(canonical=_canonical(pedagogical_context=context))
    assert prepared.port_request.pedagogical_context == {
        "audience": {"levels": ("beginner", "mixed")}
    }
    with pytest.raises(TypeError):
        prepared.port_request.pedagogical_context["audience"] = {}  # type: ignore[index]


def test_prepare_does_not_allow_resolved_inputs_to_replace_canonical_context() -> None:
    canonical = _canonical(pedagogical_context={"audience": "canonical"})
    _, _, prepared = _prepare(
        canonical=canonical,
        resolved_inputs={"pedagogical_context": {"audience": "contradictory"}},
    )
    assert prepared.port_request.pedagogical_context == {"audience": "canonical"}
    assert prepared.port_request.resolved_inputs == {
        "pedagogical_context": {"audience": "contradictory"}
    }


def test_prepare_preserves_empty_canonical_pedagogical_context() -> None:
    _, _, prepared = _prepare(
        canonical=_canonical(pedagogical_context={}),
    )
    assert prepared.port_request.pedagogical_context == {}


@pytest.mark.parametrize(
    ("capability_id", "target_ref", "operation"),
    (
        (G01, None, GenerationOperation.GENERATE),
        (G02, "production:target:v1", GenerationOperation.TRANSFORM),
    ),
)
def test_prepare_preserves_context_for_generate_and_transform(
    capability_id: CapabilityId,
    target_ref: str | None,
    operation: GenerationOperation,
) -> None:
    context = {"grade": "CM1", "language": "fr"}
    _, _, prepared = _prepare(
        capability_id,
        canonical=_canonical(
            target_ref=target_ref,
            pedagogical_context=context,
        ),
        response=_result(operation=operation),
    )
    assert prepared.port_request.pedagogical_context == context


def test_preparation_request_mappings_are_deeply_immutable() -> None:
    request = GenerationPreparationRequest(
        G01,
        _canonical(),
        resolved_inputs={"nested": {"items": ["one"]}},
        output_contract={"schema": {"fields": ["title"]}},
    )
    assert request.resolved_inputs["nested"] == {"items": ("one",)}
    assert request.output_contract["schema"] == {"fields": ("title",)}
    with pytest.raises(TypeError):
        request.resolved_inputs["nested"] = {}  # type: ignore[index]


def test_preparation_and_prepared_models_are_frozen_and_slotted() -> None:
    preparation = GenerationPreparationRequest(G01, _canonical())
    _, _, prepared = _prepare()
    with pytest.raises(FrozenInstanceError):
        preparation.capability_id = G02  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        prepared.capability_id = G02  # type: ignore[misc]
    assert not hasattr(preparation, "__dict__")
    assert not hasattr(prepared, "__dict__")


@pytest.mark.parametrize(
    ("field_name", "forged_value"),
    [
        ("production_kind", "other_kind"),
        ("objective", "Forged objective"),
        ("output_format", "html"),
        ("constraints", {"forged": True}),
        ("evidence_refs", ("evidence:foreign",)),
        ("expected_sections", ("Forged",)),
    ],
)
def test_prepared_constructor_rejects_forged_canonical_copies(
    field_name: str,
    forged_value: object,
) -> None:
    _, _, prepared = _prepare()
    forged_port_request = replace(prepared.port_request, **{field_name: forged_value})
    with pytest.raises(GenerationCoordinationError) as raised:
        PreparedGenerationCall(
            prepared.preparation_request,
            prepared.capability_id,
            prepared.canonical_request,
            forged_port_request,
        )
    assert raised.value.code is GenerationCoordinationErrorCode.CAPABILITY_OPERATION_MISMATCH


def test_prepared_constructor_rejects_source_step_mismatch() -> None:
    _, _, prepared = _prepare()
    with pytest.raises(GenerationCoordinationError) as raised:
        PreparedGenerationCall(
            prepared.preparation_request,
            G01,
            prepared.canonical_request,
            replace(prepared.port_request, source_step_id="forged-step"),
        )
    assert raised.value.code is GenerationCoordinationErrorCode.SOURCE_STEP_MISMATCH


def test_prepared_constructor_rejects_divergent_pedagogical_context() -> None:
    _, _, prepared = _prepare()
    with pytest.raises(GenerationCoordinationError) as raised:
        PreparedGenerationCall(
            prepared.preparation_request,
            G01,
            prepared.canonical_request,
            replace(
                prepared.port_request,
                pedagogical_context={"audience": "forged"},
            ),
        )
    assert raised.value.code is GenerationCoordinationErrorCode.CAPABILITY_OPERATION_MISMATCH
    assert "pedagogical_context" in raised.value.safe_reason


def test_prepared_constructor_rejects_nested_context_divergence() -> None:
    _, _, prepared = _prepare()
    with pytest.raises(GenerationCoordinationError) as raised:
        PreparedGenerationCall(
            prepared.preparation_request,
            G01,
            prepared.canonical_request,
            replace(
                prepared.port_request,
                pedagogical_context={
                    "audience": {"level": "advanced", "needs": ["scaffolding"]}
                },
            ),
        )
    assert raised.value.code is GenerationCoordinationErrorCode.CAPABILITY_OPERATION_MISMATCH


def test_prepared_constructor_rejects_capability_operation_mismatch() -> None:
    _, _, prepared = _prepare()
    canonical = _canonical(target_ref="production:target:v1")
    preparation = GenerationPreparationRequest(
        G02,
        canonical,
        prepared.preparation_request.resolved_inputs,
        prepared.preparation_request.output_contract,
    )
    with pytest.raises(GenerationCoordinationError) as raised:
        PreparedGenerationCall(
            preparation,
            G02,
            canonical,
            replace(
                prepared.port_request,
                target_ref="production:target:v1",
            ),
        )
    assert raised.value.code is GenerationCoordinationErrorCode.CAPABILITY_OPERATION_MISMATCH


def test_execute_calls_port_exactly_once_and_returns_same_result() -> None:
    expected = _result()
    coordinator, port, prepared = _prepare(response=expected)
    actual = coordinator.execute(prepared=prepared)
    assert actual is expected
    assert port.calls == [prepared.port_request]


def test_execute_g02_calls_port_exactly_once() -> None:
    expected = _result(operation=GenerationOperation.TRANSFORM)
    coordinator, port, prepared = _prepare(
        G02,
        canonical=_canonical(target_ref="production:target:v1"),
        response=expected,
    )
    assert coordinator.execute(prepared=prepared) is expected
    assert port.calls == [prepared.port_request]


def test_execute_propagates_generation_port_error_without_retry() -> None:
    technical_error = GenerationPortError(
        GenerationPortErrorCode.UNAVAILABLE,
        "Generation mechanism unavailable",
    )
    coordinator, port, prepared = _prepare(response=technical_error)
    with pytest.raises(GenerationPortError) as raised:
        coordinator.execute(prepared=prepared)
    assert raised.value is technical_error
    assert port.calls == [prepared.port_request]


def test_execute_rejects_invalid_port_response_as_boundary_error() -> None:
    coordinator, port, prepared = _prepare(response=object())
    with pytest.raises(GenerationPortError) as raised:
        coordinator.execute(prepared=prepared)
    assert raised.value.code is GenerationPortErrorCode.INVALID_RESPONSE
    assert len(port.calls) == 1


def test_execute_rejects_result_source_step_mismatch() -> None:
    coordinator, port, prepared = _prepare(response=_result(source_step_id="other-step"))
    with pytest.raises(GenerationCoordinationError) as raised:
        coordinator.execute(prepared=prepared)
    assert raised.value.code is GenerationCoordinationErrorCode.SOURCE_STEP_MISMATCH
    assert len(port.calls) == 1


def test_execute_rejects_result_operation_mismatch() -> None:
    coordinator, port, prepared = _prepare(response=_result(operation=GenerationOperation.TRANSFORM))
    with pytest.raises(GenerationCoordinationError) as raised:
        coordinator.execute(prepared=prepared)
    assert raised.value.code is GenerationCoordinationErrorCode.OPERATION_MISMATCH
    assert len(port.calls) == 1


def test_execute_accepts_evidence_subset_and_zero_refs() -> None:
    for refs in (("evidence:two",), ()):
        coordinator, port, prepared = _prepare(response=_result(evidence_refs_used=refs))
        assert coordinator.execute(prepared=prepared).evidence_refs_used == refs
        assert len(port.calls) == 1


def test_execute_rejects_foreign_evidence_reference() -> None:
    coordinator, port, prepared = _prepare(response=_result(evidence_refs_used=("evidence:foreign",)))
    with pytest.raises(GenerationCoordinationError) as raised:
        coordinator.execute(prepared=prepared)
    assert raised.value.code is GenerationCoordinationErrorCode.EVIDENCE_REF_OUT_OF_SCOPE
    assert len(port.calls) == 1


def test_execute_rejects_duplicate_evidence_references() -> None:
    coordinator, port, prepared = _prepare(response=_result(evidence_refs_used=("evidence:one", "evidence:one")))
    with pytest.raises(GenerationCoordinationError) as raised:
        coordinator.execute(prepared=prepared)
    assert raised.value.code is GenerationCoordinationErrorCode.DUPLICATE_EVIDENCE_REF_USED
    assert len(port.calls) == 1


@pytest.mark.parametrize(
    "status",
    (
        GenerationPortResultStatus.REFUSED,
        GenerationPortResultStatus.INSUFFICIENT_EVIDENCE,
        GenerationPortResultStatus.PARTIAL,
    ),
)
def test_execute_returns_nominal_non_success_status_unchanged(
    status: GenerationPortResultStatus,
) -> None:
    expected = _result(status=status)
    coordinator, _, prepared = _prepare(response=expected)
    assert coordinator.execute(prepared=prepared) is expected


def test_execute_revalidates_forged_prepared_before_outbound_call() -> None:
    coordinator, port, prepared = _prepare()
    forged = _forge(
        prepared,
        port_request=replace(prepared.port_request, objective="Forged objective"),
    )
    with pytest.raises(GenerationCoordinationError) as raised:
        coordinator.execute(prepared=forged)
    assert raised.value.code is GenerationCoordinationErrorCode.CAPABILITY_OPERATION_MISMATCH
    assert port.calls == []


def test_execute_rejects_divergent_snapshot_capability_before_port() -> None:
    coordinator, port, prepared = _prepare()
    forged_snapshot = replace(prepared.preparation_request, capability_id=G02)
    forged = _forge(prepared, preparation_request=forged_snapshot)
    with pytest.raises(GenerationCoordinationError) as raised:
        coordinator.execute(prepared=forged)
    assert raised.value.code is GenerationCoordinationErrorCode.CAPABILITY_OPERATION_MISMATCH
    assert port.calls == []


def test_execute_rejects_divergent_snapshot_request_before_port() -> None:
    coordinator, port, prepared = _prepare()
    forged_snapshot = replace(
        prepared.preparation_request,
        request=_canonical(pedagogical_context={"audience": "foreign"}),
    )
    forged = _forge(prepared, preparation_request=forged_snapshot)
    with pytest.raises(GenerationCoordinationError) as raised:
        coordinator.execute(prepared=forged)
    assert raised.value.code is GenerationCoordinationErrorCode.CAPABILITY_OPERATION_MISMATCH
    assert port.calls == []


def test_execute_rejects_non_preparation_snapshot_type_before_port() -> None:
    coordinator, port, prepared = _prepare()
    forged = _forge(prepared, preparation_request=object())
    with pytest.raises(TypeError, match="GenerationPreparationRequest"):
        coordinator.execute(prepared=forged)
    assert port.calls == []


def test_execute_rejects_forged_context_before_outbound_call() -> None:
    coordinator, port, prepared = _prepare()
    forged = _forge(
        prepared,
        port_request=replace(
            prepared.port_request,
            pedagogical_context={"audience": {"level": "forged"}},
        ),
    )
    with pytest.raises(GenerationCoordinationError) as raised:
        coordinator.execute(prepared=forged)
    assert raised.value.code is GenerationCoordinationErrorCode.CAPABILITY_OPERATION_MISMATCH
    assert "pedagogical_context" in raised.value.safe_reason
    assert port.calls == []


def test_execute_revalidates_forged_unsupported_capability_before_port() -> None:
    coordinator, port, prepared = _prepare()
    forged = _forge(prepared, capability_id=CapabilityId("CAP-E01"))
    with pytest.raises(GenerationCoordinationError) as raised:
        coordinator.execute(prepared=forged)
    assert raised.value.code is GenerationCoordinationErrorCode.UNSUPPORTED_CAPABILITY
    assert port.calls == []


def test_coordinator_rejects_non_port() -> None:
    with pytest.raises(TypeError, match="GenerationPort"):
        GenerationCoordinator(object())  # type: ignore[arg-type]


def test_prepare_and_execute_reject_wrong_request_types() -> None:
    coordinator = GenerationCoordinator(RecordingGenerationPort(_result()))
    with pytest.raises(TypeError, match="GenerationPreparationRequest"):
        coordinator.prepare(request=object())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="PreparedGenerationCall"):
        coordinator.execute(prepared=object())  # type: ignore[arg-type]


def test_coordination_error_requires_safe_reason_and_valid_code() -> None:
    with pytest.raises(ValueError, match="safe_reason"):
        GenerationCoordinationError(
            GenerationCoordinationErrorCode.UNSUPPORTED_CAPABILITY,
            " ",
        )
    with pytest.raises(TypeError, match="code"):
        GenerationCoordinationError("UNSUPPORTED_CAPABILITY", "Safe")  # type: ignore[arg-type]
