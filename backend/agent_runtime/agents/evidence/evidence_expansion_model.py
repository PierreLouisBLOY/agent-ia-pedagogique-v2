from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from backend.agent_runtime.agents.evidence.evidence_agent_model import (
    EvidenceMaterializationError,
    validate_retrieval_lineage,
)
from backend.agent_runtime.agents.evidence.evidence_security_model import (
    EvidenceSecurityAssessment,
    EvidenceSecuritySignalCode,
    EvidenceSignalCode,
)
from backend.agent_runtime.agents.evidence.retrieval_coordination_model import (
    RetrievalCoordinationResult,
)
from backend.agent_runtime.contracts.common import freeze_agent_safe_mapping
from backend.agent_runtime.contracts.evidence import EvidenceRequest, EvidenceSet
from backend.agent_runtime.contracts.security import ContentThreatSignalCode
from backend.agent_runtime.policy import BASELINE_AGENT_RUNTIME_POLICY
from backend.shared_kernel._strings import require_non_empty


@dataclass(frozen=True, slots=True)
class EvidenceExpansionPolicy:
    max_rounds: int
    max_items_per_set: int

    def __post_init__(self) -> None:
        _require_positive_integer(self.max_rounds, "max_rounds")
        _require_positive_integer(self.max_items_per_set, "max_items_per_set")


class EvidenceExpansionAction(StrEnum):
    NO_EXPANSION = "NO_EXPANSION"
    PROPOSE_NEXT_ROUND = "PROPOSE_NEXT_ROUND"
    STOP_MAX_ROUNDS = "STOP_MAX_ROUNDS"
    STOP_NO_PROGRESS = "STOP_NO_PROGRESS"


class EvidenceExpansionErrorCode(StrEnum):
    HISTORY_LINEAGE_MISMATCH = "HISTORY_LINEAGE_MISMATCH"
    EVIDENCE_SET_LINEAGE_MISMATCH = "EVIDENCE_SET_LINEAGE_MISMATCH"
    MAX_ITEMS_WIDENING = "MAX_ITEMS_WIDENING"
    INVALID_ROUND_HISTORY = "INVALID_ROUND_HISTORY"
    SECURITY_ASSESSMENT_LINEAGE_MISMATCH = (
        "SECURITY_ASSESSMENT_LINEAGE_MISMATCH"
    )


class EvidenceExpansionError(ValueError):
    code: EvidenceExpansionErrorCode

    def __init__(self, code: EvidenceExpansionErrorCode, message: str) -> None:
        if not isinstance(code, EvidenceExpansionErrorCode):
            raise TypeError("code must be an EvidenceExpansionErrorCode")
        require_non_empty(message, "message")
        self.code = code
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class EvidenceRoundRecord:
    round_number: int
    request: EvidenceRequest
    retrieval_identity_keys: tuple[tuple[str, ...], ...]
    evidence_ids: tuple[str, ...]
    coverage_status: str
    security_signal_codes: tuple[EvidenceSignalCode, ...]

    def __post_init__(self) -> None:
        _require_positive_integer(self.round_number, "round_number")
        if type(self.request) is not EvidenceRequest:
            raise TypeError("request must be an EvidenceRequest")
        _validate_identity_keys(self.retrieval_identity_keys)
        _validate_string_tuple(self.evidence_ids, "evidence_ids")
        if self.coverage_status not in {"COMPLETE", "PARTIAL", "EMPTY"}:
            raise ValueError("coverage_status must be COMPLETE, PARTIAL, or EMPTY")
        _validate_security_codes(self.security_signal_codes)

    @classmethod
    def from_results(
        cls,
        *,
        round_number: int,
        request: EvidenceRequest,
        retrieval: RetrievalCoordinationResult,
        evidence_set: EvidenceSet,
        security: EvidenceSecurityAssessment,
    ) -> EvidenceRoundRecord:
        if type(request) is not EvidenceRequest:
            raise TypeError("request must be an EvidenceRequest")
        if type(retrieval) is not RetrievalCoordinationResult:
            raise TypeError("retrieval must be a RetrievalCoordinationResult")
        if type(evidence_set) is not EvidenceSet:
            raise TypeError("evidence_set must be an EvidenceSet")
        if type(security) is not EvidenceSecurityAssessment:
            raise TypeError("security must be an EvidenceSecurityAssessment")
        try:
            validate_retrieval_lineage(request, retrieval)
        except EvidenceMaterializationError as error:
            raise EvidenceExpansionError(
                EvidenceExpansionErrorCode.HISTORY_LINEAGE_MISMATCH,
                "retrieval does not belong to the evidence request",
            ) from error
        if (
            evidence_set.meta.run_id != request.meta.run_id
            or evidence_set.meta.correlation_id != request.meta.correlation_id
        ):
            raise EvidenceExpansionError(
                EvidenceExpansionErrorCode.EVIDENCE_SET_LINEAGE_MISMATCH,
                "evidence set metadata does not match the request",
            )
        evidence_ids = tuple(
            item.evidence_id for item in evidence_set.evidence_items
        )
        assessed_ids = {
            evidence_id
            for group in security.independent_corroboration_groups
            for evidence_id in group
        }
        if assessed_ids != set(evidence_ids):
            raise EvidenceExpansionError(
                EvidenceExpansionErrorCode.EVIDENCE_SET_LINEAGE_MISMATCH,
                "security assessment does not match the evidence set",
            )
        coverage_status = evidence_set.coverage.get("status")
        if coverage_status not in {"COMPLETE", "PARTIAL", "EMPTY"}:
            raise EvidenceExpansionError(
                EvidenceExpansionErrorCode.EVIDENCE_SET_LINEAGE_MISMATCH,
                "evidence set coverage status is invalid",
            )
        security_codes = _stable_unique_security_codes(
            tuple(signal.code for signal in security.signals)
        )
        return cls(
            round_number=round_number,
            request=request,
            retrieval_identity_keys=tuple(
                candidate.identity.deterministic_key()
                for candidate in retrieval.ranked_candidates
            ),
            evidence_ids=evidence_ids,
            coverage_status=coverage_status,
            security_signal_codes=security_codes,
        )


@dataclass(frozen=True, slots=True)
class EvidenceExpansionHistory:
    records: tuple[EvidenceRoundRecord, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.records, tuple) or any(
            type(record) is not EvidenceRoundRecord for record in self.records
        ):
            raise TypeError("records must contain EvidenceRoundRecord values")
        if not self.records:
            _raise_expansion_error(
                EvidenceExpansionErrorCode.INVALID_ROUND_HISTORY,
                "history must contain at least one round",
            )
        if tuple(record.round_number for record in self.records) != tuple(
            range(1, len(self.records) + 1)
        ):
            _raise_expansion_error(
                EvidenceExpansionErrorCode.INVALID_ROUND_HISTORY,
                "round numbers must be contiguous from one",
            )
        initial = self.records[0].request
        for record in self.records[1:]:
            request = record.request
            if (
                request.meta.run_id != initial.meta.run_id
                or request.meta.correlation_id != initial.meta.correlation_id
                or request.scope != initial.scope
                or request.source_policy != initial.source_policy
                or request.filters != initial.filters
                or request.required_authority != initial.required_authority
            ):
                _raise_expansion_error(
                    EvidenceExpansionErrorCode.HISTORY_LINEAGE_MISMATCH,
                    "evidence round lineage differs from the initial request",
                )
            if initial.max_items is not None and (
                request.max_items is None or request.max_items > initial.max_items
            ):
                _raise_expansion_error(
                    EvidenceExpansionErrorCode.MAX_ITEMS_WIDENING,
                    "evidence round widens the initial item limit",
                )


@dataclass(frozen=True, slots=True)
class EvidenceExpansionNeed:
    required: bool
    reason_codes: tuple[str, ...]
    next_search_goal: str | None
    requested_max_items: int | None = None

    def __post_init__(self) -> None:
        if type(self.required) is not bool:
            raise TypeError("required must be a bool")
        _validate_string_tuple(self.reason_codes, "reason_codes")
        if self.required:
            if not self.reason_codes:
                raise ValueError("required expansion needs at least one reason code")
            if self.next_search_goal is None:
                raise ValueError("required expansion needs a next search goal")
            require_non_empty(self.next_search_goal, "next_search_goal")
        elif self.next_search_goal is not None:
            raise ValueError("next_search_goal must be None when expansion is not required")
        _require_optional_non_negative_integer(
            self.requested_max_items,
            "requested_max_items",
        )


@dataclass(frozen=True, slots=True)
class EvidenceExpansionProposal:
    next_round_number: int
    search_goal: str
    scope: Mapping[str, object]
    source_policy: Mapping[str, object]
    filters: Mapping[str, object]
    required_authority: Mapping[str, object] | None
    max_items: int
    reason_codes: tuple[str, ...]
    security_signal_codes: tuple[EvidenceSignalCode, ...]

    def __post_init__(self) -> None:
        _require_positive_integer(self.next_round_number, "next_round_number")
        require_non_empty(self.search_goal, "search_goal")
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
        _require_optional_non_negative_integer(self.max_items, "max_items")
        _validate_string_tuple(
            self.reason_codes,
            "reason_codes",
            allow_empty=False,
        )
        _validate_security_codes(self.security_signal_codes)


@dataclass(frozen=True, slots=True)
class EvidenceExpansionDecision:
    action: EvidenceExpansionAction
    current_round: int
    proposal: EvidenceExpansionProposal | None
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.action, EvidenceExpansionAction):
            raise TypeError("action must be an EvidenceExpansionAction")
        _require_positive_integer(self.current_round, "current_round")
        if self.action is EvidenceExpansionAction.PROPOSE_NEXT_ROUND:
            if type(self.proposal) is not EvidenceExpansionProposal:
                raise ValueError("PROPOSE_NEXT_ROUND requires a proposal")
        elif self.proposal is not None:
            raise ValueError("only PROPOSE_NEXT_ROUND may contain a proposal")
        _validate_string_tuple(
            self.reason_codes,
            "reason_codes",
            allow_empty=False,
        )


def _require_positive_integer(value: int, field_name: str) -> None:
    if type(value) is not int:
        raise TypeError(f"{field_name} must be an integer")
    if value <= 0:
        raise ValueError(f"{field_name} must be > 0")


def _require_optional_non_negative_integer(
    value: int | None,
    field_name: str,
) -> None:
    if value is None:
        return
    if type(value) is not int:
        raise TypeError(f"{field_name} must be an integer")
    if value < 0:
        raise ValueError(f"{field_name} must be >= 0")


def _validate_string_tuple(
    values: tuple[str, ...],
    field_name: str,
    *,
    allow_empty: bool = True,
) -> None:
    if not isinstance(values, tuple):
        raise TypeError(f"{field_name} must be a tuple")
    if not allow_empty and not values:
        raise ValueError(f"{field_name} must not be empty")
    for value in values:
        require_non_empty(value, f"{field_name} item")
    if len(values) != len(set(values)):
        raise ValueError(f"{field_name} must be unique")


def _validate_identity_keys(keys: tuple[tuple[str, ...], ...]) -> None:
    if not isinstance(keys, tuple):
        raise TypeError("retrieval_identity_keys must be a tuple")
    for key in keys:
        _validate_string_tuple(
            key,
            "retrieval identity key",
            allow_empty=False,
        )
    if len(keys) != len(set(keys)):
        raise ValueError("retrieval_identity_keys must be unique")


def _validate_security_codes(
    codes: tuple[EvidenceSignalCode, ...],
) -> None:
    if not isinstance(codes, tuple) or any(
        type(code) not in {EvidenceSecuritySignalCode, ContentThreatSignalCode}
        for code in codes
    ):
        raise TypeError("security_signal_codes must contain signal codes")
    if len(codes) != len(set(codes)):
        raise ValueError("security_signal_codes must be unique")


def _stable_unique_security_codes(
    codes: tuple[EvidenceSignalCode, ...],
) -> tuple[EvidenceSignalCode, ...]:
    unique: list[EvidenceSignalCode] = []
    for code in codes:
        if code not in unique:
            unique.append(code)
    return tuple(unique)


def _raise_expansion_error(
    code: EvidenceExpansionErrorCode,
    message: str,
) -> None:
    raise EvidenceExpansionError(code, message)


BASELINE_EVIDENCE_EXPANSION_POLICY = EvidenceExpansionPolicy(
    max_rounds=BASELINE_AGENT_RUNTIME_POLICY.max_evidence_rounds,
    max_items_per_set=12,
)
