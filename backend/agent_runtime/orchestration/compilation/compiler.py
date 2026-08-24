from __future__ import annotations

from dataclasses import dataclass, replace

from backend.agent_runtime.contracts import (
    ExecutorKind,
    ExecutorRef,
    StepKind,
    StepSpec,
)
from backend.agent_runtime.orchestration.compilation.model import (
    HumanGateAnchor,
    HumanGateBinding,
    PlanCompilationCode,
    PlanCompilationError,
    PlanCompilationRequest,
    PlanStepBinding,
)
from backend.agent_runtime.orchestration.selection import WorkflowSelectionStatus
from backend.agent_runtime.orchestration.workflows import (
    BASELINE_WORKFLOW_CATALOG,
    BASELINE_WORKFLOW_RESPONSIBILITY_DESCRIPTORS,
    WorkflowCatalog,
    WorkflowKind,
    WorkflowResponsibility,
    WorkflowTopologyDescriptor,
)
from backend.agent_runtime.registry import (
    BASELINE_CAPABILITY_REGISTRY,
    CapabilityRegistry,
)
from backend.agent_runtime.runtime import Plan, PlanValidator
from backend.core_contracts.capability import CapabilityId

R = WorkflowResponsibility
Code = PlanCompilationCode

_CAP_A01 = CapabilityId("CAP-A01")
_CAP_A02 = CapabilityId("CAP-A02")
_CAP_G03 = CapabilityId("CAP-G03")
_CAP_O04 = CapabilityId("CAP-O04")
_CAP_O05 = CapabilityId("CAP-O05")

_STEP_SHAPES = {
    R.DIRECT_APPLICATION: (StepKind.USE_CASE, ExecutorKind.APPLICATION),
    R.EVIDENCE: (StepKind.AGENT, ExecutorKind.AG_02),
    R.GENERATE_TRANSFORM: (StepKind.AGENT, ExecutorKind.AG_03),
    R.REVIEW: (StepKind.AGENT, ExecutorKind.AG_04),
    R.DETERMINISTIC_VALIDATION: (StepKind.USE_CASE, ExecutorKind.APPLICATION),
    R.CORRECTION: (StepKind.AGENT, ExecutorKind.AG_03),
    R.EVIDENCE_JOIN: (StepKind.JOIN, ExecutorKind.RUNTIME),
    R.VARIANT_GENERATION: (StepKind.AGENT, ExecutorKind.AG_03),
    R.VARIANT_JOIN: (StepKind.JOIN, ExecutorKind.RUNTIME),
    R.VARIANT_SELECTION: (StepKind.DECISION, ExecutorKind.RUNTIME),
    R.GATE: (StepKind.GATE, ExecutorKind.RUNTIME),
    R.PROMOTION: (StepKind.USE_CASE, ExecutorKind.APPLICATION),
}

_EXACT_CAPABILITIES = {
    R.DETERMINISTIC_VALIDATION: _CAP_A01,
    R.CORRECTION: _CAP_G03,
    R.PROMOTION: _CAP_A02,
}

_COMPILER_CAPABILITIES = {
    R.EVIDENCE_JOIN: _CAP_O04,
    R.VARIANT_JOIN: _CAP_O04,
    R.GATE: _CAP_O05,
}


@dataclass(frozen=True, slots=True)
class _StageGraph:
    steps: tuple[StepSpec, ...]
    roots: tuple[str, ...]
    terminals: tuple[str, ...]
    responsibilities: tuple[tuple[str, WorkflowResponsibility], ...]


@dataclass(frozen=True, slots=True)
class PlanCompiler:
    workflow_catalog: WorkflowCatalog = BASELINE_WORKFLOW_CATALOG
    capability_registry: CapabilityRegistry = BASELINE_CAPABILITY_REGISTRY
    validator: PlanValidator = PlanValidator()

    def __post_init__(self) -> None:
        if not isinstance(self.workflow_catalog, WorkflowCatalog):
            raise TypeError("workflow_catalog must be a WorkflowCatalog")
        if not isinstance(self.capability_registry, CapabilityRegistry):
            raise TypeError("capability_registry must be a CapabilityRegistry")
        if not isinstance(self.validator, PlanValidator):
            raise TypeError("validator must be a PlanValidator")

    def compile(self, request: PlanCompilationRequest) -> Plan:
        if not isinstance(request, PlanCompilationRequest):
            raise TypeError("request must be a PlanCompilationRequest")
        if request.selection.status is WorkflowSelectionStatus.WAITING_HUMAN:
            raise PlanCompilationError(
                Code.WAITING_HUMAN_NOT_COMPILABLE,
                "a waiting-human selection cannot be compiled",
            )
        self._validate_human_gate_binding(request)

        bindings_by_stage = self._bindings_by_stage(request)
        compiled_steps: list[StepSpec] = []
        responsibility_by_step: dict[str, WorkflowResponsibility] = {}
        stage_step_ids: list[tuple[WorkflowKind, tuple[str, ...]]] = []
        previous_terminals: tuple[str, ...] = ()

        for stage_index, stage in enumerate(request.selection.stages):
            handoff = (
                stage_index > 0
                and request.selection.stages[stage_index - 1].workflow_kind
                is WorkflowKind.WF_8
                and stage.workflow_kind in (WorkflowKind.WF_4, WorkflowKind.WF_6)
            )
            graph = self._compile_stage(
                request,
                stage_index,
                bindings_by_stage[stage_index],
                handoff,
            )
            graph = self._connect_to_previous(graph, previous_terminals)
            compiled_steps.extend(graph.steps)
            responsibility_by_step.update(graph.responsibilities)
            stage_step_ids.append(
                (stage.workflow_kind, tuple(step.step_id for step in graph.steps))
            )
            previous_terminals = graph.terminals

        if request.human_gate is not None:
            compiled_steps = self._insert_human_gate(
                compiled_steps,
                responsibility_by_step,
                stage_step_ids,
                request.human_gate,
            )

        plan = Plan(
            plan_id=request.plan_id,
            run_id=request.run_id,
            plan_version=request.plan_version,
            objective=request.objective,
            success_criteria=request.success_criteria,
            workflow_kind=self._workflow_kind(request),
            steps=tuple(compiled_steps),
            gate_refs=request.gate_refs,
            budget_envelope=request.budget_envelope,
            risk_profile=request.risk_profile,
            assumptions=request.assumptions,
            stop_conditions=request.stop_conditions,
        )
        validation = self.validator.validate(plan)
        if not validation.valid:
            codes = sorted({issue.code.value for issue in validation.issues})
            raise PlanCompilationError(
                Code.PLAN_VALIDATION_FAILED,
                "plan validation failed: " + ", ".join(codes),
            )
        return plan

    @staticmethod
    def _validate_human_gate_binding(request: PlanCompilationRequest) -> None:
        has_overlay = request.selection.overlays == (WorkflowKind.WF_10,)
        if has_overlay and request.human_gate is None:
            raise PlanCompilationError(
                Code.HUMAN_GATE_BINDING_REQUIRED,
                "the WF-10 overlay requires a human gate binding",
            )
        if not has_overlay and request.human_gate is not None:
            raise PlanCompilationError(
                Code.HUMAN_GATE_BINDING_FORBIDDEN,
                "a human gate binding requires the WF-10 overlay",
            )

    @staticmethod
    def _bindings_by_stage(
        request: PlanCompilationRequest,
    ) -> tuple[tuple[PlanStepBinding, ...], ...]:
        groups: list[list[PlanStepBinding]] = [
            [] for _ in request.selection.stages
        ]
        for binding in request.bindings:
            groups[binding.stage_index].append(binding)
        return tuple(tuple(group) for group in groups)

    def _compile_stage(
        self,
        request: PlanCompilationRequest,
        stage_index: int,
        bindings: tuple[PlanStepBinding, ...],
        evidence_handoff: bool,
    ) -> _StageGraph:
        stage = request.selection.stages[stage_index]
        if stage.workflow_kind is WorkflowKind.WF_10:
            raise PlanCompilationError(
                Code.UNEXPECTED_STAGE_BINDING,
                "WF-10 is an overlay and cannot be compiled as a stage",
            )
        descriptor = self._workflow_descriptor(stage.workflow_kind)
        if any(
            responsibility not in descriptor.optional_responsibilities
            for responsibility in stage.materialized_optional_responsibilities
        ):
            raise PlanCompilationError(
                Code.UNEXPECTED_STAGE_BINDING,
                f"stage optional responsibilities are incompatible with {stage.workflow_kind.value}",
            )
        expected = list(descriptor.required_responsibilities)
        expected.extend(stage.materialized_optional_responsibilities)
        if evidence_handoff:
            if R.EVIDENCE not in expected:
                raise PlanCompilationError(
                    Code.UNEXPECTED_STAGE_BINDING,
                    "the evidence handoff requires an evidence continuation",
                )
            expected.remove(R.EVIDENCE)
        self._validate_stage_bindings(
            stage.workflow_kind,
            descriptor,
            tuple(expected),
            bindings,
        )
        by_responsibility = {
            responsibility: tuple(
                binding
                for binding in bindings
                if binding.responsibility is responsibility
            )
            for responsibility in expected
        }
        return self._materialize_stage(
            request.plan_id,
            stage_index,
            stage.workflow_kind,
            tuple(expected),
            bindings,
            by_responsibility,
        )

    def _workflow_descriptor(
        self, workflow_kind: WorkflowKind
    ) -> WorkflowTopologyDescriptor:
        try:
            return self.workflow_catalog.get(workflow_kind)
        except LookupError as error:
            raise PlanCompilationError(
                Code.UNEXPECTED_STAGE_BINDING,
                f"workflow catalog is missing {workflow_kind.value}",
            ) from error

    def _validate_stage_bindings(
        self,
        workflow_kind: WorkflowKind,
        descriptor: WorkflowTopologyDescriptor,
        expected: tuple[WorkflowResponsibility, ...],
        bindings: tuple[PlanStepBinding, ...],
    ) -> None:
        expected_set = set(expected)
        if any(binding.responsibility not in expected_set for binding in bindings):
            raise PlanCompilationError(
                Code.UNEXPECTED_STAGE_BINDING,
                f"stage bindings contain an undeclared responsibility for {workflow_kind.value}",
            )
        counts = {
            responsibility: sum(
                binding.responsibility is responsibility for binding in bindings
            )
            for responsibility in expected
        }
        if workflow_kind is WorkflowKind.WF_0:
            if counts.get(R.DIRECT_APPLICATION, 0) < 1:
                raise PlanCompilationError(
                    Code.MISSING_STAGE_BINDING,
                    "WF-0 requires at least one direct Application binding",
                )
        elif workflow_kind is WorkflowKind.WF_8:
            self._validate_parallel_count(
                counts.get(R.EVIDENCE, 0), descriptor.min_parallel_branches, "WF-8"
            )
            self._require_exactly_one(counts, R.EVIDENCE_JOIN, workflow_kind)
        elif workflow_kind is WorkflowKind.WF_9:
            self._validate_parallel_count(
                counts.get(R.VARIANT_GENERATION, 0),
                descriptor.min_parallel_branches,
                "WF-9",
            )
            self._require_exactly_one(counts, R.VARIANT_JOIN, workflow_kind)
            self._require_exactly_one(counts, R.VARIANT_SELECTION, workflow_kind)
        else:
            for responsibility in expected:
                self._require_exactly_one(counts, responsibility, workflow_kind)
        self._validate_branch_indexes(workflow_kind, bindings)

    @staticmethod
    def _validate_parallel_count(actual: int, minimum: int, label: str) -> None:
        if actual < minimum:
            raise PlanCompilationError(
                Code.INVALID_BRANCH_CARDINALITY,
                f"{label} requires at least {minimum} parallel branches",
            )

    @staticmethod
    def _require_exactly_one(
        counts: dict[WorkflowResponsibility, int],
        responsibility: WorkflowResponsibility,
        workflow_kind: WorkflowKind,
    ) -> None:
        actual = counts.get(responsibility, 0)
        if actual == 0:
            raise PlanCompilationError(
                Code.MISSING_STAGE_BINDING,
                f"{workflow_kind.value} is missing responsibility {responsibility.value}",
            )
        if actual != 1:
            raise PlanCompilationError(
                Code.UNEXPECTED_STAGE_BINDING,
                f"{workflow_kind.value} requires one binding for {responsibility.value}",
            )

    @staticmethod
    def _validate_branch_indexes(
        workflow_kind: WorkflowKind, bindings: tuple[PlanStepBinding, ...]
    ) -> None:
        branch_responsibility = {
            WorkflowKind.WF_8: R.EVIDENCE,
            WorkflowKind.WF_9: R.VARIANT_GENERATION,
        }.get(workflow_kind)
        if branch_responsibility is None:
            if any(binding.branch_index is not None for binding in bindings):
                raise PlanCompilationError(
                    Code.INVALID_BRANCH_INDEX,
                    "branch_index is allowed only for WF-8 and WF-9 branches",
                )
            return
        branches = [
            binding
            for binding in bindings
            if binding.responsibility is branch_responsibility
        ]
        indexes = [binding.branch_index for binding in branches]
        if any(index is None for index in indexes):
            raise PlanCompilationError(
                Code.INVALID_BRANCH_INDEX,
                "parallel branch bindings require branch_index",
            )
        concrete_indexes = [index for index in indexes if index is not None]
        if sorted(concrete_indexes) != list(range(len(indexes))):
            raise PlanCompilationError(
                Code.INVALID_BRANCH_INDEX,
                "parallel branch indexes must be contiguous from zero",
            )
        if any(
            binding.branch_index is not None
            for binding in bindings
            if binding.responsibility is not branch_responsibility
        ):
            raise PlanCompilationError(
                Code.INVALID_BRANCH_INDEX,
                "control bindings must not have branch_index",
            )

    def _materialize_stage(
        self,
        plan_id: str,
        stage_index: int,
        workflow_kind: WorkflowKind,
        expected: tuple[WorkflowResponsibility, ...],
        bindings: tuple[PlanStepBinding, ...],
        by_responsibility: dict[
            WorkflowResponsibility, tuple[PlanStepBinding, ...]
        ],
    ) -> _StageGraph:
        if workflow_kind is WorkflowKind.WF_0:
            ordered = tuple(
                binding
                for binding in bindings
                if binding.responsibility is R.DIRECT_APPLICATION
            )
            return self._sequential_graph(ordered)
        if workflow_kind in (WorkflowKind.WF_8, WorkflowKind.WF_9):
            return self._parallel_graph(
                plan_id, stage_index, workflow_kind, by_responsibility
            )
        ordered_responsibilities = expected
        if (
            workflow_kind is WorkflowKind.WF_5
            and R.DETERMINISTIC_VALIDATION in expected
        ):
            ordered_responsibilities = (
                R.GENERATE_TRANSFORM,
                R.DETERMINISTIC_VALIDATION,
                R.REVIEW,
            )
        ordered_bindings = tuple(
            by_responsibility[item][0] for item in ordered_responsibilities
        )
        return self._sequential_graph(ordered_bindings)

    def _sequential_graph(
        self, bindings: tuple[PlanStepBinding, ...]
    ) -> _StageGraph:
        steps: list[StepSpec] = []
        previous: tuple[str, ...] = ()
        responsibilities: list[tuple[str, WorkflowResponsibility]] = []
        for binding in bindings:
            step = self._step(binding, previous, None)
            steps.append(step)
            responsibilities.append((step.step_id, binding.responsibility))
            previous = (step.step_id,)
        return _StageGraph(
            tuple(steps),
            (steps[0].step_id,),
            (steps[-1].step_id,),
            tuple(responsibilities),
        )

    def _parallel_graph(
        self,
        plan_id: str,
        stage_index: int,
        workflow_kind: WorkflowKind,
        by_responsibility: dict[
            WorkflowResponsibility, tuple[PlanStepBinding, ...]
        ],
    ) -> _StageGraph:
        branch_responsibility = (
            R.EVIDENCE
            if workflow_kind is WorkflowKind.WF_8
            else R.VARIANT_GENERATION
        )
        join_responsibility = (
            R.EVIDENCE_JOIN
            if workflow_kind is WorkflowKind.WF_8
            else R.VARIANT_JOIN
        )
        branches = tuple(
            sorted(
                by_responsibility[branch_responsibility],
                key=lambda item: item.branch_index if item.branch_index is not None else -1,
            )
        )
        parallel_group = f"{plan_id}:stage-{stage_index}:{workflow_kind.value}"
        branch_steps = tuple(
            self._step(binding, (), parallel_group) for binding in branches
        )
        join_binding = by_responsibility[join_responsibility][0]
        join = self._step(
            join_binding,
            tuple(step.step_id for step in branch_steps),
            None,
        )
        steps = (*branch_steps, join)
        responsibilities = [
            (step.step_id, branch_responsibility) for step in branch_steps
        ]
        responsibilities.append((join.step_id, join_responsibility))
        terminal = join.step_id
        if workflow_kind is WorkflowKind.WF_9:
            selection_binding = by_responsibility[R.VARIANT_SELECTION][0]
            selection = self._step(selection_binding, (join.step_id,), None)
            steps = (*steps, selection)
            responsibilities.append((selection.step_id, R.VARIANT_SELECTION))
            terminal = selection.step_id
        return _StageGraph(
            steps,
            tuple(step.step_id for step in branch_steps),
            (terminal,),
            tuple(responsibilities),
        )

    def _step(
        self,
        binding: PlanStepBinding,
        depends_on: tuple[str, ...],
        parallel_group: str | None,
    ) -> StepSpec:
        kind, executor_kind = _STEP_SHAPES[binding.responsibility]
        capability_id = self._capability_for(binding, kind)
        self._validate_scope(binding, kind)
        return StepSpec(
            step_id=binding.step_id,
            kind=kind,
            capability_id=capability_id,
            executor=ExecutorRef(executor_kind),
            objective=binding.objective,
            input_refs=binding.input_refs,
            depends_on=depends_on,
            permission_scope_ref=binding.permission_scope_ref,
            budget=binding.budget,
            success_criteria=binding.success_criteria,
            failure_policy=binding.failure_policy,
            output_contract=binding.output_contract,
            parallel_group=parallel_group,
        )

    def _capability_for(
        self, binding: PlanStepBinding, kind: StepKind
    ) -> CapabilityId | None:
        responsibility = binding.responsibility
        if responsibility is R.VARIANT_SELECTION:
            if binding.capability_id is not None:
                self._capability_error(responsibility)
            return None
        exact = _EXACT_CAPABILITIES.get(responsibility)
        derived = _COMPILER_CAPABILITIES.get(responsibility)
        if exact is not None:
            if binding.capability_id is None:
                raise PlanCompilationError(
                    Code.CAPABILITY_REQUIRED,
                    f"{responsibility.value} requires an explicit capability",
                )
            if binding.capability_id != exact:
                self._capability_error(responsibility)
            capability_id = binding.capability_id
        elif derived is not None:
            if binding.capability_id is not None and binding.capability_id != derived:
                self._capability_error(responsibility)
            capability_id = derived
        else:
            if binding.capability_id is None:
                raise PlanCompilationError(
                    Code.CAPABILITY_REQUIRED,
                    f"{responsibility.value} requires an explicit capability",
                )
            capability_id = binding.capability_id
        self._validate_capability_metadata(responsibility, capability_id, kind)
        return capability_id

    def _validate_capability_metadata(
        self,
        responsibility: WorkflowResponsibility,
        capability_id: CapabilityId,
        kind: StepKind,
    ) -> None:
        try:
            capability = self.capability_registry.get(capability_id)
        except LookupError:
            self._capability_error(responsibility)
        ownership = next(
            item
            for item in BASELINE_WORKFLOW_RESPONSIBILITY_DESCRIPTORS
            if item.responsibility is responsibility
        )
        if capability.capability_class not in ownership.allowed_capability_classes:
            self._capability_error(responsibility)
        if capability.owner_agent is not ownership.owner_agent:
            self._capability_error(responsibility)
        expected_kind, _ = _STEP_SHAPES[responsibility]
        if kind is not expected_kind:
            self._capability_error(responsibility)

    @staticmethod
    def _capability_error(responsibility: WorkflowResponsibility) -> None:
        raise PlanCompilationError(
            Code.CAPABILITY_NOT_ALLOWED,
            f"capability is not allowed for {responsibility.value}",
        )

    @staticmethod
    def _validate_scope(binding: PlanStepBinding, kind: StepKind) -> None:
        executable = kind in (StepKind.AGENT, StepKind.USE_CASE, StepKind.TOOL)
        if executable and binding.permission_scope_ref is None:
            raise PlanCompilationError(
                Code.PERMISSION_SCOPE_REQUIRED,
                f"permission_scope_ref is required for {binding.responsibility.value}",
            )
        if not executable and binding.permission_scope_ref is not None:
            raise PlanCompilationError(
                Code.PERMISSION_SCOPE_REQUIRED,
                f"permission_scope_ref is forbidden for {binding.responsibility.value}",
            )

    @staticmethod
    def _connect_to_previous(
        graph: _StageGraph, previous_terminals: tuple[str, ...]
    ) -> _StageGraph:
        if not previous_terminals:
            return graph
        roots = set(graph.roots)
        steps = tuple(
            replace(
                step,
                depends_on=_unique((*step.depends_on, *previous_terminals)),
            )
            if step.step_id in roots
            else step
            for step in graph.steps
        )
        return replace(graph, steps=steps)

    def _insert_human_gate(
        self,
        steps: list[StepSpec],
        responsibility_by_step: dict[str, WorkflowResponsibility],
        stage_step_ids: list[tuple[WorkflowKind, tuple[str, ...]]],
        binding: HumanGateBinding,
    ) -> list[StepSpec]:
        predecessor_ids: tuple[str, ...]
        successor_ids: tuple[str, ...]
        if binding.anchor is HumanGateAnchor.BEFORE_FIRST_STAGE:
            predecessor_ids = ()
            successor_ids = tuple(step.step_id for step in steps if not step.depends_on)
            insert_index = 0
        elif binding.anchor is HumanGateAnchor.AFTER_EVIDENCE:
            anchor_id = self._last_step_for(
                steps,
                responsibility_by_step,
                (R.EVIDENCE_JOIN, R.EVIDENCE),
                binding.anchor,
            )
            predecessor_ids = (anchor_id,)
            successor_ids = self._direct_successors(steps, predecessor_ids)
            insert_index = self._step_index(steps, anchor_id) + 1
        elif binding.anchor is HumanGateAnchor.AFTER_REVIEW:
            anchor_id = self._last_step_for(
                steps,
                responsibility_by_step,
                (R.REVIEW,),
                binding.anchor,
            )
            predecessor_ids = (anchor_id,)
            successor_ids = self._direct_successors(steps, predecessor_ids)
            insert_index = self._step_index(steps, anchor_id) + 1
        else:
            wf11_stages = [ids for kind, ids in stage_step_ids if kind is WorkflowKind.WF_11]
            if not wf11_stages:
                self._anchor_error(binding.anchor)
            entry_id = wf11_stages[-1][0]
            entry = steps[self._step_index(steps, entry_id)]
            predecessor_ids = entry.depends_on
            successor_ids = (entry_id,)
            insert_index = self._step_index(steps, entry_id)

        gate = StepSpec(
            step_id=binding.step_id,
            kind=StepKind.GATE,
            capability_id=_CAP_O05,
            executor=ExecutorRef(ExecutorKind.RUNTIME),
            objective=binding.objective,
            depends_on=predecessor_ids,
            success_criteria=binding.success_criteria,
            failure_policy=binding.failure_policy,
            output_contract=binding.output_contract,
        )
        rewired = [
            self._rewire_successor(step, successor_ids, predecessor_ids, gate.step_id)
            for step in steps
        ]
        rewired.insert(insert_index, gate)
        return rewired

    @staticmethod
    def _last_step_for(
        steps: list[StepSpec],
        responsibility_by_step: dict[str, WorkflowResponsibility],
        responsibilities: tuple[WorkflowResponsibility, ...],
        anchor: HumanGateAnchor,
    ) -> str:
        candidates = [
            step.step_id
            for step in steps
            if responsibility_by_step.get(step.step_id) in responsibilities
        ]
        if not candidates:
            PlanCompiler._anchor_error(anchor)
        return candidates[-1]

    @staticmethod
    def _anchor_error(anchor: HumanGateAnchor) -> None:
        raise PlanCompilationError(
            Code.HUMAN_GATE_ANCHOR_UNAVAILABLE,
            f"human gate anchor {anchor.value} is unavailable",
        )

    @staticmethod
    def _direct_successors(
        steps: list[StepSpec], predecessor_ids: tuple[str, ...]
    ) -> tuple[str, ...]:
        predecessors = set(predecessor_ids)
        return tuple(
            step.step_id for step in steps if predecessors & set(step.depends_on)
        )

    @staticmethod
    def _step_index(steps: list[StepSpec], step_id: str) -> int:
        return next(index for index, step in enumerate(steps) if step.step_id == step_id)

    @staticmethod
    def _rewire_successor(
        step: StepSpec,
        successor_ids: tuple[str, ...],
        predecessor_ids: tuple[str, ...],
        gate_id: str,
    ) -> StepSpec:
        if step.step_id not in successor_ids:
            return step
        predecessors = set(predecessor_ids)
        if predecessors:
            dependencies = _unique(
                tuple(
                    gate_id if dependency in predecessors else dependency
                    for dependency in step.depends_on
                )
            )
        else:
            dependencies = _unique((*step.depends_on, gate_id))
        return replace(step, depends_on=dependencies)

    @staticmethod
    def _workflow_kind(request: PlanCompilationRequest) -> str:
        value = "+".join(
            stage.workflow_kind.value for stage in request.selection.stages
        )
        if request.selection.overlays:
            value += "|overlay:" + "+".join(
                overlay.value for overlay in request.selection.overlays
            )
        return value


def _unique(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))
