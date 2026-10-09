"""Closed, owner-invoked maintenance; no paths, SQL, framework or provider types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from backend.modules.local_provisioning.application.runtime_schema_snapshot import (
    RuntimeSchemaSnapshot,
)


@dataclass(frozen=True, slots=True)
class SQLSuccessorBinding:
    plan_sha256: str
    decision_sha256: str
    review_sha256: str
    full_snapshot_sha256: str
    historical_schema_pin: str
    snapshot: RuntimeSchemaSnapshot

    def validate(self) -> None:
        hashes = (
            self.plan_sha256,
            self.decision_sha256,
            self.review_sha256,
            self.full_snapshot_sha256,
            self.historical_schema_pin,
            self.snapshot.source_sha256,
            self.snapshot.schema_sha256,
        )
        if any(len(h) != 64 or any(c not in "0123456789abcdef" for c in h) for h in hashes):
            raise ValueError("SQL_SUCCESSOR_BINDING_REQUIRED")
        if self.snapshot.integrity != ("ok",) or self.snapshot.foreign_key_violations:
            raise ValueError("SQL_SUCCESSOR_SOURCE_INTEGRITY")
        if dict(self.snapshot.connection_flags).get("foreign_keys") != 1:
            raise ValueError("SQL_SUCCESSOR_FOREIGN_KEYS_REQUIRED")


@dataclass(frozen=True, slots=True)
class SQLSuccessorRequest:
    plan_sha256: str
    decision_sha256: str
    review_sha256: str


@dataclass(frozen=True, slots=True)
class SQLSuccessorResult:
    state: Literal["APPLIED", "ALREADY_APPLIED"]
    plan_sha256: str
    source_sha256: str
    final_sha256: str
    backup_sha256: str
    post_schema_sha256: str
    table_fingerprints: tuple[tuple[str, int, str], ...]
    steps: tuple[str, ...]
    stability: str


@dataclass(frozen=True, slots=True)
class CurrentVersionResolution:
    diagnostic: Literal["ABSENT", "EXACT", "AMBIGUOUS_CURRENT_VERSION"]
    candidate_count: int
    version_ref: str | None

    def validate(self) -> None:
        if (
            self.diagnostic == "ABSENT"
            and (self.candidate_count != 0 or self.version_ref is not None)
            or self.diagnostic == "EXACT"
            and (self.candidate_count != 1 or not self.version_ref)
            or self.diagnostic == "AMBIGUOUS_CURRENT_VERSION"
            and (self.candidate_count < 2 or self.version_ref is not None)
            or self.diagnostic not in ("ABSENT", "EXACT", "AMBIGUOUS_CURRENT_VERSION")
        ):
            raise ValueError("SQL_SUCCESSOR_CURRENT_DIAGNOSTIC")


class SuccessorSession(Protocol):
    def __enter__(self) -> SuccessorSession: ...
    def __exit__(self, *args: object) -> None: ...
    def existing(self) -> SQLSuccessorResult | None: ...
    def prepare(self) -> None: ...
    def backup_and_verify_restore(self) -> None: ...
    def migrate_and_check(self) -> None: ...
    def publish(self) -> SQLSuccessorResult: ...


class SQLSuccessorGateway(Protocol):
    def session(self) -> SuccessorSession: ...
    def resolve_current(self, resource_ref: str) -> CurrentVersionResolution: ...


@dataclass(frozen=True, slots=True)
class ApplySQLSuccessor:
    gateway: SQLSuccessorGateway
    binding: SQLSuccessorBinding

    def execute(self, request: SQLSuccessorRequest) -> SQLSuccessorResult:
        self.binding.validate()
        if request != SQLSuccessorRequest(
            self.binding.plan_sha256, self.binding.decision_sha256, self.binding.review_sha256
        ):
            raise ValueError("SQL_SUCCESSOR_REQUEST_MISMATCH")
        with self.gateway.session() as session:
            existing = session.existing()
            if existing is not None:
                if (
                    existing.state != "ALREADY_APPLIED"
                    or existing.plan_sha256 != request.plan_sha256
                ):
                    raise ValueError("SQL_SUCCESSOR_EXISTING_ATTESTATION")
                return existing
            session.prepare()
            session.backup_and_verify_restore()
            session.migrate_and_check()
            result = session.publish()
            if (
                result.state != "APPLIED"
                or result.plan_sha256 != request.plan_sha256
                or result.source_sha256 != self.binding.snapshot.source_sha256
                or result.backup_sha256 != self.binding.snapshot.source_sha256
            ):
                raise ValueError("SQL_SUCCESSOR_RESULT_MISMATCH")
            return result


@dataclass(frozen=True, slots=True)
class ResolveSuccessorCurrentVersion:
    gateway: SQLSuccessorGateway

    def execute(self, resource_ref: str) -> CurrentVersionResolution:
        if not isinstance(resource_ref, str) or not resource_ref or len(resource_ref) > 512:
            raise ValueError("SQL_SUCCESSOR_RESOURCE_REF")
        result = self.gateway.resolve_current(resource_ref)
        result.validate()
        return result
