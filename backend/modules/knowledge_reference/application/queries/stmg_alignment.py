"""Project existing identities; contextual links never become official admissions."""
from __future__ import annotations

import re
from collections.abc import Mapping

from backend.modules.knowledge_reference.application.queries.qualified_institutional_corpus import (
    QualifiedInstitutionalCorpus,
)
from backend.modules.knowledge_reference.contracts.dto.stmg_frames import STMG_FRAMES
from backend.modules.knowledge_reference.ports.outbound.institutional_catalog import (
    InstitutionalSchemaPort,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    fingerprint,
    object_data,
)


def _rows(data: Mapping[str, object], name: str) -> list[dict[str, object]]:
    values = data.get(name, [])
    if not isinstance(values, (list, tuple)) or len(values) > 10000:
        raise ValueError("P0_INSTITUTIONAL_CATALOG_BOUND")
    return [object_data(row) for row in values]


def _theme(question: Mapping[str, object]) -> str | None:
    match = re.match(r"\s*(\d+)\.\d", str(question["official_label"]))
    return "theme:" + match[1] if match else None


def _native_theme(question: Mapping[str, object], elements: Mapping[str, dict[str, object]],
                  corpus: QualifiedInstitutionalCorpus) -> str | None:
    if corpus.version(question["framework_version_id"]) is None:
        return _theme(question)
    parent = elements.get(str(question["parent_element_id"]))
    return str(parent["id"]) if parent is not None and parent["element_type"] == "THEME" else None


class ReadSTMGAlignment:
    def __init__(self, catalog: InstitutionalSchemaPort) -> None:
        self.catalog = catalog

    def snapshot(self) -> dict[str, object]:
        return self._snapshot(self.catalog.read_institutional_catalog())

    @staticmethod
    def _snapshot(data: Mapping[str, object]) -> dict[str, object]:
        frameworks = _rows(data, "official_framework")
        versions = _rows(data, "official_framework_version")
        elements = _rows(data, "official_framework_element")
        corpus = QualifiedInstitutionalCorpus(data)
        by_element = {str(e["id"]): e for e in elements}
        frames = []
        historical_frames = []
        for key, spec in STMG_FRAMES.items():
            for framework in frameworks:
                if framework["code"] != spec[5]:
                    continue
                for version in versions:
                    if version["framework_id"] != framework["id"]:
                        continue
                    questions = [{"question_ref": e["id"], "label": e["official_label"], "theme_ref": _native_theme(e, by_element, corpus)}
                                 for e in elements if e["framework_version_id"] == version["id"] and e["element_type"] == "QUESTION"]
                    capacities = [{"capacity_ref": e["id"], "label": e["official_label"], "question_ref": e["parent_element_id"]}
                                  for e in elements if e["framework_version_id"] == version["id"] and e["element_type"] == "CAPACITY"]
                    qualified = corpus.version(version["id"])
                    admitted_doc = corpus.document(version["id"]) if qualified else None
                    frame = {"frame": key, "level": spec[0], "education_level": spec[1], "series": "STMG",
                        "teaching_subject": spec[2], "program_component": spec[3], "specific_track": spec[4],
                        "program_ref": framework["id"], "program_version": version["id"], "code": spec[5], "label": spec[6],
                        "version_label": version["version_label"], "lifecycle_status": version["lifecycle_status"],
                        "issuing_source_id": admitted_doc["source_ref"] if admitted_doc else framework["issuing_source_id"], "official_document_id": version["official_document_id"],
                        "questions": questions, "capacities": capacities,
                        "authority": "OWNER_ADMITTED_VERSIONED_PROOF" if qualified else "UNATTESTED" if not version["official_document_id"] or not framework["issuing_source_id"] else "PROVENANCE_REQUIRES_RESOLUTION"}
                    if qualified is None and any(v["framework_id"] == framework["id"] and corpus.version(v["id"]) is not None for v in versions):
                        historical_frames.append(frame)
                    else:
                        frames.append(frame)
        return {"contract_id": "STMG-CATALOG-1.0", "frames": frames, "historical_frames": historical_frames,
                "notions": [{"notion_ref": n["id"], "label": n["canonical_label"]}
                            for n in _rows(data, "notion") if n["identity_status"] == "CANONICAL"],
                "automatic_interprogramme_enrichment": False}

    def resolve(self, selection: Mapping[str, object], reference_selection: Mapping[str, object]) -> dict[str, object]:
        data = self.catalog.read_institutional_catalog()
        snapshot = self._snapshot(data)
        corpus = QualifiedInstitutionalCorpus(data)
        frames = _rows(snapshot, "frames")
        matches = [f for f in frames if f["frame"] == selection["frame"] and f["program_ref"] == selection["program_ref"]
                   and f["program_version"] == selection["program_version"]]
        if len(matches) != 1:
            raise ValueError("P0_INSTITUTIONAL_PROGRAMME_VERSION")
        frame = matches[0]
        if any(selection.get(key) != frame[key] for key in (
                "education_level", "series", "teaching_subject", "program_component", "specific_track")):
            raise ValueError("P0_INSTITUTIONAL_FRAME")
        elements = {str(e["id"]): e for e in _rows(data, "official_framework_element")}
        question = elements.get(str(selection["question_ref"]))
        if (question is None or question["framework_version_id"] != selection["program_version"] or
                question["element_type"] != "QUESTION" or _native_theme(question, elements, corpus) != selection["theme_ref"]):
            raise ValueError("P0_INSTITUTIONAL_QUESTION_THEME")
        capacity_ids = selection["capacity_refs"]
        notion_ids = selection["notion_refs"]
        assert isinstance(capacity_ids, (list, tuple)) and isinstance(notion_ids, (list, tuple))
        capacities = []
        for ref in capacity_ids:
            capacity = elements.get(str(ref))
            if (capacity is None or capacity["framework_version_id"] != selection["program_version"] or
                    capacity["element_type"] != "CAPACITY" or capacity["parent_element_id"] not in
                    ({question["id"], selection["theme_ref"]} if corpus.version(selection["program_version"]) else {question["id"]})):
                raise ValueError("P0_INSTITUTIONAL_CAPACITY_SCOPE")
            capacities.append({"capacity_ref": ref, "label": capacity["official_label"],
                               "document_reference_id": capacity["document_reference_id"]})
        notions = {str(n["id"]): n for n in _rows(data, "notion") if n["identity_status"] == "CANONICAL"}
        if any(ref not in notions for ref in notion_ids):
            raise ValueError("P0_INSTITUTIONAL_NOTION_ID")
        if reference_selection.get("notion_id") not in notion_ids:
            raise ValueError("P0_INSTITUTIONAL_EXACT_NOTION_SOURCE_REQUIRED")
        gaps = []
        qualified_version = corpus.version(selection["program_version"])
        if selection["theme_ref"] is None:
            gaps.append("THEME_RELATIONSHIP_UNRESOLVED")
        documents = {str(d["id"]): d for d in _rows(data, "document")}
        sources = {str(s["id"]): s for s in _rows(data, "source")}
        locators = {str(r["id"]): r for r in _rows(data, "document_reference")}
        document = documents.get(str(frame["official_document_id"]))
        source = sources.get(str(frame["issuing_source_id"]))
        if qualified_version is None and (source is None or source.get("status") not in {"VERIFIED", "ADMITTED"} or document is None or
                document.get("document_status") not in {"VERIFIED", "ADMITTED"} or
                re.fullmatch(r"[a-f0-9]{64}", str(document.get("sha256"))) is None):
            gaps.append("PROGRAMME_PROVENANCE_NOT_ADMITTED")
        def admitted_locator(ref: object) -> bool:
            locator = locators.get(str(ref))
            return locator is not None and locator["document_id"] == frame["official_document_id"]

        if not admitted_locator(question["document_reference_id"]):
            gaps.append("QUESTION_PROVENANCE_MISSING")
        if not capacities or any(not admitted_locator(c["document_reference_id"]) for c in capacities):
            gaps.append("CAPACITIES_OR_PROVENANCE_MISSING")
        links = []
        attachments = _rows(data, "institutional_attachment")
        for notion in notion_ids:
            admitted = []
            if qualified_version is not None:
                scoped_elements = {str(question["id"])} | {ref for ref, e in elements.items() if e["parent_element_id"] == question["id"]}
                admitted = corpus.attachments(selection["program_version"], notion, scoped_elements)
            for attachment in attachments:
                if qualified_version is not None:
                    break
                element = elements.get(str(attachment["framework_element_id"]))
                if attachment["notion_id"] != notion or element is None or element["framework_version_id"] != selection["program_version"]:
                    continue
                if element["id"] != question["id"] and element["parent_element_id"] != question["id"]:
                    continue
                if (attachment["attachment_type"] == "EXPLICIT" and attachment["status"] == "ADMITTED" and
                        attachment["origin_type"] == "OFFICIAL_DOCUMENT" and admitted_locator(element["document_reference_id"]) and
                        attachment["depth_level"] == selection["depth"]):
                    admitted.append(attachment)
            if not admitted:
                gaps.append("NOTION_ATTACHMENT_NOT_ADMITTED:" + str(notion))
            links.extend(admitted)
        result = {"contract_id": "STMG-RESOLUTION-1.0", "selection_sha256": fingerprint(selection),
            "frame": selection["frame"], "program_ref": frame["program_ref"], "program_version": frame["program_version"],
            "version_label": frame["version_label"], "program_lifecycle_status": frame["lifecycle_status"],
            "issuing_source_id": frame["issuing_source_id"], "official_document_id": frame["official_document_id"],
            "programme_document_sha256": document.get("sha256") if document else None,
            "programme_document_status": document.get("document_status") if document else None,
            "issuing_source_status": source.get("status") if source else None,
            "question": question, "theme_ref": selection["theme_ref"], "capacities": capacities, "attachments": links,
            "notions": [{"notion_ref": ref, "label": notions[str(ref)]["canonical_label"]} for ref in notion_ids],
            "depth": selection["depth"], "gaps": gaps, "status": "CONTENT_GAP" if gaps else "RESOLVED_ADMITTED",
            "implicit_propagation": False, "teacher_acceptance": "NOT_PERFORMED"}
        if qualified_version is not None:
            result.update({"qualification_sha256": corpus.proofs[str(selection["program_version"])].sha256,
                "owner_admission_sha256": corpus.proofs[str(selection["program_version"])].data["owner_decision_sha256"],
                "document_provenance": corpus.document(selection["program_version"]),
                "theme": elements.get(str(selection["theme_ref"])),
                "depth_authority": "LOCAL_PEDAGOGICAL_PROPOSAL", "official_depth": None,
                "capacity_scope": "SELECTED_THEME_OR_QUESTION_NO_NARROWER_CLAIM"})
        source_scope = self._reference_scope(selection, reference_selection, question, elements)
        result["reference_scope"] = source_scope
        if source_scope["status"] == "CONTENT_GAP":
            gaps.append("SELECTED_PASSAGE_CONTEXT_NOT_ADMITTED")
            result["status"] = "CONTENT_GAP"
        return result

    def _reference_scope(self, selection: Mapping[str, object], reference: Mapping[str, object],
                         question: Mapping[str, object], elements: Mapping[str, dict[str, object]]) -> dict[str, object]:
        identity = {key: reference.get(key) for key in ("object_ref", "object_kind", "passage_ref", "version_or_checksum")}
        verified = all(isinstance(identity[key], str) and identity[key] for key in identity)
        # A canonical notion label can establish identity; it does not supply
        # contextual examples, methods, capacities or an admission by propagation.
        if verified and identity["object_kind"] == "NOTION" and identity["object_ref"] == reference.get("notion_id"):
            return {**identity, "status": "CANONICAL_NOTION_ONLY", "relationships": [], "context_enrichment": False}
        relationships = []
        if verified and identity["object_kind"] in {"PEDAGOGICAL_CONTENT", "METHOD"}:
            for link in self.catalog.read_reference_contexts(str(identity["object_ref"])):
                element = elements.get(str(link.get("element_ref")))
                if (link.get("status") == "ADMITTED" and link.get("program_version") == selection["program_version"] and
                        link.get("depth") == selection["depth"] and element is not None and
                        element["framework_version_id"] == selection["program_version"] and
                        (element["id"] == question["id"] or element["parent_element_id"] == question["id"])):
                    relationships.append(dict(link))
        return {**identity, "status": "EXACT_CONTEXT_ADMITTED" if relationships else "CONTENT_GAP",
                "relationships": relationships, "context_enrichment": False}

    def matrix(self) -> dict[str, object]:
        data = self.catalog.read_institutional_catalog()
        snapshot = self._snapshot(data)
        treatment = QualifiedInstitutionalCorpus(data).treatment()
        qualified = {str(link["attachment_ref"]): link
                     for notion in _rows(treatment, "notions")
                     for link in _rows(notion, "relations")}
        frames = _rows(snapshot, "frames")
        contexts = {str(c["id"]): c for c in _rows(data, "pedagogical_context")}
        elements = {str(e["id"]): e for e in _rows(data, "official_framework_element")}
        context_links: dict[str, list[dict[str, object]]] = {}
        for link in _rows(data, "notion_context"):
            context_links.setdefault(str(link["notion_id"]), []).append(link)
        attachments: dict[str, list[dict[str, object]]] = {}
        for link in _rows(data, "institutional_attachment"):
            attachments.setdefault(str(link["notion_id"]), []).append(link)
        matrix = []
        for notion in _rows(snapshot, "notions"):
            scopes = []
            for frame_key in STMG_FRAMES:
                exact = [f for f in frames if f["frame"] == frame_key]
                relationships = []
                for frame in exact:
                    for link in context_links.get(str(notion["notion_ref"]), []):
                        context = contexts.get(str(link["context_id"]))
                        if link["notion_id"] == notion["notion_ref"] and context is not None and context["framework_version_id"] == frame["program_version"]:
                            element = elements.get(str(context["framework_element_id"]))
                            relationships.append({"program_ref": frame["program_ref"], "program_version": frame["program_version"],
                                "context_ref": context["id"], "element": element, "role": link["role"], "status": link["status"],
                                "provenance": context["notes"], "nature": "CONTEXTUAL_NOT_OFFICIAL_ADMISSION",
                                "depth": context["difficulty_level"], "capacity_refs": []})
                    for link in attachments.get(str(notion["notion_ref"]), []):
                        element = elements.get(str(link["framework_element_id"]))
                        if link["notion_id"] == notion["notion_ref"] and element is not None and element["framework_version_id"] == frame["program_version"]:
                            proof = qualified.get(str(link["id"]))
                            relationships.append({"program_ref": frame["program_ref"], "program_version": frame["program_version"],
                                "attachment": link, "element": element, "nature": link["attachment_type"],
                                "status": link["status"], "provenance": link["origin_type"], "depth": link["depth_level"],
                                "qualification": proof,
                                "authority": "OWNER_ADMITTED_VERSIONED_PROOF" if proof else "REQUIRES_ADMISSION"})
                scopes.append({"frame": frame_key, "relationships": relationships,
                               "status": "RESOLVED_ADMITTED" if any(r.get("qualification") for r in relationships)
                                    else "LINKS_REQUIRE_ADMISSION" if relationships else "CONTENT_GAP"})
            matrix.append({**notion, "scopes": scopes})
        return {"contract_id": "STMG-NOTION-MATRIX-1.0", "notion_count": len(matrix), "frames": list(STMG_FRAMES),
                "notions": matrix, "authority": "NO_IMPLICIT_PROMOTION", "seed_modified": False}
