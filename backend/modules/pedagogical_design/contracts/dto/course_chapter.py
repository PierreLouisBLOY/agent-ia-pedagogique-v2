"""Versioned learning chapter; answers and internal provenance never enter student views."""
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

from backend.modules.materialization_export.contracts.dto.media_asset import CourseMedia, MediaAsset
from backend.modules.pedagogical_context.contracts.dto.p0_context import P0Context
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    as_plain,
    encoded,
    items,
    nonempty,
    object_data,
)
from backend.modules.pedagogical_design.contracts.dto.visual_brief import visual_briefs
from backend.shared_kernel._safe_data import freeze_safe_mapping

COURSE_CHAPTER_CONTRACT = "COURSE-CHAPTER-1.0"
COURSE_MEDIA_CONTRACT = "COURSE-CHAPTER-MEDIA-2.0"
COURSE_PRODUCTION_CONTRACT = "R6-P0-PRODUCTION-COURSE-2.0"
CHECK_NAMES = (
    "has_program_header", "has_capabilities", "has_notions", "has_context",
    "has_learning_documents", "has_numbered_questions", "has_conceptualization",
    "has_student_response_spaces", "has_knowledge_check", "has_transfer_activity",
    "no_internal_metadata", "visual_review_required",
)
_FIELDS = {"contract_id", "chapter_number", "title", "program_header", "capabilities",
           "notions", "context", "documents", "parts", "questions", "concepts",
           "knowledge_check", "transfer", "synthesis", "teacher_answers"}
_INTERNAL = re.compile(r"SQLite|CONTENT_GAP|CANDIDATE|P0-|COURSE-|V47|search-chunk:|framework:|_sha256|codex/|localhost", re.I)


def _strings(value: object, maximum: int = 30, *, required: bool = True) -> tuple[str, ...]:
    if not isinstance(value, (tuple, list)) or not (int(required) <= len(value) <= maximum):
        raise ValueError("COURSE_CHAPTER_LIST")
    result = tuple(nonempty(v, 2000) for v in value)
    if len(result) != len(set(result)):
        raise ValueError("COURSE_CHAPTER_DUPLICATE")
    return result


def _rows(value: object, fields: set[str], *, maximum: int = 30) -> tuple[dict[str, object], ...]:
    result = items(value, maximum)
    if not result:
        raise ValueError("COURSE_CHAPTER_REQUIRED")
    ids = []
    for row in result:
        object_data(row, fields)
        ids.append(nonempty(row["id"], 40))
    if len(set(ids)) != len(ids):
        raise ValueError("COURSE_CHAPTER_DUPLICATE")
    return result


def _table(value: object) -> None:
    if value is None:
        return
    data = object_data(value, {"columns", "rows"})
    columns = _strings(data["columns"], 5)
    rows = data["rows"]
    if not isinstance(rows, (tuple, list)) or not 1 <= len(rows) <= 20:
        raise ValueError("COURSE_CHAPTER_TABLE")
    for row in rows:
        if not isinstance(row, (tuple, list)) or len(row) != len(columns):
            raise ValueError("COURSE_CHAPTER_TABLE")
        for cell in row:
            if not isinstance(cell, str) or len(cell) > 1500:
                raise ValueError("COURSE_CHAPTER_TABLE")


@dataclass(frozen=True, slots=True)
class CourseChapter:
    data: Mapping[str, object]

    def __post_init__(self) -> None:
        illustrated = self.data.get("contract_id") == COURSE_MEDIA_CONTRACT
        data = object_data(self.data, _FIELDS | {"visual_briefs", "media_assets"} if illustrated else _FIELDS)
        if data["contract_id"] not in {COURSE_CHAPTER_CONTRACT, COURSE_MEDIA_CONTRACT}:
            raise ValueError("COURSE_CHAPTER_CONTRACT")
        if type(data["chapter_number"]) is not int or not 1 <= data["chapter_number"] <= 99:
            raise ValueError("COURSE_CHAPTER_NUMBER")
        nonempty(data["title"], 200)
        header = object_data(data["program_header"], {"frame", "program_ref", "program_version",
            "theme_ref", "theme_label", "question_ref", "question_label", "level_label", "subject_label"})
        for value in header.values():
            nonempty(value, 2000)
        capacities = _rows(data["capabilities"], {"id", "label", "source_ref", "locator", "authority_status"})
        for row in capacities:
            for value in row.values():
                nonempty(value, 2000)
            if row["authority_status"] not in {"ADMITTED_A_EXACT_SCOPE", "PUBLIC_SOURCE_VERIFIED_NOT_RUNTIME_ADMITTED", "LOCAL_PROPOSED"}:
                raise ValueError("COURSE_CAPABILITY_AUTHORITY")
        _strings(data["notions"])
        story = object_data(data["context"], {"title", "text"})
        nonempty(story["title"], 200)
        nonempty(story["text"], 8000)
        documents = _rows(data["documents"], {"id", "title", "function", "text", "table", "provenance"})
        for doc in documents:
            for key in ("title", "function", "text"):
                nonempty(doc[key], 8000)
            _table(doc["table"])
            provenance = object_data(doc["provenance"], {"kind", "source_ref"})
            if provenance["kind"] not in {"LOCAL_FICTION", "SUPPLIED_REFERENCE"}:
                raise ValueError("COURSE_DOCUMENT_PROVENANCE")
            nonempty(provenance["source_ref"], 2000)
        concepts = _rows(data["concepts"], {"id", "notion", "definition", "explanation", "example"})
        for row in concepts:
            for value in row.values():
                nonempty(value, 3000)
        questions = _rows(data["questions"], {"id", "number", "prompt", "document_ids", "capability_ids", "response"}, maximum=60)
        doc_ids = {str(d["id"]) for d in documents}
        cap_ids = {str(c["id"]) for c in capacities}
        for i, row in enumerate(questions, 1):
            if type(row["number"]) is not int or row["number"] != i:
                raise ValueError("COURSE_QUESTION_NUMBER")
            nonempty(row["prompt"], 4000)
            if not set(_strings(row["document_ids"], required=False)) <= doc_ids:
                raise ValueError("COURSE_DOCUMENT_LINK")
            if not set(_strings(row["capability_ids"])) <= cap_ids:
                raise ValueError("COURSE_CAPABILITY_LINK")
            response = object_data(row["response"], {"kind", "lines", "table"})
            if response["kind"] not in {"LINES", "TABLE"} or type(response["lines"]) is not int or not 1 <= response["lines"] <= 8:
                raise ValueError("COURSE_RESPONSE_SPACE")
            _table(response["table"])
            if (response["kind"] == "TABLE") != (response["table"] is not None):
                raise ValueError("COURSE_RESPONSE_SPACE")
        question_ids = {str(q["id"]) for q in questions}
        concept_ids = {str(c["id"]) for c in concepts}
        parts = _rows(data["parts"], {"id", "title", "document_ids", "observation", "analysis", "concept_ids", "reinvestment"}, maximum=8)
        activity_ids: list[str] = []
        for row in parts:
            nonempty(row["title"], 200)
            if not set(_strings(row["document_ids"])) <= doc_ids or not set(_strings(row["concept_ids"])) <= concept_ids:
                raise ValueError("COURSE_PART_LINK")
            for role in ("observation", "analysis", "reinvestment"):
                refs = _strings(row[role])
                if not set(refs) <= question_ids:
                    raise ValueError("COURSE_QUESTION_LINK")
                activity_ids.extend(refs)
        knowledge = _strings(data["knowledge_check"])
        transfer = object_data(data["transfer"], {"title", "document_ids", "question_ids"})
        nonempty(transfer["title"], 200)
        if not set(_strings(transfer["document_ids"])) <= doc_ids:
            raise ValueError("COURSE_DOCUMENT_LINK")
        activity_ids.extend(knowledge)
        activity_ids.extend(_strings(transfer["question_ids"]))
        if len(activity_ids) != len(set(activity_ids)) or set(activity_ids) != question_ids:
            raise ValueError("COURSE_QUESTION_COVERAGE")
        nonempty(data["synthesis"], 8000)
        answers = _rows(data["teacher_answers"], {"id", "expected_answer", "rationale", "vigilance", "remediation"}, maximum=60)
        if [a["id"] for a in answers] != [q["id"] for q in questions]:
            raise ValueError("COURSE_ANSWER_LINK")
        for row in answers:
            for value in row.values():
                nonempty(value, 4000)
        if illustrated:
            briefs = visual_briefs(data["visual_briefs"])
            assets = tuple(MediaAsset(row) for row in items(data["media_assets"], 8))
            if len(briefs) != len(assets):
                raise ValueError("COURSE_MEDIA_COVERAGE")
            used_documents = {str(d) for part in parts for d in _strings(part["document_ids"])} | set(_strings(transfer["document_ids"]))
            used_concepts = {str(c) for part in parts for c in _strings(part["concept_ids"])}
            for brief, asset in zip(briefs, assets, strict=True):
                asset.bind(brief)
                brief.bind(str(brief.data["production_ref"]), documents=used_documents, concepts=used_concepts,
                           capabilities={str(c["source_ref"]) for c in capacities}, notions=set(_strings(brief.data["notion_refs"])))
        if len(encoded(data)) > 128 * 1024:
            raise ValueError("COURSE_CHAPTER_SIZE")
        object.__setattr__(self, "data", freeze_safe_mapping(data))
        if _INTERNAL.search(self.visible_text(teacher=True)):
            raise ValueError("COURSE_INTERNAL_METADATA")

    def bind_context(self, context: P0Context) -> None:
        if context.resource_type != "COURSE" or context.institutional is None:
            raise ValueError("COURSE_CONTEXT_REQUIRED")
        header = object_data(self.data["program_header"])
        for key in ("frame", "program_ref", "program_version", "theme_ref", "question_ref"):
            if header[key] != context.institutional[key]:
                raise ValueError("COURSE_PROGRAM_BINDING")
        resolution = object_data(context.data["institutional_resolution"])
        for capability in items(self.data["capabilities"]):
            if capability["authority_status"] == "ADMITTED_A_EXACT_SCOPE":
                from backend.modules.pedagogical_design.contracts.dto.program_authority import (
                    alignment_axes,
                )

                if alignment_axes(resolution)["institutional_alignment"] == "UNVERIFIED" or not any(
                    c["capacity_ref"] == capability["source_ref"] and c["label"] == capability["label"]
                    for c in items(resolution["capacities"], 16)):
                    raise ValueError("COURSE_CAPABILITY_AUTHORITY_BINDING")
        if header["question_label"] != object_data(resolution["question"])["official_label"]:
            raise ValueError("COURSE_PROGRAM_BINDING")
        if header["subject_label"] != context.data["discipline"] or set(_strings(self.data["notions"])) != set(_strings(context.data["topics"])):
            raise ValueError("COURSE_PROGRAM_BINDING")
        level_labels = {"FIRST_STMG": "Première STMG", "FINAL_STMG": "Terminale STMG"}
        if header["level_label"] != level_labels.get(str(context.data["level"])):
            raise ValueError("COURSE_PROGRAM_BINDING")
        if "visual_briefs" in self.data:
            for brief in visual_briefs(self.data["visual_briefs"]):
                if not set(_strings(brief.data["notion_refs"])) <= set(_strings(context.institutional["notion_refs"])):
                    raise ValueError("VISUAL_NOTION_BINDING")

    def bind_production(self, production_ref: str) -> None:
        if "visual_briefs" in self.data and any(b.data["production_ref"] != production_ref for b in visual_briefs(self.data["visual_briefs"])):
            raise ValueError("VISUAL_PRODUCTION_BINDING")

    def media(self, *, teacher: bool = False) -> tuple[CourseMedia, ...]:
        if "visual_briefs" not in self.data:
            return ()
        pairs = tuple(CourseMedia(b, MediaAsset(a)) for b, a in zip(
            visual_briefs(self.data["visual_briefs"]), items(self.data["media_assets"], 8), strict=True))
        return tuple(p for p in pairs if p.brief.data["teacher_visibility" if teacher else "student_visibility"])

    def media_review_context(self) -> list[dict[str, object]]:
        if "visual_briefs" not in self.data:
            return []
        return [b.review_context(str(a["png_sha256"])) for b, a in zip(
            visual_briefs(self.data["visual_briefs"]), items(self.data["media_assets"], 8), strict=True)]

    def projection(self, *, teacher: bool = False) -> dict[str, object]:
        data = object_data(as_plain(self.data))
        data["documents"] = [{k: as_plain(v) for k, v in d.items() if k != "provenance"} for d in items(self.data["documents"])]
        data["capabilities"] = [{"id": c["id"], "label": c["label"]} for c in items(self.data["capabilities"])]
        if "visual_briefs" in data:
            data.pop("visual_briefs")
            data["media_assets"] = [p.asset.projection(p.brief) for p in self.media(teacher=teacher)]
        if not teacher:
            data.pop("teacher_answers")
        return data

    def visible_text(self, *, teacher: bool = False) -> str:
        visible = self.projection(teacher=teacher)
        header = object_data(visible["program_header"])
        visible["program_header"] = {k: v for k, v in header.items() if k.endswith("_label")}
        visible.pop("contract_id")
        if "media_assets" in visible:
            visible["media_assets"] = [{k: row[k] for k in ("caption", "alt_text")} for row in items(visible["media_assets"], 8)]
            visible["diagram_text"] = [as_plain(pair.brief.data["diagram"]) for pair in self.media(teacher=teacher)]
        def text(value: object) -> list[str]:
            if isinstance(value, str):
                return [value]
            if isinstance(value, Mapping):
                return [s for v in value.values() for s in text(v)]
            if isinstance(value, (list, tuple)):
                return [s for v in value for s in text(v)]
            return []
        return "\n".join(text(visible))

    def checks(self) -> dict[str, bool]:
        return dict.fromkeys(CHECK_NAMES, True)

    def sections(self) -> list[dict[str, object]]:
        """Readable compatibility projection for the existing production screen."""
        result: list[dict[str, object]] = [{"section_id": "S_OBJECTIVES", "heading": "Repères du chapitre", "text":
                   "\n".join(str(c["label"]) for c in items(self.data["capabilities"]))},
                  {"section_id": "S_CONTEXT", "heading": str(object_data(self.data["context"])["title"]),
                   "text": str(object_data(self.data["context"])["text"])}]
        documents = {str(d["id"]): d for d in items(self.data["documents"])}
        questions = {str(q["id"]): q for q in items(self.data["questions"])}
        concepts = {str(c["id"]): c for c in items(self.data["concepts"])}
        for part in items(self.data["parts"]):
            lines: list[str] = []
            for ref in cast(tuple[str, ...], part["document_ids"]):
                doc = documents[ref]
                lines.extend((str(doc["title"]), str(doc["text"])))
                if doc["table"] is not None:
                    table = object_data(doc["table"])
                    lines.append(" | ".join(_strings(table["columns"], 5)))
                    lines.extend(" | ".join(cast(tuple[str, ...], row)) for row in cast(tuple[object, ...], table["rows"]))
            for ref in (*cast(tuple[str, ...], part["observation"]), *cast(tuple[str, ...], part["analysis"])):
                q = questions[ref]
                lines.append(str(q["number"]) + ". " + str(q["prompt"]))
            for ref in cast(tuple[str, ...], part["concept_ids"]):
                c = concepts[ref]
                lines.extend(("Notion — " + str(c["notion"]), str(c["definition"]), str(c["explanation"]), str(c["example"])))
            for ref in cast(tuple[str, ...], part["reinvestment"]):
                q = questions[ref]
                lines.append(str(q["number"]) + ". " + str(q["prompt"]))
            result.append({"section_id": "S_" + str(part["id"]), "heading": part["title"], "text": "\n\n".join(lines)})
        result.append({"section_id": "S_KNOWLEDGE", "heading": "Tester ses connaissances", "text":
            "\n".join(str(questions[q]["number"]) + ". " + str(questions[q]["prompt"]) for q in cast(tuple[str, ...], self.data["knowledge_check"]))})
        transfer = object_data(self.data["transfer"])
        result.append({"section_id": "S_TRANSFER", "heading": transfer["title"], "text":
            "\n\n".join([str(documents[d]["text"]) for d in cast(tuple[str, ...], transfer["document_ids"])] +
                [str(questions[q]["number"]) + ". " + str(questions[q]["prompt"]) for q in cast(tuple[str, ...], transfer["question_ids"])])})
        result.append({"section_id": "S_SYNTHESIS", "heading": "À retenir", "text": self.data["synthesis"]})
        return result
