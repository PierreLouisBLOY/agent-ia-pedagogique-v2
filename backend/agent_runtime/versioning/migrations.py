from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Protocol

from backend.agent_runtime.contracts import ContractSchemaVersion
from backend.agent_runtime.contracts.common import freeze_agent_safe_mapping
from backend.agent_runtime.versioning.vocabulary import (
    ContractFamily,
    SupplementalContractKind,
    VersionedContractKey,
)


class ContractMigration(Protocol):
    key: VersionedContractKey
    from_version: ContractSchemaVersion
    to_version: ContractSchemaVersion

    def migrate(self, payload: Mapping[str, object]) -> Mapping[str, object]: ...


class DuplicateContractMigration(ValueError):
    pass


class ContractMigrationUnavailable(ValueError):
    def __init__(
        self,
        key: VersionedContractKey,
        from_version: ContractSchemaVersion,
        to_version: ContractSchemaVersion,
    ) -> None:
        self.key = key
        self.from_version = from_version
        self.to_version = to_version
        super().__init__(
            f"no explicit migration for {key.value} from {from_version} to {to_version}"
        )


MigrationEdge = tuple[VersionedContractKey, ContractSchemaVersion, ContractSchemaVersion]


@dataclass(frozen=True, slots=True)
class MigrationCatalog:
    _migrations: Mapping[MigrationEdge, ContractMigration] = field(
        init=False,
        repr=False,
    )

    def __init__(self, migrations: Iterable[ContractMigration] = ()) -> None:
        by_edge: dict[MigrationEdge, ContractMigration] = {}
        for migration in migrations:
            _validate_migration(migration)
            edge = (migration.key, migration.from_version, migration.to_version)
            if edge in by_edge:
                raise DuplicateContractMigration(
                    f"duplicate migration for {migration.key.value} "
                    f"from {migration.from_version} to {migration.to_version}"
                )
            by_edge[edge] = migration
        object.__setattr__(self, "_migrations", MappingProxyType(by_edge))

    @property
    def registered_edges(self) -> tuple[MigrationEdge, ...]:
        return tuple(self._migrations)

    def migration_for(
        self,
        key: VersionedContractKey,
        from_version: ContractSchemaVersion,
        to_version: ContractSchemaVersion,
    ) -> ContractMigration:
        edge = _validated_edge(key, from_version, to_version)
        migration = self._migrations.get(edge)
        if migration is None:
            raise ContractMigrationUnavailable(key, from_version, to_version)
        return migration

    def migrate(
        self,
        key: VersionedContractKey,
        from_version: ContractSchemaVersion,
        to_version: ContractSchemaVersion,
        payload: Mapping[str, object],
    ) -> Mapping[str, object]:
        if not isinstance(payload, Mapping):
            raise TypeError("payload must be a mapping")
        migration = self.migration_for(key, from_version, to_version)
        safe_payload = freeze_agent_safe_mapping(payload)
        migrated = migration.migrate(safe_payload)
        if not isinstance(migrated, Mapping):
            raise TypeError("migration output must be a mapping")
        return freeze_agent_safe_mapping(migrated)


def _validate_migration(migration: ContractMigration) -> None:
    _validated_edge(migration.key, migration.from_version, migration.to_version)
    if migration.from_version == migration.to_version:
        raise ValueError("migration versions must differ")
    if not callable(migration.migrate):
        raise TypeError("migration must define migrate")


def _validated_edge(
    key: VersionedContractKey,
    from_version: ContractSchemaVersion,
    to_version: ContractSchemaVersion,
) -> MigrationEdge:
    if not isinstance(key, ContractFamily | SupplementalContractKind):
        raise TypeError("key must be a VersionedContractKey")
    if not isinstance(from_version, ContractSchemaVersion):
        raise TypeError("from_version must be a ContractSchemaVersion")
    if not isinstance(to_version, ContractSchemaVersion):
        raise TypeError("to_version must be a ContractSchemaVersion")
    return key, from_version, to_version


BASELINE_MIGRATION_CATALOG = MigrationCatalog()
