"""Synthetic institutional proof on a fresh authenticated CP645 test copy.

The pinned source hashes exercise verification shape only. No public PDF bytes
are supplied or verified here. None of these synthetic prescriptions constitutes
an admission for the product or the teacher. No production module imports this.
"""
import hashlib
import shutil

from backend.adapters.inbound.application.institutional_qualification import (
    InstitutionalQualificationInbound,
)
from backend.adapters.outbound.persistence.migrations import CANONICAL_SEED_SHA256
from backend.adapters.outbound.persistence.sqlite import connect_sqlite
from backend.adapters.outbound.resource_library.institutional_qualification_sqlite import (
    SQLiteInstitutionalQualificationAdapter,
)
from backend.infrastructure.composition.factories.institutional_catalog import (
    inspect_institutional_catalog,
)
from backend.infrastructure.composition.factories.local_browser import Read15RuntimeTarget
from backend.infrastructure.composition.factories.r6_all_notions import exact_notion_evidence
from backend.infrastructure.filesystem import ensure_private_directory
from backend.modules.knowledge_reference.application.commands.admit_institutional_qualification import (
    AdmitInstitutionalQualification,
)
from backend.modules.knowledge_reference.contracts.dto.admitted_institutional_sources import (
    ADMITTED_DOCUMENTS,
    OWNER_ADMISSION_SHA256,
)
from backend.modules.knowledge_reference.contracts.dto.stmg_frames import STMG_FRAMES


def build_test_target(seed, root):
    original = Read15RuntimeTarget(seed, seed.parent, CANONICAL_SEED_SHA256)
    catalog = inspect_institutional_catalog(original, read=True)
    notion_ref = "notion:absence"
    canonical = [row for row in catalog["notion"] if row["identity_status"] == "CANONICAL"]
    assert len(canonical) == 628 and any(row["id"] == notion_ref for row in canonical)
    frameworks = {row["code"]: row["id"] for row in catalog["official_framework"]}
    data = {"contract_id": "INSTITUTIONAL-QUALIFICATION-1.0", "owner_decision_sha256": OWNER_ADMISSION_SHA256,
            "documents": [], "versions": [], "elements": [], "attachments": [], "notions": [], "regulatory_context": []}
    selections = {}
    for frame, candidate in (("MANAGEMENT_PREMIERE", "A01"), ("MSDGN_TERMINALE_COMMON", "A03"), ("BTS", "A04B")):
        bts = frame == "BTS"
        code = "BTS CG - Annexe I" if bts else STMG_FRAMES[frame][5]
        version = "version:http-test-" + frame
        doc = "document:http-test-" + frame
        theme, question, capacity, knowledge = ["element:http-test-" + frame + "-" + name
                                              for name in ("theme", "question", "capacity", "knowledge")]
        data["documents"].append({"id": doc, "candidate_id": candidate, "title": "SYNTHETIC HTTP TEST SOURCE",
            "url": "https://example.test/institutional-http/" + frame, "sha256": ADMITTED_DOCUMENTS[candidate],
            "publication_date": "2026-10-06", "source_ref": "source:http-test-" + frame,
            "source_name": "SYNTHETIC HTTP TEST INSTITUTION", "provenance": "TEST_FIXTURE_ONLY_NO_PUBLIC_BYTES", "pages": 1})
        data["versions"].append({"id": version, "framework_ref": frameworks[code], "frame": code,
            "version_label": "SYNTHETIC-HTTP-V1", "publication_date": "2026-10-06", "document_ref": doc})
        for position, (ref, kind, parent) in enumerate(((theme, "PROCESS" if bts else "THEME", None),
                (question, "ACTIVITY" if bts else "QUESTION", theme),
                (capacity, "COMPETENCY" if bts else "CAPACITY", question), (knowledge, "KNOWLEDGE", question)), 1):
            data["elements"].append({"id": ref, "version_ref": version, "parent_ref": parent, "element_type": kind,
                "official_code": None, "official_label": "SYNTHETIC " + kind,
                "official_text": "Synthetic structural prescription; no public source verification.",
                "document_ref": doc, "page": 1, "page_end": 1, "locator": "synthetic page 1 " + ref, "position": position})
        attachment = "attachment:http-test-" + frame
        data["attachments"].append({"id": attachment, "notion_ref": notion_ref, "element_ref": knowledge,
            "disposition": "VERIFIED_EXPLICIT", "justification": "Synthetic test attachment only.",
            "importance": None, "official_depth": None, "pedagogical_depth": "APPLICATION",
            "validated_by": "TEST_FIXTURE_ONLY", "validated_at": "2026-10-06", "evidence_ref": "evidence:http-test-" + frame})
        if bts:
            for year in ("BTS_CG_YEAR_1", "BTS_CG_YEAR_2"):
                selections[year] = {"contract_id": "BTS-INSTITUTIONAL-CONTEXT-1.0", "program_ref": frameworks[code],
                    "program_version": version, "process_ref": theme, "activity_ref": question,
                    "competency_refs": [capacity], "notion_refs": [notion_ref], "depth": "APPLICATION", "local_year": year}
        else:
            spec = STMG_FRAMES[frame]
            selections[spec[0]] = {"contract_id": "STMG-INSTITUTIONAL-CONTEXT-1.0", "frame": frame,
                "education_level": spec[1], "series": "STMG", "teaching_subject": spec[2],
                "program_component": spec[3], "specific_track": spec[4], "program_ref": frameworks[code],
                "program_version": version, "theme_ref": theme, "question_ref": question,
                "capacity_refs": [capacity], "notion_refs": [notion_ref], "depth": "APPLICATION"}
    attachments = [row["id"] for row in data["attachments"]]
    for row in canonical:
        selected = row["id"] == notion_ref
        data["notions"].append({"notion_ref": row["id"], "label": row["canonical_label"],
            "disposition": "VERIFIED_EXPLICIT" if selected else "SOURCE_GAP",
            "reason": "Synthetic fixture only, never a product admission.",
            "attachment_refs": attachments if selected else [], "candidate_scopes": ["SYNTHETIC_HTTP"]})
    ensure_private_directory(root, allowed_root=root.parent)
    runtime = root / "synthetic-qualified.sqlite"
    assert not runtime.exists()
    original.validate()
    shutil.copy2(seed, runtime)
    original.validate()
    connection = connect_sqlite(runtime, allowed_root=root)
    try:
        receipt = InstitutionalQualificationInbound(AdmitInstitutionalQualification(
            SQLiteInstitutionalQualificationAdapter(connection), owner_decision_sha256=OWNER_ADMISSION_SHA256,
            admitted_document_hashes=ADMITTED_DOCUMENTS)).execute(data)
        assert receipt["notion_count"] == 628 and receipt["provider_calls"] == 0
    finally:
        connection.close()
    original.validate()
    target = Read15RuntimeTarget(runtime, root, hashlib.sha256(runtime.read_bytes()).hexdigest())
    with exact_notion_evidence(target) as inbound:
        passages = inbound.inspect(notion_ref)["items"]
    passage = next(row for row in passages if row["object_kind"] == "NOTION" and not row["excerpt_truncated"])
    reference = {"notion_id": notion_ref, "passage_ref": passage["passage_ref"]}
    return target, selections, reference
