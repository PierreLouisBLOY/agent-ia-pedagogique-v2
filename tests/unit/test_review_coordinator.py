from __future__ import annotations

from dataclasses import FrozenInstanceError, fields, replace
from datetime import UTC, datetime

import pytest

from backend.agent_runtime.agents.review import (
    PreparedReviewCall,
    ResolvedReviewTarget,
    ReviewCoordinationError,
    ReviewCoordinationErrorCode,
    ReviewCoordinator,
    ReviewOperation,
    ReviewPortError,
    ReviewPortErrorCode,
    ReviewPortRequest,
    ReviewPortResult,
    ReviewPortResultStatus,
    ReviewPreparationRequest,
)
from backend.agent_runtime.contracts import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    ActorKind,
    ActorRef,
    AgentId,
    BudgetSpec,
    ContractMeta,
    InvocationStatus,
    ReviewDimension,
    ReviewRequest,
)
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.identifiers import TypedEntityId
from backend.shared_kernel.references import ObjectVersionRef, TypedEntityRef, VersionRef
from backend.shared_kernel.time import Instant

NOW = Instant(datetime(2026, 8, 26, 10, 0, tzinfo=UTC))
V01 = CapabilityId("CAP-V01")
V02 = CapabilityId("CAP-V02")


def _target_ref(name: str = "lesson-1") -> ObjectVersionRef:
    return ObjectVersionRef(
        TypedEntityRef(TypedEntityId("production", name)),
        VersionRef("v3"),
    )


def _canonical(
    *,
    target_ref: ObjectVersionRef | None = None,
    step_id: str = "step-review-c",
    evidence_refs: tuple[str, ...] = ("evidence:one", "evidence:two"),
    criteria: dict[str, object] | None = None,
) -> ReviewRequest:
    return ReviewRequest(
        meta=ContractMeta(
            schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
            run_id="run-review-c",
            step_id=step_id,
            parent_step_id=None,
            correlation_id=CorrelationId("corr-review-c"),
            created_at=NOW,
            actor=ActorRef(ActorKind.AGENT, AgentId.AG_04.value),
            status=InvocationStatus.PLANNED,
        ),
        target_production_ref=target_ref or _target_ref(),
        review_dimensions=(ReviewDimension.ACCURACY, ReviewDimension.SOURCES),
        criteria=criteria or {"required": ["traceable", "accurate"]},
        evidence_refs=evidence_refs,
        severity_policy={"blocking": ["fabrication"]},
        context_slice={"sections": ["intro", "sources"]},
        independence_requirements={"exclude_author": True},
        review_budget=BudgetSpec(max_tokens=1200),
    )


def _result(
    *,
    operation: ReviewOperation = ReviewOperation.SEMANTIC_REVIEW,
    source_step_id: str = "step-review-c",
    evidence_refs_used: tuple[str, ...] = ("evidence:one",),
) -> ReviewPortResult:
    return ReviewPortResult(
        source_step_id=source_step_id,
        operation=operation,
        status=ReviewPortResultStatus.SUCCEEDED,
        structured_payload={"assessment": "technical-only"},
        technical_findings=({"finding_key": "f-1"},),
        evidence_refs_used=evidence_refs_used,
    )


class RecordingRawReviewPort:
    def __init__(self, response: ReviewPortResult | ReviewPortError | object) -> None:
        self.response = response
        self.calls: list[ReviewPortRequest] = []

    def review(self, *, request: ReviewPortRequest) -> ReviewPortResult:
        self.calls.append(request)
        if isinstance(self.response, ReviewPortError):
            raise self.response
        return self.response  # type: ignore[return-value]


def _prepare(
    capability_id: CapabilityId = V01,
    *,
    canonical: ReviewRequest | None = None,
    target: ResolvedReviewTarget | None = None,
    resolved_inputs: dict[str, object] | None = None,
    output_contract: dict[str, object] | None = None,
    response: ReviewPortResult | ReviewPortError | object | None = None,
) -> tuple[ReviewCoordinator, RecordingRawReviewPort, PreparedReviewCall]:
    canonical = canonical or _canonical()
    target = target or ResolvedReviewTarget(
        canonical.target_production_ref,
        content="Caller-resolved lesson content.",
        structured_payload={"sections": ["intro", "sources"]},
    )
    operation = (
        ReviewOperation.ASSESS_FINDINGS if capability_id == V02 else ReviewOperation.SEMANTIC_REVIEW
    )
    port = RecordingRawReviewPort(response or _result(operation=operation))
    coordinator = ReviewCoordinator(port)
    prepared = coordinator.prepare(
        request=ReviewPreparationRequest(
            capability_id=capability_id,
            request=canonical,
            target=target,
            resolved_inputs=resolved_inputs or {"findings": [{"id": "f-1"}]},
            output_contract=output_contract or {"type": "technical_review"},
        )
    )
    return coordinator, port, prepared


def _forge(
    prepared: PreparedReviewCall,
    *,
    preparation_request: object | None = None,
    capability_id: CapabilityId | None = None,
    canonical_request: ReviewRequest | None = None,
    target: ResolvedReviewTarget | None = None,
    port_request: ReviewPortRequest | None = None,
) -> PreparedReviewCall:
    forged = object.__new__(PreparedReviewCall)
    object.__setattr__(
        forged,
        "preparation_request",
        prepared.preparation_request if preparation_request is None else preparation_request,
    )
    object.__setattr__(forged, "capability_id", capability_id or prepared.capability_id)
    object.__setattr__(
        forged,
        "canonical_request",
        canonical_request or prepared.canonical_request,
    )
    object.__setattr__(forged, "target", target or prepared.target)
    object.__setattr__(forged, "port_request", port_request or prepared.port_request)
    return forged


def _forge_result(
    result: ReviewPortResult,
    **changes: object,
) -> ReviewPortResult:
    forged = object.__new__(ReviewPortResult)
    for item in fields(ReviewPortResult):
        object.__setattr__(forged, item.name, changes.get(item.name, getattr(result, item.name)))
    return forged


def test_coordination_error_vocabulary_is_exact_and_closed() -> None:
    assert tuple(item.value for item in ReviewCoordinationErrorCode) == (
        "UNSUPPORTED_CAPABILITY",
        "CAPABILITY_OPERATION_MISMATCH",
        "TARGET_REF_MISMATCH",
        "SOURCE_STEP_MISMATCH",
        "OPERATION_MISMATCH",
        "EVIDENCE_REF_OUT_OF_SCOPE",
        "DUPLICATE_EVIDENCE_REF_USED",
        "PREPARATION_MISMATCH",
    )


@pytest.mark.parametrize(
    ("capability_id", "operation"),
    ((V01, ReviewOperation.SEMANTIC_REVIEW), (V02, ReviewOperation.ASSESS_FINDINGS)),
)
def test_prepare_maps_capability_and_preserves_exact_snapshot(
    capability_id: CapabilityId,
    operation: ReviewOperation,
) -> None:
    canonical = _canonical()
    preparation = ReviewPreparationRequest(
        capability_id,
        canonical,
        ResolvedReviewTarget(canonical.target_production_ref, content="Resolved."),
        resolved_inputs={"findings": [{"id": "f-1"}]},
        output_contract={"schema": {"type": "technical"}},
    )
    coordinator = ReviewCoordinator(RecordingRawReviewPort(_result(operation=operation)))
    prepared = coordinator.prepare(request=preparation)
    technical = prepared.port_request
    assert prepared.preparation_request is preparation
    assert prepared.canonical_request is canonical
    assert prepared.target is preparation.target
    assert technical.operation is operation
    assert technical.source_step_id == canonical.meta.step_id
    assert technical.capability_id == capability_id
    assert technical.target_production_ref == canonical.target_production_ref
    assert technical.target_content == "Resolved."
    assert technical.review_dimensions == canonical.review_dimensions
    assert technical.criteria == canonical.criteria
    assert technical.evidence_refs == canonical.evidence_refs
    assert technical.coverage_context == {
        "severity_policy": canonical.severity_policy,
        "context_slice": canonical.context_slice,
        "independence_requirements": canonical.independence_requirements,
    }
    assert technical.resolved_inputs == preparation.resolved_inputs
    assert technical.output_contract == preparation.output_contract
    assert technical.review_budget == canonical.review_budget


def test_prepare_rejects_unsupported_capability_without_port_call() -> None:
    canonical = _canonical()
    port = RecordingRawReviewPort(_result())
    with pytest.raises(ReviewCoordinationError) as raised:
        ReviewCoordinator(port).prepare(
            request=ReviewPreparationRequest(
                CapabilityId("CAP-E01"),
                canonical,
                ResolvedReviewTarget(canonical.target_production_ref, content="Resolved."),
            )
        )
    assert raised.value.code is ReviewCoordinationErrorCode.UNSUPPORTED_CAPABILITY
    assert port.calls == []


def test_prepare_rejects_target_and_duplicate_canonical_evidence() -> None:
    canonical = _canonical()
    port = RecordingRawReviewPort(_result())
    coordinator = ReviewCoordinator(port)
    with pytest.raises(ReviewCoordinationError) as target_error:
        coordinator.prepare(
            request=ReviewPreparationRequest(
                V01,
                canonical,
                ResolvedReviewTarget(_target_ref("other"), content="Resolved."),
            )
        )
    assert target_error.value.code is ReviewCoordinationErrorCode.TARGET_REF_MISMATCH
    duplicated = _canonical(evidence_refs=("evidence:one", "evidence:one"))
    with pytest.raises(ReviewCoordinationError) as evidence_error:
        coordinator.prepare(
            request=ReviewPreparationRequest(
                V01,
                duplicated,
                ResolvedReviewTarget(duplicated.target_production_ref, content="Resolved."),
            )
        )
    assert evidence_error.value.code is ReviewCoordinationErrorCode.PREPARATION_MISMATCH
    assert port.calls == []


@pytest.mark.parametrize(
    ("field_name", "forged_value", "expected_code"),
    (
        ("source_step_id", "forged-step", ReviewCoordinationErrorCode.SOURCE_STEP_MISMATCH),
        (
            "operation",
            ReviewOperation.ASSESS_FINDINGS,
            ReviewCoordinationErrorCode.CAPABILITY_OPERATION_MISMATCH,
        ),
        (
            "target_production_ref",
            _target_ref("other"),
            ReviewCoordinationErrorCode.TARGET_REF_MISMATCH,
        ),
        ("target_content", "Forged content.", ReviewCoordinationErrorCode.PREPARATION_MISMATCH),
        ("target_payload", {"forged": True}, ReviewCoordinationErrorCode.PREPARATION_MISMATCH),
        (
            "review_dimensions",
            (ReviewDimension.RISK,),
            ReviewCoordinationErrorCode.PREPARATION_MISMATCH,
        ),
        ("criteria", {"forged": True}, ReviewCoordinationErrorCode.PREPARATION_MISMATCH),
        ("evidence_refs", ("evidence:two",), ReviewCoordinationErrorCode.PREPARATION_MISMATCH),
        ("resolved_inputs", {"forged": True}, ReviewCoordinationErrorCode.PREPARATION_MISMATCH),
        ("output_contract", {"type": "forged"}, ReviewCoordinationErrorCode.PREPARATION_MISMATCH),
        (
            "review_budget",
            BudgetSpec(max_tokens=1),
            ReviewCoordinationErrorCode.PREPARATION_MISMATCH,
        ),
    ),
)
def test_execute_rejects_forged_technical_lineage_before_port(
    field_name: str,
    forged_value: object,
    expected_code: ReviewCoordinationErrorCode,
) -> None:
    coordinator, port, prepared = _prepare()
    forged = _forge(
        prepared,
        port_request=replace(prepared.port_request, **{field_name: forged_value}),
    )
    with pytest.raises(ReviewCoordinationError) as raised:
        coordinator.execute(prepared=forged)
    assert raised.value.code is expected_code
    assert port.calls == []


@pytest.mark.parametrize(
    "coverage_context",
    (
        {"severity_policy": {"forged": True}, "context_slice": {}, "independence_requirements": {}},
        {"severity_policy": {}, "context_slice": {"forged": True}, "independence_requirements": {}},
        {"severity_policy": {}, "context_slice": {}, "independence_requirements": {"forged": True}},
    ),
)
def test_execute_rejects_each_forged_coverage_subcontext(
    coverage_context: dict[str, object],
) -> None:
    coordinator, port, prepared = _prepare()
    forged = _forge(
        prepared,
        port_request=replace(prepared.port_request, coverage_context=coverage_context),
    )
    with pytest.raises(ReviewCoordinationError) as raised:
        coordinator.execute(prepared=forged)
    assert raised.value.code is ReviewCoordinationErrorCode.PREPARATION_MISMATCH
    assert port.calls == []


def test_execute_rejects_forged_snapshot_capability_request_and_target() -> None:
    coordinator, port, prepared = _prepare()
    forged_values = (
        _forge(prepared, capability_id=V02),
        _forge(prepared, canonical_request=_canonical(criteria={"forged": True})),
        _forge(
            prepared,
            target=ResolvedReviewTarget(prepared.target.target_production_ref, content="Forged."),
        ),
    )
    expected = (
        ReviewCoordinationErrorCode.CAPABILITY_OPERATION_MISMATCH,
        ReviewCoordinationErrorCode.PREPARATION_MISMATCH,
        ReviewCoordinationErrorCode.PREPARATION_MISMATCH,
    )
    for forged, code in zip(forged_values, expected, strict=True):
        with pytest.raises(ReviewCoordinationError) as raised:
            coordinator.execute(prepared=forged)
        assert raised.value.code is code
    assert port.calls == []


def test_execute_calls_port_once_and_returns_exact_technical_result() -> None:
    result = _result()
    coordinator, port, prepared = _prepare(response=result)
    assert coordinator.execute(prepared=prepared) is result
    assert port.calls == [prepared.port_request]


def test_execute_rejects_invalid_result_type_after_one_call() -> None:
    coordinator, port, prepared = _prepare(response=object())
    with pytest.raises(ReviewPortError) as raised:
        coordinator.execute(prepared=prepared)
    assert raised.value.code is ReviewPortErrorCode.INVALID_RESPONSE
    assert port.calls == [prepared.port_request]


@pytest.mark.parametrize(
    ("result", "code"),
    (
        (_result(source_step_id="other-step"), ReviewCoordinationErrorCode.SOURCE_STEP_MISMATCH),
        (
            _result(operation=ReviewOperation.ASSESS_FINDINGS),
            ReviewCoordinationErrorCode.OPERATION_MISMATCH,
        ),
        (
            _result(evidence_refs_used=("evidence:foreign",)),
            ReviewCoordinationErrorCode.EVIDENCE_REF_OUT_OF_SCOPE,
        ),
    ),
)
def test_execute_rejects_invalid_result_lineage_after_one_call(
    result: ReviewPortResult,
    code: ReviewCoordinationErrorCode,
) -> None:
    coordinator, port, prepared = _prepare(response=result)
    with pytest.raises(ReviewCoordinationError) as raised:
        coordinator.execute(prepared=prepared)
    assert raised.value.code is code
    assert port.calls == [prepared.port_request]


def test_execute_rejects_forged_duplicate_result_evidence_after_one_call() -> None:
    result = _forge_result(_result(), evidence_refs_used=("evidence:one", "evidence:one"))
    coordinator, port, prepared = _prepare(response=result)
    with pytest.raises(ReviewCoordinationError) as raised:
        coordinator.execute(prepared=prepared)
    assert raised.value.code is ReviewCoordinationErrorCode.DUPLICATE_EVIDENCE_REF_USED
    assert port.calls == [prepared.port_request]


def test_execute_propagates_port_error_without_retry_or_translation() -> None:
    error = ReviewPortError(ReviewPortErrorCode.UNAVAILABLE)
    coordinator, port, prepared = _prepare(response=error)
    with pytest.raises(ReviewPortError) as raised:
        coordinator.execute(prepared=prepared)
    assert raised.value is error
    assert port.calls == [prepared.port_request]


def test_coordination_errors_expose_only_fixed_safe_reasons() -> None:
    for code in ReviewCoordinationErrorCode:
        error = ReviewCoordinationError(code)
        assert str(error) == error.safe_reason
        assert "lesson-1" not in error.safe_reason
        assert "evidence:one" not in error.safe_reason
    with pytest.raises(TypeError, match="code"):
        ReviewCoordinationError("UNSUPPORTED_CAPABILITY")  # type: ignore[arg-type]


def test_preparation_models_are_deeply_immutable_frozen_and_slotted() -> None:
    canonical = _canonical()
    target = ResolvedReviewTarget(
        canonical.target_production_ref,
        structured_payload={"sections": ["intro"]},
    )
    preparation = ReviewPreparationRequest(
        V01,
        canonical,
        target,
        resolved_inputs={"nested": {"items": ["one"]}},
    )
    _, _, prepared = _prepare()
    assert target.structured_payload == {"sections": ("intro",)}
    assert preparation.resolved_inputs == {"nested": {"items": ("one",)}}
    with pytest.raises(FrozenInstanceError):
        preparation.capability_id = V02  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        prepared.capability_id = V02  # type: ignore[misc]
    assert not hasattr(target, "__dict__")
    assert not hasattr(preparation, "__dict__")
    assert not hasattr(prepared, "__dict__")
