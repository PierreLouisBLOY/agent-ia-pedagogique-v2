import pytest

from backend.modules.pedagogical_design.application.commands.revise_assessment import (
    ReviseAssessmentCommand,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_revision import (
    HARDEN,
    AssessmentRevisionRequest,
)
from tests.support.r3_synthetic import PROD, V1, V2, bundle, harden_delta, lineage
from tests.unit.test_assessment_deterministic_validation import validate


def revised(delta=None):
    b = bundle()
    request = AssessmentRevisionRequest(HARDEN, PROD, V1, b.data["subject"],
        b.data["pedagogical_context"], tuple(b.data["references"]), b)
    return b, ReviseAssessmentCommand().execute(request, delta or harden_delta(),
        version_ref=V2, lineage=lineage(b))


def test_d3_revision_keeps_v1_and_d1_d2_and_total():
    before = bundle().sha256
    b, new = revised()
    assert b.sha256 == before and new.version_ref == V2
    assert b.data["subject"]["sections"][:-1] == new.data["subject"]["sections"][:-1]
    assert validate(new, b).overall_status == "PASS", validate(new, b).as_dict()
    assert new.data["marking"]["total_points"] == "20.00"


def test_outside_scope_and_empty_delta_refused():
    delta = harden_delta()
    delta["dossier_1"] = "not authorized"
    with pytest.raises(ValueError):
        revised(delta)


def test_preparation_refuses_invented_correction_identity():
    from backend.modules.pedagogical_design.contracts.dto.assessment_revision import PREPARE
    from tests.support.r3_synthetic import production, subject, supplements
    prod = production()
    request = AssessmentRevisionRequest(PREPARE, PROD, V1, subject(),
        prod.data["pedagogical_context"], tuple(prod.data["references"]))
    delta = supplements()
    delta["correction"]["version_ref"] = "ver:" + "f" * 32
    with pytest.raises(ValueError, match="ASSESSMENT_REFERENCE"):
        ReviseAssessmentCommand().execute(request, delta, version_ref=V1, lineage=lineage())
    delta = harden_delta()
    delta["questions_d3"] = delta["questions_d3"][:1]
    with pytest.raises(ValueError, match="COMPLEXIFICATION_REQUIRED"):
        revised(delta)
