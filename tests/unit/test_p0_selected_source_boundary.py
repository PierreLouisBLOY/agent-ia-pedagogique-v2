import hashlib
from contextlib import contextmanager

import pytest

from backend.infrastructure.composition.factories import p0_creation, r6_all_notions, r6_p0
from tests.unit.test_p0_creation_contract import context


@pytest.mark.parametrize("kind,truncated,expected", [
    ("PEDAGOGICAL_CONTENT", False, None), ("METHOD", False, None), ("NOTION", False, None),
    ("CORRECTION", False, "P0_TEACHER_SOURCE_FORBIDDEN"),
    ("MARKING", False, "P0_TEACHER_SOURCE_FORBIDDEN"),
    ("PEDAGOGICAL_CONTENT", True, "P0_REFERENCE_INCOMPLETE"),
])
def test_exact_selection_reuses_inbound_and_rejects_oracle_or_incomplete_source(monkeypatch, kind, truncated, expected):
    calls = []
    class Inbound:
        def inspect(self, notion):
            calls.append(notion)
            return {"items": [{"object_ref": "content:source", "object_kind": kind, "passage_ref": "passage:exact",
                               "version_or_checksum": "version:1", "excerpt": "Source admise mais non officielle.", "excerpt_truncated": truncated}]}
    @contextmanager
    def boundary(target):
        yield Inbound()
    monkeypatch.setattr(r6_all_notions, "exact_notion_evidence", boundary)
    app, _ = p0_creation.build_p0_creation(object(), "nonce")
    command = {"command_id": "a" * 32, "context": context("FIRST_STMG", "COURSE", None),
               "reference": {"notion_id": "notion:exact", "passage_ref": "passage:exact"}}
    if expected:
        with pytest.raises(ValueError, match=expected):
            app.execute("prepare", command)
    else:
        result = app.execute("prepare", command)
        assert result["references"][0]["excerpt_sha256"] == hashlib.sha256(b"Source admise mais non officielle.").hexdigest()
        assert result["provider_attempts"] == 0
    assert calls == ["notion:exact"]


@pytest.mark.parametrize("kind", ["CORRECTION", "MARKING", "QUESTION", "RESOURCE"])
def test_lexical_teacher_source_never_becomes_generation_evidence(monkeypatch, kind):
    monkeypatch.setattr(r6_p0, "load_p0_reference", lambda *a, **k: {"object_kind": kind, "reference": {}, "excerpt": "Oracle interdit"})
    app, _ = p0_creation.build_p0_creation(object(), "nonce")
    with pytest.raises(ValueError, match="P0_TEACHER_SOURCE_FORBIDDEN"):
        app.execute("prepare", {"command_id": "a" * 32, "context": context("FIRST_STMG", "COURSE", None),
                                "reference": {"query": "q", "passage_ref": "p"}})
