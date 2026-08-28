from __future__ import annotations

from dataclasses import dataclass, field, replace

from backend.agent_runtime.agents.evidence import (
    EvidenceCoverageStatus,
    EvidenceSecurityScanner,
)
from backend.agent_runtime.agents.generation import (
    GenerationClaimAttribution,
    GenerationClaimClass,
    GenerationGuardDisposition,
    GenerationGuardPolicy,
    GenerationOperation,
)
from backend.agent_runtime.contracts import (
    AgentId,
    ExecutorKind,
    GateDecisionValue,
    ProductionValidationState,
    StepKind,
)
from backend.agent_runtime.gates import (
    BASELINE_GATE_AUTHORITY_POLICY,
    GateEngine,
    GateResolutionDisposition,
)
from backend.agent_runtime.observability import NullLogSink, NullMetricSink, NullTraceSink
from backend.agent_runtime.orchestration import (
    PlanCompiler,
    WorkflowKind,
    WorkflowRequirements,
    WorkflowResponsibility,
    WorkflowSelectionStatus,
    WorkflowSelector,
)
from backend.agent_runtime.recovery import (
    ReconciliationObservationDisposition,
    ReplayGuard,
    ReplayGuardDisposition,
)
from backend.agent_runtime.runtime import DeterministicScheduler, PlanExecutor
from evaluation_harness import (
    EvaluationDeadline,
    EvaluationFixtureHandle,
    EvaluationFixtureRef,
    EvaluationInputFactoryRef,
    EvaluationInvariantCode,
    EvaluationObservationRef,
    EvaluationObservationSnapshot,
    EvaluationObservationSnapshotEntry,
    EvaluationObservationValue,
    EvaluationRepetitionContext,
    EvaluationScorerRef,
    EvaluationTargetRef,
    EvaluationVerdict,
    InvariantCheckResult,
    InvariantNotFoundError,
    NormalizedScore,
    ObservationScalar,
    ObservationScalarKind,
    ObservationSequence,
    PreparedEvaluationInput,
    ScorerNotFoundError,
    ScorerOutcome,
    ScoreStatus,
    TargetExecutionOutcome,
    TargetExecutionStatus,
)
from tests.integration.test_ag02_search_rag_pipeline import (
    CHANNEL_ORDER,
)
from tests.integration.test_ag02_search_rag_pipeline import (
    _agent as evidence_agent,
)
from tests.integration.test_ag02_search_rag_pipeline import (
    _build_set as build_evidence_set,
)
from tests.integration.test_ag02_search_rag_pipeline import (
    _full_fixture as evidence_fixture,
)
from tests.integration.test_ag02_search_rag_pipeline import (
    _materialize_explicitly as materialize_evidence,
)
from tests.integration.test_ag02_search_rag_pipeline import (
    _request as evidence_request,
)
from tests.integration.test_ag03_generation_pipeline import (
    _assessment as generation_assessment,
)
from tests.integration.test_ag03_generation_pipeline import (
    _candidate_request as generation_candidate_request,
)
from tests.integration.test_ag03_generation_pipeline import (
    _execute_generation as execute_generation,
)
from tests.integration.test_ag03_generation_pipeline import (
    _request as generation_request,
)
from tests.integration.test_ag03_generation_pipeline import (
    _technical as generation_technical,
)
from tests.integration.test_retry_after_reconciliation import (
    _reconcile as reconcile_effect,
)
from tests.integration.test_retry_after_reconciliation import (
    _unknown_record as unknown_effect_record,
)
from tests.integration.test_review_security_pipeline import (
    _materialize as materialize_review,
)
from tests.integration.test_review_security_pipeline import (
    _v01_result as review_technical,
)
from tests.integration.test_runtime_observability_integration import (
    _execute as execute_observed_runtime,
)
from tests.integration.test_workflow_selection_to_plan import (
    _binding as workflow_binding,
)
from tests.integration.test_workflow_selection_to_plan import (
    _request as workflow_compilation_request,
)
from tests.support.gate_fakes import (
    NOW as GATE_NOW,
)
from tests.support.gate_fakes import (
    RecordingGateDecisionSource,
    make_gate_decision,
    make_gate_request,
)
from tests.support.retry_replay_fakes import make_none_record, make_preconditions
from tests.support.runtime_observability_fakes import (
    RaisingLogSink,
    RaisingMetricSink,
    RaisingTraceSink,
)
from tests.support.runtime_routing_fakes import (
    NOW as RUNTIME_NOW,
)
from tests.support.runtime_routing_fakes import (
    make_plan,
    make_run_state,
    make_runtime_harness,
    make_step,
)
from tests.support.use_case_routing_fakes import make_request, make_router


@dataclass(slots=True)
class TechnicalEvaluationInput:
    profile_code: str
    repetition_index: int

    @property
    def evaluation_input_marker(self) -> None:
        return None


@dataclass(slots=True)
class TechnicalRuntimeFixture:
    repetition_index: int
    invocation_codes: list[str] = field(default_factory=list)
    cleaned: bool = False

    @property
    def evaluation_fixture_marker(self) -> None:
        return None


class TechnicalRuntimeInputFactory:
    def __init__(self) -> None:
        self.calls: list[EvaluationRepetitionContext] = []
        self.inputs: list[TechnicalEvaluationInput] = []

    def build(
        self,
        input_factory_ref: EvaluationInputFactoryRef,
        context: EvaluationRepetitionContext,
    ) -> PreparedEvaluationInput:
        self.calls.append(context)
        value = TechnicalEvaluationInput(input_factory_ref.value, context.repetition_index)
        self.inputs.append(value)
        return value


class TechnicalRuntimeFixtureFactory:
    def __init__(self) -> None:
        self.create_calls: list[EvaluationRepetitionContext] = []
        self.cleanup_calls: list[EvaluationRepetitionContext] = []
        self.fixtures: list[TechnicalRuntimeFixture] = []

    def create(
        self,
        fixture_ref: EvaluationFixtureRef,
        context: EvaluationRepetitionContext,
    ) -> EvaluationFixtureHandle:
        if fixture_ref.value != "runtime-fixture":
            raise LookupError
        self.create_calls.append(context)
        value = TechnicalRuntimeFixture(context.repetition_index)
        self.fixtures.append(value)
        return value

    def cleanup(
        self,
        handle: EvaluationFixtureHandle,
        context: EvaluationRepetitionContext,
    ) -> None:
        if not isinstance(handle, TechnicalRuntimeFixture):
            raise TypeError("unsupported technical fixture")
        handle.cleaned = True
        self.cleanup_calls.append(context)


@dataclass(frozen=True, slots=True)
class ClosedTechnicalFacts:
    primary_fact: bool
    technical_checks: tuple[bool, ...]
    status_codes: tuple[str, ...] = ()
    counts: tuple[int, ...] = ()


class ClosedFactSnapshotProjector:
    """Allowlisted projection of closed owner facts only."""

    def project(
        self,
        target_code: str,
        facts: ClosedTechnicalFacts,
    ) -> EvaluationObservationSnapshot:
        prefix = f"runtime.{target_code}"
        return EvaluationObservationSnapshot(
            (
                EvaluationObservationSnapshotEntry(
                    EvaluationObservationRef(f"{prefix}.primary"),
                    _boolean(facts.primary_fact),
                ),
                EvaluationObservationSnapshotEntry(
                    EvaluationObservationRef(f"{prefix}.checks"),
                    ObservationSequence(tuple(_boolean(item) for item in facts.technical_checks)),
                ),
                EvaluationObservationSnapshotEntry(
                    EvaluationObservationRef(f"{prefix}.status-codes"),
                    ObservationSequence(tuple(_string(item) for item in facts.status_codes)),
                ),
                EvaluationObservationSnapshotEntry(
                    EvaluationObservationRef(f"{prefix}.counts"),
                    ObservationSequence(tuple(_integer(item) for item in facts.counts)),
                ),
            )
        )


class TechnicalRuntimeTargetExecutor:
    """Explicitly composed test-only bridge to canonical production owners."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []
        self.projected_facts: list[tuple[str, ClosedTechnicalFacts]] = []
        self._projector = ClosedFactSnapshotProjector()

    def execute(
        self,
        target: EvaluationTargetRef,
        prepared_input: PreparedEvaluationInput,
        fixture: EvaluationFixtureHandle | None,
        context: EvaluationRepetitionContext,
        deadline: EvaluationDeadline,
    ) -> TargetExecutionOutcome:
        del deadline
        if not isinstance(prepared_input, TechnicalEvaluationInput):
            raise TypeError("unsupported technical input")
        if not isinstance(fixture, TechnicalRuntimeFixture):
            raise TypeError("technical runtime target requires a fixture")
        code = target.code.value
        self.calls.append((code, context.repetition_index))
        fixture.invocation_codes.append(code)
        facts = self._execute_owner(code, prepared_input)
        self.projected_facts.append((code, facts))
        return TargetExecutionOutcome(
            TargetExecutionStatus.COMPLETED,
            self._projector.project(code, facts),
            duration_milliseconds=1,
        )

    def _execute_owner(
        self,
        code: str,
        prepared_input: TechnicalEvaluationInput,
    ) -> ClosedTechnicalFacts:
        if code == "ag01":
            return _ag01_facts()
        if code == "ag02":
            return _ag02_facts(prepared_input.repetition_index)
        if code == "ag03":
            return _ag03_facts(prepared_input.repetition_index)
        if code == "ag04":
            return _ag04_facts()
        if code == "authority":
            return _authority_facts()
        if code == "security":
            return _security_facts()
        if code == "recovery":
            return _recovery_facts()
        if code == "observability":
            return _observability_facts()
        if code == "comparison":
            return _comparison_facts(prepared_input.profile_code)
        raise LookupError


class TechnicalOwnerInvariantEvaluator:
    def evaluate(
        self,
        invariant_code: EvaluationInvariantCode,
        observation: EvaluationObservationValue,
    ) -> InvariantCheckResult:
        if invariant_code.value != "owner.closed-fact-true":
            raise InvariantNotFoundError
        passed = (
            type(observation) is ObservationScalar
            and observation.kind is ObservationScalarKind.BOOLEAN
            and observation.value is True
        )
        return InvariantCheckResult(
            EvaluationVerdict.PASS if passed else EvaluationVerdict.FAIL
        )


class TechnicalFactScorer:
    def score(
        self,
        scorer_ref: EvaluationScorerRef,
        observations: tuple[EvaluationObservationValue, ...],
    ) -> ScorerOutcome:
        if scorer_ref.value != "technical-fact-ratio":
            raise ScorerNotFoundError
        checks: list[bool] = []
        for observation in observations:
            if type(observation) is ObservationScalar:
                if observation.kind is not ObservationScalarKind.BOOLEAN:
                    raise TypeError("technical score accepts boolean facts only")
                checks.append(observation.value is True)
            elif type(observation) is ObservationSequence:
                for item in observation.items:
                    if type(item) is not ObservationScalar or item.kind is not ObservationScalarKind.BOOLEAN:
                        raise TypeError("technical score accepts boolean facts only")
                    checks.append(item.value is True)
            else:
                raise TypeError("technical score accepts boolean facts only")
        if not checks:
            raise TypeError("technical score requires facts")
        return ScorerOutcome(
            ScoreStatus.SCORED,
            NormalizedScore(sum(checks), len(checks)),
        )


def _ag01_facts() -> ClosedTechnicalFacts:
    requirements = WorkflowRequirements(
        external_evidence_required=True,
        production_required=True,
        independent_review_required=True,
    )
    selection = WorkflowSelector().select(requirements)
    responsibilities = (
        WorkflowResponsibility.EVIDENCE,
        WorkflowResponsibility.GENERATE_TRANSFORM,
        WorkflowResponsibility.DETERMINISTIC_VALIDATION,
        WorkflowResponsibility.REVIEW,
    )
    bindings = tuple(workflow_binding(0, item) for item in responsibilities)
    plan = PlanCompiler().compile(workflow_compilation_request(selection, bindings))
    executors = tuple(step.executor.kind for step in plan.steps)
    expected = (
        ExecutorKind.AG_02,
        ExecutorKind.AG_03,
        ExecutorKind.APPLICATION,
        ExecutorKind.AG_04,
    )
    return ClosedTechnicalFacts(
        selection.status is WorkflowSelectionStatus.SELECTED and executors == expected,
        (len(selection.stages) == 1, len(plan.steps) == 4, executors == expected),
        tuple(stage.workflow_kind.value for stage in selection.stages),
        (len(plan.steps),),
    )


def _ag02_facts(repetition_index: int) -> ClosedTechnicalFacts:
    request = evidence_request(suffix=f"g-{repetition_index}")
    _, responses, documents = evidence_fixture()
    agent, search_port, document_port = evidence_agent(responses, documents)
    retrieval = agent.search_evidence(request=request)
    materialized, errors = materialize_evidence(agent, request, retrieval)
    coverage, evidence_set = build_evidence_set(
        agent, request, retrieval, materialized
    )
    security = EvidenceSecurityScanner().assess(evidence_set=evidence_set)
    channels = tuple(channel for _, channel in search_port.calls)
    checks = (
        channels == CHANNEL_ORDER,
        not errors,
        len(document_port.calls) == len(materialized) == 3,
        not security.document_instructions_authoritative,
    )
    return ClosedTechnicalFacts(
        coverage.status is EvidenceCoverageStatus.COMPLETE and all(checks),
        checks,
        (retrieval.mode.value, coverage.status.value),
        (len(retrieval.ranked_candidates), len(materialized)),
    )


def _ag03_facts(repetition_index: int) -> ClosedTechnicalFacts:
    request = generation_request(step_id=f"step-g-{repetition_index}")
    technical = generation_technical(request.meta.step_id, GenerationOperation.GENERATE)
    agent, prepared, result, port = execute_generation(request, "CAP-G01", technical)
    guard = generation_assessment(
        prepared,
        result,
        policy=GenerationGuardPolicy(grounding_required=True),
        attributions=(
            GenerationClaimAttribution(
                "claim:technical",
                GenerationClaimClass.GROUNDED,
                ("evidence:one",),
            ),
        ),
    )
    candidate = agent.build_candidate(
        request=generation_candidate_request(request, prepared, result, guard)
    )
    checks = (
        len(port.calls) == 1,
        guard.disposition is GenerationGuardDisposition.ALLOW,
        candidate.validation_state is ProductionValidationState.CANDIDATE,
        candidate.lineage["capability_id"] == "CAP-G01",
    )
    return ClosedTechnicalFacts(
        all(checks),
        checks,
        (result.status.value, guard.disposition.value),
        (len(port.calls),),
    )


def _ag04_facts() -> ClosedTechnicalFacts:
    result, port = materialize_review(
        technical=review_technical("Exact secure target.")
    )
    checks = (
        len(port.calls) == 1,
        result.correction_required is False,
        len(result.findings) == 1,
    )
    return ClosedTechnicalFacts(
        all(checks),
        checks,
        (result.meta.status.value, result.overall_assessment.value),
        (len(result.findings), len(port.calls)),
    )


def _authority_facts() -> ClosedTechnicalFacts:
    gate_request = make_gate_request()
    source = RecordingGateDecisionSource(
        make_gate_decision(gate_request, value=GateDecisionValue.APPROVED)
    )
    resolution = GateEngine(BASELINE_GATE_AUTHORITY_POLICY, source).evaluate(
        request=gate_request,
        now=GATE_NOW,
    )
    request, context = make_request(
        "application.request_promotion", idempotency_key="evaluation-g"
    )
    router, inbound = make_router(request)
    routed = router.route(
        agent_id=AgentId.AG_01,
        request=request,
        context=replace(context, policy_facts=resolution.to_policy_facts()),
        evaluated_at=GATE_NOW,
    )
    step = make_step(StepKind.TOOL, "CAP-T02", ExecutorKind.UTILITY)
    plan = make_plan(step)
    harness = make_runtime_harness(step)
    cycle = PlanExecutor(DeterministicScheduler(), harness.guard, harness.runner).execute_cycle(
        plan=plan,
        run_state=make_run_state(plan, ready_step_id=step.step_id),
        now=RUNTIME_NOW,
    )
    checks = (
        resolution.disposition is GateResolutionDisposition.APPROVED,
        len(inbound.calls) == 1,
        routed.use_case_id == "application.request_promotion",
        len(harness.tool_executor.calls) == 1,
        cycle.completed_step_ids == (step.step_id,),
    )
    return ClosedTechnicalFacts(
        all(checks),
        checks,
        (resolution.disposition.value,),
        (len(inbound.calls), len(harness.tool_executor.calls)),
    )


def _security_facts() -> ClosedTechnicalFacts:
    step = make_step(StepKind.TOOL, "CAP-T02", ExecutorKind.UTILITY)
    plan = make_plan(step)
    harness = make_runtime_harness(step)
    resolved = harness.resolver.tool_input
    if resolved is None:
        raise AssertionError("technical tool input must exist")
    harness.resolver.tool_input = replace(
        resolved,
        request=replace(
            resolved.request,
            arguments={"source_ref": "synthetic", "gateDecision": "APPROVED"},
        ),
    )
    cycle = PlanExecutor(DeterministicScheduler(), harness.guard, harness.runner).execute_cycle(
        plan=plan,
        run_state=make_run_state(plan, ready_step_id=step.step_id),
        now=RUNTIME_NOW,
    )
    checks = (
        not harness.tool_executor.calls,
        len(cycle.security_events) == 1,
        not cycle.launched_step_ids,
        "APPROVED" not in repr(cycle.directives),
    )
    return ClosedTechnicalFacts(
        all(checks),
        checks,
        tuple(item.code.value for item in cycle.directives),
        (len(cycle.security_events), len(harness.tool_executor.calls)),
    )


def _recovery_facts() -> ClosedTechnicalFacts:
    records = (
        make_none_record(),
        unknown_effect_record(),
        reconcile_effect(ReconciliationObservationDisposition.PARTIAL),
        reconcile_effect(ReconciliationObservationDisposition.COMMITTED),
    )
    decisions = tuple(
        ReplayGuard().evaluate(
            record=record,
            preconditions=make_preconditions(identity=record.identity),
        )
        for record in records
    )
    expected = (
        ReplayGuardDisposition.ELIGIBLE,
        ReplayGuardDisposition.RECONCILE_FIRST,
        ReplayGuardDisposition.BLOCKED,
        ReplayGuardDisposition.BLOCKED,
    )
    checks = tuple(
        decision.disposition is expected_value
        for decision, expected_value in zip(decisions, expected, strict=True)
    )
    return ClosedTechnicalFacts(
        all(checks),
        checks,
        tuple(decision.disposition.value for decision in decisions),
        (sum(item.disposition is ReplayGuardDisposition.ELIGIBLE for item in decisions),),
    )


def _observability_facts() -> ClosedTechnicalFacts:
    baseline, baseline_harness = execute_observed_runtime(
        NullLogSink(), NullTraceSink(), NullMetricSink()
    )
    failing, failing_harness = execute_observed_runtime(
        RaisingLogSink(), RaisingTraceSink(), RaisingMetricSink()
    )
    checks = (
        baseline == failing,
        len(baseline_harness.tool_executor.calls) == 1,
        len(failing_harness.tool_executor.calls) == 1,
    )
    return ClosedTechnicalFacts(
        all(checks),
        checks,
        ("DISABLED", "FAILING", "EQUIVALENT"),
        (
            len(baseline_harness.tool_executor.calls),
            len(failing_harness.tool_executor.calls),
        ),
    )


def _comparison_facts(profile_code: str) -> ClosedTechnicalFacts:
    requirements = WorkflowRequirements(
        production_required=True,
        independent_review_required=profile_code.endswith("candidate"),
    )
    selection = WorkflowSelector().select(requirements)
    kinds = tuple(stage.workflow_kind for stage in selection.stages)
    checks = (
        selection.status is WorkflowSelectionStatus.SELECTED,
        any(kind in {WorkflowKind.WF_2, WorkflowKind.WF_5} for kind in kinds),
        WorkflowKind.WF_5 in kinds,
    )
    return ClosedTechnicalFacts(
        checks[0],
        checks,
        tuple(kind.value for kind in kinds),
        (len(kinds),),
    )


def _boolean(value: bool) -> ObservationScalar:
    return ObservationScalar(ObservationScalarKind.BOOLEAN, value)


def _integer(value: int) -> ObservationScalar:
    return ObservationScalar(ObservationScalarKind.INTEGER, value)


def _string(value: str) -> ObservationScalar:
    return ObservationScalar(ObservationScalarKind.STRING, value)
