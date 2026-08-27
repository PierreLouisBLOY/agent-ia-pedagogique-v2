from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from backend.agent_runtime.contracts.security import (
    ContentSecurityDisposition,
    SecurityEvent,
    StructuredContentSecurityAssessment,
)
from backend.shared_kernel._value_safety import (
    SensitiveValueRejected,
    StructuredDataLimitError,
)


class RuntimeSecurityDisposition(StrEnum):
    """Restriction-only result; PASS is descriptive and never grants authority."""

    PASS = "PASS"
    RESTRICT = "RESTRICT"
    DENY = "DENY"
    QUARANTINE = "QUARANTINE"
    ESCALATE = "ESCALATE"


class RuntimeSecurityReasonCode(StrEnum):
    CONTENT_ISOLATED = "SECURITY.CONTENT_ISOLATED"
    CONTENT_QUARANTINED = "SECURITY.CONTENT_QUARANTINED"
    CONTENT_REJECTED = "SECURITY.CONTENT_REJECTED"
    REVIEW_ESCALATION_REQUIRED = "SECURITY.REVIEW_ESCALATION_REQUIRED"
    STRUCTURAL_AUTHORITY_DATA = "SECURITY.STRUCTURAL_AUTHORITY_DATA"
    SENSITIVE_VALUE_REJECTED = "SECURITY.SENSITIVE_VALUE_REJECTED"
    STRUCTURAL_LIMIT_EXCEEDED = "SECURITY.STRUCTURAL_LIMIT_EXCEEDED"
    HANDOFF_REJECTED = "SECURITY.HANDOFF_REJECTED"
    POST_RESULT_REJECTED = "SECURITY.POST_RESULT_REJECTED"


class RuntimeSecurityFailureStage(StrEnum):
    PRE_EFFECT = "PRE_EFFECT"
    POST_EFFECT = "POST_EFFECT"


@dataclass(frozen=True, slots=True)
class RuntimeSecurityAssessment:
    disposition: RuntimeSecurityDisposition
    reason_codes: tuple[RuntimeSecurityReasonCode, ...] = ()

    def __post_init__(self) -> None:
        if type(self.disposition) is not RuntimeSecurityDisposition:
            raise TypeError("disposition must be a RuntimeSecurityDisposition")
        if type(self.reason_codes) is not tuple or any(
            type(item) is not RuntimeSecurityReasonCode for item in self.reason_codes
        ):
            raise TypeError("reason_codes must contain RuntimeSecurityReasonCode values")
        if len(set(self.reason_codes)) != len(self.reason_codes):
            raise ValueError("reason_codes must be unique")
        if self.disposition is RuntimeSecurityDisposition.PASS:
            if self.reason_codes:
                raise ValueError("PASS cannot contain reason codes")
        elif not self.reason_codes:
            raise ValueError("a restrictive disposition requires a reason code")

    @property
    def launchable(self) -> bool:
        return self.disposition in {
            RuntimeSecurityDisposition.PASS,
            RuntimeSecurityDisposition.RESTRICT,
        }


class RuntimeSecurityViolation(RuntimeError):
    """Raw-free runtime refusal carrying at most one immutable security event."""

    def __init__(
        self,
        assessment: RuntimeSecurityAssessment,
        *,
        stage: RuntimeSecurityFailureStage,
        event: SecurityEvent | None = None,
    ) -> None:
        if type(assessment) is not RuntimeSecurityAssessment:
            raise TypeError("assessment must be a RuntimeSecurityAssessment")
        if assessment.launchable:
            raise ValueError("a runtime security violation must not be launchable")
        if type(stage) is not RuntimeSecurityFailureStage:
            raise TypeError("stage must be a RuntimeSecurityFailureStage")
        if event is not None and type(event) is not SecurityEvent:
            raise TypeError("event must be a SecurityEvent or None")
        self.assessment = assessment
        self.stage = stage
        self.event = event
        super().__init__(assessment.reason_codes[0].value)


@dataclass(frozen=True, slots=True)
class SecurityRuntimeGuard:
    """Compose B-F findings without authorizing, launching, or persisting anything."""

    def compose(
        self,
        assessments: tuple[StructuredContentSecurityAssessment, ...],
    ) -> RuntimeSecurityAssessment:
        if type(assessments) is not tuple or any(
            type(item) is not StructuredContentSecurityAssessment
            for item in assessments
        ):
            raise TypeError(
                "assessments must contain StructuredContentSecurityAssessment values"
            )
        if any(item.structural_locations for item in assessments):
            return _assessment(
                RuntimeSecurityDisposition.DENY,
                RuntimeSecurityReasonCode.STRUCTURAL_AUTHORITY_DATA,
            )
        dispositions = {item.disposition for item in assessments}
        if ContentSecurityDisposition.REJECT_CONTENT in dispositions:
            return _assessment(
                RuntimeSecurityDisposition.DENY,
                RuntimeSecurityReasonCode.CONTENT_REJECTED,
            )
        if ContentSecurityDisposition.QUARANTINE in dispositions:
            return _assessment(
                RuntimeSecurityDisposition.QUARANTINE,
                RuntimeSecurityReasonCode.CONTENT_QUARANTINED,
            )
        if ContentSecurityDisposition.ESCALATE_REVIEW in dispositions:
            return _assessment(
                RuntimeSecurityDisposition.ESCALATE,
                RuntimeSecurityReasonCode.REVIEW_ESCALATION_REQUIRED,
            )
        if ContentSecurityDisposition.ISOLATE_AS_DATA in dispositions:
            return _assessment(
                RuntimeSecurityDisposition.RESTRICT,
                RuntimeSecurityReasonCode.CONTENT_ISOLATED,
            )
        return RuntimeSecurityAssessment(RuntimeSecurityDisposition.PASS)

    def from_error(
        self,
        error: SensitiveValueRejected | StructuredDataLimitError,
    ) -> RuntimeSecurityAssessment:
        if type(error) is SensitiveValueRejected:
            return _assessment(
                RuntimeSecurityDisposition.DENY,
                RuntimeSecurityReasonCode.SENSITIVE_VALUE_REJECTED,
            )
        if type(error) is StructuredDataLimitError:
            return _assessment(
                RuntimeSecurityDisposition.DENY,
                RuntimeSecurityReasonCode.STRUCTURAL_LIMIT_EXCEEDED,
            )
        raise TypeError("error must be a sensitive-value or structured-limit refusal")

    def handoff_rejected(self) -> RuntimeSecurityAssessment:
        return _assessment(
            RuntimeSecurityDisposition.DENY,
            RuntimeSecurityReasonCode.HANDOFF_REJECTED,
        )

    def post_result_rejected(self) -> RuntimeSecurityAssessment:
        return _assessment(
            RuntimeSecurityDisposition.DENY,
            RuntimeSecurityReasonCode.POST_RESULT_REJECTED,
        )


def _assessment(
    disposition: RuntimeSecurityDisposition,
    reason_code: RuntimeSecurityReasonCode,
) -> RuntimeSecurityAssessment:
    return RuntimeSecurityAssessment(disposition, (reason_code,))
