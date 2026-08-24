from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from backend.agent_runtime.contracts import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    AgentInvocation,
    AgentResult,
    ContractSchemaVersion,
    CorrectionRequest,
    CorrectionResult,
    DelegationEnvelope,
    DelegationResult,
    ErrorEnvelope,
    EvidenceRequest,
    EvidenceSet,
    GateDecision,
    GateRequest,
    ProductionCandidate,
    ProductionRequest,
    ReviewRequest,
    ReviewResult,
    ToolCallRequest,
    ToolCallResult,
    UseCaseRequest,
    UseCaseResult,
    WorkflowEvent,
)
from backend.agent_runtime.versioning.vocabulary import (
    ContractFamily,
    MetadataMode,
    SupplementalContractKind,
    VersionedContractKey,
)
from backend.shared_kernel._strings import require_non_empty


@dataclass(frozen=True, slots=True)
class ContractVersionDescriptor:
    key: VersionedContractKey
    contract_type: type[object]
    metadata_mode: MetadataMode
    current_version: ContractSchemaVersion
    version_path: str

    def __post_init__(self) -> None:
        if not isinstance(self.key, ContractFamily | SupplementalContractKind):
            raise TypeError("key must be a VersionedContractKey")
        if not isinstance(self.contract_type, type):
            raise TypeError("contract_type must be a type")
        if not isinstance(self.metadata_mode, MetadataMode):
            raise TypeError("metadata_mode must be a MetadataMode")
        if not isinstance(self.current_version, ContractSchemaVersion):
            raise TypeError("current_version must be a ContractSchemaVersion")
        require_non_empty(self.version_path, "version_path")


def _descriptor(
    key: VersionedContractKey,
    contract_type: type[object],
    metadata_mode: MetadataMode,
    version_path: str,
) -> ContractVersionDescriptor:
    return ContractVersionDescriptor(
        key=key,
        contract_type=contract_type,
        metadata_mode=metadata_mode,
        current_version=AGENT_CONTRACT_SCHEMA_V1_0,
        version_path=version_path,
    )


CONTRACT_VERSION_DESCRIPTORS: Final[
    Mapping[VersionedContractKey, ContractVersionDescriptor]
] = MappingProxyType(
    {
        ContractFamily.C01: _descriptor(
            ContractFamily.C01, AgentInvocation, MetadataMode.DIRECT_META, "meta.schema_version"
        ),
        ContractFamily.C02: _descriptor(
            ContractFamily.C02, AgentResult, MetadataMode.DIRECT_META, "meta.schema_version"
        ),
        ContractFamily.C03: _descriptor(
            ContractFamily.C03,
            DelegationEnvelope,
            MetadataMode.NESTED_VALUE,
            "parent.meta.schema_version",
        ),
        ContractFamily.C04: _descriptor(
            ContractFamily.C04,
            DelegationResult,
            MetadataMode.COMPOSED_META,
            "agent_result.meta.schema_version",
        ),
        ContractFamily.C05: _descriptor(
            ContractFamily.C05, EvidenceRequest, MetadataMode.DIRECT_META, "meta.schema_version"
        ),
        ContractFamily.C06: _descriptor(
            ContractFamily.C06, EvidenceSet, MetadataMode.DIRECT_META, "meta.schema_version"
        ),
        ContractFamily.C07: _descriptor(
            ContractFamily.C07, ProductionRequest, MetadataMode.DIRECT_META, "meta.schema_version"
        ),
        ContractFamily.C08: _descriptor(
            ContractFamily.C08, ProductionCandidate, MetadataMode.DIRECT_META, "meta.schema_version"
        ),
        ContractFamily.C09: _descriptor(
            ContractFamily.C09, ReviewRequest, MetadataMode.DIRECT_META, "meta.schema_version"
        ),
        ContractFamily.C10: _descriptor(
            ContractFamily.C10, ReviewResult, MetadataMode.DIRECT_META, "meta.schema_version"
        ),
        ContractFamily.C11: _descriptor(
            ContractFamily.C11, CorrectionRequest, MetadataMode.DIRECT_META, "meta.schema_version"
        ),
        ContractFamily.C12: _descriptor(
            ContractFamily.C12, UseCaseRequest, MetadataMode.DIRECT_META, "meta.schema_version"
        ),
        ContractFamily.C13: _descriptor(
            ContractFamily.C13, UseCaseResult, MetadataMode.DIRECT_META, "meta.schema_version"
        ),
        ContractFamily.C14: _descriptor(
            ContractFamily.C14, ToolCallRequest, MetadataMode.DIRECT_META, "meta.schema_version"
        ),
        ContractFamily.C15: _descriptor(
            ContractFamily.C15, ToolCallResult, MetadataMode.DIRECT_META, "meta.schema_version"
        ),
        ContractFamily.C16: _descriptor(
            ContractFamily.C16, GateRequest, MetadataMode.DIRECT_META, "meta.schema_version"
        ),
        ContractFamily.C17: _descriptor(
            ContractFamily.C17, GateDecision, MetadataMode.DIRECT_META, "meta.schema_version"
        ),
        ContractFamily.C18: _descriptor(
            ContractFamily.C18, WorkflowEvent, MetadataMode.DIRECT_META, "meta.schema_version"
        ),
        ContractFamily.C19: _descriptor(
            ContractFamily.C19,
            ErrorEnvelope,
            MetadataMode.NESTED_VALUE,
            "parent.meta.schema_version",
        ),
        SupplementalContractKind.CORRECTION_RESULT: _descriptor(
            SupplementalContractKind.CORRECTION_RESULT,
            CorrectionResult,
            MetadataMode.DIRECT_META,
            "meta.schema_version",
        ),
    }
)
