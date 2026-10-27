"""Versioned case-study dossier under EXERCISE (Phase 0 F-EX-015, Phase 5.9)."""
from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    items,
    nonempty,
    object_data,
)
from backend.shared_kernel._safe_data import freeze_safe_mapping

CASE_CONTEXT = "P0-CONTEXT-CASE-STUDY-1.0"
CASE_PRODUCTION = "P0-PRODUCTION-CASE-STUDY-1.0"
CASE_DOSSIER = "CASE-STUDY-DOSSIER-1.0"


def case_study_schema() -> dict[str, object]:
    def obj(properties: dict[str, object]) -> dict[str, object]:
        return {"type": "object", "additionalProperties": False, "required": list(properties), "properties": properties}
    string: dict[str, object] = {"type": "string"}
    strings = {"type": "array", "items": string}
    assertion = obj({"data_id": string, "organization_id": string,
        "kind": {"type": "string", "enum": ["DOCUMENTED_FACT", "INFERENCE", "FICTION"]},
        "text": string, "document_id": string, "quote": {"type": ["string", "null"]}})
    return obj({"contract_id": {"type": "string", "enum": [CASE_DOSSIER]},
        "organizations": {"type": "array", "items": obj({"organization_id": string, "label": string})},
        "data": {"type": "array", "items": assertion},
        "missions": {"type": "array", "items": obj({"mission_id": string, "title": string,
            "document_ids": strings, "question_ids": strings, "data_ids": strings})}})


@dataclass(frozen=True, slots=True)
class CaseStudyDossier:
    data: Mapping[str, object]

    def __post_init__(self) -> None:
        fields = set(object_data(case_study_schema()["properties"]))
        data = object_data(self.data, fields)
        if data["contract_id"] != CASE_DOSSIER:
            raise ValueError("P0_CASE_CONTRACT")
        for field, keys, maximum, id_key in (
                ("organizations", {"organization_id", "label"}, 8, "organization_id"),
                ("data", {"data_id", "organization_id", "kind", "text", "document_id", "quote"}, 30, "data_id"),
                ("missions", {"mission_id", "title", "document_ids", "question_ids", "data_ids"}, 12, "mission_id")):
            rows = items(data[field], maximum)
            if not rows or len({str(row.get(id_key)) for row in rows}) != len(rows):
                raise ValueError("P0_CASE_REQUIRED_UNIQUE_ROWS")
            for row in rows:
                object_data(row, keys)
                for key in keys - {"quote", "document_ids", "question_ids", "data_ids"}:
                    nonempty(row[key], 4000 if key == "text" else 300)
        object.__setattr__(self, "data", freeze_safe_mapping(data))

    def bind(self, exercise: Mapping[str, object]) -> None:
        docs = {str(row["document_id"]): row for row in items(exercise["documents"], 12)}
        questions = {str(row["question_id"]): row for row in items(exercise["questions"], 30)}
        organizations = {str(row["organization_id"]): str(row["label"]) for row in items(self.data["organizations"], 8)}
        assertions = {str(row["data_id"]): row for row in items(self.data["data"], 30)}
        used_orgs = set()
        for row in assertions.values():
            document = docs.get(str(row["document_id"]))
            org = str(row["organization_id"])
            if document is None or org not in organizations:
                raise ValueError("P0_CASE_SOURCE_LINK")
            used_orgs.add(org)
            kind, quote = row["kind"], row["quote"]
            if kind == "FICTION":
                if quote is not None or document["provenance"] != "LOCAL_FICTION":
                    raise ValueError("P0_CASE_FICTION_SOURCE")
            elif kind in {"DOCUMENTED_FACT", "INFERENCE"}:
                if (document["provenance"] != "SUPPLIED_REFERENCE" or not isinstance(quote, str)
                        or not quote.strip() or quote not in str(document["text"])
                        or organizations[org] not in str(document["text"])):
                    raise ValueError("P0_CASE_QUOTE_NOT_SUPPORTED")
                if kind == "DOCUMENTED_FACT" and row["text"] != quote:
                    raise ValueError("P0_CASE_FACT_REQUIRES_EXACT_QUOTE")
            else:
                raise ValueError("P0_CASE_DATA_KIND")
        if used_orgs != set(organizations):
            raise ValueError("P0_CASE_UNUSED_ORGANIZATION")
        used_questions: list[str] = []
        used_data: set[str] = set()
        used_docs: set[str] = set()
        for mission in items(self.data["missions"], 12):
            links: dict[str, tuple[str, ...]] = {}
            for key, known in (("document_ids", set(docs)), ("question_ids", set(questions)), ("data_ids", set(assertions))):
                refs = mission[key]
                if (not isinstance(refs, (list, tuple)) or not refs or any(not isinstance(ref, str) for ref in refs)
                        or len(set(refs)) != len(refs) or not set(refs) <= known):
                    raise ValueError("P0_CASE_MISSION_LINK")
                links[key] = tuple(refs)
            document_ids = set(links["document_ids"])
            for qid in links["question_ids"]:
                if not set(cast(tuple[str, ...], questions[qid]["document_ids"])) <= document_ids:
                    raise ValueError("P0_CASE_MISSION_DOCUMENTS")
            for data_id in links["data_ids"]:
                if assertions[str(data_id)]["document_id"] not in document_ids:
                    raise ValueError("P0_CASE_MISSION_DOCUMENTS")
            used_questions.extend(links["question_ids"])
            used_data.update(links["data_ids"])
            used_docs.update(document_ids)
        if (len(used_questions) != len(set(used_questions)) or set(used_questions) != set(questions)
                or used_data != set(assertions) or used_docs != set(docs)):
            raise ValueError("P0_CASE_MISSION_COVERAGE")

    def public_text(self) -> str:
        labels = {str(row["organization_id"]): str(row["label"]) for row in items(self.data["organizations"], 8)}
        kinds = {"DOCUMENTED_FACT": "Citation documentaire", "INFERENCE": "Interprétation à discuter", "FICTION": "Donnée fictive"}
        data = [kinds[str(row["kind"])] + " — " + labels[str(row["organization_id"])] + " : " + str(row["text"])
                for row in items(self.data["data"], 30)]
        missions = ["Mission : " + str(row["title"]) + " (" + ", ".join(cast(tuple[str, ...], row["question_ids"])) + ")"
                    for row in items(self.data["missions"], 12)]
        return "\n".join([*data, *missions])
