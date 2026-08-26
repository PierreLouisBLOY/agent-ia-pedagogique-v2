from __future__ import annotations

from collections.abc import Mapping

from backend.agent_runtime.agents.review.review_assessment_model import (
    _ASSESSMENT_PAYLOAD_FIELDS,
    CorrectionHandoffSignal,
    FindingsAssessmentRequest,
    ReviewAssessmentErrorCode,
    ReviewAssessmentSignal,
    _assessment_request_security,
    _blocking_finding_ids,
    _correction_finding_ids,
    _raise_assessment,
    _validate_findings_assessment_request,
    _validate_ref_tuple,
)
from backend.agent_runtime.agents.review.review_coordination_model import (
    PreparedReviewCall,
    ReviewPreparationRequest,
)
from backend.agent_runtime.agents.review.review_coordinator import ReviewCoordinator
from backend.agent_runtime.agents.review.review_model import (
    ReviewOperation,
    ReviewPortResult,
    ReviewPortResultStatus,
    _reject_authority_keys,
)
from backend.agent_runtime.agents.review.review_security import (
    finding_lineage_fingerprint,
    reject_activatable_review_metadata,
    require_security_output_allowed,
    target_snapshot_fingerprint,
)
from backend.agent_runtime.agents.review.review_security_model import (
    ReviewSecurityAssessment,
)
from backend.agent_runtime.contracts import AgentId, Finding, OverallAssessment
from backend.agent_runtime.contracts.common import (
    ContractRef,
    freeze_agent_safe_mapping,
)

_ASSESSMENTS_BY_VALUE = {item.value: item for item in OverallAssessment}


def execute_findings_assessment(
    *,
    coordinator: ReviewCoordinator,
    request: FindingsAssessmentRequest,
) -> tuple[ReviewAssessmentSignal, CorrectionHandoffSignal | None]:
    if not isinstance(coordinator, ReviewCoordinator):
        raise TypeError("coordinator must be a ReviewCoordinator")
    if type(request) is not FindingsAssessmentRequest:
        raise TypeError("request must be a FindingsAssessmentRequest")
    _validate_findings_assessment_request(request)
    security = _assessment_request_security(request)
    require_security_output_allowed(security, request.security_policy)
    preparation = ReviewPreparationRequest(
        capability_id=request.capability_id,
        request=request.source_request,
        target=request.target,
        resolved_inputs=_assessment_resolved_inputs(request),
        output_contract=request.output_contract,
    )
    prepared = coordinator.prepare(request=preparation)
    _validate_assessment_prepared(request, prepared)
    technical_result = coordinator.execute(prepared=prepared)
    signal = _assessment_signal(request, technical_result, security)
    handoff = _correction_handoff(request, signal)
    return signal, handoff


def _assessment_resolved_inputs(
    request: FindingsAssessmentRequest,
) -> Mapping[str, object]:
    source = request.source_result
    return freeze_agent_safe_mapping(
        {
            "source_review": {
                "review_ref": request.review_ref,
                "review_id": source.review_id,
                "target_production_ref": source.target_production_ref,
                "target_snapshot_fingerprint": target_snapshot_fingerprint(
                    request.target
                ),
                "findings": _findings_snapshot(source.findings),
                "overall_assessment": source.overall_assessment.value,
                "correction_required": source.correction_required,
                "coverage": tuple(item.value for item in source.coverage),
                "evidence_refs_used": source.evidence_refs_used,
                "confidence": source.confidence,
                "limitations": source.limitations,
                "warnings": source.warnings,
            },
            "additional_inputs": request.resolved_inputs,
        }
    )


def _findings_snapshot(findings: tuple[Finding, ...]) -> tuple[Mapping[str, object], ...]:
    return tuple(
        {
            "finding_id": finding.finding_id,
            "dimension": finding.dimension.value,
            "severity": finding.severity.value,
            "description": finding.description,
            "target_locator": finding.target_locator,
            "rationale": finding.rationale,
            "correction_required": finding.correction_required,
            "evidence_refs": finding.evidence_refs,
            "confidence": finding.confidence,
            "suggested_action": finding.suggested_action,
            "lineage_fingerprint": finding_lineage_fingerprint(finding),
        }
        for finding in findings
    )


def _validate_assessment_prepared(
    request: FindingsAssessmentRequest,
    prepared: PreparedReviewCall,
) -> None:
    technical = prepared.port_request
    if (
        prepared.capability_id != request.capability_id
        or technical.capability_id != request.capability_id
    ):
        _raise_assessment(ReviewAssessmentErrorCode.UNSUPPORTED_CAPABILITY)
    if technical.operation is not ReviewOperation.ASSESS_FINDINGS:
        _raise_assessment(ReviewAssessmentErrorCode.OPERATION_MISMATCH)
    if technical.source_step_id != request.source_request.meta.step_id:
        _raise_assessment(ReviewAssessmentErrorCode.SOURCE_STEP_MISMATCH)
    if technical.target_production_ref != request.source_result.target_production_ref:
        _raise_assessment(ReviewAssessmentErrorCode.TARGET_MISMATCH)
    if technical.resolved_inputs != _assessment_resolved_inputs(request):
        _raise_assessment(ReviewAssessmentErrorCode.SNAPSHOT_MISMATCH)
    if technical.output_contract != request.output_contract:
        _raise_assessment(ReviewAssessmentErrorCode.SNAPSHOT_MISMATCH)


def _assessment_signal(
    request: FindingsAssessmentRequest,
    technical: ReviewPortResult,
    security: ReviewSecurityAssessment,
) -> ReviewAssessmentSignal:
    if type(technical.status) is not ReviewPortResultStatus:
        _raise_assessment(ReviewAssessmentErrorCode.INVALID_TECHNICAL_PAYLOAD)
    if technical.status in {ReviewPortResultStatus.REFUSED, ReviewPortResultStatus.FAILED}:
        _raise_assessment(ReviewAssessmentErrorCode.NON_ASSESSABLE_STATUS)
    if technical.technical_findings != ():
        _raise_assessment(ReviewAssessmentErrorCode.TECHNICAL_FINDINGS_FORBIDDEN)
    payload = _revalidated_technical_mappings(technical)
    try:
        _validate_ref_tuple(technical.evidence_refs_used, "evidence_refs_used")
    except (TypeError, ValueError):
        _raise_assessment(ReviewAssessmentErrorCode.EVIDENCE_OUT_OF_SCOPE)
    if not set(technical.evidence_refs_used).issubset(
        request.source_result.evidence_refs_used
    ):
        _raise_assessment(ReviewAssessmentErrorCode.EVIDENCE_OUT_OF_SCOPE)

    if set(payload) != _ASSESSMENT_PAYLOAD_FIELDS:
        _raise_assessment(ReviewAssessmentErrorCode.INVALID_TECHNICAL_PAYLOAD)
    assessed_ids = _technical_ids(payload["assessed_finding_ids"])
    blocking_ids = _technical_ids(payload["blocking_finding_ids"])
    correction_ids = _technical_ids(payload["correction_finding_ids"])
    expected_assessed = tuple(item.finding_id for item in request.source_result.findings)
    expected_blocking = _blocking_finding_ids(request.source_result)
    expected_correction = _correction_finding_ids(request.source_result)
    if assessed_ids != expected_assessed:
        _raise_assessment(ReviewAssessmentErrorCode.ASSESSED_IDS_MISMATCH)
    if blocking_ids != expected_blocking:
        _raise_assessment(ReviewAssessmentErrorCode.BLOCKING_IDS_MISMATCH)
    if correction_ids != expected_correction:
        _raise_assessment(ReviewAssessmentErrorCode.CORRECTION_IDS_MISMATCH)

    raw_assessment = payload["overall_assessment"]
    if type(raw_assessment) is not str:
        _raise_assessment(ReviewAssessmentErrorCode.INVALID_ASSESSMENT)
    assessment = _ASSESSMENTS_BY_VALUE.get(raw_assessment)
    if assessment is None:
        _raise_assessment(ReviewAssessmentErrorCode.INVALID_ASSESSMENT)
    raw_correction_required = payload["correction_required"]
    if type(raw_correction_required) is not bool:
        _raise_assessment(ReviewAssessmentErrorCode.INVALID_TECHNICAL_PAYLOAD)
    if raw_correction_required != bool(expected_correction):
        _raise_assessment(ReviewAssessmentErrorCode.ASSESSMENT_INCOHERENT)
    if technical.status is ReviewPortResultStatus.PARTIAL and assessment is not OverallAssessment.INCOMPLETE:
        _raise_assessment(ReviewAssessmentErrorCode.ASSESSMENT_INCOHERENT)
    _validate_assessment_coherence(assessment, expected_blocking, expected_correction)
    confidence = payload["confidence"]
    if not isinstance(confidence, Mapping):
        _raise_assessment(ReviewAssessmentErrorCode.INVALID_TECHNICAL_PAYLOAD)

    limitations = (
        request.source_result.limitations
        + technical.limitations
        + security.limitations
    )
    warnings = request.source_result.warnings + technical.warnings + security.warnings
    return ReviewAssessmentSignal(
        review_ref=request.review_ref,
        review_id=request.source_result.review_id,
        target_production_ref=request.source_result.target_production_ref,
        assessed_finding_ids=expected_assessed,
        blocking_finding_ids=expected_blocking,
        correction_finding_ids=expected_correction,
        overall_assessment=assessment,
        correction_required=raw_correction_required,
        promotion_blocked_by_review=bool(expected_blocking),
        evidence_refs_used=technical.evidence_refs_used,
        confidence=confidence,
        limitations=limitations,
        warnings=warnings,
        technical_status=technical.status,
        target_snapshot_fingerprint=security.target_snapshot_fingerprint,
        finding_lineage_fingerprints=tuple(
            (finding.finding_id, finding_lineage_fingerprint(finding))
            for finding in request.source_result.findings
        ),
        security_signal_codes=tuple(signal.code for signal in security.signals),
    )


def _validate_assessment_coherence(
    assessment: OverallAssessment,
    blocking_ids: tuple[str, ...],
    correction_ids: tuple[str, ...],
) -> None:
    if assessment is OverallAssessment.ACCEPTABLE and (blocking_ids or correction_ids):
        _raise_assessment(ReviewAssessmentErrorCode.ASSESSMENT_INCOHERENT)
    if blocking_ids and assessment in {
        OverallAssessment.ACCEPTABLE,
        OverallAssessment.ACCEPTABLE_WITH_RESERVATIONS,
    }:
        _raise_assessment(ReviewAssessmentErrorCode.ASSESSMENT_INCOHERENT)
    if assessment is OverallAssessment.CORRECTION_REQUIRED and not correction_ids:
        _raise_assessment(ReviewAssessmentErrorCode.ASSESSMENT_INCOHERENT)


def _revalidated_technical_mappings(
    technical: ReviewPortResult,
) -> Mapping[str, object]:
    try:
        payload = freeze_agent_safe_mapping(technical.structured_payload)
        structured_sequences = (
            (technical.limitations, "limitations"),
            (technical.warnings, "warnings"),
            (technical.uncertainties, "uncertainties"),
        )
        if any(
            type(values) is not tuple
            or any(not isinstance(value, Mapping) for value in values)
            for values, _ in structured_sequences
        ):
            raise TypeError("technical mapping sequences must contain mappings")
        frozen_sequences = tuple(
            (
                tuple(freeze_agent_safe_mapping(value) for value in values),
                field_name,
            )
            for values, field_name in structured_sequences
        )
        execution_metadata = freeze_agent_safe_mapping(technical.execution_metadata)
    except (TypeError, ValueError):
        _raise_assessment(ReviewAssessmentErrorCode.INVALID_TECHNICAL_PAYLOAD)
    try:
        _reject_authority_keys(payload, "structured_payload")
        _reject_authority_keys(frozen_sequences, "technical_diagnostics")
        _reject_authority_keys(execution_metadata, "execution_metadata")
        reject_activatable_review_metadata(payload)
        reject_activatable_review_metadata(frozen_sequences)
        reject_activatable_review_metadata(execution_metadata)
    except (TypeError, ValueError):
        _raise_assessment(ReviewAssessmentErrorCode.AUTHORITY_METADATA_FORBIDDEN)
    return payload


def _technical_ids(raw: object) -> tuple[str, ...]:
    if type(raw) is not tuple:
        _raise_assessment(ReviewAssessmentErrorCode.INVALID_TECHNICAL_PAYLOAD)
    if any(type(value) is not str or not value.strip() for value in raw):
        _raise_assessment(ReviewAssessmentErrorCode.INVALID_TECHNICAL_PAYLOAD)
    values: tuple[str, ...] = raw
    if len(values) != len(set(values)):
        _raise_assessment(ReviewAssessmentErrorCode.INVALID_TECHNICAL_PAYLOAD)
    return values


def _correction_handoff(
    request: FindingsAssessmentRequest,
    signal: ReviewAssessmentSignal,
) -> CorrectionHandoffSignal | None:
    if not signal.correction_finding_ids:
        return None
    selected = tuple(
        finding
        for finding in request.source_result.findings
        if finding.finding_id in signal.correction_finding_ids
    )
    evidence_refs: tuple[ContractRef, ...] = tuple(
        dict.fromkeys(ref for finding in selected for ref in finding.evidence_refs)
    )
    if not set(evidence_refs).issubset(request.source_request.evidence_refs) or not set(
        evidence_refs
    ).issubset(request.source_result.evidence_refs_used):
        _raise_assessment(ReviewAssessmentErrorCode.EVIDENCE_OUT_OF_SCOPE)
    suggested_actions = tuple(
        {
            "finding_id": finding.finding_id,
            "suggested_action": finding.suggested_action,
        }
        for finding in selected
        if finding.suggested_action
    )
    return CorrectionHandoffSignal(
        destination_agent_id=AgentId.AG_01,
        review_ref=signal.review_ref,
        review_id=signal.review_id,
        target_production_ref=signal.target_production_ref,
        finding_ids=signal.correction_finding_ids,
        blocking_finding_ids=signal.blocking_finding_ids,
        evidence_refs=evidence_refs,
        suggested_actions=suggested_actions,
        limitations=signal.limitations,
        warnings=signal.warnings,
        security_signal_codes=signal.security_signal_codes,
    )
