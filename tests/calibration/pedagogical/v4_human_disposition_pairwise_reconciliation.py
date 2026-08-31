"""Strict offline reconciliation of the completed v4 human review."""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections import Counter
from collections.abc import Mapping
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import cast

from tests.calibration.pedagogical.anchor_corpus_v4 import (
    DISPOSITIONS,
    PACKET_RELATIVE_PATH,
    PEDAGOGICAL_CALIBRATION_CORPUS_V4_VERSION,
    RECONCILIATION_KEY_RELATIVE_PATH,
    build_human_reconciliation_key,
    v4_anchor_by_id,
    v4_calibration_corpus_sha256,
)

ROOT = Path(__file__).resolve().parents[3]

COMPLETED_REVIEW_RELATIVE_PATH = (
    "artifacts/calibration/12.16-g2-anchor-corpus-v4/"
    "completed_human_disposition_pairwise.md"
)
RESULT_JSON_RELATIVE_PATH = (
    "artifacts/calibration/12.16-g2-anchor-corpus-v4/"
    "human_disposition_pairwise_reconciliation_result.json"
)
REPORT_RELATIVE_PATH = (
    "docs/development/"
    "PHASE_12_16_G2_V4_HUMAN_DISPOSITION_PAIRWISE_RECONCILIATION.md"
)

EXPECTED_COMPLETED_V4_PREVALIDATION_SHA256 = (
    "4ecd7fb8c796ab9c73c12fa8b4a7f3482df5699c4123c15690d57ea81eba5b51"
)
EXPECTED_RECONCILIATION_KEY_SHA256 = (
    "a5b2ed4ebed755b128d3cc163f8004bedb57f2087bd2b444f9835069609edc21"
)
EXPECTED_PACKET_SHA256 = (
    "56bc9d28b65b2e7b82a982cf36afb56d13e147ce6c0716587acaef47e4c42a1f"
)
EXPECTED_CORPUS_SHA256 = (
    "9c8e262028f1d63fa50963f2f8bcb742e4c24d4e106a73244861416f826ca034"
)

TIER_ORDER = ("STRONG", "MIXED", "WEAK_BUT_STRUCTURALLY_VALID")
RELATIONS = ("GT", "EQ", "LT")
NEXT_GATE_PASS = "12.16-G2-V4-PROVIDER-RECALIBRATION-PLAN_READY"
NEXT_GATE_FAIL = "12.16-G2-V4-OWNER_DECISION_REQUIRED"

_CARD_BLOCK = re.compile(
    r"(?ms)^## (V4H-\d{3}) — (SCN-\d{2})\s*\n"
    r"(.*?)(?=^## (?:V4H-\d{3}|Synthèse)|\Z)"
)
_CANDIDATE_BLOCK = re.compile(
    r"(?ms)^### Candidat `([^`]+)`\s*\n"
    r"(.*?)(?=^### Candidat|^- Classement relatif|\Z)"
)
_RANKING_LINE = re.compile(
    r"(?m)^- Classement relatif — `([^`]+)` "
    r"\(IDs\s*:\s*(.*?)\s*\)\s*:\s*$"
)


class V4HumanReconciliationErrorCode(StrEnum):
    REVIEW_INCOMPLETE = "V4_REVIEW_INCOMPLETE"
    REVIEW_INVALID = "V4_REVIEW_INVALID"
    COMPLETED_SHA256_MISMATCH = "COMPLETED_V4_PREVALIDATION_SHA256_MISMATCH"
    PACKET_SHA256_MISMATCH = "V4_PACKET_SHA256_MISMATCH"
    RECONCILIATION_KEY_INVALID = "V4_RECONCILIATION_KEY_INVALID"
    CORPUS_INVALID = "V4_CORPUS_INVALID"


class V4HumanReconciliationError(RuntimeError):
    pass


def _fail(code: V4HumanReconciliationErrorCode, detail: str = "") -> None:
    suffix = f":{detail}" if detail else ""
    raise V4HumanReconciliationError(f"{code.value}{suffix}")


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
            rf"\[\s*([xX]?)\s*\]\s*{re.escape(choice)}(?:\s|$)",
            line,
        )
        if match is None:
            return None
        if match.group(1).casefold() == "x":
            selected.append(choice)
    return selected[0] if len(selected) == 1 else None


def classify_exposure(declaration: str) -> str:
    normalized = " ".join(declaration.casefold().split())
    if (
        "revues v2 et v3" in normalized
        and "aucun mapping candidat v4→tier" in normalized
        and "aucune clé locale v4" in normalized
        and "aucun résultat fournisseur v4" in normalized
    ):
        return "V2_V3_RESULTS_EXPOSED_V4_MAPPING_KEY_AND_RESULTS_BLIND"
    return "UNCLASSIFIED_DECLARED_EXPOSURE" if normalized else "UNDECLARED"


def _default_key_loader(path: Path) -> Mapping[str, object]:
    return cast(Mapping[str, object], json.loads(path.read_text(encoding="utf-8")))


def _validate_key(key: Mapping[str, object]) -> tuple[dict[str, object], ...]:
    expected = build_human_reconciliation_key()
    if _canonical_sha256(key) != _canonical_sha256(expected):
        _fail(
            V4HumanReconciliationErrorCode.RECONCILIATION_KEY_INVALID,
            "CANONICAL_CONTENT",
        )
    if (
        key.get("review_status") != "NOT_COMPLETED"
        or key.get("corpus_version") != PEDAGOGICAL_CALIBRATION_CORPUS_V4_VERSION
        or key.get("corpus_sha256") != EXPECTED_CORPUS_SHA256
        or key.get("packet_sha256") != EXPECTED_PACKET_SHA256
        or key.get("card_count") != 8
        or key.get("candidate_count") != 24
        or key.get("criterion_ranking_count") != 16
    ):
        _fail(
            V4HumanReconciliationErrorCode.RECONCILIATION_KEY_INVALID,
            "METADATA",
        )
    cards = key.get("cards")
    if not isinstance(cards, list) or len(cards) != 8:
        _fail(
            V4HumanReconciliationErrorCode.RECONCILIATION_KEY_INVALID,
            "CARDS",
        )
    return tuple(cast(dict[str, object], card) for card in cards)


def _parse_disposition(candidate_body: str, candidate_id: str) -> str:
    matches = tuple(
        re.finditer(
            r"(?m)^- \[\s*([xX]?)\s*\] "
            r"(DELIVER_AS_IS|REVISE_BEFORE_DELIVERY|REJECT|NON_EVALUABLE)\s*$",
            candidate_body,
        )
    )
    if len(matches) != 4 or tuple(match.group(2) for match in matches) != DISPOSITIONS:
        _fail(
            V4HumanReconciliationErrorCode.REVIEW_INCOMPLETE,
            f"{candidate_id}:DISPOSITION_CHOICES",
        )
    selected = [
        match.group(2)
        for match in matches
        if match.group(1).casefold() == "x"
    ]
    if len(selected) != 1:
        _fail(
            V4HumanReconciliationErrorCode.REVIEW_INCOMPLETE,
            f"{candidate_id}:DISPOSITION_SELECTION",
        )
    return selected[0]


def _parse_ranking_expression(
    expression: str,
    *,
    expected_candidate_ids: tuple[str, ...],
    criterion_ref: str,
) -> tuple[tuple[str, ...], tuple[str, ...], dict[str, int]]:
    if "<" in expression or re.search(r"\d+(?:[.,]\d+)?\s*/\s*\d+", expression):
        _fail(
            V4HumanReconciliationErrorCode.REVIEW_INVALID,
            f"{criterion_ref}:RANKING_GRAMMAR",
        )
    parts = re.split(r"\s*([>=])\s*", expression.strip())
    if len(parts) != 5:
        _fail(
            V4HumanReconciliationErrorCode.REVIEW_INVALID,
            f"{criterion_ref}:RANKING_GRAMMAR",
        )
    candidate_ids = (parts[0], parts[2], parts[4])
    operators = (parts[1], parts[3])
    if (
        any(not re.fullmatch(r"CAND-[A-F0-9]{10}", item) for item in candidate_ids)
        or set(candidate_ids) != set(expected_candidate_ids)
        or len(set(candidate_ids)) != 3
        or any(operator not in {">", "="} for operator in operators)
    ):
        _fail(
            V4HumanReconciliationErrorCode.REVIEW_INVALID,
            f"{criterion_ref}:RANKING_IDS",
        )
    level_by_id = {candidate_ids[0]: 0}
    level = 0
    for operator, candidate_id in zip(operators, candidate_ids[1:], strict=True):
        if operator == ">":
            level += 1
        level_by_id[candidate_id] = level
    return candidate_ids, operators, level_by_id


def _relation(left_level: int, right_level: int) -> str:
    if left_level < right_level:
        return "GT"
    if left_level == right_level:
        return "EQ"
    return "LT"


def _parse_completed_review(
    review_text: str,
    key_cards: tuple[dict[str, object], ...],
) -> dict[str, object]:
    header = review_text.split("## Définitions contrôlées", maxsplit=1)[0]
    if _field(header, "REVIEW_STATUS") != "COMPLETED":
        _fail(V4HumanReconciliationErrorCode.REVIEW_INCOMPLETE, "REVIEW_STATUS")
    if (
        _field(header, "Corpus") != PEDAGOGICAL_CALIBRATION_CORPUS_V4_VERSION
        or _field(header, "Checksum corpus") != EXPECTED_CORPUS_SHA256
        or v4_calibration_corpus_sha256() != EXPECTED_CORPUS_SHA256
    ):
        _fail(V4HumanReconciliationErrorCode.CORPUS_INVALID, "IDENTITY")
    reviewer = _field(header, "Relecteur ou relectrice")
    review_date = _field(header, "Date")
    grid_version = _field(header, "Version de la grille")
    exposure = _field(header, "Exposition préalable")
    if re.fullmatch(r"[A-Z][A-Z0-9_]{2,63}", reviewer) is None:
        _fail(V4HumanReconciliationErrorCode.REVIEW_INVALID, "REVIEWER_CODE")
    try:
        date.fromisoformat(review_date)
    except ValueError:
        _fail(V4HumanReconciliationErrorCode.REVIEW_INVALID, "REVIEW_DATE")
    if grid_version != "human-disposition-pairwise-v4":
        _fail(V4HumanReconciliationErrorCode.REVIEW_INVALID, "GRID_VERSION")
    if not exposure:
        _fail(V4HumanReconciliationErrorCode.REVIEW_INCOMPLETE, "EXPOSURE")

    matches = tuple(_CARD_BLOCK.finditer(review_text))
    expected_card_ids = tuple(f"V4H-{index:03d}" for index in range(1, 9))
    if tuple(match.group(1) for match in matches) != expected_card_ids:
        _fail(V4HumanReconciliationErrorCode.REVIEW_INVALID, "CARD_IDS")

    parsed_cards: list[dict[str, object]] = []
    disposition_count = 0
    ranking_count = 0
    for match, key_card in zip(matches, key_cards, strict=True):
        card_id, scenario_code, body = match.groups()
        if (
            key_card.get("card_id") != card_id
            or key_card.get("scenario_code") != scenario_code
        ):
            _fail(V4HumanReconciliationErrorCode.REVIEW_INVALID, f"{card_id}:KEY")
        key_candidates = cast(list[dict[str, str]], key_card.get("candidates"))
        criterion_refs = tuple(cast(list[str], key_card.get("criterion_refs")))
        expected_by_candidate = {
            item["blinded_candidate_id"]: item for item in key_candidates
        }
        candidate_matches = tuple(_CANDIDATE_BLOCK.finditer(body))
        candidate_ids = tuple(item.group(1) for item in candidate_matches)
        expected_ids = tuple(item["blinded_candidate_id"] for item in key_candidates)
        if candidate_ids != expected_ids or len(candidate_matches) != 3:
            _fail(
                V4HumanReconciliationErrorCode.REVIEW_INVALID,
                f"{card_id}:CANDIDATES",
            )

        candidates: list[dict[str, str]] = []
        tier_by_candidate: dict[str, str] = {}
        for candidate_match in candidate_matches:
            candidate_id, candidate_body = candidate_match.groups()
            mapping = expected_by_candidate[candidate_id]
            anchor = v4_anchor_by_id(mapping["anchor_id"])
            sections = tuple(
                (section.group(1), section.group(2).strip())
                for section in re.finditer(
                    r"(?m)^- `([^`]+)`\s*:\s*(.+)$",
                    candidate_body,
                )
            )
            if sections != anchor.sections:
                _fail(
                    V4HumanReconciliationErrorCode.REVIEW_INVALID,
                    f"{candidate_id}:CONTENT_MUTATED",
                )
            disposition = _parse_disposition(candidate_body, candidate_id)
            tier = mapping["expected_tier"]
            tier_by_candidate[candidate_id] = tier
            candidates.append(
                {
                    "blinded_candidate_id": candidate_id,
                    "anchor_id": mapping["anchor_id"],
                    "tier": tier,
                    "disposition": disposition,
                }
            )
            disposition_count += 1

        ranking_matches = tuple(_RANKING_LINE.finditer(body))
        if (
            len(ranking_matches) != 2
            or tuple(item.group(1) for item in ranking_matches) != criterion_refs
        ):
            _fail(
                V4HumanReconciliationErrorCode.REVIEW_INCOMPLETE,
                f"{card_id}:RANKINGS",
            )
        rankings: list[dict[str, object]] = []
        for ranking_match in ranking_matches:
            criterion_ref, expression = ranking_match.groups()
            ordered_ids, operators, level_by_id = _parse_ranking_expression(
                expression,
                expected_candidate_ids=expected_ids,
                criterion_ref=criterion_ref,
            )
            level_by_tier = {
                tier_by_candidate[candidate_id]: level
                for candidate_id, level in level_by_id.items()
            }
            if set(level_by_tier) != set(TIER_ORDER):
                _fail(
                    V4HumanReconciliationErrorCode.REVIEW_INVALID,
                    f"{criterion_ref}:TIER_MAPPING",
                )
            relation_strong_mixed = _relation(
                level_by_tier["STRONG"], level_by_tier["MIXED"]
            )
            relation_strong_weak = _relation(
                level_by_tier["STRONG"],
                level_by_tier["WEAK_BUT_STRUCTURALLY_VALID"],
            )
            relation_mixed_weak = _relation(
                level_by_tier["MIXED"],
                level_by_tier["WEAK_BUT_STRUCTURALLY_VALID"],
            )
            tier_expression_parts: list[str] = []
            for index, candidate_id in enumerate(ordered_ids):
                if index:
                    tier_expression_parts.append(operators[index - 1])
                tier_expression_parts.append(tier_by_candidate[candidate_id])
            rankings.append(
                {
                    "criterion_ref": criterion_ref,
                    "blinded_expression": " ".join(
                        part
                        for pair in zip(ordered_ids, (*operators, ""), strict=True)
                        for part in pair
                        if part
                    ),
                    "tier_expression": " ".join(tier_expression_parts),
                    "strong_vs_mixed": relation_strong_mixed,
                    "strong_vs_weak": relation_strong_weak,
                    "mixed_vs_weak": relation_mixed_weak,
                    "non_evaluable": False,
                    "trinary_strict": (
                        relation_strong_mixed == "GT"
                        and relation_mixed_weak == "GT"
                    ),
                }
            )
            ranking_count += 1

        justifications = tuple(
            item.group(1).strip()
            for item in re.finditer(
                r"(?m)^- Justification pédagogique courte de la carte\s*:\s*(.+)$",
                body,
            )
        )
        if len(justifications) != 1 or not justifications[0]:
            _fail(
                V4HumanReconciliationErrorCode.REVIEW_INCOMPLETE,
                f"{card_id}:JUSTIFICATION",
            )
        parsed_cards.append(
            {
                "card_id": card_id,
                "scenario_code": scenario_code,
                "candidates": candidates,
                "rankings": rankings,
                "justification": justifications[0],
            }
        )

    if disposition_count != 24 or ranking_count != 16:
        _fail(V4HumanReconciliationErrorCode.REVIEW_INCOMPLETE, "COUNTS")
    synthesis_parts = review_text.split("## Synthèse et signatures", maxsplit=1)
    if len(synthesis_parts) != 2:
        _fail(V4HumanReconciliationErrorCode.REVIEW_INCOMPLETE, "SYNTHESIS")
    synthesis = synthesis_parts[1]
    summary_checks = (
        ("Huit cartes revues", ("oui", "non")),
        ("Vingt-quatre dispositions renseignées", ("oui", "non")),
        ("Seize classements relatifs renseignés", ("oui", "non")),
    )
    for label, choices in summary_checks:
        line = re.search(rf"(?m)^- {re.escape(label)}\s*:.*$", synthesis)
        if line is None or _checked_choice(line.group(0), choices) != "oui":
            _fail(
                V4HumanReconciliationErrorCode.REVIEW_INCOMPLETE,
                f"SYNTHESIS:{label}",
            )
    opinion_line = re.search(r"(?m)^- Avis\s*:.*$", synthesis)
    opinion_choices = ("utilisable", "révisions requises", "inconclusif")
    if opinion_line is None:
        _fail(V4HumanReconciliationErrorCode.REVIEW_INCOMPLETE, "OPINION")
    opinion = _checked_choice(opinion_line.group(0), opinion_choices)
    if opinion is None:
        _fail(V4HumanReconciliationErrorCode.REVIEW_INCOMPLETE, "OPINION")
    synthesis_reviewer = _field(synthesis, "Relecteur ou relectrice")
    responsible = _field(synthesis, "Responsable de la calibration")
    closure_date = _field(synthesis, "Date de clôture")
    if synthesis_reviewer != reviewer or not responsible:
        _fail(V4HumanReconciliationErrorCode.REVIEW_INVALID, "SIGNATURES")
    try:
        date.fromisoformat(closure_date)
    except ValueError:
        _fail(V4HumanReconciliationErrorCode.REVIEW_INVALID, "CLOSURE_DATE")

    return {
        "review_status": "COMPLETED",
        "reviewer_code": reviewer,
        "review_date": review_date,
        "closure_date": closure_date,
        "responsible_code": responsible,
        "grid_version": grid_version,
        "exposure_declaration": exposure,
        "exposure_class": classify_exposure(exposure),
        "global_opinion": opinion.replace(" ", "_").upper(),
        "review_card_count": len(parsed_cards),
        "disposition_count": disposition_count,
        "pairwise_ranking_count": ranking_count,
        "cards": parsed_cards,
    }


def _load_and_validate_inputs(
    root: Path,
    *,
    expected_completed_sha256: str,
    key_loader: object | None = None,
) -> tuple[dict[str, object], dict[str, str]]:
    packet_path = root / PACKET_RELATIVE_PATH
    completed_path = root / COMPLETED_REVIEW_RELATIVE_PATH
    key_path = root / RECONCILIATION_KEY_RELATIVE_PATH
    try:
        packet_bytes = packet_path.read_bytes()
        completed_bytes = completed_path.read_bytes()
        key_bytes = key_path.read_bytes()
    except OSError:
        _fail(V4HumanReconciliationErrorCode.REVIEW_INCOMPLETE, "MISSING_FILE")
    packet_sha256 = _sha256(packet_bytes)
    completed_sha256 = _sha256(completed_bytes)
    key_sha256 = _sha256(key_bytes)
    if packet_sha256 != EXPECTED_PACKET_SHA256:
        _fail(V4HumanReconciliationErrorCode.PACKET_SHA256_MISMATCH, packet_sha256)
    if completed_sha256 != expected_completed_sha256:
        _fail(
            V4HumanReconciliationErrorCode.COMPLETED_SHA256_MISMATCH,
            completed_sha256,
        )
    if key_sha256 != EXPECTED_RECONCILIATION_KEY_SHA256:
        _fail(V4HumanReconciliationErrorCode.RECONCILIATION_KEY_INVALID, key_sha256)
    loader = key_loader if key_loader is not None else _default_key_loader
    key = cast(Mapping[str, object], cast(object, loader)(key_path))
    key_cards = _validate_key(key)
    parsed = _parse_completed_review(completed_bytes.decode("utf-8"), key_cards)
    if _sha256(completed_path.read_bytes()) != completed_sha256:
        _fail(V4HumanReconciliationErrorCode.REVIEW_INVALID, "MUTATED_DURING_READ")
    return parsed, {
        "packet_sha256": packet_sha256,
        "completed_v4_prevalidation_sha256": completed_sha256,
        "reconciliation_key_sha256": key_sha256,
        "corpus_sha256": v4_calibration_corpus_sha256(),
    }


def build_reconciliation_payload(
    root: Path = ROOT,
    *,
    expected_completed_sha256: str = EXPECTED_COMPLETED_V4_PREVALIDATION_SHA256,
    key_loader: object | None = None,
) -> dict[str, object]:
    review, proofs = _load_and_validate_inputs(
        root,
        expected_completed_sha256=expected_completed_sha256,
        key_loader=key_loader,
    )
    cards = cast(list[dict[str, object]], review["cards"])
    dispositions = {
        tier: Counter({choice: 0 for choice in DISPOSITIONS}) for tier in TIER_ORDER
    }
    rankings: list[dict[str, object]] = []
    scenario_dispositions: list[dict[str, str]] = []
    for card in cards:
        by_tier: dict[str, str] = {}
        for candidate in cast(list[dict[str, str]], card["candidates"]):
            tier = candidate["tier"]
            disposition = candidate["disposition"]
            dispositions[tier][disposition] += 1
            by_tier[tier] = disposition
        scenario_dispositions.append(
            {
                "scenario_code": cast(str, card["scenario_code"]),
                **{tier: by_tier[tier] for tier in TIER_ORDER},
            }
        )
        rankings.extend(cast(list[dict[str, object]], card["rankings"]))

    strong_gt_mixed = sum(item["strong_vs_mixed"] == "GT" for item in rankings)
    strong_gt_weak = sum(item["strong_vs_weak"] == "GT" for item in rankings)
    non_evaluable_rankings = sum(bool(item["non_evaluable"]) for item in rankings)
    mixed_weak = Counter(cast(str, item["mixed_vs_weak"]) for item in rankings)
    trinary_strict = sum(bool(item["trinary_strict"]) for item in rankings)
    non_evaluable_dispositions = sum(
        dispositions[tier]["NON_EVALUABLE"] for tier in TIER_ORDER
    )
    deliverability_pass = (
        dispositions["STRONG"]["DELIVER_AS_IS"] == 8
        and dispositions["MIXED"]["DELIVER_AS_IS"] == 0
        and dispositions["WEAK_BUT_STRUCTURALLY_VALID"]["DELIVER_AS_IS"] == 0
        and non_evaluable_dispositions == 0
    )
    pairwise_pass = (
        strong_gt_mixed == 16
        and strong_gt_weak == 16
        and non_evaluable_rankings == 0
    )
    human_pass = deliverability_pass and pairwise_pass
    decision = "PASS" if human_pass else "FAIL"
    provider_recalibration = "READY_FOR_OFFLINE_PLAN_ONLY" if human_pass else "FALSE"
    next_gate = NEXT_GATE_PASS if human_pass else NEXT_GATE_FAIL
    return {
        "phase": "12.16-G2-V4-HUMAN-DISPOSITION-PAIRWISE-RECONCILIATION",
        "decision": decision,
        "human_v4_prevalidation": decision,
        "corpus": {
            "version": PEDAGOGICAL_CALIBRATION_CORPUS_V4_VERSION,
            "sha256": EXPECTED_CORPUS_SHA256,
        },
        "proofs": proofs,
        "review": review,
        "distribution_by_tier": {
            tier: dict(dispositions[tier]) for tier in TIER_ORDER
        },
        "scenario_dispositions": scenario_dispositions,
        "criterion_rankings": rankings,
        "gate_a": {
            "strong_deliver_as_is": dispositions["STRONG"]["DELIVER_AS_IS"],
            "mixed_deliver_as_is": dispositions["MIXED"]["DELIVER_AS_IS"],
            "weak_deliver_as_is": dispositions["WEAK_BUT_STRUCTURALLY_VALID"][
                "DELIVER_AS_IS"
            ],
            "non_evaluable_dispositions": non_evaluable_dispositions,
            "status": "PASS" if deliverability_pass else "FAIL",
        },
        "disposition_diagnostic": {
            "mixed_revise": dispositions["MIXED"]["REVISE_BEFORE_DELIVERY"],
            "mixed_reject": dispositions["MIXED"]["REJECT"],
            "weak_revise": dispositions["WEAK_BUT_STRUCTURALLY_VALID"][
                "REVISE_BEFORE_DELIVERY"
            ],
            "weak_reject": dispositions["WEAK_BUT_STRUCTURALLY_VALID"]["REJECT"],
        },
        "gate_b": {
            "strong_gt_mixed": strong_gt_mixed,
            "strong_gt_weak": strong_gt_weak,
            "non_evaluable_rankings": non_evaluable_rankings,
            "status": "PASS" if pairwise_pass else "FAIL",
        },
        "mixed_weak_diagnostic": {
            "mixed_gt_weak": mixed_weak["GT"],
            "mixed_eq_weak": mixed_weak["EQ"],
            "mixed_lt_weak": mixed_weak["LT"],
            "trinary_strict_order_count": trinary_strict,
            "blocking": False,
        },
        "authority_separation": {
            "provider_is_authority": False,
            "model_judge_is_domain_validator": False,
            "scorer_result_is_runtime_outcome": False,
            "model_routing_is_gate_approval": False,
        },
        "provider_recalibration_allowed": provider_recalibration,
        "provider_calls": 0,
        "provider_cost": 0,
        "credentials_resolved": False,
        "provider_transport_constructed": False,
        "runtime_route_change": "NONE",
        "release_threshold_adoption": "NOT_ALLOWED",
        "test_level": "T2_BOUNDED",
        "global_suite_run": "NO",
        "next_gate": next_gate,
    }


def render_result_json(root: Path = ROOT) -> str:
    return _pretty_json(build_reconciliation_payload(root))


def render_report_markdown(root: Path = ROOT) -> str:
    payload = build_reconciliation_payload(root)
    proofs = cast(dict[str, str], payload["proofs"])
    review = cast(dict[str, object], payload["review"])
    gate_a = cast(dict[str, object], payload["gate_a"])
    gate_b = cast(dict[str, object], payload["gate_b"])
    diagnostic = cast(dict[str, object], payload["disposition_diagnostic"])
    mixed_weak = cast(dict[str, object], payload["mixed_weak_diagnostic"])
    distributions = cast(dict[str, dict[str, int]], payload["distribution_by_tier"])
    lines = [
        "# Phase 12.16-G2 — Réconciliation humaine disposition et pairwise v4",
        "",
        "## Décision",
        "",
        f"- HUMAN_V4_PREVALIDATION = `{payload['human_v4_prevalidation']}`.",
        f"- DELIVERABILITY_GATE = `{gate_a['status']}`.",
        f"- PAIRWISE_CRITERION_GATE = `{gate_b['status']}`.",
        f"- PROVIDER_RECALIBRATION_ALLOWED = `{payload['provider_recalibration_allowed']}`.",
        f"- NEXT_GATE = `{payload['next_gate']}`.",
        "",
        "## Identité et preuves",
        "",
        f"- Corpus : `{PEDAGOGICAL_CALIBRATION_CORPUS_V4_VERSION}`.",
        f"- Checksum corpus : `{proofs['corpus_sha256']}`.",
        f"- Checksum paquet : `{proofs['packet_sha256']}`.",
        f"- Checksum formulaire complété : `{proofs['completed_v4_prevalidation_sha256']}`.",
        f"- Checksum clé locale : `{proofs['reconciliation_key_sha256']}`.",
        "",
        "## Revue humaine et complétude",
        "",
        f"- REVIEW_STATUS : `{review['review_status']}`.",
        f"- Relecteur ou relectrice : `{review['reviewer_code']}`.",
        f"- Date : `{review['review_date']}`; clôture : `{review['closure_date']}`.",
        f"- Exposition déclarée : {review['exposure_declaration']}",
        f"- Classe d'exposition : `{review['exposure_class']}`.",
        f"- Opinion globale : `{review['global_opinion']}`.",
        "- Complétude : `8 cartes / 24 dispositions / 16 classements / 8 justifications`.",
        "",
        "## Distribution des dispositions par tier",
        "",
        "| Tier | DELIVER_AS_IS | REVISE_BEFORE_DELIVERY | REJECT | NON_EVALUABLE |",
        "|---|---:|---:|---:|---:|",
    ]
    for tier in TIER_ORDER:
        row = distributions[tier]
        lines.append(
            f"| {tier} | {row['DELIVER_AS_IS']} | "
            f"{row['REVISE_BEFORE_DELIVERY']} | {row['REJECT']} | "
            f"{row['NON_EVALUABLE']} |"
        )
    lines.extend(
        (
            "",
            "## Dispositions par scénario",
            "",
            "| Scénario | STRONG | MIXED | WEAK_BUT_STRUCTURALLY_VALID |",
            "|---|---|---|---|",
        )
    )
    for item in cast(list[dict[str, str]], payload["scenario_dispositions"]):
        lines.append(
            f"| {item['scenario_code']} | {item['STRONG']} | {item['MIXED']} | "
            f"{item['WEAK_BUT_STRUCTURALLY_VALID']} |"
        )
    lines.extend(
        (
            "",
            "## Gate A — Livrabilité globale",
            "",
            f"- STRONG_DELIVER_AS_IS = `{gate_a['strong_deliver_as_is']}/8`.",
            f"- MIXED_DELIVER_AS_IS = `{gate_a['mixed_deliver_as_is']}/8`.",
            f"- WEAK_DELIVER_AS_IS = `{gate_a['weak_deliver_as_is']}/8`.",
            f"- NON_EVALUABLE_DISPOSITIONS = `{gate_a['non_evaluable_dispositions']}/24`.",
            f"- MIXED_REVISE = `{diagnostic['mixed_revise']}`; MIXED_REJECT = `{diagnostic['mixed_reject']}`.",
            f"- WEAK_REVISE = `{diagnostic['weak_revise']}`; WEAK_REJECT = `{diagnostic['weak_reject']}`.",
            f"- Résultat : `{gate_a['status']}`.",
            "",
            "## Relations par critère",
            "",
            "| Critère | Relation reconstruite | STRONG/MIXED | STRONG/WEAK | MIXED/WEAK |",
            "|---|---|---|---|---|",
        )
    )
    for item in cast(list[dict[str, object]], payload["criterion_rankings"]):
        lines.append(
            f"| {item['criterion_ref']} | {item['tier_expression']} | "
            f"{item['strong_vs_mixed']} | {item['strong_vs_weak']} | "
            f"{item['mixed_vs_weak']} |"
        )
    lines.extend(
        (
            "",
            "## Gate B — Discrimination critère par critère",
            "",
            f"- STRONG_STRICTLY_PREFERRED_TO_MIXED = `{gate_b['strong_gt_mixed']}/16`.",
            f"- STRONG_STRICTLY_PREFERRED_TO_WEAK = `{gate_b['strong_gt_weak']}/16`.",
            f"- NON_EVALUABLE_RANKINGS = `{gate_b['non_evaluable_rankings']}/16`.",
            f"- Résultat : `{gate_b['status']}`.",
            "",
            "## Diagnostic secondaire Mixed/Weak",
            "",
            f"- MIXED_GT_WEAK = `{mixed_weak['mixed_gt_weak']}`.",
            f"- MIXED_EQ_WEAK = `{mixed_weak['mixed_eq_weak']}`.",
            f"- MIXED_LT_WEAK = `{mixed_weak['mixed_lt_weak']}`.",
            f"- TRINARY_STRICT_ORDER_COUNT = `{mixed_weak['trinary_strict_order_count']}`.",
            "- Ce diagnostic est non bloquant.",
            "",
            "## Décision finale et frontières",
            "",
            f"- HUMAN_V4_PREVALIDATION = `{payload['human_v4_prevalidation']}`.",
            f"- PROVIDER_RECALIBRATION_ALLOWED = `{payload['provider_recalibration_allowed']}`.",
            "- PROVIDER_CALLS = `0`; PROVIDER_COST = `0`.",
            "- CREDENTIALS_RESOLVED = `FALSE`; PROVIDER_TRANSPORT_CONSTRUCTED = `FALSE`.",
            "- RUNTIME_ROUTE_CHANGE = `NONE`.",
            "- RELEASE_THRESHOLD_ADOPTION = `NOT_ALLOWED`.",
            "- PROVIDER != AUTHORITY; MODEL_JUDGE != DOMAIN_VALIDATOR.",
            "- SCORER_RESULT != RUNTIME_OUTCOME; MODEL_ROUTING != GATE_APPROVAL.",
            "- Aucun corpus v5 n'est créé automatiquement.",
            f"- NEXT_GATE = `{payload['next_gate']}`.",
            "- TEST_LEVEL = `T2_BOUNDED`; GLOBAL_SUITE_RUN = `NO`.",
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
    payload = build_reconciliation_payload(ROOT)
    gate_a = cast(dict[str, object], payload["gate_a"])
    gate_b = cast(dict[str, object], payload["gate_b"])
    print(
        json.dumps(
            {
                "decision": payload["decision"],
                "gate_a": gate_a["status"],
                "gate_b": gate_b["status"],
                "provider_calls": 0,
                "next_gate": payload["next_gate"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
