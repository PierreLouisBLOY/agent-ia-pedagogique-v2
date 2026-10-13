"""Pure binding of declared COURSE content to immutable Application context.

No provider, HTTP, storage or filesystem authority. The provider authors content;
Application owns programme labels, capabilities, local identities and projections.
"""
from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from typing import cast

from backend.modules.pedagogical_context.contracts.dto.p0_context import P0Context
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    as_plain,
    items,
    nonempty,
    object_data,
)
from backend.modules.pedagogical_design.contracts.dto.course_chapter import (
    COURSE_LINEAGE_CONTRACT,
    COURSE_PRODUCTION_CONTRACT,
    CourseChapter,
)
from backend.modules.pedagogical_design.contracts.dto.p0_production import P0Production
from backend.modules.pedagogical_design.contracts.dto.program_authority import alignment_axes

RICH_CONTENT_FIELDS = {"title", "course_chapter", "limitations"}
CHAPTER_CONTENT_FIELDS = {"context", "documents", "parts", "questions", "concepts",
                          "knowledge_check", "transfer", "synthesis", "teacher_answers"}
LOCAL_CONSTRUCTION_SOURCE = "LOCAL_APPLICATION_CONSTRUCTION"
CANDIDATE_LIMITATION = "CANDIDATE — ressource non validée, à relire par l'enseignant avant usage."
_BINDINGS = ("production_ref", "version_ref", "context", "context_sha256", "references", "lineage")
_DISPATCH_FIELDS = {"contract_id", "evidence", *_BINDINGS}


def course_capability_rows(context: P0Context) -> list[dict[str, object]]:
    """Alias only the exact selected capacities; never accept provider authority."""
    if context.course_format != "CHAPTER" or context.institutional is None:
        raise ValueError("P0_RICH_COURSE_CONTEXT_REQUIRED")
    context.require_institutional_dispatch()
    selection = context.institutional
    resolution = object_data(context.data["institutional_resolution"])
    rows = items(resolution["capacities"], 16)
    by_ref = {str(row["capacity_ref"]): row for row in rows}
    selected = cast(tuple[str, ...], selection["capacity_refs"])
    if (not selected or len(by_ref) != len(rows)
            or set(by_ref) != set(selected)):
        raise ValueError("P0_RICH_COURSE_CAPABILITIES")
    admitted = alignment_axes(resolution)["institutional_alignment"] != "UNVERIFIED"
    result: list[dict[str, object]] = []
    for number, ref in enumerate(selected, 1):
        row = by_ref[ref]
        locator = row.get("locator") or row.get("document_reference_id")
        result.append({"id": "C" + str(number), "label": nonempty(row["label"], 2000),
                       "source_ref": ref, "locator": nonempty(locator, 2000),
                       "authority_status": "ADMITTED_A_EXACT_SCOPE" if admitted else "LOCAL_PROPOSED"})
    return result


def _header(context: P0Context) -> dict[str, object]:
    selection = context.institutional
    if selection is None:
        raise ValueError("P0_RICH_COURSE_CONTEXT_REQUIRED")
    resolution = object_data(context.data["institutional_resolution"])
    theme_ref = nonempty(selection["theme_ref"], 200)
    theme = resolution.get("theme")
    numeric_theme = re.fullmatch(r"theme:([0-9]+)", theme_ref)
    theme_label = (object_data(theme)["official_label"] if theme is not None
                   else "Thème " + numeric_theme[1] if numeric_theme is not None
                   else "Thème non renseigné")
    return {**{key: selection[key] for key in
               ("frame", "program_ref", "program_version", "theme_ref", "question_ref")},
            "theme_label": theme_label,
            "question_label": object_data(resolution["question"])["official_label"],
            "level_label": {"FIRST_STMG": "Première STMG", "FINAL_STMG": "Terminale STMG"}[
                str(context.data["level"])],
            "subject_label": context.data["discipline"]}


def bind_course_provider_content(request: Mapping[str, object],
                                 content: Mapping[str, object]) -> P0Production:
    """Materialize a complete rich chapter; never supply missing pedagogical text."""
    data = object_data(as_plain(request), _DISPATCH_FIELDS)
    if data["contract_id"] != "R6-P0-DISPATCH-1.0":
        raise ValueError("P0_DISPATCH_CONTRACT")
    context = P0Context(object_data(data["context"]))
    if context.sha256 != data["context_sha256"]:
        raise ValueError("P0_CONTEXT_HASH")
    proposed = object_data(as_plain(content), RICH_CONTENT_FIELDS)
    chapter_content = object_data(proposed["course_chapter"], CHAPTER_CONTENT_FIELDS)
    for field in ("documents", "parts", "questions", "concepts", "teacher_answers"):
        for row in items(chapter_content[field], 60):
            if re.fullmatch(r"[A-Z][A-Z0-9_-]{0,39}", str(row.get("id"))) is None:
                raise ValueError("P0_RICH_COURSE_CONTENT_ID")
    capabilities = course_capability_rows(context)
    progression = object_data(context.data["local_progression"])
    chapter_number = progression["chapter"]
    if (not isinstance(chapter_number, str)
            or re.fullmatch(r"[1-9][0-9]?", chapter_number) is None):
        raise ValueError("P0_RICH_COURSE_CHAPTER_NUMBER")
    references = items(data["references"], 8)
    by_evidence = {str(row["evidence_id"]): row for row in references}
    if not references or len(by_evidence) != len(references):
        raise ValueError("P0_EVIDENCE_BINDING")
    evidence = object_data(data["evidence"])
    if set(evidence) != set(by_evidence):
        raise ValueError("P0_EVIDENCE_BINDING")
    for ref in references:
        excerpt = evidence[str(ref["evidence_id"])]
        if (not isinstance(excerpt, str) or not excerpt
                or hashlib.sha256(excerpt.encode()).hexdigest() != ref["excerpt_sha256"]):
            raise ValueError("P0_EVIDENCE_HASH")

    documents: list[dict[str, object]] = []
    for row in items(chapter_content["documents"], 30):
        document = object_data(row, {"id", "title", "function", "text", "table", "provenance"})
        nonempty(document["title"], 200)
        nonempty(document["function"], 200)
        provenance = object_data(document["provenance"], {"kind", "evidence_id"})
        source = provenance["evidence_id"]
        if provenance["kind"] == "LOCAL_FICTION":
            if source is not None:
                raise ValueError("P0_RICH_COURSE_DOCUMENT_PROVENANCE")
            source_ref = LOCAL_CONSTRUCTION_SOURCE
        elif provenance["kind"] == "SUPPLIED_REFERENCE":
            if not isinstance(source, str) or source not in by_evidence:
                raise ValueError("P0_RICH_COURSE_REFERENCE_UNKNOWN")
            # The evidence identity binds the exact passage, even if two passages
            # share the same source_ref. Internal provenance is never diffused.
            source_ref = source
        else:
            raise ValueError("P0_RICH_COURSE_DOCUMENT_PROVENANCE")
        documents.append({**document, "provenance": {"kind": provenance["kind"], "source_ref": source_ref}})
    topics = cast(tuple[str, ...], context.data["topics"])
    if any(row["notion"] not in topics for row in items(chapter_content["concepts"], 30)):
        raise ValueError("P0_RICH_COURSE_NOTION_UNKNOWN")
    chapter = CourseChapter({"contract_id": COURSE_LINEAGE_CONTRACT,
        "chapter_number": int(chapter_number), "title": proposed["title"],
        "program_header": _header(context), "capabilities": capabilities, "notions": list(topics),
        **chapter_content, "documents": documents})
    chapter.bind_context(context)
    from backend.modules.pedagogical_design.contracts.dto.course_delivery import (
        validate_course_delivery,
    )

    validate_course_delivery(context, chapter.data, data["references"])
    limitations = proposed["limitations"]
    if not isinstance(limitations, (list, tuple)) or len(limitations) > 15:
        raise ValueError("P0_LIMITATIONS")
    for limit in limitations:
        nonempty(limit, 500)
    bound_limits = list(limitations)
    if not any("CANDIDATE" in str(limit) for limit in bound_limits):
        bound_limits.append(CANDIDATE_LIMITATION)
    return P0Production({"contract_id": COURSE_PRODUCTION_CONTRACT,
        **{key: data[key] for key in _BINDINGS}, "title": chapter.data["title"],
        "sections": chapter.sections(), "questions": [], "corrections": [], "marking": [],
        "course_chapter": as_plain(chapter.data), "limitations": bound_limits})
