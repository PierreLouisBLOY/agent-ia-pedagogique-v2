from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from backend.agent_runtime.contracts import AgentId
from backend.agent_runtime.orchestration import (
    BASELINE_WORKFLOW_CATALOG,
    BASELINE_WORKFLOW_RESPONSIBILITY_DESCRIPTORS,
    WorkflowCatalog,
    WorkflowGateProfile,
    WorkflowKind,
    WorkflowOrderingConstraint,
    WorkflowParallelProfile,
    WorkflowResponsibility,
    WorkflowRevisionProfile,
    WorkflowTopologyDescriptor,
)
from backend.agent_runtime.registry import CapabilityClass

R = WorkflowResponsibility


def _order(
    before: WorkflowResponsibility, after: WorkflowResponsibility
) -> WorkflowOrderingConstraint:
    return WorkflowOrderingConstraint(before, after)


def _descriptor(**changes: object) -> WorkflowTopologyDescriptor:
    values: dict[str, object] = {
        "workflow_kind": WorkflowKind.WF_0,
        "canonical_name": "Example",
        "purpose": "Exercise topology invariants.",
        "required_responsibilities": (R.DIRECT_APPLICATION,),
    }
    values.update(changes)
    return WorkflowTopologyDescriptor(**values)  # type: ignore[arg-type]


def _edges(descriptor: WorkflowTopologyDescriptor) -> set[tuple[R, R]]:
    return {(item.before, item.after) for item in descriptor.ordering_constraints}


def test_workflow_kind_has_exactly_the_twelve_canonical_values() -> None:
    assert [item.value for item in WorkflowKind] == [f"WF-{index}" for index in range(12)]
    assert len(WorkflowKind) == 12


def test_workflow_kind_has_no_fallback_member() -> None:
    assert "CUSTOM" not in WorkflowKind.__members__
    assert "UNKNOWN" not in WorkflowKind.__members__


def test_workflow_responsibility_vocabulary_is_exact() -> None:
    assert [item.value for item in R] == [
        "DIRECT_APPLICATION",
        "EVIDENCE",
        "GENERATE_TRANSFORM",
        "REVIEW",
        "DETERMINISTIC_VALIDATION",
        "CORRECTION",
        "EVIDENCE_JOIN",
        "VARIANT_GENERATION",
        "VARIANT_JOIN",
        "VARIANT_SELECTION",
        "GATE",
        "PROMOTION",
    ]


def test_structural_profile_vocabularies_are_exact() -> None:
    assert [item.value for item in WorkflowGateProfile] == [
        "NONE",
        "HUMAN",
        "POLICY_REQUIRED",
    ]
    assert [item.value for item in WorkflowParallelProfile] == [
        "NONE",
        "EVIDENCE_FANOUT",
        "VARIANT_FANOUT",
    ]
    assert [item.value for item in WorkflowRevisionProfile] == [
        "NONE",
        "CORRECTION_REVIEW",
    ]


def test_ordering_constraint_requires_distinct_typed_responsibilities() -> None:
    with pytest.raises(ValueError, match="different"):
        _order(R.EVIDENCE, R.EVIDENCE)
    with pytest.raises(TypeError, match="before"):
        WorkflowOrderingConstraint("EVIDENCE", R.REVIEW)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="after"):
        WorkflowOrderingConstraint(R.EVIDENCE, "REVIEW")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"canonical_name": " "}, "canonical_name"),
        ({"purpose": ""}, "purpose"),
        ({"required_responsibilities": []}, "must be a tuple"),
        ({"required_responsibilities": ()}, "must not be empty"),
        (
            {"required_responsibilities": (R.EVIDENCE, R.EVIDENCE)},
            "must be unique",
        ),
        ({"optional_responsibilities": [R.REVIEW]}, "must be a tuple"),
        (
            {"optional_responsibilities": (R.REVIEW, R.REVIEW)},
            "must be unique",
        ),
        (
            {
                "required_responsibilities": (R.REVIEW,),
                "optional_responsibilities": (R.REVIEW,),
            },
            "must be disjoint",
        ),
        (
            {
                "ordering_constraints": (
                    _order(R.DIRECT_APPLICATION, R.REVIEW),
                )
            },
            "declared responsibilities",
        ),
        (
            {
                "required_responsibilities": (R.EVIDENCE, R.REVIEW),
                "ordering_constraints": (
                    _order(R.EVIDENCE, R.REVIEW),
                    _order(R.EVIDENCE, R.REVIEW),
                ),
            },
            "duplicate pairs",
        ),
        (
            {
                "required_responsibilities": (R.EVIDENCE, R.REVIEW),
                "ordering_constraints": (
                    _order(R.EVIDENCE, R.REVIEW),
                    _order(R.REVIEW, R.EVIDENCE),
                ),
            },
            "acyclic",
        ),
        ({"application_boundary": 1}, "application_boundary"),
        ({"overlay": 0}, "overlay"),
        ({"min_parallel_branches": True}, "integer"),
        ({"min_parallel_branches": -1}, ">= 0"),
    ],
)
def test_topology_descriptor_rejects_invalid_core_invariants(
    changes: dict[str, object], message: str
) -> None:
    with pytest.raises((TypeError, ValueError), match=message):
        _descriptor(**changes)


def test_parallel_none_requires_zero_branches_and_no_join() -> None:
    with pytest.raises(ValueError, match="parallel NONE"):
        _descriptor(min_parallel_branches=2)
    with pytest.raises(ValueError, match="parallel NONE"):
        _descriptor(join_responsibility=R.EVIDENCE_JOIN)


def test_evidence_fanout_requires_minimum_two_branches() -> None:
    with pytest.raises(ValueError, match="at least two"):
        _descriptor(
            required_responsibilities=(R.EVIDENCE, R.EVIDENCE_JOIN),
            parallel_profile=WorkflowParallelProfile.EVIDENCE_FANOUT,
            min_parallel_branches=1,
            join_responsibility=R.EVIDENCE_JOIN,
        )


@pytest.mark.parametrize(
    ("required", "join"),
    [
        ((R.EVIDENCE_JOIN,), R.EVIDENCE_JOIN),
        ((R.EVIDENCE,), R.EVIDENCE_JOIN),
        ((R.EVIDENCE, R.EVIDENCE_JOIN), R.VARIANT_JOIN),
    ],
)
def test_evidence_fanout_requires_evidence_and_its_join(
    required: tuple[R, ...], join: R
) -> None:
    with pytest.raises(ValueError, match="EVIDENCE_FANOUT"):
        _descriptor(
            required_responsibilities=required,
            parallel_profile=WorkflowParallelProfile.EVIDENCE_FANOUT,
            min_parallel_branches=2,
            join_responsibility=join,
        )


@pytest.mark.parametrize(
    "required",
    [
        (R.VARIANT_GENERATION, R.VARIANT_JOIN),
        (R.VARIANT_GENERATION, R.VARIANT_SELECTION),
        (R.VARIANT_JOIN, R.VARIANT_SELECTION),
    ],
)
def test_variant_fanout_requires_generation_join_and_selection(
    required: tuple[R, ...]
) -> None:
    with pytest.raises(ValueError, match="VARIANT_FANOUT"):
        _descriptor(
            required_responsibilities=required,
            parallel_profile=WorkflowParallelProfile.VARIANT_FANOUT,
            min_parallel_branches=2,
            join_responsibility=R.VARIANT_JOIN,
        )


def test_variant_fanout_requires_join_before_selection() -> None:
    with pytest.raises(ValueError, match="before VARIANT_SELECTION"):
        _descriptor(
            required_responsibilities=(
                R.VARIANT_GENERATION,
                R.VARIANT_JOIN,
                R.VARIANT_SELECTION,
            ),
            parallel_profile=WorkflowParallelProfile.VARIANT_FANOUT,
            min_parallel_branches=2,
            join_responsibility=R.VARIANT_JOIN,
        )


@pytest.mark.parametrize(
    "profile",
    [WorkflowGateProfile.HUMAN, WorkflowGateProfile.POLICY_REQUIRED],
)
def test_gate_profiles_require_gate(profile: WorkflowGateProfile) -> None:
    with pytest.raises(ValueError, match="requires GATE"):
        _descriptor(
            gate_profile=profile,
            overlay=profile is WorkflowGateProfile.HUMAN,
            application_boundary=profile is WorkflowGateProfile.POLICY_REQUIRED,
        )


def test_human_and_policy_gate_profiles_require_their_structural_boundary() -> None:
    with pytest.raises(ValueError, match="overlay"):
        _descriptor(required_responsibilities=(R.GATE,), gate_profile=WorkflowGateProfile.HUMAN)
    with pytest.raises(ValueError, match="application boundary"):
        _descriptor(
            required_responsibilities=(R.GATE,),
            gate_profile=WorkflowGateProfile.POLICY_REQUIRED,
        )


def test_correction_review_profile_requires_correction_and_review() -> None:
    with pytest.raises(ValueError, match="CORRECTION"):
        _descriptor(
            required_responsibilities=(R.REVIEW,),
            revision_profile=WorkflowRevisionProfile.CORRECTION_REVIEW,
        )
    with pytest.raises(ValueError, match="REVIEW"):
        _descriptor(
            required_responsibilities=(R.CORRECTION,),
            revision_profile=WorkflowRevisionProfile.CORRECTION_REVIEW,
        )


def test_workflow_catalog_rejects_duplicate_kind_and_name() -> None:
    first = _descriptor()
    with pytest.raises(ValueError, match="duplicate WorkflowKind"):
        WorkflowCatalog((first, replace(first, canonical_name="Second")))
    with pytest.raises(ValueError, match="duplicate canonical_name"):
        WorkflowCatalog((first, replace(first, workflow_kind=WorkflowKind.WF_1)))


def test_workflow_catalog_get_contains_and_all_are_typed_and_stable() -> None:
    descriptor = _descriptor()
    catalog = WorkflowCatalog((descriptor,))
    assert catalog.get(WorkflowKind.WF_0) is descriptor
    assert catalog.contains(WorkflowKind.WF_0)
    assert catalog.all() == (descriptor,)
    assert isinstance(catalog.all(), tuple)
    with pytest.raises(TypeError):
        catalog.contains("WF-0")  # type: ignore[arg-type]


def test_baseline_catalog_contains_exactly_twelve_ordered_descriptors() -> None:
    descriptors = BASELINE_WORKFLOW_CATALOG.all()
    assert len(descriptors) == 12
    assert tuple(item.workflow_kind for item in descriptors) == tuple(WorkflowKind)
    assert all(BASELINE_WORKFLOW_CATALOG.contains(kind) for kind in WorkflowKind)


@pytest.mark.parametrize(
    ("kind", "name", "required", "optional", "edges"),
    [
        (WorkflowKind.WF_0, "Application/direct", (R.DIRECT_APPLICATION,), (), set()),
        (WorkflowKind.WF_1, "Evidence", (R.EVIDENCE,), (), set()),
        (
            WorkflowKind.WF_2,
            "Generation/Transformation",
            (R.GENERATE_TRANSFORM,),
            (R.DETERMINISTIC_VALIDATION,),
            {(R.GENERATE_TRANSFORM, R.DETERMINISTIC_VALIDATION)},
        ),
        (WorkflowKind.WF_3, "Independent review", (R.REVIEW,), (), set()),
        (
            WorkflowKind.WF_4,
            "Evidence then generation",
            (R.EVIDENCE, R.GENERATE_TRANSFORM),
            (R.DETERMINISTIC_VALIDATION,),
            {
                (R.EVIDENCE, R.GENERATE_TRANSFORM),
                (R.GENERATE_TRANSFORM, R.DETERMINISTIC_VALIDATION),
            },
        ),
        (
            WorkflowKind.WF_5,
            "Generation then review",
            (R.GENERATE_TRANSFORM, R.REVIEW),
            (R.DETERMINISTIC_VALIDATION,),
            {
                (R.GENERATE_TRANSFORM, R.REVIEW),
                (R.GENERATE_TRANSFORM, R.DETERMINISTIC_VALIDATION),
                (R.DETERMINISTIC_VALIDATION, R.REVIEW),
            },
        ),
        (
            WorkflowKind.WF_6,
            "Evidence generation validation review",
            (R.EVIDENCE, R.GENERATE_TRANSFORM, R.DETERMINISTIC_VALIDATION, R.REVIEW),
            (),
            {
                (R.EVIDENCE, R.GENERATE_TRANSFORM),
                (R.GENERATE_TRANSFORM, R.DETERMINISTIC_VALIDATION),
                (R.DETERMINISTIC_VALIDATION, R.REVIEW),
            },
        ),
        (
            WorkflowKind.WF_7,
            "Bounded correction/re-review",
            (R.CORRECTION,),
            (R.REVIEW,),
            {(R.CORRECTION, R.REVIEW)},
        ),
        (
            WorkflowKind.WF_8,
            "Parallel evidence",
            (R.EVIDENCE, R.EVIDENCE_JOIN),
            (),
            {(R.EVIDENCE, R.EVIDENCE_JOIN)},
        ),
        (
            WorkflowKind.WF_9,
            "Parallel variants and selection",
            (R.VARIANT_GENERATION, R.VARIANT_JOIN, R.VARIANT_SELECTION),
            (),
            {
                (R.VARIANT_GENERATION, R.VARIANT_JOIN),
                (R.VARIANT_JOIN, R.VARIANT_SELECTION),
            },
        ),
        (WorkflowKind.WF_10, "Human-gated workflow", (R.GATE,), (), set()),
        (
            WorkflowKind.WF_11,
            "Application validation and promotion",
            (R.DETERMINISTIC_VALIDATION, R.GATE, R.PROMOTION),
            (),
            {(R.DETERMINISTIC_VALIDATION, R.GATE), (R.GATE, R.PROMOTION)},
        ),
    ],
)
def test_each_baseline_workflow_has_its_exact_canonical_topology(
    kind: WorkflowKind,
    name: str,
    required: tuple[R, ...],
    optional: tuple[R, ...],
    edges: set[tuple[R, R]],
) -> None:
    descriptor = BASELINE_WORKFLOW_CATALOG.get(kind)
    assert descriptor.canonical_name == name
    assert descriptor.required_responsibilities == required
    assert descriptor.optional_responsibilities == optional
    assert _edges(descriptor) == edges


def test_wf0_and_wf11_are_the_application_boundaries() -> None:
    boundaries = {
        item.workflow_kind
        for item in BASELINE_WORKFLOW_CATALOG.all()
        if item.application_boundary
    }
    assert boundaries == {WorkflowKind.WF_0, WorkflowKind.WF_11}


def test_wf7_is_acyclic_and_plan_versioned() -> None:
    descriptor = BASELINE_WORKFLOW_CATALOG.get(WorkflowKind.WF_7)
    assert descriptor.revision_profile is WorkflowRevisionProfile.CORRECTION_REVIEW
    assert _edges(descriptor) == {(R.CORRECTION, R.REVIEW)}


def test_wf8_and_wf9_describe_dynamic_fanout_minima_and_joins() -> None:
    wf8 = BASELINE_WORKFLOW_CATALOG.get(WorkflowKind.WF_8)
    wf9 = BASELINE_WORKFLOW_CATALOG.get(WorkflowKind.WF_9)
    assert (wf8.parallel_profile, wf8.min_parallel_branches, wf8.join_responsibility) == (
        WorkflowParallelProfile.EVIDENCE_FANOUT,
        2,
        R.EVIDENCE_JOIN,
    )
    assert (wf9.parallel_profile, wf9.min_parallel_branches, wf9.join_responsibility) == (
        WorkflowParallelProfile.VARIANT_FANOUT,
        2,
        R.VARIANT_JOIN,
    )


def test_wf10_is_a_human_gate_overlay() -> None:
    descriptor = BASELINE_WORKFLOW_CATALOG.get(WorkflowKind.WF_10)
    assert descriptor.gate_profile is WorkflowGateProfile.HUMAN
    assert descriptor.overlay
    assert "base topology" in descriptor.purpose


def test_wf11_is_policy_gated_before_application_promotion() -> None:
    descriptor = BASELINE_WORKFLOW_CATALOG.get(WorkflowKind.WF_11)
    assert descriptor.gate_profile is WorkflowGateProfile.POLICY_REQUIRED
    assert descriptor.application_boundary
    assert _edges(descriptor) == {
        (R.DETERMINISTIC_VALIDATION, R.GATE),
        (R.GATE, R.PROMOTION),
    }


def test_responsibility_metadata_is_complete_and_has_unique_keys() -> None:
    descriptors = BASELINE_WORKFLOW_RESPONSIBILITY_DESCRIPTORS
    assert isinstance(descriptors, tuple)
    assert tuple(item.responsibility for item in descriptors) == tuple(R)
    assert len({item.responsibility for item in descriptors}) == len(R)


def test_specialist_responsibility_ownership_is_exact() -> None:
    by_responsibility = {
        item.responsibility: item for item in BASELINE_WORKFLOW_RESPONSIBILITY_DESCRIPTORS
    }
    assert by_responsibility[R.EVIDENCE].owner_agent is AgentId.AG_02
    for responsibility in (R.GENERATE_TRANSFORM, R.CORRECTION, R.VARIANT_GENERATION):
        descriptor = by_responsibility[responsibility]
        assert descriptor.owner_agent is AgentId.AG_03
        assert descriptor.allowed_capability_classes == (CapabilityClass.GENERATE_TRANSFORM,)
    assert by_responsibility[R.REVIEW].owner_agent is AgentId.AG_04
    assert by_responsibility[R.REVIEW].allowed_capability_classes == (CapabilityClass.REVIEW,)


def test_application_responsibilities_have_no_agent_owner() -> None:
    by_responsibility = {
        item.responsibility: item for item in BASELINE_WORKFLOW_RESPONSIBILITY_DESCRIPTORS
    }
    assert by_responsibility[R.DETERMINISTIC_VALIDATION].owner_agent is None
    assert by_responsibility[R.PROMOTION].owner_agent is None
    assert by_responsibility[R.DETERMINISTIC_VALIDATION].allowed_capability_classes == (
        CapabilityClass.APPLICATION_ACTION,
    )
    assert by_responsibility[R.PROMOTION].allowed_capability_classes == (
        CapabilityClass.APPLICATION_ACTION,
    )


def test_runtime_control_responsibilities_are_descriptive_orchestration_metadata() -> None:
    by_responsibility = {
        item.responsibility: item for item in BASELINE_WORKFLOW_RESPONSIBILITY_DESCRIPTORS
    }
    for responsibility in (R.EVIDENCE_JOIN, R.VARIANT_JOIN, R.VARIANT_SELECTION, R.GATE):
        descriptor = by_responsibility[responsibility]
        assert descriptor.owner_agent is None
        assert descriptor.allowed_capability_classes == (CapabilityClass.ORCHESTRATION,)


def test_direct_application_allows_read_and_application_action_classes() -> None:
    descriptor = next(
        item
        for item in BASELINE_WORKFLOW_RESPONSIBILITY_DESCRIPTORS
        if item.responsibility is R.DIRECT_APPLICATION
    )
    assert descriptor.owner_agent is None
    assert descriptor.allowed_capability_classes == (
        CapabilityClass.READ,
        CapabilityClass.APPLICATION_ACTION,
    )


def test_descriptors_are_hashable_frozen_and_collections_are_immutable() -> None:
    descriptor = BASELINE_WORKFLOW_CATALOG.get(WorkflowKind.WF_6)
    assert hash(descriptor)
    assert isinstance(descriptor.required_responsibilities, tuple)
    assert isinstance(descriptor.ordering_constraints, tuple)
    with pytest.raises(FrozenInstanceError):
        descriptor.overlay = True  # type: ignore[misc]
    with pytest.raises(TypeError):
        BASELINE_WORKFLOW_CATALOG._by_kind[WorkflowKind.WF_0] = descriptor  # type: ignore[index]
