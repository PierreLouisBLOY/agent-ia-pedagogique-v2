from __future__ import annotations

from backend.agent_runtime.contracts import (
    ContentOrigin,
    ContentRole,
    ContentSecurityAssessment,
    ContentSecurityDisposition,
    ContentThreatSignal,
    ContentThreatSignalCode,
    ContentTrustClass,
    ContentTrustLabel,
    SecurityBoundary,
    SecurityReasonCode,
    StructuredContentSecurityAssessment,
)
from backend.agent_runtime.security.runtime_composition import (
    RuntimeSecurityDisposition,
    RuntimeSecurityReasonCode,
    SecurityRuntimeGuard,
)


def _finding(
    disposition: ContentSecurityDisposition,
    *,
    structural: bool = False,
) -> StructuredContentSecurityAssessment:
    label = ContentTrustLabel(
        ContentOrigin.AGENT_OUTPUT,
        ContentRole.RESULT,
        ContentTrustClass.UNTRUSTED,
        "source-ref",
    )
    signals = (
        ()
        if structural
        else (
            ContentThreatSignal(
                ContentThreatSignalCode.INSTRUCTION_LIKE_CONTENT,
                "content-ref:text:0",
                "payload.text",
            ),
        )
    )
    nested = (
        ()
        if structural
        else (
            ContentSecurityAssessment(
                content_ref="content-ref:text:0",
                label=label,
                disposition=disposition,
                signals=signals,
                reason_codes=(SecurityReasonCode("CONTENT.THREAT_SIGNAL_PRESENT"),),
            ),
        )
    )
    return StructuredContentSecurityAssessment(
        content_ref="content-ref",
        label=label,
        boundary=SecurityBoundary.TOOL,
        disposition=disposition,
        content_assessments=nested,
        structural_locations=("tool_arguments.permission",) if structural else (),
        reason_codes=(SecurityReasonCode("BOUNDARY.TEST"),),
    )


def test_runtime_security_guard_is_restriction_only() -> None:
    guard = SecurityRuntimeGuard()

    assert guard.compose(()).disposition is RuntimeSecurityDisposition.PASS
    isolated = guard.compose(
        (_finding(ContentSecurityDisposition.ISOLATE_AS_DATA),)
    )
    assert isolated.disposition is RuntimeSecurityDisposition.RESTRICT
    assert isolated.launchable

    denied = guard.compose(
        (_finding(ContentSecurityDisposition.QUARANTINE, structural=True),)
    )
    assert denied.disposition is RuntimeSecurityDisposition.DENY
    assert denied.reason_codes == (
        RuntimeSecurityReasonCode.STRUCTURAL_AUTHORITY_DATA,
    )
    assert not denied.launchable


def test_most_restrictive_security_finding_wins_without_granting_authority() -> None:
    assessment = SecurityRuntimeGuard().compose(
        (
            _finding(ContentSecurityDisposition.ISOLATE_AS_DATA),
            _finding(ContentSecurityDisposition.REJECT_CONTENT),
        )
    )

    assert assessment.disposition is RuntimeSecurityDisposition.DENY
    assert assessment.reason_codes == (
        RuntimeSecurityReasonCode.CONTENT_REJECTED,
    )
