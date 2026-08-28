from backend.agent_runtime.contracts import GateDecisionValue, ProductionValidationState
from backend.agent_runtime.gates import GateResolutionDisposition
from backend.core_contracts.capability import CapabilityId
from evaluation_harness import EvaluationCaseCode
from tests.e2e.core.assessment_bindings import (
    candidate_sections,
    execute_gate_promotion,
    execute_scn06,
    execute_scn07,
    execute_scn08,
    second_correction_plan,
)
from tests.e2e.core.catalog import scenario_for
from tests.e2e.core.fixtures import SyntheticPedagogicalFixture


def _fixture(case_code: str) -> SyntheticPedagogicalFixture:
    scenario = scenario_for(EvaluationCaseCode(case_code))
    assert scenario is not None
    return scenario.fixture


def test_scn06_two_independent_evidence_branches_join_before_generation() -> None:
    witness = execute_scn06(_fixture("SCN-06"))
    branches = witness.evidence
    join = next(step for step in witness.compiled.plan.steps if step.capability_id == CapabilityId("CAP-O04"))

    assert witness.compiled.plan.workflow_kind == "WF-8+WF-6"
    assert len(branches) == 2
    assert branches[0].request is not branches[1].request
    assert branches[0].request != branches[1].request
    assert branches[0].evidence_set != branches[1].evidence_set
    assert all(branch.search_call_count == 4 for branch in branches)
    assert all(branch.content_call_count == 1 for branch in branches)
    assert join.depends_on == tuple(
        step.step_id
        for step in witness.compiled.plan.steps
        if step.capability_id == CapabilityId("CAP-E01")
    )
    assert witness.events[:4] == (
        "EVIDENCE_BRANCH_0",
        "EVIDENCE_BRANCH_1",
        "JOIN",
        "GENERATION",
    )
    assert candidate_sections(witness.generation.candidate) == (
        "instructions",
        "questions",
        "marking-scheme",
    )
    assert witness.validation.call_count == witness.review.port_call_count == 1


def test_scn07_correction_increases_version_and_stops_once() -> None:
    witness = execute_scn07(_fixture("SCN-07"))

    assert witness.compiled.plan.workflow_kind == "WF-1+WF-7+WF-0"
    assert witness.correction_port_call_count == witness.correction_count == 1
    assert witness.candidate.validation_state is ProductionValidationState.CANDIDATE
    assert witness.correction_result.parent_production_ref.version_ref.value == "v1"
    assert witness.correction_result.new_production_ref.version_ref.value == "v2"
    assert witness.correction_result.parent_production_ref.object_ref == (
        witness.correction_result.new_production_ref.object_ref
    )
    assert witness.correction_result.addressed_findings == (
        "finding:scn-07:major",
    )
    assert witness.correction_result.unresolved_findings == ()
    assert witness.events[-1] == "STOP"
    assert witness.final_read.use_case_id == "application.read_production"
    assert witness.final_read.call_count == 1


def test_second_correction_requires_a_new_plan_version() -> None:
    first, second = second_correction_plan()

    assert first.plan_id == second.plan_id
    assert first.plan_version == 1
    assert second.plan_version == 2
    assert tuple(step.step_id for step in first.steps) == tuple(
        step.step_id for step in second.steps
    )


def test_scn08_variants_are_distinct_and_selection_is_opaque() -> None:
    witness = execute_scn08(_fixture("SCN-08"))

    assert witness.compiled.plan.workflow_kind == "WF-9+WF-3+WF-11"
    assert len(witness.variants) == 2
    assert witness.variants[0].candidate.production_id != (
        witness.variants[1].candidate.production_id
    )
    assert witness.selected_index == 0
    assert witness.selection_policy == "opaque_deterministic_first_joined_ref"
    assert witness.selection_call_count == 1
    assert witness.events[:4] == ("VARIANT_0", "VARIANT_1", "JOIN", "SELECTION")
    assert witness.review.port_call_count == 1
    assert witness.validation.call_count == 1
    assert witness.gate_promotion.promotion is not None
    assert witness.gate_promotion.promotion.call_count == 1
    assert witness.gate_promotion.promotion.idempotency_key == "promotion:scn-08:0"
    assert witness.render_effect_count == 0


def test_rejected_gate_blocks_promotion_route() -> None:
    witness = execute_gate_promotion(GateDecisionValue.REJECTED)

    assert witness.resolution.disposition is GateResolutionDisposition.REJECTED
    assert witness.resolution.to_policy_facts().matrix_gate_satisfied is False
    assert witness.promotion is None
    assert witness.events == ("VALIDATION", "GATE_REJECTED")
