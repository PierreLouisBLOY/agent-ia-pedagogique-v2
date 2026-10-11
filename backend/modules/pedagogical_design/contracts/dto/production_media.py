"""Versioned media dossier: immutable content dependencies and separate audiences."""
import re
from collections.abc import Mapping
from dataclasses import dataclass

from backend.modules.materialization_export.contracts.dto.media_asset import CourseMedia, MediaAsset
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    as_plain,
    fingerprint,
    items,
    nonempty,
    object_data,
)
from backend.modules.pedagogical_design.contracts.dto.visual_brief import VisualBrief
from backend.shared_kernel._safe_data import freeze_safe_mapping

MEDIA_PRODUCTION_CONTRACT = "R6-P0-PRODUCTION-MEDIA-3.0"
MEDIA_PLAN_CONTRACT = "PRODUCTION-MEDIA-1.0"


def dependencies(data: Mapping[str, object]) -> dict[str, str]:
    result = {"context": str(data["context_sha256"])}
    for field, prefix, identifier in (("sections", "section", "section_id"),
                                      ("questions", "question", "question_id"),
                                      ("corrections", "correction", "question_id"),
                                      ("marking", "marking", "question_id")):
        result.update({prefix + ":" + str(row[identifier]): fingerprint(row)
                       for row in items(data[field], 60)})
    return result


def rebind_unchanged_media(parent: Mapping[str, object], child: Mapping[str, object]) -> dict[str, object]:
    """Rebind one pure version/title edit; changed content never reattests an asset."""
    data = object_data(as_plain(child))
    if "media_plan" not in parent:
        return data
    if as_plain(data.get("media_plan")) != as_plain(parent["media_plan"]):
        raise ValueError("PRODUCTION_MEDIA_PLAN_CHANGED")
    if dependencies(parent) != dependencies(data):
        raise ValueError("PRODUCTION_MEDIA_DEPENDENCY_STALE")
    plan = object_data(as_plain(parent["media_plan"]))
    plan["version_ref"] = data["version_ref"]
    exact = ProductionMediaPlan(plan)
    exact.bind(data)
    data["media_plan"] = exact.as_dict()
    return data


def _visible_strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        return [s for child in value.values() for s in _visible_strings(child)]
    if isinstance(value, (list, tuple)):
        return [s for child in value for s in _visible_strings(child)]
    return []


@dataclass(frozen=True, slots=True)
class ProductionMediaPlan:
    data: Mapping[str, object]

    def __post_init__(self) -> None:
        data = object_data(self.data, {"contract_id", "version_ref", "context_sha256", "entries", "no_media_reason"})
        if data["contract_id"] != MEDIA_PLAN_CONTRACT:
            raise ValueError("PRODUCTION_MEDIA_CONTRACT")
        nonempty(data["version_ref"], 100)
        if re.fullmatch(r"[0-9a-f]{64}", str(data["context_sha256"])) is None:
            raise ValueError("PRODUCTION_MEDIA_CONTEXT_HASH")
        entries = items(data["entries"], 8)
        if not entries:
            nonempty(data["no_media_reason"], 1000)
        elif data["no_media_reason"] is not None:
            raise ValueError("PRODUCTION_MEDIA_NO_MEDIA_REASON")
        visual_ids: list[str] = []
        for entry in entries:
            object_data(entry, {"brief", "asset", "required", "dependencies", "omission_reason"})
            brief = VisualBrief(object_data(entry["brief"]))
            visual_ids.append(str(brief.data["visual_id"]))
            if type(entry["required"]) is not bool:
                raise ValueError("PRODUCTION_MEDIA_REQUIRED")
            hashes = object_data(entry["dependencies"])
            if not 1 <= len(hashes) <= 16 or any(re.fullmatch(r"[0-9a-f]{64}", str(v)) is None for v in hashes.values()):
                raise ValueError("PRODUCTION_MEDIA_DEPENDENCIES")
            if entry["asset"] is not None:
                MediaAsset(object_data(entry["asset"])).bind(brief)
                if entry["omission_reason"] is not None:
                    raise ValueError("PRODUCTION_MEDIA_OMISSION_REASON")
            else:
                nonempty(entry["omission_reason"], 1000)
        if len(visual_ids) != len(set(visual_ids)):
            raise ValueError("PRODUCTION_MEDIA_DUPLICATE")
        object.__setattr__(self, "data", freeze_safe_mapping(data))

    def bind(self, data: Mapping[str, object]) -> None:
        if (self.data["version_ref"], self.data["context_sha256"]) != (data["version_ref"], data["context_sha256"]):
            raise ValueError("PRODUCTION_MEDIA_VERSION_BINDING")
        known = dependencies(data)
        context = object_data(data["context"])
        selection = context.get("institutional")
        if items(self.data["entries"], 8):
            resolution = object_data(context.get("institutional_resolution"))
            if selection is None or resolution.get("status") != "RESOLVED_ADMITTED":
                raise ValueError("PRODUCTION_MEDIA_INSTITUTIONAL_REQUIRED")
        selected = object_data(selection) if selection is not None else {}
        def refs(value: object) -> set[str]:
            if not isinstance(value, (tuple, list)) or any(not isinstance(s, str) for s in value):
                raise ValueError("PRODUCTION_MEDIA_INSTITUTIONAL_REFS")
            return set(value)
        capabilities = refs(selected.get("capacity_refs", selected.get("competency_refs", ())))
        notions = refs(selected.get("notion_refs", ()))
        sections = {str(s["section_id"]) for s in items(data["sections"], 16)}
        questions = {str(q["question_id"]) for q in items(data["questions"], 60)}
        for entry in items(self.data["entries"], 8):
            hashes = object_data(entry["dependencies"])
            if "context" not in hashes or any(known.get(k) != v for k, v in hashes.items()):
                raise ValueError("PRODUCTION_MEDIA_DEPENDENCY_STALE")
            brief = VisualBrief(object_data(entry["brief"]))
            brief.bind(str(data["production_ref"]), documents=sections, concepts=questions,
                       capabilities=capabilities, notions=notions)
            anchor = str(brief.data["section_ref"])
            anchor_dep = ("section:" if anchor in sections else "question:") + anchor
            if anchor_dep not in hashes:
                raise ValueError("PRODUCTION_MEDIA_ANCHOR_DEPENDENCY")
            if brief.data["student_visibility"]:
                if any(k.startswith(("correction:", "marking:")) for k in hashes):
                    raise ValueError("PRODUCTION_MEDIA_STUDENT_CORRECTION_DEPENDENCY")
                visible = "\n".join(_visible_strings({k: brief.data[k] for k in ("caption", "alt_text", "diagram")}))
                for answer in items(data["corrections"], 60):
                    expected = str(answer["expected_answer"]).strip()
                    if expected and re.search(r"(?<!\w)" + re.escape(expected) + r"(?!\w)", visible, re.I):
                        raise ValueError("PRODUCTION_MEDIA_STUDENT_ANSWER_LEAK")

    def media(self, audience: str, *, require_complete: bool = True) -> tuple[CourseMedia, ...]:
        if audience not in {"student", "correction", "marking"}:
            raise ValueError("PRODUCTION_MEDIA_AUDIENCE")
        result = []
        for entry in items(self.data["entries"], 8):
            brief = VisualBrief(object_data(entry["brief"]))
            if not brief.data["student_visibility" if audience == "student" else "teacher_visibility"]:
                continue
            if entry["asset"] is None:
                if entry["required"] and require_complete:
                    raise ValueError("PRODUCTION_MEDIA_REQUIRED_MISSING:" + str(brief.data["visual_id"]))
                continue
            result.append(CourseMedia(brief, MediaAsset(object_data(entry["asset"]))))
        return tuple(result)

    def projection(self, audience: str, *, require_complete: bool = False) -> list[dict[str, object]]:
        return [pair.asset.projection(pair.brief) for pair in self.media(audience, require_complete=require_complete)]

    def as_dict(self) -> dict[str, object]:
        return object_data(as_plain(self.data))
