from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType

from backend.agent_runtime.agents.evidence.retrieval_model import (
    RetrievalCandidate,
    RetrievalChannel,
    RetrievalQuery,
    RetrievalSearchResult,
)
from backend.agent_runtime.contracts.common import ContractRef, require_contract_ref
from backend.shared_kernel._strings import require_non_empty
from backend.shared_kernel.references import ObjectVersionRef, TypedEntityRef


class RetrievalCoordinationMode(StrEnum):
    FULL = "FULL"
    DEGRADED = "DEGRADED"


@dataclass(frozen=True, slots=True)
class RetrievalCoordinationPolicy:
    """Replaceable technical defaults for deterministic hybrid coordination."""

    enabled_channels: tuple[RetrievalChannel, ...]
    required_channels: tuple[RetrievalChannel, ...]
    channel_limit: int
    final_limit: int
    rrf_k: int

    def __post_init__(self) -> None:
        _validate_channel_tuple(self.enabled_channels, "enabled_channels")
        _validate_channel_tuple(self.required_channels, "required_channels")
        enabled = frozenset(self.enabled_channels)
        required = frozenset(self.required_channels)
        baseline_required = {RetrievalChannel.STRUCTURED, RetrievalChannel.LEXICAL}
        if not baseline_required.issubset(enabled):
            raise ValueError("STRUCTURED and LEXICAL must be enabled")
        if not baseline_required.issubset(required):
            raise ValueError("STRUCTURED and LEXICAL must be required")
        if not required.issubset(enabled):
            raise ValueError("required_channels must be a subset of enabled_channels")
        if RetrievalChannel.DOCUMENT in enabled or RetrievalChannel.DOCUMENT in required:
            raise ValueError("DOCUMENT is not available during retrieval coordination")
        _require_positive_integer(self.channel_limit, "channel_limit")
        _require_positive_integer(self.final_limit, "final_limit")
        _require_positive_integer(self.rrf_k, "rrf_k")


class RetrievalChannelUnavailable(RuntimeError):
    channel: RetrievalChannel
    reason_code: str

    def __init__(self, channel: RetrievalChannel, reason_code: str) -> None:
        if not isinstance(channel, RetrievalChannel):
            raise TypeError("channel must be a RetrievalChannel")
        require_non_empty(reason_code, "reason_code")
        self.channel = channel
        self.reason_code = reason_code
        super().__init__(
            f"retrieval channel unavailable: {channel.value} ({reason_code})"
        )


class RetrievalCoordinationErrorCode(StrEnum):
    REQUIRED_CHANNEL_UNAVAILABLE = "REQUIRED_CHANNEL_UNAVAILABLE"
    INVALID_CHANNEL_RESULT = "INVALID_CHANNEL_RESULT"
    CHANNEL_RESULT_LIMIT_EXCEEDED = "CHANNEL_RESULT_LIMIT_EXCEEDED"
    STRUCTURED_ADMISSIBILITY_MISSING = "STRUCTURED_ADMISSIBILITY_MISSING"


class RetrievalCoordinationError(ValueError):
    code: RetrievalCoordinationErrorCode

    def __init__(self, code: RetrievalCoordinationErrorCode, message: str) -> None:
        if not isinstance(code, RetrievalCoordinationErrorCode):
            raise TypeError("code must be a RetrievalCoordinationErrorCode")
        require_non_empty(message, "message")
        self.code = code
        super().__init__(message)


@dataclass(frozen=True, slots=True, eq=False)
class RetrievalIdentity:
    canonical_object_ref: ContractRef | None
    source_ref: ContractRef
    locator: str
    version_or_checksum: str | None

    def __post_init__(self) -> None:
        if self.canonical_object_ref is not None:
            require_contract_ref(self.canonical_object_ref, "canonical_object_ref")
        require_contract_ref(self.source_ref, "source_ref")
        require_non_empty(self.locator, "locator")
        if self.version_or_checksum is not None:
            require_non_empty(self.version_or_checksum, "version_or_checksum")

    @classmethod
    def from_candidate(cls, candidate: RetrievalCandidate) -> RetrievalIdentity:
        if type(candidate) is not RetrievalCandidate:
            raise TypeError("candidate must be a RetrievalCandidate")
        return cls(
            canonical_object_ref=candidate.canonical_object_ref,
            source_ref=candidate.source_ref,
            locator=candidate.locator,
            version_or_checksum=candidate.version_or_checksum,
        )

    def deterministic_key(self) -> tuple[str, ...]:
        version_key = (
            ("version-none",)
            if self.version_or_checksum is None
            else ("version", self.version_or_checksum)
        )
        if self.canonical_object_ref is not None:
            return (
                "canonical",
                *_normalize_contract_ref(self.canonical_object_ref),
                *version_key,
            )
        return (
            "fallback",
            *_normalize_contract_ref(self.source_ref),
            "locator",
            self.locator,
            *version_key,
        )

    def __hash__(self) -> int:
        return hash(self.deterministic_key())

    def __eq__(self, other: object) -> bool:
        return isinstance(other, RetrievalIdentity) and (
            self.deterministic_key() == other.deterministic_key()
        )


@dataclass(frozen=True, slots=True)
class FusedRetrievalCandidate:
    identity: RetrievalIdentity
    representative: RetrievalCandidate
    occurrences: tuple[RetrievalCandidate, ...]
    channel_ranks: Mapping[RetrievalChannel, int]
    fusion_score: Decimal
    technical_rank: int

    def __post_init__(self) -> None:
        if not isinstance(self.identity, RetrievalIdentity):
            raise TypeError("identity must be a RetrievalIdentity")
        if not isinstance(self.occurrences, tuple):
            raise TypeError("occurrences must be a tuple")
        if not self.occurrences:
            raise ValueError("occurrences must not be empty")
        if any(type(item) is not RetrievalCandidate for item in self.occurrences):
            raise TypeError("occurrences must contain RetrievalCandidate values")
        if any(RetrievalIdentity.from_candidate(item) != self.identity for item in self.occurrences):
            raise ValueError("all occurrences must have the fused identity")
        if type(self.representative) is not RetrievalCandidate:
            raise TypeError("representative must be a RetrievalCandidate")
        if self.representative not in self.occurrences:
            raise ValueError("representative must belong to occurrences")
        has_structured = any(
            item.channel is RetrievalChannel.STRUCTURED for item in self.occurrences
        )
        if has_structured and self.representative.channel is not RetrievalChannel.STRUCTURED:
            raise ValueError("representative must prefer a STRUCTURED occurrence")
        if not isinstance(self.channel_ranks, Mapping):
            raise TypeError("channel_ranks must be a mapping")
        normalized_ranks: dict[RetrievalChannel, int] = {}
        for channel, rank in self.channel_ranks.items():
            if not isinstance(channel, RetrievalChannel):
                raise TypeError("channel_ranks keys must be RetrievalChannel values")
            _require_positive_integer(rank, "channel rank")
            normalized_ranks[channel] = rank
        occurrence_channels = {item.channel for item in self.occurrences}
        if set(normalized_ranks) != occurrence_channels:
            raise ValueError("channel_ranks must match occurrence channels")
        object.__setattr__(self, "channel_ranks", MappingProxyType(normalized_ranks))
        if not isinstance(self.fusion_score, Decimal):
            raise TypeError("fusion_score must be a Decimal")
        if not self.fusion_score.is_finite() or self.fusion_score <= 0:
            raise ValueError("fusion_score must be finite and > 0")
        _require_positive_integer(self.technical_rank, "technical_rank")


@dataclass(frozen=True, slots=True)
class RetrievalCoordinationResult:
    query: RetrievalQuery
    mode: RetrievalCoordinationMode
    ranked_candidates: tuple[FusedRetrievalCandidate, ...]
    channel_results: tuple[RetrievalSearchResult, ...]
    unavailable_channels: tuple[RetrievalChannel, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if type(self.query) is not RetrievalQuery:
            raise TypeError("query must be a RetrievalQuery")
        if not isinstance(self.mode, RetrievalCoordinationMode):
            raise TypeError("mode must be a RetrievalCoordinationMode")
        if not isinstance(self.ranked_candidates, tuple):
            raise TypeError("ranked_candidates must be a tuple")
        if any(
            type(candidate) is not FusedRetrievalCandidate
            for candidate in self.ranked_candidates
        ):
            raise TypeError("ranked_candidates must contain fused candidates")
        if tuple(candidate.technical_rank for candidate in self.ranked_candidates) != tuple(
            range(1, len(self.ranked_candidates) + 1)
        ):
            raise ValueError("technical ranks must be contiguous from 1")
        if not isinstance(self.channel_results, tuple):
            raise TypeError("channel_results must be a tuple")
        if any(type(result) is not RetrievalSearchResult for result in self.channel_results):
            raise TypeError("channel_results must contain RetrievalSearchResult values")
        result_channels = tuple(result.channel for result in self.channel_results)
        if len(result_channels) != len(set(result_channels)):
            raise ValueError("channel_results must have unique channels")
        required_result_channels = {
            RetrievalChannel.STRUCTURED,
            RetrievalChannel.LEXICAL,
        }
        if self.query.max_items != 0 and not required_result_channels.issubset(
            result_channels
        ):
            raise ValueError("STRUCTURED and LEXICAL channel results are required")
        if not isinstance(self.unavailable_channels, tuple):
            raise TypeError("unavailable_channels must be a tuple")
        if any(
            not isinstance(channel, RetrievalChannel)
            for channel in self.unavailable_channels
        ):
            raise TypeError("unavailable_channels must contain RetrievalChannel values")
        if len(self.unavailable_channels) != len(set(self.unavailable_channels)):
            raise ValueError("unavailable_channels must be unique")
        if set(result_channels).intersection(self.unavailable_channels):
            raise ValueError("a channel cannot be both available and unavailable")
        if self.mode is RetrievalCoordinationMode.FULL and self.unavailable_channels:
            raise ValueError("FULL mode cannot contain unavailable channels")
        if self.mode is RetrievalCoordinationMode.DEGRADED and not self.unavailable_channels:
            raise ValueError("DEGRADED mode requires an unavailable optional channel")
        if not isinstance(self.limitations, tuple):
            raise TypeError("limitations must be a tuple")
        for limitation in self.limitations:
            require_non_empty(limitation, "limitation")
        if len(self.limitations) != len(set(self.limitations)):
            raise ValueError("limitations must be unique")


def _validate_channel_tuple(
    channels: tuple[RetrievalChannel, ...], field_name: str
) -> None:
    if not isinstance(channels, tuple):
        raise TypeError(f"{field_name} must be a tuple")
    if any(not isinstance(channel, RetrievalChannel) for channel in channels):
        raise TypeError(f"{field_name} must contain RetrievalChannel values")
    if len(channels) != len(set(channels)):
        raise ValueError(f"{field_name} must contain unique channels")


def _require_positive_integer(value: int, field_name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{field_name} must be an integer")
    if value <= 0:
        raise ValueError(f"{field_name} must be > 0")


def _normalize_contract_ref(reference: ContractRef) -> tuple[str, ...]:
    if isinstance(reference, str):
        return ("string-ref", reference)
    if isinstance(reference, TypedEntityRef):
        return (
            "typed-entity-ref",
            reference.entity_id.entity_type,
            reference.entity_id.value,
        )
    if isinstance(reference, ObjectVersionRef):
        return (
            "object-version-ref",
            reference.object_ref.entity_id.entity_type,
            reference.object_ref.entity_id.value,
            reference.version_ref.value,
        )
    raise TypeError("reference must be a canonical ContractRef")


BASELINE_RETRIEVAL_COORDINATION_POLICY = RetrievalCoordinationPolicy(
    enabled_channels=(
        RetrievalChannel.STRUCTURED,
        RetrievalChannel.LEXICAL,
        RetrievalChannel.RELATIONAL,
        RetrievalChannel.SEMANTIC,
    ),
    required_channels=(
        RetrievalChannel.STRUCTURED,
        RetrievalChannel.LEXICAL,
    ),
    channel_limit=20,
    final_limit=10,
    rrf_k=60,
)
