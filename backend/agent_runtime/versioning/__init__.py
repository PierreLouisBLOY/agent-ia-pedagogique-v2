"""Version compatibility policy for canonical agent runtime contracts."""

from backend.agent_runtime.versioning.descriptors import (
    CONTRACT_VERSION_DESCRIPTORS,
    ContractVersionDescriptor,
)
from backend.agent_runtime.versioning.migrations import (
    BASELINE_MIGRATION_CATALOG,
    ContractMigration,
    ContractMigrationUnavailable,
    DuplicateContractMigration,
    MigrationCatalog,
)
from backend.agent_runtime.versioning.policy import (
    BASELINE_POLICY,
    ContractVersionPolicy,
    NestedContractVersionContextRequired,
    SupportedVersionRange,
    UnsupportedContractVersion,
    contract_schema_version,
    ensure_contract_version_supported,
    ensure_nested_contract_version_supported,
    is_valid_version_transition,
    required_bump,
)
from backend.agent_runtime.versioning.vocabulary import (
    ContractChangeKind,
    ContractFamily,
    MetadataMode,
    SupplementalContractKind,
    VersionBump,
    VersionedContractKey,
)

__all__ = [
    "BASELINE_MIGRATION_CATALOG",
    "BASELINE_POLICY",
    "CONTRACT_VERSION_DESCRIPTORS",
    "ContractChangeKind",
    "ContractFamily",
    "ContractMigration",
    "ContractMigrationUnavailable",
    "ContractVersionDescriptor",
    "ContractVersionPolicy",
    "DuplicateContractMigration",
    "MetadataMode",
    "MigrationCatalog",
    "NestedContractVersionContextRequired",
    "SupportedVersionRange",
    "SupplementalContractKind",
    "UnsupportedContractVersion",
    "VersionBump",
    "VersionedContractKey",
    "contract_schema_version",
    "ensure_contract_version_supported",
    "ensure_nested_contract_version_supported",
    "is_valid_version_transition",
    "required_bump",
]
