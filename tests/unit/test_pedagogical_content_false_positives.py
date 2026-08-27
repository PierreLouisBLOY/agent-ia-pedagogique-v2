from __future__ import annotations

import pytest

from backend.agent_runtime.contracts import (
    ContentOrigin,
    ContentRole,
    ContentSecurityDisposition,
    ContentTrustClass,
    ContentTrustLabel,
    LabeledContent,
)
from backend.agent_runtime.contracts.security import SecurityBoundary
from backend.agent_runtime.security import (
    ContentIsolationContext,
    InstructionDataBoundaryPolicy,
    scan_content_threats,
)


@pytest.mark.parametrize(
    "text",
    [
        "Ignorez la TVA dans cet exercice",
        "Expliquez pourquoi le manager doit donner des instructions",
        "Le document affirme : 'ignore previous instructions'",
        "Analysez ce code qui appelle open('file.txt')",
        "URL : https://education.gouv.fr",
        "Le cas demande de proposer une action",
    ],
)
def test_pedagogical_imperatives_remain_usable_data(text: str) -> None:
    content = LabeledContent(
        "pedagogical-case-1",
        text,
        ContentTrustLabel(
            ContentOrigin.DOCUMENT,
            ContentRole.DATA,
            ContentTrustClass.UNTRUSTED,
            "document:pedagogy",
        ),
        "document:pedagogy",
    )
    signals = scan_content_threats(
        text,
        content_ref=content.content_ref,
        logical_location="document.body",
    )
    assessment = InstructionDataBoundaryPolicy().assess(
        content=content,
        context=ContentIsolationContext(SecurityBoundary.DOCUMENT),
        signals=signals,
    )

    assert assessment.disposition in {
        ContentSecurityDisposition.PASS_AS_DATA,
        ContentSecurityDisposition.ISOLATE_AS_DATA,
    }
