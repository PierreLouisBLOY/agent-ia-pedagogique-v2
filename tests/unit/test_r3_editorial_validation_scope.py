"""Authenticated A14 policy tests, wholly artificial data."""
from dataclasses import replace

import pytest

from backend.adapters.outbound.generation.openai.locator_materialization import calculation_locators
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import AssessmentBundle
from backend.modules.validation_control.application.commands.validate_assessment import (
    ValidateAssessmentCommand,
)
from backend.modules.validation_control.contracts.dto.editorial_scope import (
    EditorialValidationScope,
    build_editorial_scope,
    verify_editorial_scope,
)
from tests.unit.test_r3_editorial_corrections import scope_for


def validate(child, parent, scope=None):
    return ValidateAssessmentCommand().execute(child, production_ref=child.production_ref,
        version_ref=child.version_ref, subject_sha256=child.data["subject_sha256"],
        validation_ref="synthetic-editorial", evaluated_at="2026-01-01T00:00:00Z",
        references=tuple(child.data["references"]), parent=parent, editorial_scope=scope)


def test_all_sixteen_checks_warning_and_exact_revalidation():
    parent, plan, evidence, child, scope, live = scope_for()
    report = validate(child, parent, scope)
    assert len(report.checks) == 16
    assert [c.check_id for c in report.checks] == [f"A{i:02}" for i in range(1, 17)]
    assert all(c.status == "PASS" for c in report.checks[:15]), report.as_dict()
    assert report.checks[15].status == "WARNING" and report.overall_status == "WARNING"
    assert validate(child, parent, scope).overall_status == "WARNING"
    live["open"] = False
    assert validate(child, parent, scope).checks[13].status == "FAIL"


@pytest.mark.parametrize("mode", ["none", "copy", "flag", "parent_none", "other_parent", "wrong_evidence"])
def test_scope_cannot_self_authenticate(mode):
    parent, plan, evidence, child, scope, live = scope_for()
    if mode == "none":
        scope = None
    elif mode == "copy":
        scope = replace(scope)
    elif mode == "flag":
        scope = {"approved": True, "plan_sha256": plan.sha256}
    elif mode == "parent_none":
        parent = None
    elif mode == "other_parent":
        data = parent.mutable_copy()
        data["limitations"].append("artificial alternate parent")
        parent = AssessmentBundle(data)
    else:
        scope = replace(scope, evidence=replace(evidence, receipt=object()))
    assert not verify_editorial_scope(scope, parent=parent, candidate=child.data)
    assert validate(child, parent, scope).checks[13].status == "FAIL"


@pytest.mark.parametrize("mutation", [
    "subject", "rationale", "value", "expression", "points", "duration", "limitation",
    "locator", "keys", "order", "provenance", "plan_hash", "command", "version", "text",
])
def test_exhaustive_diff_rejects_each_unapproved_mutation(mutation):
    parent, plan, evidence, child, scope, live = scope_for()
    d = child.mutable_copy()
    if mutation == "subject":
        d["subject"]["sections"][4]["text"] += " changed"
    elif mutation == "rationale":
        d["correction"]["answers"][0]["rationale"] += " changed"
    elif mutation == "value":
        d["correction"]["answers"][0]["calculations"][0]["value"] = "0.00"
    elif mutation == "expression":
        d["correction"]["answers"][0]["calculations"][0]["expression"]["op"] = "ADD"
    elif mutation == "points":
        d["marking"]["total_points"] = "19.00"
    elif mutation == "duration":
        d["marking"]["dossiers"][0]["duration_minutes"] = 19
    elif mutation == "limitation":
        d["limitations"].append("changed")
    elif mutation == "locator":
        d["correction"]["answers"][0]["calculations"][0]["locator"]["start"] += 1
    elif mutation == "keys":
        d["lineage"]["approved"] = True
    elif mutation == "order":
        d["correction"]["answers"].reverse()
    elif mutation == "provenance":
        d["lineage"]["source_capability"] = "CAP-G02"
    elif mutation == "plan_hash":
        d["lineage"]["instruction_sha256"] = "1"*64
    elif mutation == "command":
        d["lineage"]["command_id"] = "0"*8+"-"+"0"*4+"-"+"0"*4+"-"+"0"*4+"-"+"0"*12
    elif mutation == "version":
        d["version_ref"] = parent.version_ref
    else:
        d["correction"]["answers"][1]["expected_answer"] += " unapproved"
    assert not verify_editorial_scope(scope, parent=parent, candidate=d)


def test_independent_receipt_verifier_required_and_no_harden_fallback():
    parent, plan, evidence, child, scope, live = scope_for()
    with pytest.raises(ValueError, match="R3_NOT_AUTHORIZED"):
        build_editorial_scope(evidence, parent, child, command_id=scope.command_id,
            operation_ref=scope.operation_ref, authenticate=lambda e: False,
            calculate_locators=calculation_locators)
    copied = EditorialValidationScope(evidence, parent, child, scope.command_id,
                                      scope.operation_ref, scope.locators)
    assert not verify_editorial_scope(copied, parent=parent, candidate=child.data)
    d = child.mutable_copy()
    d["lineage"]["source_capability"] = "CAP-G02"
    assert validate(AssessmentBundle(d), parent).checks[13].status == "FAIL"
