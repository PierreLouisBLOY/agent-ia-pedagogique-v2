from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from backend.agent_runtime.contracts.common import (
    ContractRef,
    freeze_agent_safe_mapping,
    require_contract_ref,
)
from backend.agent_runtime.contracts.policy import BudgetSpec
from backend.agent_runtime.contracts.review import ReviewDimension
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel._strings import require_non_empty
from backend.shared_kernel.references import ObjectVersionRef


class ReviewOperation(StrEnum):
    SEMANTIC_REVIEW = "SEMANTIC_REVIEW"
    ASSESS_FINDINGS = "ASSESS_FINDINGS"


@dataclass(frozen=True, slots=True)
class ReviewPortRequest:
    """Caller-resolved provider-neutral input for one technical review call."""

    source_step_id: str
    operation: ReviewOperation
    capability_id: CapabilityId
    target_production_ref: ObjectVersionRef
    review_dimensions: tuple[ReviewDimension, ...]
    target_content: str | None = None
    target_payload: Mapping[str, object] = field(default_factory=dict)
    criteria: Mapping[str, object] = field(default_factory=dict)
    evidence_refs: tuple[ContractRef, ...] = ()
    coverage_context: Mapping[str, object] = field(default_factory=dict)
    resolved_inputs: Mapping[str, object] = field(default_factory=dict)
    output_contract: Mapping[str, object] = field(default_factory=dict)
    review_budget: BudgetSpec | None = None

    def __post_init__(self) -> None:
        require_non_empty(self.source_step_id, "source_step_id")
        if type(self.operation) is not ReviewOperation:
            raise TypeError("operation must be a ReviewOperation")
        if type(self.capability_id) is not CapabilityId:
            raise TypeError("capability_id must be a CapabilityId")
        if type(self.target_production_ref) is not ObjectVersionRef:
            raise TypeError("target_production_ref must be an ObjectVersionRef")
        dimensions = _validated_dimensions(self.review_dimensions)
        if self.target_content is not None:
            require_non_empty(self.target_content, "target_content")
        target_payload = freeze_agent_safe_mapping(self.target_payload)
        if self.target_content is None and not target_payload:
            raise ValueError("target_content or target_payload is required")
        evidence_refs = _validated_refs(self.evidence_refs, "evidence_refs")
        if self.review_budget is not None and type(self.review_budget) is not BudgetSpec:
            raise TypeError("review_budget must be a BudgetSpec")

        output_contract = freeze_agent_safe_mapping(self.output_contract)
        _reject_authority_keys(output_contract, "output_contract")
        object.__setattr__(self, "review_dimensions", dimensions)
        object.__setattr__(self, "target_payload", target_payload)
        object.__setattr__(self, "criteria", freeze_agent_safe_mapping(self.criteria))
        object.__setattr__(self, "evidence_refs", evidence_refs)
        object.__setattr__(
            self,
            "coverage_context",
            freeze_agent_safe_mapping(self.coverage_context),
        )
        object.__setattr__(
            self,
            "resolved_inputs",
            freeze_agent_safe_mapping(self.resolved_inputs),
        )
        object.__setattr__(self, "output_contract", output_contract)


class ReviewPortResultStatus(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    PARTIAL = "PARTIAL"
    REFUSED = "REFUSED"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class ReviewPortResult:
    """Non-canonical technical output awaiting coordinator revalidation."""

    source_step_id: str
    operation: ReviewOperation
    status: ReviewPortResultStatus
    structured_payload: Mapping[str, object] = field(default_factory=dict)
    technical_findings: tuple[Mapping[str, object], ...] = ()
    evidence_refs_used: tuple[ContractRef, ...] = ()
    limitations: tuple[Mapping[str, object], ...] = ()
    warnings: tuple[Mapping[str, object], ...] = ()
    uncertainties: tuple[Mapping[str, object], ...] = ()
    execution_metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty(self.source_step_id, "source_step_id")
        if type(self.operation) is not ReviewOperation:
            raise TypeError("operation must be a ReviewOperation")
        if type(self.status) is not ReviewPortResultStatus:
            raise TypeError("status must be a ReviewPortResultStatus")

        structured_payload = _frozen_authority_free_mapping(
            self.structured_payload,
            "structured_payload",
        )
        technical_findings = _frozen_authority_free_mapping_tuple(
            self.technical_findings,
            "technical_findings",
        )
        evidence_refs_used = _validated_refs(
            self.evidence_refs_used,
            "evidence_refs_used",
        )
        limitations = _frozen_authority_free_mapping_tuple(
            self.limitations,
            "limitations",
        )
        warnings = _frozen_authority_free_mapping_tuple(self.warnings, "warnings")
        uncertainties = _frozen_authority_free_mapping_tuple(
            self.uncertainties,
            "uncertainties",
        )
        execution_metadata = _frozen_authority_free_mapping(
            self.execution_metadata,
            "execution_metadata",
        )

        has_output = bool(structured_payload) or bool(technical_findings)
        has_limitation = bool(limitations) or bool(warnings) or bool(uncertainties)
        if self.status is ReviewPortResultStatus.SUCCEEDED and not has_output:
            raise ValueError("SUCCEEDED requires structured technical output")
        if self.status is ReviewPortResultStatus.PARTIAL:
            if not has_output:
                raise ValueError("PARTIAL requires structured technical output")
            if not has_limitation:
                raise ValueError("PARTIAL requires a limitation, warning or uncertainty")
        if self.status in {
            ReviewPortResultStatus.REFUSED,
            ReviewPortResultStatus.FAILED,
        }:
            if has_output:
                raise ValueError(f"{self.status.value} cannot contain technical output")
            if not has_limitation:
                raise ValueError(
                    f"{self.status.value} requires a limitation, warning or uncertainty"
                )

        object.__setattr__(self, "structured_payload", structured_payload)
        object.__setattr__(self, "technical_findings", technical_findings)
        object.__setattr__(self, "evidence_refs_used", evidence_refs_used)
        object.__setattr__(self, "limitations", limitations)
        object.__setattr__(self, "warnings", warnings)
        object.__setattr__(self, "uncertainties", uncertainties)
        object.__setattr__(self, "execution_metadata", execution_metadata)


class ReviewPortErrorCode(StrEnum):
    UNAVAILABLE = "UNAVAILABLE"
    INVALID_RESPONSE = "INVALID_RESPONSE"
    REQUEST_REJECTED = "REQUEST_REJECTED"


_SAFE_ERROR_REASON: Mapping[ReviewPortErrorCode, str] = {
    ReviewPortErrorCode.UNAVAILABLE: "Review mechanism unavailable",
    ReviewPortErrorCode.INVALID_RESPONSE: "Review response did not match the technical contract",
    ReviewPortErrorCode.REQUEST_REJECTED: "Review request was rejected by the technical boundary",
}


class ReviewPortError(RuntimeError):
    """Closed provider-neutral failure exposing only a fixed agent-safe reason."""

    code: ReviewPortErrorCode
    safe_reason: str

    def __init__(self, code: ReviewPortErrorCode) -> None:
        if type(code) is not ReviewPortErrorCode:
            raise TypeError("code must be a ReviewPortErrorCode")
        self.code = code
        self.safe_reason = _SAFE_ERROR_REASON[code]
        super().__init__(self.safe_reason)


_FORBIDDEN_AUTHORITY_KEYS = frozenset(
    {
        "approved",
        "canonical",
        "gate_approved",
        "permission_granted",
        "promoted",
        "promotion_allowed",
        "review_passed",
        "safe",
        "trusted",
        "validated",
        "validator_passed",
    }
)


def _validated_dimensions(
    values: tuple[ReviewDimension, ...],
) -> tuple[ReviewDimension, ...]:
    if not isinstance(values, tuple):
        raise TypeError("review_dimensions must be a tuple")
    if not values:
        raise ValueError("review_dimensions must not be empty")
    if any(type(value) is not ReviewDimension for value in values):
        raise TypeError("review_dimensions must contain ReviewDimension values")
    if len(values) != len(set(values)):
        raise ValueError("review_dimensions must contain unique values")
    return values


def _validated_refs(
    values: tuple[ContractRef, ...],
    field_name: str,
) -> tuple[ContractRef, ...]:
    if not isinstance(values, tuple):
        raise TypeError(f"{field_name} must be a tuple")
    for value in values:
        require_contract_ref(value, f"{field_name} item")
    if len(values) != len(set(values)):
        raise ValueError(f"{field_name} must contain unique references")
    return values


def _frozen_authority_free_mapping(
    value: Mapping[str, object],
    field_name: str,
) -> Mapping[str, object]:
    frozen = freeze_agent_safe_mapping(value)
    _reject_authority_keys(frozen, field_name)
    return frozen


def _frozen_authority_free_mapping_tuple(
    values: tuple[Mapping[str, object], ...],
    field_name: str,
) -> tuple[Mapping[str, object], ...]:
    if not isinstance(values, tuple):
        raise TypeError(f"{field_name} must be a tuple")
    return tuple(
        _frozen_authority_free_mapping(value, f"{field_name} item")
        for value in values
    )


def _reject_authority_keys(value: object, field_name: str) -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if _normalized_key(key) in _FORBIDDEN_AUTHORITY_KEYS:
                raise ValueError(f"{field_name} contains forbidden authority vocabulary")
            _reject_authority_keys(nested, field_name)
    elif isinstance(value, tuple):
        for nested in value:
            _reject_authority_keys(nested, field_name)


def _normalized_key(key: str) -> str:
    snake_case = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", key)
    return re.sub(r"[^a-z0-9]+", "_", snake_case.casefold()).strip("_")
