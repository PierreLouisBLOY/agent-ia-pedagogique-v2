from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class OwnerApprovals:
    create_data_root: bool
    locate_and_hash_seed: bool
    copy_seed: bool
    create_runtime: bool
    apply_migrations: bool
    create_library: bool
    update_user_config: bool
    evidence_sha256: str

    @property
    def all_approved(self) -> bool:
        return (
            all(
                (
                    self.create_data_root,
                    self.locate_and_hash_seed,
                    self.copy_seed,
                    self.create_runtime,
                    self.apply_migrations,
                    self.create_library,
                    self.update_user_config,
                )
            )
            and self.evidence_sha256
            == "0abe109eab2f0f1c49c4ac484ffd596d63b5964c34a66e19a789f880145d2287"
        )


@dataclass(frozen=True, slots=True)
class SeedExpectation:
    sha256: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class SeedCandidate:
    path: Path
    sha256: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class SeedInspection:
    candidate: SeedCandidate
    authenticated: bool
    integrity: str
    quick_check: str
    foreign_key_violations: int
    tables: int
    explicit_indexes: int
    triggers: int
    views: int


@dataclass(frozen=True, slots=True)
class SuppliedSeedFileInspectionRequest:
    project_identity: str
    allowed_root: Path
    candidate_path: Path
    expected_seed: SeedExpectation
    read_only: bool = True


@dataclass(frozen=True, slots=True)
class SuppliedSeedFileInspectionResult:
    candidate: SeedCandidate | None
    matches_expected: bool
    findings: tuple[str, ...]
    database_opened: bool = False


@dataclass(frozen=True, slots=True)
class ProvisioningInspectionRequest:
    project_identity: str
    allowed_roots: tuple[Path, ...]
    seed_expectations: tuple[SeedExpectation, ...]
    old_data_root: Path
    current_config: tuple[tuple[str, str | None], ...]
    read_only: bool = True


@dataclass(frozen=True, slots=True)
class ProvisioningInspectionResult:
    seed_candidates: tuple[SeedInspection, ...]
    current_config: tuple[tuple[str, str | None], ...]
    current_runtime_claim: str
    migration_state_claim: str
    library_root_claim: str
    findings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProvisioningTargetInspectionRequest:
    project_identity: str
    data_root: Path
    old_data_root: Path
    read_only: bool = True


@dataclass(frozen=True, slots=True)
class ProvisioningTargetInspectionResult:
    data_root_exists: bool
    root_marker_valid: bool
    observed_relative_paths: tuple[str, ...]
    unexpected_relative_paths: tuple[str, ...]
    findings: tuple[str, ...]
    recoverable_temporary_paths: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MigrationExpectation:
    version: str
    sha256: str
    source_path: Path


@dataclass(frozen=True, slots=True)
class ProvisioningPlan:
    project_identity: str
    seed: SeedInspection
    data_root: Path
    reference_seed: Path
    runtime: Path
    backup: Path
    library_root: Path
    migrations: tuple[MigrationExpectation, ...]
    allowed_seed_roots: tuple[Path, ...]
    old_data_root: Path
    config_target: str
    config_values: tuple[tuple[str, str], ...]
    idempotency_key: str
    approvals: OwnerApprovals


@dataclass(frozen=True, slots=True)
class RuntimeMigrationState:
    exists: bool
    identity_sha256: str | None
    seed_sha256: str | None
    applied_migrations: tuple[tuple[str, str], ...]
    integrity: str | None
    quick_check: str | None
    foreign_key_violations: int | None


@dataclass(frozen=True, slots=True)
class ProvisioningApplyResult:
    data_root: Path
    seed_sha256: str
    reference_seed_sha256: str
    runtime_sha256: str
    migrations_applied: tuple[str, ...]
    migrations_skipped: tuple[str, ...]
    backup_sha256: str
    library_root_ready: bool
    config_before: tuple[tuple[str, str | None], ...]
    config_after: tuple[tuple[str, str | None], ...]
    startup_ready: bool
    rollback_config_available: bool
    idempotent_replay: bool
    old_root_unchanged: bool
