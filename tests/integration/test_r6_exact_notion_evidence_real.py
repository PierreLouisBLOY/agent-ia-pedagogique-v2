"""Exact two-ID closure through Application on the authenticated owner-supplied seed."""
import os
from pathlib import Path

from backend.infrastructure.composition.factories.local_browser import Read15RuntimeTarget
from backend.infrastructure.composition.factories.r6_all_notions import exact_notion_evidence
from tools.r6.run_all_notions import SEED_SHA256


def test_both_historical_gaps_have_current_admitted_identity_and_linked_content():
    path = Path(os.environ["PROJET_V2_CANONICAL_DB"])
    target = Read15RuntimeTarget(path, path.parent, SEED_SHA256)
    with exact_notion_evidence(target) as inbound:
        for notion_id in ("notion:cout", "notion:production"):
            data = inbound.inspect(notion_id)
            assert data["status"] == "CANONICAL"
            assert data["retrieval_path"] == "EXACT_ID_AND_EXPLICIT_LINKS"
            passages = data["items"]
            assert any(p["object_ref"] == notion_id for p in passages)
            assert any(p["object_ref"] != notion_id for p in passages)
            assert all(p["provenance"]["admission_policy"] == "F2A" for p in passages)
            assert all(p["provenance"]["authority_absolute"] is False for p in passages)
        assert inbound.inspect("notion:missing") == {
            "notion_id": "notion:missing", "status": "NOT_CANONICAL_OR_ABSENT", "items": [],
        }
