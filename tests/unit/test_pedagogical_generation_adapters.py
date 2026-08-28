from backend.agent_runtime.contracts import (
    GateDecisionValue,
    StepKind,
)
from backend.agent_runtime.gates import GateResolutionDisposition
from evaluation_harness import EvaluationCaseCode
from tests.e2e.core.generation_adapters import (
    compile_d_plan,
    run_human_gate_sequence,
)


def _step_signature(case_code: str) -> tuple[tuple[str, str, str | None], ...]:
    plan = compile_d_plan(EvaluationCaseCode(case_code))
    return tuple(
        (
            step.executor.kind.value,
            step.kind.value,
            step.capability_id.value if step.capability_id is not None else None,
        )
        for step in plan.steps
    )


def test_scn_03_compiles_only_wf2_generation() -> None:
    plan = compile_d_plan(EvaluationCaseCode("SCN-03"))

    assert plan.workflow_kind == "WF-2"
    assert _step_signature("SCN-03") == (("AG-03", "agent", "CAP-G01"),)
    assert plan.steps[0].depends_on == ()


def test_scn_04_compiles_evidence_before_transformation() -> None:
    plan = compile_d_plan(EvaluationCaseCode("SCN-04"))

    assert plan.workflow_kind == "WF-4"
    assert _step_signature("SCN-04") == (
        ("AG-02", "agent", "CAP-E01"),
        ("AG-03", "agent", "CAP-G02"),
    )
    assert plan.steps[1].depends_on == (plan.steps[0].step_id,)


def test_scn_05_compiles_wf5_with_wf10_gate_after_review() -> None:
    plan = compile_d_plan(EvaluationCaseCode("SCN-05"))

    assert plan.workflow_kind == "WF-5|overlay:WF-10"
    assert _step_signature("SCN-05") == (
        ("AG-03", "agent", "CAP-G01"),
        ("AG-04", "agent", "CAP-V01"),
        ("RUNTIME", "gate", "CAP-O05"),
    )
    assert plan.steps[2].kind is StepKind.GATE
    assert plan.steps[2].depends_on == (plan.steps[1].step_id,)


def test_external_approved_gate_continues_once() -> None:
    witness = run_human_gate_sequence(GateDecisionValue.APPROVED)

    assert witness.resolution.disposition is GateResolutionDisposition.APPROVED
    assert witness.decision_request == witness.resolution.request
    assert witness.source_request is witness.resolution.request
    assert witness.resolution.to_policy_facts().matrix_gate_satisfied is True
    assert witness.source_call_count == 1
    assert witness.continuation_count == 1
    assert witness.events == (
        "review-complete",
        "gate-request",
        "external-APPROVED",
        "continuation",
    )


def test_external_rejected_gate_blocks_continuation() -> None:
    witness = run_human_gate_sequence(GateDecisionValue.REJECTED)

    assert witness.resolution.disposition is GateResolutionDisposition.REJECTED
    assert witness.decision_request == witness.resolution.request
    assert witness.source_request is witness.resolution.request
    assert witness.resolution.to_policy_facts().matrix_gate_satisfied is False
    assert witness.source_call_count == 1
    assert witness.continuation_count == 0
    assert witness.events[-1] == "external-REJECTED"
