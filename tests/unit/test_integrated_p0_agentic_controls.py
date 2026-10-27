"""Application control mutations with declared doubles; no provider quality claim."""

import hashlib

import pytest

from backend.modules.pedagogical_context.contracts.dto.p0_context import P0Context
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import fingerprint
from backend.modules.work_orchestration.application.services.p0_agentic import (
    effort_plan,
    evidence_pack,
    quality_status,
)
from tests.integration.test_p0_creation_http import context


def reference_pack(count):
    references, evidence = [], {}
    for index in range(count):
        text = f"Declared synthetic passage {index}; no official authority."
        identifier = f"evidence:{index + 1:032x}"
        references.append({
            "evidence_id": identifier,
            "source_ref": f"unit:source-{index}",
            "locator": f"unit:passage-{index}",
            "checksum_or_version": "unit:v1",
            "excerpt_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "provenance_label": "SYNTHETIC_UNIT_REFERENCE",
        })
        evidence[identifier] = text
    return references, evidence


@pytest.mark.parametrize("kind,topics,difficulty,limit", [
    ("COURSE", ["Organisation"], "INTRODUCTORY", 1),
    ("EXERCISE", ["Organisation"], "STANDARD", 3),
    ("COURSE", ["Organisation"], "ADVANCED", 6),
    ("ASSESSMENT", ["Organisation"], "STANDARD", 8),
])
def test_evidence_pack_enforces_application_effort_bound(kind, topics, difficulty, limit):
    data = context("BTS_CG_YEAR_1", kind, None)
    data.update(topics=topics, objectives=["Expliquer les rôles des acteurs."],
                difficulty=difficulty)
    selected_context = P0Context(data)
    assert effort_plan(selected_context)["retrieval"]["max_passages"] == limit
    references, evidence = reference_pack(limit)
    accepted = evidence_pack(selected_context, references, evidence)
    assert len(accepted["passages"]) == limit
    assert accepted["authority"] == "NONE"
    if limit < 8:
        references, evidence = reference_pack(limit + 1)
        with pytest.raises(ValueError, match="P0_EVIDENCE_PACK_SCOPE"):
            evidence_pack(selected_context, references, evidence)


def test_evidence_pack_rejects_duplicate_identity_instead_of_expanding_same_passage():
    selected_context = P0Context(context("BTS_CG_YEAR_2", "ASSESSMENT", None))
    references, evidence = reference_pack(1)
    with pytest.raises(ValueError, match="P0_EVIDENCE_PACK_SCOPE"):
        evidence_pack(selected_context, [references[0], dict(references[0])], evidence)


def bound_quality():
    data = context("FIRST_STMG", "COURSE", None)
    data.update(topics=["Organisation"], objectives=["Expliquer les rôles des acteurs."])
    selected_context = P0Context(data)
    production = {"production_ref": "prod:" + "a" * 32,
                  "version_ref": "ver:" + "b" * 32,
                  "context_sha256": selected_context.sha256,
                  "sections": [{"text": "Les rôles des acteurs sont expliqués."}]}
    review = {"production_ref": production["production_ref"],
              "version_ref": production["version_ref"],
              "bundle_sha256": fingerprint(production),
              "status": "completed", "overall_assessment": "acceptable",
              "instruction_coverage": "FULL", "correction_required": False,
              "limitations": [], "uncertainties": []}
    return effort_plan(selected_context, production=production), production, review


def test_quality_accepts_only_current_exact_review_without_conferring_human_authority():
    plan, production, review = bound_quality()
    result = quality_status(plan, review=review, production=production)
    assert result["review"] == "REVUE_OK"
    assert result["instruction"] == "CONSIGNE_COUVERTE"
    assert result["human_review"] == "HUMAN_REVIEW_REQUIRED"


@pytest.mark.parametrize("mutation", ["production", "version", "hash", "content"])
def test_quality_rejects_review_of_another_version_or_changed_content(mutation):
    plan, production, review = bound_quality()
    if mutation == "content":
        production["sections"] = [{"text": "Changed output after review."}]
    else:
        key = {"production": "production_ref", "version": "version_ref",
               "hash": "bundle_sha256"}[mutation]
        review[key] = "0" * 64
    with pytest.raises(ValueError, match="P0_QUALITY_REVIEW_BINDING"):
        quality_status(plan, review=review, production=production)


def test_quality_rejects_plan_of_another_context():
    plan, production, review = bound_quality()
    plan["context_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="P0_QUALITY_CONTEXT_BINDING"):
        quality_status(plan, review=review, production=production)


def test_contradictory_review_requires_reserve_even_when_assessment_says_acceptable():
    plan, production, review = bound_quality()
    review["correction_required"] = True
    result = quality_status(plan, review=review, production=production)
    assert result["review"] == "RESERVE"
    assert result["calculations"] != "CALCULS_VERIFIES"
