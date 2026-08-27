from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import cast

from backend.agent_runtime.agents.generation.generation_coordination_model import (
    GenerationCoordinationError,
    PreparedGenerationCall,
    _validate_prepared_call,
)
from backend.agent_runtime.agents.generation.generation_coordinator import (
    _validate_generation_result,
)
from backend.agent_runtime.agents.generation.generation_correction_model import (
    CorrectionMaterializationError,
    PreparedCorrectionCall,
    _validate_correction_technical_result,
    _validate_prepared_correction_call,
)
from backend.agent_runtime.agents.generation.generation_model import (
    GenerationPortError,
    GenerationPortResult,
)
from backend.agent_runtime.contracts.common import ContractRef, require_contract_ref
from backend.agent_runtime.contracts.security import (
    ContentThreatSignal,
    ContentThreatSignalCode,
)
from backend.shared_kernel._strings import require_non_empty


class GenerationClaimClass(StrEnum):
    DETERMINISTIC = "DETERMINISTIC"
    GROUNDED = "GROUNDED"
    SYNTHESIZED = "SYNTHESIZED"
    GENERATED_PEDAGOGICAL = "GENERATED_PEDAGOGICAL"
    UNKNOWN = "UNKNOWN"
    CONFLICTED = "CONFLICTED"


@dataclass(frozen=True, slots=True)
class GenerationClaimAttribution:
    claim_id: str
    claim_class: GenerationClaimClass
    evidence_refs: tuple[ContractRef, ...] = ()

    def __post_init__(self) -> None:
        require_non_empty(self.claim_id, "claim_id")
        if type(self.claim_class) is not GenerationClaimClass:
            raise TypeError("claim_class must be a GenerationClaimClass")
        if not isinstance(self.evidence_refs, tuple):
            raise TypeError("evidence_refs must be a tuple")
        for reference in self.evidence_refs:
            require_contract_ref(reference, "evidence_refs item")
        if len(self.evidence_refs) != len(set(self.evidence_refs)):
            raise ValueError("evidence_refs must contain unique references")
        if self.claim_class in {
            GenerationClaimClass.GROUNDED,
            GenerationClaimClass.SYNTHESIZED,
        } and not self.evidence_refs:
            raise ValueError(f"{self.claim_class.value} requires an evidence reference")
        if self.claim_class in {
            GenerationClaimClass.GENERATED_PEDAGOGICAL,
            GenerationClaimClass.UNKNOWN,
        } and self.evidence_refs:
            raise ValueError(f"{self.claim_class.value} forbids evidence references")
        if (
            self.claim_class is GenerationClaimClass.CONFLICTED
            and len(self.evidence_refs) < 2
        ):
            raise ValueError("CONFLICTED requires at least two evidence references")


@dataclass(frozen=True, slots=True)
class GenerationGuardPolicy:
    grounding_required: bool = False
    require_structured_payload: bool = False
    required_payload_keys: tuple[str, ...] = ()
    allowed_payload_keys: tuple[str, ...] | None = None
    section_container_key: str | None = None

    def __post_init__(self) -> None:
        if type(self.grounding_required) is not bool:
            raise TypeError("grounding_required must be a bool")
        if type(self.require_structured_payload) is not bool:
            raise TypeError("require_structured_payload must be a bool")
        _validate_string_tuple(self.required_payload_keys, "required_payload_keys")
        if self.allowed_payload_keys is not None:
            _validate_string_tuple(self.allowed_payload_keys, "allowed_payload_keys")
            if not set(self.required_payload_keys).issubset(self.allowed_payload_keys):
                raise ValueError(
                    "required_payload_keys must be a subset of allowed_payload_keys"
                )
        if self.section_container_key is not None:
            require_non_empty(self.section_container_key, "section_container_key")


GenerationSecuritySignalCode = ContentThreatSignalCode
GenerationSecuritySignal = ContentThreatSignal


class GenerationGuardIssueCode(StrEnum):
    PREPARED_LINEAGE_MISMATCH = "PREPARED_LINEAGE_MISMATCH"
    TECHNICAL_RESULT_MISMATCH = "TECHNICAL_RESULT_MISMATCH"
    GROUNDING_REQUIRED_NO_EVIDENCE = "GROUNDING_REQUIRED_NO_EVIDENCE"
    CLAIM_EVIDENCE_OUT_OF_SCOPE = "CLAIM_EVIDENCE_OUT_OF_SCOPE"
    DUPLICATE_CLAIM_ID = "DUPLICATE_CLAIM_ID"
    STRUCTURED_PAYLOAD_REQUIRED = "STRUCTURED_PAYLOAD_REQUIRED"
    REQUIRED_PAYLOAD_KEY_MISSING = "REQUIRED_PAYLOAD_KEY_MISSING"
    UNEXPECTED_PAYLOAD_KEY = "UNEXPECTED_PAYLOAD_KEY"
    EXPECTED_SECTION_CONTAINER_MISSING = "EXPECTED_SECTION_CONTAINER_MISSING"
    EXPECTED_SECTION_MISSING = "EXPECTED_SECTION_MISSING"


class GenerationGuardDisposition(StrEnum):
    ALLOW = "ALLOW"
    ALLOW_WITH_WARNINGS = "ALLOW_WITH_WARNINGS"
    REPAIR_REQUIRED = "REPAIR_REQUIRED"
    ABSTAIN = "ABSTAIN"
    REJECT = "REJECT"


class GenerationRepairKind(StrEnum):
    STRUCTURE_REPAIR = "STRUCTURE_REPAIR"
    REDUCE_SCOPE = "REDUCE_SCOPE"
    REQUEST_EVIDENCE = "REQUEST_EVIDENCE"


@dataclass(frozen=True, slots=True)
class GenerationRepairProposal:
    kind: GenerationRepairKind
    issue_codes: tuple[GenerationGuardIssueCode, ...]

    def __post_init__(self) -> None:
        if type(self.kind) is not GenerationRepairKind:
            raise TypeError("kind must be a GenerationRepairKind")
        _validate_issue_codes(self.issue_codes, allow_empty=False)


class GenerationGuardError(ValueError):
    issue_code: GenerationGuardIssueCode
    safe_reason: str

    def __init__(
        self,
        issue_code: GenerationGuardIssueCode,
        safe_reason: str,
    ) -> None:
        if type(issue_code) is not GenerationGuardIssueCode:
            raise TypeError("issue_code must be a GenerationGuardIssueCode")
        require_non_empty(safe_reason, "safe_reason")
        self.issue_code = issue_code
        self.safe_reason = safe_reason
        super().__init__(safe_reason)


type PreparedSubject = PreparedGenerationCall | PreparedCorrectionCall


@dataclass(frozen=True, slots=True)
class GenerationGuardRequest:
    prepared: PreparedSubject
    technical_result: GenerationPortResult
    policy: GenerationGuardPolicy
    claim_attributions: tuple[GenerationClaimAttribution, ...] = ()

    def __post_init__(self) -> None:
        validate_generation_guard_request(self)


@dataclass(frozen=True, slots=True)
class GenerationGuardAssessment:
    request: GenerationGuardRequest
    disposition: GenerationGuardDisposition
    issue_codes: tuple[GenerationGuardIssueCode, ...]
    security_signals: tuple[ContentThreatSignal, ...]
    repair_proposal: GenerationRepairProposal | None = None

    def __post_init__(self) -> None:
        if type(self.request) is not GenerationGuardRequest:
            raise TypeError("request must be a GenerationGuardRequest")
        if type(self.disposition) is not GenerationGuardDisposition:
            raise TypeError("disposition must be a GenerationGuardDisposition")
        _validate_issue_codes(self.issue_codes, allow_empty=True)
        if not isinstance(self.security_signals, tuple):
            raise TypeError("security_signals must be a tuple")
        if any(
            type(signal) is not ContentThreatSignal
            for signal in self.security_signals
        ):
            raise TypeError("security_signals must contain ContentThreatSignal")
        if len(self.security_signals) != len(set(self.security_signals)):
            raise ValueError("security_signals must contain unique signals")
        if self.disposition is GenerationGuardDisposition.REPAIR_REQUIRED:
            if type(self.repair_proposal) is not GenerationRepairProposal:
                raise ValueError("REPAIR_REQUIRED requires a repair proposal")
        elif self.repair_proposal is not None:
            raise ValueError("repair proposal is reserved for REPAIR_REQUIRED")


def validate_generation_guard_request(request: GenerationGuardRequest) -> None:
    if type(request.prepared) not in {PreparedGenerationCall, PreparedCorrectionCall}:
        raise TypeError(
            "prepared must be a PreparedGenerationCall or PreparedCorrectionCall"
        )
    if type(request.technical_result) is not GenerationPortResult:
        raise TypeError("technical_result must be a GenerationPortResult")
    if type(request.policy) is not GenerationGuardPolicy:
        raise TypeError("policy must be a GenerationGuardPolicy")
    if not isinstance(request.claim_attributions, tuple):
        raise TypeError("claim_attributions must be a tuple")
    if any(
        type(attribution) is not GenerationClaimAttribution
        for attribution in request.claim_attributions
    ):
        raise TypeError(
            "claim_attributions must contain GenerationClaimAttribution values"
        )
    try:
        if type(request.prepared) is PreparedGenerationCall:
            _validate_prepared_call(request.prepared)
        else:
            _validate_prepared_correction_call(
                cast(PreparedCorrectionCall, request.prepared)
            )
    except (GenerationCoordinationError, CorrectionMaterializationError, TypeError) as error:
        raise GenerationGuardError(
            GenerationGuardIssueCode.PREPARED_LINEAGE_MISMATCH,
            "prepared generation lineage is invalid",
        ) from error
    try:
        if type(request.prepared) is PreparedGenerationCall:
            _validate_generation_result(request.prepared, request.technical_result)
        else:
            _validate_correction_technical_result(
                cast(PreparedCorrectionCall, request.prepared),
                request.technical_result,
            )
    except (GenerationCoordinationError, GenerationPortError, TypeError) as error:
        raise GenerationGuardError(
            GenerationGuardIssueCode.TECHNICAL_RESULT_MISMATCH,
            "technical result does not match the prepared generation call",
        ) from error


def _validate_string_tuple(values: tuple[str, ...], field_name: str) -> None:
    if not isinstance(values, tuple):
        raise TypeError(f"{field_name} must be a tuple")
    for value in values:
        require_non_empty(value, f"{field_name} item")
    if len(values) != len(set(values)):
        raise ValueError(f"{field_name} must contain unique values")


def _validate_issue_codes(
    values: tuple[GenerationGuardIssueCode, ...],
    *,
    allow_empty: bool,
) -> None:
    if not isinstance(values, tuple):
        raise TypeError("issue_codes must be a tuple")
    if not allow_empty and not values:
        raise ValueError("issue_codes must not be empty")
    if any(type(value) is not GenerationGuardIssueCode for value in values):
        raise TypeError("issue_codes must contain GenerationGuardIssueCode values")
    if len(values) != len(set(values)):
        raise ValueError("issue_codes must contain unique values")


BASELINE_GENERATION_GUARD_POLICY = GenerationGuardPolicy()
