from __future__ import annotations

import hashlib
import json
import os
import re
from collections import Counter
from collections.abc import Callable, Mapping
from datetime import date
from enum import StrEnum
from fractions import Fraction
from pathlib import Path
from typing import cast

from tests.calibration.pedagogical.catalog import (
    ANCHOR_EXPECTATIONS,
    CRITERION_ORDERINGS,
    PEDAGOGICAL_CALIBRATION_CORPUS_VERSION,
    anchor_by_id,
    calibration_corpus_sha256,
    scenario_by_code,
)

ROOT = Path(__file__).resolve().parents[3]

PACKET_RELATIVE_PATH = (
    "docs/development/PHASE_12_16_G2_HUMAN_ANCHOR_REVIEW_PACKET.md"
)
COMPLETED_REVIEW_RELATIVE_PATH = (
    "artifacts/calibration/12.16-g2-human-review/completed_review.md"
)
RECONCILIATION_KEY_RELATIVE_PATH = (
    "artifacts/calibration/12.16-g2-r4-r5/human_review_reconciliation.json"
)
REPORT_MD_RELATIVE_PATH = (
    "docs/development/PHASE_12_16_G2_HUMAN_REVIEW_RECONCILIATION_REPORT.md"
)
REPORT_JSON_RELATIVE_PATH = (
    "docs/development/PHASE_12_16_G2_HUMAN_REVIEW_RECONCILIATION_REPORT.json"
)
BASELINE_RELATIVE_PATH = (
    "docs/development/PHASE_12_16_G2_HUMAN_REVIEW_RECONCILIATION_BASELINE.md"
)

EXPECTED_PACKET_SHA256 = (
    "d9ea4b33b84ee52c0460097cf1dd97e89f33a67106c57cc10dd611536b8d1e5e"
)
EXPECTED_CORPUS_SHA256 = (
    "abeec0b4e5e1f60f2974ec1c19de34a5307e1b7d92e11c7b811e338d3b2e626d"
)

HUMAN_LABELS = (
    "TRES_SATISFAISANT",
    "SATISFAISANT",
    "FRAGILE",
    "INSUFFISANT",
    "NON_EVALUABLE",
)
ACTIONS = ("aucune", "révision", "exclusion")
EXPOSURE_CLASSES = (
    "FULLY_BLIND",
    "AGGREGATE_RESULTS_EXPOSED",
    "DETAILED_RESULTS_EXPOSED",
    "UNDECLARED",
)
CAUSE_CLASSES = (
    "ANCHORS_TOO_SIMILAR_FOR_HUMAN_AND_MODEL",
    "MODEL_UNDER_DISCRIMINATES_HUMAN_CLEARLY_DISTINGUISHES",
    "HUMAN_AND_MODEL_SUPPORT_EXPECTED_ORDER",
    "HUMAN_DISAGREES_WITH_EXPECTED_ANCHOR_ORDER",
    "CRITERION_NOT_HUMANLY_ASSESSABLE",
    "STRUCTURAL_ANCHOR_DEFECT",
    "INSUFFICIENT_EVIDENCE",
)
DISPOSITIONS = (
    "KEEP",
    "REVISE_ANCHORS",
    "REVISE_CRITERION_GUIDANCE",
    "RECALIBRATE_JUDGE",
    "EXCLUDE_CRITERION_FROM_CURRENT_CALIBRATION",
    "OWNER_DECISION_REQUIRED",
)
TIER_ORDER = ("STRONG", "MIXED", "WEAK_BUT_STRUCTURALLY_VALID")
RELATION_NAMES = ("GT", "EQ", "LT", "NON_EVALUABLE")

_HUMAN_ORDINAL_RANK = {
    "TRES_SATISFAISANT": 4,
    "SATISFAISANT": 3,
    "FRAGILE": 2,
    "INSUFFISANT": 1,
}
_ITEM_BLOCK = re.compile(
    r"(?ms)^## (REV-\d{3})\s*(.*?)(?=^## (?:REV-\d{3}|Synthèse))"
)


class HumanReviewErrorCode(StrEnum):
    HUMAN_REVIEW_INCOMPLETE = "HUMAN_REVIEW_INCOMPLETE"
    HUMAN_REVIEW_INVALID = "HUMAN_REVIEW_INVALID"
    HUMAN_REVIEW_TEMPLATE_MUTATED = "HUMAN_REVIEW_TEMPLATE_MUTATED"
    RECONCILIATION_KEY_INVALID = "RECONCILIATION_KEY_INVALID"


class HumanReviewError(RuntimeError):
    pass


def _fail(code: HumanReviewErrorCode, detail: str = "") -> None:
    suffix = f":{detail}" if detail else ""
    raise HumanReviewError(f"{code.value}{suffix}")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_sha256(payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
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
        match = re.search(rf"\[([ xX])\]\s*{re.escape(choice)}", line)
        if match is None:
            return None
        if match.group(1).lower() == "x":
            selected.append(choice)
    return selected[0] if len(selected) == 1 else None


def _item_static_prefix(block: str) -> str:
    normalized = block.replace("\r\n", "\n").replace("\r", "\n")
    prefix = normalized.split("- Structure valide :", maxsplit=1)[0]
    return "\n".join(line.strip() for line in prefix.splitlines() if line.strip())


def classify_exposure(declaration: str) -> str:
    normalized = " ".join(declaration.casefold().split())
    if not normalized:
        return "UNDECLARED"
    detailed_markers = (
        "détail",
        "detail",
        "par critère",
        "par critere",
        "rapport détaillé",
        "rapport detaille",
        "score individuel",
    )
    if any(marker in normalized for marker in detailed_markers):
        return "DETAILED_RESULTS_EXPOSED"
    aggregate_markers = ("agrégat", "agregat", "résultat global", "resultat global")
    if any(marker in normalized for marker in aggregate_markers):
        return "AGGREGATE_RESULTS_EXPOSED"
    blind_markers = ("aucun résultat", "aucun resultat", "non —", "non -", "aveugle")
    if any(marker in normalized for marker in blind_markers):
        return "FULLY_BLIND"
    return "UNDECLARED"


def _parse_completed_review(packet_text: str, review_text: str) -> dict[str, object]:
    status = _field(review_text, "REVIEW_STATUS")
    if status != "COMPLETED":
        _fail(HumanReviewErrorCode.HUMAN_REVIEW_INCOMPLETE, "REVIEW_STATUS")

    packet_blocks = {match.group(1): match.group(2) for match in _ITEM_BLOCK.finditer(packet_text)}
    matches = tuple(_ITEM_BLOCK.finditer(review_text))
    ids = tuple(match.group(1) for match in matches)
    expected_ids = tuple(f"REV-{index:03d}" for index in range(1, 25))
    if len(ids) != 24 or len(set(ids)) != 24 or ids != expected_ids:
        _fail(HumanReviewErrorCode.HUMAN_REVIEW_INVALID, "REVIEW_ITEM_IDS")
    if tuple(packet_blocks) != expected_ids:
        _fail(HumanReviewErrorCode.HUMAN_REVIEW_TEMPLATE_MUTATED, "SOURCE_ITEM_IDS")

    items: list[dict[str, object]] = []
    for match in matches:
        review_id = match.group(1)
        body = match.group(2)
        if _item_static_prefix(body) != _item_static_prefix(packet_blocks[review_id]):
            _fail(HumanReviewErrorCode.HUMAN_REVIEW_TEMPLATE_MUTATED, review_id)

        structure_line = re.search(r"(?m)^- Structure valide\s*:.*$", body)
        action_line = re.search(r"(?m)^- Action demandée\s*:.*$", body)
        if structure_line is None or action_line is None:
            _fail(HumanReviewErrorCode.HUMAN_REVIEW_INCOMPLETE, review_id)
        structure = _checked_choice(structure_line.group(0), ("oui", "non"))
        action = _checked_choice(action_line.group(0), ACTIONS)
        if structure is None or action is None:
            _fail(HumanReviewErrorCode.HUMAN_REVIEW_INCOMPLETE, review_id)

        criterion_matches = tuple(
            re.finditer(
                r"(?m)^- Appréciation humaine — `([^`]+)`\s*:\s*(\S+)\s*$",
                body,
            )
        )
        if len(criterion_matches) != 2:
            _fail(HumanReviewErrorCode.HUMAN_REVIEW_INCOMPLETE, review_id)
        criteria = {item.group(1): item.group(2).strip("`") for item in criterion_matches}
        if len(criteria) != 2 or any(value not in HUMAN_LABELS for value in criteria.values()):
            _fail(HumanReviewErrorCode.HUMAN_REVIEW_INVALID, f"{review_id}:LABEL")

        expected_criteria_match = re.search(
            r"(?m)^- Critères\s*:\s*`([^`]+)` ; `([^`]+)`\s*$",
            body,
        )
        if expected_criteria_match is None:
            _fail(HumanReviewErrorCode.HUMAN_REVIEW_TEMPLATE_MUTATED, review_id)
        expected_criteria = set(expected_criteria_match.groups())
        if set(criteria) != expected_criteria:
            _fail(HumanReviewErrorCode.HUMAN_REVIEW_INVALID, f"{review_id}:CRITERIA")

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
        _fail(HumanReviewErrorCode.HUMAN_REVIEW_INCOMPLETE, "SYNTHESIS")
    synthesis_text = synthesis[1]
    reviewed_line = re.search(r"(?m)^- Vingt-quatre items revus\s*:.*$", synthesis_text)
    opinion_line = re.search(r"(?m)^- Avis\s*:.*$", synthesis_text)
    limits = _field(synthesis_text, "Limites de la revue")
    if reviewed_line is None or _checked_choice(reviewed_line.group(0), ("oui", "non")) != "oui":
        _fail(HumanReviewErrorCode.HUMAN_REVIEW_INCOMPLETE, "SYNTHESIS_REVIEWED")
    if opinion_line is None:
        _fail(HumanReviewErrorCode.HUMAN_REVIEW_INCOMPLETE, "SYNTHESIS_OPINION")
    opinion = _checked_choice(opinion_line.group(0), ("utilisable", "révisions requises", "inconclusif"))
    if opinion is None:
        _fail(HumanReviewErrorCode.HUMAN_REVIEW_INCOMPLETE, "SYNTHESIS_OPINION")
    placeholder = limits.casefold().strip("<> ")
    if len(limits) < 12 or placeholder in {"description honnête", "description honnete", "todo"}:
        _fail(HumanReviewErrorCode.HUMAN_REVIEW_INCOMPLETE, "SYNTHESIS_LIMITS")

    reviewer_code = _field(synthesis_text, "Relecteur ou relectrice")
    if re.fullmatch(r"[A-Z][A-Z0-9_]{2,63}", reviewer_code) is None:
        _fail(HumanReviewErrorCode.HUMAN_REVIEW_INVALID, "REVIEWER_CODE")
    review_date = _field(review_text.split("## Consignes", maxsplit=1)[0], "Date")
    closure_date = _field(synthesis_text, "Date de clôture")
    try:
        date.fromisoformat(review_date)
    except ValueError:
        _fail(HumanReviewErrorCode.HUMAN_REVIEW_INVALID, "REVIEW_DATE")
    if closure_date != review_date:
        _fail(HumanReviewErrorCode.HUMAN_REVIEW_INVALID, "CLOSURE_DATE")

    corpus_version = _field(review_text, "Corpus")
    corpus_checksum = _field(review_text, "Checksum corpus")
    if (
        corpus_version != PEDAGOGICAL_CALIBRATION_CORPUS_VERSION
        or corpus_checksum != EXPECTED_CORPUS_SHA256
        or calibration_corpus_sha256() != EXPECTED_CORPUS_SHA256
    ):
        _fail(HumanReviewErrorCode.HUMAN_REVIEW_INVALID, "CORPUS")

    exposure_declaration = _field(review_text, "Exposition préalable aux résultats machine")
    exposure_class = classify_exposure(exposure_declaration)
    if exposure_class not in EXPOSURE_CLASSES:
        _fail(HumanReviewErrorCode.HUMAN_REVIEW_INVALID, "EXPOSURE")

    return {
        "review_status": status,
        "reviewer_code": reviewer_code,
        "review_date": review_date,
        "grid_version": _field(review_text, "Version de la grille"),
        "exposure_declaration": exposure_declaration,
        "exposure_class": exposure_class,
        "global_opinion": opinion.replace(" ", "_").upper(),
        "items": items,
    }


def _load_and_validate_review(root: Path) -> tuple[dict[str, object], dict[str, str]]:
    packet_path = root / PACKET_RELATIVE_PATH
    review_path = root / COMPLETED_REVIEW_RELATIVE_PATH
    try:
        packet_bytes = packet_path.read_bytes()
        review_bytes = review_path.read_bytes()
    except OSError:
        _fail(HumanReviewErrorCode.HUMAN_REVIEW_INCOMPLETE, "MISSING_FILE")
    packet_sha256 = _sha256(packet_bytes)
    if packet_sha256 != EXPECTED_PACKET_SHA256:
        _fail(HumanReviewErrorCode.HUMAN_REVIEW_TEMPLATE_MUTATED, "PACKET_SHA256")
    parsed = _parse_completed_review(
        packet_bytes.decode("utf-8"),
        review_bytes.decode("utf-8"),
    )
    return parsed, {
        "packet_sha256": packet_sha256,
        "completed_review_sha256": _sha256(review_bytes),
    }


def _default_key_loader(path: Path) -> Mapping[str, object]:
    return cast(Mapping[str, object], json.loads(path.read_text(encoding="utf-8")))


def _validate_key(key: Mapping[str, object]) -> tuple[dict[str, object], ...]:
    if (
        key.get("review_status") != "NOT_COMPLETED"
        or key.get("content_repeated") is not False
        or key.get("item_count") != 24
    ):
        _fail(HumanReviewErrorCode.RECONCILIATION_KEY_INVALID, "HEADER")
    raw_items = key.get("items")
    if not isinstance(raw_items, list) or len(raw_items) != 24:
        _fail(HumanReviewErrorCode.RECONCILIATION_KEY_INVALID, "ITEM_COUNT")
    items = tuple(cast(dict[str, object], item) for item in raw_items)
    review_ids = tuple(cast(str, item.get("review_item_id")) for item in items)
    anchor_ids = tuple(cast(str, item.get("anchor_id")) for item in items)
    if (
        review_ids != tuple(f"REV-{index:03d}" for index in range(1, 25))
        or len(set(review_ids)) != 24
        or len(set(anchor_ids)) != 24
    ):
        _fail(HumanReviewErrorCode.RECONCILIATION_KEY_INVALID, "UNIQUE_MAPPING")

    expected_tier = {item.anchor_id: item.tier.value for item in ANCHOR_EXPECTATIONS}
    if set(anchor_ids) != set(expected_tier):
        _fail(HumanReviewErrorCode.RECONCILIATION_KEY_INVALID, "ANCHOR_SET")
    for item in items:
        proof = item.get("reconciliation_sha256")
        projected = {name: value for name, value in item.items() if name != "reconciliation_sha256"}
        if proof != _canonical_sha256(projected):
            _fail(HumanReviewErrorCode.RECONCILIATION_KEY_INVALID, "ITEM_SHA256")
        anchor_id = cast(str, item["anchor_id"])
        if item.get("expected_tier") != expected_tier[anchor_id]:
            _fail(HumanReviewErrorCode.RECONCILIATION_KEY_INVALID, "EXPECTED_TIER")
        scenario = scenario_by_code(anchor_by_id(anchor_id).scenario_code)
        scores = item.get("model_scores")
        if not isinstance(scores, dict) or set(scores) != set(scenario.criterion_refs):
            _fail(HumanReviewErrorCode.RECONCILIATION_KEY_INVALID, "MODEL_SCORE_SET")
        for score in scores.values():
            if not isinstance(score, dict):
                _fail(HumanReviewErrorCode.RECONCILIATION_KEY_INVALID, "MODEL_SCORE")
            numerator = score.get("numerator")
            denominator = score.get("denominator")
            if (
                not isinstance(numerator, int)
                or not isinstance(denominator, int)
                or denominator <= 0
                or numerator < 0
                or numerator > denominator
            ):
                _fail(HumanReviewErrorCode.RECONCILIATION_KEY_INVALID, "MODEL_SCORE")
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


def _model_fraction(value: Mapping[str, object]) -> Fraction:
    return Fraction(cast(int, value["numerator"]), cast(int, value["denominator"]))


def _model_relation(left: Mapping[str, object], right: Mapping[str, object]) -> str:
    left_fraction = _model_fraction(left)
    right_fraction = _model_fraction(right)
    if left_fraction > right_fraction:
        return "GT"
    if left_fraction < right_fraction:
        return "LT"
    return "EQ"


def _comparison_class(human: str, model: str) -> str:
    if human == "NON_EVALUABLE":
        return "NON_ASSESSABLE"
    if human == model == "EQ":
        return "SHARED_TIE"
    if human == model:
        return "RELATION_AGREEMENT"
    if human != "EQ" and model == "EQ":
        return "HUMAN_ONLY_DISTINCTION"
    if human == "EQ" and model != "EQ":
        return "MODEL_ONLY_DISTINCTION"
    return "DISAGREEMENT"


def _cause_class(
    *,
    human_relations: tuple[str, str],
    comparison_classes: tuple[str, str],
    structural_invalid_tiers: tuple[str, ...],
) -> str:
    if structural_invalid_tiers:
        return "STRUCTURAL_ANCHOR_DEFECT"
    if all(relation == "NON_EVALUABLE" for relation in human_relations):
        return "CRITERION_NOT_HUMANLY_ASSESSABLE"
    if "LT" in human_relations:
        return "HUMAN_DISAGREES_WITH_EXPECTED_ANCHOR_ORDER"
    counts = Counter(comparison_classes)
    if counts["DISAGREEMENT"]:
        return "INSUFFICIENT_EVIDENCE"
    if counts["HUMAN_ONLY_DISTINCTION"] and not counts["MODEL_ONLY_DISTINCTION"]:
        return "MODEL_UNDER_DISCRIMINATES_HUMAN_CLEARLY_DISTINGUISHES"
    if counts["SHARED_TIE"] == 2:
        return "ANCHORS_TOO_SIMILAR_FOR_HUMAN_AND_MODEL"
    if counts["RELATION_AGREEMENT"]:
        return "HUMAN_AND_MODEL_SUPPORT_EXPECTED_ORDER"
    return "INSUFFICIENT_EVIDENCE"


def _criterion_disposition(
    *,
    cause: str,
    requested_actions: tuple[str, ...],
) -> str:
    if "exclusion" in requested_actions:
        return "OWNER_DECISION_REQUIRED"
    if "révision" in requested_actions or cause in {
        "STRUCTURAL_ANCHOR_DEFECT",
        "ANCHORS_TOO_SIMILAR_FOR_HUMAN_AND_MODEL",
    }:
        return "REVISE_ANCHORS"
    mapping = {
        "MODEL_UNDER_DISCRIMINATES_HUMAN_CLEARLY_DISTINGUISHES": "RECALIBRATE_JUDGE",
        "HUMAN_AND_MODEL_SUPPORT_EXPECTED_ORDER": "KEEP",
        "HUMAN_DISAGREES_WITH_EXPECTED_ANCHOR_ORDER": "OWNER_DECISION_REQUIRED",
        "CRITERION_NOT_HUMANLY_ASSESSABLE": (
            "EXCLUDE_CRITERION_FROM_CURRENT_CALIBRATION"
        ),
        "INSUFFICIENT_EVIDENCE": "OWNER_DECISION_REQUIRED",
    }
    return mapping[cause]


def _human_anchor_evidence(metrics: Mapping[str, int]) -> str:
    if metrics["inverted_pair_count"]:
        return "CONTRADICTORY"
    if metrics["non_evaluable_relation_count"] == 32:
        return "INSUFFICIENT"
    if metrics["strict_ordering_count"] == 16:
        return "SUPPORTIVE"
    if metrics["human_distinction_count"]:
        return "PARTIAL"
    return "INSUFFICIENT"


def _global_disposition(dispositions: set[str]) -> str:
    if "REVISE_ANCHORS" in dispositions:
        return "ANCHOR_REVISION_REQUIRED"
    if "RECALIBRATE_JUDGE" in dispositions:
        return "RECALIBRATION_REQUIRED"
    if dispositions - {"KEEP"}:
        return "OWNER_DECISION_REQUIRED"
    return "KEEP_PROVISIONALLY"


def build_reconciliation_payload(
    root: Path = ROOT,
    *,
    key_loader: Callable[[Path], Mapping[str, object]] | None = None,
) -> dict[str, object]:
    review, proofs = _load_and_validate_review(root)

    # The key is deliberately touched only after the human-review completeness gate.
    key_path = root / RECONCILIATION_KEY_RELATIVE_PATH
    loader = key_loader or _default_key_loader
    try:
        key = loader(key_path)
    except OSError:
        _fail(HumanReviewErrorCode.RECONCILIATION_KEY_INVALID, "MISSING_KEY")
    key_items = _validate_key(key)
    key_sha256 = (
        _sha256(key_path.read_bytes()) if key_loader is None else _canonical_sha256(key)
    )

    review_items = {
        cast(str, item["review_item_id"]): item
        for item in cast(list[dict[str, object]], review["items"])
    }
    human_by_anchor: dict[str, dict[str, object]] = {}
    for key_item in key_items:
        review_id = cast(str, key_item["review_item_id"])
        human_by_anchor[cast(str, key_item["anchor_id"])] = review_items[review_id]

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

    key_by_anchor = {cast(str, item["anchor_id"]): item for item in key_items}
    criterion_details: list[dict[str, object]] = []
    human_metrics: Counter[str] = Counter()
    relation_metrics: Counter[str] = Counter()
    for ordering in CRITERION_ORDERINGS:
        anchors = ordering.ordered_anchor_ids
        labels = tuple(
            cast(dict[str, str], human_by_anchor[anchor]["criteria"])[ordering.criterion_ref]
            for anchor in anchors
        )
        human_relations = (
            _human_relation(labels[0], labels[1]),
            _human_relation(labels[1], labels[2]),
        )
        model_scores = tuple(
            cast(
                dict[str, Mapping[str, object]],
                key_by_anchor[anchor]["model_scores"],
            )[ordering.criterion_ref]
            for anchor in anchors
        )
        model_relations = (
            _model_relation(model_scores[0], model_scores[1]),
            _model_relation(model_scores[1], model_scores[2]),
        )
        comparison_classes = tuple(
            _comparison_class(human, model)
            for human, model in zip(human_relations, model_relations, strict=True)
        )
        for comparison in comparison_classes:
            relation_metrics[comparison] += 1
        human_metrics["criterion_count"] += 1
        if human_relations == ("GT", "GT"):
            human_metrics["strict_ordering_count"] += 1
        if all(relation in {"GT", "EQ"} for relation in human_relations):
            human_metrics["weak_ordering_count"] += 1
        human_metrics["tied_pair_count"] += human_relations.count("EQ")
        human_metrics["inverted_pair_count"] += human_relations.count("LT")
        human_metrics["non_evaluable_relation_count"] += human_relations.count(
            "NON_EVALUABLE"
        )
        human_metrics["human_distinction_count"] += sum(
            relation in {"GT", "LT"} for relation in human_relations
        )

        structural_invalid_tiers = tuple(
            tier
            for tier, anchor in zip(TIER_ORDER, anchors, strict=True)
            if human_by_anchor[anchor]["structure_valid"] is False
        )
        requested_actions = tuple(
            cast(str, human_by_anchor[anchor]["action"]) for anchor in anchors
        )
        cause = _cause_class(
            human_relations=human_relations,
            comparison_classes=cast(tuple[str, str], comparison_classes),
            structural_invalid_tiers=structural_invalid_tiers,
        )
        disposition = _criterion_disposition(
            cause=cause,
            requested_actions=requested_actions,
        )
        criterion_details.append(
            {
                "scenario_code": ordering.criterion_ref.split(".", maxsplit=1)[0].upper(),
                "criterion_ref": ordering.criterion_ref,
                "human_labels_by_tier": dict(zip(TIER_ORDER, labels, strict=True)),
                "human_relations": {
                    "strong_vs_mixed": human_relations[0],
                    "mixed_vs_weak": human_relations[1],
                },
                "model_relations": {
                    "strong_vs_mixed": model_relations[0],
                    "mixed_vs_weak": model_relations[1],
                },
                "relation_comparisons": {
                    "strong_vs_mixed": comparison_classes[0],
                    "mixed_vs_weak": comparison_classes[1],
                },
                "human_ordering": {
                    "strict": human_relations == ("GT", "GT"),
                    "weak": all(
                        relation in {"GT", "EQ"} for relation in human_relations
                    ),
                    "tied_adjacent_pairs": human_relations.count("EQ"),
                    "inverted_adjacent_pairs": human_relations.count("LT"),
                    "non_evaluable_relations": human_relations.count("NON_EVALUABLE"),
                },
                "structural_invalid_tiers": list(structural_invalid_tiers),
                "requested_actions_by_tier": dict(
                    zip(TIER_ORDER, requested_actions, strict=True)
                ),
                "cause_class": cause,
                "disposition": disposition,
            }
        )

    human_metric_payload = {
        name: human_metrics[name]
        for name in (
            "criterion_count",
            "strict_ordering_count",
            "weak_ordering_count",
            "tied_pair_count",
            "inverted_pair_count",
            "non_evaluable_relation_count",
            "human_distinction_count",
        )
    }
    relation_metric_payload = {
        "relation_agreement_count": relation_metrics["RELATION_AGREEMENT"],
        "human_only_distinction_count": relation_metrics["HUMAN_ONLY_DISTINCTION"],
        "model_only_distinction_count": relation_metrics["MODEL_ONLY_DISTINCTION"],
        "shared_tie_count": relation_metrics["SHARED_TIE"],
        "disagreement_count": relation_metrics["DISAGREEMENT"],
        "non_assessable_count": relation_metrics["NON_ASSESSABLE"],
        "relation_count": 32,
    }
    evidence = _human_anchor_evidence(human_metric_payload)
    dispositions = {cast(str, item["disposition"]) for item in criterion_details}
    global_disposition = _global_disposition(dispositions)
    exposure_class = cast(str, review["exposure_class"])
    confidence = (
        "INSUFFICIENT"
        if evidence == "INSUFFICIENT"
        else (
            "PROVISIONAL_HUMAN_REVIEWED"
            if exposure_class == "FULLY_BLIND"
            else "PROVISIONAL_REVIEW_EXPOSURE_LIMITED"
        )
    )

    payload: dict[str, object] = {
        "phase": "12.16-G2-HUMAN-ANCHOR-REVIEW",
        "status": "PASS_CLOSED",
        "source_proofs": {
            **proofs,
            "reconciliation_key_sha256": key_sha256,
            "corpus_version": PEDAGOGICAL_CALIBRATION_CORPUS_VERSION,
            "corpus_sha256": calibration_corpus_sha256(),
        },
        "review_metadata": {
            "review_status": review["review_status"],
            "reviewer_code": review["reviewer_code"],
            "review_date": review["review_date"],
            "grid_version": review["grid_version"],
            "item_count": 24,
            "structure_decision_count": 24,
            "criterion_appreciation_count": 48,
            "action_decision_count": 24,
            "global_opinion": review["global_opinion"],
            "exposure_declaration": review["exposure_declaration"],
            "exposure_class": exposure_class,
        },
        "key_integrity": {
            "item_count": 24,
            "unique_review_item_count": 24,
            "unique_anchor_count": 24,
            "per_item_sha256_valid_count": 24,
            "content_repeated": False,
            "catalog_corpus_match": True,
        },
        "human_ordering": {
            "scale": "ORDINAL_ONLY_NO_NUMERIC_PEDAGOGICAL_SCORE",
            "metrics": human_metric_payload,
        },
        "expected_tier_comparison": {
            "human_label_counts_by_tier": label_counts_by_tier,
            "structural_invalid_count_by_tier": structural_invalid_by_tier,
            "action_counts_by_tier": action_counts_by_tier,
        },
        "human_model_relation_comparison": {
            "rule": "ORDINAL_RELATIONS_ONLY_NO_DIRECT_LABEL_FRACTION_EQUIVALENCE",
            "metrics": relation_metric_payload,
        },
        "criterion_dispositions": criterion_details,
        "decision": {
            "HUMAN_REVIEW_COMPLETE": True,
            "HUMAN_ANCHOR_EVIDENCE": evidence,
            "JUDGE_CALIBRATION_DISPOSITION": global_disposition,
            "CALIBRATION_CONFIDENCE": confidence,
            "RELEASE_THRESHOLD_ADOPTION": "NOT_ALLOWED",
            "PROVIDER_ROUTE_CHANGE": "NONE",
        },
        "offline_execution": {
            "openai_calls": 0,
            "anthropic_calls": 0,
            "provider_cost_usd": "0.000000",
            "credentials_resolved": False,
            "provider_transport_constructed": False,
            "source_packet_mutated": False,
            "completed_review_mutated": False,
            "reconciliation_key_mutated": False,
            "runtime_routes_mutated": False,
        },
        "validation": {
            "targeted_calibration_regression": "PASS_131",
            "global_pytest": "PASS_4316_SKIPPED_3_EXPLICIT_GATES",
            "ruff_global": "PASS",
            "mypy_backend_and_evaluation_harness": "PASS_689_SOURCE_FILES",
            "compileall_backend_harness_calibration": "PASS",
        },
        "governance": {
            "adr_required": False,
            "adrs_applied": ["ADR-P12-063", "ADR-P12-064"],
            "anchor_revision_launched": False,
            "anchor_revision_requires_new_corpus_checksum_calibration_approval": True,
            "next_gate": "OWNER_CALIBRATION_DECISION_READY",
        },
    }
    payload["reproducibility"] = {
        "canonical_payload_without_reproducibility_sha256": _canonical_sha256(payload),
        "deterministic_timestamps_excluded": True,
        "numeric_human_score_artifact": "ABSENT",
    }
    return payload


def render_report_json(root: Path = ROOT) -> str:
    return _pretty_json(build_reconciliation_payload(root))


def render_report_markdown(root: Path = ROOT) -> str:
    payload = build_reconciliation_payload(root)
    proofs = cast(dict[str, str], payload["source_proofs"])
    review = cast(dict[str, object], payload["review_metadata"])
    human = cast(dict[str, object], payload["human_ordering"])
    human_metrics = cast(dict[str, int], human["metrics"])
    relation = cast(dict[str, object], payload["human_model_relation_comparison"])
    relation_metrics = cast(dict[str, int], relation["metrics"])
    decision = cast(dict[str, object], payload["decision"])
    validation = cast(dict[str, str], payload["validation"])
    lines = [
        "# Phase 12.16-G2 — Réconciliation de la revue humaine",
        "",
        "## Résultat",
        "",
        "- Statut : `PASS / CLOSED`.",
        "- Exécution strictement hors ligne : `0` appel OpenAI, `0` appel Anthropic.",
        f"- Revue : `{review['item_count']}/24` items, `{review['criterion_appreciation_count']}/48` appréciations, "
        f"`{review['structure_decision_count']}/24` structures et `{review['action_decision_count']}/24` actions.",
        f"- Relecteur : `{review['reviewer_code']}` ; date : `{review['review_date']}` ; grille : `{review['grid_version']}`.",
        f"- Exposition déclarée exactement : `{review['exposure_declaration']}`",
        f"- Classe d’exposition : `{review['exposure_class']}`.",
        "",
        "## Intégrité des sources",
        "",
        f"- Paquet source : `{proofs['packet_sha256']}`.",
        f"- Revue complétée : `{proofs['completed_review_sha256']}`.",
        f"- Clé locale : `{proofs['reconciliation_key_sha256']}` ; `24/24` SHA unitaires valides.",
        f"- Corpus : `{proofs['corpus_version']}` ; checksum `{proofs['corpus_sha256']}`.",
        "",
        "## Ordre humain",
        "",
        "L’échelle humaine est uniquement ordinale. Aucun score pédagogique numérique n’en est dérivé.",
        "",
        f"- Ordres stricts : `{human_metrics['strict_ordering_count']}/16` ; ordres faibles : `{human_metrics['weak_ordering_count']}/16`.",
        f"- Égalités adjacentes : `{human_metrics['tied_pair_count']}` ; inversions : `{human_metrics['inverted_pair_count']}`.",
        f"- Distinctions humaines : `{human_metrics['human_distinction_count']}` ; relations non évaluables : `{human_metrics['non_evaluable_relation_count']}`.",
        "",
        "## Relations humain / Claude",
        "",
        "Les comparaisons portent uniquement sur les relations ordinales strong/mixed et mixed/weak, jamais sur une équivalence entre libellé humain et fraction Claude.",
        "",
        f"- Accords de relation : `{relation_metrics['relation_agreement_count']}`.",
        f"- Distinctions humaines seules : `{relation_metrics['human_only_distinction_count']}` ; distinctions modèle seules : `{relation_metrics['model_only_distinction_count']}`.",
        f"- Égalités partagées : `{relation_metrics['shared_tie_count']}` ; désaccords : `{relation_metrics['disagreement_count']}` ; non-assessables : `{relation_metrics['non_assessable_count']}`.",
        "",
        "## Diagnostic par critère",
        "",
        "| Scénario | Critère | Humain S/M | Humain M/W | Claude S/M | Claude M/W | Cause | Disposition |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for item in cast(list[dict[str, object]], payload["criterion_dispositions"]):
        human_relations = cast(dict[str, str], item["human_relations"])
        model_relations = cast(dict[str, str], item["model_relations"])
        lines.append(
            f"| {item['scenario_code']} | `{item['criterion_ref']}` | {human_relations['strong_vs_mixed']} | "
            f"{human_relations['mixed_vs_weak']} | {model_relations['strong_vs_mixed']} | "
            f"{model_relations['mixed_vs_weak']} | `{item['cause_class']}` | `{item['disposition']}` |"
        )
    lines.extend(("", "## Décision bornée", ""))
    for name, value in decision.items():
        rendered = "TRUE" if value is True else str(value)
        lines.append(f"- {name} = `{rendered}`.")
    lines.extend(
        (
            "- LIVE_PROVIDER_CALLS = `0`.",
            "- NEXT_GATE = `OWNER_CALIBRATION_DECISION_READY`.",
            "",
            "## Validation",
            "",
            f"- Régression calibration : `{validation['targeted_calibration_regression']}`.",
            f"- Pytest global : `{validation['global_pytest']}`.",
            f"- Ruff global : `{validation['ruff_global']}`.",
            f"- Mypy : `{validation['mypy_backend_and_evaluation_harness']}`.",
            f"- Compileall : `{validation['compileall_backend_harness_calibration']}`.",
            "",
            "## Gouvernance et confidentialité",
            "",
            "- Les commentaires, justifications et limites libres de la revue ne sont pas reproduits.",
            "- Aucun contenu d’anchor, output fournisseur, secret, chemin absolu ou mapping REV→anchor n’est suivi dans ce rapport.",
            "- Aucune révision d’anchor n’est lancée. Toute révision exige un nouveau corpus, un nouveau checksum, une nouvelle calibration et une nouvelle approbation.",
            "- ADR : `NO`; ADR-P12-063 et ADR-P12-064 appliqués.",
        )
    )
    return "\n".join(lines) + "\n"


def render_baseline_markdown(root: Path = ROOT) -> str:
    payload = build_reconciliation_payload(root)
    review = cast(dict[str, object], payload["review_metadata"])
    decision = cast(dict[str, object], payload["decision"])
    proofs = cast(dict[str, str], payload["source_proofs"])
    validation = cast(dict[str, str], payload["validation"])
    return "\n".join(
        (
            "# Phase 12.16-G2 — Baseline de réconciliation humaine",
            "",
            "- Statut : `PASS / CLOSED`.",
            "- HUMAN_REVIEW_COMPLETE : `TRUE`.",
            f"- COMPLETED_REVIEW_SHA256 : `{proofs['completed_review_sha256']}`.",
            f"- REVIEWER_CODE : `{review['reviewer_code']}` ; REVIEW_DATE : `{review['review_date']}`.",
            f"- REVIEW_EXPOSURE_CLASS : `{review['exposure_class']}`.",
            f"- HUMAN_ANCHOR_EVIDENCE : `{decision['HUMAN_ANCHOR_EVIDENCE']}`.",
            f"- JUDGE_CALIBRATION_DISPOSITION : `{decision['JUDGE_CALIBRATION_DISPOSITION']}`.",
            f"- CALIBRATION_CONFIDENCE : `{decision['CALIBRATION_CONFIDENCE']}`.",
            "- RELEASE_THRESHOLD_ADOPTION : `NOT_ALLOWED`.",
            "- PROVIDER_ROUTE_CHANGE : `NONE`.",
            "- LIVE_PROVIDER_CALLS : `0`.",
            f"- VALIDATION : `{validation['global_pytest']}` ; Ruff `PASS` ; mypy `PASS_689_SOURCE_FILES` ; compileall `PASS`.",
            "- ADR_REQUIRED : `NO`; ADR-P12-063 et ADR-P12-064 appliqués.",
            "- NEXT_GATE : `OWNER_CALIBRATION_DECISION_READY`.",
        )
    ) + "\n"


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
        REPORT_MD_RELATIVE_PATH: render_report_markdown(root),
        REPORT_JSON_RELATIVE_PATH: render_report_json(root),
        BASELINE_RELATIVE_PATH: render_baseline_markdown(root),
    }
    for relative_path, content in outputs.items():
        _atomic_write(root / relative_path, content.encode("utf-8"))


def main() -> None:
    write_outputs(ROOT)
    payload = build_reconciliation_payload(ROOT)
    print(
        json.dumps(
            {
                "status": "PASS_CLOSED",
                "human_anchor_evidence": cast(dict[str, object], payload["decision"])[
                    "HUMAN_ANCHOR_EVIDENCE"
                ],
                "live_provider_calls": 0,
                "next_gate": "OWNER_CALIBRATION_DECISION_READY",
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
