"""Immutable M04 assessment data; no provider, store, HTTP or filesystem authority."""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import cast

from backend.modules.pedagogical_design.contracts.dto.conversation_draft import SECTION_IDS
from backend.shared_kernel._safe_data import freeze_safe_mapping

BUNDLE_CONTRACT = "R3-ASSESSMENT-BUNDLE-1.0"
DOSSIERS = SECTION_IDS[2:]


def object_data(value: object, fields: set[str] | None = None) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(not isinstance(k, str) for k in value):
        raise ValueError("ASSESSMENT_SCHEMA")
    data = dict(cast(Mapping[str, object], value))
    if fields is not None and set(data) != fields:
        raise ValueError("ASSESSMENT_FIELDS")
    return data


def items(value: object, maximum: int = 60) -> tuple[dict[str, object], ...]:
    if not isinstance(value, (list, tuple)) or len(value) > maximum:
        raise ValueError("ASSESSMENT_ITEMS")
    return tuple(object_data(v) for v in value)


def as_plain(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(k): as_plain(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [as_plain(v) for v in value]
    return value


def encoded(value: object) -> bytes:
    return json.dumps(as_plain(value), ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def fingerprint(value: object) -> str:
    return hashlib.sha256(encoded(value)).hexdigest()


def identifier(value: object, prefix: str) -> str:
    if not isinstance(value, str) or re.fullmatch(prefix + r":[0-9a-f]{32}", value) is None:
        raise ValueError("ASSESSMENT_REFERENCE")
    return value


def nonempty(value: object, maximum: int = 4000) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError("ASSESSMENT_TEXT")
    return value


def decimal_value(value: object) -> Decimal:
    if not isinstance(value, str) or re.fullmatch(r"-?(?:0|[1-9][0-9]{0,8})\.[0-9]{2}", value) is None:
        raise ValueError("ASSESSMENT_DECIMAL")
    return Decimal(value)


def source_to_eur(value: object, scale: object, *, explicit_label: object) -> str:
    """No guessing: a bound source label is mandatory, including for factor one."""
    allowed = {"EUR": ("EUR", "euros", "€"), "kEUR": ("kEUR", "k€", "milliers d'euros")}
    if not isinstance(scale, str) or scale not in allowed or explicit_label not in allowed[scale]:
        raise ValueError("SOURCE_SCALE_REQUIRED")
    amount = decimal_value(value) * (Decimal(1000) if scale == "kEUR" else Decimal(1))
    if abs(amount) > Decimal("999999999.99"):
        raise ValueError("ASSESSMENT_DECIMAL")
    return format(amount, ".2f")


def locate(locator: object, sections: object) -> str:
    loc = object_data(locator, {"section_id", "start", "end", "exact_text"})
    texts = {s.get("section_id"): s.get("text") for s in items(sections, 5)}
    text = texts.get(loc["section_id"])
    start, end = loc["start"], loc["end"]
    if (not isinstance(text, str) or type(start) is not int or type(end) is not int
            or not 0 <= start < end <= len(text) or text[start:end] != loc["exact_text"]):
        raise ValueError("ASSESSMENT_LOCATOR")
    return nonempty(loc["exact_text"])


@dataclass(frozen=True, slots=True)
class AssessmentBundle:
    data: Mapping[str, object]

    def __post_init__(self) -> None:
        data = object_data(self.data, {
            "contract_id", "production_ref", "version_ref", "subject_sha256", "subject",
            "pedagogical_context", "context_sha256", "questions", "correction", "marking",
            "case_data", "references", "lineage", "limitations",
        })
        if data["contract_id"] != BUNDLE_CONTRACT:
            raise ValueError("ASSESSMENT_CONTRACT")
        identifier(data["production_ref"], "prod")
        identifier(data["version_ref"], "ver")
        subject = object_data(data["subject"], {"content", "sections"})
        nonempty(subject["content"], 65536)
        sections = items(subject["sections"], 5)
        if tuple(s.get("section_id") for s in sections) != SECTION_IDS:
            raise ValueError("ASSESSMENT_SECTIONS")
        for section in sections:
            object_data(section, {"section_id", "text"})
            nonempty(section["text"], 65536)
        if fingerprint(subject) != data["subject_sha256"]:
            raise ValueError("ASSESSMENT_SUBJECT_HASH")
        if len(encoded(data)) > 128 * 1024 or len(encoded(subject)) > 64 * 1024:
            raise ValueError("ASSESSMENT_SIZE")
        if not isinstance(data["limitations"], (tuple, list)) or len(data["limitations"]) > 16:
            raise ValueError("ASSESSMENT_LIMITATIONS")
        for limit in data["limitations"]:
            nonempty(limit, 500)
        object.__setattr__(self, "data", freeze_safe_mapping(data))

    @property
    def production_ref(self) -> str:
        return str(self.data["production_ref"])

    @property
    def version_ref(self) -> str:
        return str(self.data["version_ref"])

    @property
    def sha256(self) -> str:
        return fingerprint(self.data)

    def mutable_copy(self) -> dict[str, object]:
        return object_data(as_plain(self.data))
