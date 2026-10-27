"""Wire format never creates a canonical source or grants source authority."""
from urllib.parse import quote

import pytest

from backend.adapters.inbound.api.p0_notion_evidence import P0NotionEvidenceEndpoint
from backend.adapters.inbound.api.routes import (
    P0_NOTION_EVIDENCE_TEMPLATE,
    resolve_p0_notion_evidence,
)
from backend.modules.resource_library.ports.outbound.local_search import require_logical_identifier


@pytest.mark.parametrize("suffix", ["é", "字", "١", "Ａ", "Coût", "a_b-c.d", "9", "X:Y"])
def test_valid_wire_unicode_still_requires_actual_canonical_application_source(suffix):
    notion = "notion:" + suffix
    target = P0_NOTION_EVIDENCE_TEMPLATE + "?notion_id=" + quote(notion, safe="")
    require_logical_identifier(notion, 256)
    assert resolve_p0_notion_evidence("GET", target) == notion
    calls = []

    def reader(ref):
        calls.append(ref)
        return {"notion_id": ref, "status": "NOT_CANONICAL_OR_ABSENT", "items": []}

    status, _, raw, _ = P0NotionEvidenceEndpoint(reader).respond("GET", target, b"", "wire")
    assert status == 404 and calls == [notion] and b"P0_NOTION_NOT_FOUND" in raw
    assert b'"data"' not in raw


@pytest.mark.parametrize("suffix", ["e\u0301", "a\u200d", "a\u2028", "🧪", "a/b", "a\\b", "a#b", "a?b", "a%b", "a b", "a\x00b", "a\ud800b"])
def test_wire_invalid_identifier_is_rejected_before_application(suffix):
    notion = "notion:" + suffix
    with pytest.raises(ValueError):
        require_logical_identifier(notion, 256)
    value = quote(notion, safe="", errors="surrogatepass")
    target = P0_NOTION_EVIDENCE_TEMPLATE + "?notion_id=" + value
    with pytest.raises(ValueError, match="P0_REFERENCE_REQUEST_REJECTED"):
        resolve_p0_notion_evidence("GET", target)
    calls = []
    status, _, raw, _ = P0NotionEvidenceEndpoint(lambda ref: calls.append(ref) or {}).respond("GET", target, b"", "wire")
    assert status == 400 and calls == [] and b'"data"' not in raw
