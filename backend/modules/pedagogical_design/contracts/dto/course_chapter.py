"""Versioned learning chapter; answers and internal provenance never enter student views."""
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

from backend.modules.materialization_export.contracts.dto.media_asset import CourseMedia, MediaAsset
from backend.modules.pedagogical_context.contracts.dto.course_notions import course_notion_rows
from backend.modules.pedagogical_context.contracts.dto.p0_context import (
    P0_NOTION_COURSE_CONTEXT_CONTRACT,
    P0Context,
)
from backend.modules.pedagogical_context.contracts.dto.real_course_thread import (
    REAL_CHAPTER,
    RealCourseThread,
    thread_from_context,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    as_plain,
    encoded,
    items,
    nonempty,
    object_data,
)
from backend.modules.pedagogical_design.contracts.dto.chapter_assembly import (
    ASSEMBLY_CHAPTER_CONTRACT,
    assembly_projection,
    validate_assembly,
)
from backend.modules.pedagogical_design.contracts.dto.course_table import validate_course_table
from backend.modules.pedagogical_design.contracts.dto.learning_links import (
    require_ordered_answers,
    require_provenance_kind,
    require_subset,
    require_unique_coverage,
)
from backend.modules.pedagogical_design.contracts.dto.visual_brief import visual_briefs
from backend.shared_kernel._safe_data import freeze_safe_mapping

COURSE_CHAPTER_CONTRACT = "COURSE-CHAPTER-1.0"
COURSE_LINEAGE_CONTRACT = "COURSE-CHAPTER-LINEAGE-3.0"
COURSE_MEDIA_CONTRACT = "COURSE-CHAPTER-MEDIA-2.0"
COURSE_PRODUCTION_CONTRACT = "R6-P0-PRODUCTION-COURSE-2.0"
COURSE_NOTION_LINEAGE_CONTRACT = "COURSE-CHAPTER-LINEAGE-4.0"
COURSE_NOTION_PRODUCTION_CONTRACT = "R6-P0-PRODUCTION-COURSE-3.0"
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


def transfer_activities(value: object) -> tuple[dict[str, object], ...]:
    fields = {"title", "document_ids", "question_ids"}
    if isinstance(value, Mapping):
        return (object_data(value, fields),)
    activities = items(value, 2)
    if len(activities) != 2:
        raise ValueError("COURSE_PROGRESSIVE_ACTIVITIES_REQUIRED")
    return tuple(object_data(activity, fields) for activity in activities)


def _table(value: object) -> None:
    validate_course_table(value)


@dataclass(frozen=True, slots=True)
class CourseChapter:
    data: Mapping[str, object]

    def __post_init__(self) -> None:
        assembly = self.data.get("contract_id") == ASSEMBLY_CHAPTER_CONTRACT
        illustrated = self.data.get("contract_id") == COURSE_MEDIA_CONTRACT or (assembly and "visual_briefs" in self.data)
        real = self.data.get("contract_id") == REAL_CHAPTER
        fields = _FIELDS | ({"assembly"} if assembly else set()) | ({"organization_thread"} if real else set()) | ({"visual_briefs", "media_assets"} if illustrated else set())
        data = object_data(self.data, fields)
        if data["contract_id"] not in {
            COURSE_CHAPTER_CONTRACT, COURSE_MEDIA_CONTRACT, COURSE_LINEAGE_CONTRACT, COURSE_NOTION_LINEAGE_CONTRACT, ASSEMBLY_CHAPTER_CONTRACT, REAL_CHAPTER
        }:
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
        if real:
            RealCourseThread(object_data(data["organization_thread"]))
        story = object_data(data["context"], {"title", "text"})
        nonempty(story["title"], 200)
        nonempty(story["text"], 8000)
        documents = _rows(data["documents"], {"id", "title", "function", "text", "table", "provenance"})
        for doc in documents:
            for key in ("title", "function", "text"):
                nonempty(doc[key], 8000)
            _table(doc["table"])
            provenance = object_data(doc["provenance"], {"kind", "source_ref"})
            require_provenance_kind(provenance["kind"], code="COURSE_DOCUMENT_PROVENANCE")
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
            require_subset(_strings(row["document_ids"], required=False), doc_ids, code="COURSE_DOCUMENT_LINK")
            require_subset(_strings(row["capability_ids"]), cap_ids, code="COURSE_CAPABILITY_LINK")
            response = object_data(row["response"], {"kind", "lines", "table"})
            if response["kind"] not in {"LINES", "TABLE"} or type(response["lines"]) is not int or not 1 <= response["lines"] <= 8:
                raise ValueError("COURSE_RESPONSE_SPACE")
            _table(response["table"])
            if (response["kind"] == "TABLE") != (response["table"] is not None):
                raise ValueError("COURSE_RESPONSE_SPACE")
        question_ids = {str(q["id"]) for q in questions}
        concept_ids = {str(c["id"]) for c in concepts}
        progressive = isinstance(data["transfer"], (tuple, list))
        part_fields = {"id", "title", "document_ids", "observation", "analysis", "concept_ids", "reinvestment"}
        if progressive:
            part_fields.add("formalization")
        parts = _rows(data["parts"], part_fields, maximum=8)
        if progressive and (assembly or illustrated):
            raise ValueError("COURSE_PROGRESSIVE_FORMAT")
        activity_ids: list[str] = []
        introduced: list[str] = []
        available_documents: set[str] = set()
        question_documents = {str(q["id"]): set(_strings(q["document_ids"], required=False)) for q in questions}
        for row in parts:
            nonempty(row["title"], 200)
            if not set(_strings(row["document_ids"])) <= doc_ids or not set(_strings(row["concept_ids"])) <= concept_ids:
                raise ValueError("COURSE_PART_LINK")
            part_docs = set(_strings(row["document_ids"]))
            available_documents.update(part_docs)
            if progressive:
                if row["formalization"] not in ("AFTER_DOCUMENTS", "AFTER_OBSERVATION", "AFTER_ANALYSIS"):
                    raise ValueError("COURSE_PROGRESSIVE_FORMALIZATION")
                if not any(question_documents.get(q, set()) & part_docs for q in _strings(row["observation"])):
                    raise ValueError("COURSE_PROGRESSIVE_OBSERVATION_SUPPORT")
                introduced.extend(_strings(row["concept_ids"], 3))
                if len(part_docs) > 2:
                    raise ValueError("COURSE_PROGRESSIVE_DOCUMENT_LIMIT")
            for role in ("observation", "analysis", "reinvestment"):
                refs = _strings(row[role], required=not assembly)
                if not set(refs) <= question_ids:
                    raise ValueError("COURSE_QUESTION_LINK")
                if progressive and any(not question_documents[q] <= available_documents for q in refs):
                    raise ValueError("COURSE_PROGRESSIVE_DOCUMENT_ORDER")
                activity_ids.extend(refs)
        knowledge = _strings(data["knowledge_check"])
        activity_ids.extend(knowledge)
        activities = transfer_activities(data["transfer"])
        for transfer in activities:
            nonempty(transfer["title"], 200)
            support = set(_strings(transfer["document_ids"]))
            if not support <= doc_ids:
                raise ValueError("COURSE_DOCUMENT_LINK")
            refs = _strings(transfer["question_ids"])
            if progressive and any(not question_documents.get(q) or not question_documents[q] <= support for q in refs):
                raise ValueError("COURSE_PROGRESSIVE_ACTIVITY_SUPPORT")
            activity_ids.extend(refs)
        if progressive:
            if any(q["id"] != f"Q{i}" for i, q in enumerate(questions, 1)):
                raise ValueError("COURSE_PROGRESSIVE_QUESTION_ID")
            notions = set(_strings(data["notions"]))
            if len(notions) > 3 and len(parts) < 2:
                raise ValueError("COURSE_PROGRESSIVE_PARTS_REQUIRED")
            if {str(concept["notion"]) for concept in concepts} != notions:
                raise ValueError("COURSE_PROGRESSIVE_NOTION_COVERAGE")
            if any(not question_documents.get(q, set()) <= available_documents for q in knowledge):
                raise ValueError("COURSE_PROGRESSIVE_DOCUMENT_ORDER")
            require_unique_coverage(introduced, concept_ids, code="COURSE_PROGRESSIVE_CONCEPT_COVERAGE")
            if activity_ids != [str(q["id"]) for q in questions]:
                raise ValueError("COURSE_PROGRESSIVE_QUESTION_ORDER")
            if activities[0]["title"] == activities[1]["title"]:
                raise ValueError("COURSE_PROGRESSIVE_ACTIVITY_TITLE")
        require_unique_coverage(activity_ids, question_ids, code="COURSE_QUESTION_COVERAGE")
        nonempty(data["synthesis"], 8000)
        answers = _rows(data["teacher_answers"], {"id", "expected_answer", "rationale", "vigilance", "remediation"}, maximum=60)
        require_ordered_answers([q["id"] for q in questions], [a["id"] for a in answers], code="COURSE_ANSWER_LINK")
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
        if assembly:
            if activity_ids != [str(q["id"]) for q in questions]:
                raise ValueError("ASSEMBLY_QUESTION_ORDER")
            validate_assembly(data)
        if len(encoded(data)) > 128 * 1024:
            raise ValueError("COURSE_CHAPTER_SIZE")
        object.__setattr__(self, "data", freeze_safe_mapping(data))
        if _INTERNAL.search(self.visible_text(teacher=True)):
            raise ValueError("COURSE_INTERNAL_METADATA")

    def bind_context(self, context: P0Context) -> None:
        if context.resource_type != "COURSE" or context.institutional is None:
            raise ValueError("COURSE_CONTEXT_REQUIRED")
        notion_chapter = self.data["contract_id"] in {COURSE_NOTION_LINEAGE_CONTRACT, REAL_CHAPTER}
        thread = thread_from_context(context.data)
        if (self.data["contract_id"] == REAL_CHAPTER) != (thread is not None):
            raise ValueError("COURSE_REAL_CONTEXT_BINDING")
        if thread is not None and as_plain(self.data["organization_thread"]) != thread.as_dict():
            raise ValueError("COURSE_REAL_ORGANIZATION_CHANGED")
        if notion_chapter != (context.data["contract_id"] == P0_NOTION_COURSE_CONTEXT_CONTRACT):
            raise ValueError("COURSE_NOTION_CONTEXT_BINDING")
        if notion_chapter and str(self.data["chapter_number"]) != object_data(context.data["local_progression"])["chapter"]:
            raise ValueError("COURSE_NOTION_CHAPTER_NUMBER_BINDING")
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
        expected_notions = ([row["label"] for row in course_notion_rows(context)]
                           if notion_chapter else _strings(context.data["topics"]))
        if header["subject_label"] != context.data["discipline"] or set(_strings(self.data["notions"])) != set(expected_notions):
            raise ValueError("COURSE_PROGRAM_BINDING")
        if notion_chapter and {str(row["notion"]) for row in items(self.data["concepts"])} != set(expected_notions):
            raise ValueError("COURSE_NOTION_CONCEPT_COVERAGE")
        if notion_chapter:
            linked = {str(ref) for part in items(self.data["parts"])
                      for ref in _strings(part["concept_ids"])}
            if linked != {str(row["id"]) for row in items(self.data["concepts"])}:
                raise ValueError("COURSE_NOTION_CONCEPT_DELIVERY_COVERAGE")
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
        if "assembly" in data:
            data["assembly"] = assembly_projection(data["assembly"], teacher=teacher)
        if "organization_thread" in data:
            data["organization_thread"] = RealCourseThread(object_data(data["organization_thread"])).public_projection()
        if not teacher:
            data.pop("teacher_answers")
        return data

    def visible_text(self, *, teacher: bool = False) -> str:
        visible = self.projection(teacher=teacher)
        header = object_data(visible["program_header"])
        visible["program_header"] = {k: v for k, v in header.items() if k.endswith("_label")}
        visible.pop("contract_id")
        if "assembly" in visible:
            a = object_data(visible["assembly"])
            visible["assembly"] = {k: a[k] for k in ("thread", "parts", "concept_vigilance")}
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
        if "assembly" in self.data:
            result[1]["text"] = str(result[1]["text"]) + "\n\n" + str(object_data(object_data(self.data["assembly"])["thread"])["notice"])
        if "organization_thread" in self.data:
            thread = RealCourseThread(object_data(self.data["organization_thread"]))
            credits = "\n".join(str(s["title"]) + " — " + str(s["publisher"]) + " — "
                                + str(s["retrieved_on"]) + " — " + str(s["source_url"]) + " — " + str(s["rights"])
                                for s in thread.source_rows())
            result[1]["text"] = str(result[1]["text"]) + "\n\nOrganisation réelle : " + thread.label + "\n" + credits
        documents = {str(d["id"]): d for d in items(self.data["documents"])}
        questions = {str(q["id"]): q for q in items(self.data["questions"])}
        concepts = {str(c["id"]): c for c in items(self.data["concepts"])}
        for part in items(self.data["parts"]):
            lines: list[str] = []
            if "assembly" in self.data:
                meta = next(m for m in items(object_data(self.data["assembly"])["parts"]) if m["id"] == part["id"])
                lines.append(str(meta["transition"]))
            for ref in cast(tuple[str, ...], part["document_ids"]):
                doc = documents[ref]
                lines.extend((str(doc["title"]), str(doc["text"])))
                if doc["table"] is not None:
                    table = object_data(doc["table"])
                    lines.append(" | ".join(_strings(table["columns"], 5)))
                    lines.extend(" | ".join(cast(tuple[str, ...], row)) for row in cast(tuple[object, ...], table["rows"]))
            doc_end = len(lines)
            for ref in (*cast(tuple[str, ...], part["observation"]), *cast(tuple[str, ...], part["analysis"])):
                q = questions[ref]
                lines.append(str(q["number"]) + ". " + str(q["prompt"]))
            concept_start = len(lines)
            for ref in cast(tuple[str, ...], part["concept_ids"]):
                c = concepts[ref]
                lines.extend(("Notion — " + str(c["notion"]), str(c["definition"]), str(c["explanation"]), str(c["example"])))
            position = part.get("formalization")
            if position in ("AFTER_DOCUMENTS", "AFTER_OBSERVATION"):
                insert_at = doc_end + (len(cast(tuple[str, ...], part["observation"])) if position == "AFTER_OBSERVATION" else 0)
                lines[insert_at:] = lines[concept_start:] + lines[insert_at:concept_start]
            for ref in cast(tuple[str, ...], part["reinvestment"]):
                q = questions[ref]
                lines.append(str(q["number"]) + ". " + str(q["prompt"]))
            if "assembly" in self.data and object_data(meta["formalization"])["position"] == "BEFORE_ACTIVITY":
                start = next(i for i, line in enumerate(lines) if line.startswith("Notion — "))
                count = 4 * len(cast(tuple[str, ...], part["concept_ids"]))
                block = lines[start:start+count]
                del lines[start:start+count]
                lines[1:1] = block
            result.append({"section_id": "S_" + str(part["id"]), "heading": part["title"], "text": "\n\n".join(lines)})
        result.append({"section_id": "S_KNOWLEDGE", "heading": "Tester ses connaissances", "text":
            "\n".join(str(questions[q]["number"]) + ". " + str(questions[q]["prompt"]) for q in cast(tuple[str, ...], self.data["knowledge_check"]))})
        activities = transfer_activities(self.data["transfer"])
        for index, transfer in enumerate(activities, 1):
            paragraphs = [str(documents[d]["text"]) for d in cast(tuple[str, ...], transfer["document_ids"])]
            paragraphs.extend(str(questions[q]["number"]) + ". " + str(questions[q]["prompt"])
                              for q in cast(tuple[str, ...], transfer["question_ids"]))
            result.append({"section_id": "S_TRANSFER" if len(activities) == 1 else f"S_ACTIVITY_{index}",
                           "heading": transfer["title"], "text": "\n\n".join(paragraphs)})
        result.append({"section_id": "S_SYNTHESIS", "heading": "À retenir", "text": self.data["synthesis"]})
        if "assembly" in self.data or len(activities) == 2:
            synthesis = result.pop()
            result.insert(len(result)-1-len(activities), synthesis)
        return result
