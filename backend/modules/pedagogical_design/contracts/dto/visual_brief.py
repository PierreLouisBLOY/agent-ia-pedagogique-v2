"""A pedagogical description, never an image, path, URL or admission decision."""
import re
from collections.abc import Mapping
from dataclasses import dataclass

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    as_plain,
    fingerprint,
    items,
    nonempty,
    object_data,
)
from backend.shared_kernel._safe_data import freeze_safe_mapping

VISUAL_BRIEF_CONTRACT = "VISUAL-BRIEF-1.0"
FIELDS = {"contract_id", "visual_id", "production_ref", "section_ref", "learning_objective",
          "institutional_capability_ref", "notion_refs", "visual_type", "pedagogical_function",
          "content_description", "must_show", "must_not_show", "caption", "alt_text",
          "student_visibility", "teacher_visibility", "preferred_position", "source_policy",
          "style_policy", "diagram"}
VISUAL_REVIEW_AXES = ("exactitude", "niveau", "utilite", "coherence", "absence_surinterpretation")
LAYOUTS = {"FLOWCHART": "FLOW", "ICON_SET": "RESOURCES", "PROCESS_MAP": "CYCLE", "ORG_CHART": "RESPONSIBILITIES"}


def strings(value: object, maximum: int = 16, *, empty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or not int(not empty) <= len(value) <= maximum:
        raise ValueError("VISUAL_LIST")
    result = tuple(nonempty(v, 500) for v in value)
    if len(result) != len(set(result)):
        raise ValueError("VISUAL_DUPLICATE")
    return result


@dataclass(frozen=True, slots=True)
class VisualBrief:
    data: Mapping[str, object]

    def __post_init__(self) -> None:
        d = object_data(self.data, FIELDS)
        if d["contract_id"] != VISUAL_BRIEF_CONTRACT:
            raise ValueError("VISUAL_CONTRACT")
        for field in ("visual_id", "section_ref"):
            if re.fullmatch(r"[A-Z][A-Z0-9_]{0,39}", str(d[field])) is None:
                raise ValueError("VISUAL_ID")
        if re.fullmatch(r"prod:[a-zA-Z0-9_-]{1,64}", str(d["production_ref"])) is None:
            raise ValueError("VISUAL_PRODUCTION")
        for field in ("learning_objective", "institutional_capability_ref", "pedagogical_function",
                      "content_description", "caption", "alt_text"):
            nonempty(d[field], 1000)
        for field in ("notion_refs", "must_show", "must_not_show"):
            strings(d[field], empty=field == "must_not_show")
        for field in ("student_visibility", "teacher_visibility"):
            if type(d[field]) is not bool:
                raise ValueError("VISUAL_VISIBILITY")
        if not (d["student_visibility"] or d["teacher_visibility"]):
            raise ValueError("VISUAL_INVISIBLE")
        if d["preferred_position"] not in {"AFTER_DOCUMENT", "AFTER_CONCEPT"}:
            raise ValueError("VISUAL_POSITION")
        if d["source_policy"] not in {"LOCAL_DETERMINISTIC", "USER_SUPPLIED", "LICENSED_EXTERNAL", "GENERATED_ADMITTED"}:
            raise ValueError("VISUAL_SOURCE_POLICY")
        if d["style_policy"] != "COURSE_LOCAL_DIAGRAM_V1":
            raise ValueError("VISUAL_STYLE")
        if d["source_policy"] == "LOCAL_DETERMINISTIC":
            diagram = object_data(d["diagram"], {"layout", "nodes", "edges", "note"})
            if LAYOUTS.get(str(d["visual_type"])) != diagram["layout"]:
                raise ValueError("VISUAL_LAYOUT")
            nodes = items(diagram["nodes"], 5)
            if len(nodes) != (5 if diagram["layout"] == "RESOURCES" else 4):
                raise ValueError("VISUAL_NODES")
            ids = []
            for row in nodes:
                object_data(row, {"id", "label", "detail", "icon"})
                ids.append(nonempty(row["id"], 30))
                nonempty(row["label"], 70)
                nonempty(row["detail"], 140)
                if row["icon"] not in {"NONE", "PERSON", "COINS", "BOX", "IDEA", "SCREEN"}:
                    raise ValueError("VISUAL_ICON")
            if len(ids) != len(set(ids)):
                raise ValueError("VISUAL_DUPLICATE")
            edges = items(diagram["edges"], 8)
            pairs = []
            for row in edges:
                object_data(row, {"source", "target", "label"})
                if row["source"] not in ids or row["target"] not in ids or row["source"] == row["target"]:
                    raise ValueError("VISUAL_EDGE")
                if not isinstance(row["label"], str) or len(row["label"]) > 50:
                    raise ValueError("VISUAL_EDGE")
                pairs.append((row["source"], row["target"]))
            if len(pairs) != len(set(pairs)):
                raise ValueError("VISUAL_DUPLICATE")
            nonempty(diagram["note"], 220)
        elif d["diagram"] is not None or d["visual_type"] not in {"CONTEXT_PHOTO", "ANNOTATED_DOCUMENT", "DIAGRAM", "INFOGRAPHIC"}:
            raise ValueError("VISUAL_IMPORTED_TYPE")
        object.__setattr__(self, "data", freeze_safe_mapping(d))

    @property
    def sha256(self) -> str:
        return fingerprint(self.data)

    def bind(self, production_ref: str, *, documents: set[str], concepts: set[str],
             capabilities: set[str], notions: set[str]) -> None:
        targets = documents if self.data["preferred_position"] == "AFTER_DOCUMENT" else concepts
        if (self.data["production_ref"] != production_ref or self.data["section_ref"] not in targets
                or self.data["institutional_capability_ref"] not in capabilities
                or not set(strings(self.data["notion_refs"])) <= notions):
            raise ValueError("VISUAL_CONTEXT_BINDING")

    def review_context(self, asset_sha256: str) -> dict[str, object]:
        d = object_data(as_plain(self.data))
        diagram = d["diagram"]
        if diagram is not None:
            diagram = object_data(diagram)
            # A diagram destination is a node reference, not runtime authority.
            # Keep the shared scanner intact and use unambiguous review fields.
            diagram["edges"] = [{"from_node": e["source"], "to_node": e["target"], "label": e["label"]}
                                for e in items(diagram["edges"], 8)]
        return {"visual_id": d["visual_id"], "learning_objective": d["learning_objective"],
                "pedagogical_function": d["pedagogical_function"], "content_description": d["content_description"],
                "caption": d["caption"], "alt_text": d["alt_text"], "must_show": d["must_show"],
                "must_not_show": d["must_not_show"], "diagram": diagram,
                "student_visibility": d["student_visibility"], "teacher_visibility": d["teacher_visibility"],
                "brief_sha256": self.sha256, "asset_sha256": asset_sha256,
                "axes": list(VISUAL_REVIEW_AXES), "pixel_inspection": "SEPARATE_REQUIRED"}


def visual_briefs(value: object) -> tuple[VisualBrief, ...]:
    rows = items(value, 8)
    result = tuple(VisualBrief(row) for row in rows)
    if not result or len({b.data["visual_id"] for b in result}) != len(result):
        raise ValueError("VISUAL_BRIEFS_REQUIRED_UNIQUE")
    return result
