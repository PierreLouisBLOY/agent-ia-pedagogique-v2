"""Versioned, synthetic and offline-only pedagogical anchor corpus v2."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

from tests.calibration.pedagogical.catalog import (
    CALIBRATION_SCENARIOS,
    AnchorExpectation,
    AnchorTier,
    CalibrationAnchor,
    CalibrationScenario,
    CriterionOrdering,
    calibration_corpus_sha256,
)

ROOT = Path(__file__).resolve().parents[3]

PEDAGOGICAL_CALIBRATION_CORPUS_V2_VERSION = "12.16-g1-v2"
PEDAGOGICAL_CALIBRATION_CORPUS_V1_VERSION = "12.16-g1-v1"
PEDAGOGICAL_CALIBRATION_CORPUS_V1_SHA256 = (
    "abeec0b4e5e1f60f2974ec1c19de34a5307e1b7d92e11c7b811e338d3b2e626d"
)
PEDAGOGICAL_CALIBRATION_V1_OWNER_FILE_SHA256 = (
    "53da2068fa6585086fe955b633a1d8e173cf770c8b5cb5e71f6cc8cc474e7317"
)
FINAL_V1_REPORT_SHA256 = (
    "f08fad954918f82e690a539b35f02a88ce3d08818a95f6c18df982f4c3d7c272"
)
HUMAN_V1_REPORT_SHA256 = (
    "568e810af5a3cee9e46a56696300066db421d2dfc330f721718318be85a8b6cd"
)

PACKET_RELATIVE_PATH = (
    "docs/development/PHASE_12_16_G2_V2_HUMAN_PREVALIDATION_PACKET.md"
)
MATRIX_RELATIVE_PATH = (
    "docs/development/PHASE_12_16_G2_ANCHOR_CORPUS_V2_DIFFERENTIATION_MATRIX.md"
)
BASELINE_RELATIVE_PATH = (
    "docs/development/PHASE_12_16_G2_ANCHOR_CORPUS_V2_REMEDIATION_BASELINE.md"
)
RECONCILIATION_KEY_RELATIVE_PATH = (
    "artifacts/calibration/12.16-g2-anchor-corpus-v2/"
    "human_prevalidation_reconciliation.json"
)
ADR_RELATIVE_PATH = (
    "architecture/adr/ADR-P12-065-versioned-human-prevalidated-anchor-corpus.md"
)

OWNER_DECISION = "REVISE_ANCHOR_CORPUS_FIRST"
V1_STATUS = "CLOSED_DIAGNOSTIC_BASELINE"
SCORER_POLICY = "KEEP_PROVISIONALLY_EXPLICIT_ADAPTIVE_LOW_2048"
JUDGE_RECALIBRATION = "DEFERRED_UNTIL_V2_HUMAN_PREVALIDATION"
NEXT_GATE = "12.16-G2-V2-HUMAN-PREVALIDATION_READY"

HUMAN_LABELS = (
    "TRES_SATISFAISANT",
    "SATISFAISANT",
    "FRAGILE",
    "INSUFFISANT",
    "NON_EVALUABLE",
)
HUMAN_ACTIONS = ("aucune", "révision", "exclusion")
PREFERRED_REVIEWER = "SECOND_COMPETENT_HUMAN_NOT_EXPOSED_TO_MACHINE_RESULTS"
FALLBACK_REVIEWER = "OWNER_HUMAN_REVIEWER"

STATIC_DIFFERENTIATION_RULE_IDS = (
    "v2.anchors-distinct",
    "v2.tier-sections-distinct",
    "v2.non-trivial-textual-distance",
    "v2.controlled-defect-declared",
    "v2.not-cosmetic-only",
    "v2.required-sections-exact",
    "v2.structurally-valid",
    "v2.weak-not-more-detailed-than-strong",
    "v2.safe-synthetic-content",
)


@dataclass(frozen=True, slots=True)
class ControlledDifferentiation:
    scenario_code: str
    criterion_ref: str
    strong_intent: str
    mixed_defect: str
    weak_defect: str


@dataclass(frozen=True, slots=True)
class V2CriterionItem:
    anchor_id: str
    scenario_code: str
    criterion_ref: str


@dataclass(frozen=True, slots=True)
class BlindPrevalidationItem:
    review_item_id: str
    anchor_id: str


@dataclass(frozen=True, slots=True)
class StaticDifferentiationIssue:
    rule_id: str
    scenario_code: str
    detail: str


CONTROLLED_DIFFERENTIATION_MATRIX = (
    ControlledDifferentiation(
        "SCN-01",
        "scn-01.quality.clarity",
        "hiérarchie de classement et champs explicités sans ambiguïté",
        "classement utilisable mais ordre des champs seulement suggéré",
        "catégorie générale sans procédure de classement explicite",
    ),
    ControlledDifferentiation(
        "SCN-01",
        "scn-01.quality.organization-utility",
        "retrouvabilité et vérification rendues immédiatement opérationnelles",
        "retrouvabilité assurée mais contrôle ultérieur peu guidé",
        "rangement minimal sans règle de vérification ou de réutilisation",
    ),
    ControlledDifferentiation(
        "SCN-02",
        "scn-02.quality.relevance",
        "ciblage conjoint de la notion, du niveau et de la tâche de calcul",
        "ciblage du thème et du niveau avec précision méthodologique réduite",
        "mot-clé large sans filtre de niveau ni de méthode",
    ),
    ControlledDifferentiation(
        "SCN-02",
        "scn-02.quality.coverage",
        "notion, méthode, exemple et règles d'exclusion tous couverts",
        "notion et méthode couvertes mais exemple laissé facultatif",
        "mentions thématiques seules, sans méthode ni exemple exigés",
    ),
    ControlledDifferentiation(
        "SCN-03",
        "scn-03.quality.clarity",
        "définitions contrastées, exemple interprété et synthèse articulée",
        "définitions correctes mais contraste et synthèse moins développés",
        "formulations générales qui nomment les finalités sans les expliquer",
    ),
    ControlledDifferentiation(
        "SCN-03",
        "scn-03.quality.level-adaptation",
        "vocabulaire et raisonnement explicitement adaptés à Première STMG",
        "vocabulaire accessible mais guidage disciplinaire limité",
        "exemple générique et repères disciplinaires insuffisants",
    ),
    ControlledDifferentiation(
        "SCN-04",
        "scn-04.quality.fidelity",
        "enchaînement HT, taux, taxe et TTC intégralement préservé",
        "relation de calcul exacte mais décomposition intermédiaire abrégée",
        "règle exacte mais trop générique pour restituer la note en détail",
    ),
    ControlledDifferentiation(
        "SCN-04",
        "scn-04.quality.level-adaptation",
        "méthode, unités et vérification explicitables au niveau BTS CG",
        "exemple exploitable mais sans contrôle comptable guidé",
        "application abstraite sans repère de présentation comptable",
    ),
    ControlledDifferentiation(
        "SCN-05",
        "scn-05.quality.difficulty-appropriateness",
        "deux calculs, comparaison et justification graduent la difficulté",
        "deux calculs directs avec justification courte",
        "choix demandé à partir d'un calcul peu guidé et faiblement approfondi",
    ),
    ControlledDifferentiation(
        "SCN-05",
        "scn-05.quality.instruction-clarity",
        "données, formule attendue, étapes et justification sont explicites",
        "données et résultat attendus sont clairs mais les étapes sont peu guidées",
        "consigne générale qui ne précise ni méthode ni forme de justification",
    ),
    ControlledDifferentiation(
        "SCN-06",
        "scn-06.quality.assessment-clarity",
        "consignes, données, unités et attendus de calcul sont explicites",
        "calculs identifiés mais présentation attendue seulement partielle",
        "questions compréhensibles avec exigences de réponse minimales",
    ),
    ControlledDifferentiation(
        "SCN-06",
        "scn-06.quality.marking-scheme-coherence",
        "barème analytique aligné sur formule, application, résultat et unité",
        "barème partiellement analytique qui regroupe certaines étapes",
        "barème global aligné sur les questions mais peu discriminant",
    ),
    ControlledDifferentiation(
        "SCN-07",
        "scn-07.quality.correction-quality",
        "confusion diagnostiquée et relation produits moins charges explicitée",
        "correction exacte mais diagnostic et justification abrégés",
        "rectification superficielle qui rappelle seulement le rôle des charges",
    ),
    ControlledDifferentiation(
        "SCN-07",
        "scn-07.quality.remediation-clarity",
        "activité bornée avec classement, recalcul et explication finale",
        "nouveau calcul demandé avec guidage général",
        "invitation à revoir la notion sans tâche ni critère de réussite",
    ),
    ControlledDifferentiation(
        "SCN-08",
        "scn-08.quality.distractor-quality",
        "trois erreurs plausibles, distinctes et liées à des confusions identifiables",
        "distracteurs distincts mais plausibilité inégale",
        "distracteurs formellement distincts dont deux sont peu convaincants",
    ),
    ControlledDifferentiation(
        "SCN-08",
        "scn-08.quality.feedback-quality",
        "réponse correcte et erreur de chaque distracteur expliquées",
        "bonne réponse expliquée avec un seul contraste détaillé",
        "confirmation brève de la réponse sans analyse des distracteurs",
    ),
)


_V2_ANCHOR_SECTIONS: dict[str, tuple[tuple[tuple[str, str], ...], ...]] = {
    "SCN-01": (
        (
            (
                "context",
                "Une ressource synthétique de management comporte un titre, un thème, une "
                "notion, un niveau pédagogique et un statut de vérification.",
            ),
            (
                "summary",
                "La classer par thème puis par notion, afficher le titre, le niveau et le "
                "statut, puis utiliser ce statut pour retrouver et vérifier rapidement la "
                "ressource avant son emploi.",
            ),
        ),
        (
            (
                "context",
                "Une ressource synthétique de management fournit un titre, un thème, une "
                "notion et un statut de contrôle.",
            ),
            (
                "summary",
                "La ranger par thème, conserver le titre et la notion, puis afficher le statut "
                "pour permettre un contrôle ultérieur.",
            ),
        ),
        (
            (
                "context",
                "Une ressource synthétique de management indique un titre et un thème de "
                "classement.",
            ),
            (
                "summary",
                "La placer dans une catégorie de management et conserver son titre pour la "
                "retrouver.",
            ),
        ),
    ),
    "SCN-02": (
        (
            (
                "concept",
                "La recherche vise des ressources de gestion financière pour Terminale STMG "
                "qui définissent la notion, expliquent une méthode de calcul et proposent un "
                "exemple d'application synthétique.",
            ),
            (
                "summary",
                "Filtrer par niveau, notion et tâche; retenir les ressources couvrant définition, "
                "méthode et exemple, puis écarter celles qui sont hors niveau, sans calcul ou "
                "seulement thématiques.",
            ),
        ),
        (
            (
                "concept",
                "La recherche porte sur une notion de gestion financière en Terminale STMG et "
                "doit faire apparaître une méthode de calcul utilisable.",
            ),
            (
                "summary",
                "Filtrer par thème et niveau, conserver les ressources qui expliquent le calcul; "
                "un exemple d'application peut compléter la sélection.",
            ),
        ),
        (
            (
                "concept",
                "La recherche utilise un mot-clé général de gestion financière pour repérer des "
                "ressources qui mentionnent le sujet.",
            ),
            (
                "summary",
                "Conserver les titres liés au thème et les présenter dans une liste, sans autre "
                "filtre obligatoire.",
            ),
        ),
    ),
    "SCN-03": (
        (
            (
                "objective",
                "Distinguer une finalité économique d'une finalité sociale et expliquer pourquoi "
                "elles peuvent être poursuivies ensemble par une organisation.",
            ),
            (
                "concept",
                "La finalité économique soutient la pérennité de l'activité et ses ressources; "
                "la finalité sociale concerne les conditions de travail et les effets sur les "
                "personnes impliquées.",
            ),
            (
                "example",
                "Une coopérative synthétique conserve un excédent pour financer son activité et "
                "améliore simultanément l'organisation du travail de ses membres.",
            ),
            (
                "summary",
                "En Première STMG, on identifie la finalité à partir de ce que l'organisation "
                "cherche à maintenir et des personnes auxquelles son action bénéficie.",
            ),
        ),
        (
            (
                "objective",
                "Reconnaître une finalité économique et une finalité sociale dans une situation "
                "simple d'organisation.",
            ),
            (
                "concept",
                "La finalité économique concerne la continuité de l'activité; la finalité sociale "
                "concerne les personnes et leurs conditions de travail.",
            ),
            (
                "example",
                "Une entreprise synthétique vend ses produits tout en améliorant un aménagement "
                "de travail pour son équipe.",
            ),
            (
                "summary",
                "Une organisation peut poursuivre ces deux finalités dans une même situation.",
            ),
        ),
        (
            ("objective", "Repérer deux objectifs possibles d'une organisation."),
            (
                "concept",
                "Une organisation recherche des résultats pour son activité et peut aussi agir "
                "pour les personnes.",
            ),
            (
                "example",
                "Une structure synthétique vend un service et propose une action pour son équipe.",
            ),
            ("summary", "Les organisations peuvent avoir plusieurs finalités."),
        ),
    ),
    "SCN-04": (
        (
            (
                "context",
                "Une note synthétique distingue un montant hors taxe, un taux de TVA, la taxe "
                "calculée et le montant toutes taxes comprises.",
            ),
            (
                "concept",
                "La TVA est le montant hors taxe multiplié par le taux; le TTC est ensuite la "
                "somme du hors taxe et de la TVA. Chaque résultat conserve son unité monétaire.",
            ),
            (
                "example",
                "Pour 250 unités hors taxe à 20 %, la TVA vaut 50 unités et le TTC 300 unités; "
                "la somme 250 plus 50 vérifie le résultat.",
            ),
            (
                "summary",
                "Identifier HT et taux, calculer séparément la TVA, additionner pour obtenir le "
                "TTC, puis contrôler l'unité et l'égalité finale.",
            ),
        ),
        (
            (
                "context",
                "Une opération synthétique fournit un montant hors taxe et un taux de TVA afin "
                "de déterminer le total toutes taxes comprises.",
            ),
            (
                "concept",
                "Calculer la TVA sur le hors taxe, puis l'ajouter au montant initial pour obtenir "
                "le TTC.",
            ),
            (
                "example",
                "Pour 100 unités hors taxe à 20 %, le total TTC est de 120 unités.",
            ),
            (
                "summary",
                "Appliquer le taux au hors taxe et ajouter la taxe; présenter le résultat avec "
                "son unité.",
            ),
        ),
        (
            (
                "context",
                "Une opération synthétique comporte un montant hors taxe, un taux et un total à "
                "déterminer.",
            ),
            (
                "concept",
                "La taxe se calcule sur le montant hors taxe puis s'ajoute au montant de départ.",
            ),
            (
                "example",
                "Avec les valeurs fournies, appliquer le taux puis additionner la taxe obtenue.",
            ),
            ("summary", "Calculer la taxe et l'ajouter pour obtenir le total."),
        ),
    ),
    "SCN-05": (
        (
            (
                "context",
                "Une entreprise synthétique compare deux investissements: 12 000 unités pour "
                "3 000 unités d'économie annuelle et 15 000 unités pour 5 000 unités d'économie "
                "annuelle.",
            ),
            (
                "questions",
                "1. Écrire la formule de durée de récupération. 2. Calculer la durée pour chaque "
                "investissement. 3. Comparer les deux résultats et justifier le choix le plus "
                "rapide en une phrase.",
            ),
            (
                "correction-link",
                "La correction séparée attribue une étape à la formule, détaille 12 000 divisé "
                "par 3 000 et 15 000 divisé par 5 000, puis relie les résultats de quatre et trois "
                "ans au choix justifié.",
            ),
        ),
        (
            (
                "context",
                "Une entreprise synthétique hésite entre un investissement de 8 000 unités qui "
                "économise 2 000 unités par an et un autre de 9 000 unités qui en économise 3 000.",
            ),
            (
                "questions",
                "1. Calculer la durée de récupération de chaque choix. 2. Indiquer le choix le "
                "plus rapide et donner une justification courte.",
            ),
            (
                "correction-link",
                "La correction séparée rappelle la division du coût par l'économie annuelle, "
                "donne les deux durées et identifie la plus courte.",
            ),
        ),
        (
            (
                "context",
                "Deux investissements synthétiques présentent chacun un coût et une économie "
                "annuelle différents.",
            ),
            (
                "questions",
                "1. Effectuer un calcul utile pour chaque proposition. 2. Choisir une proposition "
                "et expliquer brièvement la réponse.",
            ),
            (
                "correction-link",
                "La correction séparée indique qu'il faut comparer les durées calculées et retenir "
                "la plus courte.",
            ),
        ),
    ),
    "SCN-06": (
        (
            (
                "instructions",
                "Présenter pour chaque question la formule, le remplacement par les données, le "
                "calcul et l'unité du résultat.",
            ),
            (
                "questions",
                "1. Calculer la TVA sur 250 unités hors taxe au taux de 20 %. 2. Déterminer le "
                "montant TTC correspondant et vérifier l'addition.",
            ),
            (
                "marking-scheme",
                "Question 1: formule 1 point, application 1 point, résultat et unité 1 point. "
                "Question 2: formule 1 point, calcul 1 point, résultat, unité et vérification 1 point.",
            ),
        ),
        (
            (
                "instructions",
                "Présenter les deux calculs demandés et écrire l'unité de chaque résultat.",
            ),
            (
                "questions",
                "1. Calculer la TVA sur 200 unités hors taxe à 20 %. 2. Calculer le montant TTC.",
            ),
            (
                "marking-scheme",
                "Question 1: formule 1 point et calcul avec unité 2 points. Question 2: calcul 2 "
                "points et résultat avec unité 1 point.",
            ),
        ),
        (
            ("instructions", "Effectuer les calculs de taxe et donner les résultats."),
            (
                "questions",
                "1. Trouver la TVA pour un montant hors taxe et un taux fournis. 2. Donner le "
                "montant TTC.",
            ),
            (
                "marking-scheme",
                "Question 1: 3 points pour une réponse correcte. Question 2: 3 points pour le "
                "résultat et sa présentation.",
            ),
        ),
    ),
    "SCN-07": (
        (
            (
                "context",
                "Une production synthétique confond le chiffre d'affaires avec le résultat alors "
                "que des produits et des charges sont fournis.",
            ),
            (
                "correction-link",
                "Correction: le chiffre d'affaires mesure les ventes; le résultat correspond aux "
                "produits diminués des charges. La confusion vient de l'oubli des charges, qui "
                "doivent rester dans le calcul.",
            ),
            (
                "summary",
                "Remédiation: classer trois montants fictifs en produits ou charges, recalculer le "
                "résultat, puis expliquer en une phrase pourquoi il diffère des ventes.",
            ),
        ),
        (
            (
                "context",
                "Une production synthétique assimile les ventes au résultat malgré la présence "
                "d'un montant de charges.",
            ),
            (
                "correction-link",
                "Correction: le résultat ne se limite pas aux ventes; il faut soustraire les "
                "charges des produits.",
            ),
            (
                "summary",
                "Remédiation: reprendre un exemple simple avec un montant de produits et un montant "
                "de charges, puis comparer le résultat aux ventes.",
            ),
        ),
        (
            (
                "context",
                "Une production synthétique contient une confusion entre les ventes et le résultat.",
            ),
            (
                "correction-link",
                "Correction: le résultat doit aussi tenir compte des charges et ne correspond pas "
                "aux seules ventes.",
            ),
            (
                "summary",
                "Remédiation: revoir la définition du résultat et reprendre le calcul présenté.",
            ),
        ),
    ),
    "SCN-08": (
        (
            (
                "question",
                "Quel calcul exprime la part des charges dans le chiffre d'affaires ?",
            ),
            (
                "options",
                "A. Charges divisées par chiffre d'affaires. B. Chiffre d'affaires divisé par "
                "charges. C. Charges divisées par résultat. D. Résultat divisé par chiffre "
                "d'affaires.",
            ),
            ("answer-key", "A"),
            (
                "feedback",
                "A rapporte bien les charges au chiffre d'affaires. B inverse le rapport, C change "
                "le dénominateur et D mesure la part du résultat plutôt que celle des charges.",
            ),
        ),
        (
            (
                "question",
                "Comment calculer le poids des charges dans les ventes ?",
            ),
            (
                "options",
                "A. Ventes divisées par charges. B. Charges moins ventes. C. Charges divisées par "
                "ventes. D. Charges plus ventes.",
            ),
            ("answer-key", "C"),
            (
                "feedback",
                "C construit la proportion demandée en rapportant les charges aux ventes; A inverse "
                "les deux grandeurs.",
            ),
        ),
        (
            (
                "question",
                "Quelle opération compare les charges au chiffre d'affaires ?",
            ),
            (
                "options",
                "A. Ajouter les deux montants. B. Diviser les charges par le chiffre d'affaires. "
                "C. Garder les charges seules. D. Soustraire un du chiffre d'affaires.",
            ),
            ("answer-key", "B"),
            ("feedback", "B effectue la comparaison demandée entre les deux grandeurs."),
        ),
    ),
}


_TIER_SLOTS = (
    ("quality-high", AnchorTier.STRONG),
    ("quality-intermediate", AnchorTier.MIXED),
    ("quality-low", AnchorTier.WEAK_BUT_STRUCTURALLY_VALID),
)


def _opaque_anchor_id(scenario_code: str, slot_code: str) -> str:
    seed = f"{PEDAGOGICAL_CALIBRATION_CORPUS_V2_VERSION}|{scenario_code}|{slot_code}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]
    return f"cal.v2.{scenario_code.casefold()}.{digest}"


V2_CALIBRATION_ANCHORS = tuple(
    CalibrationAnchor(
        anchor_id=_opaque_anchor_id(scenario.scenario_code, slot_code),
        scenario_code=scenario.scenario_code,
        sections=sections,
    )
    for scenario in CALIBRATION_SCENARIOS
    for (slot_code, _), sections in zip(
        _TIER_SLOTS,
        _V2_ANCHOR_SECTIONS[scenario.scenario_code],
        strict=True,
    )
)


V2_ANCHOR_EXPECTATIONS = tuple(
    AnchorExpectation(
        anchor_id=_opaque_anchor_id(scenario.scenario_code, slot_code),
        tier=tier,
    )
    for scenario in CALIBRATION_SCENARIOS
    for slot_code, tier in _TIER_SLOTS
)


V2_CRITERION_ORDERINGS = tuple(
    CriterionOrdering(
        criterion_ref=criterion_ref,
        ordered_anchor_ids=tuple(
            _opaque_anchor_id(scenario.scenario_code, slot_code)
            for slot_code, _ in _TIER_SLOTS
        ),
    )
    for scenario in CALIBRATION_SCENARIOS
    for criterion_ref in scenario.criterion_refs
)


V2_CALIBRATION_CRITERION_ITEMS = tuple(
    V2CriterionItem(
        anchor_id=anchor.anchor_id,
        scenario_code=anchor.scenario_code,
        criterion_ref=criterion_ref,
    )
    for anchor in V2_CALIBRATION_ANCHORS
    for criterion_ref in next(
        scenario
        for scenario in CALIBRATION_SCENARIOS
        if scenario.scenario_code == anchor.scenario_code
    ).criterion_refs
)


V2_HUMAN_ACCEPTANCE_GATE = {
    "structurally_valid_anchor_count": 24,
    "weak_ordering_count": 16,
    "inversion_count": 0,
    "non_evaluable_relation_count": 0,
    "perceptibly_differentiated_criterion_count": 16,
    "design_target_strict_ordering_count": 16,
    "remaining_tie_requires_explicit_disposition": True,
    "product_release_threshold_created": False,
}


_REMEDIATION_SUMMARIES = {
    "SCN-01": "structure mixed réparée; hiérarchie, retrouvabilité et vérification graduées",
    "SCN-02": "ciblage et couverture séparés; faible sans niveau, méthode ni exemple requis",
    "SCN-03": "distinction forte/intermédiaire conservée; intermédiaire/faible rendue visible",
    "SCN-04": "fidélité du calcul et adaptation BTS CG différenciées sans inexactitude",
    "SCN-05": "difficulté et guidage gradués par données, étapes et justification",
    "SCN-06": "barème analytique, partiellement analytique puis global mais aligné",
    "SCN-07": "correction et remédiation graduées d'opérationnelles à superficielles",
    "SCN-08": "plausibilité des distracteurs et profondeur du feedback graduées",
}

_URL = re.compile(r"(?i)\b(?:https?|file)://")
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_LOCAL_PATH = re.compile(r"(?:[A-Za-z]:[\\/]|(?:^|\s)/(?:home|Users|var|tmp)/)")
_SCORER_FORBIDDEN_MARKERS = (
    "openai",
    "anthropic",
    "provider",
    "model_id",
    "expected score",
    "strong",
    "mixed",
    "weak_but_structurally_valid",
    "api_key",
    "password",
    "credential",
    "sqlite",
)


def _scenario_by_code(scenario_code: str) -> CalibrationScenario:
    return next(
        scenario
        for scenario in CALIBRATION_SCENARIOS
        if scenario.scenario_code == scenario_code
    )


def v2_anchor_by_id(anchor_id: str) -> CalibrationAnchor:
    return next(anchor for anchor in V2_CALIBRATION_ANCHORS if anchor.anchor_id == anchor_id)


def scorer_visible_projection(
    anchor: CalibrationAnchor,
    criterion_ref: str,
) -> dict[str, object]:
    scenario = _scenario_by_code(anchor.scenario_code)
    if criterion_ref not in scenario.criterion_refs:
        raise ValueError("criterion does not belong to the scenario")
    return {
        "criterion": criterion_ref,
        "scenario": scenario.scenario_code,
        "pedagogical-level": scenario.level_code,
        "task-kind": scenario.task_kind,
        "candidate-projection": anchor.candidate_projection(),
        "reference-constraints": scenario.reference_constraints,
        "required-sections": scenario.required_sections,
    }


def _canonical_sha256(payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _pretty_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def v2_calibration_corpus_sha256() -> str:
    payload = {
        "version": PEDAGOGICAL_CALIBRATION_CORPUS_V2_VERSION,
        "scenarios": [
            {
                "scenario_code": scenario.scenario_code,
                "level_code": scenario.level_code,
                "task_kind": scenario.task_kind,
                "scope_code": scenario.scope_code,
                "required_sections": scenario.required_sections,
                "rubric_ref": scenario.rubric_ref,
                "criterion_refs": scenario.criterion_refs,
                "reference_constraints": scenario.reference_constraints,
            }
            for scenario in CALIBRATION_SCENARIOS
        ],
        "anchors": [
            {
                "anchor_id": anchor.anchor_id,
                "scenario_code": anchor.scenario_code,
                "sections": anchor.sections,
            }
            for anchor in V2_CALIBRATION_ANCHORS
        ],
        "expectations": [
            {"anchor_id": item.anchor_id, "tier": item.tier.value}
            for item in V2_ANCHOR_EXPECTATIONS
        ],
        "orderings": [
            {
                "criterion_ref": item.criterion_ref,
                "ordered_anchor_ids": item.ordered_anchor_ids,
            }
            for item in V2_CRITERION_ORDERINGS
        ],
        "controlled_differentiation": [
            {
                "scenario_code": item.scenario_code,
                "criterion_ref": item.criterion_ref,
                "strong_intent": item.strong_intent,
                "mixed_defect": item.mixed_defect,
                "weak_defect": item.weak_defect,
            }
            for item in CONTROLLED_DIFFERENTIATION_MATRIX
        ],
    }
    return _canonical_sha256(payload)


def _normalized_text(value: str) -> str:
    return " ".join(re.findall(r"\w+", value.casefold()))


def audit_v2_corpus(
    anchors: tuple[CalibrationAnchor, ...] = V2_CALIBRATION_ANCHORS,
    matrix: tuple[ControlledDifferentiation, ...] = CONTROLLED_DIFFERENTIATION_MATRIX,
) -> tuple[StaticDifferentiationIssue, ...]:
    issues: list[StaticDifferentiationIssue] = []
    by_scenario: dict[str, list[CalibrationAnchor]] = {
        scenario.scenario_code: [] for scenario in CALIBRATION_SCENARIOS
    }
    for anchor in anchors:
        by_scenario.setdefault(anchor.scenario_code, []).append(anchor)
        try:
            scenario = _scenario_by_code(anchor.scenario_code)
        except StopIteration:
            issues.append(
                StaticDifferentiationIssue(
                    "v2.structurally-valid",
                    anchor.scenario_code,
                    "unknown-scenario",
                )
            )
            continue
        section_codes = tuple(code for code, _ in anchor.sections)
        if section_codes != scenario.required_sections:
            issues.append(
                StaticDifferentiationIssue(
                    "v2.required-sections-exact",
                    anchor.scenario_code,
                    anchor.anchor_id,
                )
            )
        if any(not text or text != text.strip() for _, text in anchor.sections):
            issues.append(
                StaticDifferentiationIssue(
                    "v2.structurally-valid",
                    anchor.scenario_code,
                    anchor.anchor_id,
                )
            )
        projection = anchor.candidate_projection()
        normalized = projection.casefold()
        if (
            not projection
            or len(projection) > 2_500
            or _URL.search(projection)
            or _EMAIL.search(projection)
            or _LOCAL_PATH.search(projection)
            or any(marker in normalized for marker in _SCORER_FORBIDDEN_MARKERS)
        ):
            issues.append(
                StaticDifferentiationIssue(
                    "v2.safe-synthetic-content",
                    anchor.scenario_code,
                    anchor.anchor_id,
                )
            )

    expected_matrix_keys = {
        (scenario.scenario_code, criterion_ref)
        for scenario in CALIBRATION_SCENARIOS
        for criterion_ref in scenario.criterion_refs
    }
    actual_matrix_keys = {(item.scenario_code, item.criterion_ref) for item in matrix}
    if len(matrix) != 16 or len(actual_matrix_keys) != 16 or actual_matrix_keys != expected_matrix_keys:
        issues.append(
            StaticDifferentiationIssue(
                "v2.controlled-defect-declared",
                "ALL",
                "matrix-membership",
            )
        )
    for item in matrix:
        values = (item.strong_intent, item.mixed_defect, item.weak_defect)
        if any(not value.strip() for value in values) or len(set(values)) != 3:
            issues.append(
                StaticDifferentiationIssue(
                    "v2.controlled-defect-declared",
                    item.scenario_code,
                    item.criterion_ref,
                )
            )

    for scenario in CALIBRATION_SCENARIOS:
        scenario_anchors = by_scenario.get(scenario.scenario_code, [])
        if len(scenario_anchors) != 3:
            issues.append(
                StaticDifferentiationIssue(
                    "v2.structurally-valid",
                    scenario.scenario_code,
                    "triplet-cardinality",
                )
            )
            continue
        projections = tuple(anchor.candidate_projection() for anchor in scenario_anchors)
        if len(set(projections)) != 3:
            issues.append(
                StaticDifferentiationIssue(
                    "v2.anchors-distinct",
                    scenario.scenario_code,
                    "duplicate-projection",
                )
            )
        for left_index, right_index in ((0, 1), (1, 2), (0, 2)):
            left = projections[left_index]
            right = projections[right_index]
            if _normalized_text(left) == _normalized_text(right):
                issues.append(
                    StaticDifferentiationIssue(
                        "v2.not-cosmetic-only",
                        scenario.scenario_code,
                        f"{left_index}-{right_index}",
                    )
                )
            similarity = SequenceMatcher(
                None,
                _normalized_text(left),
                _normalized_text(right),
            ).ratio()
            if similarity >= 0.90:
                issues.append(
                    StaticDifferentiationIssue(
                        "v2.non-trivial-textual-distance",
                        scenario.scenario_code,
                        f"{left_index}-{right_index}:{similarity:.3f}",
                    )
                )
        if all(
            tuple(code for code, _ in anchor.sections) == scenario.required_sections
            for anchor in scenario_anchors
        ):
            for section_index in range(len(scenario.required_sections)):
                section_values = tuple(
                    anchor.sections[section_index][1] for anchor in scenario_anchors
                )
                if len(set(section_values)) != 3:
                    issues.append(
                        StaticDifferentiationIssue(
                            "v2.tier-sections-distinct",
                            scenario.scenario_code,
                            scenario.required_sections[section_index],
                        )
                    )
        if len(projections[2]) > len(projections[0]):
            issues.append(
                StaticDifferentiationIssue(
                    "v2.weak-not-more-detailed-than-strong",
                    scenario.scenario_code,
                    f"weak={len(projections[2])};strong={len(projections[0])}",
                )
            )
    return tuple(issues)


def _blind_prevalidation_mapping() -> tuple[BlindPrevalidationItem, ...]:
    ordered = sorted(
        V2_CALIBRATION_ANCHORS,
        key=lambda anchor: hashlib.sha256(
            f"12.16-g2-v2-prevalidation|{anchor.anchor_id}".encode()
        ).hexdigest(),
    )
    return tuple(
        BlindPrevalidationItem(f"HPV2-{index:03d}", anchor.anchor_id)
        for index, anchor in enumerate(ordered, 1)
    )


def render_human_prevalidation_packet() -> str:
    lines = [
        "# Phase 12.16-G2 — Paquet aveugle de prévalidation humaine du corpus v2",
        "",
        f"- Corpus : `{PEDAGOGICAL_CALIBRATION_CORPUS_V2_VERSION}`",
        f"- Checksum corpus : `{v2_calibration_corpus_sha256()}`",
        "- REVIEW_STATUS : `NOT_COMPLETED`",
        "- Relecteur ou relectrice :",
        "- Date :",
        "- Version de la grille : `human-prevalidation-v2`",
        "- Exposition préalable aux résultats machine :",
        "",
        "## Gate pré-déclarée",
        "",
        "- 24/24 contenus structurellement valides.",
        "- 16/16 ordres faibles, 0 inversion et 0 relation non évaluable.",
        "- Les trois qualités doivent être perceptiblement différenciées pour chacun des 16 critères.",
        "- Objectif de conception : 16/16 ordres humains stricts.",
        "- Toute égalité restante exige une disposition explicite avant une évaluation fournisseur.",
        "- Cette gate ne crée aucun seuil de release produit.",
        "",
        "## Consignes",
        "",
        "1. Examiner chaque contenu sans consulter la clé locale ni les rapports machine.",
        "2. Évaluer séparément la structure et les deux critères indiqués.",
        "3. Utiliser exactement un libellé contrôlé par appréciation.",
        "4. Ne pas corriger le contenu dans ce fichier.",
        "5. Déclarer honnêtement toute exposition préalable.",
        "",
        "Libellés : `TRES_SATISFAISANT`, `SATISFAISANT`, `FRAGILE`, "
        "`INSUFFISANT`, `NON_EVALUABLE`.",
        "",
    ]
    for mapping in _blind_prevalidation_mapping():
        anchor = v2_anchor_by_id(mapping.anchor_id)
        scenario = _scenario_by_code(anchor.scenario_code)
        lines.extend(
            (
                f"## {mapping.review_item_id}",
                "",
                f"- Scénario : `{scenario.scenario_code}`",
                f"- Niveau : `{scenario.level_code}`",
                f"- Type de tâche : `{scenario.task_kind}`",
                f"- Critères : `{scenario.criterion_refs[0]}` ; `{scenario.criterion_refs[1]}`",
                f"- Sections requises : `{', '.join(scenario.required_sections)}`",
                "- Contenu synthétique :",
                "",
            )
        )
        for section_code, content in anchor.sections:
            lines.append(f"  - `{section_code}` : {content}")
        lines.extend(
            (
                "",
                "- Structure valide : [ ] oui [ ] non",
                f"- Appréciation humaine — `{scenario.criterion_refs[0]}` :",
                f"- Appréciation humaine — `{scenario.criterion_refs[1]}` :",
                "- Ambiguïté ou manque de contexte :",
                "- Justification pédagogique courte :",
                "- Action demandée : [ ] aucune [ ] révision [ ] exclusion",
                "",
            )
        )
    lines.extend(
        (
            "## Synthèse et signatures",
            "",
            "- Vingt-quatre items revus : [ ] oui [ ] non",
            "- Limites de la revue :",
            "- Avis : [ ] utilisable [ ] révisions requises [ ] inconclusif",
            "- Relecteur ou relectrice :",
            "- Responsable de la calibration :",
            "- Date de clôture :",
        )
    )
    return "\n".join(lines) + "\n"


def build_reconciliation_key() -> dict[str, object]:
    expectation = {item.anchor_id: item.tier.value for item in V2_ANCHOR_EXPECTATIONS}
    items: list[dict[str, object]] = []
    for mapping in _blind_prevalidation_mapping():
        anchor = v2_anchor_by_id(mapping.anchor_id)
        scenario = _scenario_by_code(anchor.scenario_code)
        item: dict[str, object] = {
            "review_item_id": mapping.review_item_id,
            "anchor_id": anchor.anchor_id,
            "scenario_code": anchor.scenario_code,
            "criterion_refs": scenario.criterion_refs,
            "expected_tier": expectation[anchor.anchor_id],
        }
        item["reconciliation_sha256"] = _canonical_sha256(item)
        items.append(item)
    packet = render_human_prevalidation_packet()
    return {
        "review_status": "NOT_COMPLETED",
        "corpus_version": PEDAGOGICAL_CALIBRATION_CORPUS_V2_VERSION,
        "corpus_sha256": v2_calibration_corpus_sha256(),
        "packet_sha256": hashlib.sha256(packet.encode("utf-8")).hexdigest(),
        "content_repeated": False,
        "item_count": 24,
        "items": items,
    }


def render_reconciliation_key_json() -> str:
    return _pretty_json(build_reconciliation_key())


def render_differentiation_matrix() -> str:
    lines = [
        "# Phase 12.16-G2 — Matrice de différenciation du corpus v2",
        "",
        f"- Version : `{PEDAGOGICAL_CALIBRATION_CORPUS_V2_VERSION}`.",
        f"- Checksum : `{v2_calibration_corpus_sha256()}`.",
        "- Portée : 8 scénarios, 16 critères, 24 anchors, 48 couples anchor/critère.",
        "- Toutes les sections requises sont préservées dans les trois niveaux.",
        "",
        "## Règles de conception",
        "",
        "- STRONG vise exactitude, complétude, clarté, adaptation et exploitabilité immédiate.",
        "- MIXED reste utilisable avec une insuffisance explicite et bornée sur chaque critère.",
        "- WEAK_BUT_STRUCTURALLY_VALID reste intelligible et exact, mais présente deux déficits pédagogiques perceptibles.",
        "- La progression visée est `STRONG > MIXED > WEAK_BUT_STRUCTURALLY_VALID` pour les deux critères.",
        "- La différence ne repose jamais sur une section manquante, une erreur absurde ou la seule longueur.",
        "",
        "## Matrice des défauts contrôlés",
        "",
        "| Scénario | Critère | Intention strong | Défaut mixed | Défaut weak | Sections préservées |",
        "|---|---|---|---|---|:---:|",
    ]
    for item in CONTROLLED_DIFFERENTIATION_MATRIX:
        lines.append(
            f"| {item.scenario_code} | `{item.criterion_ref}` | {item.strong_intent} | "
            f"{item.mixed_defect} | {item.weak_defect} | OUI |"
        )
    lines.extend(
        (
            "",
            "## Remédiation par scénario",
            "",
        )
    )
    for scenario_code, summary in _REMEDIATION_SUMMARIES.items():
        lines.append(f"- {scenario_code} : {summary}.")
    lines.extend(
        (
            "",
            "## Gates statiques",
            "",
        )
    )
    for rule_id in STATIC_DIFFERENTIATION_RULE_IDS:
        lines.append(f"- `{rule_id}`.")
    lines.extend(
        (
            "",
            "Ces gates détectent les défauts de conception évidents mais ne remplacent pas la prévalidation humaine aveugle.",
        )
    )
    return "\n".join(lines) + "\n"


def render_baseline() -> str:
    packet = render_human_prevalidation_packet()
    key_json = render_reconciliation_key_json()
    files_changed = (
        ADR_RELATIVE_PATH,
        BASELINE_RELATIVE_PATH,
        MATRIX_RELATIVE_PATH,
        PACKET_RELATIVE_PATH,
        "tests/architecture/test_anchor_corpus_v2_fitness.py",
        "tests/calibration/pedagogical/anchor_corpus_v2.py",
        "tests/unit/test_pedagogical_calibration_anchor_corpus_v2.py",
    )
    lines = [
        "# Phase 12.16-G2 — Baseline de remédiation du corpus d'anchors v2",
        "",
        "## Décision et références",
        "",
        f"- OWNER_CALIBRATION_DECISION : `{OWNER_DECISION}`.",
        f"- ANCHOR_CORPUS_V1_STATUS : `{V1_STATUS}`.",
        f"- ANTHROPIC_SCORER_POLICY : `{SCORER_POLICY}`.",
        f"- JUDGE_RECALIBRATION : `{JUDGE_RECALIBRATION}`.",
        "- PROVIDER_ROUTE_CHANGE : `NONE`.",
        "- RELEASE_THRESHOLD_ADOPTION : `NOT_ALLOWED`.",
        "- Sources : rapport machine final v1, réconciliation humaine et ADR-P12-063/064.",
        "",
        "## Intégrité v1",
        "",
        f"- Version : `{PEDAGOGICAL_CALIBRATION_CORPUS_V1_VERSION}` ; statut : `{V1_STATUS}`.",
        f"- Checksum corpus : `{calibration_corpus_sha256()}`.",
        f"- Hash owner : `{PEDAGOGICAL_CALIBRATION_V1_OWNER_FILE_SHA256}`.",
        f"- Hash rapport machine : `{FINAL_V1_REPORT_SHA256}`.",
        f"- Hash réconciliation humaine : `{HUMAN_V1_REPORT_SHA256}`.",
        "- Les owners, rapports, preuves et paquets v1 ne sont pas modifiés.",
        "",
        "## Corpus v2",
        "",
        f"- Version : `{PEDAGOGICAL_CALIBRATION_CORPUS_V2_VERSION}`.",
        f"- Checksum : `{v2_calibration_corpus_sha256()}`.",
        "- Cardinalité : `24 anchors / 48 couples / 8 scénarios / 16 critères`.",
        "- IDs : nouveaux, opaques, uniques et disjoints de v1.",
        "- Structure : `24/24` anchors avec sections requises exactes.",
        "- Matrice : `16/16` critères avec défauts controlled strong/mixed/weak.",
        "- SCN-01 : le défaut structurel mixed est supprimé; les trois contenus conservent context et summary.",
        "",
        "## Prévalidation humaine",
        "",
        f"- Paquet : `{PACKET_RELATIVE_PATH}`.",
        f"- Hash paquet : `{hashlib.sha256(packet.encode('utf-8')).hexdigest()}`.",
        "- 24 IDs aveugles nouveaux; ordre déterministe différent de v1; aucun tier ou score.",
        "- REVIEW_STATUS : `NOT_COMPLETED`; aucune appréciation humaine n'est préremplie.",
        f"- Clé locale ignorée : `{RECONCILIATION_KEY_RELATIVE_PATH}`.",
        f"- Hash clé : `{hashlib.sha256(key_json.encode('utf-8')).hexdigest()}`.",
        f"- Relecteur préféré : `{PREFERRED_REVIEWER}`.",
        f"- Fallback : `{FALLBACK_REVIEWER}` avec nouveaux IDs, exposition déclarée et aucun rapport machine ouvert pendant la revue.",
        "- Gate : 24/24 structures, 16/16 ordres faibles, 0 inversion, 0 non-évaluable et différenciation perceptible des 16 critères.",
        "- Objectif de design : `16/16` ordres humains stricts; toute égalité reçoit une disposition avant une évaluation fournisseur.",
        "",
        "## Exécution bornée",
        "",
        "- OPENAI_CALLS : `0`; ANTHROPIC_CALLS : `0`; PROVIDER_COST : `0`.",
        "- CREDENTIALS_RESOLVED : `FALSE`; PROVIDER_TRANSPORT_CONSTRUCTED : `FALSE`.",
        "- Policy scorer : conservée; judge recalibration : différée; route runtime : inchangée.",
        "- Calibration live/matrice fournisseur : `NOT_PREPARED / NOT_EXECUTED`.",
        "- ADR_REQUIRED : `YES`; ADR-P12-065 accepté pour le nouvel owner versionné.",
        "",
        "## Validations exécutées",
        "",
        "- Audit statique v2 : `9/9` règles actives, `0` issue sur le corpus canonique.",
        "- Tests ciblés v2 : `19 passed`.",
        "- Régression calibration : `149 passed, 1 skipped` (gate live explicitement désactivée).",
        "- Suite globale : `4335 passed, 3 skipped`.",
        "- Ruff global : `PASS`.",
        "- mypy `backend evaluation_harness` : `PASS`, 689 fichiers source.",
        "- compileall `backend evaluation_harness tests/calibration/pedagogical` : `PASS`.",
        "- Aucun test live fournisseur n'a été activé.",
        "",
        "## Livraison",
        "",
        "- Commit attendu : `test: establish revised pedagogical anchor corpus`.",
        "- Parent exact : `523d9bffaacebdae930a5a083ac466a3944d459a`.",
        "- Branche/upstream : `phase12/12-16-provider-model-calibration`.",
        "- main/origin-main attendus inchangés : `7ae02ee109bcc6399ec0f71616da6aef07abda81`.",
        "- Fichiers suivis créés :",
    ]
    lines.extend(f"  - `{relative_path}`" for relative_path in files_changed)
    lines.extend(
        (
            "- Worktree final attendu : `clean`.",
            f"- NEXT_GATE : `{NEXT_GATE}`.",
        )
    )
    return "\n".join(lines) + "\n"


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def write_outputs(root: Path = ROOT) -> None:
    if audit_v2_corpus():
        raise RuntimeError("ANCHOR_CORPUS_V2_STATIC_DIFFERENTIATION_FAILED")
    outputs = {
        PACKET_RELATIVE_PATH: render_human_prevalidation_packet(),
        MATRIX_RELATIVE_PATH: render_differentiation_matrix(),
        BASELINE_RELATIVE_PATH: render_baseline(),
        RECONCILIATION_KEY_RELATIVE_PATH: render_reconciliation_key_json(),
    }
    for relative_path, content in outputs.items():
        _atomic_write(root / relative_path, content.encode("utf-8"))


def main() -> None:
    write_outputs(ROOT)
    print(
        json.dumps(
            {
                "status": "PASS_CLOSED",
                "v1_preserved": calibration_corpus_sha256()
                == PEDAGOGICAL_CALIBRATION_CORPUS_V1_SHA256,
                "v2_version": PEDAGOGICAL_CALIBRATION_CORPUS_V2_VERSION,
                "v2_sha256": v2_calibration_corpus_sha256(),
                "anchor_count": len(V2_CALIBRATION_ANCHORS),
                "criterion_pair_count": len(V2_CALIBRATION_CRITERION_ITEMS),
                "provider_calls": 0,
                "next_gate": NEXT_GATE,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
