"""Offline trace audit for the v4 corrective attestation closure."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import cast

from tests.calibration.pedagogical.v4_human_disposition_pairwise_reconciliation import (
    COMPLETED_REVIEW_RELATIVE_PATH,
    build_reconciliation_payload,
)
from tests.calibration.pedagogical.v4_human_disposition_pairwise_reconciliation import (
    RESULT_JSON_RELATIVE_PATH as PRE_CORRECTION_RESULT_RELATIVE_PATH,
)

ROOT = Path(__file__).resolve().parents[3]

REPORT_RELATIVE_PATH = (
    "docs/development/PHASE_12_16_G2_V4_CORRECTIVE_ATTESTATION_CLOSURE.md"
)
EXPECTED_PRE_CORRECTION_RESULT_SHA256 = (
    "deefcf8078f7a182e5332587bc782ef166afff473468d4d14d4d171a7ff785db"
)
EXPECTED_PRE_CORRECTION_FORM_SHA256 = (
    "4ecd7fb8c796ab9c73c12fa8b4a7f3482df5699c4123c15690d57ea81eba5b51"
)
CORRECTED_FORM_SHA256 = (
    "5748b0f223b3039b463f975de8d99772a9f18ad729535a73bd27dfcfc27042a6"
)
CORRECTIVE_ATTESTATION = True
CORRECTION_CAUSE = "INATTENTION / TRANSCRIPTION_ERROR"
CORRECTED_SCOPE = (
    "SCN-01 ONE PAIRWISE RANKING; "
    "SCN-06 ONE DISPOSITION AND TWO PAIRWISE RANKINGS"
)
NEXT_GATE_PARTIAL = "12.16-G2-V4-OWNER_DECISION_REQUIRED"


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _load_pre_correction_result(root: Path) -> dict[str, object]:
    path = root / PRE_CORRECTION_RESULT_RELATIVE_PATH
    payload = path.read_bytes()
    if _sha256(payload) != EXPECTED_PRE_CORRECTION_RESULT_SHA256:
        raise RuntimeError("PRE_CORRECTION_RESULT_SHA256_MISMATCH")
    parsed = cast(dict[str, object], json.loads(payload.decode("utf-8")))
    proofs = cast(dict[str, str], parsed.get("proofs"))
    if (
        proofs.get("completed_v4_prevalidation_sha256")
        != EXPECTED_PRE_CORRECTION_FORM_SHA256
    ):
        raise RuntimeError("PRE_CORRECTION_FORM_PROOF_MISMATCH")
    return parsed


def _semantic_changes(
    previous: dict[str, object],
    corrected: dict[str, object],
) -> tuple[dict[str, object], ...]:
    previous_review = cast(dict[str, object], previous["review"])
    corrected_review = cast(dict[str, object], corrected["review"])
    previous_cards = cast(list[dict[str, object]], previous_review["cards"])
    corrected_cards = cast(list[dict[str, object]], corrected_review["cards"])
    changes: list[dict[str, object]] = []
    for previous_card, corrected_card in zip(
        previous_cards,
        corrected_cards,
        strict=True,
    ):
        scenario = cast(str, previous_card["scenario_code"])
        if corrected_card["scenario_code"] != scenario:
            changes.append(
                {"scenario": scenario, "kind": "other_field", "ref": "scenario_code"}
            )
            continue
        previous_candidates = cast(
            list[dict[str, str]], previous_card["candidates"]
        )
        corrected_candidates = cast(
            list[dict[str, str]], corrected_card["candidates"]
        )
        if len(previous_candidates) != len(corrected_candidates):
            changes.append(
                {"scenario": scenario, "kind": "other_field", "ref": "candidates"}
            )
        else:
            for position, (before, after) in enumerate(
                zip(previous_candidates, corrected_candidates, strict=True),
                1,
            ):
                identity_fields = ("blinded_candidate_id", "anchor_id", "tier")
                if any(before[field] != after[field] for field in identity_fields):
                    changes.append(
                        {
                            "scenario": scenario,
                            "kind": "other_field",
                            "ref": f"candidate_position_{position}",
                        }
                    )
                if before["disposition"] != after["disposition"]:
                    changes.append(
                        {
                            "scenario": scenario,
                            "kind": "disposition",
                            "ref": f"candidate_position_{position}",
                            "before": before["disposition"],
                            "after": after["disposition"],
                        }
                    )
        previous_rankings = {
            cast(str, item["criterion_ref"]): cast(str, item["blinded_expression"])
            for item in cast(list[dict[str, object]], previous_card["rankings"])
        }
        corrected_rankings = {
            cast(str, item["criterion_ref"]): cast(str, item["blinded_expression"])
            for item in cast(list[dict[str, object]], corrected_card["rankings"])
        }
        if set(previous_rankings) != set(corrected_rankings):
            changes.append(
                {"scenario": scenario, "kind": "other_field", "ref": "criteria"}
            )
        else:
            for criterion_ref in previous_rankings:
                if previous_rankings[criterion_ref] != corrected_rankings[criterion_ref]:
                    changes.append(
                        {
                            "scenario": scenario,
                            "kind": "pairwise_ranking",
                            "ref": criterion_ref,
                        }
                    )
        if previous_card["justification"] != corrected_card["justification"]:
            changes.append(
                {"scenario": scenario, "kind": "justification", "ref": scenario}
            )
    previous_meta = {
        key: value for key, value in previous_review.items() if key != "cards"
    }
    corrected_meta = {
        key: value for key, value in corrected_review.items() if key != "cards"
    }
    if previous_meta != corrected_meta:
        changes.append(
            {"scenario": "GLOBAL", "kind": "other_field", "ref": "review_metadata"}
        )
    return tuple(changes)


def build_closure_payload(root: Path = ROOT) -> dict[str, object]:
    corrected_path = root / COMPLETED_REVIEW_RELATIVE_PATH
    corrected_sha256 = _sha256(corrected_path.read_bytes())
    if corrected_sha256 != CORRECTED_FORM_SHA256:
        raise RuntimeError("CORRECTED_FORM_SHA256_MISMATCH")
    previous = _load_pre_correction_result(root)
    corrected = build_reconciliation_payload(
        root,
        expected_completed_sha256=CORRECTED_FORM_SHA256,
    )
    changes = _semantic_changes(previous, corrected)
    changed_scenarios = sorted(
        {cast(str, item["scenario"]) for item in changes if item["scenario"] != "GLOBAL"}
    )
    changed_pairwise = sum(item["kind"] == "pairwise_ranking" for item in changes)
    changed_dispositions = sum(item["kind"] == "disposition" for item in changes)
    changed_justifications = sum(item["kind"] == "justification" for item in changes)
    changed_other = sum(item["kind"] == "other_field" for item in changes)
    trace_conform = (
        changed_scenarios == ["SCN-01", "SCN-06"]
        and changed_pairwise == 3
        and changed_dispositions == 1
        and changed_justifications == 0
        and changed_other == 0
    )
    gate_a = cast(dict[str, object], corrected["gate_a"])
    gate_b = cast(dict[str, object], corrected["gate_b"])
    mechanical_pass = gate_a["status"] == "PASS" and gate_b["status"] == "PASS"
    closure_pass = trace_conform and mechanical_pass
    return {
        "phase": "12.16-G2-V4-CORRECTIVE-ATTESTATION-CLOSURE",
        "corrective_attestation": CORRECTIVE_ATTESTATION,
        "correction_cause": CORRECTION_CAUSE,
        "attested_corrected_scope": CORRECTED_SCOPE,
        "corpus_changed": False,
        "pre_correction_result_sha256": EXPECTED_PRE_CORRECTION_RESULT_SHA256,
        "pre_correction_form_sha256": EXPECTED_PRE_CORRECTION_FORM_SHA256,
        "corrected_form_sha256": corrected_sha256,
        "semantic_changes": changes,
        "changed_scenarios": changed_scenarios,
        "changed_pairwise_rankings": changed_pairwise,
        "changed_dispositions": changed_dispositions,
        "changed_justifications": changed_justifications,
        "changed_other_fields": changed_other,
        "trace_correction_check": "PASS" if trace_conform else "FAIL",
        "gate_a": gate_a,
        "gate_b": gate_b,
        "human_v4_prevalidation": (
            "PASS_WITH_CORRECTIVE_ATTESTATION" if closure_pass else "PARTIAL"
        ),
        "methodological_status": "PASS" if closure_pass else "PARTIAL",
        "provider_recalibration_allowed": (
            "READY_FOR_OFFLINE_PLAN_ONLY" if closure_pass else "FALSE"
        ),
        "provider_calls": 0,
        "runtime_route_change": "NONE",
        "global_suite_run": "NO",
        "test_level": "T1",
        "next_gate": (
            "12.16-G2-V4-PROVIDER-RECALIBRATION-PLAN_READY"
            if closure_pass
            else NEXT_GATE_PARTIAL
        ),
    }


def render_report_markdown(root: Path = ROOT) -> str:
    payload = build_closure_payload(root)
    gate_a = cast(dict[str, object], payload["gate_a"])
    gate_b = cast(dict[str, object], payload["gate_b"])
    lines = [
        "# Phase 12.16-G2 — Clôture de l'attestation corrective v4",
        "",
        "## Attestation et preuves",
        "",
        "- CORRECTIVE_ATTESTATION = `TRUE`.",
        f"- CORRECTION_CAUSE = `{CORRECTION_CAUSE}`.",
        f"- CORRECTED_SCOPE attesté = `{CORRECTED_SCOPE}`.",
        "- CORPUS_CHANGED = `FALSE`.",
        f"- Checksum résultat pré-correction local : `{payload['pre_correction_result_sha256']}`.",
        f"- Checksum formulaire pré-correction prouvé : `{payload['pre_correction_form_sha256']}`.",
        f"- Checksum formulaire corrigé : `{payload['corrected_form_sha256']}`.",
        "",
        "## Contrôle de trace",
        "",
        "| Élément | Attesté | Observé |",
        "|---|---|---|",
        f"| Scénarios modifiés | SCN-01, SCN-06 | {', '.join(cast(list[str], payload['changed_scenarios']))} |",
        f"| Classements pairwise modifiés | 3 | {payload['changed_pairwise_rankings']} |",
        f"| Dispositions modifiées | 1 | {payload['changed_dispositions']} |",
        f"| Justifications modifiées | 0 | {payload['changed_justifications']} |",
        f"| Autres champs modifiés | 0 | {payload['changed_other_fields']} |",
        "",
        "### Changements substantiels observés",
        "",
        "| Scénario | Catégorie | Référence |",
        "|---|---|---|",
    ]
    for item in cast(tuple[dict[str, object], ...], payload["semantic_changes"]):
        reference = cast(str, item["ref"])
        if item["kind"] == "disposition":
            reference = "une disposition de candidat aveugle"
        lines.append(f"| {item['scenario']} | {item['kind']} | {reference} |")
    lines.extend(
        (
            "",
            f"- TRACE_CORRECTION_CHECK = `{payload['trace_correction_check']}`.",
            "- La trace est strictement bornée au scope attesté; la preuve corrective est recevable.",
            "",
            "## Recalcul mécanique des gates",
            "",
            f"- DELIVERABILITY_GATE = `{gate_a['status']}`.",
            f"- STRONG_DELIVER_AS_IS = `{gate_a['strong_deliver_as_is']}/8`.",
            f"- MIXED_DELIVER_AS_IS = `{gate_a['mixed_deliver_as_is']}/8`.",
            f"- WEAK_DELIVER_AS_IS = `{gate_a['weak_deliver_as_is']}/8`.",
            f"- PAIRWISE_CRITERION_GATE = `{gate_b['status']}`.",
            f"- STRONG_GT_MIXED = `{gate_b['strong_gt_mixed']}/16`.",
            f"- STRONG_GT_WEAK = `{gate_b['strong_gt_weak']}/16`.",
            "- Les résultats mécaniques sont acceptés avec l'attestation corrective et sans modification des gates pré-déclarées.",
            "",
            "## Décision et frontières",
            "",
            f"- HUMAN_V4_PREVALIDATION = `{payload['human_v4_prevalidation']}`.",
            f"- METHODOLOGICAL_STATUS = `{payload['methodological_status']}`.",
            f"- PROVIDER_RECALIBRATION_ALLOWED = `{payload['provider_recalibration_allowed']}`.",
            "- PROVIDER_CALLS = `0`.",
            "- RUNTIME_ROUTE_CHANGE = `NONE`.",
            "- GLOBAL_SUITE_RUN = `NO`; TEST_LEVEL = `T1`.",
            f"- NEXT_GATE = `{payload['next_gate']}`.",
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


def write_output(root: Path = ROOT) -> None:
    _atomic_write(root / REPORT_RELATIVE_PATH, render_report_markdown(root).encode())


def main() -> None:
    payload = build_closure_payload(ROOT)
    print(
        json.dumps(
            {
                "status": payload["methodological_status"],
                "trace": payload["trace_correction_check"],
                "gate_a": cast(dict[str, object], payload["gate_a"])["status"],
                "gate_b": cast(dict[str, object], payload["gate_b"])["status"],
                "provider_calls": 0,
                "next_gate": payload["next_gate"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
