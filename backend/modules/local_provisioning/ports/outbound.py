from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from backend.modules.local_provisioning.application.contracts import (
    MigrationExpectation,
    ProvisioningPlan,
    ProvisioningTargetInspectionResult,
    RuntimeMigrationState,
    SeedCandidate,
    SeedExpectation,
    SeedInspection,
)


@runtime_checkable
class LocalProvisioningGateway(Protocol):
    def inspect_target(
        self, data_root: Path, project_identity: str
    ) -> ProvisioningTargetInspectionResult: ...

    def validate_migration_sources(self, migrations: tuple[MigrationExpectation, ...]) -> bool: ...

    def discover_seed_candidates(
        self, roots: tuple[Path, ...], expectations: tuple[SeedExpectation, ...]
    ) -> tuple[SeedCandidate, ...]: ...

    def authenticate_seed(
        self, candidate: SeedCandidate, expectation: SeedExpectation
    ) -> SeedInspection: ...

    def inspect_runtime(
        self, path: Path, migrations: tuple[MigrationExpectation, ...]
    ) -> RuntimeMigrationState: ...

    def create_data_root(self, path: Path) -> bool: ...

    def copy_reference_seed(
        self, source: SeedInspection, target: Path, expected_sha256: str
    ) -> str: ...

    def create_runtime_from_reference(
        self, reference: Path, runtime: Path, expected_sha256: str
    ) -> str: ...

    def create_backup(
        self, runtime: Path, backup: Path, reference: Path, migration_version: str
    ) -> str: ...

    def inspect_backup(
        self,
        backup: Path,
        migrations: tuple[MigrationExpectation, ...],
        expected_migration_version: str,
    ) -> str | None: ...

    def apply_migrations(
        self, runtime: Path, migrations: tuple[MigrationExpectation, ...]
    ) -> tuple[str, ...]: ...

    def create_library_root(self, path: Path) -> bool: ...

    def read_user_config(self, names: tuple[str, ...]) -> tuple[tuple[str, str | None], ...]: ...

    def write_user_config(self, values: tuple[tuple[str, str | None], ...]) -> None: ...

    def startup_probe(self, plan: ProvisioningPlan) -> bool: ...

    def snapshot_old_root(self, path: Path) -> str: ...


@runtime_checkable
class SuppliedSeedFileGateway(Protocol):
    def measure_seed_file(self, path: Path, allowed_root: Path) -> SeedCandidate | None: ...


@runtime_checkable
class ProvisioningTargetInspectionGateway(Protocol):
    def inspect_target(
        self, data_root: Path, project_identity: str
    ) -> ProvisioningTargetInspectionResult: ...
