"""Resolve admitted native BTS process/activity evidence before planning."""
from collections.abc import Mapping

from backend.modules.knowledge_reference.application.queries.qualified_institutional_corpus import (
    QualifiedInstitutionalCorpus,
    rows,
)
from backend.modules.knowledge_reference.ports.outbound.institutional_catalog import (
    InstitutionalSchemaPort,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import fingerprint, items


class ReadBTSAlignment:
    def __init__(self, catalog: InstitutionalSchemaPort) -> None:
        self.catalog = catalog

    def snapshot(self) -> list[dict[str, object]]:
        corpus = QualifiedInstitutionalCorpus(self.catalog.read_institutional_catalog())
        result = []
        for ref, proof in corpus.proofs.items():
            version = corpus.version(ref)
            if version is None or version["frame"] != "BTS CG - Annexe I":
                continue
            elements = [e for e in items(proof.data["elements"], 3000) if e["version_ref"] == ref]
            result.append({"program_ref": version["framework_ref"], "program_version": ref,
                "version_label": version["version_label"], "label": "BTS CG — référentiel professionnel",
                "authority": "OWNER_ADMITTED_VERSIONED_PROOF", "elements": elements,
                "year_authority": "LOCAL_PROGRESSION_ONLY"})
        return result

    def resolve(self, selection: Mapping[str, object], reference: Mapping[str, object]) -> dict[str, object]:
        corpus = QualifiedInstitutionalCorpus(self.catalog.read_institutional_catalog())
        version = corpus.version(selection["program_version"])
        if (version is None or version["frame"] != "BTS CG - Annexe I" or
                version["framework_ref"] != selection["program_ref"]):
            raise ValueError("P0_BTS_INSTITUTIONAL_VERSION")
        proof = corpus.proofs[str(selection["program_version"])]
        elements = {str(e["id"]): e for e in rows(proof.data, "elements") if e["version_ref"] == selection["program_version"]}
        process = elements.get(str(selection["process_ref"]))
        activity = elements.get(str(selection["activity_ref"]))
        if process is None or process["element_type"] != "PROCESS" or activity is None or activity["element_type"] not in {"ACTIVITY", "SUB_ACTIVITY"}:
            raise ValueError("P0_BTS_INSTITUTIONAL_ACTIVITY")
        ancestor = activity
        for _ in range(len(elements)):
            if ancestor["parent_ref"] == process["id"]:
                break
            parent = elements.get(str(ancestor["parent_ref"]))
            if parent is None:
                raise ValueError("P0_BTS_INSTITUTIONAL_PROCESS_SCOPE")
            ancestor = parent
        else:
            raise ValueError("P0_BTS_INSTITUTIONAL_PROCESS_SCOPE")
        selected_notions = selection["notion_refs"]
        assert isinstance(selected_notions, (list, tuple))
        notions = tuple(str(v) for v in selected_notions)
        scope = corpus.resolve_scope(version_ref=str(version["id"]), element_ref=str(activity["id"]),
            notion_refs=notions, local_year=str(selection["local_year"]))
        available = {str(e["id"]): e for e in items(scope["competencies"], 256)}
        competencies = selection["competency_refs"]
        assert isinstance(competencies, (list, tuple))
        if not competencies or any(ref not in available for ref in competencies):
            raise ValueError("P0_BTS_INSTITUTIONAL_COMPETENCY_SCOPE")
        if (reference.get("notion_id") not in notions or reference.get("object_kind") != "NOTION" or
                reference.get("object_ref") != reference.get("notion_id") or
                not all(isinstance(reference.get(k), str) and reference.get(k) for k in ("passage_ref", "version_or_checksum"))):
            raise ValueError("P0_INSTITUTIONAL_EXACT_NOTION_SOURCE_REQUIRED")
        return {**scope, "contract_id": "BTS-RESOLUTION-1.0", "selection_sha256": fingerprint(selection),
            "program_ref": version["framework_ref"], "program_version": version["id"], "version_label": version["version_label"],
            "process": process, "activity": activity, "competencies": [available[str(ref)] for ref in competencies],
            "depth": selection["depth"], "depth_authority": "LOCAL_PEDAGOGICAL_PROPOSAL",
            "reference_scope": {**{k: reference[k] for k in ("object_ref", "object_kind", "passage_ref", "version_or_checksum")},
                "status": "CANONICAL_NOTION_ONLY", "context_enrichment": False},
            "implicit_propagation": False, "teacher_acceptance": "NOT_PERFORMED"}
