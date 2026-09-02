"""Versioned, offline-only strong-vs-non-strong calibration corpus v3."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from tests.calibration.pedagogical.anchor_corpus_v2 import (
    CONTROLLED_DIFFERENTIATION_MATRIX,
    PEDAGOGICAL_CALIBRATION_CORPUS_V2_VERSION,
    V2_ANCHOR_EXPECTATIONS,
    V2_CALIBRATION_ANCHORS,
    v2_calibration_corpus_sha256,
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

PEDAGOGICAL_CALIBRATION_CORPUS_V3_VERSION = "12.16-g1-v3"
V2_STATUS = "CLOSED_FAILED_HUMAN_PREVALIDATION_BASELINE"
OWNER_DECISION = "ALIGN_PRIMARY_CALIBRATION_TO_STRONG_ONLY_DELIVERABILITY"
PRODUCTION_CONTENT_POLICY = "STRONG_ONLY"
PRIMARY_CALIBRATION_SEPARATION = "STRONG_VS_NON_STRONG"
SECONDARY_DIAGNOSTIC = "MIXED_VS_WEAK_ORDERING_NON_BLOCKING"
NEXT_GATE = "12.16-G2-V3-HUMAN-DELTA-PREVALIDATION_READY"

V2_RECONCILIATION_RELATIVE_PATH = (
    "docs/development/"
    "PHASE_12_16_G2_V2_HUMAN_PREVALIDATION_RECONCILIATION.md"
)
MATRIX_RELATIVE_PATH = (
    "docs/development/"
    "PHASE_12_16_G2_ANCHOR_CORPUS_V3_CRITERION_DEFECT_ALIGNMENT_MATRIX.md"
)
PACKET_RELATIVE_PATH = (
    "docs/development/"
    "PHASE_12_16_G2_V3_HUMAN_DELTA_PREVALIDATION_PACKET.md"
)
BASELINE_RELATIVE_PATH = (
    "docs/development/"
    "PHASE_12_16_G2_ANCHOR_CORPUS_V3_STRONG_ONLY_REMEDIATION_BASELINE.md"
)
RECONCILIATION_KEY_RELATIVE_PATH = (
    "artifacts/calibration/12.16-g2-anchor-corpus-v3/"
    "human_delta_prevalidation_reconciliation.json"
)
ADR_RELATIVE_PATH = (
    "architecture/adr/"
    "ADR-P12-066-strong-only-deliverability-calibration-semantics.md"
)

EXPECTED_V2_RECONCILIATION_SHA256 = (
    "3ae6d71e47da917bcb904e5534ea4ec893d37887f4eba1b98c37c4ab4b0392fd"
)
EXPECTED_V2_CORPUS_SHA256 = (
    "4fe17f4286eb1a713a3d41a95b99260ef470ba32cadf33c2267dfc4dbaada427"
)
EXPECTED_V2_OWNER_SHA256 = (
    "bd0c5eff43be20b4f578b99321e076471804f8a3e0e197858b08a3701800be76"
)

HUMAN_LABELS = (
    "TRES_SATISFAISANT",
    "SATISFAISANT",
    "FRAGILE",
    "INSUFFISANT",
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

_HUMAN_RANK = {
    "TRES_SATISFAISANT": 4,
    "SATISFAISANT": 3,
    "FRAGILE": 2,
    "INSUFFISANT": 1,
}
_URL = re.compile(r"https?://", re.IGNORECASE)
_EMAIL = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b")
_LOCAL_PATH = re.compile(r"(?:[A-Za-z]:\\|/(?:home|Users|var|tmp)/)")


@dataclass(frozen=True, slots=True)
class V2HumanCriterionEvidence:
    scenario_code: str
    criterion_ref: str
    strong_label: str
    mixed_label: str
    weak_label: str


@dataclass(frozen=True, slots=True)
class CriterionDefectAlignment:
    scenario_code: str
    criterion_ref: str
    strong_intent: str
    mixed_controlled_defect: str
    weak_controlled_defect: str
    primary_deliverability_expectation: str
    secondary_mixed_weak_expectation: str
    v2_evidence: str
    v3_action: str


@dataclass(frozen=True, slots=True)
class CarryForwardEvidence:
    scenario_code: str
    criterion_ref: str
    tier: str
    v2_content_fingerprint: str
    v3_content_fingerprint: str
    human_v2_label: str
    reuse_allowed: bool
    reason: str


@dataclass(frozen=True, slots=True)
class BlindDeltaItem:
    review_item_id: str
    anchor_id: str


@dataclass(frozen=True, slots=True)
class V3StaticIssue:
    rule_id: str
    scenario_code: str
    detail: str


@dataclass(frozen=True, slots=True)
class CalibrationSemantics:
    production_content_policy: str
    primary_separation: str
    strong_role: str
    mixed_role: str
    weak_role: str
    secondary_diagnostic: str
    trinary_strict_ordering_target: str
    provider_recalibration_allowed: bool


CALIBRATION_SEMANTICS = CalibrationSemantics(
    production_content_policy="STRONG_ONLY",
    primary_separation="STRONG_VS_NON_STRONG",
    strong_role="DELIVERY_CANDIDATE",
    mixed_role="NON_DELIVERABLE_NEGATIVE_CONTROL",
    weak_role="NON_DELIVERABLE_NEGATIVE_CONTROL",
    secondary_diagnostic="MIXED_VS_WEAK_ORDERING_NON_BLOCKING",
    trinary_strict_ordering_target="DIAGNOSTIC_ONLY",
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


def _parse_v2_human_evidence() -> tuple[V2HumanCriterionEvidence, ...]:
    path = ROOT / V2_RECONCILIATION_RELATIVE_PATH
    source = path.read_bytes()
    if _sha256(source) != EXPECTED_V2_RECONCILIATION_SHA256:
        raise RuntimeError("V2_HUMAN_RECONCILIATION_SHA256_MISMATCH")
    pattern = re.compile(
        r"(?m)^\| (SCN-\d{2}) \| `([^`]+)` \| "
        r"(TRES_SATISFAISANT|SATISFAISANT|FRAGILE|INSUFFISANT|NON_EVALUABLE) \| "
        r"(TRES_SATISFAISANT|SATISFAISANT|FRAGILE|INSUFFISANT|NON_EVALUABLE) \| "
        r"(TRES_SATISFAISANT|SATISFAISANT|FRAGILE|INSUFFISANT|NON_EVALUABLE) \|"
    )
    evidence = tuple(
        V2HumanCriterionEvidence(*match.groups())
        for match in pattern.finditer(source.decode("utf-8"))
    )
    if len(evidence) != 16 or len({item.criterion_ref for item in evidence}) != 16:
        raise RuntimeError("V2_HUMAN_EVIDENCE_CARDINALITY")
    return evidence


V2_HUMAN_EVIDENCE = _parse_v2_human_evidence()


def _primary_failure_tiers(
    evidence: V2HumanCriterionEvidence,
) -> tuple[AnchorTier, ...]:
    if evidence.strong_label == "NON_EVALUABLE":
        return NEGATIVE_TIERS
    strong_rank = _HUMAN_RANK[evidence.strong_label]
    failures: list[AnchorTier] = []
    for tier, label in (
        (AnchorTier.MIXED, evidence.mixed_label),
        (AnchorTier.WEAK_BUT_STRUCTURALLY_VALID, evidence.weak_label),
    ):
        if label == "NON_EVALUABLE" or _HUMAN_RANK[label] >= strong_rank:
            failures.append(tier)
    return tuple(failures)


PRIMARY_FAILURE_TIERS_BY_CRITERION = {
    evidence.criterion_ref: _primary_failure_tiers(evidence)
    for evidence in V2_HUMAN_EVIDENCE
}
REVISED_NEGATIVE_CONTROLS = frozenset(
    (evidence.scenario_code, tier)
    for evidence in V2_HUMAN_EVIDENCE
    for tier in PRIMARY_FAILURE_TIERS_BY_CRITERION[evidence.criterion_ref]
)
REMEDIATED_SCENARIOS = tuple(
    scenario.scenario_code
    for scenario in CALIBRATION_SCENARIOS
    if any(
        (scenario.scenario_code, tier) in REVISED_NEGATIVE_CONTROLS
        for tier in NEGATIVE_TIERS
    )
)
CARRY_FORWARD_NEGATIVE_CONTROLS = frozenset(
    (scenario.scenario_code, tier)
    for scenario in CALIBRATION_SCENARIOS
    for tier in NEGATIVE_TIERS
    if (scenario.scenario_code, tier) not in REVISED_NEGATIVE_CONTROLS
)


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
            "Une ressource synthétique de management fournit un titre, un thème, une notion et un statut de contrôle sans hiérarchie de classement indiquée.",
        ),
        (
            "summary",
            "La ranger dans le thème indiqué et conserver son titre; la place de la notion et la procédure de vérification restent à définir avant réutilisation.",
        ),
    ),
    (
        "SCN-03",
        AnchorTier.MIXED,
    ): (
        (
            "objective",
            "Distinguer une finalité économique d'une finalité sociale dans une organisation.",
        ),
        (
            "concept",
            "La finalité économique concerne la pérennité et l'allocation des ressources; la finalité sociale concerne les parties prenantes internes.",
        ),
        (
            "example",
            "Une organisation synthétique finance son activité et modifie les conditions de ses parties prenantes internes.",
        ),
        (
            "summary",
            "Les deux finalités peuvent coexister, sans méthode fournie pour les identifier dans une situation de Première STMG.",
        ),
    ),
    (
        "SCN-03",
        AnchorTier.WEAK_BUT_STRUCTURALLY_VALID,
    ): (
        ("objective", "Repérer plusieurs finalités possibles d'une organisation."),
        (
            "concept",
            "Une organisation peut rechercher la continuité de son activité et agir pour les personnes, sans relier explicitement chaque action à une finalité précise.",
        ),
        (
            "example",
            "Une structure synthétique vend un service et modifie le travail de son équipe.",
        ),
        (
            "summary",
            "Ces actions peuvent répondre à plusieurs finalités, mais aucun critère ne permet ici de les distinguer.",
        ),
    ),
    (
        "SCN-04",
        AnchorTier.MIXED,
    ): (
        (
            "context",
            "Une opération synthétique fournit un montant hors taxe et un taux de TVA afin d'obtenir directement un total toutes taxes comprises.",
        ),
        (
            "concept",
            "Multiplier le montant hors taxe par un coefficient construit avec le taux permet d'obtenir le TTC, sans isoler le montant de TVA.",
        ),
        (
            "example",
            "Pour 100 unités hors taxe à 20 %, appliquer le coefficient 1,20 donne 120 unités TTC.",
        ),
        (
            "summary",
            "Calculer directement le TTC et donner son unité; la taxe intermédiaire et le contrôle comptable ne sont pas présentés.",
        ),
    ),
    (
        "SCN-04",
        AnchorTier.WEAK_BUT_STRUCTURALLY_VALID,
    ): (
        (
            "context",
            "Une opération synthétique indique un montant hors taxe, un taux et un total toutes taxes comprises à annoncer.",
        ),
        (
            "concept",
            "Le montant TTC comprend le montant hors taxe et une taxe proportionnelle, sans expliciter la formule ni l'enchaînement des calculs.",
        ),
        (
            "example",
            "Un montant hors taxe soumis à une taxe conduit à un total supérieur au montant de départ.",
        ),
        (
            "summary",
            "Identifier les données puis annoncer un TTC, sans calcul séparé de TVA, unité guidée ni vérification.",
        ),
    ),
    (
        "SCN-07",
        AnchorTier.MIXED,
    ): (
        (
            "context",
            "Une production synthétique assimile les ventes au résultat alors que des produits et des charges sont disponibles.",
        ),
        (
            "correction-link",
            "Correction: le résultat tient compte des produits et des charges; corriger l'égalité proposée sans diagnostic de l'oubli ni formule explicitée.",
        ),
        (
            "summary",
            "Remédiation: reprendre les montants, proposer un nouveau résultat puis relire la définition, sans étape de classement ni critère de réussite.",
        ),
    ),
    (
        "SCN-08",
        AnchorTier.MIXED,
    ): (
        (
            "question",
            "Quel calcul exprime la part des charges dans le chiffre d'affaires ?",
        ),
        (
            "options",
            "A. Charges divisées par chiffre d'affaires. B. Charges ajoutées au chiffre d'affaires. C. Charges multipliées par chiffre d'affaires. D. Chiffre d'affaires diminué des charges.",
        ),
        ("answer-key", "A"),
        (
            "feedback",
            "A construit le rapport demandé; les autres propositions sont incorrectes sans explication de la confusion associée.",
        ),
    ),
    (
        "SCN-08",
        AnchorTier.WEAK_BUT_STRUCTURALLY_VALID,
    ): (
        (
            "question",
            "Quelle formule donne le ratio des charges dans le chiffre d'affaires ?",
        ),
        (
            "options",
            "A. Charges divisées par chiffre d'affaires. B. Charges ajoutées au chiffre d'affaires. C. Charges diminuées du chiffre d'affaires. D. Chiffre d'affaires diminué des charges.",
        ),
        ("answer-key", "A"),
        ("feedback", "A est la bonne réponse."),
    ),
}


def _opaque_anchor_id(scenario_code: str, tier: AnchorTier) -> str:
    digest = hashlib.sha256(
        f"{PEDAGOGICAL_CALIBRATION_CORPUS_V3_VERSION}|{scenario_code}|{tier.value}".encode()
    ).hexdigest()[:12]
    return f"cal.v3.{scenario_code.casefold()}.{digest}"


_V2_TIER_BY_ANCHOR = {
    expectation.anchor_id: expectation.tier
    for expectation in V2_ANCHOR_EXPECTATIONS
}
_V2_ANCHOR_BY_SCENARIO_TIER = {
    (anchor.scenario_code, _V2_TIER_BY_ANCHOR[anchor.anchor_id]): anchor
    for anchor in V2_CALIBRATION_ANCHORS
}


V3_CALIBRATION_ANCHORS = tuple(
    CalibrationAnchor(
        anchor_id=_opaque_anchor_id(anchor.scenario_code, _V2_TIER_BY_ANCHOR[anchor.anchor_id]),
        scenario_code=anchor.scenario_code,
        sections=_REVISED_SECTIONS.get(
            (anchor.scenario_code, _V2_TIER_BY_ANCHOR[anchor.anchor_id]),
            anchor.sections,
        ),
    )
    for anchor in V2_CALIBRATION_ANCHORS
)
_V3_ANCHOR_BY_SCENARIO_TIER = {
    (anchor.scenario_code, tier): anchor
    for anchor, tier in zip(
        V3_CALIBRATION_ANCHORS,
        (_V2_TIER_BY_ANCHOR[item.anchor_id] for item in V2_CALIBRATION_ANCHORS),
        strict=True,
    )
}
V3_ANCHOR_EXPECTATIONS = tuple(
    AnchorExpectation(
        anchor_id=_V3_ANCHOR_BY_SCENARIO_TIER[(scenario.scenario_code, tier)].anchor_id,
        tier=tier,
    )
    for scenario in CALIBRATION_SCENARIOS
    for tier in TIER_ORDER
)
V3_CRITERION_ORDERINGS = tuple(
    CriterionOrdering(
        criterion_ref=criterion_ref,
        ordered_anchor_ids=tuple(
            _V3_ANCHOR_BY_SCENARIO_TIER[(scenario.scenario_code, tier)].anchor_id
            for tier in TIER_ORDER
        ),
    )
    for scenario in CALIBRATION_SCENARIOS
    for criterion_ref in scenario.criterion_refs
)


_V3_DEFECT_OVERRIDES = {
    "scn-01.quality.clarity": (
        "hiérarchie notion/thème non décidée et ordre de classement incomplet",
        "catégorie générale sans procédure de classement explicite",
    ),
    "scn-01.quality.organization-utility": (
        "statut conservé mais procédure de vérification et réutilisation non définie",
        "rangement minimal sans règle de vérification ou de réutilisation",
    ),
    "scn-03.quality.clarity": (
        "distinction correcte mais vocabulaire abstrait et articulation peu explicitée",
        "actions nommées sans correspondance explicite avec chaque finalité",
    ),
    "scn-03.quality.level-adaptation": (
        "jargon de parties prenantes et absence de méthode d'identification Première STMG",
        "exemple générique sans repères disciplinaires ni critère de distinction",
    ),
    "scn-04.quality.fidelity": (
        "TTC exact mais montant de TVA et enchaînement source non restitués",
        "relation HT/taxe/TTC seulement déclarée, sans formule ni calcul restituable",
    ),
    "scn-04.quality.level-adaptation": (
        "coefficient exploitable mais sans trace comptable ni contrôle du montant de taxe",
        "annonce abstraite du TTC sans unité guidée, étape ni vérification",
    ),
    "scn-07.quality.correction-quality": (
        "rectification générale sans diagnostic de l'oubli ni formule produits moins charges",
        "rectification superficielle qui rappelle seulement le rôle des charges",
    ),
    "scn-07.quality.remediation-clarity": (
        "nouveau résultat demandé sans classement, guidage ni critère de réussite",
        "invitation à revoir la notion sans tâche ni critère de réussite",
    ),
    "scn-08.quality.distractor-quality": (
        "trois opérations distinctes mais manifestement hors du format d'un ratio",
        "distracteurs arithmétiques formels sans confusion de ratio diagnostiquable",
    ),
    "scn-08.quality.feedback-quality": (
        "bonne réponse confirmée sans expliquer chaque erreur proposée",
        "confirmation de la lettre correcte sans justification ni remédiation",
    ),
}


_V2_MATRIX_BY_CRITERION = {
    item.criterion_ref: item for item in CONTROLLED_DIFFERENTIATION_MATRIX
}
_V2_EVIDENCE_BY_CRITERION = {
    item.criterion_ref: item for item in V2_HUMAN_EVIDENCE
}
CRITERION_DEFECT_ALIGNMENT_MATRIX = tuple(
    CriterionDefectAlignment(
        scenario_code=evidence.scenario_code,
        criterion_ref=evidence.criterion_ref,
        strong_intent=_V2_MATRIX_BY_CRITERION[evidence.criterion_ref].strong_intent,
        mixed_controlled_defect=_V3_DEFECT_OVERRIDES.get(
            evidence.criterion_ref,
            (
                _V2_MATRIX_BY_CRITERION[evidence.criterion_ref].mixed_defect,
                _V2_MATRIX_BY_CRITERION[evidence.criterion_ref].weak_defect,
            ),
        )[0],
        weak_controlled_defect=_V3_DEFECT_OVERRIDES.get(
            evidence.criterion_ref,
            (
                _V2_MATRIX_BY_CRITERION[evidence.criterion_ref].mixed_defect,
                _V2_MATRIX_BY_CRITERION[evidence.criterion_ref].weak_defect,
            ),
        )[1],
        primary_deliverability_expectation="STRONG > MIXED AND STRONG > WEAK",
        secondary_mixed_weak_expectation="DIAGNOSTIC_ONLY_NON_BLOCKING",
        v2_evidence=(
            f"STRONG={evidence.strong_label}; MIXED={evidence.mixed_label}; "
            f"WEAK={evidence.weak_label}"
        ),
        v3_action=(
            "REVISE_NEGATIVE_CONTROLS"
            if PRIMARY_FAILURE_TIERS_BY_CRITERION[evidence.criterion_ref]
            else "CARRY_FORWARD"
        ),
    )
    for evidence in V2_HUMAN_EVIDENCE
)


def _scenario_by_code(scenario_code: str) -> CalibrationScenario:
    return next(
        scenario
        for scenario in CALIBRATION_SCENARIOS
        if scenario.scenario_code == scenario_code
    )


def v3_anchor_by_id(anchor_id: str) -> CalibrationAnchor:
    return next(anchor for anchor in V3_CALIBRATION_ANCHORS if anchor.anchor_id == anchor_id)


def _content_fingerprint(anchor: CalibrationAnchor) -> str:
    return _sha256(anchor.candidate_projection().encode())


def build_carry_forward_manifest() -> tuple[CarryForwardEvidence, ...]:
    rows: list[CarryForwardEvidence] = []
    for evidence in V2_HUMAN_EVIDENCE:
        for tier, label in (
            (AnchorTier.STRONG, evidence.strong_label),
            (AnchorTier.MIXED, evidence.mixed_label),
            (AnchorTier.WEAK_BUT_STRUCTURALLY_VALID, evidence.weak_label),
        ):
            v2_anchor = _V2_ANCHOR_BY_SCENARIO_TIER[(evidence.scenario_code, tier)]
            v3_anchor = _V3_ANCHOR_BY_SCENARIO_TIER[(evidence.scenario_code, tier)]
            reused = v2_anchor.sections == v3_anchor.sections
            rows.append(
                CarryForwardEvidence(
                    scenario_code=evidence.scenario_code,
                    criterion_ref=evidence.criterion_ref,
                    tier=tier.value,
                    v2_content_fingerprint=_content_fingerprint(v2_anchor),
                    v3_content_fingerprint=_content_fingerprint(v3_anchor),
                    human_v2_label=label,
                    reuse_allowed=reused,
                    reason=(
                        "same scenario, criterion, tier, structure, context and byte-equivalent pedagogical content"
                        if reused
                        else "v2 control tied or exceeded STRONG on at least one criterion in the scenario"
                    ),
                )
            )
    return tuple(rows)


CARRY_FORWARD_MANIFEST = build_carry_forward_manifest()


def scorer_visible_projection(
    anchor: CalibrationAnchor,
    criterion_ref: str,
) -> dict[str, object]:
    scenario = _scenario_by_code(anchor.scenario_code)
    if criterion_ref not in scenario.criterion_refs:
        raise ValueError("criterion does not belong to scenario")
    return {
        "criterion": criterion_ref,
        "scenario": scenario.scenario_code,
        "pedagogical-level": scenario.level_code,
        "task-kind": scenario.task_kind,
        "candidate-projection": anchor.candidate_projection(),
        "reference-constraints": scenario.reference_constraints,
        "required-sections": scenario.required_sections,
    }


def v3_calibration_corpus_sha256() -> str:
    payload = {
        "version": PEDAGOGICAL_CALIBRATION_CORPUS_V3_VERSION,
        "semantics": {
            "production_content_policy": CALIBRATION_SEMANTICS.production_content_policy,
            "primary_separation": CALIBRATION_SEMANTICS.primary_separation,
            "strong_role": CALIBRATION_SEMANTICS.strong_role,
            "mixed_role": CALIBRATION_SEMANTICS.mixed_role,
            "weak_role": CALIBRATION_SEMANTICS.weak_role,
            "secondary_diagnostic": CALIBRATION_SEMANTICS.secondary_diagnostic,
            "trinary_strict_ordering_target": (
                CALIBRATION_SEMANTICS.trinary_strict_ordering_target
            ),
        },
        "anchors": [
            {
                "anchor_id": anchor.anchor_id,
                "scenario_code": anchor.scenario_code,
                "sections": anchor.sections,
            }
            for anchor in V3_CALIBRATION_ANCHORS
        ],
        "expectations": [
            {
                "anchor_id": item.anchor_id,
                "tier": item.tier.value,
            }
            for item in V3_ANCHOR_EXPECTATIONS
        ],
        "criterion_orderings": [
            {
                "criterion_ref": item.criterion_ref,
                "ordered_anchor_ids": item.ordered_anchor_ids,
            }
            for item in V3_CRITERION_ORDERINGS
        ],
        "alignment": [
            {
                "criterion_ref": item.criterion_ref,
                "mixed_controlled_defect": item.mixed_controlled_defect,
                "weak_controlled_defect": item.weak_controlled_defect,
                "v3_action": item.v3_action,
            }
            for item in CRITERION_DEFECT_ALIGNMENT_MATRIX
        ],
    }
    return _canonical_sha256(payload)


STATIC_RULE_IDS = (
    "v3.cardinality",
    "v3.ids-disjoint",
    "v3.strong-byte-equivalent",
    "v3.carry-forward-exact",
    "v3.revisions-bounded-by-v2-evidence",
    "v3.required-sections-exact",
    "v3.structurally-valid",
    "v3.primary-negative-distinct",
    "v3.safe-synthetic-content",
    "v3.primary-secondary-separation",
)


def audit_v3_corpus(
    anchors: tuple[CalibrationAnchor, ...] = V3_CALIBRATION_ANCHORS,
) -> tuple[V3StaticIssue, ...]:
    issues: list[V3StaticIssue] = []
    if (
        len(anchors) != 24
        or len({anchor.anchor_id for anchor in anchors}) != 24
        or len({anchor.scenario_code for anchor in anchors}) != 8
        or len(V3_CRITERION_ORDERINGS) != 16
    ):
        issues.append(V3StaticIssue("v3.cardinality", "ALL", "owner-counts"))
    legacy_ids = {anchor.anchor_id for anchor in (*CALIBRATION_ANCHORS, *V2_CALIBRATION_ANCHORS)}
    if legacy_ids & {anchor.anchor_id for anchor in anchors}:
        issues.append(V3StaticIssue("v3.ids-disjoint", "ALL", "legacy-overlap"))

    actual = {
        (anchor.scenario_code, expectation.tier): anchor
        for anchor, expectation in zip(anchors, V3_ANCHOR_EXPECTATIONS, strict=True)
    }
    for scenario in CALIBRATION_SCENARIOS:
        scenario_code = scenario.scenario_code
        for tier in TIER_ORDER:
            anchor = actual.get((scenario_code, tier))
            if anchor is None:
                issues.append(V3StaticIssue("v3.cardinality", scenario_code, tier.value))
                continue
            v2_anchor = _V2_ANCHOR_BY_SCENARIO_TIER[(scenario_code, tier)]
            revised = (scenario_code, tier) in REVISED_NEGATIVE_CONTROLS
            if tier is AnchorTier.STRONG and anchor.sections != v2_anchor.sections:
                issues.append(
                    V3StaticIssue(
                        "v3.strong-byte-equivalent",
                        scenario_code,
                        tier.value,
                    )
                )
            if tier in NEGATIVE_TIERS:
                if not revised and anchor.sections != v2_anchor.sections:
                    issues.append(
                        V3StaticIssue(
                            "v3.carry-forward-exact",
                            scenario_code,
                            tier.value,
                        )
                    )
                if revised and anchor.sections == v2_anchor.sections:
                    issues.append(
                        V3StaticIssue(
                            "v3.revisions-bounded-by-v2-evidence",
                            scenario_code,
                            tier.value,
                        )
                    )
            section_codes = tuple(code for code, _ in anchor.sections)
            if section_codes != scenario.required_sections:
                issues.append(
                    V3StaticIssue(
                        "v3.required-sections-exact",
                        scenario_code,
                        tier.value,
                    )
                )
            if any(not text or text != text.strip() for _, text in anchor.sections):
                issues.append(
                    V3StaticIssue(
                        "v3.structurally-valid",
                        scenario_code,
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
                    V3StaticIssue(
                        "v3.safe-synthetic-content",
                        scenario_code,
                        tier.value,
                    )
                )
        strong = actual.get((scenario_code, AnchorTier.STRONG))
        if strong is not None:
            for tier in NEGATIVE_TIERS:
                negative = actual.get((scenario_code, tier))
                if negative is not None and (
                    strong.candidate_projection() == negative.candidate_projection()
                ):
                    issues.append(
                        V3StaticIssue(
                            "v3.primary-negative-distinct",
                            scenario_code,
                            tier.value,
                        )
                    )
    if (
        CALIBRATION_SEMANTICS.primary_separation != "STRONG_VS_NON_STRONG"
        or CALIBRATION_SEMANTICS.secondary_diagnostic
        != "MIXED_VS_WEAK_ORDERING_NON_BLOCKING"
        or CALIBRATION_SEMANTICS.trinary_strict_ordering_target != "DIAGNOSTIC_ONLY"
    ):
        issues.append(
            V3StaticIssue(
                "v3.primary-secondary-separation",
                "ALL",
                "semantics",
            )
        )
    return tuple(issues)


def _delta_anchors() -> tuple[CalibrationAnchor, ...]:
    return tuple(
        _V3_ANCHOR_BY_SCENARIO_TIER[(scenario_code, tier)]
        for scenario_code in REMEDIATED_SCENARIOS
        for tier in TIER_ORDER
    )


def _blind_delta_mapping() -> tuple[BlindDeltaItem, ...]:
    ordered = sorted(
        _delta_anchors(),
        key=lambda anchor: hashlib.sha256(
            f"12.16-g2-v3-delta|{anchor.anchor_id}".encode()
        ).hexdigest(),
    )
    return tuple(
        BlindDeltaItem(f"HPV3D-{index:03d}", anchor.anchor_id)
        for index, anchor in enumerate(ordered, 1)
    )


def render_human_delta_packet() -> str:
    lines = [
        "# Phase 12.16-G2 — Paquet delta aveugle de prévalidation humaine v3",
        "",
        f"- Corpus : `{PEDAGOGICAL_CALIBRATION_CORPUS_V3_VERSION}`",
        f"- Checksum corpus : `{v3_calibration_corpus_sha256()}`",
        "- REVIEW_STATUS : `NOT_COMPLETED`",
        "- Relecteur ou relectrice :",
        "- Date :",
        "- Version de la grille : `human-delta-prevalidation-v3`",
        "- Exposition préalable :",
        "",
        "## Consignes",
        "",
        "1. Examiner chaque contenu sans consulter la clé locale ni les rapports antérieurs.",
        "2. Évaluer la structure et chacun des deux critères indiqués.",
        "3. Utiliser exactement un libellé contrôlé par appréciation.",
        "4. Ne pas corriger le contenu dans ce fichier.",
        "",
        "Libellés : `TRES_SATISFAISANT`, `SATISFAISANT`, `FRAGILE`, `INSUFFISANT`, `NON_EVALUABLE`.",
        "",
    ]
    for mapping in _blind_delta_mapping():
        anchor = v3_anchor_by_id(mapping.anchor_id)
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
        for section_code, section_text in anchor.sections:
            lines.append(f"  - `{section_code}` : {section_text}")
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
            "- Quinze items revus : [ ] oui [ ] non",
            "- Limites de la revue :",
            "- Avis : [ ] utilisable [ ] révisions requises [ ] inconclusif",
            "- Relecteur ou relectrice :",
            "- Responsable de la calibration :",
            "- Date de clôture :",
        )
    )
    return "\n".join(lines) + "\n"


def build_delta_reconciliation_key() -> dict[str, object]:
    expectation = {
        item.anchor_id: item.tier.value for item in V3_ANCHOR_EXPECTATIONS
    }
    items: list[dict[str, object]] = []
    for mapping in _blind_delta_mapping():
        anchor = v3_anchor_by_id(mapping.anchor_id)
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
    packet = render_human_delta_packet()
    return {
        "review_status": "NOT_COMPLETED",
        "corpus_version": PEDAGOGICAL_CALIBRATION_CORPUS_V3_VERSION,
        "corpus_sha256": v3_calibration_corpus_sha256(),
        "packet_sha256": _sha256(packet.encode()),
        "item_count": len(items),
        "remediated_scenario_count": len(REMEDIATED_SCENARIOS),
        "items": items,
    }


def render_delta_reconciliation_key_json() -> str:
    return _pretty_json(build_delta_reconciliation_key())


def render_alignment_matrix() -> str:
    lines = [
        "# Phase 12.16-G2 — Matrice d'alignement critère/défaut du corpus v3",
        "",
        f"- Version : `{PEDAGOGICAL_CALIBRATION_CORPUS_V3_VERSION}`.",
        f"- Checksum : `{v3_calibration_corpus_sha256()}`.",
        "- Séparation primaire : `STRONG > MIXED` et `STRONG > WEAK`.",
        "- Relation MIXED/WEAK : diagnostic secondaire non bloquant.",
        "- Aucun libellé humain n'est converti en seuil runtime.",
        "",
        "## Alignement des 16 critères",
        "",
        "| Scénario | Critère | Intention livrable | Défaut mixed | Défaut weak | Attente primaire | Attente secondaire | Preuve v2 | Action v3 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for item in CRITERION_DEFECT_ALIGNMENT_MATRIX:
        lines.append(
            f"| {item.scenario_code} | `{item.criterion_ref}` | {item.strong_intent} | "
            f"{item.mixed_controlled_defect} | {item.weak_controlled_defect} | "
            f"{item.primary_deliverability_expectation} | "
            f"{item.secondary_mixed_weak_expectation} | {item.v2_evidence} | "
            f"`{item.v3_action}` |"
        )
    lines.extend(
        (
            "",
            "## Manifeste de carry-forward",
            "",
            "| Scénario | Critère | Tier | Empreinte v2 | Empreinte v3 | Label humain v2 | Réutilisation | Motif |",
            "|---|---|---|---|---|---|:---:|---|",
        )
    )
    for carry_forward in CARRY_FORWARD_MANIFEST:
        lines.append(
            f"| {carry_forward.scenario_code} | `{carry_forward.criterion_ref}` | "
            f"{carry_forward.tier} | `{carry_forward.v2_content_fingerprint}` | "
            f"`{carry_forward.v3_content_fingerprint}` | "
            f"{carry_forward.human_v2_label} | "
            f"{'OUI' if carry_forward.reuse_allowed else 'NON'} | "
            f"{carry_forward.reason} |"
        )
    return "\n".join(lines) + "\n"


def render_baseline() -> str:
    packet = render_human_delta_packet()
    key = render_delta_reconciliation_key_json()
    files = (
        ADR_RELATIVE_PATH,
        BASELINE_RELATIVE_PATH,
        MATRIX_RELATIVE_PATH,
        PACKET_RELATIVE_PATH,
        "tests/architecture/test_anchor_corpus_v3_fitness.py",
        "tests/calibration/pedagogical/anchor_corpus_v3.py",
        "tests/calibration/pedagogical/test_anchor_corpus_v3.py",
    )
    lines = [
        "# Phase 12.16-G2 — Baseline de remédiation strong-only du corpus v3",
        "",
        "## Décision propriétaire",
        "",
        f"- OWNER_CALIBRATION_DECISION : `{OWNER_DECISION}`.",
        f"- ANCHOR_CORPUS_V2_STATUS : `{V2_STATUS}`.",
        f"- PRODUCTION_CONTENT_POLICY : `{PRODUCTION_CONTENT_POLICY}`.",
        f"- PRIMARY_CALIBRATION_SEPARATION : `{PRIMARY_CALIBRATION_SEPARATION}`.",
        f"- SECONDARY_DIAGNOSTIC : `{SECONDARY_DIAGNOSTIC}`.",
        "- PROVIDER_RECALIBRATION_ALLOWED : `FALSE`.",
        "- PROVIDER_ROUTE_CHANGE : `NONE`.",
        "- RELEASE_THRESHOLD_ADOPTION : `NOT_ALLOWED`.",
        "",
        "## Preuves v2 préservées",
        "",
        f"- Corpus v2 : `{PEDAGOGICAL_CALIBRATION_CORPUS_V2_VERSION}` ; checksum `{v2_calibration_corpus_sha256()}`.",
        f"- Rapport humain v2 : `{EXPECTED_V2_RECONCILIATION_SHA256}`.",
        "- Structures valides : `24/24`; STRONG TRES_SATISFAISANT : `16/16`.",
        "- Ordres stricts : `4/16`; faibles : `15/16`; inversions : `1`; non évaluable : `0`.",
        "- Différenciation perceptible : `11/16`; MIXED TRES_SATISFAISANT : `9/16`; WEAK : `6/16`.",
        "",
        "## Corpus v3",
        "",
        f"- Version : `{PEDAGOGICAL_CALIBRATION_CORPUS_V3_VERSION}`.",
        f"- Checksum : `{v3_calibration_corpus_sha256()}`.",
        "- Cardinalités : `8 scénarios / 16 critères / 24 anchors / 48 couples`.",
        "- Contenus STRONG carry-forward byte-equivalent : `8`.",
        f"- Contrôles négatifs carry-forward : `{len(CARRY_FORWARD_NEGATIVE_CONTROLS)}`.",
        f"- Contrôles négatifs remédiés : `{len(REVISED_NEGATIVE_CONTROLS)}`.",
        f"- Scénarios remédiés : `{', '.join(REMEDIATED_SCENARIOS)}`.",
        "- IDs v3 nouveaux, opaques et disjoints de v1/v2.",
        "",
        "## Paquet humain delta",
        "",
        f"- Paquet : `{PACKET_RELATIVE_PATH}`.",
        f"- Items : `{len(_blind_delta_mapping())}`.",
        f"- Hash paquet : `{_sha256(packet.encode())}`.",
        f"- Clé locale ignorée : `{RECONCILIATION_KEY_RELATIVE_PATH}`.",
        f"- Hash clé : `{_sha256(key.encode())}`.",
        "- Formulaire : `NOT_COMPLETED`; aucun tier, ordre attendu ou résultat v2 exposé.",
        "",
        "## Exécution bornée",
        "",
        "- PROVIDER_CALLS : `0`; PROVIDER_COST : `0`.",
        "- CREDENTIALS_RESOLVED : `FALSE`; PROVIDER_TRANSPORT_CONSTRUCTED : `FALSE`.",
        "- GateEngine/runtime/routes : `UNCHANGED`.",
        "- ADR-P12-066 : `ACCEPTED` pour la sémantique durable de livraison/calibration.",
        "",
        "## Livraison",
        "",
        "- Commit attendu : `test: establish strong-only pedagogical anchor corpus v3`.",
        "- Parent exact : `7a08b992a312f6d154b9630a3151a9a45ba0a65d`.",
        "- Branche : `phase12/12-16-provider-model-calibration`.",
        "- main/origin-main inchangés attendus : `7ae02ee109bcc6399ec0f71616da6aef07abda81`.",
        "- Fichiers suivis créés :",
    ]
    lines.extend(f"  - `{relative_path}`" for relative_path in files)
    lines.extend(
        (
            f"- NEXT_GATE : `{NEXT_GATE}`.",
            "- Calibration fournisseur : `NOT_AUTHORIZED / NOT_EXECUTED`.",
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
    tracked = {
        MATRIX_RELATIVE_PATH: render_alignment_matrix(),
        PACKET_RELATIVE_PATH: render_human_delta_packet(),
        BASELINE_RELATIVE_PATH: render_baseline(),
        RECONCILIATION_KEY_RELATIVE_PATH: render_delta_reconciliation_key_json(),
    }
    for relative_path, payload in tracked.items():
        _atomic_write(root / relative_path, payload.encode())


def main() -> None:
    issues = audit_v3_corpus()
    if issues:
        raise RuntimeError(_pretty_json([issue.rule_id for issue in issues]))
    write_outputs()
    packet = render_human_delta_packet()
    key = render_delta_reconciliation_key_json()
    print(
        json.dumps(
            {
                "status": "PASS_CLOSED",
                "version": PEDAGOGICAL_CALIBRATION_CORPUS_V3_VERSION,
                "corpus_sha256": v3_calibration_corpus_sha256(),
                "strong_carried_forward": 8,
                "negative_carried_forward": len(CARRY_FORWARD_NEGATIVE_CONTROLS),
                "negative_revised": len(REVISED_NEGATIVE_CONTROLS),
                "delta_items": len(_blind_delta_mapping()),
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
