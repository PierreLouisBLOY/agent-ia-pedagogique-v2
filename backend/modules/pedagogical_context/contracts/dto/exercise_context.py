"""Explicit exercise focus; missing institutional relations are never inferred."""
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    as_plain,
    fingerprint,
    items,
    nonempty,
    object_data,
)
from backend.modules.pedagogical_design.contracts.dto.case_study import CASE_CONTEXT

EXERCISE_CONTEXT = "P0-CONTEXT-EXERCISE-1.0"
FOCUSED_EXERCISE_CONTEXT = "P0-CONTEXT-EXERCISE-1.1"
FOCUSED_CONTEXTS = frozenset({FOCUSED_EXERCISE_CONTEXT, CASE_CONTEXT})
EXERCISE_CONTEXTS = frozenset({EXERCISE_CONTEXT, *FOCUSED_CONTEXTS})
LOCAL_FOCUS_AUTHORITY = "LOCAL_PEDAGOGICAL_SELECTION_NO_NARROWER_OFFICIAL_CLAIM"


@dataclass(frozen=True, slots=True)
class ExerciseQuestionFocus:
    source_question_ref: str
    source_question_sha256: str
    local_question_label: str
    authority: str

    def __post_init__(self) -> None:
        nonempty(self.source_question_ref, 200)
        if not isinstance(self.source_question_sha256, str) or re.fullmatch(r"[a-f0-9]{64}", self.source_question_sha256) is None:
            raise ValueError("EXERCISE_FOCUS_SOURCE_HASH")
        label = nonempty(self.local_question_label, 1000)
        if label.count("?") != 1 or not label.endswith("?") or label.strip() != label or not label[:-1].strip():
            raise ValueError("EXERCISE_FOCUS_COMPONENT")
        if self.authority != LOCAL_FOCUS_AUTHORITY:
            raise ValueError("EXERCISE_FOCUS_LOCAL_AUTHORITY")

    @classmethod
    def from_value(cls, value: object) -> "ExerciseQuestionFocus":
        row = object_data(value, {"source_question_ref", "source_question_sha256", "local_question_label", "authority"})
        return cls(*(cast(str, row[k]) for k in ("source_question_ref", "source_question_sha256", "local_question_label", "authority")))

    def bind(self, question: Mapping[str, object], *, question_ref: str, program_version: object) -> str:
        if (self.source_question_ref != question_ref or question.get("id") != question_ref
                or question.get("element_type") != "QUESTION" or question.get("framework_version_id") != program_version):
            raise ValueError("EXERCISE_FOCUS_SOURCE_BINDING")
        if fingerprint(question) != self.source_question_sha256:
            raise ValueError("EXERCISE_FOCUS_SOURCE_CHANGED")
        source_label = nonempty(question.get("official_label"), 1000)
        parts = re.findall(r"[^?]+\?", source_label)
        if not parts or "".join(parts).strip() != source_label.strip() or any(not part[:-1].strip() for part in parts):
            raise ValueError("EXERCISE_FOCUS_SOURCE_PARTITION")
        if [part.strip() for part in parts].count(self.local_question_label) != 1:
            raise ValueError("EXERCISE_FOCUS_COMPONENT_NOT_UNIQUE")
        return self.local_question_label


def exercise_focus(context: Mapping[str, object]) -> dict[str, object]:
    if context.get("contract_id") not in EXERCISE_CONTEXTS or context.get("resource_type") != "EXERCISE":
        raise ValueError("EXERCISE_CONTEXT_REQUIRED")
    selection = object_data(context["institutional"])
    resolution = object_data(context["institutional_resolution"])
    justification = nonempty(context.get("exercise_focus_justification"), 2000)
    question = object_data(resolution.get("question"))
    question_ref = nonempty(selection["question_ref"], 200)
    label = nonempty(question.get("official_label"), 1000)
    if question.get("id") != question_ref:
        raise ValueError("EXERCISE_SINGLE_QUESTION_BINDING")
    local = None
    if context["contract_id"] in FOCUSED_CONTEXTS:
        local = ExerciseQuestionFocus.from_value(context.get("exercise_focus_selection"))
        selected_label = local.bind(question, question_ref=question_ref, program_version=selection["program_version"])
    else:
        if label.count("?") != 1:
            raise ValueError("EXERCISE_SINGLE_QUESTION_BINDING")
        selected_label = label
    if any(resolution.get(key) != selection[key] for key in ("program_ref", "program_version")):
        raise ValueError("EXERCISE_PROGRAM_BINDING")
    result: dict[str, object] = {"question_ref": question_ref, "question_label": selected_label,
                                "program_ref": selection["program_ref"],
                                "program_version": selection["program_version"],
                                "local_focus_justification": justification,
                                "capacity_scope": resolution.get("capacity_scope", "EXPLICIT_QUESTION_RELATIONS")}
    if local is not None:
        result.update(source_question_label=label, source_question_sha256=local.source_question_sha256,
                      local_focus_authority=local.authority)
    scope_elements: set[str] = set()
    if local is not None and resolution.get("exercise_attachment_scope") is not None:
        scope = object_data(resolution["exercise_attachment_scope"], {
            "schema", "question_ref", "source_question_sha256", "program_version", "selection_sha256", "element_refs"})
        if (scope["schema"] != "EXERCISE-QUESTION-ATTACHMENT-SCOPE-1.0"
                or scope["question_ref"] != question_ref
                or scope["source_question_sha256"] != local.source_question_sha256
                or scope["program_version"] != selection["program_version"]
                or scope["selection_sha256"] != fingerprint(selection)
                or resolution.get("selection_sha256") != fingerprint(selection)):
            raise ValueError("EXERCISE_FOCUS_ATTACHMENT_SCOPE")
        refs = scope["element_refs"]
        if (not isinstance(refs, (list, tuple)) or not 1 <= len(refs) <= 10000
                or any(not isinstance(ref, str) or not ref for ref in refs)
                or len(set(refs)) != len(refs) or question_ref not in refs):
            raise ValueError("EXERCISE_FOCUS_ATTACHMENT_SCOPE")
        scope_elements = set(refs)
    for kind, selected_key, row_key in (("capacities", "capacity_refs", "capacity_ref"),
                                        ("notions", "notion_refs", "notion_ref")):
        selected = selection[selected_key]
        rows = items(resolution.get(kind), 16)
        if not isinstance(selected, (list, tuple)) or not selected or len(rows) != len(selected):
            raise ValueError("EXERCISE_FOCUS_COVERAGE")
        by_ref = {str(row.get(row_key)): row for row in rows}
        if len(by_ref) != len(rows) or set(by_ref) != set(selected):
            raise ValueError("EXERCISE_FOCUS_COVERAGE")
        projected = []
        for number, ref in enumerate(selected, 1):
            row = by_ref[str(ref)]
            explicit = row.get("question_ref") == question_ref
            if kind == "capacities" and not explicit:
                explicit = resolution.get("capacity_scope") == "SELECTED_THEME_OR_QUESTION_NO_NARROWER_CLAIM"
            if kind == "notions" and not explicit:
                # Consume the resolver's actual attachment; do not invent a
                # question_ref field absent from its historical wire contract.
                explicit = any(
                    attachment.get("notion_ref", attachment.get("notion_id")) == ref
                    and attachment.get("element_ref", attachment.get("framework_element_id")) in ({question_ref} | scope_elements)
                    and attachment.get("disposition", attachment.get("status")) in {"VERIFIED_EXPLICIT", "VERIFIED_IMPLICIT", "ADMITTED"}
                    for attachment in items(resolution.get("attachments", []), 128))
            if not explicit:
                raise ValueError("EXERCISE_FOCUS_RELATION_MISSING")
            projected.append({"id": ("C" if kind == "capacities" else "N") + str(number),
                              "ref": ref, "label": nonempty(row["label"], 2000)})
        result[kind] = projected
    # The snapshot may remain CONTENT_GAP for a local original. Dispatch separately
    # requires the existing admitted authority; these rows never manufacture it.
    result["institutional_status"] = resolution["status"]
    return object_data(as_plain(result))
