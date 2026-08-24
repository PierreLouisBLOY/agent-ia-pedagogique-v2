from __future__ import annotations

import pytest

from backend.agent_runtime.contracts import ExecutorKind, FailurePolicy, StepKind
from backend.agent_runtime.orchestration import (
    HumanGateAnchor,
    HumanGateBinding,
    PlanCompilationCode,
    PlanCompilationError,
    PlanCompilationRequest,
    PlanCompiler,
    PlanStepBinding,
    WorkflowKind,
    WorkflowRequirements,
    WorkflowResponsibility,
    WorkflowSelectionStatus,
    WorkflowSelector,
)
from backend.core_contracts.capability import CapabilityId

R = WorkflowResponsibility

_CAPABILITY = {
    R.DIRECT_APPLICATION: "CAP-A01",
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


def _binding(
    stage: int,
    responsibility: R,
    suffix: str = "0",
    branch: int | None = None,
) -> PlanStepBinding:
    capability = _CAPABILITY[responsibility]
    executable = responsibility not in {
        R.EVIDENCE_JOIN,
        R.VARIANT_JOIN,
        R.VARIANT_SELECTION,
        R.GATE,
    }
    return PlanStepBinding(
        stage_index=stage,
        responsibility=responsibility,
        step_id=f"i{stage}-{responsibility.value.lower()}-{suffix}",
        objective=f"Execute {responsibility.value}",
        capability_id=CapabilityId(capability) if capability is not None else None,
        permission_scope_ref="scope-integration" if executable else None,
        output_contract={"type": "integration-result"},
        branch_index=branch,
    )


def _request(selection, bindings, human_gate=None) -> PlanCompilationRequest:
    return PlanCompilationRequest(
        selection=selection,
        plan_id="integration-plan",
        run_id="integration-run",
        plan_version=1,
        objective="Exercise selector to compiler integration",
        success_criteria={"complete": True},
        stop_conditions={"failure": "stop"},
        bindings=tuple(bindings),
        human_gate=human_gate,
    )


def _human_gate() -> HumanGateBinding:
    return HumanGateBinding(
        step_id="integration-human-gate",
        objective="Request human approval",
        anchor=HumanGateAnchor.BEFORE_FIRST_STAGE,
        success_criteria={"recorded": True},
        failure_policy=FailurePolicy.STOP,
        output_contract={"type": "gate-result"},
    )


def _parallel_evidence_bindings(continuation: R) -> tuple[PlanStepBinding, ...]:
    return (
        *(_binding(0, R.EVIDENCE, str(index), index) for index in range(3)),
        _binding(0, R.EVIDENCE_JOIN),
        _binding(1, continuation),
    )


def test_production_requirement_selects_wf2_and_compiles_ag03() -> None:
    selection = WorkflowSelector().select(WorkflowRequirements(production_required=True))
    plan = PlanCompiler().compile(
        _request(selection, (_binding(0, R.GENERATE_TRANSFORM),))
    )
    assert tuple(stage.workflow_kind for stage in selection.stages) == (
        WorkflowKind.WF_2,
    )
    assert len(plan.steps) == 1
    assert plan.steps[0].executor.kind is ExecutorKind.AG_03


def test_sourced_reviewed_requirements_select_wf6() -> None:
    selection = WorkflowSelector().select(
        WorkflowRequirements(
            external_evidence_required=True,
            production_required=True,
            independent_review_required=True,
        )
    )
    assert tuple(stage.workflow_kind for stage in selection.stages) == (
        WorkflowKind.WF_6,
    )


def test_wf6_compiles_evidence_generation_validation_review() -> None:
    selection = WorkflowSelector().select(
        WorkflowRequirements(
            external_evidence_required=True,
            production_required=True,
            independent_review_required=True,
        )
    )
    plan = PlanCompiler().compile(
        _request(
            selection,
            (
                _binding(0, R.EVIDENCE),
                _binding(0, R.GENERATE_TRANSFORM),
                _binding(0, R.DETERMINISTIC_VALIDATION),
                _binding(0, R.REVIEW),
            ),
        )
    )
    assert [step.executor.kind for step in plan.steps] == [
        ExecutorKind.AG_02,
        ExecutorKind.AG_03,
        ExecutorKind.APPLICATION,
        ExecutorKind.AG_04,
    ]


def test_parallel_evidence_requirements_select_wf8_then_wf4() -> None:
    selection = WorkflowSelector().select(
        WorkflowRequirements(
            external_evidence_required=True,
            parallel_evidence_branches=3,
            parallel_evidence_independent=True,
            production_required=True,
        )
    )
    assert tuple(stage.workflow_kind for stage in selection.stages) == (
        WorkflowKind.WF_8,
        WorkflowKind.WF_4,
    )


def test_parallel_evidence_compiles_three_ag02_join_and_one_ag03() -> None:
    selection = WorkflowSelector().select(
        WorkflowRequirements(
            external_evidence_required=True,
            parallel_evidence_branches=3,
            parallel_evidence_independent=True,
            production_required=True,
        )
    )
    plan = PlanCompiler().compile(
        _request(selection, _parallel_evidence_bindings(R.GENERATE_TRANSFORM))
    )
    assert sum(step.executor.kind is ExecutorKind.AG_02 for step in plan.steps) == 3
    assert sum(step.kind is StepKind.JOIN for step in plan.steps) == 1
    assert sum(step.executor.kind is ExecutorKind.AG_03 for step in plan.steps) == 1


def test_parallel_evidence_handoff_never_adds_a_fourth_ag02() -> None:
    selection = WorkflowSelector().select(
        WorkflowRequirements(
            external_evidence_required=True,
            parallel_evidence_branches=3,
            parallel_evidence_independent=True,
            production_required=True,
        )
    )
    plan = PlanCompiler().compile(
        _request(selection, _parallel_evidence_bindings(R.GENERATE_TRANSFORM))
    )
    evidence_ids = [
        step.step_id for step in plan.steps if step.executor.kind is ExecutorKind.AG_02
    ]
    assert evidence_ids == [
        "i0-evidence-0",
        "i0-evidence-1",
        "i0-evidence-2",
    ]


def test_three_useful_variants_with_review_select_wf9_then_wf3() -> None:
    selection = WorkflowSelector().select(
        WorkflowRequirements(
            production_required=True,
            variant_count=3,
            variants_explicitly_useful=True,
            independent_review_required=True,
        )
    )
    assert tuple(stage.workflow_kind for stage in selection.stages) == (
        WorkflowKind.WF_9,
        WorkflowKind.WF_3,
    )


def test_variants_compile_parallel_ag03_join_decision_then_ag04() -> None:
    selection = WorkflowSelector().select(
        WorkflowRequirements(
            production_required=True,
            variant_count=3,
            variants_explicitly_useful=True,
            independent_review_required=True,
        )
    )
    bindings = (
        *(_binding(0, R.VARIANT_GENERATION, str(index), index) for index in range(3)),
        _binding(0, R.VARIANT_JOIN),
        _binding(0, R.VARIANT_SELECTION),
        _binding(1, R.REVIEW),
    )
    plan = PlanCompiler().compile(_request(selection, bindings))
    assert [step.kind for step in plan.steps] == [
        StepKind.AGENT,
        StepKind.AGENT,
        StepKind.AGENT,
        StepKind.JOIN,
        StepKind.DECISION,
        StepKind.AGENT,
    ]
    assert plan.steps[-1].executor.kind is ExecutorKind.AG_04


def test_production_review_promotion_selects_wf5_then_wf11() -> None:
    selection = WorkflowSelector().select(
        WorkflowRequirements(
            production_required=True,
            independent_review_required=True,
            promotion_required=True,
        )
    )
    assert tuple(stage.workflow_kind for stage in selection.stages) == (
        WorkflowKind.WF_5,
        WorkflowKind.WF_11,
    )


def test_promotion_compiles_terminal_cap_a02_with_policy_gate_ancestor() -> None:
    selection = WorkflowSelector().select(
        WorkflowRequirements(
            production_required=True,
            independent_review_required=True,
            promotion_required=True,
        )
    )
    plan = PlanCompiler().compile(
        _request(
            selection,
            (
                _binding(0, R.GENERATE_TRANSFORM),
                _binding(0, R.REVIEW),
                _binding(1, R.DETERMINISTIC_VALIDATION),
                _binding(1, R.GATE),
                _binding(1, R.PROMOTION),
            ),
        )
    )
    promotion = plan.steps[-1]
    gate = plan.steps[-2]
    assert promotion.capability_id == CapabilityId("CAP-A02")
    assert promotion.depends_on == (gate.step_id,)
    assert gate.kind is StepKind.GATE


def test_human_gate_requirement_selects_wf10_overlay() -> None:
    selection = WorkflowSelector().select(
        WorkflowRequirements(production_required=True, human_gate_required=True)
    )
    assert selection.overlays == (WorkflowKind.WF_10,)


def test_before_first_human_gate_precedes_ag03_in_compiled_plan() -> None:
    selection = WorkflowSelector().select(
        WorkflowRequirements(production_required=True, human_gate_required=True)
    )
    plan = PlanCompiler().compile(
        _request(
            selection,
            (_binding(0, R.GENERATE_TRANSFORM),),
            _human_gate(),
        )
    )
    gate, generation = plan.steps
    assert gate.kind is StepKind.GATE
    assert generation.depends_on == (gate.step_id,)


def test_blocking_ambiguity_stops_selection_before_plan_compilation() -> None:
    selection = WorkflowSelector().select(
        WorkflowRequirements(human_gate_required=True, blocking_ambiguity=True)
    )
    assert selection.status is WorkflowSelectionStatus.WAITING_HUMAN
    request = _request(selection, (), _human_gate())
    with pytest.raises(PlanCompilationError) as captured:
        PlanCompiler().compile(request)
    assert captured.value.code is PlanCompilationCode.WAITING_HUMAN_NOT_COMPILABLE
