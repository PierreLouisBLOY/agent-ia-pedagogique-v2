"""Verify native rows against versioned proof; ACTIVE/PUBLISHED are not admission."""
from collections.abc import Mapping

from backend.modules.knowledge_reference.contracts.dto.admitted_institutional_sources import (
    ADMITTED_DOCUMENTS,
    DOCUMENT_FRAMES,
    OWNER_ADMISSION_SHA256,
)
from backend.modules.knowledge_reference.contracts.dto.institutional_qualification import (
    InstitutionalQualification,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import items


def rows(data: Mapping[str, object], key: str) -> tuple[dict[str, object], ...]:
    return items(data.get(key, []), 10000)


class QualifiedInstitutionalCorpus:
    def __init__(self, data: Mapping[str, object]) -> None:
        self.data = data
        self.proofs: dict[str, InstitutionalQualification] = {}
        for raw in rows(data, "institutional_qualifications"):
            proof = InstitutionalQualification(raw)
            if proof.data["owner_decision_sha256"] != OWNER_ADMISSION_SHA256:
                raise ValueError("INSTITUTIONAL_OWNER_DECISION_CHANGED")
            self._verify(proof)
            for version in items(proof.data["versions"], 16):
                key = str(version["id"])
                if key in self.proofs:
                    raise ValueError("INSTITUTIONAL_ACTIVE_VERSION_CONFLICT")
                self.proofs[key] = proof

    def _verify(self, proof: InstitutionalQualification) -> None:
        documents = {str(r["id"]): r for r in rows(self.data, "document")}
        sources = {str(r["id"]): r for r in rows(self.data, "source")}
        framework = {str(r["id"]): r for r in rows(self.data, "official_framework")}
        versions = {str(r["id"]): r for r in rows(self.data, "official_framework_version")}
        elements = {str(r["id"]): r for r in rows(self.data, "official_framework_element")}
        locators = {str(r["id"]): r for r in rows(self.data, "document_reference")}
        attachments = {str(r["id"]): r for r in rows(self.data, "institutional_attachment")}
        notions = {str(r["id"]): r for r in rows(self.data, "notion") if r["identity_status"] == "CANONICAL"}
        if {str(r["notion_ref"]): r["label"] for r in items(proof.data["notions"], 628)} != {ref: r["canonical_label"] for ref, r in notions.items()}:
            raise ValueError("INSTITUTIONAL_CANONICAL_UNIVERSE_CHANGED")
        admitted_docs = {str(r["id"]): r for r in items(proof.data["documents"], 8)}
        for doc in admitted_docs.values():
            native = documents.get(str(doc["id"]))
            source = sources.get(str(doc["source_ref"]))
            if (native is None or source is None or ADMITTED_DOCUMENTS.get(str(doc["candidate_id"])) != doc["sha256"] or
                any(native.get(key) != doc[key] for key in ("sha256", "url", "title", "publication_date")) or
                native.get("document_status") != "ACTIVE" or source.get("source_type") != "INSTITUTION" or
                source.get("canonical_name") != doc["source_name"] or source.get("status") != "ACTIVE" or
                not any(r["source_id"] == doc["source_ref"] and r["document_id"] == doc["id"] and r["source_role"] == "PRODUCER" for r in rows(self.data, "source_document"))):
                raise ValueError("INSTITUTIONAL_ADMITTED_DOCUMENT_CHANGED")
        for version in items(proof.data["versions"], 16):
            native = versions.get(str(version["id"]))
            owner = framework.get(str(version["framework_ref"]))
            doc = admitted_docs[str(version["document_ref"])]
            if (native is None or owner is None or owner["code"] != version["frame"] or
                version["frame"] not in DOCUMENT_FRAMES[str(doc["candidate_id"])] or
                native["framework_id"] != version["framework_ref"] or native["official_document_id"] != version["document_ref"] or
                native["version_label"] != version["version_label"] or native["publication_date"] != version["publication_date"] or
                native["lifecycle_status"] != "PUBLISHED"):
                raise ValueError("INSTITUTIONAL_VERSION_CHANGED")
        fields = {"version_ref": "framework_version_id", "parent_ref": "parent_element_id", "element_type": "element_type",
                  "official_code": "official_code", "official_label": "official_label", "official_text": "official_text", "position": "position"}
        for element in items(proof.data["elements"], 3000):
            native = elements.get(str(element["id"]))
            if native is None or any(native.get(dest) != element[src] for src, dest in fields.items()):
                raise ValueError("INSTITUTIONAL_ELEMENT_CHANGED")
            locator = locators.get(str(native.get("document_reference_id")))
            if locator is None or any(locator.get(dest) != element[src] for src, dest in {
                "document_ref": "document_id", "page": "page_start", "page_end": "page_end", "locator": "locator_text", "official_text": "original_excerpt"}.items()):
                raise ValueError("INSTITUTIONAL_LOCATOR_CHANGED")
        for attachment in items(proof.data["attachments"], 6000):
            native = attachments.get(str(attachment["id"]))
            kind = "EXPLICIT" if attachment["disposition"] == "VERIFIED_EXPLICIT" else "IMPLICIT"
            if (native is None or native["notion_id"] != attachment["notion_ref"] or
                native["framework_element_id"] != attachment["element_ref"] or native["attachment_type"] != kind or
                native["origin_type"] != "OFFICIAL" or native["status"] != "VALIDATED" or
                native["depth_level"] != attachment["pedagogical_depth"] or native["importance_level"] != attachment["importance"]):
                raise ValueError("INSTITUTIONAL_ATTACHMENT_CHANGED")

    def version(self, version_ref: object) -> dict[str, object] | None:
        proof = self.proofs.get(str(version_ref))
        if proof is None:
            return None
        return next(r for r in items(proof.data["versions"], 16) if r["id"] == version_ref)

    def document(self, version_ref: object) -> dict[str, object]:
        version = self.version(version_ref)
        if version is None:
            raise ValueError("INSTITUTIONAL_UNKNOWN_VERSION")
        return next(r for r in items(self.proofs[str(version_ref)].data["documents"], 8) if r["id"] == version["document_ref"])

    def attachments(self, version_ref: object, notion_ref: object, element_refs: set[str]) -> list[dict[str, object]]:
        proof = self.proofs.get(str(version_ref))
        if proof is None:
            return []
        return [r for r in items(proof.data["attachments"], 6000) if r["notion_ref"] == notion_ref and r["element_ref"] in element_refs]

    def treatment(self) -> dict[str, object]:
        """Trace current admissions and gaps, without promoting contextual links."""
        qualifications = {proof.sha256: proof for proof in self.proofs.values()}
        qualified_notions: dict[str, list[dict[str, object]]] = {}
        relations: dict[str, list[dict[str, object]]] = {}
        for checksum, proof in qualifications.items():
            for notion in items(proof.data["notions"], 628):
                qualified_notions.setdefault(str(notion["notion_ref"]), []).append({
                    **notion, "qualification_sha256": checksum})
            elements = {str(e["id"]): e for e in items(proof.data["elements"], 3000)}
            for link in items(proof.data["attachments"], 6000):
                element = elements[str(link["element_ref"])]
                version = self.version(element["version_ref"])
                assert version is not None
                ancestors = [element]
                parent = elements.get(str(element["parent_ref"]))
                while parent is not None:
                    ancestors.append(parent)
                    parent = elements.get(str(parent["parent_ref"]))
                ancestor_ids = {str(e["id"]) for e in ancestors}
                capabilities = [e for e in elements.values()
                    if e["version_ref"] == element["version_ref"]
                    and e["element_type"] in {"CAPACITY", "COMPETENCY"}
                    and (e["id"] in ancestor_ids or e["parent_ref"] in ancestor_ids)]
                relations.setdefault(str(link["notion_ref"]), []).append({
                    "attachment_ref": link["id"],
                    "relation_type": "EXPLICIT" if link["disposition"] == "VERIFIED_EXPLICIT" else "IMPLICIT",
                    "disposition": link["disposition"], "justification": link["justification"],
                    "framework": version, "element": element,
                    "ancestors": list(reversed(ancestors)), "capabilities": capabilities,
                    "capability_scope": "SAME_QUESTION_THEME_OR_ACTIVITY_NO_NARROWER_CLAIM",
                    "document_provenance": self.document(element["version_ref"]),
                    "qualification_sha256": checksum,
                    "owner_admission_sha256": proof.data["owner_decision_sha256"],
                    "authority": "OWNER_ADMITTED_VERSIONED_PROOF",
                    "pedagogical_depth": link["pedagogical_depth"],
                    "official_depth": link["official_depth"],
                    "year_authority": "LOCAL_PROGRESSION_ONLY" if version["frame"] == "BTS CG - Annexe I" else "NOT_APPLICABLE",
                    "teacher_acceptance": "NOT_PERFORMED"})
        contexts = {str(c["id"]): c for c in rows(self.data, "pedagogical_context")}
        contextual: dict[str, list[dict[str, object]]] = {}
        for link in rows(self.data, "notion_context"):
            context = contexts.get(str(link["context_id"]))
            if context is not None:
                contextual.setdefault(str(link["notion_id"]), []).append({
                    "context_ref": context["id"],
                    "program_version": context["framework_version_id"],
                    "element_ref": context["framework_element_id"],
                    "role": link["role"], "status": link["status"],
                    "authority": "CONTEXTUAL_NOT_OFFICIAL_ADMISSION",
                    "provenance": context["notes"]})
        treatment = []
        for notion in rows(self.data, "notion"):
            if notion["identity_status"] != "CANONICAL":
                continue
            ref = str(notion["id"])
            dispositions = qualified_notions.get(ref, [])
            links = relations.get(ref, [])
            if links:
                disposition = "VERIFIED_EXPLICIT" if any(
                    link["relation_type"] == "EXPLICIT" for link in links) else "VERIFIED_IMPLICIT"
            elif dispositions and len({n["disposition"] for n in dispositions}) == 1:
                disposition = str(dispositions[0]["disposition"])
            else:
                disposition = "HUMAN_REVIEW_REQUIRED" if dispositions else "SOURCE_GAP"
            treatment.append({
                "notion_ref": ref, "label": notion["canonical_label"],
                "identity_status": "CANONICAL", "disposition": disposition,
                "qualification_dispositions": dispositions,
                "relations": links, "contextual_relationships": contextual.get(ref, []),
                "reason": " | ".join(str(n["reason"]) for n in dispositions) if dispositions
                    else "NO_VERSIONED_INSTITUTIONAL_QUALIFICATION_FOR_THIS_IDENTITY",
                "disciplinary_authority": "SEPARATE_EVIDENCE_REQUIRED",
                "teacher_acceptance": "NOT_PERFORMED"})
        return {"contract_id": "INSTITUTIONAL-NOTION-TREATMENT-1.0",
            "notion_count": len(treatment), "notions": treatment,
            "qualification_sha256s": sorted(qualifications),
            "authority": "NO_IMPLICIT_PROMOTION", "provider_calls": 0}

    def resolve_scope(self, *, version_ref: str, element_ref: str, notion_refs: tuple[str, ...],
                      local_year: str | None = None) -> dict[str, object]:
        """Native BTS process/activity or STMG question; no inferred yearly syllabus."""
        if not 1 <= len(notion_refs) <= 16 or len(set(notion_refs)) != len(notion_refs):
            raise ValueError("INSTITUTIONAL_SCOPE_BOUND")
        version = self.version(version_ref)
        if version is None:
            raise ValueError("INSTITUTIONAL_UNKNOWN_VERSION")
        if local_year not in {None, "BTS_CG_YEAR_1", "BTS_CG_YEAR_2"} or (local_year and version["frame"] != "BTS CG - Annexe I"):
            raise ValueError("INSTITUTIONAL_LOCAL_YEAR")
        proof = self.proofs[version_ref]
        elements = {str(e["id"]): e for e in items(proof.data["elements"], 3000) if e["version_ref"] == version_ref}
        element = elements.get(element_ref)
        if element is None:
            raise ValueError("INSTITUTIONAL_SCOPE_ELEMENT")
        scope = {element_ref}
        for _ in range(len(elements)):
            expanded = scope | {ref for ref, e in elements.items() if e["parent_ref"] in scope}
            if expanded == scope:
                break
            scope = expanded
        known = {str(n["notion_ref"]): n for n in items(proof.data["notions"], 628)}
        if any(ref not in known for ref in notion_refs):
            raise ValueError("INSTITUTIONAL_NOTION_SCOPE")
        links = [a for ref in notion_refs for a in self.attachments(version_ref, ref, scope)]
        gaps = [ref for ref in notion_refs if not any(a["notion_ref"] == ref for a in links)]
        return {"contract_id": "INSTITUTIONAL-SCOPE-RESOLUTION-1.0", "status": "CONTENT_GAP" if gaps else "RESOLVED_ADMITTED",
            "framework": version, "element": element,
            "competencies": [e for ref, e in elements.items() if ref in scope and e["element_type"] in {"COMPETENCY", "CAPACITY"}],
            "limits": [e for ref, e in elements.items() if ref in scope and e["element_type"] == "OTHER"],
            "notions": [known[ref] for ref in notion_refs], "attachments": links, "gaps": gaps,
            "qualification_sha256": proof.sha256, "owner_admission_sha256": proof.data["owner_decision_sha256"],
            "document_provenance": self.document(version_ref), "local_year": local_year,
            "year_authority": "LOCAL_PROGRESSION_ONLY" if local_year else "NOT_SELECTED",
            "official_depth": None, "pedagogical_depth": "LOCAL_PROPOSAL_REQUIRED", "provider_calls": 0}
