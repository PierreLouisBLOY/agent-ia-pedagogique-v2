"""A complete local reading exercise from an exact prepared excerpt, never AI."""

from collections.abc import Mapping

from backend.modules.pedagogical_context.contracts.dto.p0_context import P0Context
from backend.modules.pedagogical_design.application.commands.create_p0_candidate import (
    CreateP0Candidate,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import as_plain, object_data
from backend.modules.pedagogical_design.contracts.dto.p0_production import P0Production


class ProposeLocalReading:
    def execute(self, request: Mapping[str, object]) -> P0Production:
        context = P0Context(object_data(request["context"]))
        # No silent conversion of a rich exercise, chapter, or institutional scope.
        if context.resource_type != "EXERCISE" or context.data["contract_id"] not in {
            "R6-P0-CONTEXT-1.0", "P0-CONTEXT-2.0"
        }:
            raise ValueError("P0_LOCAL_PROPOSAL_PROFILE_UNSUPPORTED")
        if context.institutional is not None:
            context.require_institutional_dispatch()
        evidence = {str(k): str(v) for k, v in object_data(request["evidence"]).items()}
        if len(evidence) != 1:
            raise ValueError("P0_LOCAL_PROPOSAL_SINGLE_EXCERPT_REQUIRED")
        excerpt = next(iter(evidence.values()))
        # Preserve the complete prepared EXCERPT, not a claim to the full source.
        if len(excerpt) > 12000:
            raise ValueError("P0_LOCAL_PROPOSAL_EXCERPT_TOO_LONG")
        title = "Lecture critique du passage sélectionné"
        questions = [
            {"question_id": "Q1", "prompt": "Recopiez exactement le passage fourni. Distinguez ce texte de son titre et de son repère de provenance.", "options": []},
            {"question_id": "Q2", "prompt": "Le passage fourni suffit-il, à lui seul, à attester une définition complète, un exemple réel et une validation pédagogique ? Justifiez votre prudence.", "options": []},
        ]
        corrections = [
            {"question_id": "Q1", "expected_answer": excerpt,
             "rationale": "La réponse reproduit uniquement l'extrait préparé, dont le repère reste dans les références de la ressource."},
            {"question_id": "Q2", "expected_answer": "Ces trois affirmations ne sont pas attestées par le seul fait qu'un passage a été sélectionné. Chacune exige des éléments explicites et une vérification distincte.",
             "rationale": "La sélection technique d'une donnée ne constitue ni une preuve de complétude ni une validation du cours. Examiner le texte exact avant toute conclusion."},
        ]
        data = {key: as_plain(request[key]) for key in (
            "production_ref", "version_ref", "context", "context_sha256", "references", "lineage")}
        data.update(contract_id="R6-P0-PRODUCTION-1.0", title=title,
            sections=[{"section_id": "S1", "heading": "Extrait sélectionné", "text": excerpt},
                      {"section_id": "S2", "heading": "Méthode de lecture", "text": "Séparez le texte observé, sa provenance et les conclusions qu'il permet effectivement d'étayer. Les questions ci-dessous sont une construction pédagogique locale ; elles n'ajoutent aucune définition disciplinaire au passage."}],
            questions=questions, corrections=corrections, marking=[],
            limitations=["CANDIDATE — proposition locale à relire par l'enseignant.",
                         "Exercice de lecture critique uniquement ; ne constitue pas un cours disciplinaire complet. Aucun appel fournisseur."])
        return CreateP0Candidate().execute(data, evidence=evidence)
