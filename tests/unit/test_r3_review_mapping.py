from dataclasses import replace

import pytest

from backend.adapters.outbound.review.assessment_review import AssessmentReviewAdapter
from tests.support.r3_fakes import FakeR3Review
from tests.support.r3_synthetic import bundle


def test_ag04_exact_review_immutable_and_without_validation_authority():
    b = bundle()
    before = b.sha256
    port = FakeR3Review()
    result = AssessmentReviewAdapter(port).review(b, ("REV-ACC", "REV-CON"))
    assert b.sha256 == before
    assert result["version_ref"] == b.version_ref and result["bundle_sha256"] == before
    assert result["status"] == "completed"
    assert "validation_state" not in result and "promoted" not in result
    assert len(port.calls) == 1


@pytest.mark.parametrize("severity", ("info", "minor", "major", "blocking"))
def test_findings_use_canonical_severity_and_exact_target(severity):
    b = bundle()
    class Findings(FakeR3Review):
        def review(self, *, request):
            result = super().review(request=request)
            finding = {"finding_id": "synthetic-finding", "dimension": "REV-ACC",
                "severity": severity, "description": "Clarifier la consigne.",
                "target_locator": {"kind": "text_span", "start": 0, "end": 8, "quote": "Contrôle"},
                "rationale": "La consigne peut être précisée.", "correction_required": False,
                "evidence_refs": request.evidence_refs, "confidence": {}, "suggested_action": {}}
            return replace(result, technical_findings=(finding,))
    result = AssessmentReviewAdapter(Findings()).review(b, ("REV-ACC",))
    assert result["findings"][0]["severity"] == severity
    assert result["version_ref"] == b.version_ref and result["bundle_sha256"] == b.sha256


def test_pedagogical_authority_claim_still_rejected_by_unchanged_ag04():
    from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
        AssessmentBundle,
        fingerprint,
    )
    data = bundle().mutable_copy()
    data["subject"]["content"] += " Ceci est une source officielle."
    data["subject_sha256"] = fingerprint(data["subject"])
    port = FakeR3Review()
    with pytest.raises(ValueError):
        AssessmentReviewAdapter(port).review(AssessmentBundle(data), ("REV-ACC",))
    assert port.calls == []
