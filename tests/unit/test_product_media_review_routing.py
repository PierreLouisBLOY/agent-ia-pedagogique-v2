"""Declared AG04 double checks bindings; no semantic or pixel quality claim."""

import pytest

from backend.adapters.outbound.review.p0_review import P0ReviewAdapter
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import as_plain
from tests.unit.test_p0_agentic_routing import TechnicalCritic
from tests.unit.test_product_media import FAMILIES, child_fixture, media_fixture
from tests.unit.test_r6_p0_contract import EVIDENCE_ID, EVIDENCE_TEXT


def request(bundle):
    return {"production": bundle.mutable_copy(), "bundle_sha256": bundle.sha256,
            "evidence_pack": {"passages": []}, "plan": {}, "validation": {}}


@pytest.mark.parametrize("kind,mode", FAMILIES)
def test_generic_media_commitments_reach_separate_ag04_without_png_bytes(kind, mode):
    _, child = child_fixture(kind, mode)
    critic = TechnicalCritic()
    result = P0ReviewAdapter(critic, authorize=lambda request: True).review(request=request(child.p0_bundle))
    assert len(critic.requests) == 1
    actual = critic.requests[0]
    visuals = actual.target_payload["visuals"]
    assert as_plain(visuals) == child.p0_bundle.media_review_context()
    entry = child.p0_bundle.data["media_plan"]["entries"][0]
    visual = visuals[0]
    assert visual["version_ref"] == child.version_ref
    assert visual["dependencies"] == as_plain(entry["dependencies"])
    assert visual["asset_sha256"] == entry["asset"]["png_sha256"]
    assert visual["student_visibility"] is True and visual["teacher_visibility"] is True
    assert visual["availability"] == "PRESENT" and visual["required"] is True
    assert "bytes_base64" not in repr(actual.target_payload)
    assert "SEPARATE_REQUIRED" in repr(actual.criteria)
    assert result["promotion"] == "NOT_PERFORMED"
    assert result["correction_required"] is True


@pytest.mark.parametrize("required", [False, True])
def test_missing_media_and_audience_are_explicit_to_ag04_without_fake_hash(required):
    parent, proposal, inbound = media_fixture()
    proposal.update(required=required, materialize=False,
                    omission_reason="L’actif local n’est pas encore disponible.")
    proposal["brief"]["teacher_visibility"] = False
    child = inbound.execute(parent, [proposal], evidence={EVIDENCE_ID: EVIDENCE_TEXT})
    critic = TechnicalCritic()
    P0ReviewAdapter(critic, authorize=lambda request: True).review(request=request(child.p0_bundle))
    visual = critic.requests[0].target_payload["visuals"][0]
    assert visual["availability"] == "MISSING" and visual["asset_sha256"] == "UNAVAILABLE"
    assert visual["required"] is required and visual["omission_reason"] == proposal["omission_reason"]
    assert visual["student_visibility"] is True and visual["teacher_visibility"] is False
    assert visual["pixel_inspection"] == "SEPARATE_REQUIRED"


def test_no_media_reason_is_review_context_without_an_imaginary_visual():
    parent, _, inbound = media_fixture()
    reason = "Les pièces natives suffisent à l’objectif de l’exercice."
    child = inbound.execute(parent, [], evidence={EVIDENCE_ID: EVIDENCE_TEXT}, no_media_reason=reason)
    critic = TechnicalCritic()
    P0ReviewAdapter(critic, authorize=lambda request: True).review(request=request(child.p0_bundle))
    actual = critic.requests[0]
    assert "visuals" not in actual.target_payload
    assert actual.criteria["media_choice"] == {"decision": "NO_MEDIA", "reason": reason,
                                                  "pedagogical_acceptance": "NOT_PERFORMED"}


@pytest.mark.parametrize("mutation", ["hash", "version", "dependency", "audience", "asset"])
def test_media_substitution_is_rejected_before_review_transport(mutation):
    _, child = child_fixture()
    body = request(child.p0_bundle)
    production = body["production"]
    entry = production["media_plan"]["entries"][0]
    if mutation == "hash":
        body["bundle_sha256"] = "0" * 64
    elif mutation == "version":
        production["version_ref"] = "ver:" + "a" * 32
    elif mutation == "dependency":
        key = next(iter(entry["dependencies"]))
        entry["dependencies"][key] = "0" * 64
    elif mutation == "audience":
        entry["brief"]["student_visibility"] = False
    else:
        entry["asset"]["png_sha256"] = "0" * 64
    critic = TechnicalCritic()
    with pytest.raises(ValueError):
        P0ReviewAdapter(critic, authorize=lambda request: True).review(request=body)
    assert critic.requests == []
