from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from backend.agent_runtime.contracts.common import (
    ContractMeta,
    ContractRef,
    freeze_agent_safe_mapping,
    require_contract_ref,
)
from backend.agent_runtime.contracts.errors import ErrorEnvelope
from backend.agent_runtime.contracts.invocation import AgentResultStatus
from backend.agent_runtime.contracts.security import (
    ContentOrigin,
    ContentRole,
    ContentTrustClass,
    ContentTrustLabel,
    LabeledContent,
    SecurityBoundary,
    StructuredContentSecurityAssessment,
)
from backend.shared_kernel._strings import require_non_empty


@dataclass(frozen=True, slots=True)
class ToolCallResult:
    """Data-only tool result whose output is not evidence by default."""

    meta: ContractMeta[AgentResultStatus]
    tool_id: str
    output: Mapping[str, object] | None = None
    artifacts: tuple[ContractRef, ...] = ()
    metrics: Mapping[str, object] = field(default_factory=dict)
    error: ErrorEnvelope | None = None
    content_label: ContentTrustLabel | None = None
    labeled_content: tuple[LabeledContent, ...] = ()
    security_assessment: StructuredContentSecurityAssessment | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.meta, ContractMeta):
            raise TypeError("meta must be a ContractMeta")
        if not isinstance(self.meta.status, AgentResultStatus):
            raise TypeError("meta.status must be an AgentResultStatus")
        require_non_empty(self.tool_id, "tool_id")
        if self.output is not None:
            object.__setattr__(self, "output", freeze_agent_safe_mapping(self.output))
        artifacts = tuple(self.artifacts)
        for artifact in artifacts:
            require_contract_ref(artifact, "artifact")
        if self.error is not None:
            if not isinstance(self.error, ErrorEnvelope):
                raise TypeError("error must be an ErrorEnvelope")
            if self.error.step_id != self.meta.step_id:
                raise ValueError("error.step_id must match meta.step_id")
        if self.meta.status is AgentResultStatus.FAILED and self.error is None:
            raise ValueError("failed tool result requires an error")
        expected_ref = f"tool-result:{self.tool_id}:{self.meta.step_id}"
        content_label = self.content_label or ContentTrustLabel(
            origin=ContentOrigin.TOOL_OUTPUT,
            role=ContentRole.RESULT,
            trust_class=ContentTrustClass.UNTRUSTED,
            source_ref=expected_ref,
        )
        if (
            type(content_label) is ContentTrustLabel
            and content_label.origin is ContentOrigin.TOOL_OUTPUT
            and content_label.role is ContentRole.RESULT
            and content_label.trust_class is ContentTrustClass.UNTRUSTED
            and isinstance(content_label.source_ref, str)
            and content_label.source_ref.startswith("tool-result:")
            and not self.labeled_content
            and self.security_assessment is None
        ):
            content_label = ContentTrustLabel(
                origin=ContentOrigin.TOOL_OUTPUT,
                role=ContentRole.RESULT,
                trust_class=ContentTrustClass.UNTRUSTED,
                source_ref=expected_ref,
            )
        if type(content_label) is not ContentTrustLabel:
            raise TypeError("content_label must be a ContentTrustLabel")
        if (
            content_label.origin is not ContentOrigin.TOOL_OUTPUT
            or content_label.role is not ContentRole.RESULT
            or content_label.trust_class is not ContentTrustClass.UNTRUSTED
            or content_label.source_ref != expected_ref
        ):
            raise ValueError("content_label must preserve untrusted Tool provenance")
        labeled_content = tuple(self.labeled_content)
        if any(type(item) is not LabeledContent for item in labeled_content):
            raise TypeError("labeled_content must contain LabeledContent values")
        if any(item.label != content_label for item in labeled_content):
            raise ValueError("labeled_content must preserve the Tool result label")
        if len({item.content_ref for item in labeled_content}) != len(labeled_content):
            raise ValueError("labeled_content references must be unique")
        assessment = self.security_assessment
        if assessment is not None:
            if type(assessment) is not StructuredContentSecurityAssessment:
                raise TypeError("security_assessment has an invalid type")
            if (
                assessment.label != content_label
                or assessment.boundary is not SecurityBoundary.TOOL
                or {item.content_ref for item in assessment.content_assessments}
                != {item.content_ref for item in labeled_content}
            ):
                raise ValueError("security assessment must preserve Tool result lineage")
        object.__setattr__(self, "artifacts", artifacts)
        object.__setattr__(self, "metrics", freeze_agent_safe_mapping(self.metrics))
        object.__setattr__(self, "content_label", content_label)
        object.__setattr__(self, "labeled_content", labeled_content)
