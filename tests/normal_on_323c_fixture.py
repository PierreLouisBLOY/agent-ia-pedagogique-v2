"""Only synthetic sources, authority documents, secret and Responses effects.

The normal CLI, factories, exact inventory/source-coverage guards, finalization,
consent, native LOCK/budget ledger, parsing, persistence and writer stay real.
No synthetic admission below is an owner decision or provider permission.
"""
import json
from copy import deepcopy

from backend.adapters.outbound.generation.openai.p0_exercise_schema import exercise_content_schema
from backend.modules.knowledge_reference.contracts.dto.admitted_institutional_sources import (
    ADMITTED_DOCUMENTS,
    OWNER_ADMISSION_SHA256,
)
from tests.exercise_quality_fixture import blueprint
from tests.test_normal_on_323a import f


def install(monkeypatch, *, invalid_response=False, invalid_focus=False):
    old_catalog = f.Catalog
    old_context = f.context
    old_configuration = f.configuration
    old_install = f.install_boundaries

    class SyntheticCatalog(old_catalog):
        def __init__(self):
            super().__init__()
            for row in self.data["official_framework_element"]:
                if row["id"] == "question:SGN_PREMIERE":
                    row["official_label"] = "1.1 Comment un individu devient-il acteur dans une organisation ?"
                    if invalid_focus:
                        row["official_label"] = "1.1 Comment définir les différents types d'organisation ? Comment un individu devient-il acteur dans une organisation ?"
            self.data["official_framework_element"].append({
                "id": "capacity:SGN_PREMIERE:communication", "framework_version_id": "version:SGN_PREMIERE",
                "parent_element_id": "question:SGN_PREMIERE", "element_type": "CAPACITY",
                "official_label": "Analyser les composantes synthétiques d'une communication",
                "document_reference_id": "locator:SGN_PREMIERE"})

    def context():
        value = old_context()
        value["contract_id"] = "P0-CONTEXT-EXERCISE-1.0"
        value["exercise_focus_justification"] = "QUALIFICATION SYNTHETIQUE : analyser la perception d'un message puis clarifier la communication."
        value["institutional"]["capacity_refs"].append("capacity:SGN_PREMIERE:communication")
        return value

    def boundaries(monkeypatch, control):
        catalogue = old_install(monkeypatch, control)
        old_resolver = f.catalog_factory.stmg_alignment

        def source_port(target, *, selection=None, reference=None, matrix=False, mode="LEGACY", question_fingerprints=False, focus_witness=False):
            result = old_resolver(target, selection=selection, reference=reference, matrix=matrix, mode=mode, question_fingerprints=question_fingerprints,focus_witness=focus_witness)
            if selection is not None:
                # A declared synthetic proof at the source port, not a doubled guard.
                candidate_id, doc_sha = next(iter(ADMITTED_DOCUMENTS.items()))
                result.update(qualification_sha256="d" * 64, owner_admission_sha256=OWNER_ADMISSION_SHA256,
                              document_provenance={"candidate_id": candidate_id, "sha256": doc_sha},
                              capacity_scope="SELECTED_THEME_OR_QUESTION_NO_NARROWER_CLAIM")
            return result

        monkeypatch.setattr(f.catalog_factory, "stmg_alignment", source_port)
        return catalogue

    def configuration(root, *, proposed=False):
        path, target, saved, receipts = old_configuration(root, proposed=proposed)
        envelope = json.loads(path.read_bytes())
        permission = json.loads(f.Path(envelope["permission"]["path"]).read_bytes())
        decision = json.loads(f.Path(envelope["decision"]["path"]).read_bytes())
        permission["output_schema_sha256"] = f.sha(f.canonical(exercise_content_schema()))
        decision["permission_policy_sha256"] = f.sha(f.canonical({key: value for key, value in permission.items() if key != "owner_decision_sha256"}))
        envelope["decision"] = f.artifact(root, "SYNTHETIC-decision-NOT-OWNER-ACCORD.json", decision)
        permission["owner_decision_sha256"] = envelope["decision"]["sha256"]
        envelope["permission"] = f.artifact(root, "SYNTHETIC-permission-NOT-LIVE.json", permission)
        path.write_bytes(f.canonical(envelope))
        return path, target, saved, receipts

    _, content = blueprint()
    content["title"] = "Perception et communication Démonstration locale"
    content["exercise"]["situation"]["text"] = "Exercice synthétique de qualification locale, sans appel fournisseur. " + content["exercise"]["situation"]["text"]
    content["limitations"].append("Les preuves et admissions institutionnelles de cette fixture de qualification sont synthétiques ; aucun rattachement officiel réel n'est créé.")
    if invalid_response:
        content["exercise"]["questions"][0]["document_ids"] = ["D99"]
    monkeypatch.setattr(f, "Catalog", SyntheticCatalog)
    monkeypatch.setattr(f, "context", context)
    monkeypatch.setattr(f, "configuration", configuration)
    monkeypatch.setattr(f, "install_boundaries", boundaries)
    monkeypatch.setattr(f, "CONTENT", deepcopy(content))
    return f
