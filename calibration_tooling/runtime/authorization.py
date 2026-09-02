from __future__ import annotations

from dataclasses import dataclass

from calibration_tooling.contracts.errors import CalibrationErrorCode, fail_execution
from calibration_tooling.contracts.models import (
    CALIBRATION_SCHEMA_V1,
    AuthorizationRef,
    CalibrationPlan,
    CalibrationSchemaVersion,
    CallRef,
    Sha256Digest,
)


@dataclass(frozen=True, slots=True)
class ExecutionAuthorization:
    schema_version: CalibrationSchemaVersion
    authorization_ref: AuthorizationRef
    matrix_sha256: Sha256Digest
    allowlisted_call_refs: tuple[CallRef, ...]
    maximum_call_count: int

    def __post_init__(self) -> None:
        if self.schema_version is not CALIBRATION_SCHEMA_V1:
            raise ValueError("authorization schema version is not supported")
        if type(self.authorization_ref) is not AuthorizationRef:
            raise TypeError("authorization_ref must be an AuthorizationRef")
        if type(self.matrix_sha256) is not Sha256Digest:
            raise TypeError("matrix_sha256 must be a Sha256Digest")
        if type(self.allowlisted_call_refs) is not tuple:
            raise TypeError("allowlisted_call_refs must be a tuple")
        if not self.allowlisted_call_refs or any(
            type(item) is not CallRef for item in self.allowlisted_call_refs
        ):
            raise ValueError("authorization requires a typed non-empty allowlist")
        if len(set(self.allowlisted_call_refs)) != len(self.allowlisted_call_refs):
            raise ValueError("authorization allowlist must be unique")
        if type(self.maximum_call_count) is not int or self.maximum_call_count <= 0:
            raise ValueError("maximum_call_count must be a positive integer")
        if self.maximum_call_count != len(self.allowlisted_call_refs):
            raise ValueError("maximum_call_count must equal the exact allowlist")


class OneShotAuthorizationGuard:
    def __init__(self) -> None:
        self._consumed: set[AuthorizationRef] = set()

    def consume(
        self,
        plan: CalibrationPlan,
        authorization: ExecutionAuthorization,
    ) -> None:
        if type(authorization) is not ExecutionAuthorization:
            fail_execution(CalibrationErrorCode.AUTHORIZATION_REQUIRED)
        if authorization.authorization_ref in self._consumed:
            fail_execution(CalibrationErrorCode.AUTHORIZATION_CONSUMED)
        call_refs = tuple(item.call_ref for item in plan.observations)
        if (
            authorization.schema_version is not plan.schema_version
            or authorization.matrix_sha256 != plan.matrix_sha256
        ):
            fail_execution(CalibrationErrorCode.IDENTITY_MISMATCH)
        if (
            authorization.allowlisted_call_refs != call_refs
            or authorization.maximum_call_count != len(call_refs)
        ):
            fail_execution(CalibrationErrorCode.ALLOWLIST_MISMATCH)
        self._consumed.add(authorization.authorization_ref)

    def is_consumed(self, authorization_ref: AuthorizationRef) -> bool:
        if type(authorization_ref) is not AuthorizationRef:
            raise TypeError("authorization_ref must be an AuthorizationRef")
        return authorization_ref in self._consumed
