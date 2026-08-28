"""Test-only SCN-01 binding from the golden corpus to WF-0/Application/OP-03."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from backend.agent_runtime.application_routing import (
    ApplicationInboundPort,
    UseCaseRouter,
    UseCaseRoutingContext,
)
from backend.agent_runtime.contracts import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    ActorKind,
    ActorRef,
    AgentId,
    ContractMeta,
    ExecutorKind,
    ExecutorRef,
    InvocationStatus,
    PermissionScope,
    StepKind,
    StepSpec,
    UseCaseRequest,
    UseCaseResult,
)
from backend.agent_runtime.orchestration.selection import (
    WorkflowRequirements,
    WorkflowSelectionDecision,
    WorkflowSelectionStatus,
    WorkflowSelector,
)
from backend.agent_runtime.orchestration.workflows import WorkflowKind
from backend.core_contracts.capability import CapabilityId
from backend.core_contracts.invocation import UseCaseContext
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant
from evaluation_harness import (
    EvaluationDeadline,
    EvaluationFixtureHandle,
    EvaluationFixtureRef,
    EvaluationInputFactoryRef,
    EvaluationObservationRef,
    EvaluationObservationSnapshot,
    EvaluationObservationSnapshotEntry,
    EvaluationRepetitionContext,
    EvaluationTargetRef,
    FixtureNotFoundError,
    InputFactoryNotFoundError,
    ObservationScalar,
    ObservationScalarKind,
    ObservationSequence,
    PreparedEvaluationInput,
    TargetExecutionOutcome,
    TargetExecutionStatus,
    TargetExecutorNotFoundError,
)
from tests.e2e.core.catalog import PEDAGOGICAL_INPUT_FACTORY_REF
from tests.e2e.core.fixtures import SyntheticPedagogicalFixture, fixture_for

SCN_01_RESOURCE_REF = "resource-assessment:00eb327998342b43b7416808"
_SCN_01_TARGET = "pedagogical.scn-01"
_APPLICATION_PATH = "WF0_APPLICATION_GETRESOURCE_OP03_SQLITE"
_USE_CASE_ID = "application.read_canonical_resource"


@dataclass(frozen=True, slots=True)
class C2PreparedInput:
    resource_ref: str

    @property
    def evaluation_input_marker(self) -> None:
        return None


@dataclass(frozen=True, slots=True)
class C2FixtureHandle:
    fixture: SyntheticPedagogicalFixture

    @property
    def evaluation_fixture_marker(self) -> None:
        return None


@dataclass(frozen=True, slots=True)
class C2ExecutionWitness:
    selection: WorkflowSelectionDecision
    request: UseCaseRequest
    result: UseCaseResult[object, object]
    route_count: int


@dataclass(frozen=True, slots=True)
class FixedEvaluationClock:
    second: int

    def now_seconds(self) -> int:
        return self.second


class C2InputFactory:
    def __init__(self, resource_ref: str = SCN_01_RESOURCE_REF) -> None:
        self._resource_ref = resource_ref

    def build(
        self,
        input_factory_ref: EvaluationInputFactoryRef,
        context: EvaluationRepetitionContext,
    ) -> PreparedEvaluationInput:
        del context
        if input_factory_ref != PEDAGOGICAL_INPUT_FACTORY_REF:
            raise InputFactoryNotFoundError(input_factory_ref.value)
        return C2PreparedInput(self._resource_ref)


class C2FixtureFactory:
    def create(
        self,
        fixture_ref: EvaluationFixtureRef,
        context: EvaluationRepetitionContext,
    ) -> EvaluationFixtureHandle:
        del context
        fixture = fixture_for(fixture_ref)
        if fixture is None:
            raise FixtureNotFoundError(fixture_ref.value)
        return C2FixtureHandle(fixture)

    def cleanup(
        self,
        handle: EvaluationFixtureHandle,
        context: EvaluationRepetitionContext,
    ) -> None:
        del handle, context


class CountingApplicationInbound:
    """Recording wrapper around the real inbound, used only for route cardinality."""

    def __init__(self, delegate: ApplicationInboundPort) -> None:
        if not isinstance(delegate, ApplicationInboundPort):
            raise TypeError("delegate must implement ApplicationInboundPort")
        self._delegate = delegate
        self.calls: list[UseCaseRequest] = []

    def invoke(self, *, request: UseCaseRequest) -> UseCaseResult[object, object]:
        self.calls.append(request)
        return self._delegate.invoke(request=request)


class C2SQLiteTargetExecutor:
    def __init__(
        self,
        router: UseCaseRouter,
        inbound: CountingApplicationInbound,
        now: Instant,
    ) -> None:
        self._router = router
        self._inbound = inbound
        self._now = now
        self.last_witness: C2ExecutionWitness | None = None

    def execute(
        self,
        target: EvaluationTargetRef,
        prepared_input: PreparedEvaluationInput,
        fixture: EvaluationFixtureHandle | None,
        context: EvaluationRepetitionContext,
        deadline: EvaluationDeadline,
    ) -> TargetExecutionOutcome:
        del deadline
        if target.code.value != _SCN_01_TARGET:
            raise TargetExecutorNotFoundError(target.code.value)
        if type(prepared_input) is not C2PreparedInput:
            raise TypeError("SCN-01 requires C2PreparedInput")
        if type(fixture) is not C2FixtureHandle:
            raise TypeError("SCN-01 requires its declared fixture")

        selection = WorkflowSelector().select(
            WorkflowRequirements(application_action_required=True)
        )
        if (
            selection.status is not WorkflowSelectionStatus.SELECTED
            or tuple(stage.workflow_kind for stage in selection.stages)
            != (WorkflowKind.WF_0,)
        ):
            raise RuntimeError("SCN-01 did not choose the canonical WF-0 path")

        request, routing_context = _route_input(prepared_input, context, self._now)
        result = self._router.route(
            agent_id=AgentId.AG_01,
            request=request,
            context=routing_context,
            evaluated_at=self._now,
        )
        route_count = len(self._inbound.calls)
        self.last_witness = C2ExecutionWitness(
            selection, request, result, route_count
        )
        return TargetExecutionOutcome(
            TargetExecutionStatus.COMPLETED,
            _observations(prepared_input, result, route_count),
            duration_milliseconds=1,
        )


def _route_input(
    prepared: C2PreparedInput,
    context: EvaluationRepetitionContext,
    now: Instant,
) -> tuple[UseCaseRequest, UseCaseRoutingContext]:
    suffix = f"{context.case_id.value}-{context.repetition_index}"
    principal = ActorRef(ActorKind.AGENT, AgentId.AG_01.value)
    capability_id = CapabilityId("CAP-R01")
    step = StepSpec(
        step_id=f"step-{suffix}",
        kind=StepKind.USE_CASE,
        capability_id=capability_id,
        executor=ExecutorRef(ExecutorKind.APPLICATION),
        objective="Read one canonical resource through Application",
        permission_scope_ref=f"permission-{suffix}",
        output_contract={"contract_id": "C-13"},
    )
    request = UseCaseRequest(
        meta=ContractMeta(
            schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
            run_id=f"run-{suffix}",
            step_id=step.step_id,
            parent_step_id=None,
            correlation_id=CorrelationId(f"corr-{suffix}"),
            created_at=now,
            actor=principal,
            status=InvocationStatus.PLANNED,
        ),
        use_case_id=_USE_CASE_ID,
        payload={"resource_ref": prepared.resource_ref},
        actor_context=UseCaseContext(
            correlation_id=CorrelationId(f"corr-{suffix}")
        ),
    )
    scope = PermissionScope(
        principal=principal,
        capability_ids=(capability_id,),
        resource_scope={"resource_refs": (prepared.resource_ref,)},
        operations=("read",),
        valid_from=now,
    )
    return (
        request,
        UseCaseRoutingContext(
            step=step,
            permission_scope_ref=f"permission-{suffix}",
            permission_scope=scope,
        ),
    )


def _observations(
    prepared: C2PreparedInput,
    result: UseCaseResult[object, object],
    route_count: int,
) -> EvaluationObservationSnapshot:
    if not result.outcome.success or not isinstance(result.outcome.data, Mapping):
        raise RuntimeError("SCN-01 resource read did not succeed")
    resource_ref = result.outcome.data.get("resource_ref")
    if type(resource_ref) is not str:
        raise RuntimeError("SCN-01 result did not preserve a logical resource ref")
    values: tuple[tuple[str, ObservationScalar], ...] = (
        ("scn-01.workflow", _string("WF-0")),
        ("scn-01.expected.workflow", _string("WF-0")),
        ("scn-01.application-path", _string(_APPLICATION_PATH)),
        ("scn-01.expected.application-path", _string(_APPLICATION_PATH)),
        (
            "scn-01.route-count",
            ObservationSequence(
                tuple(_string(_USE_CASE_ID) for _ in range(route_count))
            ),
        ),
        ("scn-01.resource-ref", _string(resource_ref)),
        ("scn-01.expected.resource-ref", _string(prepared.resource_ref)),
    )
    return EvaluationObservationSnapshot(
        tuple(
            EvaluationObservationSnapshotEntry(EvaluationObservationRef(ref), value)
            for ref, value in values
        )
    )


def _string(value: str) -> ObservationScalar:
    return ObservationScalar(ObservationScalarKind.STRING, value)
