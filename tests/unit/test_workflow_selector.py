from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from backend.agent_runtime.orchestration import (
    BASELINE_WORKFLOW_CATALOG,
    WorkflowCatalog,
    WorkflowKind,
    WorkflowRequirements,
    WorkflowResponsibility,
    WorkflowSelectionDecision,
    WorkflowSelectionError,
    WorkflowSelectionReason,
    WorkflowSelectionStage,
    WorkflowSelectionStatus,
    WorkflowSelector,
    WorkflowTopologyDescriptor,
)

R = WorkflowResponsibility
Reason = WorkflowSelectionReason


def _select(**requirements: object) -> WorkflowSelectionDecision:
    return WorkflowSelector().select(WorkflowRequirements(**requirements))  # type: ignore[arg-type]


def _kinds(decision: WorkflowSelectionDecision) -> tuple[WorkflowKind, ...]:
    return tuple(stage.workflow_kind for stage in decision.stages)


def test_selection_status_vocabulary_is_exact() -> None:
    assert [item.value for item in WorkflowSelectionStatus] == [
        "selected",
        "waiting_human",
    ]


def test_selection_reason_vocabulary_is_exact() -> None:
    assert [item.value for item in WorkflowSelectionReason] == [
        "DIRECT_APPLICATION_REQUIRED",
        "EVIDENCE_REQUIRED",
        "GENERATION_REQUIRED",
        "REVIEW_REQUIRED",
        "CORRECTION_REQUIRED",
        "DETERMINISTIC_VALIDATION_REQUIRED",
        "PARALLEL_EVIDENCE_ADMISSIBLE",
        "PARALLEL_EVIDENCE_NOT_ADMISSIBLE",
        "VARIANTS_EXPLICITLY_USEFUL",
        "HUMAN_GATE_REQUIRED",
        "BLOCKING_AMBIGUITY",
        "PROMOTION_REQUIRED",
        "MINIMAL_CANONICAL_PATH",
    ]


@pytest.mark.parametrize(
    "field_name",
    [
        "application_action_required",
        "external_evidence_required",
        "production_required",
        "independent_review_required",
        "deterministic_validation_required",
        "correction_required",
        "promotion_required",
        "human_gate_required",
        "blocking_ambiguity",
        "parallel_evidence_independent",
        "variants_explicitly_useful",
    ],
)
def test_requirements_boolean_fields_are_strict(field_name: str) -> None:
    values: dict[str, object] = {"application_action_required": True, field_name: 1}
    with pytest.raises(TypeError, match=field_name):
        WorkflowRequirements(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize("field_name", ["parallel_evidence_branches", "variant_count"])
@pytest.mark.parametrize("invalid", [True, 1.5, "2"])
def test_requirement_counts_are_strict_integers(field_name: str, invalid: object) -> None:
    with pytest.raises(TypeError, match=field_name):
        WorkflowRequirements(
            application_action_required=True,
            **{field_name: invalid},  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("field_name", ["parallel_evidence_branches", "variant_count"])
def test_requirement_counts_cannot_be_negative(field_name: str) -> None:
    with pytest.raises(ValueError, match=">= 0"):
        WorkflowRequirements(
            application_action_required=True,
            **{field_name: -1},  # type: ignore[arg-type]
        )


def test_correction_and_production_are_distinct_exclusive_modes() -> None:
    with pytest.raises(ValueError, match="mutually exclusive"):
        WorkflowRequirements(correction_required=True, production_required=True)


def test_evidence_branch_count_requires_external_evidence() -> None:
    with pytest.raises(ValueError, match="require external evidence"):
        WorkflowRequirements(application_action_required=True, parallel_evidence_branches=1)


@pytest.mark.parametrize("branch_count", [0, 1])
def test_independent_parallel_evidence_requires_at_least_two_branches(
    branch_count: int,
) -> None:
    with pytest.raises(ValueError, match="at least two branches"):
        WorkflowRequirements(
            external_evidence_required=True,
            parallel_evidence_branches=branch_count,
            parallel_evidence_independent=True,
        )


def test_variant_count_requires_production() -> None:
    with pytest.raises(ValueError, match="variants require production"):
        WorkflowRequirements(application_action_required=True, variant_count=1)


def test_multiple_variants_must_be_explicitly_useful() -> None:
    with pytest.raises(ValueError, match="explicitly useful"):
        WorkflowRequirements(production_required=True, variant_count=2)


@pytest.mark.parametrize("variant_count", [0, 1])
def test_explicitly_useful_variants_require_plurality(variant_count: int) -> None:
    with pytest.raises(ValueError, match="at least two variants"):
        WorkflowRequirements(
            production_required=True,
            variant_count=variant_count,
            variants_explicitly_useful=True,
        )


def test_blocking_ambiguity_requires_human_gate() -> None:
    with pytest.raises(ValueError, match="requires a human gate"):
        WorkflowRequirements(blocking_ambiguity=True)


def test_empty_requirements_are_refused() -> None:
    with pytest.raises(ValueError, match="substantive"):
        WorkflowRequirements()


def test_blocking_ambiguity_waits_without_selecting_business_work() -> None:
    decision = _select(
        human_gate_required=True,
        blocking_ambiguity=True,
        external_evidence_required=True,
        production_required=True,
        independent_review_required=True,
    )
    assert decision.status is WorkflowSelectionStatus.WAITING_HUMAN
    assert decision.stages == ()
    assert decision.overlays == (WorkflowKind.WF_10,)
    assert decision.reasons == (Reason.BLOCKING_AMBIGUITY, Reason.HUMAN_GATE_REQUIRED)


@pytest.mark.parametrize(
    ("requirements", "expected"),
    [
        ({"application_action_required": True}, (WorkflowKind.WF_0,)),
        ({"deterministic_validation_required": True}, (WorkflowKind.WF_0,)),
        ({"external_evidence_required": True}, (WorkflowKind.WF_1,)),
        ({"production_required": True}, (WorkflowKind.WF_2,)),
        ({"independent_review_required": True}, (WorkflowKind.WF_3,)),
        (
            {"external_evidence_required": True, "production_required": True},
            (WorkflowKind.WF_4,),
        ),
        (
            {"production_required": True, "independent_review_required": True},
            (WorkflowKind.WF_5,),
        ),
        (
            {
                "external_evidence_required": True,
                "production_required": True,
                "independent_review_required": True,
            },
            (WorkflowKind.WF_6,),
        ),
    ],
)
def test_simple_requirements_use_the_minimal_canonical_mapping(
    requirements: dict[str, object], expected: tuple[WorkflowKind, ...]
) -> None:
    decision = _select(**requirements)
    assert decision.status is WorkflowSelectionStatus.SELECTED
    assert _kinds(decision) == expected
    assert decision.reasons[-1] is Reason.MINIMAL_CANONICAL_PATH


@pytest.mark.parametrize(
    ("requirements", "kind"),
    [
        ({"production_required": True}, WorkflowKind.WF_2),
        (
            {"external_evidence_required": True, "production_required": True},
            WorkflowKind.WF_4,
        ),
        (
            {"production_required": True, "independent_review_required": True},
            WorkflowKind.WF_5,
        ),
    ],
)
def test_validation_materializes_only_the_supported_optional_responsibility(
    requirements: dict[str, object], kind: WorkflowKind
) -> None:
    decision = _select(**requirements, deterministic_validation_required=True)
    assert _kinds(decision) == (kind,)
    assert decision.stages[0].materialized_optional_responsibilities == (
        R.DETERMINISTIC_VALIDATION,
    )


def test_wf6_does_not_duplicate_its_required_validation() -> None:
    decision = _select(
        external_evidence_required=True,
        production_required=True,
        independent_review_required=True,
        deterministic_validation_required=True,
    )
    assert _kinds(decision) == (WorkflowKind.WF_6,)
    assert decision.stages[0].materialized_optional_responsibilities == ()


def test_existing_artifact_validation_precedes_independent_review() -> None:
    decision = _select(
        independent_review_required=True,
        deterministic_validation_required=True,
    )
    assert _kinds(decision) == (WorkflowKind.WF_0, WorkflowKind.WF_3)


@pytest.mark.parametrize("branch_count", [2, 4])
def test_independent_parallel_evidence_selects_wf8(branch_count: int) -> None:
    decision = _select(
        external_evidence_required=True,
        parallel_evidence_branches=branch_count,
        parallel_evidence_independent=True,
    )
    assert _kinds(decision) == (WorkflowKind.WF_8,)
    assert Reason.PARALLEL_EVIDENCE_ADMISSIBLE in decision.reasons


def test_non_independent_parallel_evidence_falls_back_to_sequential_wf1() -> None:
    decision = _select(
        external_evidence_required=True,
        parallel_evidence_branches=2,
    )
    assert _kinds(decision) == (WorkflowKind.WF_1,)
    assert Reason.PARALLEL_EVIDENCE_NOT_ADMISSIBLE in decision.reasons


@pytest.mark.parametrize(
    ("review", "continuation"),
    [(False, WorkflowKind.WF_4), (True, WorkflowKind.WF_6)],
)
def test_parallel_evidence_join_hands_off_to_the_composite_continuation(
    review: bool, continuation: WorkflowKind
) -> None:
    decision = _select(
        external_evidence_required=True,
        parallel_evidence_branches=3,
        parallel_evidence_independent=True,
        production_required=True,
        independent_review_required=review,
    )
    assert _kinds(decision) == (WorkflowKind.WF_8, continuation)


def test_non_independent_evidence_does_not_add_a_redundant_wf1_before_wf4() -> None:
    decision = _select(
        external_evidence_required=True,
        parallel_evidence_branches=2,
        production_required=True,
    )
    assert _kinds(decision) == (WorkflowKind.WF_4,)
    assert Reason.PARALLEL_EVIDENCE_NOT_ADMISSIBLE in decision.reasons


def test_correction_selects_acyclic_wf7_without_review_by_default() -> None:
    decision = _select(correction_required=True)
    assert _kinds(decision) == (WorkflowKind.WF_7,)
    assert decision.stages[0].materialized_optional_responsibilities == ()
    assert Reason.CORRECTION_REQUIRED in decision.reasons


def test_correction_materializes_independent_review_inside_wf7() -> None:
    decision = _select(correction_required=True, independent_review_required=True)
    assert _kinds(decision) == (WorkflowKind.WF_7,)
    assert decision.stages[0].materialized_optional_responsibilities == (R.REVIEW,)


@pytest.mark.parametrize(
    ("parallel", "expected_evidence"),
    [(False, WorkflowKind.WF_1), (True, WorkflowKind.WF_8)],
)
def test_evidence_precedes_correction(
    parallel: bool, expected_evidence: WorkflowKind
) -> None:
    decision = _select(
        external_evidence_required=True,
        parallel_evidence_branches=2 if parallel else 0,
        parallel_evidence_independent=parallel,
        correction_required=True,
    )
    assert _kinds(decision) == (expected_evidence, WorkflowKind.WF_7)


def test_correction_validation_uses_an_application_stage_without_mutating_wf7() -> None:
    decision = _select(correction_required=True, deterministic_validation_required=True)
    assert _kinds(decision) == (WorkflowKind.WF_7, WorkflowKind.WF_0)
    assert decision.stages[0].materialized_optional_responsibilities == ()


def test_useful_variant_plurality_selects_one_wf9_stage() -> None:
    decision = _select(
        production_required=True,
        variant_count=3,
        variants_explicitly_useful=True,
    )
    assert _kinds(decision) == (WorkflowKind.WF_9,)
    assert Reason.VARIANTS_EXPLICITLY_USEFUL in decision.reasons


@pytest.mark.parametrize(
    ("parallel", "expected_evidence"),
    [(False, WorkflowKind.WF_1), (True, WorkflowKind.WF_8)],
)
def test_evidence_precedes_variant_generation(
    parallel: bool, expected_evidence: WorkflowKind
) -> None:
    decision = _select(
        external_evidence_required=True,
        parallel_evidence_branches=2 if parallel else 0,
        parallel_evidence_independent=parallel,
        production_required=True,
        variant_count=3,
        variants_explicitly_useful=True,
    )
    assert _kinds(decision) == (expected_evidence, WorkflowKind.WF_9)


@pytest.mark.parametrize(
    ("validation", "review", "expected"),
    [
        (False, True, (WorkflowKind.WF_9, WorkflowKind.WF_3)),
        (True, False, (WorkflowKind.WF_9, WorkflowKind.WF_0)),
        (
            True,
            True,
            (WorkflowKind.WF_9, WorkflowKind.WF_0, WorkflowKind.WF_3),
        ),
    ],
)
def test_variant_post_selection_validation_and_review_are_ordered(
    validation: bool,
    review: bool,
    expected: tuple[WorkflowKind, ...],
) -> None:
    decision = _select(
        production_required=True,
        variant_count=3,
        variants_explicitly_useful=True,
        deterministic_validation_required=validation,
        independent_review_required=review,
    )
    assert _kinds(decision) == expected


def test_non_blocking_human_gate_is_an_overlay_on_the_selected_base() -> None:
    decision = _select(production_required=True, human_gate_required=True)
    assert _kinds(decision) == (WorkflowKind.WF_2,)
    assert decision.overlays == (WorkflowKind.WF_10,)
    assert Reason.HUMAN_GATE_REQUIRED in decision.reasons


def test_wf10_is_absent_without_an_explicit_human_gate() -> None:
    decision = _select(production_required=True)
    assert decision.overlays == ()
    assert WorkflowKind.WF_10 not in _kinds(decision)


@pytest.mark.parametrize(
    ("requirements", "expected"),
    [
        ({"promotion_required": True}, (WorkflowKind.WF_11,)),
        (
            {"production_required": True, "promotion_required": True},
            (WorkflowKind.WF_2, WorkflowKind.WF_11),
        ),
        (
            {
                "external_evidence_required": True,
                "production_required": True,
                "independent_review_required": True,
                "promotion_required": True,
            },
            (WorkflowKind.WF_6, WorkflowKind.WF_11),
        ),
        (
            {"correction_required": True, "promotion_required": True},
            (WorkflowKind.WF_7, WorkflowKind.WF_11),
        ),
    ],
)
def test_promotion_appends_wf11_exactly_once_as_the_last_stage(
    requirements: dict[str, object], expected: tuple[WorkflowKind, ...]
) -> None:
    decision = _select(**requirements)
    kinds = _kinds(decision)
    assert kinds == expected
    assert kinds[-1] is WorkflowKind.WF_11
    assert kinds.count(WorkflowKind.WF_11) == 1
    assert Reason.PROMOTION_REQUIRED in decision.reasons


def test_direct_application_can_precede_terminal_promotion_without_agentic_work() -> None:
    decision = _select(application_action_required=True, promotion_required=True)
    assert _kinds(decision) == (WorkflowKind.WF_0, WorkflowKind.WF_11)


@pytest.mark.parametrize(
    "agentic_requirement",
    [
        {"external_evidence_required": True},
        {"production_required": True},
        {"independent_review_required": True},
        {"correction_required": True},
    ],
)
def test_generic_application_action_cannot_be_hidden_after_agentic_work(
    agentic_requirement: dict[str, object],
) -> None:
    with pytest.raises(WorkflowSelectionError, match="must be normalized"):
        _select(application_action_required=True, **agentic_requirement)


def test_human_gate_cannot_be_selected_as_a_standalone_engine() -> None:
    with pytest.raises(WorkflowSelectionError, match="base workflow"):
        _select(human_gate_required=True)


@pytest.mark.parametrize(
    ("requirements", "forbidden"),
    [
        ({"production_required": True}, {WorkflowKind.WF_1, WorkflowKind.WF_8}),
        ({"external_evidence_required": True}, {WorkflowKind.WF_2, WorkflowKind.WF_9}),
        ({"production_required": True}, {WorkflowKind.WF_3, WorkflowKind.WF_5}),
        (
            {"external_evidence_required": True, "production_required": True},
            {WorkflowKind.WF_6},
        ),
        (
            {"production_required": True, "independent_review_required": True},
            {WorkflowKind.WF_6},
        ),
        ({"production_required": True}, {WorkflowKind.WF_10, WorkflowKind.WF_11}),
    ],
)
def test_selector_does_not_over_orchestrate(
    requirements: dict[str, object], forbidden: set[WorkflowKind]
) -> None:
    assert not set(_kinds(_select(**requirements))) & forbidden


def test_reason_order_is_deterministic_and_contains_only_explicit_facts() -> None:
    requirements = {
        "production_required": True,
        "independent_review_required": True,
        "deterministic_validation_required": True,
        "human_gate_required": True,
        "promotion_required": True,
    }
    first = _select(**requirements)
    second = _select(**requirements)
    assert first == second
    assert first.reasons == (
        Reason.GENERATION_REQUIRED,
        Reason.REVIEW_REQUIRED,
        Reason.DETERMINISTIC_VALIDATION_REQUIRED,
        Reason.HUMAN_GATE_REQUIRED,
        Reason.PROMOTION_REQUIRED,
        Reason.MINIMAL_CANONICAL_PATH,
    )


def test_selector_rejects_an_untyped_requirements_input() -> None:
    with pytest.raises(WorkflowSelectionError, match="WorkflowRequirements"):
        WorkflowSelector().select({"production_required": True})  # type: ignore[arg-type]


def test_selector_rejects_a_catalog_missing_a_required_workflow() -> None:
    catalog = WorkflowCatalog((BASELINE_WORKFLOW_CATALOG.get(WorkflowKind.WF_0),))
    with pytest.raises(WorkflowSelectionError, match="missing required workflow WF-2"):
        WorkflowSelector(catalog).select(WorkflowRequirements(production_required=True))


def test_selector_rejects_optional_responsibility_incompatible_with_catalog() -> None:
    incompatible = WorkflowTopologyDescriptor(
        workflow_kind=WorkflowKind.WF_2,
        canonical_name="Generation without optional validation",
        purpose="Exercise catalogue compatibility checks.",
        required_responsibilities=(R.GENERATE_TRANSFORM,),
    )
    with pytest.raises(WorkflowSelectionError, match="incompatible with WF-2"):
        WorkflowSelector(WorkflowCatalog((incompatible,))).select(
            WorkflowRequirements(
                production_required=True,
                deterministic_validation_required=True,
            )
        )


def test_selection_stage_requires_typed_unique_tuple_values() -> None:
    with pytest.raises(TypeError, match="workflow_kind"):
        WorkflowSelectionStage("WF-2")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="must be a tuple"):
        WorkflowSelectionStage(WorkflowKind.WF_2, [R.DETERMINISTIC_VALIDATION])  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="must be unique"):
        WorkflowSelectionStage(
            WorkflowKind.WF_2,
            (R.DETERMINISTIC_VALIDATION, R.DETERMINISTIC_VALIDATION),
        )


def test_selected_decision_requires_nonempty_stages() -> None:
    with pytest.raises(ValueError, match="SELECTED"):
        WorkflowSelectionDecision(
            WorkflowSelectionStatus.SELECTED,
            (),
            (),
            (Reason.MINIMAL_CANONICAL_PATH,),
        )


@pytest.mark.parametrize(
    ("stages", "overlays"),
    [
        ((WorkflowSelectionStage(WorkflowKind.WF_2),), (WorkflowKind.WF_10,)),
        ((), ()),
        ((), (WorkflowKind.WF_10, WorkflowKind.WF_10)),
    ],
)
def test_waiting_human_decision_requires_its_exact_shape(
    stages: tuple[WorkflowSelectionStage, ...], overlays: tuple[WorkflowKind, ...]
) -> None:
    with pytest.raises(ValueError):
        WorkflowSelectionDecision(
            WorkflowSelectionStatus.WAITING_HUMAN,
            stages,
            overlays,
            (Reason.BLOCKING_AMBIGUITY,),
        )


def test_decision_overlays_may_contain_only_wf10() -> None:
    with pytest.raises(ValueError, match="only WF-10"):
        WorkflowSelectionDecision(
            WorkflowSelectionStatus.SELECTED,
            (WorkflowSelectionStage(WorkflowKind.WF_2),),
            (WorkflowKind.WF_11,),
            (Reason.MINIMAL_CANONICAL_PATH,),
        )


@pytest.mark.parametrize(
    ("field_name", "invalid"),
    [
        ("stages", [WorkflowSelectionStage(WorkflowKind.WF_2)]),
        ("overlays", [WorkflowKind.WF_10]),
        ("reasons", [Reason.MINIMAL_CANONICAL_PATH]),
    ],
)
def test_decision_collections_must_be_strict_tuples(
    field_name: str, invalid: object
) -> None:
    values: dict[str, object] = {
        "status": WorkflowSelectionStatus.SELECTED,
        "stages": (WorkflowSelectionStage(WorkflowKind.WF_2),),
        "overlays": (),
        "reasons": (Reason.MINIMAL_CANONICAL_PATH,),
        field_name: invalid,
    }
    with pytest.raises(TypeError, match=field_name):
        WorkflowSelectionDecision(**values)  # type: ignore[arg-type]


def test_decision_refuses_duplicate_reasons_and_identical_adjacent_stages() -> None:
    stage = WorkflowSelectionStage(WorkflowKind.WF_2)
    with pytest.raises(ValueError, match="reasons must be unique"):
        WorkflowSelectionDecision(
            WorkflowSelectionStatus.SELECTED,
            (stage,),
            (),
            (Reason.GENERATION_REQUIRED, Reason.GENERATION_REQUIRED),
        )
    with pytest.raises(ValueError, match="adjacent"):
        WorkflowSelectionDecision(
            WorkflowSelectionStatus.SELECTED,
            (stage, stage),
            (),
            (Reason.MINIMAL_CANONICAL_PATH,),
        )


def test_selection_models_and_collections_are_immutable() -> None:
    requirements = WorkflowRequirements(production_required=True)
    decision = WorkflowSelector().select(requirements)
    assert hash(requirements)
    assert hash(decision)
    assert isinstance(decision.stages, tuple)
    assert isinstance(decision.overlays, tuple)
    assert isinstance(decision.reasons, tuple)
    with pytest.raises(FrozenInstanceError):
        requirements.production_required = False  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        decision.stages = ()  # type: ignore[misc]


def test_single_variant_uses_normal_generation_instead_of_wf9() -> None:
    decision = _select(production_required=True, variant_count=1)
    assert _kinds(decision) == (WorkflowKind.WF_2,)
    assert Reason.VARIANTS_EXPLICITLY_USEFUL not in decision.reasons


def test_catalog_validation_is_repeated_for_every_selected_stage() -> None:
    descriptors = tuple(
        BASELINE_WORKFLOW_CATALOG.get(kind)
        for kind in (WorkflowKind.WF_9, WorkflowKind.WF_0)
    )
    selector = WorkflowSelector(WorkflowCatalog(descriptors))
    requirements = WorkflowRequirements(
        production_required=True,
        independent_review_required=True,
        deterministic_validation_required=True,
        variant_count=2,
        variants_explicitly_useful=True,
    )
    with pytest.raises(WorkflowSelectionError, match="missing required workflow WF-3"):
        selector.select(requirements)


def test_replacing_a_decision_cannot_bypass_shape_invariants() -> None:
    decision = _select(production_required=True)
    with pytest.raises(ValueError, match="SELECTED"):
        replace(decision, stages=())
