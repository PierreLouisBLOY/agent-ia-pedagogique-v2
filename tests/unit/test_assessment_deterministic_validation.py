from copy import deepcopy

import pytest

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import AssessmentBundle
from backend.modules.validation_control.application.commands.validate_assessment import (
    ValidateAssessmentCommand,
)
from tests.support.r3_synthetic import PROD, V1, bundle


def validate(b, parent=None):
    return ValidateAssessmentCommand().execute(b, production_ref=PROD, version_ref=b.version_ref if b else V1,
        subject_sha256=b.data["subject_sha256"] if b else "0" * 64, validation_ref="validation-test",
        evaluated_at="2026-09-06T12:00:00Z", references=tuple(b.data["references"]) if b else (), parent=parent)


@pytest.mark.parametrize("scale", ("EUR", "kEUR"))
def test_sixteen_checks_pass_with_explicit_scale(scale):
    result = validate(bundle(scale))
    assert len(result.checks) == 16
    assert result.overall_status == "PASS", result.as_dict()


@pytest.mark.parametrize("mutation", ("total", "frng", "bfr", "tn", "component", "missing_answer",
                                     "orphan", "duration", "source_scale", "silent_scale"))
def test_invalid_calculations_and_structure_never_pass(mutation):
    data = deepcopy(bundle("kEUR").mutable_copy())
    case = data["case_data"]["base_case"]
    if mutation == "total":
        data["marking"]["total_points"] = "19.99"
    elif mutation in {"frng", "bfr", "tn"}:
        case["computed"][mutation.upper()] = "0.00"
    elif mutation == "component":
        case["components"]["stable_resources"][0]["amount"] = "1.00"
    elif mutation == "missing_answer":
        data["correction"]["answers"].pop()
    elif mutation == "orphan":
        data["correction"]["answers"][0]["question_id"] = "unknown"
    elif mutation == "duration":
        data["marking"]["dossiers"][0]["duration_minutes"] = 21
    elif mutation == "source_scale":
        data["case_data"]["source_scale"] = "UNKNOWN"
    else:
        case["components"]["stable_uses"][0]["amount"] = "200.00"
    assert validate(AssessmentBundle(data)).overall_status == "FAIL"


def test_missing_bundle_is_explicit_failure():
    assert validate(None).overall_status == "FAIL"
    assert all(c.reason_code == "ASSESSMENT_BUNDLE_MISSING" for c in validate(None).checks)


@pytest.mark.parametrize("expression", (
    "__import__('os')", {"op": "MULTIPLY", "operands": []},
    {"ref": "other_case.FRNG"}, {"op": "ADD", "operands": [{"ref": "totals.stable_uses"}] * 17},
    {"op": "SUB", "operands": [{"ref": "totals.stable_resources"}, {"ref": "totals.current_assets"}]},
))
def test_expression_data_language_is_closed_and_result_bound(expression):
    data = bundle().mutable_copy()
    data["correction"]["answers"][0]["calculations"][0]["expression"] = expression
    assert validate(AssessmentBundle(data)).checks[14].status == "FAIL"


def test_add_sub_depth_and_answer_coverage():
    from backend.modules.validation_control.domain.policies.assessment_checks import (
        evaluate_expression,
    )
    from tests.support.r3_synthetic import source_case
    expr = {"op": "ADD", "operands": [{"ref": "totals.current_assets"}, {"ref": "totals.current_liabilities"}]}
    assert str(evaluate_expression(expr, source_case())) == "200000.00"
    for _ in range(4):
        expr = {"op": "SUB", "operands": [expr, {"ref": "totals.cash_liabilities"}]}
    with pytest.raises(ValueError, match="EXPRESSION_DEPTH"):
        evaluate_expression(expr, source_case())
    data = bundle().mutable_copy()
    data["correction"]["answers"][0]["calculations"] = []
    assert validate(AssessmentBundle(data)).checks[14].status == "FAIL"


def test_free_text_cannot_self_declare_deterministic_coverage():
    data = bundle().mutable_copy()
    data["correction"]["answers"][0]["expected_answer"] += " Cette situation est pédagogiquement parfaite."
    result = validate(AssessmentBundle(data))
    assert result.overall_status == "WARNING"
    assert result.checks[15].reason_code == "SEMANTIC_HUMAN_REVIEW_REQUIRED"


@pytest.mark.parametrize("value", ("20.01", "-1.00", "NaN", True, 6.0))
def test_points_and_numeric_domain_fail_closed(value):
    data = bundle().mutable_copy()
    data["marking"]["dossiers"][0]["questions"][0]["criteria"][0]["points"] = value
    assert validate(AssessmentBundle(data)).overall_status == "FAIL"


def test_question_cannot_move_silently_to_another_marking_dossier():
    data = bundle().mutable_copy()
    ds = data["marking"]["dossiers"]
    ds[0]["questions"], ds[1]["questions"] = ds[1]["questions"], ds[0]["questions"]
    assert validate(AssessmentBundle(data)).checks[4].status == "FAIL"
