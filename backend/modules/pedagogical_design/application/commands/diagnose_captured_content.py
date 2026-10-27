"""Independent canonical checks; a passing subset never admits a production."""
from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping

from backend.modules.pedagogical_context.contracts.dto.p0_context import P0Context
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import items, object_data
from backend.modules.pedagogical_design.contracts.dto.p0_production import (
    P0Production,
    _validated_corrections,
    _validated_marking,
    _validated_questions,
    _validated_references,
    _validated_sections,
)


def diagnose_captured_content(dispatch: Mapping[str, object], content: Mapping[str, object]) -> dict[str, object]:
    context = P0Context(object_data(dispatch["context"]))
    checks: list[dict[str, object]] = []
    for name, validator, value in (
        ("SECTION_SCHEMA", _validated_sections, content["sections"]),
        ("QUESTION_SCHEMA", _validated_questions, content["questions"]),
        ("CORRECTION_SCHEMA", _validated_corrections, content["corrections"]),
        ("MARKING_SCHEMA", _validated_marking, content["marking"]),
        ("REFERENCE_SCHEMA", _validated_references, dispatch["references"]),
    ):
        try:
            validator(value)
            checks.append({"check": name, "status": "PASS"})
        except ValueError as error:
            code = str(error) if re.fullmatch(r"[A-Z0-9_]+", str(error)) else "CANONICAL_CHECK_REFUSED"
            checks.append({"check": name, "status": "FAIL", "code": code})
    try:
        # This independent shape/link check does not erase the ID schema failures.
        P0Production._validate_content(context, items(content["questions"]),
            items(content["corrections"]), items(content["marking"]))
        checks.append({"check": "QUESTION_CORRECTION_LINKS_AND_FAMILY_SHAPE", "status": "PASS"})
    except ValueError as error:
        checks.append({"check": "QUESTION_CORRECTION_LINKS_AND_FAMILY_SHAPE", "status": "FAIL", "code": str(error)})
    evidence = object_data(dispatch["evidence"])
    refs = items(dispatch["references"], 8)
    checksum_match = (set(evidence) == {str(row["evidence_id"]) for row in refs}
        and all(isinstance(evidence[str(row["evidence_id"])], str)
            and hashlib.sha256(str(evidence[str(row["evidence_id"])]).encode()).hexdigest() == row["excerpt_sha256"]
            for row in refs))
    checks.append({"check": "CAPTURED_EVIDENCE_CHECKSUMS", "status": "PASS" if checksum_match else "FAIL",
        "fresh_authority": "NOT_REVALIDATED"})
    checks.append({"check": "CONTEXT_AND_CONTEXT_HASH", "status": "PASS" if context.sha256 == dispatch["context_sha256"] else "FAIL"})
    limitations = content["limitations"]
    if not isinstance(limitations, (list, tuple)):
        raise ValueError("P0_LIMITATIONS")
    return {"checks": checks, "normal_full_candidate": "REFUSED_IF_ANY_SCHEMA_FAILURE",
        "candidate_label_already_present": any("CANDIDATE" in str(value) for value in limitations),
        "pedagogical_acceptance": "NOT_PERFORMED", "promotion": "NOT_PERFORMED"}
