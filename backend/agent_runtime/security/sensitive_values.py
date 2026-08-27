from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from backend.agent_runtime.contracts.common import ContractRef, ContractSchemaVersion
from backend.agent_runtime.contracts.security import (
    SecurityBoundary,
    SecurityEvent,
    SecurityEventType,
    SecurityReasonCode,
    SecuritySeverity,
)
from backend.shared_kernel._value_safety import (
    DEFAULT_STRUCTURED_DATA_LIMITS,
    SensitiveValueClass,
    SensitiveValueLocation,
    SensitiveValueRejected,
    StructuredDataLimitCode,
    StructuredDataLimitError,
    StructuredDataLimits,
    inspect_structured_value,
)
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant

__all__ = [
    "SensitiveValueAssessment",
    "SensitiveValueClass",
    "SensitiveValuePolicy",
    "SensitiveValueRejected",
    "StructuredDataLimitCode",
    "StructuredDataLimitError",
    "StructuredDataLimits",
    "security_event_from_sensitive_value_rejection",
    "security_event_from_structured_limit_error",
]


@dataclass(frozen=True, slots=True)
class SensitiveValueAssessment:
    """Raw-free findings for one bounded structured value."""

    findings: tuple[SensitiveValueLocation, ...]

    def __post_init__(self) -> None:
        if type(self.findings) is not tuple or any(
            type(item) is not SensitiveValueLocation for item in self.findings
        ):
            raise TypeError("findings must contain SensitiveValueLocation values")
        if len(self.findings) != len(set(self.findings)):
            raise ValueError("findings must be unique")

    @property
    def safe(self) -> bool:
        return not self.findings


@dataclass(frozen=True, slots=True)
class SensitiveValuePolicy:
    """Pure local classifier; it stores no raw value and grants no authority."""

    limits: StructuredDataLimits = DEFAULT_STRUCTURED_DATA_LIMITS

    def __post_init__(self) -> None:
        if type(self.limits) is not StructuredDataLimits:
            raise TypeError("limits must be StructuredDataLimits")

    def assess(
        self,
        value: object,
        *,
        root_location: str,
    ) -> SensitiveValueAssessment:
        return SensitiveValueAssessment(
            inspect_structured_value(
                value,
                limits=self.limits,
                root_location=root_location,
            )
        )

    def require_safe(self, value: object, *, root_location: str) -> None:
        assessment = self.assess(value, root_location=root_location)
        if assessment.findings:
            raise SensitiveValueRejected(assessment.findings[0])


_SENSITIVE_REASON: Final = {
    SensitiveValueClass.CREDENTIAL_LIKE: SecurityReasonCode(
        "SECRET.CREDENTIAL_LIKE"
    ),
    SensitiveValueClass.AUTH_TOKEN_LIKE: SecurityReasonCode("SECRET.AUTH_TOKEN_LIKE"),
    SensitiveValueClass.PRIVATE_KEY_LIKE: SecurityReasonCode(
        "SECRET.PRIVATE_KEY_LIKE"
    ),
    SensitiveValueClass.CONNECTION_SECRET_LIKE: SecurityReasonCode(
        "SECRET.CONNECTION_SECRET_LIKE"
    ),
    SensitiveValueClass.PRIVATE_PATH_LIKE: SecurityReasonCode(
        "SECRET.PRIVATE_PATH_LIKE"
    ),
}


def security_event_from_sensitive_value_rejection(
    error: SensitiveValueRejected,
    *,
    schema_version: ContractSchemaVersion,
    event_id: str,
    occurred_at: Instant,
    run_id: str,
    correlation_id: CorrelationId,
    boundary: SecurityBoundary,
    step_id: str | None = None,
    refs: tuple[ContractRef, ...] = (),
    exfiltration_requested: bool = False,
) -> SecurityEvent:
    if type(error) is not SensitiveValueRejected:
        raise TypeError("error must be a SensitiveValueRejected")
    if type(exfiltration_requested) is not bool:
        raise TypeError("exfiltration_requested must be a bool")
    finding = error.finding
    return SecurityEvent(
        schema_version=schema_version,
        event_id=event_id,
        event_type=(
            SecurityEventType.SECRET_EXFILTRATION_ATTEMPT
            if exfiltration_requested
            else SecurityEventType.SECRET_EXPOSURE
        ),
        severity=SecuritySeverity.CRITICAL,
        boundary=boundary,
        reason_code=_SENSITIVE_REASON[finding.classification],
        occurred_at=occurred_at,
        run_id=run_id,
        correlation_id=correlation_id,
        step_id=step_id,
        refs=refs,
        metadata={
            "classification": finding.classification.value,
            "logical_location": finding.logical_location,
        },
    )


def security_event_from_structured_limit_error(
    error: StructuredDataLimitError,
    *,
    schema_version: ContractSchemaVersion,
    event_id: str,
    occurred_at: Instant,
    run_id: str,
    correlation_id: CorrelationId,
    boundary: SecurityBoundary,
    step_id: str | None = None,
    refs: tuple[ContractRef, ...] = (),
) -> SecurityEvent:
    if type(error) is not StructuredDataLimitError:
        raise TypeError("error must be a StructuredDataLimitError")
    return SecurityEvent(
        schema_version=schema_version,
        event_id=event_id,
        event_type=SecurityEventType.INPUT_LIMIT_EXCEEDED,
        severity=SecuritySeverity.HIGH,
        boundary=boundary,
        reason_code=SecurityReasonCode(f"LIMIT.{error.code.value}"),
        occurred_at=occurred_at,
        run_id=run_id,
        correlation_id=correlation_id,
        step_id=step_id,
        refs=refs,
        metadata={
            "limit_code": error.code.value,
            "logical_location": error.logical_location,
        },
    )
