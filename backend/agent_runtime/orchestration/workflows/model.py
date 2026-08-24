from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from backend.agent_runtime.contracts import AgentId
from backend.agent_runtime.registry import CapabilityClass
from backend.shared_kernel._strings import require_non_empty


class WorkflowKind(StrEnum):
    WF_0 = "WF-0"
    WF_1 = "WF-1"
    WF_2 = "WF-2"
    WF_3 = "WF-3"
    WF_4 = "WF-4"
    WF_5 = "WF-5"
    WF_6 = "WF-6"
    WF_7 = "WF-7"
    WF_8 = "WF-8"
    WF_9 = "WF-9"
    WF_10 = "WF-10"
    WF_11 = "WF-11"


class WorkflowResponsibility(StrEnum):
    DIRECT_APPLICATION = "DIRECT_APPLICATION"
    EVIDENCE = "EVIDENCE"
    GENERATE_TRANSFORM = "GENERATE_TRANSFORM"
    REVIEW = "REVIEW"
    DETERMINISTIC_VALIDATION = "DETERMINISTIC_VALIDATION"
    CORRECTION = "CORRECTION"
    EVIDENCE_JOIN = "EVIDENCE_JOIN"
    VARIANT_GENERATION = "VARIANT_GENERATION"
    VARIANT_JOIN = "VARIANT_JOIN"
    VARIANT_SELECTION = "VARIANT_SELECTION"
    GATE = "GATE"
    PROMOTION = "PROMOTION"


class WorkflowGateProfile(StrEnum):
    NONE = "NONE"
    HUMAN = "HUMAN"
    POLICY_REQUIRED = "POLICY_REQUIRED"


class WorkflowParallelProfile(StrEnum):
    NONE = "NONE"
    EVIDENCE_FANOUT = "EVIDENCE_FANOUT"
    VARIANT_FANOUT = "VARIANT_FANOUT"


class WorkflowRevisionProfile(StrEnum):
    NONE = "NONE"
    CORRECTION_REVIEW = "CORRECTION_REVIEW"


@dataclass(frozen=True, slots=True)
class WorkflowOrderingConstraint:
    before: WorkflowResponsibility
    after: WorkflowResponsibility

    def __post_init__(self) -> None:
        if not isinstance(self.before, WorkflowResponsibility):
            raise TypeError("before must be a WorkflowResponsibility")
        if not isinstance(self.after, WorkflowResponsibility):
            raise TypeError("after must be a WorkflowResponsibility")
        if self.before is self.after:
            raise ValueError("before and after must be different")


@dataclass(frozen=True, slots=True)
class WorkflowResponsibilityDescriptor:
    responsibility: WorkflowResponsibility
    owner_agent: AgentId | None
    allowed_capability_classes: tuple[CapabilityClass, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.responsibility, WorkflowResponsibility):
            raise TypeError("responsibility must be a WorkflowResponsibility")
        if self.owner_agent is not None and not isinstance(self.owner_agent, AgentId):
            raise TypeError("owner_agent must be an AgentId or None")
        if not isinstance(self.allowed_capability_classes, tuple):
            raise TypeError("allowed_capability_classes must be a tuple")
        if not self.allowed_capability_classes:
            raise ValueError("allowed_capability_classes must not be empty")
        if any(
            not isinstance(item, CapabilityClass)
            for item in self.allowed_capability_classes
        ):
            raise TypeError("allowed_capability_classes must contain CapabilityClass values")
        if len(set(self.allowed_capability_classes)) != len(
            self.allowed_capability_classes
        ):
            raise ValueError("allowed_capability_classes must be unique")


@dataclass(frozen=True, slots=True)
class WorkflowTopologyDescriptor:
    workflow_kind: WorkflowKind
    canonical_name: str
    purpose: str
    required_responsibilities: tuple[WorkflowResponsibility, ...]
    optional_responsibilities: tuple[WorkflowResponsibility, ...] = ()
    ordering_constraints: tuple[WorkflowOrderingConstraint, ...] = ()
    gate_profile: WorkflowGateProfile = WorkflowGateProfile.NONE
    parallel_profile: WorkflowParallelProfile = WorkflowParallelProfile.NONE
    min_parallel_branches: int = 0
    join_responsibility: WorkflowResponsibility | None = None
    revision_profile: WorkflowRevisionProfile = WorkflowRevisionProfile.NONE
    application_boundary: bool = False
    overlay: bool = False

    def __post_init__(self) -> None:
        self._validate_scalar_fields()
        declared = self._validate_responsibility_tuples()
        self._validate_ordering_constraints(declared)
        self._validate_parallel_profile()
        self._validate_gate_profile()
        self._validate_revision_profile()

    def _validate_scalar_fields(self) -> None:
        if not isinstance(self.workflow_kind, WorkflowKind):
            raise TypeError("workflow_kind must be a WorkflowKind")
        require_non_empty(self.canonical_name, "canonical_name")
        require_non_empty(self.purpose, "purpose")
        if not isinstance(self.gate_profile, WorkflowGateProfile):
            raise TypeError("gate_profile must be a WorkflowGateProfile")
        if not isinstance(self.parallel_profile, WorkflowParallelProfile):
            raise TypeError("parallel_profile must be a WorkflowParallelProfile")
        if type(self.min_parallel_branches) is not int:
            raise TypeError("min_parallel_branches must be an integer")
        if self.min_parallel_branches < 0:
            raise ValueError("min_parallel_branches must be >= 0")
        if self.join_responsibility is not None and not isinstance(
            self.join_responsibility, WorkflowResponsibility
        ):
            raise TypeError("join_responsibility must be a WorkflowResponsibility or None")
        if not isinstance(self.revision_profile, WorkflowRevisionProfile):
            raise TypeError("revision_profile must be a WorkflowRevisionProfile")
        if not isinstance(self.application_boundary, bool):
            raise TypeError("application_boundary must be a bool")
        if not isinstance(self.overlay, bool):
            raise TypeError("overlay must be a bool")

    def _validate_responsibility_tuples(self) -> set[WorkflowResponsibility]:
        for field_name, values in (
            ("required_responsibilities", self.required_responsibilities),
            ("optional_responsibilities", self.optional_responsibilities),
        ):
            if not isinstance(values, tuple):
                raise TypeError(f"{field_name} must be a tuple")
            if any(not isinstance(item, WorkflowResponsibility) for item in values):
                raise TypeError(f"{field_name} must contain WorkflowResponsibility values")
            if len(set(values)) != len(values):
                raise ValueError(f"{field_name} must be unique")
        if not self.required_responsibilities:
            raise ValueError("required_responsibilities must not be empty")
        required = set(self.required_responsibilities)
        optional = set(self.optional_responsibilities)
        if required & optional:
            raise ValueError("required_responsibilities and optional_responsibilities must be disjoint")
        return required | optional

    def _validate_ordering_constraints(
        self, declared: set[WorkflowResponsibility]
    ) -> None:
        if not isinstance(self.ordering_constraints, tuple):
            raise TypeError("ordering_constraints must be a tuple")
        if any(
            not isinstance(item, WorkflowOrderingConstraint)
            for item in self.ordering_constraints
        ):
            raise TypeError("ordering_constraints must contain WorkflowOrderingConstraint values")
        pairs = tuple(
            (constraint.before, constraint.after)
            for constraint in self.ordering_constraints
        )
        if len(set(pairs)) != len(pairs):
            raise ValueError("ordering_constraints must not contain duplicate pairs")
        if any(before not in declared or after not in declared for before, after in pairs):
            raise ValueError("ordering_constraints must reference declared responsibilities")
        if self._contains_ordering_cycle(declared, pairs):
            raise ValueError("ordering_constraints must be acyclic")

    @staticmethod
    def _contains_ordering_cycle(
        declared: set[WorkflowResponsibility],
        pairs: tuple[tuple[WorkflowResponsibility, WorkflowResponsibility], ...],
    ) -> bool:
        remaining = dict.fromkeys(declared, 0)
        following: dict[WorkflowResponsibility, list[WorkflowResponsibility]] = {
            item: [] for item in declared
        }
        for before, after in pairs:
            following[before].append(after)
            remaining[after] += 1
        ready = [item for item, count in remaining.items() if count == 0]
        visited = 0
        while ready:
            current = ready.pop()
            visited += 1
            for successor in following[current]:
                remaining[successor] -= 1
                if remaining[successor] == 0:
                    ready.append(successor)
        return visited != len(declared)

    def _validate_parallel_profile(self) -> None:
        required = set(self.required_responsibilities)
        if self.parallel_profile is WorkflowParallelProfile.NONE:
            if self.min_parallel_branches != 0 or self.join_responsibility is not None:
                raise ValueError("parallel NONE requires zero branches and no join")
            return
        if self.min_parallel_branches < 2:
            raise ValueError("parallel fanout requires at least two branches")
        if self.parallel_profile is WorkflowParallelProfile.EVIDENCE_FANOUT:
            if WorkflowResponsibility.EVIDENCE not in required:
                raise ValueError("EVIDENCE_FANOUT requires EVIDENCE")
            if self.join_responsibility is not WorkflowResponsibility.EVIDENCE_JOIN:
                raise ValueError("EVIDENCE_FANOUT requires EVIDENCE_JOIN as join")
            if WorkflowResponsibility.EVIDENCE_JOIN not in required:
                raise ValueError("EVIDENCE_FANOUT requires EVIDENCE_JOIN")
            return
        variant_required = {
            WorkflowResponsibility.VARIANT_GENERATION,
            WorkflowResponsibility.VARIANT_JOIN,
            WorkflowResponsibility.VARIANT_SELECTION,
        }
        if not variant_required <= required:
            raise ValueError("VARIANT_FANOUT requires generation, join and selection")
        if self.join_responsibility is not WorkflowResponsibility.VARIANT_JOIN:
            raise ValueError("VARIANT_FANOUT requires VARIANT_JOIN as join")
        required_order = WorkflowOrderingConstraint(
            WorkflowResponsibility.VARIANT_JOIN,
            WorkflowResponsibility.VARIANT_SELECTION,
        )
        if required_order not in self.ordering_constraints:
            raise ValueError("VARIANT_FANOUT requires VARIANT_JOIN before VARIANT_SELECTION")

    def _validate_gate_profile(self) -> None:
        if self.gate_profile is WorkflowGateProfile.NONE:
            return
        if WorkflowResponsibility.GATE not in self.required_responsibilities:
            raise ValueError("a gate profile requires GATE")
        if self.gate_profile is WorkflowGateProfile.HUMAN and not self.overlay:
            raise ValueError("the HUMAN gate profile must be an overlay")
        if (
            self.gate_profile is WorkflowGateProfile.POLICY_REQUIRED
            and not self.application_boundary
        ):
            raise ValueError("the POLICY_REQUIRED gate profile needs an application boundary")

    def _validate_revision_profile(self) -> None:
        if self.revision_profile is WorkflowRevisionProfile.NONE:
            return
        if WorkflowResponsibility.CORRECTION not in self.required_responsibilities:
            raise ValueError("CORRECTION_REVIEW requires CORRECTION")
        declared = set(self.required_responsibilities) | set(
            self.optional_responsibilities
        )
        if WorkflowResponsibility.REVIEW not in declared:
            raise ValueError("CORRECTION_REVIEW requires REVIEW")
