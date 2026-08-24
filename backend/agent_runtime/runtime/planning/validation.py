from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import StrEnum

from backend.agent_runtime.contracts import ExecutorKind, StepKind, StepSpec
from backend.agent_runtime.policy import (
    BASELINE_AGENT_RUNTIME_POLICY,
    AgentRuntimePolicy,
    budget_is_narrower_or_equal,
)
from backend.agent_runtime.registry import (
    BASELINE_CAPABILITY_REGISTRY,
    CapabilityExecutionRoute,
    CapabilityRegistry,
)
from backend.agent_runtime.runtime.planning.plan import Plan


class PlanValidationCode(StrEnum):
    DUPLICATE_STEP_ID = "DUPLICATE_STEP_ID"
    STEP_LIMIT_EXCEEDED = "STEP_LIMIT_EXCEEDED"
    UNKNOWN_DEPENDENCY = "UNKNOWN_DEPENDENCY"
    DEPENDENCY_CYCLE = "DEPENDENCY_CYCLE"
    UNKNOWN_CAPABILITY = "UNKNOWN_CAPABILITY"
    KIND_EXECUTOR_MISMATCH = "KIND_EXECUTOR_MISMATCH"
    CAPABILITY_ROUTE_MISMATCH = "CAPABILITY_ROUTE_MISMATCH"
    AGENT_OWNER_MISMATCH = "AGENT_OWNER_MISMATCH"
    PARALLEL_DEPENDENCY_CONFLICT = "PARALLEL_DEPENDENCY_CONFLICT"
    STEP_BUDGET_OUT_OF_ENVELOPE = "STEP_BUDGET_OUT_OF_ENVELOPE"


@dataclass(frozen=True, slots=True)
class PlanValidationIssue:
    code: PlanValidationCode
    message: str
    step_id: str | None = None
    related_step_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.code, PlanValidationCode):
            raise TypeError("code must be a PlanValidationCode")
        if not isinstance(self.message, str) or not self.message.strip():
            raise ValueError("message must be a non-empty string")
        if self.step_id is not None and (
            not isinstance(self.step_id, str) or not self.step_id.strip()
        ):
            raise ValueError("step_id must be a non-empty string or None")
        if not isinstance(self.related_step_ids, tuple):
            raise TypeError("related_step_ids must be a tuple")
        if any(
            not isinstance(item, str) or not item.strip()
            for item in self.related_step_ids
        ):
            raise ValueError("related_step_ids must contain non-empty strings")


@dataclass(frozen=True, slots=True)
class PlanValidationResult:
    valid: bool
    issues: tuple[PlanValidationIssue, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.valid, bool):
            raise TypeError("valid must be a bool")
        if not isinstance(self.issues, tuple):
            raise TypeError("issues must be a tuple")
        if any(not isinstance(issue, PlanValidationIssue) for issue in self.issues):
            raise TypeError("issues must contain PlanValidationIssue values")
        if self.valid is not (len(self.issues) == 0):
            raise ValueError("valid must equal whether issues is empty")


_EXECUTOR_BY_KIND = {
    StepKind.AGENT: frozenset(
        {ExecutorKind.AG_02, ExecutorKind.AG_03, ExecutorKind.AG_04}
    ),
    StepKind.USE_CASE: frozenset({ExecutorKind.APPLICATION}),
    StepKind.TOOL: frozenset({ExecutorKind.UTILITY}),
    StepKind.GATE: frozenset({ExecutorKind.RUNTIME}),
    StepKind.JOIN: frozenset({ExecutorKind.RUNTIME}),
    StepKind.DECISION: frozenset({ExecutorKind.RUNTIME}),
}

_ROUTE_BY_KIND = {
    StepKind.AGENT: CapabilityExecutionRoute.AGENT,
    StepKind.USE_CASE: CapabilityExecutionRoute.APPLICATION,
    StepKind.TOOL: CapabilityExecutionRoute.UTILITY,
    StepKind.GATE: CapabilityExecutionRoute.RUNTIME,
    StepKind.JOIN: CapabilityExecutionRoute.RUNTIME,
    StepKind.DECISION: CapabilityExecutionRoute.RUNTIME,
}

_CAPABILITY_REQUIRED_KINDS = frozenset(
    {StepKind.AGENT, StepKind.USE_CASE, StepKind.TOOL}
)


@dataclass(frozen=True, slots=True)
class PlanValidator:
    capability_registry: CapabilityRegistry = BASELINE_CAPABILITY_REGISTRY
    runtime_policy: AgentRuntimePolicy = BASELINE_AGENT_RUNTIME_POLICY

    def __post_init__(self) -> None:
        if not isinstance(self.capability_registry, CapabilityRegistry):
            raise TypeError("capability_registry must be a CapabilityRegistry")
        if not isinstance(self.runtime_policy, AgentRuntimePolicy):
            raise TypeError("runtime_policy must be an AgentRuntimePolicy")

    def validate(self, plan: Plan) -> PlanValidationResult:
        if not isinstance(plan, Plan):
            raise TypeError("plan must be a Plan")

        issues: list[PlanValidationIssue] = []
        self._validate_cardinality(plan, issues)
        graph = self._dependency_graph(plan)
        self._validate_dependencies(plan, graph, issues)
        self._validate_cycles(graph, issues)
        self._validate_steps(plan, issues)
        self._validate_parallel_groups(plan, graph, issues)
        return PlanValidationResult(valid=not issues, issues=tuple(issues))

    def _validate_cardinality(
        self, plan: Plan, issues: list[PlanValidationIssue]
    ) -> None:
        if len(plan.steps) > self.runtime_policy.max_steps_per_run:
            issues.append(
                PlanValidationIssue(
                    code=PlanValidationCode.STEP_LIMIT_EXCEEDED,
                    message=(
                        f"plan has {len(plan.steps)} steps; maximum is "
                        f"{self.runtime_policy.max_steps_per_run}"
                    ),
                )
            )
        counts = Counter(step.step_id for step in plan.steps)
        seen: set[str] = set()
        for step in plan.steps:
            if counts[step.step_id] > 1 and step.step_id not in seen:
                issues.append(
                    PlanValidationIssue(
                        code=PlanValidationCode.DUPLICATE_STEP_ID,
                        message=f"duplicate step id: {step.step_id}",
                        step_id=step.step_id,
                    )
                )
                seen.add(step.step_id)

    @staticmethod
    def _dependency_graph(plan: Plan) -> dict[str, tuple[str, ...]]:
        graph: dict[str, tuple[str, ...]] = {}
        for step in plan.steps:
            graph.setdefault(step.step_id, step.depends_on)
        return graph

    @staticmethod
    def _validate_dependencies(
        plan: Plan,
        graph: dict[str, tuple[str, ...]],
        issues: list[PlanValidationIssue],
    ) -> None:
        known_ids = set(graph)
        for step in plan.steps:
            for dependency in step.depends_on:
                if dependency not in known_ids:
                    issues.append(
                        PlanValidationIssue(
                            code=PlanValidationCode.UNKNOWN_DEPENDENCY,
                            message=(
                                f"step {step.step_id} depends on unknown step {dependency}"
                            ),
                            step_id=step.step_id,
                            related_step_ids=(dependency,),
                        )
                    )

    @staticmethod
    def _validate_cycles(
        graph: dict[str, tuple[str, ...]], issues: list[PlanValidationIssue]
    ) -> None:
        state: dict[str, int] = {step_id: 0 for step_id in graph}
        path: list[str] = []
        path_indexes: dict[str, int] = {}
        reported: set[frozenset[str]] = set()

        def visit(step_id: str) -> None:
            state[step_id] = 1
            path_indexes[step_id] = len(path)
            path.append(step_id)
            for dependency in graph[step_id]:
                if dependency not in graph:
                    continue
                if state[dependency] == 0:
                    visit(dependency)
                elif state[dependency] == 1:
                    cycle = tuple(path[path_indexes[dependency] :])
                    cycle_key = frozenset(cycle)
                    if cycle_key not in reported:
                        issues.append(
                            PlanValidationIssue(
                                code=PlanValidationCode.DEPENDENCY_CYCLE,
                                message="dependency cycle: " + " -> ".join((*cycle, cycle[0])),
                                step_id=cycle[0],
                                related_step_ids=cycle,
                            )
                        )
                        reported.add(cycle_key)
            path.pop()
            path_indexes.pop(step_id)
            state[step_id] = 2

        for step_id in graph:
            if state[step_id] == 0:
                visit(step_id)

    def _validate_steps(
        self, plan: Plan, issues: list[PlanValidationIssue]
    ) -> None:
        for step in plan.steps:
            self._validate_kind_and_capability(step, issues)
            if not budget_is_narrower_or_equal(plan.budget_envelope, step.budget):
                issues.append(
                    PlanValidationIssue(
                        code=PlanValidationCode.STEP_BUDGET_OUT_OF_ENVELOPE,
                        message=f"step {step.step_id} budget exceeds the plan envelope",
                        step_id=step.step_id,
                    )
                )

    def _validate_kind_and_capability(
        self, step: StepSpec, issues: list[PlanValidationIssue]
    ) -> None:
        if step.executor.kind not in _EXECUTOR_BY_KIND[step.kind]:
            issues.append(
                PlanValidationIssue(
                    code=PlanValidationCode.KIND_EXECUTOR_MISMATCH,
                    message=(
                        f"step kind {step.kind.value} is incompatible with executor "
                        f"{step.executor.kind.value}"
                    ),
                    step_id=step.step_id,
                )
            )

        if step.capability_id is None:
            if step.kind in _CAPABILITY_REQUIRED_KINDS:
                issues.append(
                    PlanValidationIssue(
                        code=PlanValidationCode.UNKNOWN_CAPABILITY,
                        message=f"capability required for step kind {step.kind.value}",
                        step_id=step.step_id,
                    )
                )
            return
        if not self.capability_registry.contains(step.capability_id):
            issues.append(
                PlanValidationIssue(
                    code=PlanValidationCode.UNKNOWN_CAPABILITY,
                    message=f"unknown capability: {step.capability_id.value}",
                    step_id=step.step_id,
                )
            )
            return

        descriptor = self.capability_registry.get(step.capability_id)
        expected_route = _ROUTE_BY_KIND[step.kind]
        if descriptor.execution_route is not expected_route:
            issues.append(
                PlanValidationIssue(
                    code=PlanValidationCode.CAPABILITY_ROUTE_MISMATCH,
                    message=(
                        f"capability {step.capability_id.value} uses route "
                        f"{descriptor.execution_route.value}; expected {expected_route.value}"
                    ),
                    step_id=step.step_id,
                )
            )
        if (
            step.kind is StepKind.AGENT
            and descriptor.execution_route is CapabilityExecutionRoute.AGENT
            and descriptor.owner_agent is not step.executor.agent_id
        ):
            issues.append(
                PlanValidationIssue(
                    code=PlanValidationCode.AGENT_OWNER_MISMATCH,
                    message=(
                        f"capability {step.capability_id.value} owner does not match "
                        f"executor {step.executor.kind.value}"
                    ),
                    step_id=step.step_id,
                )
            )

    @staticmethod
    def _validate_parallel_groups(
        plan: Plan,
        graph: dict[str, tuple[str, ...]],
        issues: list[PlanValidationIssue],
    ) -> None:
        reachability = {
            step_id: PlanValidator._reachable_dependencies(step_id, graph)
            for step_id in graph
        }
        groups: dict[str, list[str]] = {}
        for step in plan.steps:
            if step.parallel_group is not None:
                group = groups.setdefault(step.parallel_group, [])
                if step.step_id not in group:
                    group.append(step.step_id)

        for group_name, step_ids in groups.items():
            for left_index, left_id in enumerate(step_ids):
                for right_id in step_ids[left_index + 1 :]:
                    if right_id in reachability[left_id]:
                        dependent, dependency = left_id, right_id
                    elif left_id in reachability[right_id]:
                        dependent, dependency = right_id, left_id
                    else:
                        continue
                    issues.append(
                        PlanValidationIssue(
                            code=PlanValidationCode.PARALLEL_DEPENDENCY_CONFLICT,
                            message=(
                                f"parallel group {group_name} contains dependency "
                                f"{dependent} -> {dependency}"
                            ),
                            step_id=dependent,
                            related_step_ids=(dependent, dependency),
                        )
                    )

    @staticmethod
    def _reachable_dependencies(
        step_id: str, graph: dict[str, tuple[str, ...]]
    ) -> frozenset[str]:
        reachable: set[str] = set()
        pending = list(reversed(graph[step_id]))
        while pending:
            dependency = pending.pop()
            if dependency not in graph or dependency in reachable:
                continue
            reachable.add(dependency)
            pending.extend(reversed(graph[dependency]))
        return frozenset(reachable)
