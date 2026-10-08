"""PR4 quantities through Application; all institutional/output data are synthetic."""
from copy import deepcopy
from secrets import token_hex

import pytest

from tests.support.p0_generation_double import P0GenerationDouble
from tests.unit.test_bts_institutional_preparation import context, prepare, service


class QuantityDouble(P0GenerationDouble):
    def __init__(self, document, question, answer, rationale=None):
        super().__init__()
        self.document, self.question, self.answer = document, question, answer
        self.rationale = rationale or "Réponse synthétique de test ; aucun oracle indépendant exécuté."

    def generate(self, *, request):
        result = dict(super().generate(request=request))
        result["sections"][0]["text"] = self.document
        result["questions"][0]["prompt"] = self.question
        result["corrections"][0].update(expected_answer=self.answer, rationale=self.rationale)
        return result


def generated(objective, document, question, answer, *, rationale=None):
    app, _, _ = service()
    double = QuantityDouble(document, question, answer, rationale)
    app.generation = double
    data = context()
    data.update(topics=["Application synthétique"], objectives=[objective])
    prepared = prepare(app, data)
    result = app.execute("generate", {"command_id": token_hex(16),
        "preparation_ref": prepared["preparation_ref"], "preparation_sha256": prepared["preparation_sha256"]})
    assert result["view"]["pedagogical_context"]["institutional_resolution"]["process"]["element_type"] == "PROCESS"
    assert len(double.requests) == 1
    return app, prepared, result


@pytest.mark.parametrize("answer", ["6", "6 salariés supplémentaires", "L’association compte 6 salariés de plus."])
@pytest.mark.parametrize("question", [
    "Combien de salariés supplémentaires l’association compte-t-elle ?",
    "Déterminez la différence entre les effectifs final et initial.",
    "Quelle est la variation du nombre de personnes ?",
])
def test_staff_variation_requires_control_through_admitted_synthetic_context(answer, question):
    app, prepared, result = generated("Analyser la variation des effectifs entre deux dates",
        "L’association passe de 18 salariés à 24 salariés", question, answer)
    assert prepared["agentic"]["plan"]["calculation_applicability"]["status"] == "REQUIRED"
    quality = result["agentic"]["quality"]
    assert quality["calculations"] == "ECHEC"
    assert quality["calculation_reason"] == "INDEPENDENT_ORACLE_NOT_EXECUTED"
    view = result["view"]
    command = {"command_id": token_hex(16), **{k: view[k] for k in ("production_ref", "version_ref", "bundle_sha256")}}
    validated = app.execute("validate", command)
    assert validated["quality"]["calculations"] == "ECHEC"
    reviewed = app.execute("review", {**command, "command_id": token_hex(16)})
    assert reviewed["provider_attempts"] == 0
    assert reviewed["quality"]["calculations"] == "ECHEC"
    saved = app.saved_source(view["production_ref"], view["version_ref"])
    assert saved.view.version_ref == view["version_ref"]


@pytest.mark.parametrize("objective,document,question,answer", [
    ("Déterminer la distance parcourue", "Un trajet comprend deux étapes de 5 km et 7 km.", "Quelle distance totale ?", "12 km"),
    ("Estimer la durée totale", "Deux tâches durent 2 heures et 3 heures.", "Quelle durée totale ?", "5 heures"),
    ("Analyser la variation du volume traité", "Le service traite 12 dossiers puis 19 dossiers.", "Quelle est la différence de volume ?", "7 dossiers supplémentaires"),
    ("Expliquer l’organisation", "Situation sans données quantitatives.", "Présentez le résultat.", "7 articles supplémentaires"),
])
def test_non_monetary_measures_or_numeric_answer_with_unit_require_control(objective, document, question, answer):
    _, _, result = generated(objective, document, question, answer)
    assert result["agentic"]["quality"]["calculations"] == "ECHEC"


def test_revision_adds_quantity_without_inheriting_parent_non_applicability():
    app, _, result = generated("Identifier les acteurs de l’association fondée en 2024",
        "L’association associe des bénévoles et des adhérents.", "Présentez leurs rôles.", "Les bénévoles organisent les activités.")
    assert result["agentic"]["quality"]["calculations"] == "NON_APPLICABLE"
    parent = result["view"]
    original = deepcopy(app.records[parent["version_ref"]].mutable_copy())
    child = app.execute("revise", {"command_id": token_hex(16), **{k: parent[k] for k in ("production_ref", "version_ref", "bundle_sha256")},
        "edits": {"corrections": [{"question_id": "Q01", "expected_answer": "6 salariés supplémentaires", "rationale": "Quantité synthétique ajoutée à la révision."}]}})
    assert child["quality"]["calculations"] == "ECHEC"
    assert child["quality"]["review"] == "RESERVE"
    assert child["view"]["version_ref"] != parent["version_ref"]
    assert app.records[parent["version_ref"]].mutable_copy() == original
    assert app.saved_source(child["view"]["production_ref"], child["view"]["version_ref"]).data["reviews"] == ()


@pytest.mark.parametrize("objective,expected", [
    ("Identifier les acteurs de l’association fondée en 2024", "NON_APPLICABLE"),
    ("Expliquer les rôles des acteurs en 2024", "NON_APPLICABLE"),
    ("Analyser les stratégies de l’organisation", "A_DETERMINER"),
])
def test_year_is_not_an_arithmetic_proof_and_analysis_is_not_a_qualitative_proof(objective, expected):
    _, _, result = generated(objective, "L’association est fondée en 2024.",
        "Présentez les rôles des acteurs.", "Les bénévoles assurent l’organisation.")
    assert result["agentic"]["quality"]["calculations"] == expected


def assert_consumed_quality(app, result, expected):
    view = result["view"]
    quality = result.get("quality", result.get("agentic", {}).get("quality"))
    assert quality["calculations"] == expected
    assert quality["human_review"] == "HUMAN_REVIEW_REQUIRED"
    command = {k: view[k] for k in ("production_ref", "version_ref", "bundle_sha256")}
    validated = app.execute("validate", {"command_id": token_hex(16), **command})
    assert validated["quality"]["calculations"] == expected
    reviewed = app.execute("review", {"command_id": token_hex(16), **command})
    assert reviewed["provider_attempts"] == 0
    assert reviewed["quality"]["calculations"] == expected
    assert reviewed["quality"]["human_review"] == "HUMAN_REVIEW_REQUIRED"
    saved = app.saved_source(view["production_ref"], view["version_ref"])
    assert saved.view.version_ref == view["version_ref"]
    assert saved.view.data["bundle_sha256"] == view["bundle_sha256"]
    assert app.read(view["production_ref"], view["version_ref"]) == view
    assert app.read(view["production_ref"], view["version_ref"], teacher=True)["corrections"]
    assert "corrections" not in view


@pytest.mark.parametrize("answer,rationale", [
    ("42", "Réunir les chaises des deux salles."),
    ("42 chaises disponibles.", "Réunir les chaises des deux salles."),
    ("Chaises disponibles : 42.", "Réunir les chaises des deux salles."),
    ("Il y a 42 chaises disponibles.", "Réunir les chaises des deux salles."),
    ("La réunion dispose de 42 chaises.", "Réunir les chaises des deux salles."),
    ("Il y a 42 chaises disponibles.", "18 + 24 = 42."),
])
def test_review_residual_total_from_qualitative_context_is_formulation_invariant(answer, rationale):
    app, prepared, result = generated("Expliquer l’organisation de la réunion.",
        "La salle A contient 18 chaises et la salle B contient 24 chaises.",
        "Donnez le total des chaises disponibles pour la réunion.", answer, rationale=rationale)
    assert prepared["agentic"]["plan"]["calculation_applicability"]["status"] == "NOT_REQUIRED"
    assert result["agentic"]["plan"]["calculation_applicability"]["status"] == "REQUIRED"
    assert result["agentic"]["quality"]["calculation_reason"] == "INDEPENDENT_ORACLE_NOT_EXECUTED"
    assert_consumed_quality(app, result, "ECHEC")


@pytest.mark.parametrize("unit", ["dossiers", "lampes", "minutes"])
def test_review_residual_total_does_not_depend_on_a_unit_lexicon(unit):
    app, prepared, result = generated("Expliquer l’organisation de l’activité.",
        f"Le premier groupe dispose de 18 {unit} et le second de 24 {unit}.",
        f"Donnez le total des {unit}.", f"Il y a 42 {unit}.", rationale="Réunir les deux groupes.")
    assert prepared["agentic"]["plan"]["calculation_applicability"]["status"] == "NOT_REQUIRED"
    assert_consumed_quality(app, result, "ECHEC")


@pytest.mark.parametrize("answer", ["Il y a 42 objets.", "Objets : 42."])
def test_review_residual_numeric_answer_without_operation_keyword_requires_control(answer):
    app, prepared, result = generated("Expliquer l’organisation de l’activité.",
        "Des objets sont disponibles.", "Présentez la réponse.", answer)
    assert prepared["agentic"]["quality"]["calculations"] == "NON_APPLICABLE"
    assert_consumed_quality(app, result, "ECHEC")


def test_review_residual_unresolved_quantity_cannot_inherit_qualitative_non_applicability():
    app, prepared, result = generated("Expliquer l’organisation de la réunion.",
        "La salle A accueille 18 personnes et la salle B en accueille 24.",
        "Présentez l’organisation de la réunion.", "Les groupes occupent les salles.")
    assert prepared["agentic"]["quality"]["calculations"] == "NON_APPLICABLE"
    assert result["agentic"]["plan"]["calculation_applicability"]["status"] == "UNDETERMINED"
    assert_consumed_quality(app, result, "A_DETERMINER")


@pytest.mark.parametrize("date", ["2024", "2024-10-09", "09/10/2024", "9 octobre 2024"])
def test_review_residual_contextual_dates_preserve_qualitative_witnesses(date):
    app, prepared, result = generated("Identifier les acteurs de l’association.",
        f"L’association est fondée le {date}.", "Présentez les acteurs et leur date de création.",
        f"Les bénévoles ont fondé l’association en {date}.")
    assert prepared["agentic"]["quality"]["calculations"] == "NON_APPLICABLE"
    assert_consumed_quality(app, result, "NON_APPLICABLE")


def test_review_residual_revision_introduces_total_and_preserves_parent_and_identity():
    app, _, parent_result = generated("Expliquer l’organisation de la réunion.",
        "Les participants se réunissent dans les salles.", "Présentez l’organisation.",
        "Les groupes occupent les salles.")
    assert parent_result["agentic"]["quality"]["calculations"] == "NON_APPLICABLE"
    parent = parent_result["view"]
    original = deepcopy(app.records[parent["version_ref"]].mutable_copy())
    child = app.execute("revise", {"command_id": token_hex(16),
        **{k: parent[k] for k in ("production_ref", "version_ref", "bundle_sha256")},
        "edits": {"sections": [{**original["sections"][0], "text":
            "La salle A contient 18 chaises et la salle B contient 24 chaises."}],
            "questions": [{**original["questions"][0], "prompt":
                "Donnez le total des chaises disponibles pour la réunion."}],
            "corrections": [{"question_id": "Q01", "expected_answer": "Il y a 42 chaises disponibles.",
                "rationale": "Réunir les chaises des deux salles."}]}})
    assert child["provider_attempts"] == 0
    assert child["quality"]["review"] == "RESERVE"
    assert app.plans[child["view"]["version_ref"]]["calculation_applicability"]["status"] == "REQUIRED"
    assert_consumed_quality(app, child, "ECHEC")
    assert app.records[parent["version_ref"]].mutable_copy() == original
    assert app.read(parent["production_ref"], parent["version_ref"]) == parent
    assert app.saved_source(child["view"]["production_ref"], child["view"]["version_ref"]).data["reviews"] == ()
    with pytest.raises(ValueError, match="P0_VERSION_CHANGED"):
        app.execute("validate", {"command_id": token_hex(16),
            "production_ref": child["view"]["production_ref"], "version_ref": child["view"]["version_ref"],
            "bundle_sha256": parent["bundle_sha256"]})



@pytest.mark.parametrize("document,expected", [
    ("Expression : 2024-10-09 = 2005.", "ECHEC"),
    ("Expression : 15+2024-10-09.", "ECHEC"),
    ("La salle accueille 2024 personnes.", "A_DETERMINER"),
])
def test_review_residual_date_filter_cannot_erase_operation_or_quantity(document, expected):
    app, prepared, result = generated("Expliquer l’organisation de la réunion.",
        document, "Présentez l’organisation.", "Les groupes occupent les salles.",
        rationale="Réponse qualitative.")
    assert prepared["agentic"]["quality"]["calculations"] == "NON_APPLICABLE"
    assert_consumed_quality(app, result, expected)
