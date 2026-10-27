"""Provider-neutral comparison of two Application preparations, never semantic approval."""
from __future__ import annotations

import unicodedata
from collections.abc import Mapping

from backend.modules.pedagogical_context.contracts.dto.p0_context import P0Context
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    as_plain,
    fingerprint,
    object_data,
)


def _normalized(value: object) -> object:
    if isinstance(value, str):
        return " ".join(unicodedata.normalize("NFKC", value).casefold().split())
    if isinstance(value, Mapping):
        return {str(k): _normalized(v) for k, v in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        items = {_key(_normalized(v)): _normalized(v) for v in value}
        return [items[k] for k in sorted(items)]
    return value


def _key(value: object) -> str:
    return fingerprint(value)


def operation_projection(request: Mapping[str, object]) -> tuple[str, str]:
    context = P0Context(object_data(request.get("context")))
    if context.resource_type != "COURSE" or context.course_format != "CHAPTER":
        raise ValueError("P1_NEW_OPERATION_COURSE_REQUIRED")
    refs = request.get("references")
    if not isinstance(refs, (list, tuple)) or not refs or any(not isinstance(v, Mapping) for v in refs):
        raise ValueError("P1_NEW_OPERATION_REFERENCES_REQUIRED")
    data = {k: as_plain(context.data[k]) for k in
        ("resource_type", "level", "discipline", "institutional", "topics", "objectives", "difficulty")}
    data["references"] = as_plain(refs)
    return fingerprint(_normalized(data)), fingerprint(_normalized(data["objectives"]))


def distinct_operation(old: Mapping[str, object], new: Mapping[str, object]) -> dict[str, str]:
    previous, previous_objectives = operation_projection(old)
    current, current_objectives = operation_projection(new)
    if previous == current or previous_objectives == current_objectives:
        raise ValueError("P1_NEW_OPERATION_REPLAY_REFUSED")
    return {"old_intent_sha256": previous, "new_intent_sha256": current,
        "old_objectives_sha256": previous_objectives, "new_objectives_sha256": current_objectives}
