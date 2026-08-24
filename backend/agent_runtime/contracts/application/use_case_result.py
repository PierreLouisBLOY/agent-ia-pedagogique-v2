from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from backend.agent_runtime.contracts.common import (
    ContractMeta,
    ContractRef,
    freeze_agent_safe_mapping,
    require_contract_ref,
)
from backend.agent_runtime.contracts.errors import ErrorEnvelope
from backend.core_contracts.outcome import ApplicationOutcome, OutcomeStatus
from backend.shared_kernel._strings import require_non_empty


@dataclass(frozen=True, slots=True)
class UseCaseResult[TData, TValidationResult]:
    """Agent-runtime view of an ApplicationOutcome without masking domain errors."""

    meta: ContractMeta[OutcomeStatus]
    use_case_id: str
    outcome: ApplicationOutcome[TData, TValidationResult]
    result_ref: ContractRef | None = None
    domain_events: tuple[ContractRef | Mapping[str, object], ...] = ()
    error: ErrorEnvelope | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.meta, ContractMeta):
            raise TypeError("meta must be a ContractMeta")
        if not isinstance(self.meta.status, OutcomeStatus):
            raise TypeError("meta.status must be an OutcomeStatus")
        require_non_empty(self.use_case_id, "use_case_id")
        if not isinstance(self.outcome, ApplicationOutcome):
            raise TypeError("outcome must be an ApplicationOutcome")
        if self.meta.status is not self.outcome.outcome_status:
            raise ValueError("meta.status must match outcome.outcome_status")
        if self.meta.correlation_id != self.outcome.correlation_id:
            raise ValueError("outcome correlation must match meta correlation")
        if self.result_ref is not None:
            require_contract_ref(self.result_ref, "result_ref")
        domain_events: list[ContractRef | Mapping[str, object]] = []
        for event in self.domain_events:
            if isinstance(event, Mapping):
                domain_events.append(freeze_agent_safe_mapping(event))
            else:
                require_contract_ref(event, "domain_event")
                domain_events.append(event)
        if self.error is not None:
            if not isinstance(self.error, ErrorEnvelope):
                raise TypeError("error must be an ErrorEnvelope")
            if self.error.step_id != self.meta.step_id:
                raise ValueError("error.step_id must match meta.step_id")
        object.__setattr__(self, "domain_events", tuple(domain_events))
