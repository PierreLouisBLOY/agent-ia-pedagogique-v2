from __future__ import annotations

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

NOW = Instant(datetime(2026, 8, 25, 19, 0, tzinfo=UTC))


class RecordingGenerationPort:
    """Test-only port with no provider, I/O, retry or hidden mapping."""

    def __init__(
        self,
        response: GenerationPortResult | GenerationPortError,
    ) -> None:
        self.response = response
        self.calls: list[GenerationPortRequest] = []

    def generate(self, *, request: GenerationPortRequest) -> GenerationPortResult:
        self.calls.append(request)
        if isinstance(self.response, GenerationPortError):
            raise self.response
        return self.response


def _request(*, target_ref: str | None = None) -> ProductionRequest:
    return ProductionRequest(
        meta=ContractMeta(
            schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
            run_id="run-integration-generation",
            step_id="step-integration-generation",
            parent_step_id=None,
            correlation_id=CorrelationId("corr-integration-generation"),
            created_at=NOW,
            actor=ActorRef(ActorKind.AGENT, AgentId.AG_03.value),
            status=InvocationStatus.PLANNED,
        ),
        production_kind="learning_activity",
        brief="Generate an evidence-grounded learning activity",
        output_format="structured-markdown",
        pedagogical_context={
            "audience": {"level": "beginner", "supports": ["examples"]}
        },
        constraints={"duration_minutes": 30},
        evidence_refs=("evidence:alpha", "evidence:beta"),
        target_ref=target_ref,
        expected_sections=("Instructions", "Assessment"),
    )


def _result(
    operation: GenerationOperation,
    *,
    status: GenerationPortResultStatus = GenerationPortResultStatus.SUCCEEDED,
    evidence_refs_used: tuple[str, ...] = ("evidence:alpha",),
) -> GenerationPortResult:
    if status in {
        GenerationPortResultStatus.REFUSED,
        GenerationPortResultStatus.INSUFFICIENT_EVIDENCE,
    }:
        return GenerationPortResult(
            source_step_id="step-integration-generation",
            operation=operation,
            status=status,
            content=None,
            evidence_refs_used=evidence_refs_used,
            warnings=({"code": status.value},),
        )
    return GenerationPortResult(
        source_step_id="step-integration-generation",
        operation=operation,
        status=status,
        content="Technical activity output.",
        evidence_refs_used=evidence_refs_used,
    )


def _execute(
    capability: str,
    canonical: ProductionRequest,
    response: GenerationPortResult | GenerationPortError,
) -> tuple[GenerationPortResult, RecordingGenerationPort, GenerationPortRequest]:
    port = RecordingGenerationPort(response)
    coordinator = GenerationCoordinator(port)
    prepared = coordinator.prepare(
        request=GenerationPreparationRequest(
            capability_id=CapabilityId(capability),
            request=canonical,
            resolved_inputs={"authorized_input": "already resolved"},
            output_contract={"type": "learning_activity"},
        )
    )
    result = coordinator.execute(prepared=prepared)
    return result, port, prepared.port_request


def test_generate_crosses_boundary_once_with_exact_prepared_lineage() -> None:
    expected = _result(GenerationOperation.GENERATE)
    result, port, technical = _execute("CAP-G01", _request(), expected)
    assert result is expected
    assert port.calls == [technical]
    assert technical.operation is GenerationOperation.GENERATE
    assert technical.source_step_id == "step-integration-generation"
    assert technical.target_ref is None
    assert technical.pedagogical_context == {
        "audience": {"level": "beginner", "supports": ("examples",)}
    }
    assert technical.resolved_inputs == {"authorized_input": "already resolved"}


def test_transform_crosses_boundary_once_with_same_target_reference() -> None:
    target = "production:activity:v1"
    expected = _result(GenerationOperation.TRANSFORM)
    result, port, technical = _execute(
        "CAP-G02",
        _request(target_ref=target),
        expected,
    )
    assert result is expected
    assert port.calls == [technical]
    assert technical.operation is GenerationOperation.TRANSFORM
    assert technical.target_ref == target
    assert technical.pedagogical_context == {
        "audience": {"level": "beginner", "supports": ("examples",)}
    }


def test_evidence_subset_is_preserved_without_fetch_or_authority_evaluation() -> None:
    expected = _result(
        GenerationOperation.GENERATE,
        evidence_refs_used=("evidence:beta",),
    )
    result, port, technical = _execute("CAP-G01", _request(), expected)
    assert result.evidence_refs_used == ("evidence:beta",)
    assert technical.evidence_refs == ("evidence:alpha", "evidence:beta")
    assert len(port.calls) == 1


def test_foreign_evidence_is_rejected_after_single_boundary_call() -> None:
    port = RecordingGenerationPort(
        _result(
            GenerationOperation.GENERATE,
            evidence_refs_used=("evidence:foreign",),
        )
    )
    coordinator = GenerationCoordinator(port)
    prepared = coordinator.prepare(
        request=GenerationPreparationRequest(CapabilityId("CAP-G01"), _request())
    )
    with pytest.raises(GenerationCoordinationError) as raised:
        coordinator.execute(prepared=prepared)
    assert raised.value.code is GenerationCoordinationErrorCode.EVIDENCE_REF_OUT_OF_SCOPE
    assert port.calls == [prepared.port_request]


def test_operation_mismatch_is_rejected_after_single_boundary_call() -> None:
    port = RecordingGenerationPort(_result(GenerationOperation.TRANSFORM))
    coordinator = GenerationCoordinator(port)
    prepared = coordinator.prepare(
        request=GenerationPreparationRequest(CapabilityId("CAP-G01"), _request())
    )
    with pytest.raises(GenerationCoordinationError) as raised:
        coordinator.execute(prepared=prepared)
    assert raised.value.code is GenerationCoordinationErrorCode.OPERATION_MISMATCH
    assert port.calls == [prepared.port_request]


def test_technical_error_propagates_without_retry_or_translation() -> None:
    error = GenerationPortError(
        GenerationPortErrorCode.UNAVAILABLE,
        "Test-only generation mechanism unavailable",
    )
    port = RecordingGenerationPort(error)
    coordinator = GenerationCoordinator(port)
    prepared = coordinator.prepare(
        request=GenerationPreparationRequest(CapabilityId("CAP-G01"), _request())
    )
    with pytest.raises(GenerationPortError) as raised:
        coordinator.execute(prepared=prepared)
    assert raised.value is error
    assert port.calls == [prepared.port_request]


@pytest.mark.parametrize(
    "status",
    (
        GenerationPortResultStatus.REFUSED,
        GenerationPortResultStatus.INSUFFICIENT_EVIDENCE,
    ),
)
def test_nominal_limit_status_is_not_transformed_into_success(
    status: GenerationPortResultStatus,
) -> None:
    expected = _result(GenerationOperation.GENERATE, status=status)
    result, port, technical = _execute("CAP-G01", _request(), expected)
    assert result is expected
    assert result.status is status
    assert result.status is not GenerationPortResultStatus.SUCCEEDED
    assert port.calls == [technical]
