from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from backend.agent_runtime.contracts import AgentId
from backend.agent_runtime.orchestration.workflows.model import (
    WorkflowGateProfile,
    WorkflowKind,
    WorkflowOrderingConstraint,
    WorkflowParallelProfile,
    WorkflowResponsibility,
    WorkflowResponsibilityDescriptor,
    WorkflowRevisionProfile,
    WorkflowTopologyDescriptor,
)
from backend.agent_runtime.registry import CapabilityClass

R = WorkflowResponsibility


class UnknownWorkflowError(LookupError):
    def __init__(self, workflow_kind: WorkflowKind) -> None:
        self.workflow_kind = workflow_kind
        super().__init__(f"unknown workflow: {workflow_kind.value}")


@dataclass(frozen=True, slots=True)
class WorkflowCatalog:
    _descriptors: tuple[WorkflowTopologyDescriptor, ...]
    _by_kind: MappingProxyType[WorkflowKind, WorkflowTopologyDescriptor]

    def __init__(self, descriptors: Iterable[WorkflowTopologyDescriptor]) -> None:
        normalized = tuple(descriptors)
        if any(not isinstance(item, WorkflowTopologyDescriptor) for item in normalized):
            raise TypeError("descriptors must contain WorkflowTopologyDescriptor values")
        workflow_kinds = tuple(item.workflow_kind for item in normalized)
        canonical_names = tuple(item.canonical_name for item in normalized)
        if len(set(workflow_kinds)) != len(workflow_kinds):
            raise ValueError("duplicate WorkflowKind in catalog")
        if len(set(canonical_names)) != len(canonical_names):
            raise ValueError("duplicate canonical_name in catalog")
        object.__setattr__(self, "_descriptors", normalized)
        object.__setattr__(
            self,
            "_by_kind",
            MappingProxyType({item.workflow_kind: item for item in normalized}),
        )

    def get(self, workflow_kind: WorkflowKind) -> WorkflowTopologyDescriptor:
        if not isinstance(workflow_kind, WorkflowKind):
            raise TypeError("workflow_kind must be a WorkflowKind")
        try:
            return self._by_kind[workflow_kind]
        except KeyError as error:
            raise UnknownWorkflowError(workflow_kind) from error

    def contains(self, workflow_kind: WorkflowKind) -> bool:
        if not isinstance(workflow_kind, WorkflowKind):
            raise TypeError("workflow_kind must be a WorkflowKind")
        return workflow_kind in self._by_kind

    def all(self) -> tuple[WorkflowTopologyDescriptor, ...]:
        return self._descriptors


def _order(
    before: WorkflowResponsibility, after: WorkflowResponsibility
) -> WorkflowOrderingConstraint:
    return WorkflowOrderingConstraint(before, after)


BASELINE_WORKFLOW_RESPONSIBILITY_DESCRIPTORS: Final = (
    WorkflowResponsibilityDescriptor(
        R.DIRECT_APPLICATION,
        None,
        (CapabilityClass.READ, CapabilityClass.APPLICATION_ACTION),
    ),
    WorkflowResponsibilityDescriptor(R.EVIDENCE, AgentId.AG_02, (CapabilityClass.EVIDENCE,)),
    WorkflowResponsibilityDescriptor(
        R.GENERATE_TRANSFORM,
        AgentId.AG_03,
        (CapabilityClass.GENERATE_TRANSFORM,),
    ),
    WorkflowResponsibilityDescriptor(R.REVIEW, AgentId.AG_04, (CapabilityClass.REVIEW,)),
    WorkflowResponsibilityDescriptor(
        R.DETERMINISTIC_VALIDATION,
        None,
        (CapabilityClass.APPLICATION_ACTION,),
    ),
    WorkflowResponsibilityDescriptor(
        R.CORRECTION,
        AgentId.AG_03,
        (CapabilityClass.GENERATE_TRANSFORM,),
    ),
    WorkflowResponsibilityDescriptor(
        R.EVIDENCE_JOIN,
        None,
        (CapabilityClass.ORCHESTRATION,),
    ),
    WorkflowResponsibilityDescriptor(
        R.VARIANT_GENERATION,
        AgentId.AG_03,
        (CapabilityClass.GENERATE_TRANSFORM,),
    ),
    WorkflowResponsibilityDescriptor(
        R.VARIANT_JOIN,
        None,
        (CapabilityClass.ORCHESTRATION,),
    ),
    WorkflowResponsibilityDescriptor(
        R.VARIANT_SELECTION,
        None,
        (CapabilityClass.ORCHESTRATION,),
    ),
    WorkflowResponsibilityDescriptor(R.GATE, None, (CapabilityClass.ORCHESTRATION,)),
    WorkflowResponsibilityDescriptor(
        R.PROMOTION,
        None,
        (CapabilityClass.APPLICATION_ACTION,),
    ),
)


BASELINE_WORKFLOW_CATALOG: Final = WorkflowCatalog(
    (
        WorkflowTopologyDescriptor(
            WorkflowKind.WF_0,
            "Application/direct",
            "Direct execution through an Application inbound boundary.",
            (R.DIRECT_APPLICATION,),
            application_boundary=True,
        ),
        WorkflowTopologyDescriptor(
            WorkflowKind.WF_1,
            "Evidence",
            "Evidence retrieval and assessment by AG-02.",
            (R.EVIDENCE,),
        ),
        WorkflowTopologyDescriptor(
            WorkflowKind.WF_2,
            "Generation/Transformation",
            "Generation or transformation with optional deterministic validation.",
            (R.GENERATE_TRANSFORM,),
            (R.DETERMINISTIC_VALIDATION,),
            (_order(R.GENERATE_TRANSFORM, R.DETERMINISTIC_VALIDATION),),
        ),
        WorkflowTopologyDescriptor(
            WorkflowKind.WF_3,
            "Independent review",
            "Independent semantic review by AG-04.",
            (R.REVIEW,),
        ),
        WorkflowTopologyDescriptor(
            WorkflowKind.WF_4,
            "Evidence then generation",
            "Evidence precedes generation and optional deterministic validation.",
            (R.EVIDENCE, R.GENERATE_TRANSFORM),
            (R.DETERMINISTIC_VALIDATION,),
            (
                _order(R.EVIDENCE, R.GENERATE_TRANSFORM),
                _order(R.GENERATE_TRANSFORM, R.DETERMINISTIC_VALIDATION),
            ),
        ),
        WorkflowTopologyDescriptor(
            WorkflowKind.WF_5,
            "Generation then review",
            "Generation precedes independent review, with optional validation before review.",
            (R.GENERATE_TRANSFORM, R.REVIEW),
            (R.DETERMINISTIC_VALIDATION,),
            (
                _order(R.GENERATE_TRANSFORM, R.REVIEW),
                _order(R.GENERATE_TRANSFORM, R.DETERMINISTIC_VALIDATION),
                _order(R.DETERMINISTIC_VALIDATION, R.REVIEW),
            ),
        ),
        WorkflowTopologyDescriptor(
            WorkflowKind.WF_6,
            "Evidence generation validation review",
            "Evidence, generation, Application validation and independent review in order.",
            (R.EVIDENCE, R.GENERATE_TRANSFORM, R.DETERMINISTIC_VALIDATION, R.REVIEW),
            ordering_constraints=(
                _order(R.EVIDENCE, R.GENERATE_TRANSFORM),
                _order(R.GENERATE_TRANSFORM, R.DETERMINISTIC_VALIDATION),
                _order(R.DETERMINISTIC_VALIDATION, R.REVIEW),
            ),
        ),
        WorkflowTopologyDescriptor(
            WorkflowKind.WF_7,
            "Bounded correction/re-review",
            "Correction followed by optional re-review; repetition creates a new Plan version.",
            (R.CORRECTION,),
            (R.REVIEW,),
            (_order(R.CORRECTION, R.REVIEW),),
            revision_profile=WorkflowRevisionProfile.CORRECTION_REVIEW,
        ),
        WorkflowTopologyDescriptor(
            WorkflowKind.WF_8,
            "Parallel evidence",
            "A dynamic number of independent evidence branches converges on one evidence join.",
            (R.EVIDENCE, R.EVIDENCE_JOIN),
            ordering_constraints=(_order(R.EVIDENCE, R.EVIDENCE_JOIN),),
            parallel_profile=WorkflowParallelProfile.EVIDENCE_FANOUT,
            min_parallel_branches=2,
            join_responsibility=R.EVIDENCE_JOIN,
        ),
        WorkflowTopologyDescriptor(
            WorkflowKind.WF_9,
            "Parallel variants and selection",
            "A dynamic number of generated variants converges before a selection.",
            (R.VARIANT_GENERATION, R.VARIANT_JOIN, R.VARIANT_SELECTION),
            ordering_constraints=(
                _order(R.VARIANT_GENERATION, R.VARIANT_JOIN),
                _order(R.VARIANT_JOIN, R.VARIANT_SELECTION),
            ),
            parallel_profile=WorkflowParallelProfile.VARIANT_FANOUT,
            min_parallel_branches=2,
            join_responsibility=R.VARIANT_JOIN,
        ),
        WorkflowTopologyDescriptor(
            WorkflowKind.WF_10,
            "Human-gated workflow",
            "A composable human gate can wrap a base topology in Phase 12.6-C/D.",
            (R.GATE,),
            gate_profile=WorkflowGateProfile.HUMAN,
            overlay=True,
        ),
        WorkflowTopologyDescriptor(
            WorkflowKind.WF_11,
            "Application validation and promotion",
            "Application validation, policy-required gate and Application promotion.",
            (R.DETERMINISTIC_VALIDATION, R.GATE, R.PROMOTION),
            ordering_constraints=(
                _order(R.DETERMINISTIC_VALIDATION, R.GATE),
                _order(R.GATE, R.PROMOTION),
            ),
            gate_profile=WorkflowGateProfile.POLICY_REQUIRED,
            application_boundary=True,
        ),
    )
)
