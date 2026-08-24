from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from backend.agent_runtime.contracts.common import (
    ContractRef,
    freeze_agent_safe_mapping,
    require_contract_ref,
)
from backend.shared_kernel._strings import require_non_empty
from backend.shared_kernel.time import Instant

_NON_EVIDENCE_SOURCE_KINDS = frozenset(
    {"agent_output", "llm", "llm_output", "model_output"}
)


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    """One public evidence item with mandatory source provenance."""

    evidence_id: str
    source_ref: ContractRef
    source_kind: str
    locator: str
    retrieved_at: Instant
    relevance: Mapping[str, object] = field(default_factory=dict)
    authority: Mapping[str, object] = field(default_factory=dict)
    excerpt_or_summary: str | None = None
    checksum_or_version: str | None = None

    def __post_init__(self) -> None:
        require_non_empty(self.evidence_id, "evidence_id")
        require_contract_ref(self.source_ref, "source_ref")
        require_non_empty(self.source_kind, "source_kind")
        if self.source_kind.casefold() in _NON_EVIDENCE_SOURCE_KINDS:
            raise ValueError("agent or model output is not evidence by default")
        require_non_empty(self.locator, "locator")
        if not isinstance(self.retrieved_at, Instant):
            raise TypeError("retrieved_at must be an Instant")
        if self.excerpt_or_summary is not None:
            require_non_empty(self.excerpt_or_summary, "excerpt_or_summary")
        if self.checksum_or_version is not None:
            require_non_empty(self.checksum_or_version, "checksum_or_version")
        object.__setattr__(self, "relevance", freeze_agent_safe_mapping(self.relevance))
        object.__setattr__(self, "authority", freeze_agent_safe_mapping(self.authority))
