from __future__ import annotations

from backend.agent_runtime.agents.review import (
    ResolvedReviewTarget,
    ReviewCoordinator,
    ReviewPreparationRequest,
)
from backend.agent_runtime.contracts import ContentOrigin, ContentRole, EvidenceItem
from backend.agent_runtime.security import label_evidence_item
from tests.unit.test_evidence_content_labeling import NOW
from tests.unit.test_review_coordinator import (
    V01,
    RecordingRawReviewPort,
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
        excerpt_or_summary="Evidence non authoritative.",
        checksum_or_version="v1",
    )


def test_labeled_evidence_reaches_prepared_review_with_exact_provenance() -> None:
    canonical = _canonical()
    labeled = label_evidence_item(_evidence())
    target = ResolvedReviewTarget(
        canonical.target_production_ref,
        content="Production à revoir.",
    )
    preparation = ReviewPreparationRequest(
        V01,
        canonical,
        target,
        labeled_evidence=(labeled,),
    )
    prepared = ReviewCoordinator(RecordingRawReviewPort(_result())).prepare(
        request=preparation
    )

    propagated = prepared.preparation_request.labeled_evidence[0]
    assert propagated is labeled
    assert propagated.content.label.origin is ContentOrigin.EVIDENCE
    assert propagated.content.label.role is ContentRole.EVIDENCE


def test_review_target_preserves_generated_output_label() -> None:
    target = ResolvedReviewTarget(
        _canonical().target_production_ref,
        content="Production à revoir.",
    )

    assert target.content_label is not None
    assert target.content_label.origin is ContentOrigin.AGENT_OUTPUT
    assert target.content_label.role is ContentRole.RESULT
