"""Local understanding is deterministic proposal, never a provider intelligence score."""

import json

import pytest

from backend.adapters.inbound.api.p0_creation import P0CreationEndpoint
from backend.adapters.inbound.api.routes import P0_ROUTE_SPECS, resolve_p0_route
from backend.modules.work_orchestration.application.queries.propose_p0_intention import (
    ProposeP0Intention,
)

FAMILIES = [
    ("cours", "COURSE", "COURSE", None),
    ("exercice", "EXERCISE", "EXERCISE", None),
    ("questions ouvertes", "OPEN_QUESTIONS", "QUESTION_SET", "OPEN_QUESTIONS"),
    ("QCM", "QCM", "QUESTION_SET", "QCM"),
    ("quiz", "QUIZ", "QUESTION_SET", "QUIZ"),
    ("évaluation", "ASSESSMENT", "ASSESSMENT", None),
]
LEVELS = [
    ("Première STMG", "FIRST_STMG"),
    ("Terminale STMG", "FINAL_STMG"),
    ("BTS CG première année", "BTS_CG_YEAR_1"),
    ("BTS CG deuxième année", "BTS_CG_YEAR_2"),
]


def propose(text):
    return ProposeP0Intention().execute({"command_id": "a" * 32, "intention": text})


@pytest.mark.parametrize("word,family,kind,mode", FAMILIES)
@pytest.mark.parametrize("label,level", LEVELS)
def test_general_proposal_recognizes_family_and_explicit_level_without_matrix_ids(
    word, family, kind, mode, label, level
):
    constraints = " de 60 minutes, notée sur 20" if kind == "ASSESSMENT" else ""
    result = propose(f"Un {word} pour {label} sur la productivité{constraints}, difficulté standard ; "
                     "expliquer les facteurs de variation ; identifier les facteurs techniques.")
    assert result["contract_id"] == "P0-INTENTION-PROPOSAL-1.0"
    assert result["state"] == "CONTEXT_PROPOSED"
    output = result["proposal"]
    assert (output["family"], output["resource_type"], output["question_mode"], output["level"]) == (
        family, kind, mode, level)
    assert output["topics"] == ["la productivité"]
    assert len(output["objectives"]) == 2
    assert output["difficulty"] == "STANDARD"
    assert result["confirmation_required"] is True
    assert result["institutional_selection"] == "EXACT_CATALOG_CONFIRMATION_REQUIRED"
    assert result["authority"] == "NONE" and result["provider_attempts"] == 0


@pytest.mark.parametrize("text,field,candidates", [
    ("Un cours ou un exercice pour Première STMG sur la concurrence ; expliquer les rôles.",
     "family", {"COURSE", "EXERCISE"}),
    ("Un quiz Première STMG ou Terminale STMG sur la concurrence ; expliquer les rôles.",
     "level", {"FIRST_STMG", "FINAL_STMG"}),
    ("Une évaluation BTS CG première année ou deuxième année sur la concurrence ; expliquer les rôles.",
     "level", {"BTS_CG_YEAR_1", "BTS_CG_YEAR_2"}),
    ("Une évaluation BTS CG première année sur la concurrence 60 minutes ou 90 minutes ; expliquer les rôles.",
     "duration_minutes", {60, 90}),
    ("Une évaluation BTS CG première année sur la concurrence notée sur 20 ou notée sur 30 ; expliquer les rôles.",
     "total_points", {20, 30}),
    ("Un cours Première STMG sur la concurrence, difficulté standard ou avancée ; expliquer les rôles.",
     "difficulty", {"STANDARD", "ADVANCED"}),
])
def test_ambiguity_is_explicit_and_never_resolved_by_guess(text, field, candidates):
    result = propose(text)
    assert result["state"] == "CLARIFICATION_REQUIRED"
    assert result["proposal"][field] is None
    found = next(item for item in result["ambiguities"] if item["field"] == field)
    assert set(found["candidates"]) == candidates


def test_bts_without_year_and_institutional_teaching_without_admission_remain_unconfirmed():
    result = propose("Un cours BTS CG sur la facturation, difficulté standard ; expliquer les étapes.")
    assert result["proposal"]["level"] is None and "level" in result["missing_fields"]
    secondary = propose("Un cours Terminale STMG sur la concurrence, difficulté standard ; expliquer les rôles.")
    assert secondary["proposal"]["teaching_hint"] is None
    explicit = propose("Un cours Première STMG en Management sur les finalités, difficulté standard ; expliquer les rôles.")
    assert explicit["proposal"]["teaching_hint"] == "Management"
    assert explicit["institutional_selection"] == "EXACT_CATALOG_CONFIRMATION_REQUIRED"


def test_outside_matrix_subject_is_preserved_without_fake_official_relation():
    text = "Un QCM BTS CG deuxième année sur les fonctions du tableur, difficulté avancée ; identifier les références relatives."
    result = propose(text)
    assert result["proposal"]["topics"] == ["les fonctions du tableur"]
    assert result["proposal"]["difficulty"] == "ADVANCED"
    assert result == propose(text)
    assert result["implementation"] == "DETERMINISTIC_APPLICATION_PROPOSAL"


def test_non_assessment_duration_and_points_are_preserved_and_not_silently_dropped():
    result = propose("Un exercice Première STMG sur la concurrence, 60 minutes et 20 points, difficulté standard ; expliquer les rôles.")
    assert result["proposal"]["duration_minutes"] == 60
    assert result["proposal"]["total_points"] == 20
    assert {"duration_constraint_application", "points_constraint_application"} <= set(result["missing_fields"])
    assert result["state"] == "CLARIFICATION_REQUIRED"


def test_compound_teaching_hint_does_not_select_silently_between_distinct_teachings():
    result = propose("Un cours Terminale STMG en Management ou MSDGN sur les organisations ; expliquer les finalités.")
    assert result["proposal"]["teaching_hint"] is None
    assert next(row for row in result["ambiguities"] if row["field"] == "teaching_hint")["candidates"] == [
        "Management, sciences de gestion et numérique", "Management"]
    compound = propose("Un cours Terminale STMG en Management, sciences de gestion et numérique sur les organisations ; expliquer les finalités.")
    assert compound["proposal"]["teaching_hint"] == "Management, sciences de gestion et numérique"


def test_compound_duration_is_one_exact_constraint():
    result = propose("Une évaluation BTS CG deuxième année de 1h30 sur la facturation, notée sur 20 ; expliquer les étapes.")
    assert result["proposal"]["duration_minutes"] == 90
    assert not any(row["field"] == "duration_minutes" for row in result["ambiguities"])


@pytest.mark.parametrize("constraint,code", [("481 minutes", "DURATION"), ("201 points", "POINTS")])
def test_outside_context_bounds_is_rejected_before_preparation(constraint, code):
    with pytest.raises(ValueError, match="P0_INTENTION_" + code):
        propose("Une évaluation BTS CG deuxième année sur la facturation, " + constraint)


@pytest.mark.parametrize("text,operation", [
    ("Modifier le cours actif pour Terminale STMG.", "MODIFY"),
    ("Exporter le QCM actif en Word.", "EXPORT"),
    ("Relire le quiz actif.", "REVIEW"),
])
def test_existing_version_actions_never_become_a_new_preparation(text, operation):
    result = propose(text)
    assert result["state"] == "OUT_OF_SCOPE"
    assert result["unsupported_operation"] == operation
    assert result["provider_attempts"] == 0


@pytest.mark.parametrize("body", [
    {}, {"command_id": "a" * 32, "intention": "Un cours", "provider": "ignored?"},
    {"command_id": "A" * 32, "intention": "Un cours"},
    {"command_id": "a" * 32, "intention": ""},
    {"command_id": "a" * 32, "intention": "x" * 4001},
    {"command_id": "a" * 32, "intention": "Un cours\u202e"},
])
def test_request_contract_and_text_are_bounded_and_closed(body):
    with pytest.raises(ValueError, match="P0_INTENTION_"):
        ProposeP0Intention().execute(body)


def test_companion_does_not_mutate_historical_registry_or_dispatch_creation():
    from tests.architecture.test_local_browser_product_boundary import route_contract_violations
    from tests.unit.test_r6_recipe_guard import ROOT

    assert ("POST", "/api/v2/p0/intention") not in P0_ROUTE_SPECS
    assert resolve_p0_route("POST", "/api/v2/p0/intention")[0] == "intention"
    assert route_contract_violations(ROOT) == []

    def forbidden(*args, **kwargs):
        raise AssertionError("Intention must not read, generate, review or persist.")

    endpoint = P0CreationEndpoint(forbidden, forbidden, [], nonce="unit-no-secret",
        intention_execute=ProposeP0Intention().execute)
    payload = json.dumps({"command_id": "a" * 32,
                          "intention": "Un cours Première STMG sur les finalités."}).encode()
    status, _, raw, template = endpoint.respond("POST", "/api/v2/p0/intention", payload, "unit.intent")
    assert status == 200 and template == "/api/v2/p0/intention"
    assert json.loads(raw)["data"]["provider_attempts"] == 0
    duplicate = b'{"command_id":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","intention":"cours","intention":"quiz"}'
    assert endpoint.respond("POST", "/api/v2/p0/intention", duplicate, "unit.duplicate")[0] == 409


@pytest.mark.parametrize("method,target", [
    ("GET", "/api/v2/p0/intention"), ("POST", "/api/v2/p0/intention/"),
    ("POST", "/api/v2/p0/intention?latest=true"), ("POST", "/api/v2/p0/%69ntention"),
])
def test_intention_route_does_not_accept_alias_method_or_decoding(method, target):
    with pytest.raises(ValueError, match="P0_ROUTE_REJECTED"):
        resolve_p0_route(method, target)
