"""Disposition-first, pairwise, offline-only calibration corpus v4."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from tests.calibration.pedagogical.anchor_corpus_v2 import V2_CALIBRATION_ANCHORS
from tests.calibration.pedagogical.anchor_corpus_v3 import (
    V3_ANCHOR_EXPECTATIONS,
    V3_CALIBRATION_ANCHORS,
)
from tests.calibration.pedagogical.catalog import (
    CALIBRATION_ANCHORS,
    CALIBRATION_SCENARIOS,
    AnchorExpectation,
    AnchorTier,
    CalibrationAnchor,
    CalibrationScenario,
    CriterionOrdering,
)

ROOT = Path(__file__).resolve().parents[3]

PEDAGOGICAL_CALIBRATION_CORPUS_V4_VERSION = "12.16-g1-v4"
V3_STATUS = "CLOSED_FAILED_HUMAN_PREVALIDATION_BASELINE"
OWNER_DECISION = "ADOPT_DISPOSITION_FIRST_PAIRWISE_HUMAN_CALIBRATION"
PRODUCTION_CONTENT_POLICY = "STRONG_ONLY"
PRIMARY_HUMAN_INSTRUMENT = (
    "DELIVERABILITY_DISPOSITION_PLUS_BLIND_PAIRWISE_CRITERION_COMPARISON"
)
ABSOLUTE_QUALITY_LABELS = "DIAGNOSTIC_ONLY"
PRIMARY_DELIVERY_GATE = "STRONG_DELIVER_AS_IS_AND_NEGATIVES_NOT_DELIVER_AS_IS"
PRIMARY_CRITERION_GATE = "STRONG_STRICTLY_PREFERRED_TO_EACH_NEGATIVE"
SECONDARY_DIAGNOSTIC = "MIXED_VS_WEAK_ORDERING_NON_BLOCKING"
REVISION_POLICY = "REVISE_ONLY_V3_NEGATIVES_WITH_ACTION_NONE"
STRONG_POLICY = "CARRY_FORWARD_ALL_8_BYTE_EQUIVALENT"
NEXT_GATE = "12.16-G2-V4-HUMAN-DISPOSITION-PAIRWISE-PREVALIDATION_READY"

ADR_RELATIVE_PATH = (
    "architecture/adr/"
    "ADR-P12-067-disposition-first-pairwise-human-calibration.md"
)
MATRIX_RELATIVE_PATH = (
    "docs/development/"
    "PHASE_12_16_G2_V4_NEGATIVE_CONTROL_REMEDIATION_MATRIX.md"
)
PACKET_RELATIVE_PATH = (
    "docs/development/"
    "PHASE_12_16_G2_V4_HUMAN_DISPOSITION_PAIRWISE_PACKET.md"
)
BASELINE_RELATIVE_PATH = (
    "docs/development/"
    "PHASE_12_16_G2_V4_DISPOSITION_FIRST_REMEDIATION_BASELINE.md"
)
RECONCILIATION_KEY_RELATIVE_PATH = (
    "artifacts/calibration/12.16-g2-anchor-corpus-v4/"
    "human_disposition_pairwise_reconciliation.json"
)

EXPECTED_V3_RECONCILIATION_REPORT_SHA256 = (
    "4268c70543a8cf26274db6fc2c9b334ee71473a9ef8f960f0e3109c64b7dffc9"
)
EXPECTED_V3_OWNER_SHA256 = (
    "cf90457393b02dca233cd4bc5d5c73e4a63a091591cb448d19b30b68e6bdc241"
)
EXPECTED_V3_BASELINE_SHA256 = (
    "216a2f9f938557e116b8306604decdafbe51a9f0e2fab235e560a7e719ba876c"
)
EXPECTED_ADR_P12_066_SHA256 = (
    "aaba7d443ef17d8e557ccbceb87961758901b12591a6f368bc38ad05fda8d3ea"
)
EXPECTED_V3_COMPLETED_REVIEW_SHA256 = (
    "a9595169083488c635886d18a608320f2ea7fed6576a6aa408c0e419c3ca3e9b"
)
EXPECTED_V3_RECONCILIATION_KEY_SHA256 = (
    "afe21aab0e83e2046fd5e6a26c5f3548f75ecc702550f16b5a4b6c2d7a4c6205"
)

DISPOSITIONS = (
    "DELIVER_AS_IS",
    "REVISE_BEFORE_DELIVERY",
    "REJECT",
    "NON_EVALUABLE",
)
TIER_ORDER = (
    AnchorTier.STRONG,
    AnchorTier.MIXED,
    AnchorTier.WEAK_BUT_STRUCTURALLY_VALID,
)
NEGATIVE_TIERS = (
    AnchorTier.MIXED,
    AnchorTier.WEAK_BUT_STRUCTURALLY_VALID,
)

_URL = re.compile(r"https?://", re.IGNORECASE)
_EMAIL = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b")
_LOCAL_PATH = re.compile(r"(?:[A-Za-z]:\\|/(?:home|Users|var|tmp)/)")


@dataclass(frozen=True, slots=True)
class DispositionFirstSemantics:
    production_content_policy: str
    strong_role: str
    mixed_role: str
    weak_role: str
    primary_human_instrument: str
    absolute_quality_labels: str
    primary_delivery_gate: str
    primary_criterion_gate: str
    secondary_diagnostic: str
    provider_recalibration_allowed: bool


@dataclass(frozen=True, slots=True)
class V3AnchorActionEvidence:
    scenario_code: str
    tier: str
    action: str
    labels: tuple[tuple[str, str], ...]
    source: str


@dataclass(frozen=True, slots=True)
class V4RemediationEvidence:
    scenario_code: str
    tier: str
    v3_action: str
    v3_content_hash: str
    v4_content_hash: str
    why_v3_was_deliverable: str
    v4_controlled_defect: str
    criterion_alignment: str
    expected_disposition: str


@dataclass(frozen=True, slots=True)
class BlindedCandidate:
    blinded_candidate_id: str
    anchor_id: str


@dataclass(frozen=True, slots=True)
class HumanScenarioCard:
    card_id: str
    scenario_code: str
    candidates: tuple[BlindedCandidate, ...]


@dataclass(frozen=True, slots=True)
class V4StaticIssue:
    rule_id: str
    scenario_code: str
    detail: str


CALIBRATION_SEMANTICS = DispositionFirstSemantics(
    production_content_policy="STRONG_ONLY",
    strong_role="DELIVERY_CANDIDATE",
    mixed_role="NON_DELIVERABLE_NEGATIVE_CONTROL",
    weak_role="NON_DELIVERABLE_NEGATIVE_CONTROL",
    primary_human_instrument=PRIMARY_HUMAN_INSTRUMENT,
    absolute_quality_labels=ABSOLUTE_QUALITY_LABELS,
    primary_delivery_gate=PRIMARY_DELIVERY_GATE,
    primary_criterion_gate=PRIMARY_CRITERION_GATE,
    secondary_diagnostic=SECONDARY_DIAGNOSTIC,
    provider_recalibration_allowed=False,
)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_sha256(payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return _sha256(encoded)


def _pretty_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _content_fingerprint(anchor: CalibrationAnchor) -> str:
    return _sha256(anchor.candidate_projection().encode())


_V3_REVIEW_ACTIONS = {
    "SCN-01": ("aucune", "aucune", "révision"),
    "SCN-02": ("aucune", "révision", "révision"),
    "SCN-03": ("aucune", "révision", "révision"),
    "SCN-04": ("aucune", "aucune", "exclusion"),
    "SCN-05": ("aucune", "révision", "exclusion"),
    "SCN-06": ("aucune", "aucune", "révision"),
    "SCN-07": ("aucune", "révision", "aucune"),
    "SCN-08": ("aucune", "révision", "aucune"),
}
_V3_REVIEW_SOURCES = {
    "SCN-01": "V3_DELTA",
    "SCN-02": "V2_CARRY_FORWARD",
    "SCN-03": "V3_DELTA",
    "SCN-04": "V3_DELTA",
    "SCN-05": "V2_CARRY_FORWARD",
    "SCN-06": "V2_CARRY_FORWARD",
    "SCN-07": "V3_DELTA",
    "SCN-08": "V3_DELTA",
}
_V3_TARGET_LABELS = {
    ("SCN-01", AnchorTier.MIXED): (
        ("scn-01.quality.clarity", "TRES_SATISFAISANT"),
        ("scn-01.quality.organization-utility", "TRES_SATISFAISANT"),
    ),
    ("SCN-04", AnchorTier.MIXED): (
        ("scn-04.quality.fidelity", "TRES_SATISFAISANT"),
        ("scn-04.quality.level-adaptation", "TRES_SATISFAISANT"),
    ),
    ("SCN-06", AnchorTier.MIXED): (
        ("scn-06.quality.assessment-clarity", "SATISFAISANT"),
        ("scn-06.quality.marking-scheme-coherence", "SATISFAISANT"),
    ),
    ("SCN-07", AnchorTier.WEAK_BUT_STRUCTURALLY_VALID): (
        ("scn-07.quality.correction-quality", "TRES_SATISFAISANT"),
        ("scn-07.quality.remediation-clarity", "TRES_SATISFAISANT"),
    ),
    ("SCN-08", AnchorTier.WEAK_BUT_STRUCTURALLY_VALID): (
        ("scn-08.quality.distractor-quality", "TRES_SATISFAISANT"),
        ("scn-08.quality.feedback-quality", "TRES_SATISFAISANT"),
    ),
}


def _build_v3_action_evidence() -> tuple[V3AnchorActionEvidence, ...]:
    evidence = tuple(
        V3AnchorActionEvidence(
            scenario_code=scenario_code,
            tier=tier.value,
            action=_V3_REVIEW_ACTIONS[scenario_code][tier_index],
            labels=_V3_TARGET_LABELS.get((scenario_code, tier), ()),
            source=_V3_REVIEW_SOURCES[scenario_code],
        )
        for scenario_code in _V3_REVIEW_ACTIONS
        for tier_index, tier in enumerate(TIER_ORDER)
    )
    actions = ("aucune", "révision", "exclusion")
    action_counts = {
        tier.value: {
            action: sum(
                item.tier == tier.value and item.action == action
                for item in evidence
            )
            for action in actions
        }
        for tier in TIER_ORDER
    }
    expected = {
        "STRONG": {"aucune": 8, "révision": 0, "exclusion": 0},
        "MIXED": {"aucune": 3, "révision": 5, "exclusion": 0},
        "WEAK_BUT_STRUCTURALLY_VALID": {
            "aucune": 2,
            "révision": 4,
            "exclusion": 2,
        },
    }
    if action_counts != expected or len(evidence) != 24:
        raise RuntimeError("V3_ACTION_EVIDENCE_CARDINALITY")
    return evidence


V3_ANCHOR_ACTION_EVIDENCE = _build_v3_action_evidence()
V3_ACTION_BY_SCENARIO_TIER = {
    (item.scenario_code, item.tier): item for item in V3_ANCHOR_ACTION_EVIDENCE
}
TARGETED_NEGATIVE_CONTROLS = frozenset(
    (item.scenario_code, AnchorTier(item.tier))
    for item in V3_ANCHOR_ACTION_EVIDENCE
    if item.tier != AnchorTier.STRONG.value and item.action == "aucune"
)
CARRIED_FORWARD_NEGATIVE_CONTROLS = frozenset(
    (item.scenario_code, AnchorTier(item.tier))
    for item in V3_ANCHOR_ACTION_EVIDENCE
    if item.tier != AnchorTier.STRONG.value
    and item.action in {"révision", "exclusion"}
)
if len(TARGETED_NEGATIVE_CONTROLS) != 5:
    raise RuntimeError("NEGATIVE_CONTROLS_TO_REVISE_MUST_EQUAL_5")
if len(CARRIED_FORWARD_NEGATIVE_CONTROLS) != 11:
    raise RuntimeError("NEGATIVE_CONTROLS_TO_CARRY_FORWARD_MUST_EQUAL_11")


_REVISED_SECTIONS: dict[
    tuple[str, AnchorTier],
    tuple[tuple[str, str], ...],
] = {
    (
        "SCN-01",
        AnchorTier.MIXED,
    ): (
        (
            "context",
            "Une ressource synthétique de management fournit un titre, un thème, une notion, un niveau et un statut de vérification, tous consignés dans une note libre unique.",
        ),
        (
            "summary",
            "Conserver cette note telle quelle et retrouver la ressource en parcourant les titres; aucune hiérarchie thème/notion, aucun champ de niveau et aucune règle d'usage du statut ne sont définis.",
        ),
    ),
    (
        "SCN-04",
        AnchorTier.MIXED,
    ): (
        (
            "context",
            "Une opération synthétique fournit un montant hors taxe et un taux de TVA, mais la transformation ne conserve que le total toutes taxes comprises à communiquer.",
        ),
        (
            "concept",
            "Le TTC comprend le montant hors taxe et une TVA proportionnelle; la relation est correcte, mais aucune formule ni étape ne montre comment obtenir la taxe.",
        ),
        (
            "example",
            "Pour 250 unités hors taxe à 20 %, la note annonce correctement 300 unités TTC sans faire apparaître les 50 unités de TVA ni le contrôle 250 plus 50.",
        ),
        (
            "summary",
            "Restituer le TTC correct en laissant à l'utilisateur la reconstruction du calcul de TVA, de l'enchaînement des étapes et du contrôle final.",
        ),
    ),
    (
        "SCN-06",
        AnchorTier.MIXED,
    ): (
        (
            "instructions",
            "Répondre aux deux questions à partir des données fournies, sans forme de calcul, unité ni justification explicitement attendue.",
        ),
        (
            "questions",
            "1. Calculer la TVA sur 200 unités hors taxe à 20 %. 2. Calculer le montant TTC.",
        ),
        (
            "marking-scheme",
            "Attribuer 6 points globalement si l'ensemble paraît correct, sans répartition par question, formule, application numérique, résultat ou unité.",
        ),
    ),
    (
        "SCN-07",
        AnchorTier.WEAK_BUT_STRUCTURALLY_VALID,
    ): (
        (
            "context",
            "Une production synthétique assimile les ventes au résultat alors que des produits et des charges sont disponibles.",
        ),
        (
            "correction-link",
            "Correction: le chiffre d'affaires et le résultat sont deux indicateurs différents, et les charges interviennent dans le résultat, sans diagnostic précis ni relation de calcul explicitée.",
        ),
        (
            "summary",
            "Remédiation: relire la définition puis remplacer la phrase erronée, sans classement des montants, recalcul guidé ni critère de réussite.",
        ),
    ),
    (
        "SCN-08",
        AnchorTier.WEAK_BUT_STRUCTURALLY_VALID,
    ): (
        (
            "question",
            "Quel calcul exprime la part des charges dans le chiffre d'affaires ?",
        ),
        (
            "options",
            "A. Charges divisées par chiffre d'affaires. B. Charges ajoutées au chiffre d'affaires. C. Charges multipliées par chiffre d'affaires. D. Charges diminuées du chiffre d'affaires.",
        ),
        ("answer-key", "A"),
        (
            "feedback",
            "A exprime le rapport demandé; les trois autres réponses sont seulement déclarées incorrectes, sans relier chacune à une confusion ni proposer de remédiation.",
        ),
    ),
}

_CONTROLLED_DEFECTS = {
    ("SCN-01", AnchorTier.MIXED): (
        "métadonnées aplaties dans une note libre sans hiérarchie, indexation ni procédure de vérification"
    ),
    ("SCN-04", AnchorTier.MIXED): (
        "résultat TTC factuellement exact mais méthode, taxe intermédiaire et contrôle non restituables"
    ),
    ("SCN-06", AnchorTier.MIXED): (
        "consignes sous-spécifiées et barème global non aligné sur les étapes évaluées"
    ),
    ("SCN-07", AnchorTier.WEAK_BUT_STRUCTURALLY_VALID): (
        "correction générale sans diagnostic, formule, activité bornée ni critère de réussite"
    ),
    ("SCN-08", AnchorTier.WEAK_BUT_STRUCTURALLY_VALID): (
        "distracteurs arithmétiques peu diagnostiques et feedback sans explication individualisée"
    ),
}


def _opaque_anchor_id(scenario_code: str, tier: AnchorTier) -> str:
    digest = hashlib.sha256(
        f"{PEDAGOGICAL_CALIBRATION_CORPUS_V4_VERSION}|{scenario_code}|{tier.value}".encode()
    ).hexdigest()[:12]
    return f"cal.v4.{scenario_code.casefold()}.{digest}"


_V3_TIER_BY_ANCHOR = {
    item.anchor_id: item.tier for item in V3_ANCHOR_EXPECTATIONS
}
_V3_ANCHOR_BY_SCENARIO_TIER = {
    (anchor.scenario_code, _V3_TIER_BY_ANCHOR[anchor.anchor_id]): anchor
    for anchor in V3_CALIBRATION_ANCHORS
}

V4_CALIBRATION_ANCHORS = tuple(
    CalibrationAnchor(
        anchor_id=_opaque_anchor_id(
            anchor.scenario_code,
            _V3_TIER_BY_ANCHOR[anchor.anchor_id],
        ),
        scenario_code=anchor.scenario_code,
        sections=_REVISED_SECTIONS.get(
            (anchor.scenario_code, _V3_TIER_BY_ANCHOR[anchor.anchor_id]),
            anchor.sections,
        ),
    )
    for anchor in V3_CALIBRATION_ANCHORS
)
_V4_ANCHOR_BY_SCENARIO_TIER = {
    (anchor.scenario_code, tier): anchor
    for anchor, tier in zip(
        V4_CALIBRATION_ANCHORS,
        (_V3_TIER_BY_ANCHOR[item.anchor_id] for item in V3_CALIBRATION_ANCHORS),
        strict=True,
    )
}
V4_ANCHOR_EXPECTATIONS = tuple(
    AnchorExpectation(
        anchor_id=_V4_ANCHOR_BY_SCENARIO_TIER[(scenario.scenario_code, tier)].anchor_id,
        tier=tier,
    )
    for scenario in CALIBRATION_SCENARIOS
    for tier in TIER_ORDER
)
V4_CRITERION_ORDERINGS = tuple(
    CriterionOrdering(
        criterion_ref=criterion_ref,
        ordered_anchor_ids=tuple(
            _V4_ANCHOR_BY_SCENARIO_TIER[(scenario.scenario_code, tier)].anchor_id
            for tier in TIER_ORDER
        ),
    )
    for scenario in CALIBRATION_SCENARIOS
    for criterion_ref in scenario.criterion_refs
)


def _scenario_by_code(scenario_code: str) -> CalibrationScenario:
    return next(
        scenario
        for scenario in CALIBRATION_SCENARIOS
        if scenario.scenario_code == scenario_code
    )


def v4_anchor_by_id(anchor_id: str) -> CalibrationAnchor:
    return next(anchor for anchor in V4_CALIBRATION_ANCHORS if anchor.anchor_id == anchor_id)


def _why_v3_was_deliverable(scenario_code: str, tier: AnchorTier) -> str:
    evidence = V3_ACTION_BY_SCENARIO_TIER[(scenario_code, tier.value)]
    labels = "; ".join(f"{criterion}={label}" for criterion, label in evidence.labels)
    return f"action=aucune; {labels}"


V4_REMEDIATION_MATRIX = tuple(
    V4RemediationEvidence(
        scenario_code=scenario_code,
        tier=tier.value,
        v3_action=V3_ACTION_BY_SCENARIO_TIER[(scenario_code, tier.value)].action,
        v3_content_hash=_content_fingerprint(
            _V3_ANCHOR_BY_SCENARIO_TIER[(scenario_code, tier)]
        ),
        v4_content_hash=_content_fingerprint(
            _V4_ANCHOR_BY_SCENARIO_TIER[(scenario_code, tier)]
        ),
        why_v3_was_deliverable=_why_v3_was_deliverable(scenario_code, tier),
        v4_controlled_defect=_CONTROLLED_DEFECTS[(scenario_code, tier)],
        criterion_alignment="; ".join(_scenario_by_code(scenario_code).criterion_refs),
        expected_disposition="REVISE_BEFORE_DELIVERY",
    )
    for scenario_code, tier in sorted(
        TARGETED_NEGATIVE_CONTROLS,
        key=lambda item: (item[0], item[1].value),
    )
)


def v4_calibration_corpus_sha256() -> str:
    payload = {
        "version": PEDAGOGICAL_CALIBRATION_CORPUS_V4_VERSION,
        "semantics": {
            "production_content_policy": CALIBRATION_SEMANTICS.production_content_policy,
            "strong_role": CALIBRATION_SEMANTICS.strong_role,
            "mixed_role": CALIBRATION_SEMANTICS.mixed_role,
            "weak_role": CALIBRATION_SEMANTICS.weak_role,
            "primary_human_instrument": (
                CALIBRATION_SEMANTICS.primary_human_instrument
            ),
            "absolute_quality_labels": CALIBRATION_SEMANTICS.absolute_quality_labels,
            "primary_delivery_gate": CALIBRATION_SEMANTICS.primary_delivery_gate,
            "primary_criterion_gate": CALIBRATION_SEMANTICS.primary_criterion_gate,
            "secondary_diagnostic": CALIBRATION_SEMANTICS.secondary_diagnostic,
        },
        "anchors": [
            {
                "anchor_id": anchor.anchor_id,
                "scenario_code": anchor.scenario_code,
                "sections": anchor.sections,
            }
            for anchor in V4_CALIBRATION_ANCHORS
        ],
        "expectations": [
            {"anchor_id": item.anchor_id, "tier": item.tier.value}
            for item in V4_ANCHOR_EXPECTATIONS
        ],
        "criterion_orderings": [
            {
                "criterion_ref": item.criterion_ref,
                "ordered_anchor_ids": item.ordered_anchor_ids,
            }
            for item in V4_CRITERION_ORDERINGS
        ],
        "targeted_remediation": [
            {
                "scenario_code": item.scenario_code,
                "tier": item.tier,
                "v3_action": item.v3_action,
                "v3_content_hash": item.v3_content_hash,
                "v4_content_hash": item.v4_content_hash,
                "controlled_defect": item.v4_controlled_defect,
                "expected_disposition": item.expected_disposition,
            }
            for item in V4_REMEDIATION_MATRIX
        ],
    }
    return _canonical_sha256(payload)


def _blinded_candidate_id(scenario_code: str, tier: AnchorTier) -> str:
    digest = hashlib.sha256(
        f"v4-human-candidate|{scenario_code}|{tier.value}".encode()
    ).hexdigest()[:10]
    return f"CAND-{digest.upper()}"


def _candidate_tier_order(scenario_code: str) -> tuple[AnchorTier, ...]:
    return tuple(
        sorted(
            TIER_ORDER,
            key=lambda tier: hashlib.sha256(
                f"v4-human-card-order|{scenario_code}|{tier.value}".encode()
            ).hexdigest(),
        )
    )


def build_human_scenario_cards() -> tuple[HumanScenarioCard, ...]:
    return tuple(
        HumanScenarioCard(
            card_id=f"V4H-{index:03d}",
            scenario_code=scenario.scenario_code,
            candidates=tuple(
                BlindedCandidate(
                    blinded_candidate_id=_blinded_candidate_id(
                        scenario.scenario_code,
                        tier,
                    ),
                    anchor_id=_V4_ANCHOR_BY_SCENARIO_TIER[
                        (scenario.scenario_code, tier)
                    ].anchor_id,
                )
                for tier in _candidate_tier_order(scenario.scenario_code)
            ),
        )
        for index, scenario in enumerate(CALIBRATION_SCENARIOS, 1)
    )


HUMAN_SCENARIO_CARDS = build_human_scenario_cards()


def render_human_packet() -> str:
    lines = [
        "# Phase 12.16-G2 — Prévalidation humaine disposition et comparaison v4",
        "",
        f"- Corpus : `{PEDAGOGICAL_CALIBRATION_CORPUS_V4_VERSION}`",
        f"- Checksum corpus : `{v4_calibration_corpus_sha256()}`",
        "- REVIEW_STATUS : `NOT_COMPLETED`",
        "- Relecteur ou relectrice :",
        "- Date :",
        "- Version de la grille : `human-disposition-pairwise-v4`",
        "- Exposition préalable :",
        "",
        "## Définitions contrôlées",
        "",
        "- `DELIVER_AS_IS` : peut être remis à l'utilisateur sans correction préalable.",
        "- `REVISE_BEFORE_DELIVERY` : pédagogiquement exploitable mais doit être corrigé ou amélioré avant livraison.",
        "- `REJECT` : ne doit pas être livré et nécessite une reprise substantielle.",
        "- `NON_EVALUABLE` : le contexte ne permet pas une décision fiable.",
        "",
        "## Consignes",
        "",
        "1. Examiner les trois candidats de chaque carte dans l'ordre affiché.",
        "2. Cocher exactement une disposition globale par candidat.",
        "3. Pour chaque critère, classer directement les trois IDs avec `>` et `=`.",
        "4. Utiliser chaque ID exactement une fois; exemple syntaxique : `ID-1 > ID-2 = ID-3`.",
        "5. Ne fournir aucun score numérique.",
        "6. Ajouter une seule justification courte par carte.",
        "",
    ]
    for card in HUMAN_SCENARIO_CARDS:
        scenario = _scenario_by_code(card.scenario_code)
        lines.extend(
            (
                f"## {card.card_id} — {scenario.scenario_code}",
                "",
                f"- Niveau : `{scenario.level_code}`",
                f"- Type de tâche : `{scenario.task_kind}`",
                f"- Critères : `{scenario.criterion_refs[0]}` ; `{scenario.criterion_refs[1]}`",
                f"- Sections requises : `{', '.join(scenario.required_sections)}`",
                "",
            )
        )
        for candidate in card.candidates:
            anchor = v4_anchor_by_id(candidate.anchor_id)
            lines.extend(
                (
                    f"### Candidat `{candidate.blinded_candidate_id}`",
                    "",
                )
            )
            lines.extend(
                f"- `{section_code}` : {section_text}"
                for section_code, section_text in anchor.sections
            )
            lines.extend(
                (
                    "",
                    "Disposition :",
                    "",
                    "- [ ] DELIVER_AS_IS",
                    "- [ ] REVISE_BEFORE_DELIVERY",
                    "- [ ] REJECT",
                    "- [ ] NON_EVALUABLE",
                    "",
                )
            )
        candidate_ids = ", ".join(
            candidate.blinded_candidate_id for candidate in card.candidates
        )
        for criterion_ref in scenario.criterion_refs:
            lines.append(
                f"- Classement relatif — `{criterion_ref}` (IDs : {candidate_ids}) :"
            )
        lines.extend(
            (
                "- Justification pédagogique courte de la carte :",
                "",
            )
        )
    lines.extend(
        (
            "## Synthèse et signatures",
            "",
            "- Huit cartes revues : [ ] oui [ ] non",
            "- Vingt-quatre dispositions renseignées : [ ] oui [ ] non",
            "- Seize classements relatifs renseignés : [ ] oui [ ] non",
            "- Avis : [ ] utilisable [ ] révisions requises [ ] inconclusif",
            "- Relecteur ou relectrice :",
            "- Responsable de la calibration :",
            "- Date de clôture :",
        )
    )
    return "\n".join(lines) + "\n"


def build_human_reconciliation_key() -> dict[str, object]:
    expected_tier = {
        item.anchor_id: item.tier.value for item in V4_ANCHOR_EXPECTATIONS
    }
    cards: list[dict[str, object]] = []
    for card in HUMAN_SCENARIO_CARDS:
        scenario = _scenario_by_code(card.scenario_code)
        projected: dict[str, object] = {
            "card_id": card.card_id,
            "scenario_code": card.scenario_code,
            "criterion_refs": scenario.criterion_refs,
            "candidates": [
                {
                    "blinded_candidate_id": candidate.blinded_candidate_id,
                    "anchor_id": candidate.anchor_id,
                    "expected_tier": expected_tier[candidate.anchor_id],
                }
                for candidate in card.candidates
            ],
        }
        projected["reconciliation_sha256"] = _canonical_sha256(projected)
        cards.append(projected)
    packet = render_human_packet()
    return {
        "review_status": "NOT_COMPLETED",
        "corpus_version": PEDAGOGICAL_CALIBRATION_CORPUS_V4_VERSION,
        "corpus_sha256": v4_calibration_corpus_sha256(),
        "packet_sha256": _sha256(packet.encode()),
        "card_count": len(cards),
        "candidate_count": sum(
            len(cast(list[object], card["candidates"])) for card in cards
        ),
        "criterion_ranking_count": 16,
        "disposition_choices": DISPOSITIONS,
        "cards": cards,
    }


def render_human_reconciliation_key_json() -> str:
    return _pretty_json(build_human_reconciliation_key())


def render_remediation_matrix() -> str:
    lines = [
        "# Phase 12.16-G2 — Matrice de remédiation ciblée des contrôles négatifs v4",
        "",
        f"- Corpus : `{PEDAGOGICAL_CALIBRATION_CORPUS_V4_VERSION}`.",
        f"- Checksum : `{v4_calibration_corpus_sha256()}`.",
        f"- Politique : `{REVISION_POLICY}`.",
        "- Les contenus restent factuellement exacts et structurellement complets.",
        "",
        "| scenario | tier | v3_action | v3_content_hash | v4_content_hash | why_v3_was_deliverable | v4_controlled_defect | criterion_alignment | expected_disposition |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for item in V4_REMEDIATION_MATRIX:
        lines.append(
            f"| {item.scenario_code} | {item.tier} | {item.v3_action} | "
            f"`{item.v3_content_hash}` | `{item.v4_content_hash}` | "
            f"{item.why_v3_was_deliverable} | {item.v4_controlled_defect} | "
            f"{item.criterion_alignment} | {item.expected_disposition} |"
        )
    return "\n".join(lines) + "\n"


def render_adr() -> str:
    return """# ADR-P12-067 — Calibration humaine disposition-first et pairwise

- Statut : Accepté
- Date : 2026-08-31
- Phase : 12.16-G2-V4-DISPOSITION-FIRST-REMEDIATION-A

## Contexte

La prévalidation humaine v3 est clôturée comme `CLOSED_FAILED_HUMAN_PREVALIDATION_BASELINE`. Les labels absolus ont confirmé la qualité des contenus livrables, mais ils n'ont pas discriminé uniformément les deux contrôles négatifs. La politique produit reste `STRONG_ONLY`; le changement porte sur l'instrument humain, sans baisse d'exigence.

## Décision

La disposition globale mesure directement la livrabilité avec `DELIVER_AS_IS`, `REVISE_BEFORE_DELIVERY`, `REJECT` ou `NON_EVALUABLE`. La comparaison pairwise aveugle mesure séparément, pour chaque critère, la préférence entre les trois candidats. Les labels absolus restent un diagnostic secondaire.

Le rôle `DELIVERY_CANDIDATE` reste réservé au contenu de référence. Les rôles `NON_DELIVERABLE_NEGATIVE_CONTROL` restent distincts; leur ordre relatif demeure secondaire et non bloquant. La gate primaire exige que le candidat livrable soit `DELIVER_AS_IS`, que les deux contrôles ne le soient pas et que le candidat livrable soit strictement préféré à chacun d'eux sur les seize critères.

Un scorer ou un model judge n'obtient aucune autorité runtime. Aucun seuil produit, aucune route fournisseur et aucune gate runtime ne sont créés. Les corpus v1, v2 et v3 restent byte-exact immuables.

## Conséquences

- Le corpus v4 reste un owner test-only offline.
- Les huit contenus livrables sont carry-forward byte-equivalent.
- Seuls les cinq contrôles négatifs associés à l'action humaine v3 `aucune` sont révisés.
- Les onze autres contrôles négatifs sont carry-forward byte-equivalent.
- Le paquet humain masque les tiers, les historiques et les mappings.
- La calibration fournisseur reste interdite.
"""


def render_baseline() -> str:
    packet = render_human_packet()
    key = render_human_reconciliation_key_json()
    return f"""# Phase 12.16-G2 — Baseline de remédiation disposition-first du corpus v4

## Décision propriétaire

- OWNER_CALIBRATION_DECISION : `{OWNER_DECISION}`.
- ANCHOR_CORPUS_V3_STATUS : `{V3_STATUS}`.
- PRODUCTION_CONTENT_POLICY : `{PRODUCTION_CONTENT_POLICY}`.
- PRIMARY_HUMAN_INSTRUMENT : `{PRIMARY_HUMAN_INSTRUMENT}`.
- ABSOLUTE_QUALITY_LABELS : `{ABSOLUTE_QUALITY_LABELS}`.
- PROVIDER_RECALIBRATION_ALLOWED : `FALSE`.
- PROVIDER_ROUTE_CHANGE : `NONE`.
- RELEASE_THRESHOLD_ADOPTION : `NOT_ALLOWED`.

## Corpus v4

- Version : `{PEDAGOGICAL_CALIBRATION_CORPUS_V4_VERSION}`.
- Checksum : `{v4_calibration_corpus_sha256()}`.
- Cardinalités : `8 scénarios / 16 critères / 24 anchors / 48 couples`.
- STRONG carry-forward byte-equivalent : `8/8`.
- Contrôles négatifs carry-forward byte-equivalent : `11/16`.
- Contrôles négatifs révisés : `5/16`.
- Politique de révision : `{REVISION_POLICY}`.
- IDs v4 opaques et disjoints de v1/v2/v3.

## Instrument humain

- Cartes scénario : `8`.
- Candidats anonymisés : `24`.
- Dispositions globales attendues : `24`.
- Classements critère par critère attendus : `16`.
- Paquet : `{PACKET_RELATIVE_PATH}`.
- Hash paquet : `{_sha256(packet.encode())}`.
- Clé locale ignorée : `{RECONCILIATION_KEY_RELATIVE_PATH}`.
- Hash clé : `{_sha256(key.encode())}`.

## Gates pré-déclarées

- Livrabilité : `8/8 candidat livrable = DELIVER_AS_IS`; `0/16 contrôles = DELIVER_AS_IS`; `0 NON_EVALUABLE`.
- Discrimination : `16/16 candidat livrable > contrôle intermédiaire`; `16/16 candidat livrable > contrôle faible`.
- Ordre entre contrôles : `SECONDARY_DIAGNOSTIC_NON_BLOCKING`.

## Exécution bornée

- PROVIDER_CALLS : `0`; PROVIDER_COST : `0`.
- CREDENTIALS_RESOLVED : `FALSE`; PROVIDER_TRANSPORT_CONSTRUCTED : `FALSE`.
- RUNTIME_ROUTE_CHANGE : `NONE`.
- RELEASE_THRESHOLD_ADOPTION : `NOT_ALLOWED`.
- TEST_LEVEL : `T2_BOUNDED`; GLOBAL_SUITE_RUN : `NO`.
- NEXT_GATE : `{NEXT_GATE}`.
"""


STATIC_RULE_IDS = (
    "v4.cardinality",
    "v4.ids-disjoint",
    "v4.strong-byte-equivalent",
    "v4.negative-carry-forward-exact",
    "v4.revisions-action-none-only",
    "v4.required-sections-exact",
    "v4.structurally-valid",
    "v4.safe-factual-synthetic-content",
    "v4.human-card-cardinality",
    "v4.packet-blindness",
    "v4.method-separation",
)


def audit_v4_corpus(
    anchors: tuple[CalibrationAnchor, ...] = V4_CALIBRATION_ANCHORS,
) -> tuple[V4StaticIssue, ...]:
    issues: list[V4StaticIssue] = []
    if (
        len(anchors) != 24
        or len({anchor.anchor_id for anchor in anchors}) != 24
        or len({anchor.scenario_code for anchor in anchors}) != 8
        or len(V4_CRITERION_ORDERINGS) != 16
    ):
        issues.append(V4StaticIssue("v4.cardinality", "ALL", "owner-counts"))
    legacy_ids = {
        anchor.anchor_id
        for anchor in (
            *CALIBRATION_ANCHORS,
            *V2_CALIBRATION_ANCHORS,
            *V3_CALIBRATION_ANCHORS,
        )
    }
    if legacy_ids & {anchor.anchor_id for anchor in anchors}:
        issues.append(V4StaticIssue("v4.ids-disjoint", "ALL", "legacy-overlap"))

    actual = {
        (anchor.scenario_code, expectation.tier): anchor
        for anchor, expectation in zip(anchors, V4_ANCHOR_EXPECTATIONS, strict=True)
    }
    for scenario in CALIBRATION_SCENARIOS:
        for tier in TIER_ORDER:
            key = (scenario.scenario_code, tier)
            anchor = actual[key]
            v3_anchor = _V3_ANCHOR_BY_SCENARIO_TIER[key]
            revised = key in TARGETED_NEGATIVE_CONTROLS
            if tier is AnchorTier.STRONG and anchor.sections != v3_anchor.sections:
                issues.append(
                    V4StaticIssue(
                        "v4.strong-byte-equivalent",
                        scenario.scenario_code,
                        tier.value,
                    )
                )
            if tier in NEGATIVE_TIERS:
                if revised and anchor.sections == v3_anchor.sections:
                    issues.append(
                        V4StaticIssue(
                            "v4.revisions-action-none-only",
                            scenario.scenario_code,
                            tier.value,
                        )
                    )
                if not revised and anchor.sections != v3_anchor.sections:
                    issues.append(
                        V4StaticIssue(
                            "v4.negative-carry-forward-exact",
                            scenario.scenario_code,
                            tier.value,
                        )
                    )
            section_codes = tuple(code for code, _ in anchor.sections)
            if section_codes != scenario.required_sections:
                issues.append(
                    V4StaticIssue(
                        "v4.required-sections-exact",
                        scenario.scenario_code,
                        tier.value,
                    )
                )
            if any(not text or text != text.strip() for _, text in anchor.sections):
                issues.append(
                    V4StaticIssue(
                        "v4.structurally-valid",
                        scenario.scenario_code,
                        tier.value,
                    )
                )
            projection = anchor.candidate_projection()
            if (
                not projection
                or len(projection) > 3_000
                or _URL.search(projection)
                or _EMAIL.search(projection)
                or _LOCAL_PATH.search(projection)
            ):
                issues.append(
                    V4StaticIssue(
                        "v4.safe-factual-synthetic-content",
                        scenario.scenario_code,
                        tier.value,
                    )
                )
    if (
        len(HUMAN_SCENARIO_CARDS) != 8
        or any(len(card.candidates) != 3 for card in HUMAN_SCENARIO_CARDS)
        or len(
            {
                candidate.blinded_candidate_id
                for card in HUMAN_SCENARIO_CARDS
                for candidate in card.candidates
            }
        )
        != 24
    ):
        issues.append(
            V4StaticIssue("v4.human-card-cardinality", "ALL", "8x3")
        )
    packet = render_human_packet()
    forbidden = (
        "STRONG",
        "MIXED",
        "WEAK_BUT_STRUCTURALLY_VALID",
        "action historique",
        "résultat v2",
        "résultat v3",
    )
    if any(marker.casefold() in packet.casefold() for marker in forbidden):
        issues.append(V4StaticIssue("v4.packet-blindness", "ALL", "tier-marker"))
    if (
        CALIBRATION_SEMANTICS.primary_human_instrument != PRIMARY_HUMAN_INSTRUMENT
        or CALIBRATION_SEMANTICS.absolute_quality_labels != "DIAGNOSTIC_ONLY"
        or CALIBRATION_SEMANTICS.secondary_diagnostic
        != "MIXED_VS_WEAK_ORDERING_NON_BLOCKING"
    ):
        issues.append(V4StaticIssue("v4.method-separation", "ALL", "semantics"))
    return tuple(issues)


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
    outputs = {
        ADR_RELATIVE_PATH: render_adr(),
        MATRIX_RELATIVE_PATH: render_remediation_matrix(),
        PACKET_RELATIVE_PATH: render_human_packet(),
        BASELINE_RELATIVE_PATH: render_baseline(),
        RECONCILIATION_KEY_RELATIVE_PATH: (
            render_human_reconciliation_key_json()
        ),
    }
    for relative_path, payload in outputs.items():
        _atomic_write(root / relative_path, payload.encode())


def main() -> None:
    issues = audit_v4_corpus()
    if issues:
        raise RuntimeError(_pretty_json([issue.rule_id for issue in issues]))
    packet = render_human_packet()
    key = render_human_reconciliation_key_json()
    print(
        json.dumps(
            {
                "status": "PASS_CLOSED",
                "version": PEDAGOGICAL_CALIBRATION_CORPUS_V4_VERSION,
                "corpus_sha256": v4_calibration_corpus_sha256(),
                "strong_carried_forward": 8,
                "negative_carried_forward": 11,
                "negative_revised": 5,
                "human_scenario_cards": len(HUMAN_SCENARIO_CARDS),
                "packet_sha256": _sha256(packet.encode()),
                "key_sha256": _sha256(key.encode()),
                "provider_calls": 0,
                "next_gate": NEXT_GATE,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
