"""Technical content-ID casing adapter; never changes teaching text or contracts."""
from __future__ import annotations

import copy
import re
from typing import Any

CANDIDATE_STATUS = "CANDIDATE — Ressource générée à contrôler ; aucune validation ou promotion pédagogique n'est attestée."


def bind_candidate_status(content: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    """Attach the local lifecycle label, separately attributed from provider content."""
    result = copy.deepcopy(content)
    limitations = result["limitations"]
    if type(limitations) is not list or not 1 <= len(limitations) <= 16 or any(type(item) is not str or not item.strip() for item in limitations):
        raise ValueError("P0_ORIGINAL_LIMITATIONS_REQUIRED")
    if any("CANDIDATE" in item for item in limitations):
        return result, None
    if len(limitations) == 16:
        raise ValueError("P0_LOCAL_STATUS_LIMITATION_CAPACITY")
    limitations.append(CANDIDATE_STATUS)
    return result, CANDIDATE_STATUS


def normalize_ids(content: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    result = copy.deepcopy(content)
    changes = []
    maps = {}
    for collection, field, prefix in (("sections", "section_id", "S"), ("questions", "question_id", "Q")):
        mapping = {}
        targets = set()
        for row in result[collection]:
            old = row[field]
            if not isinstance(old, str) or not re.fullmatch(prefix + r"[A-Z0-9_-]{1,63}", old, re.IGNORECASE):
                raise ValueError("P0_ID_SHAPE_NOT_CASE_ONLY")
            new = old.upper()
            if old in mapping or new in targets:
                raise ValueError("P0_ID_NORMALIZATION_COLLISION")
            mapping[old] = new
            targets.add(new)
            row[field] = new
            if old != new:
                changes.append({"collection": collection, "field": field, "before": old, "after": new})
        maps[collection] = mapping
    for collection in ("corrections", "marking"):
        for row in result[collection]:
            old = row["question_id"]
            if not isinstance(old, str) or old not in maps["questions"]:
                raise ValueError("P0_ID_REFERENCE_NOT_IN_ORIGINAL_QUESTIONS")
            row["question_id"] = maps["questions"][old]
            if old != row["question_id"]:
                changes.append({"collection": collection, "field": "question_id", "before": old, "after": row["question_id"]})
    return result, changes
