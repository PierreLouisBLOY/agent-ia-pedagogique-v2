import pytest

from backend.adapters.outbound.generation.assessment_revision import (
    AssessmentRevisionAdapter,
    parse_revision_result,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_revision import (
    PREPARE,
    AssessmentRevisionRequest,
)
from tests.support.r3_fakes import FakeR3Generation
from tests.support.r3_synthetic import PROD, V1, bundle


def test_ag03_generic_section_is_strictly_decoded():
    b = bundle()
    request = AssessmentRevisionRequest(PREPARE, PROD, V1, b.data["subject"],
                                        b.data["pedagogical_context"], tuple(b.data["references"]))
    port = FakeR3Generation()
    result = AssessmentRevisionAdapter(port).propose(request)
    assert result["marking"]["total_points"] == "20.00"
    assert len(port.calls) == 1
    assert port.calls[0].expected_sections == ("R3_RESULT_JSON",)


@pytest.mark.parametrize("raw", ('{"a":1,"a":2}', '{"a":NaN}', 'null', '{"broken"', '[]'))
def test_invalid_json_never_repaired(raw):
    with pytest.raises(ValueError):
        parse_revision_result({"sections": {"R3_RESULT_JSON": raw}})
