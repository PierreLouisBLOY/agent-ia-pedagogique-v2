from __future__ import annotations

import hashlib
import json
import re
import shutil
from collections import Counter
from pathlib import Path

import pytest

from tests.calibration.pedagogical.v2_human_prevalidation_reconciliation import (
    COMPLETED_PREVALIDATION_RELATIVE_PATH,
    EXPECTED_COMPLETED_PREVALIDATION_SHA256,
    EXPECTED_CORPUS_SHA256,
    EXPECTED_PACKET_SHA256,
    EXPECTED_RECONCILIATION_KEY_SHA256,
    PACKET_RELATIVE_PATH,
    RECONCILIATION_KEY_RELATIVE_PATH,
    REPORT_RELATIVE_PATH,
    RESULT_JSON_RELATIVE_PATH,
    V2HumanPrevalidationError,
    V2HumanPrevalidationErrorCode,
    build_reconciliation_payload,
    render_report_markdown,
    render_result_json,
    write_outputs,
)

ROOT = Path(__file__).resolve().parents[3]


def _reconciliation_root(tmp_path: Path) -> Path:
    for relative_path in (
        PACKET_RELATIVE_PATH,
        COMPLETED_PREVALIDATION_RELATIVE_PATH,
        RECONCILIATION_KEY_RELATIVE_PATH,
    ):
        source = ROOT / relative_path
        target = tmp_path / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return tmp_path


def _mutate_review(root: Path, transform: object) -> str:
    path = root / COMPLETED_PREVALIDATION_RELATIVE_PATH
    text = path.read_text(encoding="utf-8")
    if not callable(transform):
        raise TypeError("transform must be callable")
    mutated = transform(text)
    path.write_text(mutated, encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_corrected_owner_override_source_proofs_are_exact() -> None:
    payload = build_reconciliation_payload(ROOT)
    proofs = payload["source_proofs"]
    assert proofs["completed_prevalidation_sha256"] == (
        EXPECTED_COMPLETED_PREVALIDATION_SHA256
    )
    assert proofs["packet_sha256"] == EXPECTED_PACKET_SHA256
    assert proofs["reconciliation_key_sha256"] == EXPECTED_RECONCILIATION_KEY_SHA256
    assert proofs["corpus_sha256"] == EXPECTED_CORPUS_SHA256
    assert proofs["owner_checksum_override"] == "APPROVED"
    assert payload["review_metadata"] == {
        "review_status": "COMPLETED",
        "reviewer_code": "OWNER_HUMAN_REVIEWER",
        "review_date": "2026-08-30",
        "closure_date_declared": "2026-08-3",
        "grid_version": "human-prevalidation-v2",
        "item_count": 24,
        "structure_decision_count": 24,
        "criterion_appreciation_count": 48,
        "action_decision_count": 24,
        "global_opinion": "RÉVISIONS_REQUISES",
        "exposure_declaration": (
            "OUI — résultats et limites du corpus v1 ainsi que l’objectif de "
            "remédiation v2 connus ; aucune clé HPV2→anchor/tier et aucun "
            "résultat fournisseur v2 consultés."
        ),
        "exposure_class": (
            "V1_DIAGNOSTIC_EXPOSED_V2_MAPPING_AND_RESULTS_BLIND"
        ),
    }


@pytest.mark.parametrize("mutation", ["structure", "label", "content"])
def test_invalid_review_stops_before_key_access(
    tmp_path: Path,
    mutation: str,
) -> None:
    root = _reconciliation_root(tmp_path)
    if mutation == "structure":
        expected_sha = _mutate_review(
            root,
            lambda text: text.replace(
                "- Structure valide : [x] oui [ ] non",
                "- Structure valide : [x] oui [x] non",
                1,
            ),
        )
        expected_error = V2HumanPrevalidationErrorCode.PREVALIDATION_INCOMPLETE
    elif mutation == "label":
        expected_sha = _mutate_review(
            root,
            lambda text: re.sub(
                r"(?m)(^- Appréciation humaine — `[^`]+`\s*:\s*)\S+",
                r"\1EXCELLENT",
                text,
                count=1,
            ),
        )
        expected_error = V2HumanPrevalidationErrorCode.PREVALIDATION_INVALID
    else:
        expected_sha = _mutate_review(
            root,
            lambda text: text.replace(
                "La recherche vise des ressources de gestion financière",
                "La recherche vise des documents de gestion financière",
                1,
            ),
        )
        expected_error = (
            V2HumanPrevalidationErrorCode.PREVALIDATION_TEMPLATE_MUTATED
        )

    key_accessed = False

    def forbidden_key_loader(_: Path) -> dict[str, object]:
        nonlocal key_accessed
        key_accessed = True
        raise AssertionError("the blind key must remain unopened")

    with pytest.raises(V2HumanPrevalidationError, match=expected_error.value):
        build_reconciliation_payload(
            root,
            key_loader=forbidden_key_loader,
            expected_completed_sha256=expected_sha,
        )
    assert key_accessed is False


def test_unapproved_completed_checksum_stops_reconciliation() -> None:
    with pytest.raises(
        V2HumanPrevalidationError,
        match=(
            V2HumanPrevalidationErrorCode.COMPLETED_PREVALIDATION_SHA256_MISMATCH.value
        ),
    ):
        build_reconciliation_payload(
            ROOT,
            expected_completed_sha256="0" * 64,
        )


def test_tampered_key_stops_reconciliation(tmp_path: Path) -> None:
    root = _reconciliation_root(tmp_path)
    key_path = root / RECONCILIATION_KEY_RELATIVE_PATH
    key = json.loads(key_path.read_text(encoding="utf-8"))
    key["items"][0]["expected_tier"] = "MIXED"
    key_path.write_text(json.dumps(key), encoding="utf-8")
    with pytest.raises(
        V2HumanPrevalidationError,
        match=V2HumanPrevalidationErrorCode.RECONCILIATION_KEY_INVALID.value,
    ):
        build_reconciliation_payload(root)


def test_human_distributions_and_ordering_are_exact() -> None:
    payload = build_reconciliation_payload(ROOT)
    distributions = payload["human_distributions"]
    assert distributions["labels_by_tier"] == {
        "STRONG": {
            "TRES_SATISFAISANT": 16,
            "SATISFAISANT": 0,
            "FRAGILE": 0,
            "INSUFFISANT": 0,
            "NON_EVALUABLE": 0,
        },
        "MIXED": {
            "TRES_SATISFAISANT": 9,
            "SATISFAISANT": 7,
            "FRAGILE": 0,
            "INSUFFISANT": 0,
            "NON_EVALUABLE": 0,
        },
        "WEAK_BUT_STRUCTURALLY_VALID": {
            "TRES_SATISFAISANT": 6,
            "SATISFAISANT": 4,
            "FRAGILE": 6,
            "INSUFFISANT": 0,
            "NON_EVALUABLE": 0,
        },
    }
    assert distributions["structural_invalid_by_tier"] == {
        "STRONG": 0,
        "MIXED": 0,
        "WEAK_BUT_STRUCTURALLY_VALID": 0,
    }
    assert payload["human_ordering"]["metrics"] == {
        "criterion_count": 16,
        "strict_ordering_count": 4,
        "weak_ordering_count": 15,
        "tied_pair_count": 16,
        "inverted_pair_count": 1,
        "non_evaluable_relation_count": 0,
        "differentiation_perceptible_count": 11,
    }


def test_criterion_relations_dispositions_and_gate_are_exact() -> None:
    payload = build_reconciliation_payload(ROOT)
    details = payload["criterion_dispositions"]
    assert len(details) == 16
    assert Counter(item["relation"] for item in details) == {
        "STRONG > MIXED > WEAK": 4,
        "STRONG = MIXED > WEAK": 4,
        "STRONG > MIXED = WEAK": 2,
        "STRONG = MIXED = WEAK": 5,
        "STRONG > MIXED < WEAK": 1,
    }
    assert payload["disposition_counts"] == {
        "PASS_STRICT": 4,
        "PASS_WEAK_WITH_TIE_REVIEW": 0,
        "REVISE_ANCHORS": 12,
        "OWNER_DECISION_REQUIRED": 0,
        "NON_EVALUABLE": 0,
        "STRUCTURAL_ANCHOR_DEFECT": 0,
    }
    assert payload["gate"] == {
        "structures_valid": "24/24",
        "weak_order": "15/16",
        "inversions": 1,
        "non_evaluable": 0,
        "differentiation_perceptible": "11/16",
        "design_target_strict": "4/16",
        "passed": False,
    }
    assert payload["decision"] == {
        "HUMAN_PREVALIDATION": "FAIL",
        "PROVIDER_RECALIBRATION_ALLOWED": "FALSE",
        "RELEASE_THRESHOLD_ADOPTION": "NOT_ALLOWED",
        "PROVIDER_ROUTE_CHANGE": "NONE",
        "NEXT_GATE": "12.16-G2-V2-ANCHOR-REVISION_REQUIRED",
    }


def test_report_and_local_result_are_deterministic_and_minimized() -> None:
    report_a = render_report_markdown(ROOT)
    report_b = render_report_markdown(ROOT)
    result_a = render_result_json(ROOT)
    result_b = render_result_json(ROOT)
    assert report_a == report_b
    assert result_a == result_b
    assert report_a == (ROOT / REPORT_RELATIVE_PATH).read_text(encoding="utf-8")
    assert result_a == (ROOT / RESULT_JSON_RELATIVE_PATH).read_text(encoding="utf-8")

    combined = report_a + result_a
    lowered = combined.casefold()
    assert "hpv2-001" not in lowered
    assert "cal.v2.scn-" not in lowered
    assert "c:\\users\\" not in lowered
    assert "api_key" not in lowered
    assert "justification pédagogique courte" not in lowered
    assert "ambiguïté ou manque de contexte" not in lowered
    assert "provider_cost_usd" in result_a
    assert '"openai_calls": 0' in result_a
    assert '"anthropic_calls": 0' in result_a


def test_outputs_are_byte_stable_when_regenerated(tmp_path: Path) -> None:
    root = _reconciliation_root(tmp_path)
    write_outputs(root)
    first = tuple(
        (root / relative_path).read_bytes()
        for relative_path in (REPORT_RELATIVE_PATH, RESULT_JSON_RELATIVE_PATH)
    )
    write_outputs(root)
    second = tuple(
        (root / relative_path).read_bytes()
        for relative_path in (REPORT_RELATIVE_PATH, RESULT_JSON_RELATIVE_PATH)
    )
    assert first == second
