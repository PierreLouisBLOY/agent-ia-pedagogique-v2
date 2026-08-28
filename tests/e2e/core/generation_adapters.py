"""Test-only D bindings for real AG-03, AG-04, GateEngine and workflow owners."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime

from backend.agent_runtime.agents.evidence import (
    EvidenceAgent,
    EvidenceCoverageStatus,
    EvidenceFetchRequest,
    EvidenceSetBuildRequest,
)
from backend.agent_runtime.agents.generation import (
    GenerationCoordinator,
    GenerationGuardAssessment,
    GenerationGuardDisposition,
    GenerationGuardPolicy,
    GenerationGuardRequest,
    GenerationOperation,
    GenerationOutputGuard,
    GenerationPortResult,
    GenerationPortResultStatus,
    GenerationPreparationRequest,
    GeneratorAgent,
    ProductionCandidateBuildRequest,
)
from backend.agent_runtime.agents.review import (
    ResolvedReviewTarget,
    ReviewCoordinator,
    ReviewerAgent,
    ReviewOperation,
    ReviewPortResult,
    ReviewPortResultStatus,
    ReviewPreparationRequest,
    ReviewResultMaterializationRequest,
)
from backend.agent_runtime.contracts import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    ActorKind,
    ActorRef,
    AgentId,
    AgentResultStatus,
    ContractMeta,
    EvidenceRequest,
    EvidenceSet,
    FailurePolicy,
    GateDecisionValue,
    GateRequest,
    GateStatus,
    InvocationStatus,
    OverallAssessment,
    ProductionCandidate,
    ProductionRequest,
    ProductionValidationState,
    ReviewDimension,
    ReviewRequest,
    ReviewResult,
    ReviewStatus,
)
from backend.agent_runtime.gates import (
    BASELINE_GATE_AUTHORITY_POLICY,
    GateEngine,
    GateResolution,
    GateResolutionDisposition,
)
from backend.agent_runtime.orchestration.compilation import (
    HumanGateAnchor,
    HumanGateBinding,
    PlanCompilationRequest,
    PlanCompiler,
    PlanStepBinding,
)
from backend.agent_runtime.orchestration.selection import (
    WorkflowRequirements,
    WorkflowSelectionStatus,
    WorkflowSelector,
)
from backend.agent_runtime.orchestration.workflows import WorkflowResponsibility
from backend.agent_runtime.runtime import Plan
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.identifiers import TypedEntityId
from backend.shared_kernel.references import ObjectVersionRef, TypedEntityRef, VersionRef
from backend.shared_kernel.time import Instant
from evaluation_harness import (
    EvaluationCaseCode,
    EvaluationDeadline,
    EvaluationFixtureHandle,
    EvaluationFixtureRef,
    EvaluationInputFactoryRef,
    EvaluationInvariantCode,
    EvaluationObservationRef,
    EvaluationObservationSnapshot,
    EvaluationObservationSnapshotEntry,
    EvaluationRepetitionContext,
    EvaluationTargetRef,
    EvaluationVerdict,
    FixtureNotFoundError,
    InputFactoryNotFoundError,
    InvariantCheckResult,
    InvariantNotFoundError,
    ObservationScalar,
    ObservationScalarKind,
    ObservationSequence,
    PreparedEvaluationInput,
    TargetExecutionOutcome,
    TargetExecutionStatus,
    TargetExecutorNotFoundError,
)
from tests.e2e.core.catalog import (
    PEDAGOGICAL_INPUT_FACTORY_REF,
    scenario_for,
)
from tests.e2e.core.fixtures import SyntheticPedagogicalFixture, fixture_for
from tests.support.gate_fakes import (
    RecordingGateDecisionSource,
    make_gate_decision,
)
from tests.support.generation_fakes import RecordingGenerationPort
from tests.support.review_fakes import RecordingReviewPort

D_NOW = Instant(datetime(2026, 8, 28, 12, 0, tzinfo=UTC))
D_LATER = Instant(datetime(2026, 8, 28, 12, 1, tzinfo=UTC))
D_GATE_NOW = Instant(datetime(2026, 8, 28, 12, 2, tzinfo=UTC))
SCN04_EVIDENCE_QUERY = "tva"
SCN04_TARGET_REF = "synthetic:scn-04.tva-note"

_D_TARGETS = frozenset(
    {"pedagogical.scn-03", "pedagogical.scn-04", "pedagogical.scn-05"}
)
_CASE_BY_ID = {
    "case.scn-03": EvaluationCaseCode("SCN-03"),
    "case.scn-04": EvaluationCaseCode("SCN-04"),
    "case.scn-05": EvaluationCaseCode("SCN-05"),
}
_INVARIANTS = frozenset(
    {
        "pedagogical.scn-04.transformation-lineage",
        "pedagogical.scn-05.gate-before-downstream",
        "pedagogical.scn-05.review-performed",
    }
)


@dataclass(frozen=True, slots=True)
class DPreparedInput:
    case_code: EvaluationCaseCode
    level: str
    expected_sections: tuple[str, ...]

    @property
    def evaluation_input_marker(self) -> None:
        return None


@dataclass(frozen=True, slots=True)
class DFixtureHandle:
    fixture: SyntheticPedagogicalFixture

    @property
    def evaluation_fixture_marker(self) -> None:
        return None


@dataclass(frozen=True, slots=True)
class GenerationWitness:
    request: ProductionRequest
    candidate: ProductionCandidate
    guard: GenerationGuardAssessment
    port_call_count: int


@dataclass(frozen=True, slots=True)
class DScenarioWitness:
    plan: Plan
    events: tuple[str, ...]
    generation: GenerationWitness
    evidence_set: EvidenceSet | None = None
    review: ReviewResult | None = None
    review_port_call_count: int = 0
    gate: GateResolution | None = None
    continuation_count: int = 0
    source_unchanged: bool = True


@dataclass(frozen=True, slots=True)
class GateSequenceWitness:
    resolution: GateResolution
    decision_request: GateRequest
    source_request: GateRequest
    events: tuple[str, ...]
    source_call_count: int
    continuation_count: int


@dataclass(frozen=True, slots=True)
class FixedEvaluationClock:
    second: int

    def now_seconds(self) -> int:
        return self.second


class DInputFactory:
    def build(
        self,
        input_factory_ref: EvaluationInputFactoryRef,
        context: EvaluationRepetitionContext,
    ) -> PreparedEvaluationInput:
        if input_factory_ref != PEDAGOGICAL_INPUT_FACTORY_REF:
            raise InputFactoryNotFoundError(input_factory_ref.value)
        try:
            case_code = _CASE_BY_ID[context.case_id.value]
        except KeyError as error:
            raise InputFactoryNotFoundError(context.case_id.value) from error
        scenario = scenario_for(case_code)
        if scenario is None:
            raise InputFactoryNotFoundError(case_code.value)
        return DPreparedInput(
            case_code,
            scenario.level.value,
            tuple(section.value for section in scenario.section_codes),
        )


class DFixtureFactory:
    def create(
        self,
        fixture_ref: EvaluationFixtureRef,
        context: EvaluationRepetitionContext,
    ) -> EvaluationFixtureHandle:
        del context
        fixture = fixture_for(fixture_ref)
        if fixture is None:
            raise FixtureNotFoundError(fixture_ref.value)
        return DFixtureHandle(fixture)

    def cleanup(
        self,
        handle: EvaluationFixtureHandle,
        context: EvaluationRepetitionContext,
    ) -> None:
        del handle, context


class DInvariantEvaluator:
    def evaluate(
        self,
        invariant_code: EvaluationInvariantCode,
        observation: object,
    ) -> InvariantCheckResult:
        if invariant_code.value not in _INVARIANTS:
            raise InvariantNotFoundError(invariant_code.value)
        passed = (
            type(observation) is ObservationScalar
            and observation.kind is ObservationScalarKind.BOOLEAN
            and observation.value is True
        )
        return InvariantCheckResult(
            EvaluationVerdict.PASS if passed else EvaluationVerdict.FAIL
        )


class RecordingContinuation:
    def __init__(self, events: list[str]) -> None:
        self._events = events
        self.calls = 0

    def continue_after_gate(self) -> None:
        self.calls += 1
        self._events.append("continuation")


class DGenerationTargetExecutor:
    def __init__(
        self,
        generation_port: RecordingGenerationPort,
        review_port: RecordingReviewPort,
        evidence_agent: EvidenceAgent | None,
    ) -> None:
        self._generation_port = generation_port
        self._review_port = review_port
        self._generator = GeneratorAgent(GenerationCoordinator(generation_port))
        self._reviewer = ReviewerAgent(ReviewCoordinator(review_port))
        self._evidence_agent = evidence_agent
        self.witnesses: dict[str, DScenarioWitness] = {}
        self.raw_texts: list[str] = []

    def execute(
        self,
        target: EvaluationTargetRef,
        prepared_input: PreparedEvaluationInput,
        fixture: EvaluationFixtureHandle | None,
        context: EvaluationRepetitionContext,
        deadline: EvaluationDeadline,
    ) -> TargetExecutionOutcome:
        del context, deadline
        if target.code.value not in _D_TARGETS:
            raise TargetExecutorNotFoundError(target.code.value)
        if type(prepared_input) is not DPreparedInput:
            raise TypeError("D scenarios require DPreparedInput")
        if type(fixture) is not DFixtureHandle:
            raise TypeError("D scenarios require their declared fixture")
        self.raw_texts.extend(source.text for source in fixture.fixture.sources)

        if prepared_input.case_code == EvaluationCaseCode("SCN-03"):
            witness, snapshot = self._execute_scn03(prepared_input)
        elif prepared_input.case_code == EvaluationCaseCode("SCN-04"):
            witness, snapshot = self._execute_scn04(prepared_input, fixture)
        else:
            witness, snapshot = self._execute_scn05(prepared_input)
        self.witnesses[prepared_input.case_code.value] = witness
        return TargetExecutionOutcome(
            TargetExecutionStatus.COMPLETED,
            snapshot,
            duration_milliseconds=1,
        )

    def _execute_scn03(
        self, prepared_input: DPreparedInput
    ) -> tuple[DScenarioWitness, EvaluationObservationSnapshot]:
        plan = compile_d_plan(prepared_input.case_code)
        generation = self._generate(
            case_code="SCN-03",
            plan=plan,
            level=prepared_input.level,
            expected_sections=prepared_input.expected_sections,
            capability_id=CapabilityId("CAP-G01"),
            production_kind="course_lesson",
            evidence_refs=(),
            target_ref=None,
        )
        events = ("AG-03:CAP-G01",)
        witness = DScenarioWitness(plan, events, generation)
        authority_summary = "|".join(
            (
                generation.candidate.validation_state.value,
                str(generation.candidate.lineage["capability_id"]),
                str(generation.candidate.lineage["generation_operation"]),
            )
        )
        values = (
            ("scn-03.workflow", _string("WF-2")),
            ("scn-03.expected.workflow", _string("WF-2")),
            (
                "scn-03.generation-path",
                _string("CAP-G01_GENERATOR_COORDINATOR_PORT_GUARD_CANDIDATE"),
            ),
            (
                "scn-03.expected.generation-path",
                _string("CAP-G01_GENERATOR_COORDINATOR_PORT_GUARD_CANDIDATE"),
            ),
            (
                "scn-03.required-sections",
                _sequence(prepared_input.expected_sections),
            ),
            (
                "scn-03.expected.required-sections",
                _sequence(prepared_input.expected_sections),
            ),
            ("scn-03.authority-smuggling", _string(authority_summary)),
            ("scn-03.expected.authority-marker", _string("validated")),
            ("scn-03.expected.gate-marker", _string("promoted")),
        )
        return witness, _snapshot(values)

    def _execute_scn04(
        self,
        prepared_input: DPreparedInput,
        fixture: DFixtureHandle,
    ) -> tuple[DScenarioWitness, EvaluationObservationSnapshot]:
        if self._evidence_agent is None:
            raise RuntimeError("SCN-04 requires the real C1 SQLite evidence path")
        plan = compile_d_plan(prepared_input.case_code)
        source_before = fixture.fixture.sources
        evidence_set, evidence_raw = _build_real_tva_evidence(self._evidence_agent)
        self.raw_texts.extend(evidence_raw)
        evidence_refs = tuple(item.evidence_id for item in evidence_set.evidence_items)
        if not evidence_refs:
            raise RuntimeError("SCN-04 TVA evidence resolved no materialized item")
        generation = self._generate(
            case_code="SCN-04",
            plan=plan,
            level=prepared_input.level,
            expected_sections=prepared_input.expected_sections,
            capability_id=CapabilityId("CAP-G02"),
            production_kind="transformed_resource",
            evidence_refs=evidence_refs,
            target_ref=SCN04_TARGET_REF,
        )
        events = ("AG-02:CAP-E01", "AG-03:CAP-G02")
        lineage = generation.candidate.lineage
        lineage_valid = (
            lineage.get("capability_id") == "CAP-G02"
            and lineage.get("generation_operation") == GenerationOperation.TRANSFORM.value
            and lineage.get("target_ref") == SCN04_TARGET_REF
            and bool(generation.candidate.evidence_refs_used)
            and set(generation.candidate.evidence_refs_used).issubset(evidence_refs)
            and generation.candidate.validation_state
            is ProductionValidationState.CANDIDATE
        )
        source_unchanged = fixture.fixture.sources == source_before
        witness = DScenarioWitness(
            plan,
            events,
            generation,
            evidence_set=evidence_set,
            source_unchanged=source_unchanged,
        )
        values = (
            ("scn-04.workflow", _string("WF-4")),
            ("scn-04.expected.workflow", _string("WF-4")),
            ("scn-04.evidence-generation-order", _sequence(events)),
            ("scn-04.expected.evidence-generation-order", _sequence(events)),
            (
                "scn-04.transformation-lineage",
                _boolean(lineage_valid and source_unchanged),
            ),
        )
        return witness, _snapshot(values)

    def _execute_scn05(
        self, prepared_input: DPreparedInput
    ) -> tuple[DScenarioWitness, EvaluationObservationSnapshot]:
        plan = compile_d_plan(prepared_input.case_code)
        generation = self._generate(
            case_code="SCN-05",
            plan=plan,
            level=prepared_input.level,
            expected_sections=prepared_input.expected_sections,
            capability_id=CapabilityId("CAP-G01"),
            production_kind="exercise",
            evidence_refs=(),
            target_ref=None,
        )
        events = ["AG-03:CAP-G01"]
        review = self._review_candidate(generation.candidate)
        events.extend(("AG-04:CAP-V01", "review-complete"))
        gate = run_human_gate_sequence(
            GateDecisionValue.APPROVED,
            initial_events=events,
        )
        generation_review_order = ("AG-03:CAP-G01", "AG-04:CAP-V01")
        gate_order_valid = gate.events[-4:] == (
            "review-complete",
            "gate-request",
            "external-APPROVED",
            "continuation",
        )
        review_performed = (
            len(self._review_port.calls) == 1
            and review.meta.status is ReviewStatus.COMPLETED
            and review.overall_assessment
            in {
                OverallAssessment.ACCEPTABLE,
                OverallAssessment.ACCEPTABLE_WITH_RESERVATIONS,
            }
            and review.correction_required is False
        )
        witness = DScenarioWitness(
            plan,
            gate.events,
            generation,
            review=review,
            review_port_call_count=len(self._review_port.calls),
            gate=gate.resolution,
            continuation_count=gate.continuation_count,
        )
        values = (
            ("scn-05.workflow", _string("WF-5+WF-10")),
            ("scn-05.expected.workflow", _string("WF-5+WF-10")),
            ("scn-05.generation-review-order", _sequence(generation_review_order)),
            (
                "scn-05.expected.generation-review-order",
                _sequence(generation_review_order),
            ),
            ("scn-05.gate-before-downstream", _boolean(gate_order_valid)),
            ("scn-05.review-performed", _boolean(review_performed)),
        )
        return witness, _snapshot(values)

    def _generate(
        self,
        *,
        case_code: str,
        plan: Plan,
        level: str,
        expected_sections: tuple[str, ...],
        capability_id: CapabilityId,
        production_kind: str,
        evidence_refs: tuple[str, ...],
        target_ref: str | None,
    ) -> GenerationWitness:
        generation_step = next(
            step
            for step in plan.steps
            if step.capability_id == capability_id
            and step.executor.kind.value == AgentId.AG_03.value
        )
        request = ProductionRequest(
            meta=_invocation_meta(
                case_code, generation_step.step_id, AgentId.AG_03, D_NOW
            ),
            production_kind=production_kind,
            brief=f"Create bounded synthetic pedagogical output for {case_code}",
            output_format="structured",
            pedagogical_context={"level": level},
            constraints={"synthetic": True},
            evidence_refs=evidence_refs,
            target_ref=target_ref,
            expected_sections=expected_sections,
        )
        preparation = GenerationPreparationRequest(
            capability_id,
            request,
            resolved_inputs={"fixture_scope": case_code.casefold()},
            output_contract={"type": "structured_pedagogical_candidate"},
        )
        before = len(self._generation_port.calls)
        if capability_id.value == "CAP-G01":
            prepared, technical = self._generator.generate_production(
                request=preparation
            )
        else:
            prepared, technical = self._generator.transform_production(
                request=preparation
            )
        guard = GenerationOutputGuard().assess(
            request=GenerationGuardRequest(
                prepared,
                technical,
                GenerationGuardPolicy(
                    require_structured_payload=True,
                    required_payload_keys=("sections",),
                    allowed_payload_keys=("sections",),
                    section_container_key="sections",
                ),
            )
        )
        if guard.disposition not in {
            GenerationGuardDisposition.ALLOW,
            GenerationGuardDisposition.ALLOW_WITH_WARNINGS,
        }:
            raise RuntimeError("D generation output guard did not allow materialization")
        candidate = self._generator.build_candidate(
            request=ProductionCandidateBuildRequest(
                canonical_request=request,
                prepared=prepared,
                technical_result=technical,
                guard_assessment=guard,
                result_meta=_generation_result_meta(request),
                production_id=f"production-candidate:{case_code.casefold()}",
            )
        )
        if technical.content is not None:
            self.raw_texts.append(technical.content)
        sections = technical.structured_payload.get("sections")
        if isinstance(sections, Mapping):
            self.raw_texts.extend(
                value for value in sections.values() if isinstance(value, str)
            )
        return GenerationWitness(
            request,
            candidate,
            guard,
            len(self._generation_port.calls) - before,
        )

    def _review_candidate(self, candidate: ProductionCandidate) -> ReviewResult:
        target_ref = ObjectVersionRef(
            TypedEntityRef(TypedEntityId("production", candidate.production_id)),
            VersionRef("candidate-v1"),
        )
        request = ReviewRequest(
            meta=_invocation_meta("SCN-05", "scn-05-review", AgentId.AG_04, D_NOW),
            target_production_ref=target_ref,
            review_dimensions=(
                ReviewDimension.PEDAGOGY,
                ReviewDimension.INSTRUCTION,
                ReviewDimension.STRUCTURE,
            ),
            criteria={"candidate_only": True},
            evidence_refs=(),
            severity_policy={"blocking": "reject"},
            context_slice={"scenario": "SCN-05"},
            independence_requirements={"separate_from_generation": True},
        )
        prepared, technical = self._reviewer.semantic_review(
            request=ReviewPreparationRequest(
                CapabilityId("CAP-V01"),
                request,
                ResolvedReviewTarget(
                    target_ref,
                    content=candidate.content,
                    structured_payload=candidate.structured_payload,
                ),
                resolved_inputs={"candidate_version": "candidate-v1"},
                output_contract={"type": "semantic_review"},
            )
        )
        return self._reviewer.build_review_result(
            request=ReviewResultMaterializationRequest(
                prepared=prepared,
                technical_result=technical,
                result_meta=ContractMeta(
                    AGENT_CONTRACT_SCHEMA_V1_0,
                    request.meta.run_id,
                    request.meta.step_id,
                    request.meta.parent_step_id,
                    request.meta.correlation_id,
                    D_LATER,
                    ActorRef(ActorKind.AGENT, AgentId.AG_04.value),
                    ReviewStatus.COMPLETED,
                ),
                review_id="review:scn-05",
            )
        )


def build_d_executor(evidence_agent: EvidenceAgent | None) -> DGenerationTargetExecutor:
    generation_results = {
        "scn-03-generate": _generation_result(
            "scn-03-generate",
            GenerationOperation.GENERATE,
            ("objective", "concept", "example", "summary"),
        ),
        "scn-04-generate": _generation_result(
            "scn-04-generate",
            GenerationOperation.TRANSFORM,
            ("context", "concept", "example", "summary"),
            evidence_refs=("evidence-scn04-1",),
        ),
        "scn-05-generate": _generation_result(
            "scn-05-generate",
            GenerationOperation.GENERATE,
            ("context", "questions", "correction-link"),
        ),
    }
    review_result = ReviewPortResult(
        source_step_id="scn-05-review",
        operation=ReviewOperation.SEMANTIC_REVIEW,
        status=ReviewPortResultStatus.SUCCEEDED,
        structured_payload={
            "overall_assessment": OverallAssessment.ACCEPTABLE.value,
            "correction_required": False,
            "coverage": (
                ReviewDimension.PEDAGOGY.value,
                ReviewDimension.INSTRUCTION.value,
                ReviewDimension.STRUCTURE.value,
            ),
            "confidence": {"level": "high"},
        },
        technical_findings=(),
        evidence_refs_used=(),
    )
    return DGenerationTargetExecutor(
        RecordingGenerationPort(generation_results),
        RecordingReviewPort(result=review_result),
        evidence_agent,
    )


def compile_d_plan(case_code: EvaluationCaseCode) -> Plan:
    bindings: tuple[PlanStepBinding, ...]
    if case_code == EvaluationCaseCode("SCN-03"):
        requirements = WorkflowRequirements(production_required=True)
        bindings = (
            _binding(
                WorkflowResponsibility.GENERATE_TRANSFORM,
                "scn-03-generate",
                "CAP-G01",
            ),
        )
        human_gate = None
    elif case_code == EvaluationCaseCode("SCN-04"):
        requirements = WorkflowRequirements(
            external_evidence_required=True,
            production_required=True,
        )
        bindings = (
            _binding(WorkflowResponsibility.EVIDENCE, "scn-04-evidence", "CAP-E01"),
            _binding(
                WorkflowResponsibility.GENERATE_TRANSFORM,
                "scn-04-generate",
                "CAP-G02",
            ),
        )
        human_gate = None
    elif case_code == EvaluationCaseCode("SCN-05"):
        requirements = WorkflowRequirements(
            production_required=True,
            independent_review_required=True,
            human_gate_required=True,
        )
        bindings = (
            _binding(
                WorkflowResponsibility.GENERATE_TRANSFORM,
                "scn-05-generate",
                "CAP-G01",
            ),
            _binding(WorkflowResponsibility.REVIEW, "scn-05-review", "CAP-V01"),
        )
        human_gate = HumanGateBinding(
            step_id="scn-05-gate",
            objective="Require an external human decision after review",
            anchor=HumanGateAnchor.AFTER_REVIEW,
            success_criteria={"external_decision_recorded": True},
            failure_policy=FailurePolicy.STOP,
            output_contract={"type": "gate_resolution"},
        )
    else:
        raise ValueError("unsupported D scenario")
    selection = WorkflowSelector().select(requirements)
    if selection.status is not WorkflowSelectionStatus.SELECTED:
        raise RuntimeError("D workflow selection did not produce a plan")
    return PlanCompiler().compile(
        PlanCompilationRequest(
            selection=selection,
            plan_id=f"plan-{case_code.value.casefold()}",
            run_id=f"run-{case_code.value.casefold()}",
            plan_version=1,
            objective=f"Execute canonical {case_code.value}",
            success_criteria={"hard_assertions": True},
            stop_conditions={"on_failure": "stop"},
            bindings=bindings,
            human_gate=human_gate,
        )
    )


def run_human_gate_sequence(
    decision_value: GateDecisionValue,
    *,
    initial_events: list[str] | None = None,
) -> GateSequenceWitness:
    events = list(initial_events or ["review-complete"])
    request = GateRequest(
        meta=ContractMeta(
            AGENT_CONTRACT_SCHEMA_V1_0,
            "run-scn-05",
            "scn-05-gate",
            "scn-05-review",
            CorrelationId("corr-scn-05"),
            D_LATER,
            ActorRef(ActorKind.AGENT, AgentId.AG_01.value),
            GateStatus.PENDING,
        ),
        gate_id="gate-scn-05-human",
        gate_type="human_exercise_approval",
        reason="Reviewed exercise requires an external human decision",
        options=({"id": "approve"}, {"id": "reject"}),
        required_actor=ActorRef(ActorKind.USER, "user-scn-05"),
        context_summary={"candidate_ref": "production-candidate:scn-05"},
        expires_at=None,
    )
    selected: dict[str, object] | None
    if decision_value is GateDecisionValue.APPROVED:
        selected = {"id": "approve"}
    elif decision_value is GateDecisionValue.REJECTED:
        selected = {"id": "reject"}
    else:
        selected = None
    decision = make_gate_decision(
        request,
        value=decision_value,
        decided_at=D_GATE_NOW,
        selected_option=selected,
        decision_ref=f"gate-decision:scn-05:{decision_value.value}",
    )
    source = RecordingGateDecisionSource(decision)
    events.append("gate-request")
    resolution = GateEngine(BASELINE_GATE_AUTHORITY_POLICY, source).evaluate(
        request=request,
        now=D_GATE_NOW,
    )
    events.append(f"external-{resolution.disposition.value}")
    continuation = RecordingContinuation(events)
    if resolution.disposition is GateResolutionDisposition.APPROVED:
        continuation.continue_after_gate()
    return GateSequenceWitness(
        resolution,
        decision.request,
        source.calls[0],
        tuple(events),
        len(source.calls),
        continuation.calls,
    )


def _binding(
    responsibility: WorkflowResponsibility,
    step_id: str,
    capability_id: str,
) -> PlanStepBinding:
    return PlanStepBinding(
        stage_index=0,
        responsibility=responsibility,
        step_id=step_id,
        objective=f"Execute {responsibility.value}",
        capability_id=CapabilityId(capability_id),
        permission_scope_ref=f"scope:{step_id}",
        success_criteria={"completed": True},
        output_contract={"type": responsibility.value.casefold()},
    )


def _generation_result(
    source_step_id: str,
    operation: GenerationOperation,
    sections: tuple[str, ...],
    *,
    evidence_refs: tuple[str, ...] = (),
) -> GenerationPortResult:
    return GenerationPortResult(
        source_step_id=source_step_id,
        operation=operation,
        status=GenerationPortResultStatus.SUCCEEDED,
        content=f"Synthetic bounded output for {source_step_id}.",
        structured_payload={
            "sections": {
                section: f"Synthetic {section} section for {source_step_id}."
                for section in sections
            }
        },
        evidence_refs_used=evidence_refs,
        execution_metadata={"port_mode": "deterministic_test"},
    )


def _build_real_tva_evidence(
    agent: EvidenceAgent,
) -> tuple[EvidenceSet, tuple[str, ...]]:
    request = EvidenceRequest(
        meta=_invocation_meta("SCN-04", "scn-04-evidence", AgentId.AG_02, D_NOW),
        search_goal=SCN04_EVIDENCE_QUERY,
        scope={"level": "bts-cg-1", "topic": "tva"},
        source_policy={"kinds": ("canonical",)},
        filters={"active": True},
        required_authority=None,
        max_items=2,
    )
    retrieval = agent.search_evidence(request=request)
    materialized = tuple(
        agent.fetch_evidence_item(
            request=EvidenceFetchRequest(
                evidence_id=f"evidence-scn04-{candidate.technical_rank}",
                request=request,
                retrieval=retrieval,
                candidate=candidate,
            )
        )
        for candidate in retrieval.ranked_candidates
    )
    coverage = agent.assess_evidence_coverage(
        retrieval=retrieval,
        materialized=materialized,
    )
    status = (
        AgentResultStatus.PARTIAL
        if coverage.status is EvidenceCoverageStatus.PARTIAL
        else AgentResultStatus.SUCCEEDED
    )
    evidence_set = agent.build_evidence_set(
        build_request=EvidenceSetBuildRequest(
            request=request,
            result_meta=ContractMeta(
                AGENT_CONTRACT_SCHEMA_V1_0,
                request.meta.run_id,
                request.meta.step_id,
                request.meta.parent_step_id,
                request.meta.correlation_id,
                D_LATER,
                ActorRef(ActorKind.AGENT, AgentId.AG_02.value),
                status,
            ),
            retrieval=retrieval,
            materialized=materialized,
        )
    )
    raw = tuple(
        item.item.excerpt_or_summary or "" for item in materialized
    )
    return evidence_set, raw


def _invocation_meta(
    case_code: str,
    step_id: str,
    agent_id: AgentId,
    created_at: Instant,
) -> ContractMeta[InvocationStatus]:
    suffix = case_code.casefold()
    return ContractMeta(
        AGENT_CONTRACT_SCHEMA_V1_0,
        f"run-{suffix}",
        step_id,
        None,
        CorrelationId(f"corr-{suffix}"),
        created_at,
        ActorRef(ActorKind.AGENT, agent_id.value),
        InvocationStatus.PLANNED,
    )


def _generation_result_meta(
    request: ProductionRequest,
) -> ContractMeta[AgentResultStatus]:
    return ContractMeta(
        AGENT_CONTRACT_SCHEMA_V1_0,
        request.meta.run_id,
        request.meta.step_id,
        request.meta.parent_step_id,
        request.meta.correlation_id,
        D_LATER,
        ActorRef(ActorKind.AGENT, AgentId.AG_03.value),
        AgentResultStatus.SUCCEEDED,
    )


def _snapshot(
    values: tuple[
        tuple[str, ObservationScalar | ObservationSequence], ...
    ],
) -> EvaluationObservationSnapshot:
    return EvaluationObservationSnapshot(
        tuple(
            EvaluationObservationSnapshotEntry(EvaluationObservationRef(ref), value)
            for ref, value in values
        )
    )


def _sequence(values: tuple[str, ...]) -> ObservationSequence:
    return ObservationSequence(tuple(_string(value) for value in values))


def _string(value: str) -> ObservationScalar:
    return ObservationScalar(ObservationScalarKind.STRING, value)


def _boolean(value: bool) -> ObservationScalar:
    return ObservationScalar(ObservationScalarKind.BOOLEAN, value)
