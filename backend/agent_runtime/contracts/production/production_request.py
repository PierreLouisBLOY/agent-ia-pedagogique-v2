from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from backend.agent_runtime.contracts.common import (
    ContractMeta,
    ContractRef,
    freeze_agent_safe_mapping,
    require_contract_ref,
)
from backend.agent_runtime.contracts.invocation import InvocationStatus
from backend.shared_kernel._strings import require_non_empty


@dataclass(frozen=True, slots=True)
class ProductionRequest:
    """Declarative request for a non-persistent production candidate."""

    meta: ContractMeta[InvocationStatus]
    production_kind: str
    brief: str
    output_format: str
    pedagogical_context: Mapping[str, object] = field(default_factory=dict)
    constraints: Mapping[str, object] = field(default_factory=dict)
    evidence_refs: tuple[ContractRef, ...] = ()
    target_ref: ContractRef | None = None
    expected_sections: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.meta, ContractMeta):
            raise TypeError("meta must be a ContractMeta")
        if not isinstance(self.meta.status, InvocationStatus):
            raise TypeError("meta.status must be an InvocationStatus")
        require_non_empty(self.production_kind, "production_kind")
        require_non_empty(self.brief, "brief")
        require_non_empty(self.output_format, "output_format")
        evidence_refs = tuple(self.evidence_refs)
        for evidence_ref in evidence_refs:
            require_contract_ref(evidence_ref, "evidence_ref")
        if self.target_ref is not None:
            require_contract_ref(self.target_ref, "target_ref")
        sections = tuple(self.expected_sections)
        for section in sections:
            require_non_empty(section, "expected_section")
        object.__setattr__(
            self,
            "pedagogical_context",
            freeze_agent_safe_mapping(self.pedagogical_context),
        )
        object.__setattr__(self, "constraints", freeze_agent_safe_mapping(self.constraints))
        object.__setattr__(self, "evidence_refs", evidence_refs)
        object.__setattr__(self, "expected_sections", sections)
