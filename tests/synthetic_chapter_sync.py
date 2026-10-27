"""Independent technical cases; never the private chapter 321 or its golden output."""

from backend.adapters.inbound.application.chapter_assembly import ChapterAssemblyInbound
from backend.modules.pedagogical_design.application.commands.assemble_chapter import AssembleChapter
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import as_plain
from backend.modules.pedagogical_design.contracts.dto.chapter_assembly import (
    ASSEMBLY_CHAPTER_CONTRACT,
    ASSEMBLY_PROVENANCE,
)
from backend.modules.resource_library.contracts.dto.format_reference import FormatReference
from tests.unit.test_course_chapter import chapter_data, child_fixture


def format_metadata():
    # The pinned public source identity exercises the contract only. No document,
    # owner decision, registration or operational admission is supplied by tests.
    return FormatReference({
        "schema": "FORMAT-REFERENCE-1.0", "reference_id": "V2-FORMAT-COURS-STMG-001",
        "title": "Metadata for independent synthetic qualification", "document_type": "cours_version_eleve",
        "level": "Première STMG", "scope": {"approved_for": ["format"], "excluded": ["teacher", "third_party_media"]},
        "approval_status": "OWNER_APPROVED_REFERENCE", "decision_date": "2026-10-24",
        "decision_sha256": "a" * 64,
        "source_sha256": "31c14d3dac56e4a8dccc48bd8afee99594bb81fefafd07c3a828ff5ed54651ae",
        "size_bytes": 1, "storage_ref": "format-reference:V2-FORMAT-COURS-STMG-001/document.docx",
        "provenance": {"kind": "OWNER_PROVIDED_DOCX", "filename": "synthetic-metadata-only.docx",
                       "decision_ref": "owner-decision:" + "a" * 64},
        "media_policy": "NO_REDISTRIBUTION_WITHOUT_RIGHTS",
    })


def blueprint():
    _, original = child_fixture()
    parent = original.p0_bundle
    context = parent.context.as_dict()
    chapter = chapter_data(context)
    chapter["contract_id"] = ASSEMBLY_CHAPTER_CONTRACT
    metadata = format_metadata()
    chapter["assembly"] = {
        "thread": {"organization": "Atelier fictif de test", "nature": "FICTION",
                   "notice": "Situation fictive indépendante de qualification technique.", "source_ids": []},
        "parts": [{"id": "I", "transition": "Relier les indices synthétiques.",
                   "formalization": {"position": "AFTER_ANALYSIS", "reason": "Qualification technique."}}],
        "question_links": [{"id": "Q" + str(i), "concept_ids": ["N1"]} for i in range(1, 6)],
        "sources": [{"id": "unit:fiction", "title": "Independent synthetic test data", "url": None,
                     "publisher": "Synthetic fixture", "consulted_on": "2026-10-27", "locator": "unit:fiction",
                     "fact": "Situation de test inventée, aucune observation réelle.",
                     "rights": "Synthetic technical data, no third-party media.", "authority_status": "LOCAL_ORIGINAL"}],
        "document_sources": [{"id": "D1", "nature": "Situation fictive originale", "source_ids": ["unit:fiction"],
                              "limits": "Aucune donnée réelle ni recette pédagogique."}],
        "format_reference": {"record": metadata.as_dict(), "version_ref": metadata.version_ref},
        "concept_vigilance": [{"id": "N1", "text": "Cas synthétique, aucune généralisation."}],
        "answer_criteria": [{"id": "Q" + str(i), "criteria": "Un indice synthétique justifié."} for i in range(1, 6)],
    }
    references = as_plain(parent.data["references"])
    for ref in references:
        ref["provenance_label"] = ASSEMBLY_PROVENANCE
    lineage = as_plain(parent.data["lineage"])
    lineage["parent_version_ref"] = None
    return {"schema": "LOCAL-CHAPTER-BLUEPRINT-1.0",
            "identity": {"production_ref": parent.production_ref, "version_ref": "ver:" + "e" * 32, "lineage": lineage},
            "context": context, "chapter": chapter, "references": references,
            "limitations": ["CANDIDATE — independent synthetic technical case, not chapter 321 or an owner acceptance."]}


def prepare():
    return ChapterAssemblyInbound(AssembleChapter()).prepare(blueprint(), {})
