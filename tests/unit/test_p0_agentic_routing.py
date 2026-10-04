"""Declared doubles exercise the local protocol, never semantic quality or live."""

from secrets import token_hex

import pytest

from backend.adapters.outbound.review.p0_review import P0ReviewAdapter
from backend.agent_runtime.agents.review.review_model import (
    ReviewPortResult,
    ReviewPortResultStatus,
)
from backend.modules.pedagogical_context.contracts.dto.p0_context import P0Context
from backend.modules.work_orchestration.application.services.p0_agentic import (
    effort_plan,
    evidence_pack,
)
from tests.integration.test_p0_creation_http import context
from tests.support.p0_generation_double import P0GenerationDouble
from tests.unit.test_p0_creation_contract import service


class TechnicalCritic:
    def __init__(self, *, mutate=False, fail=False):
        self.requests = []
        self.mutate, self.fail = mutate, fail

    def review(self, *, request):
        self.requests.append(request)
        if self.fail:
            raise TimeoutError("private diagnostic never exposed")
        output = {
            "overall_assessment": "correction_required",
            "correction_required": True,
            "coverage": tuple(d.value for d in request.review_dimensions),
            "confidence": {},
        }
        return ReviewPortResult(
            request.source_step_id,
            request.operation,
            ReviewPortResultStatus.SUCCEEDED,
            structured_payload=output,
            evidence_refs_used=request.evidence_refs if not self.mutate else ("outside",),
        )


def candidate(app):
    prepared = app.execute(
        "prepare",
        {
            "command_id": token_hex(16),
            "context": context("BTS_CG_YEAR_2", "ASSESSMENT", None),
            "reference": {},
        },
    )
    result = app.execute(
        "generate",
        {
            "command_id": token_hex(16),
            "preparation_ref": prepared["preparation_ref"],
            "preparation_sha256": prepared["preparation_sha256"],
        },
    )
    return result["view"], prepared


def identity(view):
    return {k: view[k] for k in ("production_ref", "version_ref", "bundle_sha256")}


@pytest.mark.parametrize(
    "kind,topics,difficulty,expected",
    [
        ("COURSE", ["organisation"], "INTRODUCTORY", "SIMPLE"),
        ("QUESTION_SET", ["parties prenantes"], "STANDARD", "STANDARD"),
        ("COURSE", ["organisation"], "ADVANCED", "COMPLEXE"),
        ("ASSESSMENT", ["organisation"], "STANDARD", "HAUT_RISQUE_PEDAGOGIQUE"),
        ("EXERCISE", ["Seuil de rentabilité et coût"], "STANDARD", "HAUT_RISQUE_PEDAGOGIQUE"),
    ],
)
def test_effort_is_explainable_and_has_no_spend_authority(kind, topics, difficulty, expected):
    data = context("BTS_CG_YEAR_2", kind, "OPEN_QUESTIONS" if kind == "QUESTION_SET" else None)
    data.update(topics=topics, difficulty=difficulty)
    plan = effort_plan(P0Context(data))
    assert plan["effort"] == expected
    assert plan["budget"]["authority"] == "OWNER_GATE_REQUIRED"
    assert plan["budget"]["retry"] == 0 and len(plan["subtasks"]) == 4


@pytest.mark.parametrize("objective,required", [
    ("Calculer la part de marché en pourcentage.", True),
    ("Distinguer part de marché et croissance.", False),
])
def test_quantitative_objective_requires_an_oracle_even_without_quantitative_topic(objective, required):
    data = context("FINAL_STMG", "QUESTION_SET", "OPEN_QUESTIONS")
    data.update(topics=["Part de marché"], objectives=[objective])
    plan = effort_plan(P0Context(data))
    assert plan["quantitative_review_required"] is required
    assert ("INDEPENDENT_CALCULATION_ORACLE_REQUIRED" in plan["validations"]) is required
    assert plan["effort"] == ("HAUT_RISQUE_PEDAGOGIQUE" if required else "STANDARD")


@pytest.mark.parametrize("mutation", ["hash", "scope", "oversized"])
def test_evidence_pack_refuses_substitution_incomplete_or_oversized(mutation):
    app = service(P0GenerationDouble())
    _, prepared = candidate(app)
    pack = prepared["agentic"]["evidence_pack"]
    refs = prepared["references"]
    evidence = {pack["passages"][0]["evidence_id"]: pack["passages"][0]["text"]}
    if mutation == "hash":
        evidence[next(iter(evidence))] += "substitution"
    if mutation == "scope":
        evidence["outside"] = "other"
    if mutation == "oversized":
        evidence[next(iter(evidence))] = "x" * 16001
    with pytest.raises(ValueError, match="P0_EVIDENCE_PACK"):
        evidence_pack(P0Context(prepared["context"]), refs, evidence)


def test_normal_unbound_review_has_no_hidden_transport_or_calculation_pass():
    double = P0GenerationDouble()
    app = service(double)
    view, prepared = candidate(app)
    assert prepared["agentic"]["evidence_pack"]["authority"] == "NONE"
    assert prepared["agentic"]["quality"]["calculations"] != "CALCULS_VERIFIES"
    result = app.execute("review", {"command_id": token_hex(16), **identity(view)})
    assert result["state"] == "AUTHORIZATION_REQUIRED" and result["provider_attempts"] == 0
    assert len(double.requests) == 1 and not app.review_consumed


def test_independent_ag04_bounded_local_correction_revalidation_and_exact_memory():
    double = P0GenerationDouble()
    app = service(double)
    critic = TechnicalCritic()
    app.review = P0ReviewAdapter(critic, authorize=lambda request: True)
    view, _ = candidate(app)
    parent = app.saved_source(view["production_ref"], view["version_ref"])
    command = {"command_id": token_hex(16), **identity(view)}
    reviewed = app.execute("review", command)
    assert app.execute("review", command) == reviewed and len(critic.requests) == 1
    assert reviewed["quality"]["review"] == "RESERVE"
    assert reviewed["report"]["correction_required"] is True
    request = critic.requests[0]
    assert request.target_payload["context"]["level"] == "BTS_CG_YEAR_2"
    assert request.resolved_inputs["passages"][0]["text"].startswith("Synthetic unit")
    assert request.coverage_context["independence_requirements"]["separate_from_generation"] is True
    saved = app.saved_source(view["production_ref"], view["version_ref"])
    assert saved.data["reviews"][0]["bundle_sha256"] == view["bundle_sha256"]
    assert saved.data["provenance"]["PLAN_SHA256"]
    corrected = app.execute(
        "correct",
        {
            "command_id": token_hex(16),
            **identity(view),
            "review_sha256": reviewed["review_sha256"],
            "edits": {"title": "Correction locale explicitement demandée"},
        },
    )
    child = corrected["view"]
    assert corrected["revalidation"]["status"] == "PASS"
    assert (
        corrected["provider_attempts"] == 0
        and child["lineage"]["parent_version_ref"] == view["version_ref"]
    )
    assert app.read(parent.production_ref, parent.version_ref) == view
    assert not app.saved_source(child["production_ref"], child["version_ref"]).data["reviews"]
    with pytest.raises(ValueError, match="P0_CORRECTION_ALREADY_CONSUMED"):
        app.execute(
            "correct",
            {
                "command_id": token_hex(16),
                **identity(view),
                "review_sha256": reviewed["review_sha256"],
                "edits": {"title": "Second correction"},
            },
        )
    with pytest.raises(ValueError, match="P0_REVIEW_ALREADY_CONSUMED"):
        app.execute("review", {"command_id": token_hex(16), **identity(child)})
    assert len(critic.requests) == 1 and len(double.requests) == 1


@pytest.mark.parametrize("failure", ["unavailable", "substitution", "refusal"])
def test_critic_refusal_unknown_and_source_mutation_do_not_retry_or_publish(failure):
    app = service(P0GenerationDouble())
    critic = TechnicalCritic(mutate=failure == "substitution", fail=failure == "unavailable")
    app.review = P0ReviewAdapter(critic, authorize=lambda request: failure != "refusal")
    view, _ = candidate(app)
    command = {"command_id": token_hex(16), **identity(view)}
    if failure == "refusal":
        assert (
            app.execute("review", command)["state"] == "AUTHORIZATION_REQUIRED"
            and not critic.requests
        )
    else:
        with pytest.raises(ValueError):
            app.execute("review", command)
        app.execute("review", command)
        assert len(critic.requests) == 1 and not app.reports
        with pytest.raises(ValueError, match="P0_REVIEW_ALREADY_CONSUMED"):
            app.execute("review", {**command, "command_id": token_hex(16)})


def test_public_plan_and_cached_result_cannot_mutate_application_memory():
    app = service(P0GenerationDouble())
    _, prepared = candidate(app)
    stored = app.plans[next(iter(app.records))]["effort"]
    prepared["agentic"]["plan"]["effort"] = "forged"
    assert app.plans[next(iter(app.records))]["effort"] == stored
