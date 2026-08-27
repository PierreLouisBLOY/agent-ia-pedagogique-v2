from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from backend.agent_runtime.contracts.common import (
    ContractRef,
    freeze_agent_safe_mapping,
    require_contract_ref,
)
from backend.agent_runtime.contracts.security import (
    ContentOrigin,
    ContentRole,
    ContentTrustClass,
    ContentTrustLabel,
)
from backend.shared_kernel._strings import require_non_empty
from backend.shared_kernel.references import ObjectVersionRef


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
    target_version_ref: ObjectVersionRef | None = None
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
        if self.target_version_ref is not None and type(self.target_version_ref) is not ObjectVersionRef:
            raise TypeError("target_version_ref must be an ObjectVersionRef")
        if self.operation is GenerationOperation.CORRECT:
            if self.target_ref is not None:
                raise ValueError("CORRECT forbids target_ref")
            if self.target_version_ref is None:
                raise ValueError("CORRECT requires target_version_ref")
        elif self.target_version_ref is not None:
            raise ValueError("target_version_ref is reserved for CORRECT")
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
    operation_details: Mapping[str, object] = field(default_factory=dict)
    content_label: ContentTrustLabel | None = None

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
        operation_details = freeze_agent_safe_mapping(self.operation_details)

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

        content_label = self.content_label
        if has_output:
            expected_origin = (
                ContentOrigin.CORRECTION_OUTPUT
                if self.operation is GenerationOperation.CORRECT
                else ContentOrigin.AGENT_OUTPUT
            )
            expected_ref = f"generation-output:{self.source_step_id}"
            if content_label is None:
                content_label = ContentTrustLabel(
                    origin=expected_origin,
                    role=ContentRole.RESULT,
                    trust_class=ContentTrustClass.UNTRUSTED,
                    source_ref=expected_ref,
                )
            if type(content_label) is not ContentTrustLabel:
                raise TypeError("content_label must be a ContentTrustLabel")
            if (
                content_label.origin is not expected_origin
                or content_label.role is not ContentRole.RESULT
                or content_label.source_ref != expected_ref
            ):
                raise ValueError("content_label must preserve generated output provenance")
        elif content_label is not None:
            raise ValueError("content_label requires generated output")

        object.__setattr__(self, "structured_payload", structured_payload)
        object.__setattr__(self, "evidence_refs_used", evidence_refs_used)
        object.__setattr__(self, "warnings", warnings)
        object.__setattr__(self, "uncertainties", uncertainties)
        object.__setattr__(self, "execution_metadata", execution_metadata)
        object.__setattr__(self, "operation_details", operation_details)
        object.__setattr__(self, "content_label", content_label)


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
