from __future__ import annotations

from backend.agent_runtime.agents.generation import (
    GenerationCoordinator,
    GenerationPreparationRequest,
)
from backend.agent_runtime.contracts import ContentOrigin, ContentRole, EvidenceItem
from backend.agent_runtime.security import label_evidence_item
from tests.unit.test_evidence_content_labeling import NOW
from tests.unit.test_generation_coordinator import (
    G01,
    RecordingGenerationPort,
    _canonical,
    _result,
)


def _evidence() -> EvidenceItem:
    return EvidenceItem(
        evidence_id="evidence:one",
        source_ref="document:one",
        source_kind="canonical_document",
        locator="section:one",
        retrieved_at=NOW,
        excerpt_or_summary="Source pédagogique avec URL https://education.gouv.fr",
        checksum_or_version="v1",
    )


def test_labeled_evidence_reaches_prepared_generation_without_trust_promotion() -> None:
    labeled = label_evidence_item(_evidence())
    preparation = GenerationPreparationRequest(
        G01,
        _canonical(),
        labeled_evidence=(labeled,),
    )
    prepared = GenerationCoordinator(RecordingGenerationPort(_result())).prepare(
        request=preparation
    )

    propagated = prepared.preparation_request.labeled_evidence[0]
    assert propagated is labeled
    assert propagated.content.label.origin is ContentOrigin.EVIDENCE
    assert propagated.content.label.role is ContentRole.EVIDENCE
    assert propagated.content.label == labeled.security_assessment.label


def test_generated_result_receives_non_authoritative_output_label() -> None:
    result = _result()

    assert result.content_label is not None
    assert result.content_label.origin is ContentOrigin.AGENT_OUTPUT
    assert result.content_label.role is ContentRole.RESULT
