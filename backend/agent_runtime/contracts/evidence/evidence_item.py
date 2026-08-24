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
        if _is_manifestly_generative_source_kind(self.source_kind):
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


def _is_manifestly_generative_source_kind(source_kind: str) -> bool:
    components = frozenset(_source_kind_components(source_kind))
    if "llm" in components:
        return True
    generated_output = bool(components.intersection({"generated", "output"}))
    return generated_output and bool(components.intersection({"agent", "model"}))


def _source_kind_components(source_kind: str) -> tuple[str, ...]:
    components: list[str] = []
    current: list[str] = []

    for index, character in enumerate(source_kind):
        if not character.isalnum():
            if current:
                components.append("".join(current).casefold())
                current = []
            continue

        next_character = source_kind[index + 1] if index + 1 < len(source_kind) else ""
        starts_camel_word = bool(
            current
            and character.isupper()
            and (
                current[-1].islower()
                or (current[-1].isupper() and next_character.islower())
            )
        )
        if starts_camel_word:
            components.append("".join(current).casefold())
            current = []
        current.append(character)

    if current:
        components.append("".join(current).casefold())
    return tuple(components)
