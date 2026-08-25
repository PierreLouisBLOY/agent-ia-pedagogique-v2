from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from backend.agent_runtime.contracts.common import (
    ContractRef,
    freeze_agent_safe_mapping,
    require_contract_ref,
)
from backend.shared_kernel._strings import require_non_empty


class GenerationOperation(StrEnum):
    GENERATE = "GENERATE"
    TRANSFORM = "TRANSFORM"
    CORRECT = "CORRECT"


@dataclass(frozen=True, slots=True)
class GenerationPortRequest:
    """Prepared provider-neutral input for one technical generation call."""

    operation: GenerationOperation
    source_step_id: str
    production_kind: str
    objective: str
    output_format: str
    pedagogical_context: Mapping[str, object] = field(default_factory=dict)
    resolved_inputs: Mapping[str, object] = field(default_factory=dict)
    constraints: Mapping[str, object] = field(default_factory=dict)
    evidence_refs: tuple[ContractRef, ...] = ()
    target_ref: ContractRef | None = None
    expected_sections: tuple[str, ...] = ()
    output_contract: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if type(self.operation) is not GenerationOperation:
            raise TypeError("operation must be a GenerationOperation")
        require_non_empty(self.source_step_id, "source_step_id")
        require_non_empty(self.production_kind, "production_kind")
        require_non_empty(self.objective, "objective")
        require_non_empty(self.output_format, "output_format")
        evidence_refs = _validated_refs(self.evidence_refs, "evidence_refs")
        if self.target_ref is not None:
            require_contract_ref(self.target_ref, "target_ref")
        expected_sections = _validated_string_tuple(
            self.expected_sections,
            "expected_sections",
        )
        object.__setattr__(
            self,
            "pedagogical_context",
            freeze_agent_safe_mapping(self.pedagogical_context),
        )
        object.__setattr__(
            self,
            "resolved_inputs",
            freeze_agent_safe_mapping(self.resolved_inputs),
        )
        object.__setattr__(
            self,
            "constraints",
            freeze_agent_safe_mapping(self.constraints),
        )
        object.__setattr__(self, "evidence_refs", evidence_refs)
        object.__setattr__(self, "expected_sections", expected_sections)
        object.__setattr__(
            self,
            "output_contract",
            freeze_agent_safe_mapping(self.output_contract),
        )


class GenerationPortResultStatus(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    PARTIAL = "PARTIAL"
    REFUSED = "REFUSED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


@dataclass(frozen=True, slots=True)
class GenerationPortResult:
    """Technical generation output, distinct from an agent ProductionCandidate."""

    source_step_id: str
    operation: GenerationOperation
    status: GenerationPortResultStatus
    content: str | None = None
    structured_payload: Mapping[str, object] = field(default_factory=dict)
    evidence_refs_used: tuple[ContractRef, ...] = ()
    warnings: tuple[Mapping[str, object], ...] = ()
    uncertainties: tuple[Mapping[str, object], ...] = ()
    execution_metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty(self.source_step_id, "source_step_id")
        if type(self.operation) is not GenerationOperation:
            raise TypeError("operation must be a GenerationOperation")
        if type(self.status) is not GenerationPortResultStatus:
            raise TypeError("status must be a GenerationPortResultStatus")
        if self.content is not None:
            require_non_empty(self.content, "content")
        structured_payload = freeze_agent_safe_mapping(self.structured_payload)
        evidence_refs_used = _validated_refs(
            self.evidence_refs_used,
            "evidence_refs_used",
        )
        warnings = _validated_mapping_tuple(self.warnings, "warnings")
        uncertainties = _validated_mapping_tuple(
            self.uncertainties,
            "uncertainties",
        )
        execution_metadata = freeze_agent_safe_mapping(self.execution_metadata)

        has_output = self.content is not None or bool(structured_payload)
        has_limitation = bool(warnings) or bool(uncertainties)
        if self.status is GenerationPortResultStatus.SUCCEEDED and not has_output:
            raise ValueError("SUCCEEDED requires content or structured_payload")
        if self.status is GenerationPortResultStatus.PARTIAL:
            if not has_output:
                raise ValueError("PARTIAL requires content or structured_payload")
            if not has_limitation:
                raise ValueError("PARTIAL requires a warning or uncertainty")
        if self.status in {
            GenerationPortResultStatus.REFUSED,
            GenerationPortResultStatus.INSUFFICIENT_EVIDENCE,
        }:
            if has_output:
                raise ValueError(f"{self.status.value} cannot contain generated output")
            if not has_limitation:
                raise ValueError(
                    f"{self.status.value} requires a warning or uncertainty"
                )

        object.__setattr__(self, "structured_payload", structured_payload)
        object.__setattr__(self, "evidence_refs_used", evidence_refs_used)
        object.__setattr__(self, "warnings", warnings)
        object.__setattr__(self, "uncertainties", uncertainties)
        object.__setattr__(self, "execution_metadata", execution_metadata)


class GenerationPortErrorCode(StrEnum):
    UNAVAILABLE = "UNAVAILABLE"
    INVALID_RESPONSE = "INVALID_RESPONSE"


class GenerationPortError(RuntimeError):
    code: GenerationPortErrorCode
    safe_reason: str

    def __init__(
        self,
        code: GenerationPortErrorCode,
        safe_reason: str,
    ) -> None:
        if type(code) is not GenerationPortErrorCode:
            raise TypeError("code must be a GenerationPortErrorCode")
        require_non_empty(safe_reason, "safe_reason")
        self.code = code
        self.safe_reason = safe_reason
        super().__init__(safe_reason)


def _validated_refs(
    values: tuple[ContractRef, ...],
    field_name: str,
) -> tuple[ContractRef, ...]:
    if not isinstance(values, tuple):
        raise TypeError(f"{field_name} must be a tuple")
    for value in values:
        require_contract_ref(value, f"{field_name} item")
    return values


def _validated_string_tuple(
    values: tuple[str, ...],
    field_name: str,
) -> tuple[str, ...]:
    if not isinstance(values, tuple):
        raise TypeError(f"{field_name} must be a tuple")
    for value in values:
        require_non_empty(value, f"{field_name} item")
    if len(values) != len(set(values)):
        raise ValueError(f"{field_name} must contain unique values")
    return values


def _validated_mapping_tuple(
    values: tuple[Mapping[str, object], ...],
    field_name: str,
) -> tuple[Mapping[str, object], ...]:
    if not isinstance(values, tuple):
        raise TypeError(f"{field_name} must be a tuple")
    return tuple(freeze_agent_safe_mapping(value) for value in values)
