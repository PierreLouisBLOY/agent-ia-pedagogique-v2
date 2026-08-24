from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import cast

from backend.agent_runtime.contracts.common import (
    ContractMeta,
    ContractRef,
    freeze_agent_safe_mapping,
    require_contract_ref,
)
from backend.agent_runtime.contracts.invocation import AgentResultStatus
from backend.shared_kernel._strings import require_non_empty


class ProductionValidationState(StrEnum):
    CANDIDATE = "candidate"


@dataclass(frozen=True, slots=True)
class ProductionCandidate:
    """Non-canonical generated content that cannot represent validation or promotion."""

    meta: ContractMeta[AgentResultStatus]
    production_id: str
    production_kind: str
    content: str | None = None
    structured_payload: Mapping[str, object] = field(default_factory=dict)
    lineage: Mapping[str, object] = field(default_factory=dict)
    evidence_refs_used: tuple[ContractRef, ...] = ()
    validation_state: ProductionValidationState = ProductionValidationState.CANDIDATE
    warnings: tuple[Mapping[str, object], ...] = ()
    uncertainties: tuple[Mapping[str, object], ...] = ()
    generation_metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.meta, ContractMeta):
            raise TypeError("meta must be a ContractMeta")
        if not isinstance(self.meta.status, AgentResultStatus):
            raise TypeError("meta.status must be an AgentResultStatus")
        require_non_empty(self.production_id, "production_id")
        require_non_empty(self.production_kind, "production_kind")
        if self.content is not None:
            require_non_empty(self.content, "content")
        if self.content is None and not self.structured_payload:
            raise ValueError("content or structured_payload is required")
        if self.validation_state is not ProductionValidationState.CANDIDATE:
            raise ValueError("validation_state must be candidate")
        evidence_refs = tuple(self.evidence_refs_used)
        for evidence_ref in evidence_refs:
            require_contract_ref(evidence_ref, "evidence_ref_used")
        warnings = tuple(freeze_agent_safe_mapping(item) for item in self.warnings)
        uncertainties = tuple(
            freeze_agent_safe_mapping(item) for item in self.uncertainties
        )
        for lineage_key in ("parent_production_ref", "target_ref"):
            if lineage_key in self.lineage:
                require_contract_ref(
                    cast(ContractRef, self.lineage[lineage_key]),
                    lineage_key,
                )
        object.__setattr__(
            self,
            "structured_payload",
            freeze_agent_safe_mapping(self.structured_payload),
        )
        object.__setattr__(self, "lineage", freeze_agent_safe_mapping(self.lineage))
        object.__setattr__(self, "evidence_refs_used", evidence_refs)
        object.__setattr__(self, "warnings", warnings)
        object.__setattr__(self, "uncertainties", uncertainties)
        object.__setattr__(
            self,
            "generation_metadata",
            freeze_agent_safe_mapping(self.generation_metadata),
        )
