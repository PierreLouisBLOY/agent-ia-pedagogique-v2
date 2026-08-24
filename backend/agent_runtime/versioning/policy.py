from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from backend.agent_runtime.contracts import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    AgentResult,
    ContractMeta,
    ContractSchemaVersion,
)
from backend.agent_runtime.versioning.descriptors import CONTRACT_VERSION_DESCRIPTORS
from backend.agent_runtime.versioning.vocabulary import (
    ContractChangeKind,
    ContractFamily,
    MetadataMode,
    SupplementalContractKind,
    VersionBump,
    VersionedContractKey,
)


@dataclass(frozen=True, slots=True)
class SupportedVersionRange:
    major: int
    min_minor: int
    max_minor: int

    def __post_init__(self) -> None:
        for field_name, value in (
            ("major", self.major),
            ("min_minor", self.min_minor),
            ("max_minor", self.max_minor),
        ):
            if type(value) is not int:
                raise TypeError(f"{field_name} must be an integer")
        if self.major < 1:
            raise ValueError("major must be >= 1")
        if self.min_minor < 0:
            raise ValueError("min_minor must be >= 0")
        if self.max_minor < self.min_minor:
            raise ValueError("max_minor must be >= min_minor")

    def supports(self, version: ContractSchemaVersion) -> bool:
        if not isinstance(version, ContractSchemaVersion):
            raise TypeError("version must be a ContractSchemaVersion")
        return (
            version.major == self.major
            and self.min_minor <= version.minor <= self.max_minor
        )


class UnsupportedContractVersion(ValueError):
    def __init__(self, key: VersionedContractKey, version: ContractSchemaVersion) -> None:
        self.key = key
        self.version = version
        super().__init__(f"unsupported version {version} for {key.value}")


class NestedContractVersionContextRequired(ValueError):
    def __init__(self, key: ContractFamily) -> None:
        self.key = key
        super().__init__(f"parent version context required for {key.value}")


@dataclass(frozen=True, slots=True)
class ContractVersionPolicy:
    ranges_by_key: Mapping[VersionedContractKey, tuple[SupportedVersionRange, ...]]

    def __post_init__(self) -> None:
        normalized: dict[VersionedContractKey, tuple[SupportedVersionRange, ...]] = {}
        for key, ranges in self.ranges_by_key.items():
            if not isinstance(key, ContractFamily | SupplementalContractKind):
                raise TypeError("policy keys must be VersionedContractKey values")
            normalized_ranges = tuple(ranges)
            if any(not isinstance(item, SupportedVersionRange) for item in normalized_ranges):
                raise TypeError("policy ranges must contain SupportedVersionRange values")
            normalized[key] = normalized_ranges
        object.__setattr__(self, "ranges_by_key", MappingProxyType(normalized))

    def supported_ranges(
        self, key: VersionedContractKey
    ) -> tuple[SupportedVersionRange, ...]:
        if not isinstance(key, ContractFamily | SupplementalContractKind):
            raise TypeError("key must be a VersionedContractKey")
        return self.ranges_by_key.get(key, ())

    def is_supported(
        self, key: VersionedContractKey, version: ContractSchemaVersion
    ) -> bool:
        if not isinstance(version, ContractSchemaVersion):
            raise TypeError("version must be a ContractSchemaVersion")
        return any(item.supports(version) for item in self.supported_ranges(key))

    def ensure_supported(
        self, key: VersionedContractKey, version: ContractSchemaVersion
    ) -> None:
        if not self.is_supported(key, version):
            raise UnsupportedContractVersion(key, version)


_BASELINE_RANGE = SupportedVersionRange(
    major=AGENT_CONTRACT_SCHEMA_V1_0.major,
    min_minor=AGENT_CONTRACT_SCHEMA_V1_0.minor,
    max_minor=AGENT_CONTRACT_SCHEMA_V1_0.minor,
)

BASELINE_POLICY = ContractVersionPolicy(
    {
        key: (_BASELINE_RANGE,) for key in CONTRACT_VERSION_DESCRIPTORS
    }
)


def contract_schema_version(
    key: VersionedContractKey, contract: object
) -> ContractSchemaVersion:
    if not isinstance(key, ContractFamily | SupplementalContractKind):
        raise TypeError("key must be a VersionedContractKey")
    descriptor = CONTRACT_VERSION_DESCRIPTORS[key]
    if not isinstance(contract, descriptor.contract_type):
        raise TypeError(f"contract must be a {descriptor.contract_type.__name__}")
    if descriptor.metadata_mode is MetadataMode.NESTED_VALUE:
        if not isinstance(key, ContractFamily):
            raise ValueError("supplemental contracts cannot use nested metadata")
        raise NestedContractVersionContextRequired(key)
    if descriptor.metadata_mode is MetadataMode.COMPOSED_META:
        agent_result = getattr(contract, "agent_result", None)
        if not isinstance(agent_result, AgentResult):
            raise TypeError("composed contract must contain an AgentResult")
        return agent_result.meta.schema_version
    meta = getattr(contract, "meta", None)
    if not isinstance(meta, ContractMeta):
        raise TypeError("direct contract must contain ContractMeta")
    return meta.schema_version


def ensure_contract_version_supported(
    key: VersionedContractKey,
    contract: object,
    policy: ContractVersionPolicy = BASELINE_POLICY,
) -> None:
    if not isinstance(policy, ContractVersionPolicy):
        raise TypeError("policy must be a ContractVersionPolicy")
    policy.ensure_supported(key, contract_schema_version(key, contract))


def ensure_nested_contract_version_supported(
    key: ContractFamily,
    parent_version: ContractSchemaVersion,
    policy: ContractVersionPolicy = BASELINE_POLICY,
) -> None:
    if not isinstance(key, ContractFamily):
        raise TypeError("key must be a ContractFamily")
    if CONTRACT_VERSION_DESCRIPTORS[key].metadata_mode is not MetadataMode.NESTED_VALUE:
        raise ValueError(f"{key.value} is not a nested contract family")
    if not isinstance(policy, ContractVersionPolicy):
        raise TypeError("policy must be a ContractVersionPolicy")
    policy.ensure_supported(key, parent_version)


def required_bump(kind: ContractChangeKind) -> VersionBump:
    if not isinstance(kind, ContractChangeKind):
        raise TypeError("kind must be a ContractChangeKind")
    if kind is ContractChangeKind.ADDITIVE:
        return VersionBump.MINOR
    return VersionBump.MAJOR


def is_valid_version_transition(
    old: ContractSchemaVersion,
    new: ContractSchemaVersion,
    kind: ContractChangeKind,
) -> bool:
    if not isinstance(old, ContractSchemaVersion):
        raise TypeError("old must be a ContractSchemaVersion")
    if not isinstance(new, ContractSchemaVersion):
        raise TypeError("new must be a ContractSchemaVersion")
    bump = required_bump(kind)
    if bump is VersionBump.MINOR:
        return new.major == old.major and new.minor > old.minor
    return new.major > old.major
