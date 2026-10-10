"""Explicit closed maintenance, separate from migration and normal runtime."""

from dataclasses import dataclass
from typing import Literal, Protocol

from backend.modules.local_provisioning.application.sql_successor import SQLSuccessorBinding


def _hash(value: str) -> None:
    if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError("SQL_ROLLBACK_EXACT_HASH_REQUIRED")


@dataclass(frozen=True, slots=True)
class RollbackFileIdentity:
    device: int
    inode: int
    size: int
    sha256: str

    def validate(self) -> None:
        _hash(self.sha256)
        if self.device < 0 or self.inode <= 0 or self.size <= 0:
            raise ValueError("SQL_ROLLBACK_PHYSICAL_IDENTITY_REQUIRED")


@dataclass(frozen=True, slots=True)
class SQLRollbackBinding:
    successor: SQLSuccessorBinding
    plan_sha256: str
    decision_sha256: str
    review_sha256: str
    operation_sha256: str
    applied_receipt_sha256: str
    retained_initial_name: str
    published: RollbackFileIdentity
    backup: RollbackFileIdentity

    def validate(self) -> None:
        self.successor.validate()
        for value in (
            self.plan_sha256,
            self.decision_sha256,
            self.review_sha256,
            self.operation_sha256,
            self.applied_receipt_sha256,
        ):
            _hash(value)
        self.published.validate()
        self.backup.validate()
        name = self.retained_initial_name
        if (
            not name.startswith("initial-")
            or not name.endswith(".sqlite")
            or any(
                c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_."
                for c in name
            )
            or ".." in name
        ):
            raise ValueError("SQL_ROLLBACK_CLOSED_EVIDENCE_NAME_REQUIRED")
        original = self.successor.snapshot
        identities = {
            (original.source_device, original.source_inode),
            (self.backup.device, self.backup.inode),
            (self.published.device, self.published.inode),
        }
        if len(identities) != 3 or self.backup.sha256 != original.source_sha256:
            raise ValueError("SQL_ROLLBACK_DISTINCT_AUTHENTICATED_FILES_REQUIRED")


@dataclass(frozen=True, slots=True)
class SQLRollbackRequest:
    plan_sha256: str
    decision_sha256: str
    review_sha256: str
    operation_sha256: str


@dataclass(frozen=True, slots=True)
class SQLRollbackResult:
    state: Literal["PREPARED", "ROLLED_BACK", "ALREADY_ROLLED_BACK"]
    operation_sha256: str
    intention_sha256: str
    restored: RollbackFileIdentity
    source_sha256: str
    applied_receipt_sha256: str
    stability: str


class SQLRollbackGateway(Protocol):
    def prepare(self) -> SQLRollbackResult: ...
    def execute(self, intention_sha256: str) -> SQLRollbackResult: ...


@dataclass(frozen=True, slots=True)
class RollbackSQLSuccessor:
    gateway: SQLRollbackGateway
    binding: SQLRollbackBinding

    def _request(self, request: SQLRollbackRequest) -> None:
        self.binding.validate()
        if request != SQLRollbackRequest(
            self.binding.plan_sha256,
            self.binding.decision_sha256,
            self.binding.review_sha256,
            self.binding.operation_sha256,
        ):
            raise ValueError("SQL_ROLLBACK_REQUEST_MISMATCH")

    def _result(self, result: SQLRollbackResult, states: tuple[str, ...]) -> SQLRollbackResult:
        result.restored.validate()
        _hash(result.intention_sha256)
        if (
            result.state not in states
            or result.operation_sha256 != self.binding.operation_sha256
            or result.source_sha256 != self.binding.successor.snapshot.source_sha256
            or result.restored.sha256 != result.source_sha256
            or result.applied_receipt_sha256 != self.binding.applied_receipt_sha256
            or not result.stability
        ):
            raise ValueError("SQL_ROLLBACK_RESULT_MISMATCH")
        return result

    def prepare(self, request: SQLRollbackRequest) -> SQLRollbackResult:
        self._request(request)
        return self._result(self.gateway.prepare(), ("PREPARED",))

    def execute(self, request: SQLRollbackRequest, intention_sha256: str) -> SQLRollbackResult:
        self._request(request)
        _hash(intention_sha256)
        result = self._result(
            self.gateway.execute(intention_sha256), ("ROLLED_BACK", "ALREADY_ROLLED_BACK")
        )
        if result.intention_sha256 != intention_sha256:
            raise ValueError("SQL_ROLLBACK_INTENTION_MISMATCH")
        return result
