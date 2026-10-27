"""Official identity facts observed publicly; fictional teaching situation is separate."""

from copy import deepcopy
from hashlib import sha256
from io import BytesIO
from zipfile import ZipFile

import pytest

from backend.adapters.inbound.application.organization_evidence import OrganizationEvidenceInbound
from backend.adapters.outbound.export.course_word import CourseOOXMLWordWriter
from backend.adapters.outbound.generation.openai.p0_content import bind_p0_content
from backend.modules.materialization_export.application.services.exercise_projection import (
    project_exercise,
)
from backend.modules.resource_library.application.queries.organization_evidence import (
    ReadOrganizationEvidence,
)
from backend.modules.resource_library.contracts.dto.organization_evidence import (
    OrganizationEvidence,
)
from tests.test_case_study_324 import case_blueprint


def official_identity():
    return OrganizationEvidence(
        {
            "schema": "PUBLIC-ORGANIZATION-EVIDENCE-1.0",
            "organization_id": "siren:306138900",
            "organization_label": "DECATHLON",
            "fact": "Dénomination : DECATHLON ; SIREN : 306138900 ; forme juridique : Société européenne.",
            "source_url": "https://annuaire-entreprises.data.gouv.fr/entreprise/306138900",
            "publisher": "INSEE / Sirene, via Annuaire des Entreprises",
            "retrieved_on": "2026-10-26",
            "license": "Licence Ouverte / Open Licence 2.0",
            "license_url": "https://www.data.gouv.fr/datasets/base-sirene-des-entreprises-et-de-leurs-etablissements-siren-siret",
            "reuse_scope": "Trois champs d’identité Sirene uniquement ; ni logo, ni site composite, ni œuvre tierce.",
            "attribution": "INSEE, répertoire Sirene ; consultation publique du 26 octobre 2026",
            "kind": "DOCUMENTED_FACT",
            "admission": "PROPOSED_NOT_CANONICALLY_ADMITTED",
        }
    )


def real_organization_case():
    dispatch, content = case_blueprint()
    exercise = content["exercise"]
    evidence = official_identity()
    text = evidence.documentary_text()
    evidence_id = "evidence:" + "d" * 32
    dispatch["references"].append(
        {
            "evidence_id": evidence_id,
            "source_ref": str(evidence.data["source_url"]),
            "locator": "Trois champs Sirene, consultation publique du 26 octobre 2026, proposition non admise canoniquement",
            "checksum_or_version": "SIRENE_IDENTITY_2026-10-26",
            "excerpt_sha256": sha256(text.encode()).hexdigest(),
            "provenance_label": dispatch["references"][0]["provenance_label"],
        }
    )
    dispatch["evidence"][evidence_id] = text
    # New local fixture, never presented as recovered or teacher-accepted content.
    exercise["documents"][0].update(
        title="Fiche d’identité publique et source",
        text=text,
        provenance="SUPPLIED_REFERENCE",
        evidence_id=evidence_id,
    )
    exercise["documents"][1]["text"] = (
        "Situation entièrement fictive : dans un atelier pédagogique imaginé autour de DECATHLON, Léa demande un relevé à Samir. Le message ne précise pas l’heure souhaitée ; Samir propose 11 h 15. Aucun de ces échanges ne décrit un salarié ou une pratique réelle."
    )
    exercise["situation"]["text"] = (
        "Étude pédagogique locale : distinguer une identité publique documentée d’une communication professionnelle fictive."
    )
    case = exercise["case_study"]
    case["organizations"][0]["label"] = "DECATHLON"
    case["data"] = [
        {
            "data_id": "A1",
            "organization_id": "O1",
            "kind": "DOCUMENTED_FACT",
            "text": str(evidence.data["fact"]),
            "document_id": "D1",
            "quote": str(evidence.data["fact"]),
        },
        {
            "data_id": "A2",
            "organization_id": "O1",
            "kind": "FICTION",
            "text": "Léa et Samir sont des personnages fictifs ; leur échange n’est pas un fait sur cette entreprise.",
            "document_id": "D2",
            "quote": None,
        },
        {
            "data_id": "A3",
            "organization_id": "O1",
            "kind": "INFERENCE",
            "text": "La fiche d’identité seule ne permet pas de conclure au style de communication interne.",
            "document_id": "D1",
            "quote": "DECATHLON",
        },
    ]
    case["missions"][0]["data_ids"] = ["A1", "A2", "A3"]
    prompts = [
        "Relevez le SIREN et la forme juridique dans D1. Identifiez la source et sa date de consultation.",
        "Séparez les faits documentés de D1 et les événements fictifs de D2. Pourquoi ne peut-on pas les confondre ?",
        "Dans la situation fictive D2, comparez le besoin de Léa et l’information dont dispose Samir. Quelle précision manque ?",
        "Rédigez une demande de clarification professionnelle dans la situation fictive D2, sans attribuer une intention à Samir.",
    ]
    answers = [
        "D1 : SIREN 306138900 ; Société européenne ; INSEE/Sirene via Annuaire des Entreprises, consulté le 26 octobre 2026.",
        "D1 documente trois champs d’identité ; D2 est explicitement inventé. La fiction ne décrit pas des pratiques réelles de DECATHLON.",
        "D2 ne précise pas l’heure souhaitée. La proposition de 11 h 15 doit être confrontée au besoin exact de Léa, qui reste à préciser.",
        "Bonjour Samir, merci pour ton retour. Pour convenir de l’heure d’envoi du relevé, peux-tu confirmer ce qui est possible ? Je vais préciser mon échéance. Merci.",
    ]
    for i, (question, answer) in enumerate(
        zip(exercise["questions"], exercise["teacher_answers"], strict=True)
    ):
        question.update(
            prompt=prompts[i], document_ids=["D1"] if i == 0 else ["D1", "D2"] if i == 1 else ["D2"]
        )
        question["success_criteria"] = [
            "Justification à partir des documents identifiés",
            "Distinction entre fait, interprétation et fiction",
        ]
        answer.update(
            expected_answer=answers[i],
            rationale="Les affirmations doivent être reliées au document et à son statut.",
            vigilance="Ne pas attribuer les échanges inventés à des salariés réels.",
            remediation="Classer chaque affirmation : citation documentaire, hypothèse ou fiction.",
        )
    content["limitations"].append(
        "Corpus local de qualification, non admis canoniquement et non accepté par un enseignant."
    )
    return dispatch, content


def test_external_source_unbound_refuses_and_fixture_remains_a_proposal():
    with pytest.raises(ValueError, match="BLOCKED_EXTERNAL_SOURCE_PROVIDER"):
        OrganizationEvidenceInbound(ReadOrganizationEvidence()).inspect("siren:306138900")

    class Fixture:
        def find(self, *, organization_id):
            return (official_identity(),)

    result = OrganizationEvidenceInbound(ReadOrganizationEvidence(Fixture())).inspect(
        "siren:306138900"
    )
    assert (
        result["canonical_admission"] == "NOT_GRANTED" and result["provider_generation_calls"] == 0
    )
    row = deepcopy(dict(official_identity().data))
    row["license"] = "NON_VERIFIEE"
    with pytest.raises(ValueError, match="P0_EXTERNAL_EVIDENCE_CONTRACT"):
        OrganizationEvidence(row)


def test_real_fact_fiction_inference_and_attribution_survive_both_word_exports():
    dispatch, content = real_organization_case()
    bundle = bind_p0_content(dispatch, content)
    for kind in ("student", "correction"):
        document = project_exercise(bundle, kind)
        with ZipFile(BytesIO(CourseOOXMLWordWriter().write(document))) as archive:
            xml = archive.read("word/document.xml").decode()
        for text in (
            "306138900",
            "Licence Ouverte",
            "Citation documentaire",
            "Interprétation à discuter",
            "Donnée fictive",
            "INSEE",
        ):
            assert text in xml
        assert ("Réponse attendue" in xml) == (kind == "correction")
