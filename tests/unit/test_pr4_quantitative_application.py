"""PR4 quantities through Application; all institutional/output data are synthetic."""
from copy import deepcopy
from secrets import token_hex

import pytest

from tests.support.p0_generation_double import P0GenerationDouble
from tests.unit.test_bts_institutional_preparation import context, prepare, service


class QuantityDouble(P0GenerationDouble):
    def __init__(self, document, question, answer):
        super().__init__()
        self.document, self.question, self.answer = document, question, answer

    def generate(self, *, request):
        result = dict(super().generate(request=request))
        result["sections"][0]["text"] = self.document
        result["questions"][0]["prompt"] = self.question
        result["corrections"][0].update(expected_answer=self.answer, rationale="Réponse synthétique de test ; aucun oracle indépendant exécuté.")
        return result


def generated(objective, document, question, answer):
    app, _, _ = service()
    double = QuantityDouble(document, question, answer)
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
