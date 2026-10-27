"""AG-01 native plans. No provider client, credential, grant or alternate ledger."""
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from hashlib import sha256
from secrets import token_hex

from backend.adapters.outbound.generation.p0_codesign_agents import (
    CoDesignGenerator,
    correction_request,
)
from backend.agent_runtime.agents.evidence.evidence_agent import EvidenceAgent
from backend.agent_runtime.agents.evidence.evidence_agent_model import EvidenceFetchRequest
from backend.agent_runtime.contracts import BudgetSpec, StepSpec
from backend.agent_runtime.contracts.common import require_contract_ref
from backend.agent_runtime.contracts.evidence import EvidenceRequest
from backend.agent_runtime.orchestration.compilation import (
    PlanCompilationRequest,
    PlanCompiler,
    PlanStepBinding,
)
from backend.agent_runtime.orchestration.coordination.completion import (
    CompletionDisposition,
    WorkflowCompletionDecision,
)
from backend.agent_runtime.orchestration.coordination.coordinator import OrchestrationCoordinator
from backend.agent_runtime.orchestration.coordination.model import CoordinationAction
from backend.agent_runtime.orchestration.selection import WorkflowRequirements, WorkflowSelector
from backend.agent_runtime.orchestration.workflows import (
    BASELINE_WORKFLOW_CATALOG,
    WorkflowResponsibility,
)
from backend.agent_runtime.runtime.execution.executor import PlanExecutor
from backend.agent_runtime.runtime.execution.prelaunch import PreLaunchGuard
from backend.agent_runtime.runtime.execution.runner import StepExecutionResult
from backend.agent_runtime.runtime.planning import Plan
from backend.agent_runtime.runtime.scheduling import DeterministicScheduler
from backend.agent_runtime.runtime.state import RunState, StepRuntimeStatus, initialize_run_state
from backend.core_contracts.capability import CapabilityId
from backend.infrastructure.composition.bindings.r3_agents import operation_meta
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    as_plain,
    fingerprint,
    items,
    object_data,
)
from backend.modules.pedagogical_design.contracts.dto.p0_production import P0Production
from backend.modules.quality_evaluation.ports.outbound.p0_review import P0ReviewPort
from backend.modules.work_orchestration.contracts.dto.operation_identity import OperationIdentity
from backend.modules.work_orchestration.ports.outbound.p0_codesign import P0CoDesignInterrupted
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant

R = WorkflowResponsibility
_CAP = {R.EVIDENCE: "CAP-E01", R.GENERATE_TRANSFORM: "CAP-G02", R.REVIEW: "CAP-V01",
        R.DETERMINISTIC_VALIDATION: "CAP-A01", R.CORRECTION: "CAP-G03"}


class NativeCoDesign:
    def __init__(self, *, generator: CoDesignGenerator, reviewer: P0ReviewPort,
                 evidence: EvidenceAgent, guard: PreLaunchGuard, envelope: BudgetSpec,
                 chain_authorize: Callable[[Mapping[str, object]], bool], permission_scope_ref: str) -> None:
        require_contract_ref(permission_scope_ref, "permission_scope_ref")
        self.permission_scope_ref = permission_scope_ref
        self.generator, self.reviewer, self.evidence = generator, reviewer, evidence
        self.guard, self.envelope, self.chain_authorize = guard, envelope, chain_authorize

    def authorize_chain(self, *, request: Mapping[str, object]) -> bool:
        # Native BudgetSpec is declarative, not a spend proof. The injected
        # existing effect owner must authorize the entire cumulative envelope.
        return self.envelope.max_retries == 0 and self.chain_authorize(request)

    def run(self, *, request: Mapping[str, object],
            validate_variant: Callable[[Mapping[str, object]], Mapping[str, object]],
            validate_review: Callable[[Mapping[str, object]], None]) -> Mapping[str, object]:
        if not self.authorize_chain(request=request):
            raise ValueError("P0_CODESIGN_CHAIN_AUTHORITY_REQUIRED")
        session = _Run(self, request, validate_variant, validate_review)
        session.execute(correction=False)
        if session.completion_reason == "P0_BOUNDED_CORRECTION_CANDIDATE":
            # A separate native WF-7, linked to the exact WF-6 result/review.
            # Reusing the same envelope never replenishes its downstream owner.
            session.parent_run = session.runs[-1]["run_id"]
            if not self.chain_authorize({**object_data(as_plain(request)),
                    "correction_parent_sha256": session.current.sha256,
                    "correction_review_sha256": fingerprint(session.report)}):
                raise ValueError("P0_CODESIGN_CORRECTION_AUTHORITY_REQUIRED")
            session.execute(correction=True)
        return {"productions": session.productions, "reports": session.reports,
                "runs": session.runs, "retrieval": session.retrieval, "operations": session.operations,
                "correction": "ONE_BOUNDED_CHILD" if len(session.runs) == 2 else "NOT_REQUIRED",
                "pedagogical_acceptance": "NOT_PERFORMED", "promotion": "NOT_PERFORMED"}


class _Run:
    def __init__(self, owner: NativeCoDesign, request: Mapping[str, object],
                 validate: Callable[[Mapping[str, object]], Mapping[str, object]],
                 validate_review: Callable[[Mapping[str, object]], None]) -> None:
        self.owner, self.request, self.validate = owner, request, validate
        self.current = P0Production(object_data(request["production"]))
        self.source = self.current
        self.evidence = object_data(request["evidence"])
        self.productions: list[dict[str, object]] = []
        self.reports: list[Mapping[str, object]] = []
        self.runs: list[dict[str, object]] = []
        self.retrieval: list[dict[str, object]] = []
        self.report: Mapping[str, object] | None = None
        self.parent_run: object = None
        self.is_correction = False
        self.validate_review = validate_review
        self.completion_reason = "NOT_EVALUATED"
        self.operations: list[dict[str, object]] = []

    def execute(self, *, correction: bool) -> None:
        self.is_correction = correction
        self.run_source = self.current
        selection = WorkflowSelector().select(WorkflowRequirements(
            external_evidence_required=not correction, production_required=not correction,
            independent_review_required=True, deterministic_validation_required=not correction,
            correction_required=correction))
        key = token_hex(16)
        bindings = []
        for index, stage in enumerate(selection.stages):
            descriptor = BASELINE_WORKFLOW_CATALOG.get(stage.workflow_kind)
            for responsibility in (*descriptor.required_responsibilities, *stage.materialized_optional_responsibilities):
                cap = _CAP[responsibility]
                if responsibility is R.GENERATE_TRANSFORM and self.request["direction"] == "AI_TO_V2":
                    cap = "CAP-G01"
                step_id = "step:" + sha256((key + responsibility.value).encode()).hexdigest()[:32]
                bindings.append(PlanStepBinding(index, responsibility, step_id,
                    responsibility.value, CapabilityId(cap), self.owner.permission_scope_ref,
                    budget=self.owner.envelope, output_contract={"contract_id": "P0-CODESIGN-STEP-1.0"}))
        plan = PlanCompiler().compile(PlanCompilationRequest(selection, "plan:" + key, "run:" + key, 1,
            "Bounded pedagogical co-design", {"no_promotion": True}, {"uncertain_effect": "STOP"}, tuple(bindings),
            budget_envelope=self.owner.envelope))
        self.bindings = {binding.step_id: binding.responsibility for binding in bindings}
        state = initialize_run_state(plan, CorrelationId(str(self.request["command_id"])))
        executor = PlanExecutor(DeterministicScheduler(), self.owner.guard, self)
        coordinator = OrchestrationCoordinator(self)
        source_sha = self.current.sha256
        cycles = []
        for _ in range(len(plan.steps) + 1):
            result = executor.execute_cycle(plan=plan, run_state=state, now=Instant(datetime.now(UTC)))
            decision = coordinator.coordinate(plan=plan, cycle=result, now=Instant(datetime.now(UTC)))
            state = decision.run_state
            cycles.append({"launched": list(result.launched_step_ids), "completed": list(result.completed_step_ids),
                           "directives": [directive.code.value for directive in result.directives],
                           "coordination": decision.action.value})
            if decision.action is not CoordinationAction.CONTINUE or not result.launched_step_ids:
                break
        self.runs.append({"run_id": plan.run_id, "workflow_kind": plan.workflow_kind, "parent_run_id": self.parent_run,
            "source_sha256": source_sha, "result_sha256": self.current.sha256,
            "shared_envelope": True, "cycles": cycles, "state": state.status.value,
            "completion_reason": self.completion_reason})
        if decision.action is not CoordinationAction.COMPLETE or any(step.status is not StepRuntimeStatus.SUCCEEDED for step in state.step_states.values()):
            unknown = any("RECONCILIATION_REQUIRED" in cycle["directives"] for cycle in cycles)
            raise P0CoDesignInterrupted(state="OUTCOME_UNKNOWN" if unknown else "BLOCKED",
                trace={"runs": self.runs, "result_sha256": self.current.sha256,
                       "productions": self.productions, "reports": self.reports, "operations": self.operations,
                       "retrieval": self.retrieval, "retry": 0})

    def evaluate(self, *, plan: Plan, run_state: RunState) -> WorkflowCompletionDecision:
        if self.report is None or self.report.get("status") != "completed":
            decision = WorkflowCompletionDecision(CompletionDisposition.STOP_REQUIRED, "P0_REVIEW_INCOMPLETE")
        elif self.report.get("correction_required") is True or any(
                row.get("severity") == "blocking" for row in items(self.report["findings"], 32)):
            decision = WorkflowCompletionDecision(CompletionDisposition.PARTIAL,
                "P0_REVIEW_UNRESOLVED_BOUNDED_STOP" if self.is_correction else "P0_BOUNDED_CORRECTION_CANDIDATE")
        else:
            decision = WorkflowCompletionDecision(CompletionDisposition.SUCCEEDED, "P0_TECHNICAL_CHAIN_COMPLETE_TEACHER_ACCEPTANCE_PENDING")
        self.completion_reason = decision.reason_code
        return decision

    def run(self, *, plan: Plan, step: StepSpec, run_state: RunState, attempt: int, now: Instant) -> StepExecutionResult:
        responsibility = self.bindings[step.step_id]
        identity = OperationIdentity(plan.run_id, step.step_id,
            str(object_data(self.run_source.data["lineage"])["source_step_id"]), str(self.request["command_id"]))
        if responsibility is R.EVIDENCE:
            query = EvidenceRequest(operation_meta(identity, "AG-02"), str(self.request["evidence_query"]), max_items=8)
            found = self.owner.evidence.search_evidence(request=query)
            for number, candidate in enumerate(found.ranked_candidates, 1):
                item = self.owner.evidence.fetch_evidence_item(request=EvidenceFetchRequest(
                    "discovery:" + str(number), query, found, candidate)).item
                self.retrieval.append({"source_ref": str(item.source_ref), "locator": item.locator,
                    "version": str(item.checksum_or_version), "selection": "NOT_ADMITTED_BY_DISCOVERY"})
            # No automatic addition to the exact admitted evidence supplied by M08.
        elif responsibility in {R.GENERATE_TRANSFORM, R.CORRECTION}:
            correction = correction_request(self.current, self.report or {}, identity) if self.is_correction else None
            before = self.current
            self.current, operation_proof = self.owner.generator.propose(parent=self.current, evidence=self.evidence,
                objective=str(self.request["objective"]), direction=str(self.request["direction"]),
                identity=identity, correction=correction)
            # Guard before the next semantic effect, including WF-7 optional review.
            self.validate(self.current.mutable_copy())
            self.productions.append(self.current.mutable_copy())
            self.operations.append({"run_id": plan.run_id, "step_id": step.step_id,
                "request_id": "req:" + str(self.request["command_id"]), "capability": step.capability_id.value if step.capability_id else "NONE",
                "parent_version_ref": before.version_ref, "version_ref": self.current.version_ref,
                "bundle_sha256": self.current.sha256, "correction": as_plain(operation_proof["correction"]),
                "controls": as_plain(operation_proof["controls"])})
        elif responsibility is R.DETERMINISTIC_VALIDATION:
            self.validate(self.current.mutable_copy())
        elif responsibility is R.REVIEW:
            review_request = {"contract_id": "P0-INDEPENDENT-REVIEW-REQUEST-1.1",
                "operation_identity": identity.as_dict(), "production": self.current.mutable_copy(),
                "bundle_sha256": self.current.sha256, "plan": as_plain(self.request["plan"]),
                "evidence_pack": as_plain(self.request["evidence_pack"]),
                "validation": self.validate(self.current.mutable_copy())}
            if not self.owner.reviewer.authorize(request=review_request):
                raise ValueError("P0_CODESIGN_REVIEW_AUTHORITY_REQUIRED")
            self.report = self.owner.reviewer.review(request=review_request)
            self.validate_review(self.report)
            self.reports.append(self.report)
        return StepExecutionResult(StepRuntimeStatus.SUCCEEDED, ("artifact:" + self.current.sha256,))
