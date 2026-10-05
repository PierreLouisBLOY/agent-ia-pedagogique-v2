"""Exact STMG selection, separate from the teacher's local progression."""
from __future__ import annotations

from collections.abc import Mapping

from backend.modules.knowledge_reference.contracts.dto.stmg_frames import STMG_FRAMES
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import object_data

STMG_CONTEXT_CONTRACT = "STMG-INSTITUTIONAL-CONTEXT-1.0"
FIELDS = {"contract_id", "frame", "education_level", "series", "teaching_subject", "program_ref", "program_version",
          "program_component", "specific_track", "theme_ref", "question_ref", "capacity_refs", "notion_refs", "depth"}


def validate_selection(value: object, *, level: str, discipline: str) -> dict[str, object]:
    data = object_data(value, FIELDS)
    frame = STMG_FRAMES.get(str(data["frame"]))
    if frame is None or data["contract_id"] != STMG_CONTEXT_CONTRACT or data["series"] != "STMG":
        raise ValueError("P0_INSTITUTIONAL_FRAME")
    if (level, data["education_level"], data["teaching_subject"], data["program_component"], data["specific_track"]) != frame[:5]:
        raise ValueError("P0_INSTITUTIONAL_FRAME")
    if discipline != frame[6]:
        raise ValueError("P0_INSTITUTIONAL_SUBJECT")
    for key in ("program_ref", "program_version", "theme_ref", "question_ref"):
        if not isinstance(data[key], str) or not 1 <= len(str(data[key])) <= 200:
            raise ValueError("P0_INSTITUTIONAL_ID")
    for key in ("capacity_refs", "notion_refs"):
        values = data[key]
        if not isinstance(values, (list, tuple)) or len(values) > 16 or (key == "notion_refs" and not values):
            raise ValueError("P0_INSTITUTIONAL_SELECTION")
        if not all(isinstance(v, str) and 0 < len(v) <= 200 for v in values) or len(set(values)) != len(values):
            raise ValueError("P0_INSTITUTIONAL_SELECTION")
    if data["depth"] not in {"DISCOVERY", "APPLICATION", "ANALYSIS"}:
        raise ValueError("P0_INSTITUTIONAL_DEPTH")
    return data


def institutional_header(context: Mapping[str, object]) -> str | None:
    selection = context.get("institutional")
    if selection is None:
        return None
    data = object_data(selection)
    frame = STMG_FRAMES[str(data["frame"])]
    return ("Première STMG" if frame[0] == "FIRST_STMG" else "Terminale STMG") + " — " + frame[6]
