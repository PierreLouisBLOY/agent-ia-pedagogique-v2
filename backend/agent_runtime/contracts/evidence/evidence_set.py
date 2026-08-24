from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from backend.agent_runtime.contracts.common import ContractMeta, freeze_agent_safe_mapping
from backend.agent_runtime.contracts.evidence.evidence_item import EvidenceItem
from backend.agent_runtime.contracts.invocation import AgentResultStatus


@dataclass(frozen=True, slots=True)
class EvidenceSet:
    """Possibly empty evidence result without synthetic filler items."""

    meta: ContractMeta[AgentResultStatus]
    evidence_items: tuple[EvidenceItem, ...] = ()
    coverage: Mapping[str, object] = field(default_factory=dict)
    conflicts: tuple[Mapping[str, object], ...] = ()
    limitations: tuple[Mapping[str, object], ...] = ()
    provenance_summary: Mapping[str, object] = field(default_factory=dict)
    retrieval_metrics: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.meta, ContractMeta):
            raise TypeError("meta must be a ContractMeta")
        if not isinstance(self.meta.status, AgentResultStatus):
            raise TypeError("meta.status must be an AgentResultStatus")
        items = tuple(self.evidence_items)
        if any(not isinstance(item, EvidenceItem) for item in items):
            raise TypeError("evidence_items must contain EvidenceItem values")
        evidence_ids = [item.evidence_id for item in items]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("evidence_items must have unique evidence_id values")
        conflicts = tuple(freeze_agent_safe_mapping(item) for item in self.conflicts)
        limitations = tuple(freeze_agent_safe_mapping(item) for item in self.limitations)
        object.__setattr__(self, "evidence_items", items)
        object.__setattr__(self, "coverage", freeze_agent_safe_mapping(self.coverage))
        object.__setattr__(self, "conflicts", conflicts)
        object.__setattr__(self, "limitations", limitations)
        object.__setattr__(
            self,
            "provenance_summary",
            freeze_agent_safe_mapping(self.provenance_summary),
        )
        object.__setattr__(
            self,
            "retrieval_metrics",
            freeze_agent_safe_mapping(self.retrieval_metrics),
        )
