from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from backend.agent_runtime.contracts import (
    BudgetSpec,
    ExecutorKind,
    FailurePolicy,
    StepKind,
)
from backend.agent_runtime.orchestration import (
    HumanGateAnchor,
    HumanGateBinding,
    PlanCompilationCode,
    PlanCompilationError,
    PlanCompilationRequest,
    PlanCompiler,
    PlanStepBinding,
    WorkflowKind,
    WorkflowResponsibility,
    WorkflowSelectionDecision,
    WorkflowSelectionReason,
    WorkflowSelectionStage,
    WorkflowSelectionStatus,
)
from backend.agent_runtime.runtime import (
    Plan,
    PlanValidationCode,
    PlanValidationIssue,
    PlanValidationResult,
    PlanValidator,
)
from backend.core_contracts.capability import CapabilityId

R = WorkflowResponsibility
Code = PlanCompilationCode

_CAPABILITY = {
    R.DIRECT_APPLICATION: "CAP-R01",
    R.EVIDENCE: "CAP-E01",
    R.GENERATE_TRANSFORM: "CAP-G01",
    R.REVIEW: "CAP-V01",
    R.DETERMINISTIC_VALIDATION: "CAP-A01",
    R.CORRECTION: "CAP-G03",
    R.EVIDENCE_JOIN: None,
    R.VARIANT_GENERATION: "CAP-G01",
    R.VARIANT_JOIN: None,
    R.VARIANT_SELECTION: None,
    R.GATE: None,
    R.PROMOTION: "CAP-A02",
}

_REQUIRED = {
    WorkflowKind.WF_0: (R.DIRECT_APPLICATION,),
    WorkflowKind.WF_1: (R.EVIDENCE,),
    WorkflowKind.WF_2: (R.GENERATE_TRANSFORM,),
    WorkflowKind.WF_3: (R.REVIEW,),
    WorkflowKind.WF_4: (R.EVIDENCE, R.GENERATE_TRANSFORM),
    WorkflowKind.WF_5: (R.GENERATE_TRANSFORM, R.REVIEW),
    WorkflowKind.WF_6: (
        R.EVIDENCE,
        R.GENERATE_TRANSFORM,
        R.DETERMINISTIC_VALIDATION,
        R.REVIEW,
    ),
    WorkflowKind.WF_7: (R.CORRECTION,),
    WorkflowKind.WF_8: (R.EVIDENCE, R.EVIDENCE_JOIN),
    WorkflowKind.WF_9: (R.VARIANT_GENERATION, R.VARIANT_JOIN, R.VARIANT_SELECTION),
    WorkflowKind.WF_11: (R.DETERMINISTIC_VALIDATION, R.GATE, R.PROMOTION),
}


def _selection(
    *kinds: WorkflowKind,
    optional: dict[int, tuple[R, ...]] | None = None,
    overlay: bool = False,
) -> WorkflowSelectionDecision:
    optional = optional or {}
    return WorkflowSelectionDecision(
        status=WorkflowSelectionStatus.SELECTED,
        stages=tuple(
            WorkflowSelectionStage(kind, optional.get(index, ()))
            for index, kind in enumerate(kinds)
        ),
        overlays=(WorkflowKind.WF_10,) if overlay else (),
        reasons=(WorkflowSelectionReason.MINIMAL_CANONICAL_PATH,),
    )


def _waiting_selection() -> WorkflowSelectionDecision:
    return WorkflowSelectionDecision(
        WorkflowSelectionStatus.WAITING_HUMAN,
        (),
        (WorkflowKind.WF_10,),
        (
            WorkflowSelectionReason.BLOCKING_AMBIGUITY,
            WorkflowSelectionReason.HUMAN_GATE_REQUIRED,
        ),
    )


def _binding(
    stage_index: int,
    responsibility: R,
    suffix: str = "0",
    *,
    branch_index: int | None = None,
    capability: str | None | object = ...,
    scope: str | None | object = ...,
    budget: BudgetSpec | None = None,
) -> PlanStepBinding:
    capability_value = _CAPABILITY[responsibility] if capability is ... else capability
    executable = responsibility in {
        R.DIRECT_APPLICATION,
        R.EVIDENCE,
        R.GENERATE_TRANSFORM,
        R.REVIEW,
        R.DETERMINISTIC_VALIDATION,
        R.CORRECTION,
        R.VARIANT_GENERATION,
        R.PROMOTION,
    }
    scope_value = "scope-1" if scope is ... and executable else scope
    if scope is ... and not executable:
        scope_value = None
    return PlanStepBinding(
        stage_index=stage_index,
        responsibility=responsibility,
        step_id=f"s{stage_index}-{responsibility.value.lower()}-{suffix}",
        objective=f"Materialize {responsibility.value}",
        capability_id=(
            CapabilityId(capability_value)
            if isinstance(capability_value, str)
            else capability_value
        ),
        permission_scope_ref=scope_value,  # type: ignore[arg-type]
        budget=budget,
        output_contract={"type": "result"},
        branch_index=branch_index,
    )


def _bindings_for(
    selection: WorkflowSelectionDecision,
    *,
    branches: int = 2,
    wf0_operations: int = 1,
) -> tuple[PlanStepBinding, ...]:
    bindings: list[PlanStepBinding] = []
    for index, stage in enumerate(selection.stages):
        responsibilities = list(_REQUIRED[stage.workflow_kind])
        responsibilities.extend(stage.materialized_optional_responsibilities)
        if (
            index > 0
            and selection.stages[index - 1].workflow_kind is WorkflowKind.WF_8
            and stage.workflow_kind in (WorkflowKind.WF_4, WorkflowKind.WF_6)
        ):
            responsibilities.remove(R.EVIDENCE)
        for responsibility in responsibilities:
            if stage.workflow_kind is WorkflowKind.WF_0:
                bindings.extend(
                    _binding(index, responsibility, str(operation))
                    for operation in range(wf0_operations)
                )
            elif responsibility in (R.EVIDENCE, R.VARIANT_GENERATION) and stage.workflow_kind in (
                WorkflowKind.WF_8,
                WorkflowKind.WF_9,
            ):
                bindings.extend(
                    _binding(
                        index,
                        responsibility,
                        str(branch),
                        branch_index=branch,
                    )
                    for branch in range(branches)
                )
            else:
                bindings.append(_binding(index, responsibility))
    return tuple(bindings)


def _human_gate(anchor: HumanGateAnchor) -> HumanGateBinding:
    return HumanGateBinding(
        step_id="human-gate",
        objective="Obtain explicit human approval",
        anchor=anchor,
        success_criteria={"decision": "recorded"},
        failure_policy=FailurePolicy.STOP,
        output_contract={"type": "gate-result"},
    )


def _request(
    selection: WorkflowSelectionDecision,
    bindings: tuple[PlanStepBinding, ...] | None = None,
    *,
    human_gate: HumanGateBinding | None = None,
    budget_envelope: BudgetSpec | None = None,
) -> PlanCompilationRequest:
    return PlanCompilationRequest(
        selection=selection,
        plan_id="plan-1",
        run_id="run-1",
        plan_version=1,
        objective="Compile the explicit workflow",
        success_criteria={"complete": True},
        stop_conditions={"failure": "stop"},
        bindings=_bindings_for(selection) if bindings is None else bindings,
        human_gate=human_gate,
        gate_refs=("gate-ref-1",),
        budget_envelope=budget_envelope,
        risk_profile={"level": "bounded"},
        assumptions={"inputs": "provided"},
    )


def _step(plan: Plan, step_id: str):
    return next(step for step in plan.steps if step.step_id == step_id)


def _steps_for(plan: Plan, executor: ExecutorKind) -> tuple:
    return tuple(step for step in plan.steps if step.executor.kind is executor)


def test_compilation_vocabularies_are_exact() -> None:
    assert [item.value for item in HumanGateAnchor] == [
        "BEFORE_FIRST_STAGE",
        "AFTER_EVIDENCE",
        "AFTER_REVIEW",
        "BEFORE_PROMOTION",
    ]
    assert [item.value for item in PlanCompilationCode] == [
        "WAITING_HUMAN_NOT_COMPILABLE",
        "MISSING_STAGE_BINDING",
        "UNEXPECTED_STAGE_BINDING",
        "DUPLICATE_STEP_ID",
        "INVALID_BRANCH_CARDINALITY",
        "INVALID_BRANCH_INDEX",
        "CAPABILITY_REQUIRED",
        "CAPABILITY_NOT_ALLOWED",
        "PERMISSION_SCOPE_REQUIRED",
        "HUMAN_GATE_BINDING_REQUIRED",
        "HUMAN_GATE_BINDING_FORBIDDEN",
        "HUMAN_GATE_ANCHOR_UNAVAILABLE",
        "PLAN_VALIDATION_FAILED",
    ]


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("stage_index", True),
        ("responsibility", "EVIDENCE"),
        ("step_id", " "),
        ("objective", ""),
        ("capability_id", "CAP-E01"),
        ("input_refs", ["input-1"]),
        ("budget", object()),
        ("failure_policy", "stop"),
        ("branch_index", True),
    ],
)
def test_plan_step_binding_requires_strict_field_types(
    field_name: str, value: object
) -> None:
    values = {
        "stage_index": 0,
        "responsibility": R.EVIDENCE,
        "step_id": "evidence",
        "objective": "Collect evidence",
        "capability_id": CapabilityId("CAP-E01"),
        "permission_scope_ref": "scope-1",
        "input_refs": (),
        "budget": None,
        "failure_policy": FailurePolicy.STOP,
        "output_contract": {"type": "result"},
        "branch_index": None,
        field_name: value,
    }
    with pytest.raises((TypeError, ValueError)):
        PlanStepBinding(**values)  # type: ignore[arg-type]


def test_binding_indexes_and_output_contract_are_validated() -> None:
    with pytest.raises(ValueError, match=">= 0"):
        replace(_binding(0, R.EVIDENCE), stage_index=-1)
    with pytest.raises(ValueError, match=">= 0"):
        replace(_binding(0, R.EVIDENCE), branch_index=-1)
    with pytest.raises(ValueError, match="output_contract"):
        replace(_binding(0, R.EVIDENCE), output_contract={})


def test_binding_and_request_mappings_are_deeply_frozen() -> None:
    binding = _binding(0, R.EVIDENCE)
    request = _request(_selection(WorkflowKind.WF_1), (binding,))
    with pytest.raises(TypeError):
        binding.output_contract["new"] = True  # type: ignore[index]
    with pytest.raises(TypeError):
        request.success_criteria["new"] = True  # type: ignore[index]


def test_request_rejects_duplicate_step_ids_including_human_gate() -> None:
    selection = _selection(WorkflowKind.WF_1, overlay=True)
    binding = replace(_binding(0, R.EVIDENCE), step_id="human-gate")
    with pytest.raises(PlanCompilationError) as captured:
        _request(
            selection,
            (binding,),
            human_gate=_human_gate(HumanGateAnchor.BEFORE_FIRST_STAGE),
        )
    assert captured.value.code is Code.DUPLICATE_STEP_ID


def test_waiting_human_selection_is_not_compilable() -> None:
    request = PlanCompilationRequest(
        selection=_waiting_selection(),
        plan_id="plan-1",
        run_id="run-1",
        plan_version=1,
        objective="Wait for clarification",
        success_criteria={},
        stop_conditions={"waiting": True},
        bindings=(),
        human_gate=_human_gate(HumanGateAnchor.BEFORE_FIRST_STAGE),
    )
    with pytest.raises(PlanCompilationError) as captured:
        PlanCompiler().compile(request)
    assert captured.value.code is Code.WAITING_HUMAN_NOT_COMPILABLE


def test_overlay_and_human_gate_binding_must_correspond() -> None:
    overlay = _selection(WorkflowKind.WF_2, overlay=True)
    with pytest.raises(PlanCompilationError) as missing:
        PlanCompiler().compile(_request(overlay))
    assert missing.value.code is Code.HUMAN_GATE_BINDING_REQUIRED
    ordinary = _selection(WorkflowKind.WF_2)
    with pytest.raises(PlanCompilationError) as forbidden:
        PlanCompiler().compile(
            _request(
                ordinary,
                human_gate=_human_gate(HumanGateAnchor.BEFORE_FIRST_STAGE),
            )
        )
    assert forbidden.value.code is Code.HUMAN_GATE_BINDING_FORBIDDEN


@pytest.mark.parametrize(
    ("responsibility", "capability", "accepted"),
    [
        (R.EVIDENCE, "CAP-E01", True),
        (R.EVIDENCE, "CAP-G01", False),
        (R.GENERATE_TRANSFORM, "CAP-G02", True),
        (R.REVIEW, "CAP-V02", True),
        (R.DETERMINISTIC_VALIDATION, "CAP-A01", True),
        (R.DETERMINISTIC_VALIDATION, "CAP-A03", False),
        (R.CORRECTION, "CAP-G03", True),
        (R.CORRECTION, "CAP-G01", False),
        (R.PROMOTION, "CAP-A02", True),
        (R.PROMOTION, "CAP-A01", False),
    ],
)
def test_compiler_enforces_canonical_capability_class_owner_and_exact_ids(
    responsibility: R, capability: str, accepted: bool
) -> None:
    kind = {
        R.EVIDENCE: WorkflowKind.WF_1,
        R.GENERATE_TRANSFORM: WorkflowKind.WF_2,
        R.REVIEW: WorkflowKind.WF_3,
        R.DETERMINISTIC_VALIDATION: WorkflowKind.WF_11,
        R.CORRECTION: WorkflowKind.WF_7,
        R.PROMOTION: WorkflowKind.WF_11,
    }[responsibility]
    selection = _selection(kind)
    bindings = list(_bindings_for(selection))
    target = next(
        index
        for index, binding in enumerate(bindings)
        if binding.responsibility is responsibility
    )
    bindings[target] = replace(bindings[target], capability_id=CapabilityId(capability))
    if accepted:
        assert PlanCompiler().compile(_request(selection, tuple(bindings)))
    else:
        with pytest.raises(PlanCompilationError) as captured:
            PlanCompiler().compile(_request(selection, tuple(bindings)))
        assert captured.value.code is Code.CAPABILITY_NOT_ALLOWED


def test_capability_is_required_for_executable_responsibilities() -> None:
    selection = _selection(WorkflowKind.WF_1)
    binding = replace(_binding(0, R.EVIDENCE), capability_id=None)
    with pytest.raises(PlanCompilationError) as captured:
        PlanCompiler().compile(_request(selection, (binding,)))
    assert captured.value.code is Code.CAPABILITY_REQUIRED


def test_executable_scope_is_required_and_control_scope_is_forbidden() -> None:
    wf1 = _selection(WorkflowKind.WF_1)
    with pytest.raises(PlanCompilationError) as missing:
        PlanCompiler().compile(
            _request(wf1, (replace(_binding(0, R.EVIDENCE), permission_scope_ref=None),))
        )
    assert missing.value.code is Code.PERMISSION_SCOPE_REQUIRED
    wf8 = _selection(WorkflowKind.WF_8)
    bindings = list(_bindings_for(wf8))
    join_index = next(
        index for index, item in enumerate(bindings) if item.responsibility is R.EVIDENCE_JOIN
    )
    bindings[join_index] = replace(bindings[join_index], permission_scope_ref="scope-1")
    with pytest.raises(PlanCompilationError) as forbidden:
        PlanCompiler().compile(_request(wf8, tuple(bindings)))
    assert forbidden.value.code is Code.PERMISSION_SCOPE_REQUIRED


def test_wf0_supports_one_or_many_sequential_application_operations_only() -> None:
    selection = _selection(WorkflowKind.WF_0)
    single = PlanCompiler().compile(_request(selection))
    assert len(single.steps) == 1
    assert single.steps[0].kind is StepKind.USE_CASE
    assert single.steps[0].executor.kind is ExecutorKind.APPLICATION
    many = PlanCompiler().compile(
        _request(selection, _bindings_for(selection, wf0_operations=3))
    )
    assert [step.depends_on for step in many.steps] == [
        (),
        (many.steps[0].step_id,),
        (many.steps[1].step_id,),
    ]
    assert _steps_for(many, ExecutorKind.AG_02) == ()
    assert _steps_for(many, ExecutorKind.AG_03) == ()
    assert _steps_for(many, ExecutorKind.AG_04) == ()


@pytest.mark.parametrize(
    ("kind", "optional", "responsibilities"),
    [
        (WorkflowKind.WF_1, {}, (R.EVIDENCE,)),
        (WorkflowKind.WF_2, {}, (R.GENERATE_TRANSFORM,)),
        (
            WorkflowKind.WF_2,
            {0: (R.DETERMINISTIC_VALIDATION,)},
            (R.GENERATE_TRANSFORM, R.DETERMINISTIC_VALIDATION),
        ),
        (WorkflowKind.WF_3, {}, (R.REVIEW,)),
        (WorkflowKind.WF_4, {}, (R.EVIDENCE, R.GENERATE_TRANSFORM)),
        (
            WorkflowKind.WF_5,
            {},
            (R.GENERATE_TRANSFORM, R.REVIEW),
        ),
        (
            WorkflowKind.WF_5,
            {0: (R.DETERMINISTIC_VALIDATION,)},
            (R.GENERATE_TRANSFORM, R.REVIEW, R.DETERMINISTIC_VALIDATION),
        ),
        (
            WorkflowKind.WF_6,
            {},
            (R.EVIDENCE, R.GENERATE_TRANSFORM, R.DETERMINISTIC_VALIDATION, R.REVIEW),
        ),
        (WorkflowKind.WF_7, {}, (R.CORRECTION,)),
        (
            WorkflowKind.WF_7,
            {0: (R.REVIEW,)},
            (R.CORRECTION, R.REVIEW),
        ),
    ],
)
def test_wf1_through_wf7_expand_to_the_expected_acyclic_sequence(
    kind: WorkflowKind,
    optional: dict[int, tuple[R, ...]],
    responsibilities: tuple[R, ...],
) -> None:
    selection = _selection(kind, optional=optional)
    plan = PlanCompiler().compile(_request(selection))
    expected_order = {
        WorkflowKind.WF_5: (
            (R.GENERATE_TRANSFORM, R.DETERMINISTIC_VALIDATION, R.REVIEW)
            if optional
            else (R.GENERATE_TRANSFORM, R.REVIEW)
        )
    }.get(kind, responsibilities)
    by_id = {binding.step_id: binding.responsibility for binding in _bindings_for(selection)}
    assert tuple(by_id[step.step_id] for step in plan.steps) == expected_order
    for index, step in enumerate(plan.steps):
        assert step.depends_on == (() if index == 0 else (plan.steps[index - 1].step_id,))
    assert PlanValidator().validate(plan).valid


@pytest.mark.parametrize("branch_count", [2, 3])
def test_wf8_fanout_has_independent_ag02_branches_and_explicit_join(
    branch_count: int,
) -> None:
    selection = _selection(WorkflowKind.WF_8)
    plan = PlanCompiler().compile(
        _request(selection, _bindings_for(selection, branches=branch_count))
    )
    branches = _steps_for(plan, ExecutorKind.AG_02)
    join = next(step for step in plan.steps if step.kind is StepKind.JOIN)
    assert len(branches) == branch_count
    assert {step.parallel_group for step in branches} == {
        "plan-1:stage-0:WF-8"
    }
    assert all(step.depends_on == () for step in branches)
    assert join.depends_on == tuple(step.step_id for step in branches)
    assert join.capability_id == CapabilityId("CAP-O04")


@pytest.mark.parametrize("indexes", [(0,), (0, 2), (1, 2)])
def test_wf8_rejects_insufficient_or_noncontiguous_branches(
    indexes: tuple[int, ...]
) -> None:
    selection = _selection(WorkflowKind.WF_8)
    bindings = tuple(
        [
            _binding(0, R.EVIDENCE, str(index), branch_index=index)
            for index in indexes
        ]
        + [_binding(0, R.EVIDENCE_JOIN)]
    )
    with pytest.raises(PlanCompilationError) as captured:
        PlanCompiler().compile(_request(selection, bindings))
    assert captured.value.code in {
        Code.INVALID_BRANCH_CARDINALITY,
        Code.INVALID_BRANCH_INDEX,
    }


@pytest.mark.parametrize("branch_count", [2, 3])
def test_wf9_fanout_joins_variants_before_runtime_selection(branch_count: int) -> None:
    selection = _selection(WorkflowKind.WF_9)
    plan = PlanCompiler().compile(
        _request(selection, _bindings_for(selection, branches=branch_count))
    )
    variants = _steps_for(plan, ExecutorKind.AG_03)
    join = next(step for step in plan.steps if step.kind is StepKind.JOIN)
    decision = next(step for step in plan.steps if step.kind is StepKind.DECISION)
    assert len(variants) == branch_count
    assert len({step.parallel_group for step in variants}) == 1
    assert all(step.depends_on == () for step in variants)
    assert join.depends_on == tuple(step.step_id for step in variants)
    assert decision.depends_on == (join.step_id,)
    assert decision.capability_id is None


@pytest.mark.parametrize("kind", [WorkflowKind.WF_8, WorkflowKind.WF_9])
def test_parallel_control_bindings_must_not_have_branch_indexes(kind: WorkflowKind) -> None:
    selection = _selection(kind)
    bindings = list(_bindings_for(selection))
    control_index = next(
        index
        for index, binding in enumerate(bindings)
        if binding.responsibility in (R.EVIDENCE_JOIN, R.VARIANT_JOIN)
    )
    bindings[control_index] = replace(bindings[control_index], branch_index=2)
    with pytest.raises(PlanCompilationError) as captured:
        PlanCompiler().compile(_request(selection, tuple(bindings)))
    assert captured.value.code is Code.INVALID_BRANCH_INDEX


def test_missing_and_unexpected_stage_bindings_are_refused() -> None:
    wf2 = _selection(WorkflowKind.WF_2)
    with pytest.raises(PlanCompilationError) as missing:
        PlanCompiler().compile(_request(wf2, (_binding(0, R.REVIEW),)))
    assert missing.value.code is Code.UNEXPECTED_STAGE_BINDING
    wf5 = _selection(WorkflowKind.WF_5)
    with pytest.raises(PlanCompilationError) as absent:
        PlanCompiler().compile(_request(wf5, (_binding(0, R.GENERATE_TRANSFORM),)))
    assert absent.value.code is Code.MISSING_STAGE_BINDING


def test_compiler_revalidates_materialized_optional_responsibilities() -> None:
    selection = _selection(
        WorkflowKind.WF_3,
        optional={0: (R.DETERMINISTIC_VALIDATION,)},
    )
    bindings = (
        _binding(0, R.REVIEW),
        _binding(0, R.DETERMINISTIC_VALIDATION),
    )
    with pytest.raises(PlanCompilationError) as captured:
        PlanCompiler().compile(_request(selection, bindings))
    assert captured.value.code is Code.UNEXPECTED_STAGE_BINDING


@pytest.mark.parametrize("continuation", [WorkflowKind.WF_4, WorkflowKind.WF_6])
def test_wf8_handoff_satisfies_continuation_evidence_without_extra_ag02(
    continuation: WorkflowKind,
) -> None:
    selection = _selection(WorkflowKind.WF_8, continuation)
    bindings = _bindings_for(selection, branches=3)
    plan = PlanCompiler().compile(_request(selection, bindings))
    evidence = _steps_for(plan, ExecutorKind.AG_02)
    join = next(step for step in plan.steps if step.kind is StepKind.JOIN)
    generation = next(
        step for step in plan.steps if step.executor.kind is ExecutorKind.AG_03
    )
    assert len(evidence) == 3
    assert generation.depends_on == (join.step_id,)
    if continuation is WorkflowKind.WF_6:
        validation = next(
            step for step in plan.steps if step.capability_id == CapabilityId("CAP-A01")
        )
        review = next(
            step for step in plan.steps if step.executor.kind is ExecutorKind.AG_04
        )
        assert validation.depends_on == (generation.step_id,)
        assert review.depends_on == (validation.step_id,)


def test_handoff_rejects_a_duplicate_evidence_binding_in_continuation() -> None:
    selection = _selection(WorkflowKind.WF_8, WorkflowKind.WF_4)
    bindings = (*_bindings_for(selection), _binding(1, R.EVIDENCE, "extra"))
    with pytest.raises(PlanCompilationError) as captured:
        PlanCompiler().compile(_request(selection, bindings))
    assert captured.value.code is Code.UNEXPECTED_STAGE_BINDING


@pytest.mark.parametrize(
    ("kinds", "terminal_executor"),
    [
        ((WorkflowKind.WF_8, WorkflowKind.WF_7), ExecutorKind.AG_03),
        ((WorkflowKind.WF_8, WorkflowKind.WF_9), ExecutorKind.RUNTIME),
        (
            (WorkflowKind.WF_9, WorkflowKind.WF_0, WorkflowKind.WF_3),
            ExecutorKind.AG_04,
        ),
    ],
)
def test_interstage_handoffs_connect_roots_to_previous_terminals(
    kinds: tuple[WorkflowKind, ...], terminal_executor: ExecutorKind
) -> None:
    selection = _selection(*kinds)
    plan = PlanCompiler().compile(_request(selection, _bindings_for(selection, branches=3)))
    for index in range(1, len(selection.stages)):
        stage_ids = {
            binding.step_id
            for binding in _bindings_for(selection, branches=3)
            if binding.stage_index == index
        }
        first = next(step for step in plan.steps if step.step_id in stage_ids)
        assert first.depends_on
    assert plan.steps[-1].executor.kind is terminal_executor


def test_wf11_is_validation_policy_gate_then_terminal_promotion() -> None:
    selection = _selection(WorkflowKind.WF_11)
    plan = PlanCompiler().compile(_request(selection))
    validation, gate, promotion = plan.steps
    assert validation.capability_id == CapabilityId("CAP-A01")
    assert gate.kind is StepKind.GATE
    assert gate.capability_id == CapabilityId("CAP-O05")
    assert promotion.capability_id == CapabilityId("CAP-A02")
    assert gate.depends_on == (validation.step_id,)
    assert promotion.depends_on == (gate.step_id,)
    assert PlanValidator().validate(plan).valid


@pytest.mark.parametrize(
    ("anchor", "kinds"),
    [
        (HumanGateAnchor.BEFORE_FIRST_STAGE, (WorkflowKind.WF_2,)),
        (HumanGateAnchor.AFTER_EVIDENCE, (WorkflowKind.WF_4,)),
        (HumanGateAnchor.AFTER_EVIDENCE, (WorkflowKind.WF_8, WorkflowKind.WF_4)),
        (HumanGateAnchor.AFTER_REVIEW, (WorkflowKind.WF_5,)),
        (
            HumanGateAnchor.BEFORE_PROMOTION,
            (WorkflowKind.WF_5, WorkflowKind.WF_11),
        ),
    ],
)
def test_wf10_human_gate_anchor_rewires_only_the_requested_cut(
    anchor: HumanGateAnchor, kinds: tuple[WorkflowKind, ...]
) -> None:
    selection = _selection(*kinds, overlay=True)
    plan = PlanCompiler().compile(
        _request(
            selection,
            _bindings_for(selection),
            human_gate=_human_gate(anchor),
        )
    )
    human = _step(plan, "human-gate")
    assert human.kind is StepKind.GATE
    assert human.capability_id == CapabilityId("CAP-O05")
    if anchor is HumanGateAnchor.BEFORE_FIRST_STAGE:
        assert human.depends_on == ()
        assert all(
            human.step_id in step.depends_on
            for step in plan.steps
            if step.executor.kind is ExecutorKind.AG_03
        )
    elif anchor is HumanGateAnchor.AFTER_EVIDENCE:
        predecessor = _step(plan, human.depends_on[0])
        if WorkflowKind.WF_8 in kinds:
            assert predecessor.kind is StepKind.JOIN
        else:
            assert predecessor.executor.kind is ExecutorKind.AG_02
    elif anchor is HumanGateAnchor.AFTER_REVIEW:
        assert _step(plan, human.depends_on[0]).executor.kind is ExecutorKind.AG_04
        assert plan.steps[-1] is human
    else:
        intrinsic_validation = next(
            step
            for step in plan.steps
            if step.capability_id == CapabilityId("CAP-A01")
        )
        assert intrinsic_validation.depends_on == (human.step_id,)
    assert PlanValidator().validate(plan).valid


@pytest.mark.parametrize(
    "anchor",
    [
        HumanGateAnchor.AFTER_EVIDENCE,
        HumanGateAnchor.AFTER_REVIEW,
        HumanGateAnchor.BEFORE_PROMOTION,
    ],
)
def test_unavailable_human_gate_anchor_is_refused(anchor: HumanGateAnchor) -> None:
    selection = _selection(WorkflowKind.WF_2, overlay=True)
    with pytest.raises(PlanCompilationError) as captured:
        PlanCompiler().compile(
            _request(selection, human_gate=_human_gate(anchor))
        )
    assert captured.value.code is Code.HUMAN_GATE_ANCHOR_UNAVAILABLE


def test_human_overlay_gate_and_wf11_policy_gate_remain_distinct() -> None:
    selection = _selection(WorkflowKind.WF_2, WorkflowKind.WF_11, overlay=True)
    plan = PlanCompiler().compile(
        _request(
            selection,
            human_gate=_human_gate(HumanGateAnchor.BEFORE_PROMOTION),
        )
    )
    gates = tuple(step for step in plan.steps if step.kind is StepKind.GATE)
    assert len(gates) == 2
    assert {step.step_id for step in gates} == {
        "human-gate",
        "s1-gate-0",
    }


@pytest.mark.parametrize(
    ("kinds", "overlay", "expected"),
    [
        ((WorkflowKind.WF_2,), False, "WF-2"),
        ((WorkflowKind.WF_8, WorkflowKind.WF_6), False, "WF-8+WF-6"),
        (
            (WorkflowKind.WF_9, WorkflowKind.WF_0, WorkflowKind.WF_3),
            False,
            "WF-9+WF-0+WF-3",
        ),
        ((WorkflowKind.WF_6,), True, "WF-6|overlay:WF-10"),
    ],
)
def test_plan_workflow_kind_has_stable_opaque_composition_convention(
    kinds: tuple[WorkflowKind, ...], overlay: bool, expected: str
) -> None:
    selection = _selection(*kinds, overlay=overlay)
    human = _human_gate(HumanGateAnchor.BEFORE_FIRST_STAGE) if overlay else None
    plan = PlanCompiler().compile(_request(selection, human_gate=human))
    assert plan.workflow_kind == expected


def test_plan_metadata_and_opaque_refs_are_transferred_without_resolution() -> None:
    request = _request(_selection(WorkflowKind.WF_2))
    plan = PlanCompiler().compile(request)
    assert plan.plan_id == request.plan_id
    assert plan.run_id == request.run_id
    assert plan.plan_version == request.plan_version
    assert plan.objective == request.objective
    assert plan.success_criteria == request.success_criteria
    assert plan.gate_refs == request.gate_refs
    assert plan.risk_profile == request.risk_profile
    assert plan.assumptions == request.assumptions
    assert plan.stop_conditions == request.stop_conditions


def test_explicit_step_budgets_are_not_allocated_or_divided() -> None:
    selection = _selection(WorkflowKind.WF_8)
    budget = BudgetSpec(max_tokens=10)
    bindings = tuple(
        replace(binding, budget=budget)
        for binding in _bindings_for(selection, branches=3)
    )
    plan = PlanCompiler().compile(
        _request(selection, bindings, budget_envelope=BudgetSpec(max_tokens=30))
    )
    assert [step.budget for step in _steps_for(plan, ExecutorKind.AG_02)] == [
        budget,
        budget,
        budget,
    ]


def test_final_plan_validator_is_called_and_invalid_plan_is_not_returned() -> None:
    calls: list[Plan] = []

    class RejectingValidator(PlanValidator):
        def validate(self, plan: Plan) -> PlanValidationResult:
            calls.append(plan)
            return PlanValidationResult(
                False,
                (
                    PlanValidationIssue(
                        PlanValidationCode.STEP_BUDGET_OUT_OF_ENVELOPE,
                        "safe validation issue",
                    ),
                    PlanValidationIssue(
                        PlanValidationCode.UNKNOWN_CAPABILITY,
                        "safe validation issue",
                    ),
                    PlanValidationIssue(
                        PlanValidationCode.UNKNOWN_CAPABILITY,
                        "duplicate safe issue",
                    ),
                ),
            )

    with pytest.raises(PlanCompilationError) as captured:
        PlanCompiler(validator=RejectingValidator()).compile(
            _request(_selection(WorkflowKind.WF_2))
        )
    assert len(calls) == 1
    assert captured.value.code is Code.PLAN_VALIDATION_FAILED
    assert str(captured.value) == (
        "plan validation failed: STEP_BUDGET_OUT_OF_ENVELOPE, UNKNOWN_CAPABILITY"
    )


def test_budget_narrowing_failure_is_reported_only_by_validation_code() -> None:
    selection = _selection(WorkflowKind.WF_2)
    binding = replace(
        _bindings_for(selection)[0], budget=BudgetSpec(max_tokens=11)
    )
    with pytest.raises(PlanCompilationError) as captured:
        PlanCompiler().compile(
            _request(
                selection,
                (binding,),
                budget_envelope=BudgetSpec(max_tokens=10),
            )
        )
    assert captured.value.code is Code.PLAN_VALIDATION_FAILED
    assert str(captured.value) == "plan validation failed: STEP_BUDGET_OUT_OF_ENVELOPE"


def test_compiled_step_order_is_deterministic_and_plan_is_frozen() -> None:
    selection = _selection(WorkflowKind.WF_8, WorkflowKind.WF_6)
    request = _request(selection, _bindings_for(selection, branches=3))
    first = PlanCompiler().compile(request)
    second = PlanCompiler().compile(request)
    assert first == second
    assert tuple(step.step_id for step in first.steps) == tuple(
        step.step_id for step in second.steps
    )
    with pytest.raises(FrozenInstanceError):
        first.steps = ()  # type: ignore[misc]
