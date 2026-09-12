"""Private neutral M09 proof. No candidate can supply its own authority."""
from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    AssessmentBundle,
    encoded,
    fingerprint,
    identifier,
    items,
    locate,
    object_data,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_revision import (
    EditorialCorrectionPlan,
)
from backend.shared_kernel._safe_data import freeze_safe_mapping


@dataclass(frozen=True, slots=True)
class EditorialAuthorizationEvidence:
    """Independent receipt; possession of these fields alone grants nothing."""

    plan: EditorialCorrectionPlan
    conversation_id: str
    baseline_commit: str
    contract_sha256: str
    owner_decision_sha256: str
    review_raw: bytes
    receipt: object = field(repr=False, compare=False)
    review: Mapping[str, object] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        identifier(self.conversation_id, "conv")
        if (type(self.plan) is not EditorialCorrectionPlan
                or self.baseline_commit != self.plan.data["implementation_baseline_commit"]
                or self.contract_sha256 != self.plan.data["contract_document_sha256"]
                or type(self.owner_decision_sha256) is not str
                or re.fullmatch(r"[0-9a-f]{64}", self.owner_decision_sha256) is None
                or type(self.review_raw) is not bytes
                or hashlib.sha256(self.review_raw).hexdigest() != self.plan.data["review_sha256"]):
            raise ValueError("ASSESSMENT_REFERENCE")
        review = EditorialCorrectionPlan.decode(self.review_raw)
        if (review.get("status") != "completed"
                or (review.get("production_ref"), review.get("version_ref"),
                    review.get("bundle_sha256"), review.get("subject_sha256")) != (
                    self.plan.data["production_ref"], self.plan.data["parent_version_ref"],
                    self.plan.data["parent_bundle_sha256"], self.plan.data["parent_subject_sha256"])):
            raise ValueError("ASSESSMENT_REFERENCE")
        findings = items(review.get("findings"), 32)
        for e in items(self.plan.data["edits"], 2):
            if sum(f.get("finding_id") == e["finding_id"] for f in findings) != 1:
                raise ValueError("ASSESSMENT_REFERENCE")
        object.__setattr__(self, "review", freeze_safe_mapping(review))


@dataclass(frozen=True, slots=True)
class EditorialValidationScope:
    evidence: EditorialAuthorizationEvidence
    parent: AssessmentBundle
    child: AssessmentBundle
    command_id: str
    operation_ref: str
    locators: tuple[Mapping[str, object], ...]
    origin_kind: str = "LOCAL_DETERMINISTIC_M04"
    # Not a field a constructor, JSON parser or dataclasses.replace can authenticate.
    _seal: Callable[[], bool] | None = field(default=None, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if type(self.evidence) is not EditorialAuthorizationEvidence:
            raise ValueError("ASSESSMENT_REFERENCE")
        identifier(self.operation_ref, "op")
        if type(self.command_id) is not str or re.fullmatch(
                r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", self.command_id) is None:
            raise ValueError("ASSESSMENT_REFERENCE")
        object.__setattr__(self, "locators", tuple(freeze_safe_mapping(x) for x in self.locators))


def build_editorial_scope(
    evidence: EditorialAuthorizationEvidence, parent: AssessmentBundle, child: AssessmentBundle, *,
    command_id: str, operation_ref: str,
    authenticate: Callable[[EditorialAuthorizationEvidence], bool],
    calculate_locators: Callable[[str, str, tuple[str, ...]], tuple[dict[str, object], ...]],
) -> EditorialValidationScope:
    """Trusted Application injection only; not reachable from a document or HTTP."""
    if authenticate(evidence) is not True:
        raise ValueError("R3_NOT_AUTHORIZED")
    evidence.plan.validate_parent(parent)
    answers = items(object_data(parent.data["correction"])["answers"])
    locators = []
    for i, edit in enumerate(items(evidence.plan.data["edits"], 2)):
        locs = calculate_locators(str(edit["question_id"]), str(edit["proposed_expected_answer"]),
                                  tuple(str(c["value"]) for c in items(answers[i]["calculations"])))
        if len(locs) != 1:
            raise ValueError("ASSESSMENT_LOCATOR")
        locators.append(locs[0])
    scope = EditorialValidationScope(evidence, parent, child, command_id, operation_ref,
                                     tuple(locators))
    object.__setattr__(scope, "_seal", lambda: authenticate(evidence) is True)
    if not verify_editorial_scope(scope, parent=parent, candidate=child.data):
        raise ValueError("ASSESSMENT_VALIDATION_FAILED")
    return scope


def verify_editorial_scope(
    scope: EditorialValidationScope | None, *, parent: AssessmentBundle | None,
    candidate: Mapping[str, object],
) -> bool:
    """Fail closed; full tree comparison rather than a permissive path allowlist."""
    try:
        if (type(scope) is not EditorialValidationScope or scope._seal is None
                or scope._seal() is not True or parent is None
                or scope.origin_kind != "LOCAL_DETERMINISTIC_M04"
                or scope.parent.sha256 != parent.sha256
                or scope.child.sha256 != fingerprint(candidate)
                or scope.child.version_ref == parent.version_ref or len(scope.locators) != 2):
            return False
        plan = scope.evidence.plan
        plan.validate_parent(parent)
        before = parent.mutable_copy()
        correction = object_data(before["correction"])
        answers = items(correction["answers"])
        for i, edit in enumerate(items(plan.data["edits"], 2)):
            locator = object_data(scope.locators[i], {"section_id", "start", "end", "exact_text"})
            old_calcs = items(answers[i]["calculations"])
            old_loc = object_data(old_calcs[0]["locator"])
            if (locator["section_id"] != old_loc["section_id"]
                    or locator["exact_text"] != old_loc["exact_text"]
                    or locate(locator, [{"section_id": edit["question_id"],
                                         "text": edit["proposed_expected_answer"]}]) != old_calcs[0]["value"]):
                return False
            old_calcs[0]["locator"] = locator
            answers[i].update(expected_answer=edit["proposed_expected_answer"],
                              calculations=list(old_calcs))
        correction["answers"] = list(answers)
        before["correction"] = correction
        before["version_ref"] = scope.child.version_ref
        for key in ("correction", "marking"):
            part = object_data(before[key])
            part["version_ref"] = scope.child.version_ref
            before[key] = part
        before["lineage"] = {
            "operation_ref": scope.operation_ref, "command_id": scope.command_id,
            "source_capability": None, "parent_version_ref": parent.version_ref,
            "parent_bundle_sha256": parent.sha256, "instruction_sha256": plan.sha256,
            "changed_locators": list(plan.PATHS), "dependency_changes": [],
        }
        return encoded(before) == encoded(candidate)
    except (ValueError, TypeError, KeyError, AttributeError, IndexError):
        return False
