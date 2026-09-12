"""Closed neutral commands and job envelopes. No agent/HTTP/provider types."""
import re
from collections.abc import Mapping
from dataclasses import dataclass

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    AssessmentBundle,
    fingerprint,
    identifier,
    object_data,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_revision import (
    HARDEN,
    INSTRUCTION,
    AssessmentRevisionRequest,
    EditorialCorrectionPlan,
)
from backend.shared_kernel._safe_data import freeze_safe_mapping

DIMENSIONS = ("REV-ACC", "REV-COV", "REV-PED", "REV-INS", "REV-STR",
              "REV-SRC", "REV-CON", "REV-FMT", "REV-RSK")
OPERATIONS = ("assessment-preparations", "reviews", "validations", "modifications")


class R3Rejected(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class R3Command:
    operation: str
    body: Mapping[str, object]

    def __post_init__(self) -> None:
        fields = {"conversation_id", "command_id", "expected_revision", "production_ref"}
        extra = {"assessment-preparations": {"version_ref", "subject_sha256"},
                 "reviews": {"version_ref", "bundle_sha256", "dimensions"},
                 "validations": {"version_ref", "bundle_sha256"},
                 "modifications": {"base_version_ref", "base_bundle_sha256", "operation", "instruction"}}
        if self.operation not in extra:
            raise R3Rejected("VALIDATION_REJECTED")
        editorial = (self.operation == "modifications"
                     and self.body.get("operation") == EditorialCorrectionPlan.OPERATION)
        if editorial:
            extra["modifications"] = {"base_version_ref", "base_bundle_sha256", "operation",
                                      "editorial_contract", "plan_sha256", "review_sha256"}
        body = object_data(self.body, fields | extra[self.operation])
        if editorial and body["editorial_contract"] != EditorialCorrectionPlan.CONTRACT:
            raise R3Rejected("VALIDATION_REJECTED")
        identifier(body["conversation_id"], "conv")
        identifier(body["production_ref"], "prod")
        identifier(body.get("base_version_ref", body.get("version_ref")), "ver")
        command_id = body["command_id"]
        if not isinstance(command_id, str) or not re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", command_id):
            raise R3Rejected("VALIDATION_REJECTED")
        if type(body["expected_revision"]) is not int or body["expected_revision"] < 1:
            raise R3Rejected("VALIDATION_REJECTED")
        for field in ("subject_sha256", "bundle_sha256", "base_bundle_sha256", "plan_sha256", "review_sha256"):
            if field in body and not (field == "bundle_sha256" and self.operation == "validations" and body[field] is None):
                hash_value = body[field]
                if not isinstance(hash_value, str) or re.fullmatch(r"[0-9a-f]{64}", hash_value) is None:
                    raise R3Rejected("VALIDATION_REJECTED")
        if self.operation == "reviews":
            ds = body["dimensions"]
            if not isinstance(ds, (list, tuple)) or not ds or any(not isinstance(d, str) for d in ds) or len(ds) != len(set(ds)) or any(d not in DIMENSIONS for d in ds):
                raise R3Rejected("VALIDATION_REJECTED")
        if self.operation == "modifications" and not editorial and (body["operation"] != HARDEN or body["instruction"] != INSTRUCTION):
            raise R3Rejected("CONTEXT_CLARIFICATION_REQUIRED")
        object.__setattr__(self, "body", freeze_safe_mapping(body))

    @property
    def command_id(self) -> str:
        return str(self.body["command_id"])

    @property
    def fingerprint(self) -> str:
        return fingerprint({"operation": self.operation, "body": self.body})

    @property
    def version_ref(self) -> str:
        return str(self.body.get("base_version_ref", self.body.get("version_ref")))


@dataclass(frozen=True, slots=True)
class R3JobRequest:
    operation_ref: str
    operation: str
    revision: AssessmentRevisionRequest | None = None
    bundle: AssessmentBundle | None = None
    dimensions: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class R3JobResult:
    operation_ref: str
    state: str
    payload: Mapping[str, object] | None = None

    def __post_init__(self) -> None:
        if self.state not in {"SUCCEEDED", "FAILED_NO_EFFECT", "FAILED_OUTPUT", "UNKNOWN"}:
            raise ValueError("R3_JOB_STATE")
        if (self.state == "SUCCEEDED") != (self.payload is not None):
            raise ValueError("R3_JOB_PAYLOAD")
        if self.payload is not None:
            object.__setattr__(self, "payload", freeze_safe_mapping(self.payload))
