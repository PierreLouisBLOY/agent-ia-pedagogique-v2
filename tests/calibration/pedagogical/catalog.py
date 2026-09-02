"""Immutable, synthetic and provider-blind pedagogical anchor corpus."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum

from tests.e2e.core.catalog import (
    CANONICAL_PEDAGOGICAL_SCENARIOS,
    CanonicalPedagogicalScenario,
)

PEDAGOGICAL_CALIBRATION_CORPUS_VERSION = "12.16-g1-v1"


class AnchorTier(StrEnum):
    """Analysis-only ordinal labels, never serialized for a scorer."""

    STRONG = "STRONG"
    MIXED = "MIXED"
    WEAK_BUT_STRUCTURALLY_VALID = "WEAK_BUT_STRUCTURALLY_VALID"


@dataclass(frozen=True, slots=True)
class CalibrationScenario:
    scenario_code: str
    level_code: str
    task_kind: str
    scope_code: str
    required_sections: tuple[str, ...]
    rubric_ref: str
    criterion_refs: tuple[str, str]
    reference_constraints: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CalibrationAnchor:
    """Scorer-visible content has no tier, provider, model or expected score."""

    anchor_id: str
    scenario_code: str
    sections: tuple[tuple[str, str], ...]

    def candidate_projection(self) -> str:
        return "\n".join(f"[{code}] {text}" for code, text in self.sections)


@dataclass(frozen=True, slots=True)
class AnchorExpectation:
    """Analysis-only link between an opaque anchor and its ordinal tier."""

    anchor_id: str
    tier: AnchorTier


@dataclass(frozen=True, slots=True)
class CriterionOrdering:
    criterion_ref: str
    ordered_anchor_ids: tuple[str, str, str]


_REFERENCE_CONSTRAINTS = {
    "SCN-01": (
        "organiser une ressource synthetique sans inventer de metadonnees",
        "rendre la structure directement exploitable par un enseignant",
    ),
    "SCN-02": (
        "rester centre sur la recherche pedagogique demandee",
        "couvrir les elements utiles sans ajouter de source externe",
    ),
    "SCN-03": (
        "expliquer un concept de management avec un exemple",
        "adapter le vocabulaire au niveau premiere-stmg",
    ),
    "SCN-04": (
        "preserver le sens de la note synthetique sur la tva",
        "adapter l'explication au niveau bts-cg-1",
    ),
    "SCN-05": (
        "proposer un exercice resoluble au niveau terminale-stmg",
        "formuler des consignes sans ambiguite",
    ),
    "SCN-06": (
        "produire une evaluation courte au niveau bts-cg-1",
        "aligner chaque attribution de points avec une reponse attendue",
    ),
    "SCN-07": (
        "corriger la production synthetique en preservant sa contrainte",
        "proposer une remediation bornee au niveau bts-cg-2",
    ),
    "SCN-08": (
        "proposer une seule bonne reponse et trois distracteurs plausibles",
        "expliquer la reponse sans introduire de nouvelle question",
    ),
}


def _criterion_refs(scenario: CanonicalPedagogicalScenario) -> tuple[str, str]:
    refs = tuple(item.criterion_ref.value for item in scenario.rubric.criteria)
    if len(refs) != 2:
        raise ValueError("each canonical pedagogical rubric must expose two criteria")
    return refs


CALIBRATION_SCENARIOS = tuple(
    CalibrationScenario(
        scenario_code=scenario.case.code.value,
        level_code=scenario.level.value,
        task_kind=scenario.intent.value,
        scope_code=scenario.fixture.scope_code,
        required_sections=tuple(code.value for code in scenario.section_codes),
        rubric_ref=scenario.rubric.rubric_ref.value,
        criterion_refs=_criterion_refs(scenario),
        reference_constraints=_REFERENCE_CONSTRAINTS[scenario.case.code.value],
    )
    for scenario in CANONICAL_PEDAGOGICAL_SCENARIOS
)


_ANCHOR_SECTIONS: dict[str, tuple[tuple[tuple[str, str], ...], ...]] = {
    "SCN-01": (
        (
            (
                "context",
                "La ressource porte sur la caracterisation d'une organisation et contient "
                "un titre, un theme et un statut synthetiques.",
            ),
            (
                "summary",
                "Classer d'abord par theme, puis afficher le titre et le statut; cette "
                "organisation permet de retrouver et verifier la ressource rapidement.",
            ),
        ),
        (
            (
                "context",
                "La ressource de management comporte un titre et quelques informations de "
                "classement utiles.",
            ),
            (
                "summary",
                "La ranger par theme et conserver le titre; le statut peut etre consulte "
                "ensuite si necessaire.",
            ),
        ),
        (
            ("context", "Une ressource synthetique doit etre rangee dans le corpus."),
            (
                "summary",
                "Placer la ressource dans une categorie et conserver les informations "
                "disponibles.",
            ),
        ),
    ),
    "SCN-02": (
        (
            (
                "concept",
                "La recherche cible les ressources de gestion financiere pour terminale-stmg "
                "qui expliquent un calcul et donnent un exemple synthetique.",
            ),
            (
                "summary",
                "Retenir les ressources couvrant a la fois la notion, la methode de calcul et "
                "un exemple; ecarter les resultats hors niveau ou sans explication.",
            ),
        ),
        (
            (
                "concept",
                "La recherche concerne la gestion financiere au niveau terminale-stmg et doit "
                "reperer une methode de calcul.",
            ),
            (
                "summary",
                "Retenir les resultats lies au theme et au niveau; la presence d'un exemple "
                "reste souhaitable.",
            ),
        ),
        (
            ("concept", "La recherche doit trouver des ressources de gestion."),
            (
                "summary",
                "Conserver les documents qui mentionnent le sujet, puis les presenter dans une "
                "liste.",
            ),
        ),
    ),
    "SCN-03": (
        (
            (
                "objective",
                "Distinguer une finalite economique d'une finalite sociale dans une "
                "organisation.",
            ),
            (
                "concept",
                "La finalite economique vise la perennite de l'activite; la finalite sociale "
                "concerne les conditions et l'interet des personnes impliquees.",
            ),
            (
                "example",
                "Une cooperative peut rechercher un excedent pour financer son activite tout "
                "en ameliorant les conditions de travail de ses membres.",
            ),
            (
                "summary",
                "Les deux finalites peuvent coexister: l'une soutient l'activite, l'autre porte "
                "sur ses effets humains.",
            ),
        ),
        (
            ("objective", "Reconnaitre deux finalites d'une organisation."),
            (
                "concept",
                "Une finalite economique concerne les resultats de l'activite, tandis qu'une "
                "finalite sociale concerne les personnes.",
            ),
            (
                "example",
                "Une entreprise peut vendre ses produits et proposer de meilleures conditions "
                "de travail.",
            ),
            ("summary", "Une organisation peut poursuivre plusieurs finalites."),
        ),
        (
            ("objective", "Comprendre les finalites."),
            (
                "concept",
                "Les organisations ont des objectifs economiques et sociaux qui orientent leur "
                "fonctionnement.",
            ),
            ("example", "Une organisation vend et emploie des personnes."),
            ("summary", "Les finalites indiquent ce que recherche l'organisation."),
        ),
    ),
    "SCN-04": (
        (
            (
                "context",
                "Une operation synthetique distingue un montant hors taxe, la tva calculee et "
                "le montant toutes taxes comprises.",
            ),
            (
                "concept",
                "La tva se calcule en appliquant le taux au montant hors taxe; le total toutes "
                "taxes comprises est la somme du hors taxe et de la tva.",
            ),
            (
                "example",
                "Pour 100 unites hors taxe avec un taux de 20 %, la tva vaut 20 unites et le "
                "total vaut 120 unites.",
            ),
            (
                "summary",
                "Identifier le hors taxe, appliquer le taux, puis additionner la taxe pour "
                "obtenir le total.",
            ),
        ),
        (
            ("context", "La note synthetique presente une operation soumise a la tva."),
            (
                "concept",
                "La taxe est calculee a partir du montant hors taxe, puis ajoutee pour obtenir "
                "le total.",
            ),
            (
                "example",
                "Avec 100 unites hors taxe et 20 % de taxe, le total est de 120 unites.",
            ),
            ("summary", "Calculer la taxe puis le montant total."),
        ),
        (
            ("context", "Une operation comptable synthetique comporte une taxe."),
            ("concept", "La taxe intervient dans le calcul du montant a payer."),
            ("example", "Un montant de 100 unites devient un montant plus eleve avec la taxe."),
            ("summary", "Ajouter la taxe au montant de depart."),
        ),
    ),
    "SCN-05": (
        (
            (
                "context",
                "Une entreprise synthetique compare deux investissements a partir de leur cout "
                "et d'une economie annuelle fournie.",
            ),
            (
                "questions",
                "1. Calculer la duree de recuperation de chaque investissement. 2. Justifier "
                "le choix le plus rapide en montrant les deux calculs.",
            ),
            (
                "correction-link",
                "La correction separee rappelle la formule cout divise par economie annuelle et "
                "detaille les deux substitutions numeriques.",
            ),
        ),
        (
            (
                "context",
                "Une entreprise synthetique hesite entre deux investissements de couts "
                "differents.",
            ),
            (
                "questions",
                "1. Calculer une duree de recuperation pour chaque choix. 2. Indiquer le choix "
                "qui semble preferable.",
            ),
            (
                "correction-link",
                "La correction separee donne la formule et les resultats, avec une justification "
                "courte.",
            ),
        ),
        (
            ("context", "Deux investissements synthetiques sont proposes a une entreprise."),
            (
                "questions",
                "1. Faire les calculs utiles. 2. Choisir un investissement et expliquer la "
                "reponse.",
            ),
            ("correction-link", "Une correction separee indique le choix retenu."),
        ),
    ),
    "SCN-06": (
        (
            (
                "instructions",
                "Repondre aux deux questions en presentant chaque formule, chaque calcul et "
                "l'unite du resultat.",
            ),
            (
                "questions",
                "1. Calculer la tva sur 250 unites hors taxe au taux de 20 %. 2. Determiner le "
                "montant toutes taxes comprises.",
            ),
            (
                "marking-scheme",
                "Question 1: formule 1 point, application 1 point, resultat 1 point. Question 2: "
                "formule 1 point, calcul 1 point, unite 1 point.",
            ),
        ),
        (
            ("instructions", "Presenter les calculs demandes et les resultats."),
            (
                "questions",
                "1. Calculer la tva sur 250 unites hors taxe a 20 %. 2. Calculer le total toutes "
                "taxes comprises.",
            ),
            (
                "marking-scheme",
                "Question 1: 3 points pour le calcul. Question 2: 3 points pour le resultat et "
                "la presentation.",
            ),
        ),
        (
            ("instructions", "Effectuer les calculs de taxe."),
            ("questions", "1. Trouver la taxe. 2. Donner le total."),
            (
                "marking-scheme",
                "Question 1: 3 points. Question 2: 3 points. Valoriser une reponse correcte.",
            ),
        ),
    ),
    "SCN-07": (
        (
            (
                "context",
                "La production synthetique confond le chiffre d'affaires avec le resultat, "
                "alors que les charges doivent rester prises en compte.",
            ),
            (
                "correction-link",
                "Correction: le chiffre d'affaires mesure les ventes; le resultat correspond "
                "aux produits diminues des charges. La contrainte sur les charges est preservee.",
            ),
            (
                "summary",
                "Remediation: classer trois montants fictifs en produits ou charges, puis "
                "recalculer le resultat et expliquer la difference avec les ventes.",
            ),
        ),
        (
            (
                "context",
                "La production synthetique assimile les ventes au resultat et mentionne aussi "
                "des charges.",
            ),
            (
                "correction-link",
                "Correction: le resultat ne se limite pas aux ventes, car les charges doivent "
                "etre soustraites.",
            ),
            (
                "summary",
                "Remediation: refaire un calcul simple avec un montant de ventes et un montant "
                "de charges.",
            ),
        ),
        (
            ("context", "Une production synthetique comporte une confusion de calcul."),
            ("correction-link", "Correction: il faut tenir compte de toutes les donnees."),
            ("summary", "Remediation: reprendre le calcul et verifier le resultat."),
        ),
    ),
    "SCN-08": (
        (
            (
                "question",
                "Quel indicateur exprime la part des charges dans le chiffre d'affaires ?",
            ),
            (
                "options",
                "A. Charges divisees par chiffre d'affaires. B. Chiffre d'affaires divise par "
                "charges. C. Charges moins chiffre d'affaires. D. Charges plus chiffre d'affaires.",
            ),
            ("answer-key", "A"),
            (
                "feedback",
                "La reponse A construit une proportion comparable en rapportant les charges au "
                "chiffre d'affaires; les autres operations inversent ou changent la relation.",
            ),
        ),
        (
            ("question", "Comment calculer le poids des charges dans les ventes ?"),
            (
                "options",
                "A. Charges divisees par ventes. B. Ventes divisees par charges. C. Charges "
                "multipliees par ventes. D. Charges seules.",
            ),
            ("answer-key", "A"),
            (
                "feedback",
                "La reponse A compare les charges aux ventes; les autres choix n'expriment pas "
                "cette part.",
            ),
        ),
        (
            ("question", "Quelle operation permet de comparer les charges aux ventes ?"),
            (
                "options",
                "A. Diviser les charges par les ventes. B. Ajouter un. C. Multiplier par zero. "
                "D. Ne faire aucun calcul.",
            ),
            ("answer-key", "A"),
            ("feedback", "La reponse A effectue la comparaison demandee."),
        ),
    ),
}


_SUFFIX_TIERS = (
    ("a", AnchorTier.STRONG),
    ("b", AnchorTier.MIXED),
    ("c", AnchorTier.WEAK_BUT_STRUCTURALLY_VALID),
)


CALIBRATION_ANCHORS = tuple(
    CalibrationAnchor(
        anchor_id=f"cal.{scenario.scenario_code.lower()}.{suffix}",
        scenario_code=scenario.scenario_code,
        sections=sections,
    )
    for scenario in CALIBRATION_SCENARIOS
    for (suffix, _), sections in zip(
        _SUFFIX_TIERS,
        _ANCHOR_SECTIONS[scenario.scenario_code],
        strict=True,
    )
)


ANCHOR_EXPECTATIONS = tuple(
    AnchorExpectation(
        anchor_id=f"cal.{scenario.scenario_code.lower()}.{suffix}",
        tier=tier,
    )
    for scenario in CALIBRATION_SCENARIOS
    for suffix, tier in _SUFFIX_TIERS
)


CRITERION_ORDERINGS = tuple(
    CriterionOrdering(
        criterion_ref=criterion_ref,
        ordered_anchor_ids=tuple(
            f"cal.{scenario.scenario_code.lower()}.{suffix}"
            for suffix, _ in _SUFFIX_TIERS
        ),
    )
    for scenario in CALIBRATION_SCENARIOS
    for criterion_ref in scenario.criterion_refs
)


def scenario_by_code(scenario_code: str) -> CalibrationScenario:
    return next(
        scenario
        for scenario in CALIBRATION_SCENARIOS
        if scenario.scenario_code == scenario_code
    )


def anchor_by_id(anchor_id: str) -> CalibrationAnchor:
    return next(anchor for anchor in CALIBRATION_ANCHORS if anchor.anchor_id == anchor_id)


def calibration_corpus_sha256() -> str:
    payload = {
        "version": PEDAGOGICAL_CALIBRATION_CORPUS_VERSION,
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
            for anchor in CALIBRATION_ANCHORS
        ],
        "expectations": [
            {"anchor_id": item.anchor_id, "tier": item.tier.value}
            for item in ANCHOR_EXPECTATIONS
        ],
        "orderings": [
            {
                "criterion_ref": item.criterion_ref,
                "ordered_anchor_ids": item.ordered_anchor_ids,
            }
            for item in CRITERION_ORDERINGS
        ],
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()
