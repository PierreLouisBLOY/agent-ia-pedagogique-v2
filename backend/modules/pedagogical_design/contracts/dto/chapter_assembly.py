"""Closed local assembly metadata; documentary verification is not promotion."""

from collections.abc import Mapping
from datetime import date
from typing import cast

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    as_plain,
    items,
    nonempty,
    object_data,
)
from backend.modules.resource_library.contracts.dto.format_reference import FormatReference

ASSEMBLY_CHAPTER_CONTRACT = "COURSE-CHAPTER-ASSEMBLY-5.0"
ASSEMBLY_PRODUCTION_CONTRACT = "R6-P0-PRODUCTION-LOCAL-CHAPTER-4.0"
ASSEMBLY_PROVENANCE = (
    "LOCAL_ORIGINAL_CHAPTER — assemblage local sans validation pédagogique attestée"
)


def validate_assembly(data: Mapping[str, object]) -> None:
    a = object_data(
        data["assembly"],
        {
            "thread",
            "parts",
            "question_links",
            "sources",
            "document_sources",
            "format_reference",
            "concept_vigilance",
            "answer_criteria",
        },
    )
    thread = object_data(a["thread"], {"organization", "nature", "notice", "source_ids"})
    nonempty(thread["organization"], 200)
    nonempty(thread["notice"], 1000)
    if thread["nature"] not in {"FICTION", "SOURCED_REAL"}:
        raise ValueError("ASSEMBLY_THREAD_NATURE")
    sources = items(a["sources"], 30)
    source_ids: set[str] = set()
    for s in sources:
        object_data(
            s,
            {
                "id",
                "title",
                "url",
                "publisher",
                "consulted_on",
                "locator",
                "fact",
                "rights",
                "authority_status",
            },
        )
        for k in ("id", "title", "publisher", "locator", "fact", "rights"):
            nonempty(s[k], 2000)
        if str(s["id"]) in source_ids:
            raise ValueError("ASSEMBLY_SOURCE_DUPLICATE")
        source_ids.add(str(s["id"]))
        date.fromisoformat(str(s["consulted_on"]))
        if s["authority_status"] == "PUBLIC_SOURCE_VERIFIED_NOT_RUNTIME_ADMITTED":
            if not isinstance(s["url"], str) or not s["url"].startswith("https://"):
                raise ValueError("ASSEMBLY_SOURCE_URL")
        elif s["authority_status"] != "LOCAL_ORIGINAL" or s["url"] is not None:
            raise ValueError("ASSEMBLY_SOURCE_AUTHORITY")

    def refs(value: object, allowed: set[str], required: bool = True) -> set[str]:
        if not isinstance(value, (tuple, list)) or not int(required) <= len(value) <= 60:
            raise ValueError("ASSEMBLY_LINK_LIST")
        if any(not isinstance(v, str) for v in value):
            raise ValueError("ASSEMBLY_LINK_TYPE")
        found = set(value)
        if len(found) != len(value) or not found <= allowed:
            raise ValueError("ASSEMBLY_LINK")
        return found

    refs(thread["source_ids"], source_ids, thread["nature"] == "SOURCED_REAL")
    public_ids = {
        str(source["id"])
        for source in sources
        if source["authority_status"] == "PUBLIC_SOURCE_VERIFIED_NOT_RUNTIME_ADMITTED"
    }
    if (
        thread["nature"] == "SOURCED_REAL"
        and not set(cast(tuple[str, ...], thread["source_ids"])) & public_ids
    ):
        raise ValueError("ASSEMBLY_REAL_SOURCE_REQUIRED")
    if thread["nature"] == "FICTION" and "fict" not in str(thread["notice"]).lower():
        raise ValueError("ASSEMBLY_FICTION_NOTICE")
    docs = {str(d["id"]): d for d in items(data["documents"])}
    concepts = {str(c["id"]): c for c in items(data["concepts"])}
    questions = {str(q["id"]): q for q in items(data["questions"], 60)}
    parts = items(data["parts"], 8)
    metadata = items(a["parts"], 8)
    if [m.get("id") for m in metadata] != [p["id"] for p in parts]:
        raise ValueError("ASSEMBLY_PART_ORDER")
    used_docs: set[str] = set()
    used_concepts: set[str] = set()
    for p, m in zip(parts, metadata, strict=True):
        object_data(m, {"id", "transition", "formalization"})
        nonempty(m["transition"], 2000)
        formal = object_data(m["formalization"], {"position", "reason"})
        if formal["position"] not in {"AFTER_ANALYSIS", "BEFORE_ACTIVITY"}:
            raise ValueError("ASSEMBLY_FORMALIZATION")
        nonempty(formal["reason"], 1000)
        pdocs = refs(p["document_ids"], set(docs))
        pconcepts = refs(p["concept_ids"], set(concepts))
        if not 1 <= len(pconcepts) <= 2:
            raise ValueError("ASSEMBLY_PRIORITY_NOTIONS")
        activity = [
            q
            for role in ("observation", "analysis", "reinvestment")
            for q in cast(tuple[str, ...], p[role])
        ]
        if not activity:
            raise ValueError("ASSEMBLY_EMPTY_PART")
        for q in activity:
            if not set(cast(tuple[str, ...], questions[q]["document_ids"])) <= pdocs:
                raise ValueError("ASSEMBLY_QUESTION_PART_DOCUMENT")
        used_docs |= pdocs
        used_concepts |= pconcepts
    used_docs |= set(cast(tuple[str, ...], object_data(data["transfer"])["document_ids"]))
    if used_docs != set(docs) or used_concepts != set(concepts):
        raise ValueError("ASSEMBLY_ORPHAN")
    if {str(c["notion"]) for c in concepts.values()} != set(cast(tuple[str, ...], data["notions"])):
        raise ValueError("ASSEMBLY_NOTION_COVERAGE")
    links = items(a["question_links"], 60)
    if [link.get("id") for link in links] != list(questions):
        raise ValueError("ASSEMBLY_QUESTION_LINK_COVERAGE")
    used_caps: set[str] = set()
    for link in links:
        object_data(link, {"id", "concept_ids"})
        linked = refs(link["concept_ids"], set(concepts))
        for part in parts:
            if link["id"] in [
                q
                for role in ("observation", "analysis", "reinvestment")
                for q in cast(tuple[str, ...], part[role])
            ]:
                if not linked <= set(cast(tuple[str, ...], part["concept_ids"])):
                    raise ValueError("ASSEMBLY_QUESTION_PART_CONCEPT")
        used_caps |= set(cast(tuple[str, ...], questions[str(link["id"])]["capability_ids"]))
    if used_caps != {str(c["id"]) for c in items(data["capabilities"])}:
        raise ValueError("ASSEMBLY_CAPABILITY_COVERAGE")
    ledger = items(a["document_sources"], 30)
    if [s.get("id") for s in ledger] != list(docs):
        raise ValueError("ASSEMBLY_DOCUMENT_SOURCE_COVERAGE")
    for s in ledger:
        object_data(s, {"id", "nature", "source_ids", "limits"})
        nonempty(s["nature"], 300)
        nonempty(s["limits"], 1000)
        selected = refs(s["source_ids"], source_ids)
        provenance = object_data(docs[str(s["id"])]["provenance"])
        if str(provenance["source_ref"]) not in selected:
            raise ValueError("ASSEMBLY_PROVENANCE_LEDGER_BINDING")
        if provenance["kind"] == "LOCAL_FICTION" and (
            s["nature"] != "Situation fictive originale" or not selected.isdisjoint(public_ids)
        ):
            raise ValueError("ASSEMBLY_FICTION_SOURCE_BINDING")
        if (
            provenance["kind"] == "SUPPLIED_REFERENCE"
            and str(provenance["source_ref"]) not in public_ids
        ):
            raise ValueError("ASSEMBLY_REAL_SOURCE_REQUIRED")
        if "document construit" in str(docs[str(s["id"])]["title"]).lower():
            raise ValueError("ASSEMBLY_DOCUMENT_LABEL")
    for key, target, field in (
        ("concept_vigilance", list(concepts), "text"),
        ("answer_criteria", list(questions), "criteria"),
    ):
        rows = items(a[key], 60)
        if [r.get("id") for r in rows] != target:
            raise ValueError("ASSEMBLY_TEACHER_COVERAGE")
        for r in rows:
            object_data(r, {"id", field})
            nonempty(r[field], 2000)
    fmt = object_data(a["format_reference"], {"record", "version_ref"})
    record = FormatReference(as_plain(fmt["record"]))
    if (
        fmt["version_ref"] != record.version_ref
        or record.reference_id != "V2-FORMAT-COURS-STMG-001"
        or record.as_dict()["source_sha256"]
        != "31c14d3dac56e4a8dccc48bd8afee99594bb81fefafd07c3a828ff5ed54651ae"
    ):
        raise ValueError("ASSEMBLY_FORMAT_IDENTITY")


def assembly_projection(value: object, *, teacher: bool) -> dict[str, object]:
    a = object_data(value)
    if teacher:
        return a
    thread = object_data(a["thread"])
    return {
        "thread": {k: thread[k] for k in ("organization", "nature", "notice")},
        "parts": [
            {
                "id": p["id"],
                "transition": p["transition"],
                "formalization": {"position": object_data(p["formalization"])["position"]},
            }
            for p in items(a["parts"], 8)
        ],
        "concept_vigilance": a["concept_vigilance"],
    }
