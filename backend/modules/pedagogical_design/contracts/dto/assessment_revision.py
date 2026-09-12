"""Closed M04 transformation requests; all identities belong to Application."""
import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import ClassVar

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    AssessmentBundle,
    identifier,
    items,
    object_data,
)
from backend.shared_kernel._safe_data import freeze_safe_mapping

PREPARE = "PREPARE_SUPPLEMENTS"
HARDEN = "HARDEN_DOSSIER_3"
INSTRUCTION = "Rends le dossier 3 plus difficile."


@dataclass(frozen=True, slots=True)
class AssessmentRevisionRequest:
    operation: str
    production_ref: str
    base_version_ref: str
    subject: Mapping[str, object]
    context: Mapping[str, object]
    references: tuple[Mapping[str, object], ...]
    base: AssessmentBundle | None = None

    def __post_init__(self) -> None:
        identifier(self.production_ref, "prod")
        identifier(self.base_version_ref, "ver")
        if self.operation not in {PREPARE, HARDEN} or (self.operation == HARDEN) != (self.base is not None):
            raise ValueError("ASSESSMENT_OPERATION")
        if self.base is not None and (self.base.production_ref, self.base.version_ref) != (
                self.production_ref, self.base_version_ref):
            raise ValueError("ASSESSMENT_REFERENCE")
        object.__setattr__(self, "subject", freeze_safe_mapping(self.subject))
        object.__setattr__(self, "context", freeze_safe_mapping(self.context))
        object.__setattr__(self, "references", tuple(freeze_safe_mapping(r) for r in self.references))


@dataclass(frozen=True, slots=True)
class EditorialCorrectionPlan:
    """Exact private bytes, not an authorization or a provider request."""

    OPERATION: ClassVar[str] = "APPLY_REVIEW_EDITORIAL_F01_F02"
    CONTRACT: ClassVar[str] = "R3-EDITORIAL-CORRECTION-1.0"
    LOCATOR_SHA: ClassVar[str] = "b30b1311ffccff4451abfd3e222fa27902077f1ac2795f6995b018f31edf2942"
    PATHS: ClassVar[tuple[str, ...]] = (
        "correction.answers[0].expected_answer",
        "correction.answers[0].calculations[0].locator",
        "correction.answers[1].expected_answer",
        "correction.answers[1].calculations[0].locator",
    )
    raw: bytes
    data: Mapping[str, object] = field(init=False)

    @staticmethod
    def decode(raw: bytes) -> dict[str, object]:
        if type(raw) is not bytes or not raw or len(raw) > 65536 or raw.startswith(b"\xef\xbb\xbf"):
            raise ValueError("ASSESSMENT_SCHEMA")

        def pairs(values: list[tuple[str, object]]) -> dict[str, object]:
            result: dict[str, object] = {}
            for key, value in values:
                if key in result:
                    raise ValueError("ASSESSMENT_FIELDS")
                result[key] = value
            return result

        def reject_constant(value: str) -> object:
            raise ValueError("ASSESSMENT_SCHEMA")

        return object_data(json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                                      parse_constant=reject_constant))

    def __post_init__(self) -> None:
        d = object_data(self.decode(self.raw), {
            "contract", "operation", "prepared_from_baseline_commit",
            "implementation_baseline_commit", "contract_document_sha256", "production_ref",
            "parent_version_ref", "parent_bundle_sha256", "parent_subject_sha256",
            "review_sha256", "proposal_source_sha256", "edits", "changed_content_paths",
            "source_capability", "origin_kind", "locator_algorithm", "locator_source_sha256",
            "max_child_publications", "provider_calls", "dependency_changes",
        })
        for key in ("prepared_from_baseline_commit", "implementation_baseline_commit"):
            if type(d[key]) is not str or re.fullmatch(r"[0-9a-f]{40}", str(d[key])) is None:
                raise ValueError("ASSESSMENT_REFERENCE")
        for key in ("contract_document_sha256", "parent_bundle_sha256", "parent_subject_sha256",
                    "review_sha256", "proposal_source_sha256", "locator_source_sha256"):
            if type(d[key]) is not str or re.fullmatch(r"[0-9a-f]{64}", str(d[key])) is None:
                raise ValueError("ASSESSMENT_REFERENCE")
        identifier(d["production_ref"], "prod")
        identifier(d["parent_version_ref"], "ver")
        if (d["operation"] != self.OPERATION or d["contract"] != self.CONTRACT
                or d["source_capability"] is not None
                or d["origin_kind"] != "LOCAL_DETERMINISTIC_M04"
                or d["locator_algorithm"] != "calculation_locators"
                or d["locator_source_sha256"] != self.LOCATOR_SHA
                or type(d["max_child_publications"]) is not int or d["max_child_publications"] != 1
                or type(d["provider_calls"]) is not int or d["provider_calls"] != 0
                or d["dependency_changes"] != []
                or d["changed_content_paths"] != list(self.PATHS)):
            raise ValueError("ASSESSMENT_SCHEMA")
        edits = items(d["edits"], 2)
        if len(edits) != 2:
            raise ValueError("ASSESSMENT_FIELDS")
        for i, supplied in enumerate(edits):
            e = object_data(supplied, {"finding_id", "question_id", "answer_index",
                "expected_answer_path", "calculation_locator_path", "original_expected_answer",
                "original_text_sha256", "proposed_expected_answer", "proposed_text_sha256"})
            if (e["finding_id"] != f"F-0{i+1}" or type(e["answer_index"]) is not int
                    or e["answer_index"] != i or e["expected_answer_path"] != self.PATHS[2*i]
                    or e["calculation_locator_path"] != self.PATHS[2*i+1]
                    or type(e["question_id"]) is not str or not e["question_id"]):
                raise ValueError("ASSESSMENT_REFERENCE")
            for prefix in ("original", "proposed"):
                text, digest = e[prefix + "_expected_answer"], e[prefix + "_text_sha256"]
                if (type(text) is not str or not text or len(text) > 65536
                        or hashlib.sha256(text.encode("utf-8")).hexdigest() != digest):
                    raise ValueError("ASSESSMENT_REFERENCE")
            old, new = str(e["original_expected_answer"]), str(e["proposed_expected_answer"])
            if new == old or not new.endswith(old):
                raise ValueError("ASSESSMENT_SCHEMA")
        if edits[0]["question_id"] == edits[1]["question_id"]:
            raise ValueError("ASSESSMENT_REFERENCE")
        object.__setattr__(self, "data", freeze_safe_mapping(d))

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.raw).hexdigest()

    def validate_parent(self, parent: AssessmentBundle) -> None:
        d = self.data
        if (parent.production_ref, parent.version_ref, parent.sha256,
                parent.data["subject_sha256"]) != (
                d["production_ref"], d["parent_version_ref"], d["parent_bundle_sha256"],
                d["parent_subject_sha256"]):
            raise ValueError("ASSESSMENT_REFERENCE")
        answers = items(object_data(parent.data["correction"])["answers"])
        questions = items(parent.data["questions"])
        for i, e in enumerate(items(d["edits"], 2)):
            if i >= len(answers):
                raise ValueError("ASSESSMENT_REFERENCE")
            a = answers[i]
            matched = [q for q in questions if q["question_id"] == e["question_id"]]
            if (a["question_id"] != e["question_id"]
                    or a["expected_answer"] != e["original_expected_answer"]
                    or len(matched) != 1 or matched[0]["dossier_id"] != f"DOSSIER_{i+1}"
                    or len(items(a["calculations"])) != 1):
                raise ValueError("ASSESSMENT_REFERENCE")
