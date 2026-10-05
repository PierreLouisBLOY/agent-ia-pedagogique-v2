"""Institutional claims require admitted A evidence, independently of content quality."""

import re
from collections.abc import Mapping

from backend.modules.knowledge_reference.contracts.dto.admitted_institutional_sources import (
    ADMITTED_DOCUMENTS,
    OWNER_ADMISSION_SHA256,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    as_plain,
    fingerprint,
    items,
    object_data,
)

CLAIMS = re.compile(
    r"conforme.{0,25}(?:programme|référentiel)|(?:au|dans le) programme officiel|"
    r"capacité officielle|compétence du référentiel|officiellement (?:citée|prescrite)|"
    r"(?:BTS\s*CG\s*[12]|première année|deuxième année).{0,35}(?:officiellement|prescri[tp])",
    re.I,
)


def alignment_axes(resolution: object) -> dict[str, str]:
    data = object_data(resolution) if isinstance(resolution, Mapping) else {}
    doc = object_data(data.get("document_provenance", {}))
    admitted = (
        data.get("status") == "RESOLVED_ADMITTED"
        and data.get("owner_admission_sha256") == OWNER_ADMISSION_SHA256
        and ADMITTED_DOCUMENTS.get(str(doc.get("candidate_id"))) == doc.get("sha256")
        and re.fullmatch(r"[a-f0-9]{64}", str(data.get("qualification_sha256"))) is not None
    )
    links = items(data.get("attachments", []), 128)
    implicit = any(r.get("disposition") == "VERIFIED_IMPLICIT" for r in links)
    return {
        "disciplinary_accuracy": "NOT_ASSESSED",
        "institutional_alignment": "VERIFIED_IMPLICIT" if admitted and implicit else "VERIFIED_EXPLICIT" if admitted else "UNVERIFIED",
        "pedagogical_adaptation": "HUMAN_REVIEW_REQUIRED",
        "provenance": "ADMITTED_A_EXACT_SCOPE" if admitted else "UNVERIFIED",
        "authority_claims": "IMPLICIT_NOT_OFFICIAL_CITATION" if admitted and implicit else "A_EVIDENCE_REQUIRED",
    }


def require_supported_claims(text: str, resolution: object) -> None:
    if not CLAIMS.search(text):
        return
    axes = alignment_axes(resolution)
    if axes["institutional_alignment"] == "UNVERIFIED":
        raise ValueError("PROGRAM_ALIGNMENT_UNVERIFIED_HUMAN_REVIEW_REQUIRED")
    if axes["institutional_alignment"] == "VERIFIED_IMPLICIT" and re.search(
        r"officiellement citée|notion[s]? (?:officiellement |explicitement )citée[s]?", text, re.I
    ):
        raise ValueError("PROGRAM_ALIGNMENT_IMPLICIT_NOT_OFFICIAL_CITATION")
    if re.search(r"(?:BTS\s*CG\s*[12]|première année|deuxième année).{0,35}(?:officiellement|prescri[tp])", text, re.I):
        raise ValueError("PROGRAM_ALIGNMENT_BTS_YEAR_IS_LOCAL")


def authority_layers(resolution: object, passages: list[dict[str, object]], local: object) -> dict[str, object]:
    data = object_data(resolution) if isinstance(resolution, Mapping) else {}
    admitted = alignment_axes(data)["institutional_alignment"] != "UNVERIFIED"
    # Old reference contracts do not state B/C admission. Preserve their text,
    # but keep it in unclassified local context rather than promote it to A/B.
    return object_data(as_plain({
        "authority_layers_contract": "PROGRAM-AUTHORITY-LAYERS-1.0",
        "institutional_evidence": [data] if admitted else [],
        "disciplinary_evidence": [],
        "pedagogical_evidence": [],
        "generated_or_local_context": {"selected_passages": passages, "local_progression": as_plain(local)},
        "content_authority_status": "B_C_NOT_ATTESTED_BY_LEGACY_REFERENCE_CONTRACT",
        "review_axes": alignment_axes(data),
    }))


def bounded_institutional_evidence(resolution: object) -> dict[str, object]:
    """Content-only view; the full immutable proof stays in Application."""
    data = object_data(resolution)
    def selected(row: object, keys: tuple[str, ...]) -> dict[str, object]:
        value = object_data(row)
        return {key: as_plain(value[key]) for key in keys if key in value}

    element_keys = ("id", "element_type", "official_code", "official_label", "official_text",
        "document_reference_id", "page", "page_end", "locator", "label", "capacity_ref")
    def element_view(row: object, *, theme: bool = False) -> dict[str, object]:
        value = selected(row, element_keys)
        # The selected question/competency carries the actual prescription.
        # Whole-theme background is committed by hash, not duplicated here.
        if theme or value.get("official_text") == value.get("official_label"):
            value.pop("official_text", None)
        return value

    links = []
    for row in items(data["attachments"], 128):
        value = selected(row, ("id", "notion_ref", "element_ref", "disposition",
            "notion_id", "framework_element_id", "attachment_type"))
        value["full_attachment_sha256"] = fingerprint(row)
        if row.get("disposition") == "VERIFIED_IMPLICIT":
            value["justification"] = row["justification"]
        links.append(value)
    return {
        "contract_id": "BOUNDED-INSTITUTIONAL-EVIDENCE-1.0", "full_resolution_sha256": fingerprint(data),
        "status": data["status"], "program_ref": data["program_ref"], "program_version": data["program_version"],
        "version_label": data["version_label"], "qualification_sha256": data.get("qualification_sha256"),
        "owner_admission_sha256": data.get("owner_admission_sha256"),
        "document": selected(data.get("document_provenance", {}), ("id", "candidate_id", "title", "url", "sha256", "publication_date", "provenance")),
        "elements": [element_view(data[key], theme=key == "theme") for key in ("theme", "question", "process", "activity") if data.get(key) is not None],
        "capacities_or_competencies": [element_view(row) for key in ("capacities", "competencies") for row in items(data.get(key, []), 16)],
        "limits": [element_view(row) for row in items(data.get("limits", []), 32)],
        "notions": [selected(row, ("notion_ref", "label")) for row in items(data["notions"], 16)],
        "attachments": links,
        "depth_authority": data.get("depth_authority"), "official_depth": data.get("official_depth"),
        "year_authority": data.get("year_authority"), "gaps": as_plain(data["gaps"]),
        "review_axes": alignment_axes(data), "teacher_acceptance": "NOT_PERFORMED",
    }
