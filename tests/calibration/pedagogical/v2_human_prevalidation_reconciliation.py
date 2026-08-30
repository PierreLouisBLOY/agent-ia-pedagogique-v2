"""Deterministic, offline reconciliation of the v2 human prevalidation."""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections import Counter
from collections.abc import Callable, Mapping
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import cast

from tests.calibration.pedagogical.anchor_corpus_v2 import (
    HUMAN_LABELS,
    PACKET_RELATIVE_PATH,
    PEDAGOGICAL_CALIBRATION_CORPUS_V2_VERSION,
    RECONCILIATION_KEY_RELATIVE_PATH,
    V2_ANCHOR_EXPECTATIONS,
    V2_CALIBRATION_ANCHORS,
    V2_CRITERION_ORDERINGS,
    build_reconciliation_key,
    v2_calibration_corpus_sha256,
)

ROOT = Path(__file__).resolve().parents[3]

COMPLETED_PREVALIDATION_RELATIVE_PATH = (
    "artifacts/calibration/12.16-g2-anchor-corpus-v2/completed_prevalidation.md"
)
RESULT_JSON_RELATIVE_PATH = (
    "artifacts/calibration/12.16-g2-anchor-corpus-v2/"
    "human_prevalidation_reconciliation_result.json"
)
REPORT_RELATIVE_PATH = (
    "docs/development/"
    "PHASE_12_16_G2_V2_HUMAN_PREVALIDATION_RECONCILIATION.md"
)

EXPECTED_COMPLETED_PREVALIDATION_SHA256 = (
    "08fb3d0d9a0dc04ced4876cbfdeace13975fc1c47f402995f9e761affe52bfb6"
)
SUPERSEDED_COMPLETED_PREVALIDATION_SHA256 = (
    "2a22172586cd8836b192a94f05c8b8cc6027d521ff04547829f3152aee55fd7e"
)
EXPECTED_RECONCILIATION_KEY_SHA256 = (
    "eb20fe93ae76215218fea3958bd44d6e2c0d7d5c476cec4350e6eb6146084ef0"
)
EXPECTED_PACKET_SHA256 = (
    "81bca8cc998e866c7b08f22af65c009714b5e4d5068fb0c19b2ba6598a7d48c9"
)
EXPECTED_CORPUS_SHA256 = (
    "4fe17f4286eb1a713a3d41a95b99260ef470ba32cadf33c2267dfc4dbaada427"
)

ACTIONS = ("aucune", "révision", "exclusion")
TIER_ORDER = ("STRONG", "MIXED", "WEAK_BUT_STRUCTURALLY_VALID")
DISPOSITIONS = (
    "PASS_STRICT",
    "PASS_WEAK_WITH_TIE_REVIEW",
    "REVISE_ANCHORS",
    "OWNER_DECISION_REQUIRED",
    "NON_EVALUABLE",
    "STRUCTURAL_ANCHOR_DEFECT",
)

_HUMAN_ORDINAL_RANK = {
    "TRES_SATISFAISANT": 4,
    "SATISFAISANT": 3,
    "FRAGILE": 2,
    "INSUFFISANT": 1,
}
_ITEM_BLOCK = re.compile(
    r"(?ms)^## (HPV2-\d{3})\s*(.*?)(?=^## (?:HPV2-\d{3}|Synthèse)|\Z)"
)


class V2HumanPrevalidationErrorCode(StrEnum):
    PREVALIDATION_INCOMPLETE = "PREVALIDATION_INCOMPLETE"
    PREVALIDATION_INVALID = "PREVALIDATION_INVALID"
    PREVALIDATION_TEMPLATE_MUTATED = "PREVALIDATION_TEMPLATE_MUTATED"
    COMPLETED_PREVALIDATION_SHA256_MISMATCH = (
        "COMPLETED_PREVALIDATION_SHA256_MISMATCH"
    )
    RECONCILIATION_KEY_INVALID = "RECONCILIATION_KEY_INVALID"


class V2HumanPrevalidationError(RuntimeError):
    pass


def _fail(code: V2HumanPrevalidationErrorCode, detail: str = "") -> None:
    suffix = f":{detail}" if detail else ""
    raise V2HumanPrevalidationError(f"{code.value}{suffix}")


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


def _field(text: str, label: str) -> str:
    match = re.search(rf"(?m)^- {re.escape(label)}\s*:\s*(.*)$", text)
    if match is None:
        return ""
    return match.group(1).strip().strip("`").strip()


def _checked_choice(line: str, choices: tuple[str, ...]) -> str | None:
    selected: list[str] = []
    for choice in choices:
        match = re.search(
            rf"\[\s*([xX]?)\s*\]\s*{re.escape(choice)}",
            line,
        )
        if match is None:
            return None
        if match.group(1).casefold() == "x":
            selected.append(choice)
    return selected[0] if len(selected) == 1 else None


def _item_static_prefix(block: str) -> str:
    normalized = block.replace("\r\n", "\n").replace("\r", "\n")
    prefix = normalized.split("- Structure valide :", maxsplit=1)[0]
    return "\n".join(line.strip() for line in prefix.splitlines() if line.strip())


def _normalize_human_label(value: str) -> str:
    return value.strip().strip("`").upper()


def classify_exposure(declaration: str) -> str:
    normalized = " ".join(declaration.casefold().split())
    if not normalized:
        return "UNDECLARED"
    if (
        "corpus v1" in normalized
        and "aucune clé" in normalized
        and "aucun résultat fournisseur v2" in normalized
    ):
        return "V1_DIAGNOSTIC_EXPOSED_V2_MAPPING_AND_RESULTS_BLIND"
    return "UNCLASSIFIED_DECLARED_EXPOSURE"


def _parse_completed_prevalidation(
    packet_text: str,
    review_text: str,
) -> dict[str, object]:
    if _field(review_text, "REVIEW_STATUS") != "COMPLETED":
        _fail(V2HumanPrevalidationErrorCode.PREVALIDATION_INCOMPLETE, "REVIEW_STATUS")

    packet_blocks = {
        match.group(1): match.group(2) for match in _ITEM_BLOCK.finditer(packet_text)
    }
    matches = tuple(_ITEM_BLOCK.finditer(review_text))
    ids = tuple(match.group(1) for match in matches)
    expected_ids = tuple(f"HPV2-{index:03d}" for index in range(1, 25))
    if len(ids) != 24 or len(set(ids)) != 24 or ids != expected_ids:
        _fail(
            V2HumanPrevalidationErrorCode.PREVALIDATION_INVALID,
            "REVIEW_ITEM_IDS",
        )
    if tuple(packet_blocks) != expected_ids:
        _fail(
            V2HumanPrevalidationErrorCode.PREVALIDATION_TEMPLATE_MUTATED,
            "SOURCE_ITEM_IDS",
        )

    items: list[dict[str, object]] = []
    for match in matches:
        review_id = match.group(1)
        body = match.group(2)
        if _item_static_prefix(body) != _item_static_prefix(packet_blocks[review_id]):
            _fail(
                V2HumanPrevalidationErrorCode.PREVALIDATION_TEMPLATE_MUTATED,
                review_id,
            )

        structure_line = re.search(r"(?m)^- Structure valide\s*:.*$", body)
        action_line = re.search(r"(?m)^- Action demandée\s*:.*$", body)
        if structure_line is None or action_line is None:
            _fail(
                V2HumanPrevalidationErrorCode.PREVALIDATION_INCOMPLETE,
                review_id,
            )
        structure = _checked_choice(structure_line.group(0), ("oui", "non"))
        action = _checked_choice(action_line.group(0), ACTIONS)
        if structure is None or action is None:
            _fail(
                V2HumanPrevalidationErrorCode.PREVALIDATION_INCOMPLETE,
                review_id,
            )

        criterion_matches = tuple(
            re.finditer(
                r"(?m)^- Appréciation humaine — `([^`]+)`\s*:\s*(\S.*?)\s*$",
                body,
            )
        )
        if len(criterion_matches) != 2:
            _fail(
                V2HumanPrevalidationErrorCode.PREVALIDATION_INCOMPLETE,
                f"{review_id}:CRITERIA",
            )
        criteria = {
            item.group(1): _normalize_human_label(item.group(2))
            for item in criterion_matches
        }
        if len(criteria) != 2 or any(value not in HUMAN_LABELS for value in criteria.values()):
            _fail(
                V2HumanPrevalidationErrorCode.PREVALIDATION_INVALID,
                f"{review_id}:LABEL",
            )

        expected_criteria_match = re.search(
            r"(?m)^- Critères\s*:\s*`([^`]+)` ; `([^`]+)`\s*$",
            body,
        )
        if expected_criteria_match is None:
            _fail(
                V2HumanPrevalidationErrorCode.PREVALIDATION_TEMPLATE_MUTATED,
                review_id,
            )
        if set(criteria) != set(expected_criteria_match.groups()):
            _fail(
                V2HumanPrevalidationErrorCode.PREVALIDATION_INVALID,
                f"{review_id}:CRITERIA",
            )

        items.append(
            {
                "review_item_id": review_id,
                "structure_valid": structure == "oui",
                "criteria": criteria,
                "action": action,
            }
        )

    synthesis = review_text.split("## Synthèse et signatures", maxsplit=1)
    if len(synthesis) != 2:
        _fail(
            V2HumanPrevalidationErrorCode.PREVALIDATION_INCOMPLETE,
            "SYNTHESIS",
        )
    synthesis_text = synthesis[1]
    reviewed_line = re.search(
        r"(?m)^- Vingt-quatre items revus\s*:.*$",
        synthesis_text,
    )
    opinion_line = re.search(r"(?m)^- Avis\s*:.*$", synthesis_text)
    if reviewed_line is None or _checked_choice(
        reviewed_line.group(0),
        ("oui", "non"),
    ) != "oui":
        _fail(
            V2HumanPrevalidationErrorCode.PREVALIDATION_INCOMPLETE,
            "SYNTHESIS_REVIEWED",
        )
    if opinion_line is None:
        _fail(
            V2HumanPrevalidationErrorCode.PREVALIDATION_INCOMPLETE,
            "SYNTHESIS_OPINION",
        )
    opinion = _checked_choice(
        opinion_line.group(0),
        ("utilisable", "révisions requises", "inconclusif"),
    )
    limits = _field(synthesis_text, "Limites de la revue")
    if opinion is None or not limits:
        _fail(
            V2HumanPrevalidationErrorCode.PREVALIDATION_INCOMPLETE,
            "SYNTHESIS",
        )

    header = review_text.split("## Gate pré-déclarée", maxsplit=1)[0]
    reviewer_code = _field(header, "Relecteur ou relectrice")
    synthesis_reviewer = _field(synthesis_text, "Relecteur ou relectrice")
    if (
        re.fullmatch(r"[A-Z][A-Z0-9_]{2,63}", reviewer_code) is None
        or synthesis_reviewer != reviewer_code
    ):
        _fail(
            V2HumanPrevalidationErrorCode.PREVALIDATION_INVALID,
            "REVIEWER_CODE",
        )
    review_date = _field(header, "Date")
    try:
        date.fromisoformat(review_date)
    except ValueError:
        _fail(
            V2HumanPrevalidationErrorCode.PREVALIDATION_INVALID,
            "REVIEW_DATE",
        )
    closure_date = _field(synthesis_text, "Date de clôture")
    if not closure_date:
        _fail(
            V2HumanPrevalidationErrorCode.PREVALIDATION_INCOMPLETE,
            "CLOSURE_DATE",
        )

    corpus_version = _field(header, "Corpus")
    corpus_checksum = _field(header, "Checksum corpus")
    if (
        corpus_version != PEDAGOGICAL_CALIBRATION_CORPUS_V2_VERSION
        or corpus_checksum != EXPECTED_CORPUS_SHA256
        or v2_calibration_corpus_sha256() != EXPECTED_CORPUS_SHA256
    ):
        _fail(V2HumanPrevalidationErrorCode.PREVALIDATION_INVALID, "CORPUS")
    grid_version = _field(header, "Version de la grille")
    if grid_version != "human-prevalidation-v2":
        _fail(
            V2HumanPrevalidationErrorCode.PREVALIDATION_INVALID,
            "GRID_VERSION",
        )
    exposure_declaration = _field(
        header,
        "Exposition préalable aux résultats machine",
    )
    if not exposure_declaration:
        _fail(
            V2HumanPrevalidationErrorCode.PREVALIDATION_INCOMPLETE,
            "EXPOSURE",
        )
    if (
        "cal.v2.scn-" in review_text
        or re.search(r"\b(?:STRONG|MIXED|WEAK_BUT_STRUCTURALLY_VALID)\b", review_text)
    ):
        _fail(
            V2HumanPrevalidationErrorCode.PREVALIDATION_INVALID,
            "BLINDNESS_MARKER",
        )

    return {
        "review_status": "COMPLETED",
        "reviewer_code": reviewer_code,
        "review_date": review_date,
        "closure_date_declared": closure_date,
        "grid_version": grid_version,
        "exposure_declaration": exposure_declaration,
        "exposure_class": classify_exposure(exposure_declaration),
        "global_opinion": opinion.replace(" ", "_").upper(),
        "items": items,
    }


def _load_and_validate_prevalidation(
    root: Path,
    *,
    expected_completed_sha256: str,
) -> tuple[dict[str, object], dict[str, str]]:
    packet_path = root / PACKET_RELATIVE_PATH
    review_path = root / COMPLETED_PREVALIDATION_RELATIVE_PATH
    try:
        packet_bytes = packet_path.read_bytes()
        review_bytes = review_path.read_bytes()
    except OSError:
        _fail(
            V2HumanPrevalidationErrorCode.PREVALIDATION_INCOMPLETE,
            "MISSING_FILE",
        )
    packet_sha256 = _sha256(packet_bytes)
    completed_sha256 = _sha256(review_bytes)
    if packet_sha256 != EXPECTED_PACKET_SHA256:
        _fail(
            V2HumanPrevalidationErrorCode.PREVALIDATION_TEMPLATE_MUTATED,
            "PACKET_SHA256",
        )
    if completed_sha256 != expected_completed_sha256:
        _fail(
            V2HumanPrevalidationErrorCode.COMPLETED_PREVALIDATION_SHA256_MISMATCH,
            completed_sha256,
        )
    parsed = _parse_completed_prevalidation(
        packet_bytes.decode("utf-8"),
        review_bytes.decode("utf-8"),
    )
    return parsed, {
        "packet_sha256": packet_sha256,
        "completed_prevalidation_sha256": completed_sha256,
    }


def _default_key_loader(path: Path) -> Mapping[str, object]:
    return cast(Mapping[str, object], json.loads(path.read_text(encoding="utf-8")))


def _validate_key(key: Mapping[str, object]) -> tuple[dict[str, object], ...]:
    expected_key = build_reconciliation_key()
    if _canonical_sha256(key) != _canonical_sha256(expected_key):
        _fail(
            V2HumanPrevalidationErrorCode.RECONCILIATION_KEY_INVALID,
            "CANONICAL_CONTENT",
        )
    raw_items = key.get("items")
    if not isinstance(raw_items, list) or len(raw_items) != 24:
        _fail(
            V2HumanPrevalidationErrorCode.RECONCILIATION_KEY_INVALID,
            "ITEM_COUNT",
        )
    items = tuple(cast(dict[str, object], item) for item in raw_items)
    review_ids = tuple(cast(str, item.get("review_item_id")) for item in items)
    anchor_ids = tuple(cast(str, item.get("anchor_id")) for item in items)
    if (
        review_ids != tuple(f"HPV2-{index:03d}" for index in range(1, 25))
        or len(set(anchor_ids)) != 24
        or set(anchor_ids) != {anchor.anchor_id for anchor in V2_CALIBRATION_ANCHORS}
    ):
        _fail(
            V2HumanPrevalidationErrorCode.RECONCILIATION_KEY_INVALID,
            "UNIQUE_MAPPING",
        )
    expected_tier = {
        expectation.anchor_id: expectation.tier.value
        for expectation in V2_ANCHOR_EXPECTATIONS
    }
    valid_item_proofs = 0
    for item in items:
        proof = item.get("reconciliation_sha256")
        projected = {
            name: value
            for name, value in item.items()
            if name != "reconciliation_sha256"
        }
        if proof != _canonical_sha256(projected):
            _fail(
                V2HumanPrevalidationErrorCode.RECONCILIATION_KEY_INVALID,
                "ITEM_SHA256",
            )
        anchor_id = cast(str, item["anchor_id"])
        if item.get("expected_tier") != expected_tier[anchor_id]:
            _fail(
                V2HumanPrevalidationErrorCode.RECONCILIATION_KEY_INVALID,
                "EXPECTED_TIER",
            )
        valid_item_proofs += 1
    if valid_item_proofs != 24:
        _fail(
            V2HumanPrevalidationErrorCode.RECONCILIATION_KEY_INVALID,
            "ITEM_SHA256_COUNT",
        )
    return items


def _human_relation(left: str, right: str) -> str:
    if left == "NON_EVALUABLE" or right == "NON_EVALUABLE":
        return "NON_EVALUABLE"
    left_rank = _HUMAN_ORDINAL_RANK[left]
    right_rank = _HUMAN_ORDINAL_RANK[right]
    if left_rank > right_rank:
        return "GT"
    if left_rank < right_rank:
        return "LT"
    return "EQ"


def _relation_text(relations: tuple[str, str]) -> str:
    if "NON_EVALUABLE" in relations:
        return "NON_EVALUABLE"
    symbols = {"GT": ">", "EQ": "=", "LT": "<"}
    return f"STRONG {symbols[relations[0]]} MIXED {symbols[relations[1]]} WEAK"


def _criterion_disposition(
    *,
    relations: tuple[str, str],
    structural_invalid_tiers: tuple[str, ...],
    requested_actions: tuple[str, ...],
) -> str:
    if structural_invalid_tiers:
        return "STRUCTURAL_ANCHOR_DEFECT"
    if "NON_EVALUABLE" in relations:
        return "NON_EVALUABLE"
    if "LT" in relations:
        return "REVISE_ANCHORS"
    if relations == ("GT", "GT"):
        return "PASS_STRICT"
    if relations == ("EQ", "EQ"):
        return "REVISE_ANCHORS"
    if all(relation in {"GT", "EQ"} for relation in relations):
        if any(action in {"révision", "exclusion"} for action in requested_actions):
            return "REVISE_ANCHORS"
        return "PASS_WEAK_WITH_TIE_REVIEW"
    return "OWNER_DECISION_REQUIRED"


def build_reconciliation_payload(
    root: Path = ROOT,
    *,
    key_loader: Callable[[Path], Mapping[str, object]] | None = None,
    expected_completed_sha256: str = EXPECTED_COMPLETED_PREVALIDATION_SHA256,
) -> dict[str, object]:
    review, proofs = _load_and_validate_prevalidation(
        root,
        expected_completed_sha256=expected_completed_sha256,
    )

    # The blind mapping is touched only after the completed-review gate passes.
    key_path = root / RECONCILIATION_KEY_RELATIVE_PATH
    loader = key_loader or _default_key_loader
    try:
        key = loader(key_path)
    except OSError:
        _fail(
            V2HumanPrevalidationErrorCode.RECONCILIATION_KEY_INVALID,
            "MISSING_KEY",
        )
    key_items = _validate_key(key)
    if key_loader is None:
        key_sha256 = _sha256(key_path.read_bytes())
        if key_sha256 != EXPECTED_RECONCILIATION_KEY_SHA256:
            _fail(
                V2HumanPrevalidationErrorCode.RECONCILIATION_KEY_INVALID,
                "FILE_SHA256",
            )
    else:
        key_sha256 = _canonical_sha256(key)

    review_items = {
        cast(str, item["review_item_id"]): item
        for item in cast(list[dict[str, object]], review["items"])
    }
    human_by_anchor = {
        cast(str, key_item["anchor_id"]): review_items[
            cast(str, key_item["review_item_id"])
        ]
        for key_item in key_items
    }
    key_by_anchor = {
        cast(str, item["anchor_id"]): item for item in key_items
    }

    label_counts_by_tier = {
        tier: {label: 0 for label in HUMAN_LABELS} for tier in TIER_ORDER
    }
    structural_invalid_by_tier = {tier: 0 for tier in TIER_ORDER}
    action_counts_by_tier = {
        tier: {action: 0 for action in ACTIONS} for tier in TIER_ORDER
    }
    for key_item in key_items:
        tier = cast(str, key_item["expected_tier"])
        human = human_by_anchor[cast(str, key_item["anchor_id"])]
        for label in cast(dict[str, str], human["criteria"]).values():
            label_counts_by_tier[tier][label] += 1
        if human["structure_valid"] is False:
            structural_invalid_by_tier[tier] += 1
        action_counts_by_tier[tier][cast(str, human["action"])] += 1

    criterion_details: list[dict[str, object]] = []
    metrics: Counter[str] = Counter()
    for ordering in V2_CRITERION_ORDERINGS:
        anchors = ordering.ordered_anchor_ids
        labels = tuple(
            cast(dict[str, str], human_by_anchor[anchor]["criteria"])[
                ordering.criterion_ref
            ]
            for anchor in anchors
        )
        relations = (
            _human_relation(labels[0], labels[1]),
            _human_relation(labels[1], labels[2]),
        )
        structural_invalid_tiers = tuple(
            tier
            for tier, anchor in zip(TIER_ORDER, anchors, strict=True)
            if human_by_anchor[anchor]["structure_valid"] is False
        )
        requested_actions = tuple(
            cast(str, human_by_anchor[anchor]["action"]) for anchor in anchors
        )
        disposition = _criterion_disposition(
            relations=relations,
            structural_invalid_tiers=structural_invalid_tiers,
            requested_actions=requested_actions,
        )
        metrics["criterion_count"] += 1
        if relations == ("GT", "GT"):
            metrics["strict_ordering_count"] += 1
        if all(relation in {"GT", "EQ"} for relation in relations):
            metrics["weak_ordering_count"] += 1
        if any(relation in {"GT", "LT"} for relation in relations):
            metrics["differentiation_perceptible_count"] += 1
        metrics["tied_pair_count"] += relations.count("EQ")
        metrics["inverted_pair_count"] += relations.count("LT")
        metrics["non_evaluable_relation_count"] += relations.count("NON_EVALUABLE")
        criterion_details.append(
            {
                "scenario_code": cast(str, key_by_anchor[anchors[0]]["scenario_code"]),
                "criterion_ref": ordering.criterion_ref,
                "human_labels_by_tier": dict(zip(TIER_ORDER, labels, strict=True)),
                "human_relations": {
                    "strong_vs_mixed": relations[0],
                    "mixed_vs_weak": relations[1],
                },
                "relation": _relation_text(relations),
                "human_ordering": {
                    "strict": relations == ("GT", "GT"),
                    "weak": all(
                        relation in {"GT", "EQ"} for relation in relations
                    ),
                    "tied_adjacent_pairs": relations.count("EQ"),
                    "inverted_adjacent_pairs": relations.count("LT"),
                    "non_evaluable_relations": relations.count("NON_EVALUABLE"),
                },
                "structural_invalid_tiers": list(structural_invalid_tiers),
                "requested_actions_by_tier": dict(
                    zip(TIER_ORDER, requested_actions, strict=True)
                ),
                "disposition": disposition,
            }
        )

    human_metrics = {
        name: metrics[name]
        for name in (
            "criterion_count",
            "strict_ordering_count",
            "weak_ordering_count",
            "tied_pair_count",
            "inverted_pair_count",
            "non_evaluable_relation_count",
            "differentiation_perceptible_count",
        )
    }
    structures_valid_count = 24 - sum(structural_invalid_by_tier.values())
    gate_pass = (
        structures_valid_count == 24
        and human_metrics["weak_ordering_count"] == 16
        and human_metrics["inverted_pair_count"] == 0
        and human_metrics["non_evaluable_relation_count"] == 0
        and human_metrics["differentiation_perceptible_count"] == 16
    )
    if gate_pass:
        human_prevalidation = "PASS"
        provider_recalibration_allowed = "READY_FOR_OWNER_AUTHORIZATION"
        next_gate = "OWNER_PROVIDER_RECALIBRATION_AUTHORIZATION_READY"
    elif (
        human_metrics["inverted_pair_count"]
        or human_metrics["non_evaluable_relation_count"]
        or structures_valid_count < 24
        or human_metrics["differentiation_perceptible_count"] < 16
    ):
        human_prevalidation = "FAIL"
        provider_recalibration_allowed = "FALSE"
        next_gate = "12.16-G2-V2-ANCHOR-REVISION_REQUIRED"
    else:
        human_prevalidation = "PARTIAL"
        provider_recalibration_allowed = "FALSE"
        next_gate = "OWNER_TIE_DISPOSITION_REQUIRED"

    disposition_counts = Counter(
        cast(str, item["disposition"]) for item in criterion_details
    )
    payload: dict[str, object] = {
        "phase": "12.16-G2-V2-HUMAN-PREVALIDATION-RECONCILIATION",
        "status": f"{human_prevalidation}_CLOSED",
        "source_proofs": {
            **proofs,
            "reconciliation_key_sha256": key_sha256,
            "corpus_version": PEDAGOGICAL_CALIBRATION_CORPUS_V2_VERSION,
            "corpus_sha256": v2_calibration_corpus_sha256(),
            "owner_checksum_override": "APPROVED",
            "superseded_completed_prevalidation_sha256": (
                SUPERSEDED_COMPLETED_PREVALIDATION_SHA256
            ),
        },
        "review_metadata": {
            "review_status": review["review_status"],
            "reviewer_code": review["reviewer_code"],
            "review_date": review["review_date"],
            "closure_date_declared": review["closure_date_declared"],
            "grid_version": review["grid_version"],
            "item_count": 24,
            "structure_decision_count": 24,
            "criterion_appreciation_count": 48,
            "action_decision_count": 24,
            "global_opinion": review["global_opinion"],
            "exposure_declaration": review["exposure_declaration"],
            "exposure_class": review["exposure_class"],
        },
        "key_integrity": {
            "item_count": 24,
            "unique_review_item_count": 24,
            "unique_anchor_count": 24,
            "per_item_sha256_valid_count": 24,
            "catalog_corpus_match": True,
            "file_sha256_match": key_loader is None,
        },
        "human_distributions": {
            "labels_by_tier": label_counts_by_tier,
            "actions_by_tier": action_counts_by_tier,
            "structural_invalid_by_tier": structural_invalid_by_tier,
        },
        "human_ordering": {
            "scale": "ORDINAL_ONLY_NO_NUMERIC_PEDAGOGICAL_SCORE",
            "metrics": human_metrics,
        },
        "criterion_dispositions": criterion_details,
        "disposition_counts": {
            disposition: disposition_counts[disposition]
            for disposition in DISPOSITIONS
        },
        "gate": {
            "structures_valid": f"{structures_valid_count}/24",
            "weak_order": f"{human_metrics['weak_ordering_count']}/16",
            "inversions": human_metrics["inverted_pair_count"],
            "non_evaluable": human_metrics["non_evaluable_relation_count"],
            "differentiation_perceptible": (
                f"{human_metrics['differentiation_perceptible_count']}/16"
            ),
            "design_target_strict": f"{human_metrics['strict_ordering_count']}/16",
            "passed": gate_pass,
        },
        "decision": {
            "HUMAN_PREVALIDATION": human_prevalidation,
            "PROVIDER_RECALIBRATION_ALLOWED": provider_recalibration_allowed,
            "RELEASE_THRESHOLD_ADOPTION": "NOT_ALLOWED",
            "PROVIDER_ROUTE_CHANGE": "NONE",
            "NEXT_GATE": next_gate,
        },
        "offline_execution": {
            "openai_calls": 0,
            "anthropic_calls": 0,
            "provider_cost_usd": "0.000000",
            "credentials_resolved": False,
            "provider_transport_constructed": False,
            "source_packet_mutated": False,
            "completed_prevalidation_mutated": False,
            "reconciliation_key_mutated": False,
            "runtime_routes_mutated": False,
        },
    }
    payload["reproducibility"] = {
        "canonical_payload_without_reproducibility_sha256": _canonical_sha256(payload),
        "deterministic_timestamps_excluded": True,
    }
    return payload


def render_result_json(root: Path = ROOT) -> str:
    return _pretty_json(build_reconciliation_payload(root))


def render_report_markdown(root: Path = ROOT) -> str:
    payload = build_reconciliation_payload(root)
    proofs = cast(dict[str, str], payload["source_proofs"])
    review = cast(dict[str, object], payload["review_metadata"])
    distributions = cast(dict[str, object], payload["human_distributions"])
    label_counts = cast(dict[str, dict[str, int]], distributions["labels_by_tier"])
    ordering = cast(dict[str, object], payload["human_ordering"])
    metrics = cast(dict[str, int], ordering["metrics"])
    gate = cast(dict[str, object], payload["gate"])
    decision = cast(dict[str, str], payload["decision"])
    disposition_counts = cast(dict[str, int], payload["disposition_counts"])
    lines = [
        "# Phase 12.16-G2 — Réconciliation de la prévalidation humaine v2",
        "",
        "## Résultat",
        "",
        f"- HUMAN_PREVALIDATION = `{decision['HUMAN_PREVALIDATION']}`.",
        f"- PROVIDER_RECALIBRATION_ALLOWED = `{decision['PROVIDER_RECALIBRATION_ALLOWED']}`.",
        "- Exécution strictement offline : `0` appel OpenAI, `0` appel Anthropic, coût `0`.",
        f"- NEXT_GATE = `{decision['NEXT_GATE']}`.",
        "",
        "## Identité et preuves",
        "",
        f"- Corpus : `{proofs['corpus_version']}` ; checksum `{proofs['corpus_sha256']}`.",
        f"- Paquet source : `{proofs['packet_sha256']}`.",
        f"- Formulaire humain corrigé : `{proofs['completed_prevalidation_sha256']}`.",
        f"- Clé locale : `{proofs['reconciliation_key_sha256']}` ; `24/24` preuves unitaires valides.",
        "- Override du checksum propriétaire : `APPROVED`; checksum antérieur superseded.",
        "",
        "## Revue humaine",
        "",
        f"- REVIEW_STATUS : `{review['review_status']}` ; items : `{review['item_count']}/24`.",
        f"- Complétude : `{review['criterion_appreciation_count']}/48` appréciations, "
        f"`{review['structure_decision_count']}/24` structures et `{review['action_decision_count']}/24` actions.",
        f"- Relecteur : `{review['reviewer_code']}` ; date : `{review['review_date']}` ; grille : `{review['grid_version']}`.",
        f"- Exposition déclarée exactement : `{review['exposure_declaration']}`",
        f"- Classe d'exposition : `{review['exposure_class']}`.",
        "",
        "## Distributions des appréciations",
        "",
        "| Tier attendu | TRES_SATISFAISANT | SATISFAISANT | FRAGILE | INSUFFISANT | NON_EVALUABLE |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for tier in TIER_ORDER:
        counts = label_counts[tier]
        lines.append(
            f"| {tier} | {counts['TRES_SATISFAISANT']} | {counts['SATISFAISANT']} | "
            f"{counts['FRAGILE']} | {counts['INSUFFISANT']} | {counts['NON_EVALUABLE']} |"
        )
    lines.extend(
        (
            "",
            "## Ordering humain",
            "",
            "Les appréciations restent ordinales; aucun score pédagogique numérique n'est dérivé.",
            "",
            f"- Ordres stricts : `{metrics['strict_ordering_count']}/16`.",
            f"- Ordres faibles : `{metrics['weak_ordering_count']}/16`.",
            f"- Égalités adjacentes : `{metrics['tied_pair_count']}`.",
            f"- Inversions adjacentes : `{metrics['inverted_pair_count']}`.",
            f"- Relations non évaluables : `{metrics['non_evaluable_relation_count']}`.",
            f"- Différenciation perceptible : `{metrics['differentiation_perceptible_count']}/16`.",
            "",
            "## Réconciliation par critère",
            "",
            "| Scénario | Critère | Strong | Mixed | Weak | Relation | Disposition |",
            "|---|---|---|---|---|---|---|",
        )
    )
    for item in cast(list[dict[str, object]], payload["criterion_dispositions"]):
        labels = cast(dict[str, str], item["human_labels_by_tier"])
        lines.append(
            f"| {item['scenario_code']} | `{item['criterion_ref']}` | "
            f"{labels['STRONG']} | {labels['MIXED']} | "
            f"{labels['WEAK_BUT_STRUCTURALLY_VALID']} | {item['relation']} | "
            f"`{item['disposition']}` |"
        )
    lines.extend(
        (
            "",
            "## Dispositions",
            "",
        )
    )
    for disposition in DISPOSITIONS:
        lines.append(f"- {disposition} : `{disposition_counts[disposition]}`.")
    lines.extend(
        (
            "",
            "## Gate prédéclarée",
            "",
            "| Condition | Observé | Résultat |",
            "|---|---:|:---:|",
            f"| Structures valides | {gate['structures_valid']} | {'PASS' if gate['structures_valid'] == '24/24' else 'FAIL'} |",
            f"| Ordres faibles | {gate['weak_order']} | {'PASS' if gate['weak_order'] == '16/16' else 'FAIL'} |",
            f"| Inversions | {gate['inversions']} | {'PASS' if gate['inversions'] == 0 else 'FAIL'} |",
            f"| Non évaluable | {gate['non_evaluable']} | {'PASS' if gate['non_evaluable'] == 0 else 'FAIL'} |",
            f"| Différenciation perceptible | {gate['differentiation_perceptible']} | {'PASS' if gate['differentiation_perceptible'] == '16/16' else 'FAIL'} |",
            f"| Objectif de conception strict | {gate['design_target_strict']} | INFORMATION |",
            "",
            "La gate humaine est `FAIL` : une inversion est observée et cinq critères restent sans différenciation perceptible. "
            "L'objectif `16/16` stricts demeure un objectif de conception du corpus, jamais un seuil produit.",
            "",
            "## Décision bornée",
            "",
            f"- HUMAN_PREVALIDATION = `{decision['HUMAN_PREVALIDATION']}`.",
            f"- PROVIDER_RECALIBRATION_ALLOWED = `{decision['PROVIDER_RECALIBRATION_ALLOWED']}`.",
            "- PROVIDER_CALLS = `0`; PROVIDER_COST = `0`.",
            "- RELEASE_THRESHOLD_ADOPTION = `NOT_ALLOWED`.",
            "- PROVIDER_ROUTE_CHANGE = `NONE`.",
            f"- NEXT_GATE = `{decision['NEXT_GATE']}`.",
            "",
            "Les commentaires libres et la clé HPV2→anchor ne sont pas reproduits. "
            "Le fichier humain, le paquet source, le corpus et la clé locale n'ont pas été modifiés.",
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
    _atomic_write(
        root / REPORT_RELATIVE_PATH,
        render_report_markdown(root).encode(),
    )
    _atomic_write(
        root / RESULT_JSON_RELATIVE_PATH,
        render_result_json(root).encode(),
    )


def main() -> None:
    write_outputs()
    payload = build_reconciliation_payload()
    metrics = cast(
        dict[str, int],
        cast(dict[str, object], payload["human_ordering"])["metrics"],
    )
    decision = cast(dict[str, str], payload["decision"])
    print(
        json.dumps(
            {
                "human_prevalidation": decision["HUMAN_PREVALIDATION"],
                "strict_order": metrics["strict_ordering_count"],
                "weak_order": metrics["weak_ordering_count"],
                "ties": metrics["tied_pair_count"],
                "inversions": metrics["inverted_pair_count"],
                "non_evaluable": metrics["non_evaluable_relation_count"],
                "provider_calls": 0,
                "next_gate": decision["NEXT_GATE"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
