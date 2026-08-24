from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from backend.agent_runtime.contracts.common import (
    ContractRef,
    freeze_agent_safe_mapping,
    require_contract_ref,
)
from backend.shared_kernel._strings import require_non_empty


@dataclass(frozen=True, slots=True)
class Finding:
    """Public, concise review finding with no private reasoning payload."""

    finding_id: str
    dimension: str
    severity: str
    description: str
    target_locator: Mapping[str, object]
    rationale: str
    evidence_refs: tuple[ContractRef, ...] = ()

    def __post_init__(self) -> None:
        require_non_empty(self.finding_id, "finding_id")
        require_non_empty(self.dimension, "dimension")
        require_non_empty(self.severity, "severity")
        require_non_empty(self.description, "description")
        require_non_empty(self.rationale, "rationale")
        evidence_refs = tuple(self.evidence_refs)
        for evidence_ref in evidence_refs:
            require_contract_ref(evidence_ref, "evidence_ref")
        object.__setattr__(
            self, "target_locator", freeze_agent_safe_mapping(self.target_locator)
        )
        object.__setattr__(self, "evidence_refs", evidence_refs)
