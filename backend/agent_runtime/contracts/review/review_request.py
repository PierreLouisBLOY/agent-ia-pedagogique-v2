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
from backend.agent_runtime.contracts.policy import BudgetSpec
from backend.agent_runtime.contracts.review.vocabulary import ReviewDimension


@dataclass(frozen=True, slots=True)
class ReviewRequest:
    """Independent review request that never mutates its production target."""

    meta: ContractMeta[InvocationStatus]
    target_production_ref: ContractRef
    review_dimensions: tuple[ReviewDimension, ...]
    criteria: Mapping[str, object] = field(default_factory=dict)
    evidence_refs: tuple[ContractRef, ...] = ()
    severity_policy: Mapping[str, object] = field(default_factory=dict)
    context_slice: Mapping[str, object] = field(default_factory=dict)
    independence_requirements: Mapping[str, object] = field(default_factory=dict)
    review_budget: BudgetSpec | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.meta, ContractMeta):
            raise TypeError("meta must be a ContractMeta")
        if not isinstance(self.meta.status, InvocationStatus):
            raise TypeError("meta.status must be an InvocationStatus")
        require_contract_ref(self.target_production_ref, "target_production_ref")
        dimensions = tuple(self.review_dimensions)
        if not dimensions:
            raise ValueError("review_dimensions must not be empty")
        if any(not isinstance(item, ReviewDimension) for item in dimensions):
            raise TypeError("review_dimensions must contain ReviewDimension values")
        if len(dimensions) != len(set(dimensions)):
            raise ValueError("review_dimensions must be unique")
        evidence_refs = tuple(self.evidence_refs)
        for evidence_ref in evidence_refs:
            require_contract_ref(evidence_ref, "evidence_ref")
        if self.review_budget is not None and not isinstance(self.review_budget, BudgetSpec):
            raise TypeError("review_budget must be a BudgetSpec")
        object.__setattr__(self, "review_dimensions", dimensions)
        object.__setattr__(self, "criteria", freeze_agent_safe_mapping(self.criteria))
        object.__setattr__(self, "evidence_refs", evidence_refs)
        object.__setattr__(
            self,
            "severity_policy",
            freeze_agent_safe_mapping(self.severity_policy),
        )
        object.__setattr__(
            self, "context_slice", freeze_agent_safe_mapping(self.context_slice)
        )
        object.__setattr__(
            self,
            "independence_requirements",
            freeze_agent_safe_mapping(self.independence_requirements),
        )
