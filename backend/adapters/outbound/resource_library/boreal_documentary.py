"""Bounded local reading of the exact historical Boréal artifacts; no provider SDK."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

from backend.infrastructure.filesystem import read_file_nofollow
from backend.modules.pedagogical_context.contracts.dto.conversation_context import (
    ConfirmedConversationContext,
)
from backend.modules.pedagogical_design.contracts.dto.conversation_draft import (
    LOCAL_REFERENCE_LABEL,
    ConversationDraft,
    ConversationDraftRequest,
)
from backend.modules.work_orchestration.contracts.dto.production_read_view import ProductionReadView
from backend.modules.work_orchestration.contracts.dto.saved_production import SavedProduction

OUTPUT_SHA = "b57333dcfc5dfd48cd3339742836884acf3e11802e89f69ac98cab3843d918e2"
RESPONSE_SHA = "693c199e17abef6ffdb8d380bf34e28fc296ab26261a995c9b672f3b102f6710"
INVENTORY_SHA = "8a24171885332475a9e4d7cd179f03ad4a423c0e798a85611f14cd18f04379c4"
REQUEST_FILE_SHA = "4f985743bdb707d8848516fcf763efd3c40a9eb12b751c62c8067bd020a0deb9"
REQUEST_SHA = "911383eb0be5ca3bd6ef11d90909b02ad3b52d855796d9e7d8f81d254b8d69fc"


def _read(path: Path, expected: str) -> dict[str, Any]:
    raw = read_file_nofollow(path, allowed_root=path.parent, maximum_bytes=512 * 1024)
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("BOREAL_DOCUMENTARY_HASH_MISMATCH")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("BOREAL_DOCUMENTARY_SHAPE_REJECTED")
    return cast(dict[str, Any], value)


def normalize_boreal_documentary(
    artifact_root: Path, scope_root: Path,
) -> tuple[SavedProduction, dict[str, object]]:
    output = _read(artifact_root / "generated_output_structured.json", OUTPUT_SHA)
    response = _read(artifact_root / "provider_response_raw.json", RESPONSE_SHA)
    inventory = _read(scope_root / "60_ATELIER_BOREAL_SOURCE_INVENTORY.json", INVENTORY_SHA)
    request = _read(scope_root / "61_ATELIER_BOREAL_GENERATION_REQUEST.json", REQUEST_FILE_SHA)
    encoded_request = json.dumps(request, ensure_ascii=False, sort_keys=True,
                                 separators=(",", ":")).encode()
    if hashlib.sha256(encoded_request).hexdigest() != REQUEST_SHA:
        raise ValueError("BOREAL_DOCUMENTARY_REQUEST_MISMATCH")
    projected = json.loads(request["input"])
    references = inventory["selected_references"]
    supplied = projected["resolved_inputs"]["evidence"]
    if not inventory["correction_and_marking_excluded_from_provider_input"]:
        raise ValueError("BOREAL_DOCUMENTARY_TEACHER_INPUT_REJECTED")
    if len(supplied) != len(references) or any(
        (r["source_ref"], r["locator"], r["version_or_checksum"], r["excerpt"])
        != (e["source_ref"], e["locator"], e["version_or_checksum"], e["text"])
        for r, e in zip(references, supplied, strict=True)
    ):
        raise ValueError("BOREAL_DOCUMENTARY_REFERENCE_MISMATCH")
    output_texts = [c.get("text") for item in response.get("output", [])
                    for c in item.get("content", []) if c.get("type") == "output_text"]
    if not any(json.loads(t) == output for t in output_texts if isinstance(t, str)):
        raise ValueError("BOREAL_DOCUMENTARY_RESPONSE_MISMATCH")
    # The historical ID is shared by three passages. Retain it as an aggregate,
    # with an explicit constituent map, rather than falsely selecting one passage.
    grouped: dict[str, list[dict[str, Any]]] = {}
    for ref in references:
        grouped.setdefault(ref["evidence_id"], []).append(ref)
    if set(output["evidence_ids_used"]) - set(grouped):
        raise ValueError("BOREAL_DOCUMENTARY_UNRESOLVED_LINEAGE")
    mapped = []
    for evidence_id, members in grouped.items():
        digest = hashlib.sha256(json.dumps(members, sort_keys=True, ensure_ascii=False,
                                           separators=(",", ":")).encode()).hexdigest()
        mapped.append({"evidence_id": evidence_id, "source_ref": "boreal:reference-aggregate",
            "version_ref": "boreal:references-v2", "checksum_sha256": digest,
            "locator": "aggregate:" + digest, "provenance_label": LOCAL_REFERENCE_LABEL,
            "declared_used": evidence_id in output["evidence_ids_used"]})
    context = ConfirmedConversationContext(projected["pedagogical_context"])
    request_id, conversation_id = "req:" + REQUEST_SHA[:32], "conv:" + OUTPUT_SHA[:32]
    draft_request = ConversationDraftRequest(request_id, conversation_id,
        "gen:" + OUTPUT_SHA[:32], "Import documentaire de la sortie historique Atelier Boréal.", context)
    draft = ConversationDraft("prod:" + OUTPUT_SHA[:32],
        "\n\n".join(section["text"] for section in output["sections"]),
        tuple({"section_id": s["code"], "text": s["text"]} for s in output["sections"]),
        tuple(mapped), {"source_run_id": "documentary:" + RESPONSE_SHA[:32],
            "source_step_id": projected["source_step_id"],
            "evidence_set_ref": "documentary-selection:" + INVENTORY_SHA[:32]},
        ("FICTIF — application guidée admise ; aucune acceptation enseignante présumée.",
         "Projection documentaire du sujet historique ; corrigé et barème de référence séparés.",
         "Les références historiques partagent un identifiant agrégé ; détails dans la matrice.",
         "Aucune autorité, session ou autorisation live restaurée."))
    view = ProductionReadView.from_draft(draft, draft_request, "ver:" + OUTPUT_SHA[32:])
    record = SavedProduction({"contract_id": "SAVED-PRODUCTION-1.0", "view": dict(view.data),
        "bundle": None, "reviews": [], "validations": [], "origin": "IMPORTED_DOCUMENTARY",
        "provenance": {"ORIGINAL_OUTPUT": OUTPUT_SHA, "ORIGINAL_RESPONSE": RESPONSE_SHA,
            "GENERATION_REQUEST": REQUEST_SHA, "SOURCE_INVENTORY": INVENTORY_SHA},
        "reservations": list(draft.limitations)})
    return record, {"schema": "BOREAL-DOCUMENTARY-MAPPING-1.0",
        "status": "MAPPED_AGGREGATE_NOT_INDIVIDUAL_ATTRIBUTION",
        "constituents": [{k: r[k] for k in ("case_reference_id", "evidence_id", "source_ref",
            "locator", "version_or_checksum", "excerpt_sha256")} for r in references],
        "normalized_record_sha256": record.sha256, "original_output_sha256": OUTPUT_SHA,
        "production_ref": record.production_ref, "version_ref": record.version_ref,
        "provider_calls": 0, "count_calls": 0, "teacher_accepted": False,
        "solving_score": None, "correction_and_marking": "SEPARATE_OWNER_REFERENCE"}
