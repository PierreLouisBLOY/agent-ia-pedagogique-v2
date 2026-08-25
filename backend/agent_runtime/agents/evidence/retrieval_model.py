from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum

from backend.agent_runtime.contracts.common import (
    ContractRef,
    freeze_agent_safe_mapping,
    require_contract_ref,
)
from backend.agent_runtime.contracts.evidence import EvidenceRequest
from backend.shared_kernel._strings import require_non_empty
from backend.shared_kernel.time import Instant


class RetrievalChannel(StrEnum):
    STRUCTURED = "STRUCTURED"
    LEXICAL = "LEXICAL"
    SEMANTIC = "SEMANTIC"
    RELATIONAL = "RELATIONAL"
    DOCUMENT = "DOCUMENT"


@dataclass(frozen=True, slots=True)
class RetrievalQuery:
    """Technical retrieval constraints derived without widening an evidence request."""

    search_goal: str
    scope: Mapping[str, object]
    source_policy: Mapping[str, object]
    filters: Mapping[str, object]
    required_authority: Mapping[str, object] | None
    max_items: int | None

    def __post_init__(self) -> None:
        require_non_empty(self.search_goal, "search_goal")
        if self.max_items is not None:
            if not isinstance(self.max_items, int) or isinstance(self.max_items, bool):
                raise TypeError("max_items must be an integer")
            if self.max_items < 0:
                raise ValueError("max_items must be >= 0")
        object.__setattr__(self, "scope", freeze_agent_safe_mapping(self.scope))
        object.__setattr__(
            self,
            "source_policy",
            freeze_agent_safe_mapping(self.source_policy),
        )
        object.__setattr__(self, "filters", freeze_agent_safe_mapping(self.filters))
        if self.required_authority is not None:
            object.__setattr__(
                self,
                "required_authority",
                freeze_agent_safe_mapping(self.required_authority),
            )

    @classmethod
    def from_evidence_request(cls, request: EvidenceRequest) -> RetrievalQuery:
        if type(request) is not EvidenceRequest:
            raise TypeError("request must be an EvidenceRequest")
        return cls(
            search_goal=request.search_goal,
            scope=request.scope,
            source_policy=request.source_policy,
            filters=request.filters,
            required_authority=request.required_authority,
            max_items=request.max_items,
        )


@dataclass(frozen=True, slots=True)
class RetrievalSignals:
    """Independent reconstructible signals; no combined authority score is implied."""

    structured_rank: int | None = None
    lexical_score: Decimal | None = None
    semantic_score: Decimal | None = None
    relational_score: Decimal | None = None

    def __post_init__(self) -> None:
        if self.structured_rank is not None:
            if not isinstance(self.structured_rank, int) or isinstance(
                self.structured_rank, bool
            ):
                raise TypeError("structured_rank must be an integer")
            if self.structured_rank < 0:
                raise ValueError("structured_rank must be >= 0")
        for field_name, score in (
            ("lexical_score", self.lexical_score),
            ("semantic_score", self.semantic_score),
            ("relational_score", self.relational_score),
        ):
            if score is not None:
                if not isinstance(score, Decimal):
                    raise TypeError(f"{field_name} must be a Decimal")
                if not score.is_finite():
                    raise ValueError(f"{field_name} must be finite")


@dataclass(frozen=True, slots=True)
class RetrievalCandidate:
    """A bounded search candidate, distinct from canonical evidence."""

    candidate_id: str
    channel: RetrievalChannel
    source_ref: ContractRef
    source_kind: str
    locator: str
    signals: RetrievalSignals
    canonical_object_ref: ContractRef | None = None
    version_or_checksum: str | None = None
    provenance: Mapping[str, object] = field(default_factory=dict)
    authority: Mapping[str, object] = field(default_factory=dict)
    metadata: Mapping[str, object] = field(default_factory=dict)
    security_warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        require_non_empty(self.candidate_id, "candidate_id")
        if not isinstance(self.channel, RetrievalChannel):
            raise TypeError("channel must be a RetrievalChannel")
        require_contract_ref(self.source_ref, "source_ref")
        require_non_empty(self.source_kind, "source_kind")
        require_non_empty(self.locator, "locator")
        if not isinstance(self.signals, RetrievalSignals):
            raise TypeError("signals must be RetrievalSignals")
        if self.canonical_object_ref is not None:
            require_contract_ref(self.canonical_object_ref, "canonical_object_ref")
        if self.version_or_checksum is not None:
            require_non_empty(self.version_or_checksum, "version_or_checksum")
        object.__setattr__(
            self,
            "provenance",
            freeze_agent_safe_mapping(self.provenance),
        )
        object.__setattr__(
            self,
            "authority",
            freeze_agent_safe_mapping(self.authority),
        )
        object.__setattr__(self, "metadata", freeze_agent_safe_mapping(self.metadata))
        _validate_security_warnings(self.security_warnings)


@dataclass(frozen=True, slots=True)
class RetrievalSearchResult:
    """The bounded result returned by exactly one retrieval channel."""

    channel: RetrievalChannel
    candidates: tuple[RetrievalCandidate, ...]
    limitations: tuple[Mapping[str, object], ...] = ()
    metrics: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.channel, RetrievalChannel):
            raise TypeError("channel must be a RetrievalChannel")
        if not isinstance(self.candidates, tuple):
            raise TypeError("candidates must be a tuple")
        if any(not isinstance(candidate, RetrievalCandidate) for candidate in self.candidates):
            raise TypeError("candidates must contain RetrievalCandidate values")
        if any(candidate.channel is not self.channel for candidate in self.candidates):
            raise ValueError("candidate channel must match result channel")
        candidate_ids = [candidate.candidate_id for candidate in self.candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("candidates must have unique candidate_id values")
        if not isinstance(self.limitations, tuple):
            raise TypeError("limitations must be a tuple")
        object.__setattr__(
            self,
            "limitations",
            tuple(freeze_agent_safe_mapping(item) for item in self.limitations),
        )
        object.__setattr__(self, "metrics", freeze_agent_safe_mapping(self.metrics))


@dataclass(frozen=True, slots=True)
class DocumentContentRequest:
    """Controlled request for content identified by an opaque adapter locator."""

    candidate_id: str
    source_ref: ContractRef
    locator: str
    source_policy: Mapping[str, object]

    def __post_init__(self) -> None:
        require_non_empty(self.candidate_id, "candidate_id")
        require_contract_ref(self.source_ref, "source_ref")
        require_non_empty(self.locator, "locator")
        object.__setattr__(
            self,
            "source_policy",
            freeze_agent_safe_mapping(self.source_policy),
        )


@dataclass(frozen=True, slots=True)
class DocumentContentResult:
    """Untrusted document data returned through controlled content access."""

    candidate_id: str
    source_ref: ContractRef
    locator: str
    content: str
    retrieved_at: Instant
    source_kind: str
    version_or_checksum: str | None = None
    provenance: Mapping[str, object] = field(default_factory=dict)
    metadata: Mapping[str, object] = field(default_factory=dict)
    security_warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        require_non_empty(self.candidate_id, "candidate_id")
        require_contract_ref(self.source_ref, "source_ref")
        require_non_empty(self.locator, "locator")
        require_non_empty(self.content, "content")
        if not isinstance(self.retrieved_at, Instant):
            raise TypeError("retrieved_at must be an Instant")
        require_non_empty(self.source_kind, "source_kind")
        if self.version_or_checksum is not None:
            require_non_empty(self.version_or_checksum, "version_or_checksum")
        object.__setattr__(
            self,
            "provenance",
            freeze_agent_safe_mapping(self.provenance),
        )
        object.__setattr__(self, "metadata", freeze_agent_safe_mapping(self.metadata))
        _validate_security_warnings(self.security_warnings)


def _validate_security_warnings(warnings: tuple[str, ...]) -> None:
    if not isinstance(warnings, tuple):
        raise TypeError("security_warnings must be a tuple")
    for warning in warnings:
        require_non_empty(warning, "security_warnings item")
    if len(warnings) != len(set(warnings)):
        raise ValueError("security_warnings must be unique")
