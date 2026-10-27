"""New local original for quality review, not a provider result or a 7c99 repair."""
from copy import deepcopy
from hashlib import sha256

from backend.modules.pedagogical_context.contracts.dto.p0_context import P0Context
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import fingerprint
from backend.modules.pedagogical_design.contracts.dto.p0_production import P0_PROVENANCE_LABEL

SOURCE_URL = "https://eduscol.education.gouv.fr/sites/default/files/document/spe646annexe31063606pdf-84600.pdf"


def blueprint():
    from tests.unit.test_stmg_institutional_alignment import context as synthetic_context

    independent = synthetic_context("SGN_PREMIERE")
    independent["institutional"]["question_ref"] = "individu-acteur"
    reference = {"context": independent, "chapter": {"capabilities": [
        {"id": "C1", "source_ref": "comportements", "label": "Analyser des comportements dans une situation synthétique", "locator": "synthetic:capacity1"},
        {"id": "C2", "source_ref": "communication", "label": "Analyser une communication dans une situation synthétique", "locator": "synthetic:capacity2"},
    ]}}
    context = deepcopy(reference["context"])
    context["contract_id"] = "P0-CONTEXT-EXERCISE-1.0"
    context["exercise_focus_justification"] = "L'exercice travaille la perception d'un message et la communication interpersonnelle pour analyser une interaction dans une organisation."
    context.pop("course_format", None)
    context.update(resource_type="EXERCISE", topics=["Perception", "Communication interpersonnelle"],
                   objectives=["Distinguer un fait d'une interprétation", "Adapter une communication au contexte"])
    selection = context["institutional"]
    selection.update(capacity_refs=["comportements", "communication"], notion_refs=["perception", "communication-interpersonnelle"])
    capacities = [row for row in reference["chapter"]["capabilities"] if row["source_ref"] in selection["capacity_refs"]]
    resolution = {"contract_id": "STMG-RESOLUTION-1.0", "status": "CONTENT_GAP",
                  "selection_sha256": fingerprint(selection), "program_ref": selection["program_ref"],
                  "program_version": selection["program_version"],
                  "question": {"id": "individu-acteur", "official_label": "Comment un individu devient-il acteur dans une organisation ?"},
                  "capacities": [{"capacity_ref": row["source_ref"], "label": row["label"],
                                  "question_ref": "individu-acteur", "locator": row["locator"],
                                  "authority_status": "PUBLIC_SOURCE_VERIFIED_NOT_RUNTIME_ADMITTED"} for row in capacities],
                  "notions": [{"notion_ref": ref, "label": label, "question_ref": "individu-acteur"}
                              for ref, label in (("perception", "Perception"), ("communication-interpersonnelle", "Communication interpersonnelle"))]}
    context["institutional_resolution"] = resolution
    context["local_progression"] = {"chapter": None, "sequence": "Exercice perception", "week": None}
    typed = P0Context(context)
    excerpt = "Repères de travail locaux : perception, communication interpersonnelle et analyse des comportements."
    evidence_id = "evidence:" + "b" * 32
    dispatch = {"contract_id": "R6-P0-DISPATCH-1.0", "production_ref": "prod:" + "b" * 32,
                "version_ref": "ver:" + "b" * 32, "context": typed.as_dict(), "context_sha256": typed.sha256,
                "references": [{"evidence_id": evidence_id, "source_ref": "local-original:323B-quality-focus",
                                "locator": "Repères et capacités reformulés localement à partir du programme SGN page 5, sans admission runtime",
                                "checksum_or_version": "BO-special-1-2019-01-22-consultation-2026-10-25",
                                "excerpt_sha256": sha256(excerpt.encode()).hexdigest(), "provenance_label": P0_PROVENANCE_LABEL}],
                "evidence": {evidence_id: excerpt},
                "lineage": {"source_run_id": "run:" + "b" * 32, "source_step_id": "step:" + "b" * 32,
                            "evidence_set_ref": evidence_id, "source_request_id": "req:" + "b" * 32,
                            "conversation_id": "conv:" + "b" * 32, "context_sha256": typed.sha256,
                            "parent_version_ref": None}}
    public_excerpt = "Comment un individu devient-il acteur dans une organisation ?"
    public_id = "evidence:" + "c" * 32
    dispatch["references"].append({"evidence_id": public_id, "source_ref": SOURCE_URL,
                                   "locator": "Page 5, thème 1, question de gestion ; document public consulté le 25 octobre 2026",
                                   "checksum_or_version": "BO-special-1-2019-01-22",
                                   "excerpt_sha256": sha256(public_excerpt.encode()).hexdigest(),
                                   "provenance_label": P0_PROVENANCE_LABEL})
    dispatch["evidence"][public_id] = public_excerpt
    content = {"title": "Perception et communication professionnelle",
               "limitations": ["Rédaction locale originale de démonstration, sans génération OpenAI ni reprise du texte de 7c99.",
                               "Cadrage public consulté et capacités reformulées ; aucune admission canonique du catalogue ni acceptation enseignante créée."],
               "exercise": {
        "instructions": "Travail individuel, puis comparaison à deux. Appuyez chaque réponse sur un document identifié. Distinguez ce qui est observé de ce qui est supposé. Pour terminer, rédigez un message professionnel permettant de clarifier la situation. Temps de travail indicatif : 25 minutes.",
        "objectives": [{"capability_id": "C1", "goal": "Relier une interprétation au contexte, sans déduire une intention ou une personnalité d'un acte isolé."},
                       {"capability_id": "C2", "goal": "Identifier les composantes d'une communication et rédiger une demande de clarification fondée sur des faits."}],
        "situation": {"text": "L'Atelier Delta prépare une commande. Léa coordonne le suivi et Samir réalise les contrôles. Leur échange écrit crée un malentendu. Vous devez l'analyser avant de proposer une réponse professionnelle.", "provenance": "LOCAL_FICTION", "evidence_id": None},
        "documents": [
            {"document_id": "D1", "title": "Les messages de la matinée", "provenance": "LOCAL_FICTION", "evidence_id": None,
             "text": "9 h 05 — Léa : Peux-tu m'envoyer le relevé de contrôle ce matin ?\n9 h 12 — Le message est indiqué comme lu.\n10 h 00 — Léa écrit dans sa note personnelle : Samir ne répond pas, il ne s'intéresse pas au suivi.\n10 h 20 — Samir : Je termine les contrôles de la commande. Je peux envoyer le relevé à 11 h 15. Est-ce compatible avec ton besoin ?"},
            {"document_id": "D2", "title": "Deux informations de contexte", "provenance": "LOCAL_FICTION", "evidence_id": None,
             "text": "La réunion de Léa commence à 10 h 45 ; elle a besoin du relevé à 10 h 30. Elle n'a pas indiqué cette heure dans son message. Samir effectue un contrôle en atelier de 9 h à 10 h 15. Il a lu la notification pendant une pause. Aucun accord préalable sur un délai de réponse à la messagerie n'est mentionné."}],
        "questions": [
            {"question_id": "Q1", "stage": "OBSERVE", "capability_ids": ["C2"], "document_ids": ["D1"], "answer_lines": 4,
             "prompt": "Identifiez l'émettrice, le destinataire, le canal et l'objet du premier message. Relevez ensuite deux faits observables et datés.",
             "success_criteria": ["Quatre composantes identifiées", "Deux faits datés sans jugement sur une intention"]},
            {"question_id": "Q2", "stage": "ANALYSE", "capability_ids": ["C1"], "document_ids": ["D1", "D2"], "answer_lines": 4,
             "prompt": "Expliquez pourquoi la note personnelle de Léa contient une interprétation. Montrez, à partir de D2, pourquoi cette interprétation n'est pas la seule possible.",
             "success_criteria": ["Fait et interprétation distingués", "Une autre explication justifiée par D2"]},
            {"question_id": "Q3", "stage": "ANALYSE", "capability_ids": ["C1", "C2"], "document_ids": ["D1", "D2"], "answer_lines": 4,
             "prompt": "Comparez ce que chacun sait de l'urgence. Comment ces informations différentes orientent-elles la perception de la situation ? Indiquez une information manquante dans l'échange initial.",
             "success_criteria": ["Deux points de vue reliés aux informations disponibles", "Une information à clarifier identifiée"]},
            {"question_id": "Q4", "stage": "APPLY", "capability_ids": ["C2"], "document_ids": ["D1", "D2"], "answer_lines": 4,
             "prompt": "Rédigez le message que Léa pourrait envoyer à 10 h 20. Formulez son besoin, son échéance et une demande de clarification, sans attribuer d'intention à Samir.",
             "success_criteria": ["Besoin et échéance explicites", "Demande réalisable à confirmer", "Ton professionnel sans jugement"]}],
        "teacher_answers": [
            {"question_id": "Q1", "expected_answer": "Émettrice : Léa ; destinataire : Samir ; canal : messagerie écrite ; objet : obtenir le relevé de contrôle. Faits possibles : message envoyé à 9 h 05, indiqué comme lu à 9 h 12, réponse envoyée à 10 h 20.",
             "rationale": "Ces éléments sont présents dans D1. Un accusé de lecture renseigne sur la consultation, sans expliquer l'absence de réponse immédiate.",
             "vigilance": "Ne pas accepter il ignore Léa comme fait observable.", "remediation": "Faire surligner les horaires et les paroles exactes, puis séparer actions observables et hypothèses."},
            {"question_id": "Q2", "expected_answer": "Léa attribue un désintérêt à Samir à partir de l'absence de réponse. D2 indique qu'il réalise des contrôles et que la lecture a eu lieu pendant une pause : cela fournit une autre explication possible, sans prouver son intention.",
             "rationale": "La perception dépend des informations disponibles et du contexte. Une explication compatible avec les faits reste une hypothèse, pas une certitude.",
             "vigilance": "Ne pas remplacer le jugement de Léa par une nouvelle certitude sur Samir.", "remediation": "Faire reformuler avec il est possible que, puis demander quel document étaye cette possibilité."},
            {"question_id": "Q3", "expected_answer": "Léa connaît la réunion de 10 h 45 et son besoin de 10 h 30. Samir ne dispose que de ce matin et propose 11 h 15. Ils n'ont donc pas la même représentation de l'urgence. L'heure précise de remise manque dans le message initial.",
             "rationale": "Les mêmes mots sont interprétés avec des contraintes différentes. L'analyse porte sur l'information partagée, sans conclure à une personnalité ou à une mauvaise volonté.",
             "vigilance": "Ne pas traiter ce matin comme une échéance précise convenue.", "remediation": "Faire deux colonnes au brouillon : informations connues de Léa et informations connues de Samir."},
            {"question_id": "Q4", "expected_answer": "Bonjour Samir, merci pour ton retour. J'ai besoin du relevé à 10 h 30 pour préparer la réunion de 10 h 45. Peux-tu me confirmer si cet envoi est possible ? Sinon, indiquons ensemble quelles informations déjà disponibles je peux utiliser. Merci.",
             "rationale": "Le message précise les faits utiles et l'échéance réelle, demande confirmation de la faisabilité et ouvre une solution de coordination, sans imposer un résultat présenté comme acquis.",
             "vigilance": "Accepter d'autres formulations professionnelles qui conservent les faits ; refuser les reproches ou les délais inventés.", "remediation": "Faire réécrire en trois éléments : mon besoin, mon échéance, ma question de clarification. Comparer ensuite au message initial."}]
    }}
    return dispatch, content
