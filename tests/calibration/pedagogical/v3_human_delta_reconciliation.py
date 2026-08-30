"""Deterministic, offline reconciliation of the v3 human delta review."""

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

from tests.calibration.pedagogical.anchor_corpus_v3 import (
    CARRY_FORWARD_MANIFEST,
    HUMAN_LABELS,
    PACKET_RELATIVE_PATH,
    PEDAGOGICAL_CALIBRATION_CORPUS_V3_VERSION,
    RECONCILIATION_KEY_RELATIVE_PATH,
    REMEDIATED_SCENARIOS,
    V3_ANCHOR_EXPECTATIONS,
    V3_CALIBRATION_ANCHORS,
    build_delta_reconciliation_key,
    v3_calibration_corpus_sha256,
)
from tests.calibration.pedagogical.catalog import CALIBRATION_SCENARIOS
from tests.calibration.pedagogical.v2_human_prevalidation_reconciliation import (
    EXPECTED_COMPLETED_PREVALIDATION_SHA256 as EXPECTED_V2_COMPLETED_SHA256,
)
from tests.calibration.pedagogical.v2_human_prevalidation_reconciliation import (
    EXPECTED_RECONCILIATION_KEY_SHA256 as EXPECTED_V2_KEY_SHA256,
)
from tests.calibration.pedagogical.v2_human_prevalidation_reconciliation import (
    build_reconciliation_payload as build_v2_reconciliation_payload,
)

ROOT = Path(__file__).resolve().parents[3]

COMPLETED_DELTA_PREVALIDATION_RELATIVE_PATH = (
    "artifacts/calibration/12.16-g2-anchor-corpus-v3/"
    "completed_delta_prevalidation.md"
)
RESULT_JSON_RELATIVE_PATH = (
    "artifacts/calibration/12.16-g2-anchor-corpus-v3/"
    "human_delta_prevalidation_reconciliation_result.json"
)
REPORT_RELATIVE_PATH = (
    "docs/development/"
    "PHASE_12_16_G2_V3_HUMAN_DELTA_PREVALIDATION_RECONCILIATION.md"
)

EXPECTED_COMPLETED_DELTA_PREVALIDATION_SHA256 = (
    "a9595169083488c635886d18a608320f2ea7fed6576a6aa408c0e419c3ca3e9b"
)
SUPERSEDED_COMPLETED_DELTA_PREVALIDATION_SHA256 = (
    "5b1047cfbb0cceeba30df30edfe93f592d1f4536396adf7c52cd9d591be3fadf"
)
EXPECTED_RECONCILIATION_KEY_SHA256 = (
    "afe21aab0e83e2046fd5e6a26c5f3548f75ecc702550f16b5a4b6c2d7a4c6205"
)
EXPECTED_PACKET_SHA256 = (
    "0cd536bdbdca68cead009bad9ae09a1d11c514ff0774c34fbe4f14f5ae4d6477"
)
EXPECTED_CORPUS_SHA256 = (
    "dad8e7d08934b7d64c3f22c4c5fdf1e3ca39768854359c26f681852852ffb50c"
)
EXPECTED_V2_RECONCILIATION_SHA256 = (
    "3ae6d71e47da917bcb904e5534ea4ec893d37887f4eba1b98c37c4ab4b0392fd"
)

ACTIONS = ("aucune", "révision", "exclusion")
TIER_ORDER = ("STRONG", "MIXED", "WEAK_BUT_STRUCTURALLY_VALID")
V2_CARRY_FORWARD_SCENARIOS = ("SCN-02", "SCN-05", "SCN-06")
V3_DELTA_SCENARIOS = tuple(REMEDIATED_SCENARIOS)

_HUMAN_ORDINAL_RANK = {
    "TRES_SATISFAISANT": 4,
    "SATISFAISANT": 3,
    "FRAGILE": 2,
    "INSUFFISANT": 1,
}
_ITEM_BLOCK = re.compile(
    r"(?ms)^## (HPV3D-\d{3})\s*(.*?)(?=^## (?:HPV3D-\d{3}|Synthèse)|\Z)"
)


class V3HumanDeltaErrorCode(StrEnum):
    DELTA_REVIEW_INCOMPLETE = "DELTA_REVIEW_INCOMPLETE"
    DELTA_REVIEW_INVALID = "DELTA_REVIEW_INVALID"
    DELTA_REVIEW_TEMPLATE_MUTATED = "DELTA_REVIEW_TEMPLATE_MUTATED"
    COMPLETED_DELTA_SHA256_MISMATCH = "COMPLETED_DELTA_SHA256_MISMATCH"
    RECONCILIATION_KEY_INVALID = "RECONCILIATION_KEY_INVALID"
    V2_CARRY_FORWARD_INVALID = "V2_CARRY_FORWARD_INVALID"


class V3HumanDeltaError(RuntimeError):
    pass


def _fail(code: V3HumanDeltaErrorCode, detail: str = "") -> None:
    suffix = f":{detail}" if detail else ""
    raise V3HumanDeltaError(f"{code.value}{suffix}")


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
        match = re.search(rf"\[\s*([xX]?)\s*\]\s*{re.escape(choice)}", line)
        if match is None:
            return None
        if match.group(1).casefold() == "x":
            selected.append(choice)
    return selected[0] if len(selected) == 1 else None


def _item_static_prefix(block: str) -> str:
    normalized = block.replace("\r\n", "\n").replace("\r", "\n")
    prefix = normalized.split("- Structure valide :", maxsplit=1)[0]
    return "\n".join(line.strip() for line in prefix.splitlines() if line.strip())


def classify_exposure(declaration: str) -> str:
    normalized = " ".join(declaration.casefold().split())
    if (
        "revue v2" in normalized
        and "aucun mapping hpv3d" in normalized
        and "aucun résultat fournisseur v3" in normalized
    ):
        return "V2_RESULTS_EXPOSED_V3_MAPPING_AND_RESULTS_BLIND"
    if normalized:
        return "UNCLASSIFIED_DECLARED_EXPOSURE"
    return "UNDECLARED"


def _parse_completed_delta(packet_text: str, review_text: str) -> dict[str, object]:
    if _field(review_text, "REVIEW_STATUS") != "COMPLETED":
        _fail(V3HumanDeltaErrorCode.DELTA_REVIEW_INCOMPLETE, "REVIEW_STATUS")

    packet_blocks = {
        match.group(1): match.group(2) for match in _ITEM_BLOCK.finditer(packet_text)
    }
    matches = tuple(_ITEM_BLOCK.finditer(review_text))
    ids = tuple(match.group(1) for match in matches)
    expected_ids = tuple(f"HPV3D-{index:03d}" for index in range(1, 16))
    if ids != expected_ids or len(set(ids)) != 15:
        _fail(V3HumanDeltaErrorCode.DELTA_REVIEW_INVALID, "REVIEW_ITEM_IDS")
    if tuple(packet_blocks) != expected_ids:
        _fail(
            V3HumanDeltaErrorCode.DELTA_REVIEW_TEMPLATE_MUTATED,
            "SOURCE_ITEM_IDS",
        )

    items: list[dict[str, object]] = []
    for match in matches:
        review_id = match.group(1)
        body = match.group(2)
        if _item_static_prefix(body) != _item_static_prefix(packet_blocks[review_id]):
            _fail(
                V3HumanDeltaErrorCode.DELTA_REVIEW_TEMPLATE_MUTATED,
                review_id,
            )

        structure_line = re.search(r"(?m)^- Structure valide\s*:.*$", body)
        action_line = re.search(r"(?m)^- Action demandée\s*:.*$", body)
        if structure_line is None or action_line is None:
            _fail(V3HumanDeltaErrorCode.DELTA_REVIEW_INCOMPLETE, review_id)
        structure = _checked_choice(structure_line.group(0), ("oui", "non"))
        action = _checked_choice(action_line.group(0), ACTIONS)
        if structure is None or action is None:
            _fail(V3HumanDeltaErrorCode.DELTA_REVIEW_INCOMPLETE, review_id)

        criterion_matches = tuple(
            re.finditer(
                r"(?m)^- Appréciation humaine — `([^`]+)`\s*:\s*"
                r"(TRES_SATISFAISANT|SATISFAISANT|FRAGILE|INSUFFISANT|"
                r"NON_EVALUABLE)\s*$",
                body,
            )
        )
        if len(criterion_matches) != 2:
            _fail(
                V3HumanDeltaErrorCode.DELTA_REVIEW_INCOMPLETE,
                f"{review_id}:CRITERIA",
            )
        criteria = {item.group(1): item.group(2) for item in criterion_matches}
        if len(criteria) != 2 or any(label not in HUMAN_LABELS for label in criteria.values()):
            _fail(
                V3HumanDeltaErrorCode.DELTA_REVIEW_INVALID,
                f"{review_id}:LABEL",
            )
        appreciation_lines = tuple(
            line
            for line in body.splitlines()
            if line.startswith("- Appréciation humaine ")
        )
        if len(appreciation_lines) != 2:
            _fail(
                V3HumanDeltaErrorCode.DELTA_REVIEW_INVALID,
                f"{review_id}:APPRECIATION_LINES",
            )

        expected_criteria = re.search(
            r"(?m)^- Critères\s*:\s*`([^`]+)` ; `([^`]+)`\s*$",
            body,
        )
        if expected_criteria is None or set(criteria) != set(expected_criteria.groups()):
            _fail(
                V3HumanDeltaErrorCode.DELTA_REVIEW_INVALID,
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

    synthesis_parts = review_text.split("## Synthèse et signatures", maxsplit=1)
    if len(synthesis_parts) != 2:
        _fail(V3HumanDeltaErrorCode.DELTA_REVIEW_INCOMPLETE, "SYNTHESIS")
    synthesis = synthesis_parts[1]
    reviewed_line = re.search(r"(?m)^- Quinze items revus\s*:.*$", synthesis)
    opinion_line = re.search(r"(?m)^- Avis\s*:.*$", synthesis)
    if reviewed_line is None or _checked_choice(
        reviewed_line.group(0), ("oui", "non")
    ) != "oui":
        _fail(
            V3HumanDeltaErrorCode.DELTA_REVIEW_INCOMPLETE,
            "SYNTHESIS_REVIEWED",
        )
    if opinion_line is None:
        _fail(V3HumanDeltaErrorCode.DELTA_REVIEW_INCOMPLETE, "SYNTHESIS_OPINION")
    opinion = _checked_choice(
        opinion_line.group(0),
        ("utilisable", "révisions requises", "inconclusif"),
    )
    if opinion is None:
        _fail(V3HumanDeltaErrorCode.DELTA_REVIEW_INCOMPLETE, "SYNTHESIS_OPINION")

    header = review_text.split("## Consignes", maxsplit=1)[0]
    reviewer = _field(header, "Relecteur ou relectrice")
    synthesis_reviewer = _field(synthesis, "Relecteur ou relectrice")
    if (
        re.fullmatch(r"[A-Z][A-Z0-9_]{2,63}", reviewer) is None
        or synthesis_reviewer != reviewer
    ):
        _fail(V3HumanDeltaErrorCode.DELTA_REVIEW_INVALID, "REVIEWER_CODE")
    review_date = _field(header, "Date")
    try:
        date.fromisoformat(review_date)
    except ValueError:
        _fail(V3HumanDeltaErrorCode.DELTA_REVIEW_INVALID, "REVIEW_DATE")
    responsible = _field(synthesis, "Responsable de la calibration")
    closure_date = _field(synthesis, "Date de clôture")
    if not responsible or not closure_date:
        _fail(V3HumanDeltaErrorCode.DELTA_REVIEW_INCOMPLETE, "SIGNATURES")

    if (
        _field(header, "Corpus") != PEDAGOGICAL_CALIBRATION_CORPUS_V3_VERSION
        or _field(header, "Checksum corpus") != EXPECTED_CORPUS_SHA256
        or v3_calibration_corpus_sha256() != EXPECTED_CORPUS_SHA256
    ):
        _fail(V3HumanDeltaErrorCode.DELTA_REVIEW_INVALID, "CORPUS")
    grid_version = _field(header, "Version de la grille")
    if grid_version != "human-delta-prevalidation-v3":
        _fail(V3HumanDeltaErrorCode.DELTA_REVIEW_INVALID, "GRID_VERSION")
    exposure = _field(header, "Exposition préalable")
    if not exposure:
        _fail(V3HumanDeltaErrorCode.DELTA_REVIEW_INCOMPLETE, "EXPOSURE")
    if "cal.v3.scn-" in review_text or re.search(
        r"\b(?:MIXED|WEAK_BUT_STRUCTURALLY_VALID)\b", review_text
    ):
        _fail(V3HumanDeltaErrorCode.DELTA_REVIEW_INVALID, "BLINDNESS_MARKER")

    return {
        "review_status": "COMPLETED",
        "reviewer_code": reviewer,
        "review_date": review_date,
        "closure_date_declared": closure_date,
        "responsible_code": responsible,
        "grid_version": grid_version,
        "exposure_declaration": exposure,
        "exposure_class": classify_exposure(exposure),
        "global_opinion": opinion.replace(" ", "_").upper(),
        "limits": _field(synthesis, "Limites de la revue"),
        "items": items,
    }


def _load_and_validate_delta(
    root: Path,
    *,
    expected_completed_sha256: str,
) -> tuple[dict[str, object], dict[str, str]]:
    packet_path = root / PACKET_RELATIVE_PATH
    review_path = root / COMPLETED_DELTA_PREVALIDATION_RELATIVE_PATH
    try:
        packet_bytes = packet_path.read_bytes()
        review_bytes = review_path.read_bytes()
    except OSError:
        _fail(V3HumanDeltaErrorCode.DELTA_REVIEW_INCOMPLETE, "MISSING_FILE")
    packet_sha256 = _sha256(packet_bytes)
    completed_sha256 = _sha256(review_bytes)
    if packet_sha256 != EXPECTED_PACKET_SHA256:
        _fail(
            V3HumanDeltaErrorCode.DELTA_REVIEW_TEMPLATE_MUTATED,
            "PACKET_SHA256",
        )
    if completed_sha256 != expected_completed_sha256:
        _fail(
            V3HumanDeltaErrorCode.COMPLETED_DELTA_SHA256_MISMATCH,
            completed_sha256,
        )
    parsed = _parse_completed_delta(
        packet_bytes.decode("utf-8"),
        review_bytes.decode("utf-8"),
    )
    return parsed, {
        "packet_sha256": packet_sha256,
        "completed_delta_prevalidation_sha256": completed_sha256,
    }


def _default_key_loader(path: Path) -> Mapping[str, object]:
    return cast(Mapping[str, object], json.loads(path.read_text(encoding="utf-8")))


def _validate_key(key: Mapping[str, object]) -> tuple[dict[str, object], ...]:
    expected = build_delta_reconciliation_key()
    if _canonical_sha256(key) != _canonical_sha256(expected):
        _fail(V3HumanDeltaErrorCode.RECONCILIATION_KEY_INVALID, "CANONICAL_CONTENT")
    raw_items = key.get("items")
    if not isinstance(raw_items, list) or len(raw_items) != 15:
        _fail(V3HumanDeltaErrorCode.RECONCILIATION_KEY_INVALID, "ITEM_COUNT")
    items = tuple(cast(dict[str, object], item) for item in raw_items)
    review_ids = tuple(cast(str, item.get("review_item_id")) for item in items)
    anchor_ids = tuple(cast(str, item.get("anchor_id")) for item in items)
    delta_anchor_ids = {
        anchor.anchor_id
        for anchor in V3_CALIBRATION_ANCHORS
        if anchor.scenario_code in V3_DELTA_SCENARIOS
    }
    if (
        review_ids != tuple(f"HPV3D-{index:03d}" for index in range(1, 16))
        or len(set(anchor_ids)) != 15
        or set(anchor_ids) != delta_anchor_ids
    ):
        _fail(V3HumanDeltaErrorCode.RECONCILIATION_KEY_INVALID, "UNIQUE_MAPPING")
    expected_tier = {
        item.anchor_id: item.tier.value for item in V3_ANCHOR_EXPECTATIONS
    }
    for item in items:
        projected = {
            name: value
            for name, value in item.items()
            if name != "reconciliation_sha256"
        }
        if item.get("reconciliation_sha256") != _canonical_sha256(projected):
            _fail(V3HumanDeltaErrorCode.RECONCILIATION_KEY_INVALID, "ITEM_SHA256")
        anchor_id = cast(str, item["anchor_id"])
        if item.get("expected_tier") != expected_tier[anchor_id]:
            _fail(V3HumanDeltaErrorCode.RECONCILIATION_KEY_INVALID, "EXPECTED_TIER")
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


def _trinary_relation(strong_mixed: str, mixed_weak: str) -> str:
    if "NON_EVALUABLE" in (strong_mixed, mixed_weak):
        return "NON_EVALUABLE"
    symbol = {"GT": ">", "EQ": "=", "LT": "<"}
    return f"STRONG {symbol[strong_mixed]} MIXED {symbol[mixed_weak]} WEAK"


def _build_full_anchor_evidence(
    root: Path,
    review: Mapping[str, object],
    key_items: tuple[dict[str, object], ...],
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    review_items = {
        cast(str, item["review_item_id"]): item
        for item in cast(list[dict[str, object]], review["items"])
    }
    delta_human_by_anchor = {
        cast(str, key_item["anchor_id"]): review_items[
            cast(str, key_item["review_item_id"])
        ]
        for key_item in key_items
    }
    key_by_anchor = {cast(str, item["anchor_id"]): item for item in key_items}
    tier_by_anchor = {
        item.anchor_id: item.tier.value for item in V3_ANCHOR_EXPECTATIONS
    }
    anchor_by_scenario_tier = {
        (anchor.scenario_code, tier_by_anchor[anchor.anchor_id]): anchor
        for anchor in V3_CALIBRATION_ANCHORS
    }

    v2_payload = build_v2_reconciliation_payload(root)
    v2_details = {
        cast(str, item["criterion_ref"]): item
        for item in cast(list[dict[str, object]], v2_payload["criterion_dispositions"])
    }
    manifest_by_key = {
        (item.scenario_code, item.criterion_ref, item.tier): item
        for item in CARRY_FORWARD_MANIFEST
    }

    anchors: list[dict[str, object]] = []
    carry_proofs: list[dict[str, object]] = []
    for scenario in CALIBRATION_SCENARIOS:
        scenario_code = scenario.scenario_code
        source = (
            "V3_DELTA"
            if scenario_code in V3_DELTA_SCENARIOS
            else "V2_CARRY_FORWARD"
        )
        for tier in TIER_ORDER:
            anchor = anchor_by_scenario_tier[(scenario_code, tier)]
            if source == "V3_DELTA":
                human = delta_human_by_anchor.get(anchor.anchor_id)
                key_item = key_by_anchor.get(anchor.anchor_id)
                if human is None or key_item is None:
                    _fail(
                        V3HumanDeltaErrorCode.RECONCILIATION_KEY_INVALID,
                        f"{scenario_code}:{tier}:MISSING_DELTA",
                    )
                if (
                    key_item["scenario_code"] != scenario_code
                    or key_item["expected_tier"] != tier
                    or tuple(cast(list[str], key_item["criterion_refs"]))
                    != scenario.criterion_refs
                ):
                    _fail(
                        V3HumanDeltaErrorCode.RECONCILIATION_KEY_INVALID,
                        f"{scenario_code}:{tier}:DELTA_MAPPING",
                    )
                criteria = cast(dict[str, str], human["criteria"])
                action = cast(str, human["action"])
                structure_valid = cast(bool, human["structure_valid"])
                carry_hashes: dict[str, str] | None = None
            else:
                details = [v2_details[criterion] for criterion in scenario.criterion_refs]
                criteria = {
                    criterion: cast(dict[str, str], detail["human_labels_by_tier"])[tier]
                    for criterion, detail in zip(
                        scenario.criterion_refs,
                        details,
                        strict=True,
                    )
                }
                actions = {
                    cast(dict[str, str], detail["requested_actions_by_tier"])[tier]
                    for detail in details
                }
                if len(actions) != 1:
                    _fail(
                        V3HumanDeltaErrorCode.V2_CARRY_FORWARD_INVALID,
                        f"{scenario_code}:{tier}:ACTION",
                    )
                action = actions.pop()
                structure_valid = all(
                    tier not in cast(list[str], detail["structural_invalid_tiers"])
                    for detail in details
                )
                rows = [
                    manifest_by_key[(scenario_code, criterion, tier)]
                    for criterion in scenario.criterion_refs
                ]
                if not all(
                    row.reuse_allowed
                    and row.v2_content_fingerprint == row.v3_content_fingerprint
                    for row in rows
                ):
                    _fail(
                        V3HumanDeltaErrorCode.V2_CARRY_FORWARD_INVALID,
                        f"{scenario_code}:{tier}:HASH",
                    )
                v2_hashes = {row.v2_content_fingerprint for row in rows}
                v3_hashes = {row.v3_content_fingerprint for row in rows}
                if len(v2_hashes) != 1 or len(v3_hashes) != 1:
                    _fail(
                        V3HumanDeltaErrorCode.V2_CARRY_FORWARD_INVALID,
                        f"{scenario_code}:{tier}:HASH_CARDINALITY",
                    )
                carry_hashes = {
                    "v2_content_sha256": v2_hashes.pop(),
                    "v3_content_sha256": v3_hashes.pop(),
                }
                carry_proofs.append(
                    {
                        "scenario_code": scenario_code,
                        "tier": tier,
                        **carry_hashes,
                        "byte_equivalent": True,
                    }
                )
            anchors.append(
                {
                    "scenario_code": scenario_code,
                    "tier": tier,
                    "criteria": dict(criteria),
                    "structure_valid": structure_valid,
                    "action": action,
                    "source": source,
                    "carry_hashes": carry_hashes,
                }
            )
    if len(anchors) != 24 or len(carry_proofs) != 9:
        _fail(V3HumanDeltaErrorCode.V2_CARRY_FORWARD_INVALID, "CARDINALITY")
    return anchors, carry_proofs, v2_payload


def build_reconciliation_payload(
    root: Path = ROOT,
    *,
    key_loader: Callable[[Path], Mapping[str, object]] | None = None,
    expected_completed_sha256: str = EXPECTED_COMPLETED_DELTA_PREVALIDATION_SHA256,
) -> dict[str, object]:
    review, proofs = _load_and_validate_delta(
        root,
        expected_completed_sha256=expected_completed_sha256,
    )

    key_path = root / RECONCILIATION_KEY_RELATIVE_PATH
    loader = key_loader or _default_key_loader
    try:
        key = loader(key_path)
    except OSError:
        _fail(V3HumanDeltaErrorCode.RECONCILIATION_KEY_INVALID, "MISSING_KEY")
    key_items = _validate_key(key)
    if key_loader is None:
        key_sha256 = _sha256(key_path.read_bytes())
        if key_sha256 != EXPECTED_RECONCILIATION_KEY_SHA256:
            _fail(V3HumanDeltaErrorCode.RECONCILIATION_KEY_INVALID, "FILE_SHA256")
    else:
        key_sha256 = EXPECTED_RECONCILIATION_KEY_SHA256

    anchors, carry_proofs, v2_payload = _build_full_anchor_evidence(
        root,
        review,
        key_items,
    )
    anchors_by_key = {
        (cast(str, item["scenario_code"]), cast(str, item["tier"])): item
        for item in anchors
    }

    label_counts_by_tier = {
        tier: {label: 0 for label in HUMAN_LABELS} for tier in TIER_ORDER
    }
    action_counts_by_tier = {
        tier: {action: 0 for action in ACTIONS} for tier in TIER_ORDER
    }
    structural_invalid_by_tier = {tier: 0 for tier in TIER_ORDER}
    for anchor in anchors:
        tier = cast(str, anchor["tier"])
        for label in cast(dict[str, str], anchor["criteria"]).values():
            label_counts_by_tier[tier][label] += 1
        action_counts_by_tier[tier][cast(str, anchor["action"])] += 1
        if anchor["structure_valid"] is False:
            structural_invalid_by_tier[tier] += 1

    metrics: Counter[str] = Counter()
    criterion_details: list[dict[str, object]] = []
    for scenario in CALIBRATION_SCENARIOS:
        tier_anchors = {
            tier: anchors_by_key[(scenario.scenario_code, tier)] for tier in TIER_ORDER
        }
        for criterion_ref in scenario.criterion_refs:
            labels = {
                tier: cast(dict[str, str], tier_anchors[tier]["criteria"])[criterion_ref]
                for tier in TIER_ORDER
            }
            strong_mixed = _human_relation(labels["STRONG"], labels["MIXED"])
            strong_weak = _human_relation(
                labels["STRONG"], labels["WEAK_BUT_STRUCTURALLY_VALID"]
            )
            mixed_weak = _human_relation(
                labels["MIXED"], labels["WEAK_BUT_STRUCTURALLY_VALID"]
            )
            strong_dominates_mixed = strong_mixed == "GT"
            strong_dominates_weak = strong_weak == "GT"
            primary_differentiated = (
                strong_dominates_mixed and strong_dominates_weak
            )
            strict = strong_mixed == "GT" and mixed_weak == "GT"
            weak = strong_mixed in {"GT", "EQ"} and mixed_weak in {"GT", "EQ"}
            metrics["criterion_count"] += 1
            metrics["strong_dominates_mixed_count"] += strong_dominates_mixed
            metrics["strong_dominates_weak_count"] += strong_dominates_weak
            metrics["primary_differentiation_count"] += primary_differentiated
            metrics["trinary_strict_order_count"] += strict
            metrics["trinary_weak_order_count"] += weak
            metrics["mixed_vs_weak_tie_count"] += mixed_weak == "EQ"
            metrics["mixed_vs_weak_inversion_count"] += mixed_weak == "LT"
            criterion_details.append(
                {
                    "scenario_code": scenario.scenario_code,
                    "criterion_ref": criterion_ref,
                    "human_labels_by_tier": labels,
                    "strong_dominates_mixed": strong_dominates_mixed,
                    "strong_dominates_weak": strong_dominates_weak,
                    "primary_strong_vs_non_strong_differentiated": (
                        primary_differentiated
                    ),
                    "mixed_vs_weak_relation": mixed_weak,
                    "trinary_relation": _trinary_relation(
                        strong_mixed,
                        mixed_weak,
                    ),
                    "source": cast(str, tier_anchors["STRONG"]["source"]),
                }
            )

    non_evaluable_count = sum(
        counts["NON_EVALUABLE"] for counts in label_counts_by_tier.values()
    )
    structures_valid_count = 24 - sum(structural_invalid_by_tier.values())
    gate_pass = (
        structures_valid_count == 24
        and non_evaluable_count == 0
        and metrics["strong_dominates_mixed_count"] == 16
        and metrics["strong_dominates_weak_count"] == 16
        and metrics["primary_differentiation_count"] == 16
    )

    action_conflicts: list[dict[str, str]] = []
    for anchor in anchors:
        scenario_code = cast(str, anchor["scenario_code"])
        tier = cast(str, anchor["tier"])
        action = cast(str, anchor["action"])
        if tier == "STRONG" and action != "aucune":
            action_conflicts.append(
                {
                    "scenario_code": scenario_code,
                    "tier": tier,
                    "action": action,
                    "reason": "DELIVERY_CANDIDATE_ACTION_NOT_NONE",
                }
            )
        elif tier != "STRONG" and action == "aucune":
            strong = anchors_by_key[(scenario_code, "STRONG")]
            separated = all(
                _human_relation(
                    cast(dict[str, str], strong["criteria"])[criterion],
                    cast(dict[str, str], anchor["criteria"])[criterion],
                )
                == "GT"
                for criterion in cast(dict[str, str], anchor["criteria"])
            )
            if not separated:
                action_conflicts.append(
                    {
                        "scenario_code": scenario_code,
                        "tier": tier,
                        "action": action,
                        "reason": (
                            "NEGATIVE_CONTROL_ACTION_NONE_WITHOUT_PRIMARY_SEPARATION"
                        ),
                    }
                )

    if gate_pass:
        human_delta_prevalidation = "PASS"
        provider_recalibration_allowed = "READY_FOR_OFFLINE_PLAN_ONLY"
        next_gate = "12.16-G2-V3-PROVIDER-RECALIBRATION-PLAN_READY"
    else:
        human_delta_prevalidation = "FAIL"
        provider_recalibration_allowed = "FALSE"
        next_gate = "12.16-G2-V3-ANCHOR-REVISION_REQUIRED"

    v2_proofs = cast(dict[str, str], v2_payload["source_proofs"])
    payload: dict[str, object] = {
        "phase": "12.16-G2-V3-HUMAN-DELTA-PREVALIDATION-RECONCILIATION",
        "status": f"{human_delta_prevalidation}_CLOSED",
        "source_proofs": {
            **proofs,
            "reconciliation_key_sha256": key_sha256,
            "corpus_version": PEDAGOGICAL_CALIBRATION_CORPUS_V3_VERSION,
            "corpus_sha256": v3_calibration_corpus_sha256(),
            "owner_checksum_override": "APPROVED",
            "superseded_completed_delta_prevalidation_sha256": (
                SUPERSEDED_COMPLETED_DELTA_PREVALIDATION_SHA256
            ),
            "v2_reconciliation_sha256": EXPECTED_V2_RECONCILIATION_SHA256,
            "v2_completed_prevalidation_sha256": v2_proofs[
                "completed_prevalidation_sha256"
            ],
            "v2_reconciliation_key_sha256": v2_proofs[
                "reconciliation_key_sha256"
            ],
        },
        "review_metadata": {
            "review_status": review["review_status"],
            "reviewer_code": review["reviewer_code"],
            "review_date": review["review_date"],
            "closure_date_declared": review["closure_date_declared"],
            "responsible_code": review["responsible_code"],
            "grid_version": review["grid_version"],
            "item_count": 15,
            "structure_decision_count": 15,
            "criterion_appreciation_count": 30,
            "action_decision_count": 15,
            "global_opinion": review["global_opinion"],
            "exposure_declaration": review["exposure_declaration"],
            "exposure_class": review["exposure_class"],
        },
        "key_integrity": {
            "item_count": 15,
            "unique_review_item_count": 15,
            "unique_anchor_count": 15,
            "per_item_sha256_valid_count": 15,
            "catalog_corpus_match": True,
            "file_sha256_match": key_loader is None,
        },
        "full_human_proof": {
            "scenario_count": 8,
            "criterion_count": 16,
            "anchor_count": 24,
            "label_count": 48,
            "v2_carry_forward_scenarios": list(V2_CARRY_FORWARD_SCENARIOS),
            "v3_delta_scenarios": list(V3_DELTA_SCENARIOS),
            "v2_carry_forward_anchor_count": 9,
            "v3_delta_anchor_count": 15,
            "carry_forward_proofs": carry_proofs,
        },
        "human_distributions": {
            "labels_by_tier": label_counts_by_tier,
            "actions_by_tier": action_counts_by_tier,
            "structural_invalid_by_tier": structural_invalid_by_tier,
        },
        "criterion_details": criterion_details,
        "primary_gate": {
            "structures_valid": f"{structures_valid_count}/24",
            "non_evaluable": f"{non_evaluable_count}/48",
            "strong_dominates_mixed": (
                f"{metrics['strong_dominates_mixed_count']}/16"
            ),
            "strong_dominates_weak": (
                f"{metrics['strong_dominates_weak_count']}/16"
            ),
            "strong_vs_non_strong_differentiation": (
                f"{metrics['primary_differentiation_count']}/16"
            ),
            "passed": gate_pass,
        },
        "secondary_diagnostic": {
            "trinary_strict_order_count": metrics[
                "trinary_strict_order_count"
            ],
            "trinary_weak_order_count": metrics["trinary_weak_order_count"],
            "mixed_vs_weak_tie_count": metrics["mixed_vs_weak_tie_count"],
            "mixed_vs_weak_inversion_count": metrics[
                "mixed_vs_weak_inversion_count"
            ],
            "blocking": False,
        },
        "action_alignment_diagnostic": {
            "conflicts": action_conflicts,
            "owner_followup_required": bool(action_conflicts),
            "blocking": False,
        },
        "decision": {
            "HUMAN_DELTA_PREVALIDATION": human_delta_prevalidation,
            "PROVIDER_RECALIBRATION_ALLOWED": provider_recalibration_allowed,
            "RELEASE_THRESHOLD_ADOPTION": "NOT_ALLOWED",
            "RUNTIME_ROUTE_CHANGE": "NONE",
            "NEXT_GATE": next_gate,
        },
        "offline_execution": {
            "openai_calls": 0,
            "anthropic_calls": 0,
            "provider_cost_usd": "0.000000",
            "credentials_resolved": False,
            "provider_transport_constructed": False,
            "source_packet_mutated": False,
            "completed_delta_mutated_during_reconciliation": False,
            "reconciliation_key_mutated": False,
            "runtime_routes_mutated": False,
        },
    }
    if (
        v2_proofs["completed_prevalidation_sha256"] != EXPECTED_V2_COMPLETED_SHA256
        or v2_proofs["reconciliation_key_sha256"] != EXPECTED_V2_KEY_SHA256
    ):
        _fail(V3HumanDeltaErrorCode.V2_CARRY_FORWARD_INVALID, "V2_PROOF_HASH")
    payload["reproducibility"] = {
        "canonical_payload_without_reproducibility_sha256": _canonical_sha256(
            payload
        ),
        "deterministic_timestamps_excluded": True,
    }
    return payload


def render_result_json(root: Path = ROOT) -> str:
    return _pretty_json(build_reconciliation_payload(root))


def render_report_markdown(root: Path = ROOT) -> str:
    payload = build_reconciliation_payload(root)
    proofs = cast(dict[str, str], payload["source_proofs"])
    review = cast(dict[str, object], payload["review_metadata"])
    full_proof = cast(dict[str, object], payload["full_human_proof"])
    distributions = cast(dict[str, object], payload["human_distributions"])
    labels = cast(dict[str, dict[str, int]], distributions["labels_by_tier"])
    actions = cast(dict[str, dict[str, int]], distributions["actions_by_tier"])
    gate = cast(dict[str, object], payload["primary_gate"])
    secondary = cast(dict[str, object], payload["secondary_diagnostic"])
    action_diagnostic = cast(
        dict[str, object], payload["action_alignment_diagnostic"]
    )
    decision = cast(dict[str, str], payload["decision"])
    lines = [
        "# Phase 12.16-G2 — Réconciliation de la prévalidation humaine delta v3",
        "",
        "## Résultat",
        "",
        f"- HUMAN_DELTA_PREVALIDATION = `{decision['HUMAN_DELTA_PREVALIDATION']}`.",
        f"- PROVIDER_RECALIBRATION_ALLOWED = `{decision['PROVIDER_RECALIBRATION_ALLOWED']}`.",
        "- Exécution strictement offline : `0` appel OpenAI, `0` appel Anthropic, coût `0`.",
        f"- NEXT_GATE = `{decision['NEXT_GATE']}`.",
        "",
        "## Identité et checksums",
        "",
        f"- Corpus : `{proofs['corpus_version']}` ; checksum `{proofs['corpus_sha256']}`.",
        f"- Paquet source aveugle : `{proofs['packet_sha256']}`.",
        f"- Formulaire humain delta final : `{proofs['completed_delta_prevalidation_sha256']}`.",
        f"- Clé locale : `{proofs['reconciliation_key_sha256']}` ; `15/15` preuves unitaires valides.",
        "- Override propriétaire du checksum : `APPROVED`; checksum initial superseded "
        f"`{proofs['superseded_completed_delta_prevalidation_sha256']}`.",
        f"- Rapport humain v2 préservé : `{proofs['v2_reconciliation_sha256']}`.",
        "",
        "## Revue humaine delta",
        "",
        f"- REVIEW_STATUS : `{review['review_status']}` ; items : `{review['item_count']}/15`.",
        f"- Complétude : `{review['criterion_appreciation_count']}/30` appréciations, "
        f"`{review['structure_decision_count']}/15` structures et "
        f"`{review['action_decision_count']}/15` actions.",
        f"- Relecteur : `{review['reviewer_code']}` ; date : `{review['review_date']}` ; "
        f"grille : `{review['grid_version']}`.",
        f"- Exposition déclarée exactement : `{review['exposure_declaration']}`",
        f"- Classe d'exposition : `{review['exposure_class']}`.",
        "",
        "## Preuve de carry-forward v2",
        "",
        "Les trois scénarios non remédiés utilisent exclusivement leurs preuves humaines v2. "
        "Chaque anchor conserve le même scénario, tier, structure, contexte et contenu pédagogique byte-equivalent.",
        "",
        "| Scénario | Tier | Empreinte v2 | Empreinte v3 | Byte-equivalent |",
        "|---|---|---|---|:---:|",
    ]
    for item in cast(list[dict[str, object]], full_proof["carry_forward_proofs"]):
        lines.append(
            f"| {item['scenario_code']} | {item['tier']} | "
            f"`{item['v2_content_sha256']}` | `{item['v3_content_sha256']}` | OUI |"
        )
    lines.extend(
        (
            "",
            "## Preuve humaine v3 complète",
            "",
            "- Couverture : `8 scénarios / 16 critères / 24 anchors / 48 appréciations`.",
            "- Source V2_CARRY_FORWARD : `3 scénarios / 9 anchors / 18 appréciations`.",
            "- Source V3_DELTA : `5 scénarios / 15 anchors / 30 appréciations`.",
            "- Aucun scénario remédié ne mélange une appréciation v2 et une appréciation delta v3.",
            "",
            "### Distribution des labels",
            "",
            "| Tier | TRES_SATISFAISANT | SATISFAISANT | FRAGILE | INSUFFISANT | NON_EVALUABLE |",
            "|---|---:|---:|---:|---:|---:|",
        )
    )
    for tier in TIER_ORDER:
        counts = labels[tier]
        lines.append(
            f"| {tier} | {counts['TRES_SATISFAISANT']} | "
            f"{counts['SATISFAISANT']} | {counts['FRAGILE']} | "
            f"{counts['INSUFFISANT']} | {counts['NON_EVALUABLE']} |"
        )
    lines.extend(
        (
            "",
            "### Réconciliation des 16 critères",
            "",
            "| Scénario | Critère | Strong | Mixed | Weak | Strong > Mixed | Strong > Weak | Mixed/Weak | Source humaine |",
            "|---|---|---|---|---|:---:|:---:|:---:|---|",
        )
    )
    for item in cast(list[dict[str, object]], payload["criterion_details"]):
        item_labels = cast(dict[str, str], item["human_labels_by_tier"])
        relation = {"GT": ">", "EQ": "=", "LT": "<", "NON_EVALUABLE": "NE"}[
            cast(str, item["mixed_vs_weak_relation"])
        ]
        lines.append(
            f"| {item['scenario_code']} | `{item['criterion_ref']}` | "
            f"{item_labels['STRONG']} | {item_labels['MIXED']} | "
            f"{item_labels['WEAK_BUT_STRUCTURALLY_VALID']} | "
            f"{'OUI' if item['strong_dominates_mixed'] else 'NON'} | "
            f"{'OUI' if item['strong_dominates_weak'] else 'NON'} | "
            f"{relation} | {item['source']} |"
        )
    lines.extend(
        (
            "",
            "## Gate primaire prédéclarée",
            "",
            "| Condition | Observé | Résultat |",
            "|---|---:|:---:|",
            f"| Structures valides | {gate['structures_valid']} | {'PASS' if gate['structures_valid'] == '24/24' else 'FAIL'} |",
            f"| NON_EVALUABLE | {gate['non_evaluable']} | {'PASS' if gate['non_evaluable'] == '0/48' else 'FAIL'} |",
            f"| STRONG > MIXED | {gate['strong_dominates_mixed']} | {'PASS' if gate['strong_dominates_mixed'] == '16/16' else 'FAIL'} |",
            f"| STRONG > WEAK | {gate['strong_dominates_weak']} | {'PASS' if gate['strong_dominates_weak'] == '16/16' else 'FAIL'} |",
            f"| STRONG vs non-STRONG | {gate['strong_vs_non_strong_differentiation']} | {'PASS' if gate['strong_vs_non_strong_differentiation'] == '16/16' else 'FAIL'} |",
            "",
            "La gate primaire est `FAIL` : les structures et l'évaluabilité sont complètes, "
            "mais plusieurs contrôles négatifs restent humainement indifférenciés de STRONG.",
            "",
            "## Diagnostic ternaire secondaire non bloquant",
            "",
            f"- TRINARY_STRICT_ORDER_COUNT : `{secondary['trinary_strict_order_count']}/16`.",
            f"- TRINARY_WEAK_ORDER_COUNT : `{secondary['trinary_weak_order_count']}/16`.",
            f"- MIXED_VS_WEAK_TIE_COUNT : `{secondary['mixed_vs_weak_tie_count']}`.",
            f"- MIXED_VS_WEAK_INVERSION_COUNT : `{secondary['mixed_vs_weak_inversion_count']}`.",
            "- Ces mesures sont informatives et n'ont pas modifié la gate primaire.",
            "",
            "## ACTION_ALIGNMENT_DIAGNOSTIC",
            "",
            "| Tier | aucune | révision | exclusion |",
            "|---|---:|---:|---:|",
        )
    )
    for tier in TIER_ORDER:
        counts = actions[tier]
        lines.append(
            f"| {tier} | {counts['aucune']} | {counts['révision']} | "
            f"{counts['exclusion']} |"
        )
    lines.extend(
        (
            "",
            f"- Conflits apparents action/rôle : `{len(cast(list[object], action_diagnostic['conflicts']))}`.",
            f"- OWNER_FOLLOWUP_REQUIRED = `{'TRUE' if action_diagnostic['owner_followup_required'] else 'FALSE'}`.",
            "- Les actions restent diagnostiques et n'ont pas réécrit la gate primaire.",
            "",
            "## Décision bornée",
            "",
            f"- HUMAN_DELTA_PREVALIDATION = `{decision['HUMAN_DELTA_PREVALIDATION']}`.",
            f"- PROVIDER_RECALIBRATION_ALLOWED = `{decision['PROVIDER_RECALIBRATION_ALLOWED']}`.",
            "- PROVIDER_CALLS = `0`; PROVIDER_COST = `0`.",
            "- RUNTIME_ROUTE_CHANGE = `NONE`.",
            "- RELEASE_THRESHOLD_ADOPTION = `NOT_ALLOWED`.",
            f"- NEXT_GATE = `{decision['NEXT_GATE']}`.",
            "",
            "Le fichier humain final, le paquet, les corpus v1/v2/v3, les preuves historiques "
            "et la clé locale n'ont pas été modifiés pendant la réconciliation.",
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
    _atomic_write(root / REPORT_RELATIVE_PATH, render_report_markdown(root).encode())
    _atomic_write(root / RESULT_JSON_RELATIVE_PATH, render_result_json(root).encode())


def main() -> None:
    payload = build_reconciliation_payload()
    gate = cast(dict[str, object], payload["primary_gate"])
    decision = cast(dict[str, str], payload["decision"])
    print(
        json.dumps(
            {
                "human_delta_prevalidation": decision[
                    "HUMAN_DELTA_PREVALIDATION"
                ],
                "strong_dominates_mixed": gate["strong_dominates_mixed"],
                "strong_dominates_weak": gate["strong_dominates_weak"],
                "provider_calls": 0,
                "next_gate": decision["NEXT_GATE"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
