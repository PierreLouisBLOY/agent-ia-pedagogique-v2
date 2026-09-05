from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest

from backend.adapters.outbound.document_content.sqlite import DocumentContentAccessAdapter
from backend.adapters.outbound.persistence.sqlite import connect_sqlite
from backend.adapters.outbound.search.local import SQLiteLocalSearchAdapter, literal_fts
from backend.agent_runtime.agents.evidence import RetrievalChannel, RetrievalQuery
from backend.infrastructure.composition.factories.local_browser import Read15RuntimeTarget
from backend.modules.resource_library.domain.value_objects.search_text import SearchText

TEXT = "bilan fonctionnel synthétique"
RESOURCE = "resource:r1"


def synthetic_search_target(tmp_path: Path, *, count: int = 1) -> Read15RuntimeTarget:
    root = tmp_path / "r1-synthetic"
    root.mkdir()
    path = root / "search.sqlite"
    assert not path.exists()
    connection = sqlite3.connect(path)
    try:
        connection.executescript("""
            CREATE TABLE object_registry(object_id TEXT PRIMARY KEY, object_type TEXT NOT NULL);
            CREATE TABLE notion(id TEXT PRIMARY KEY, canonical_label TEXT, identity_status TEXT);
            CREATE TABLE resource(id TEXT PRIMARY KEY, resource_type TEXT,
                                  canonical_title TEXT, identity_status TEXT);
            CREATE TABLE search_chunk(id TEXT PRIMARY KEY, object_id TEXT, chunk_type TEXT,
                                      chunk_hash TEXT, text TEXT, status TEXT);
            CREATE VIRTUAL TABLE search_chunk_fts USING fts5(
                text, content='search_chunk', content_rowid='rowid'
            );
        """)
        for index in range(count):
            ref = RESOURCE if index == 0 else f"notion:r1-{index}"
            kind = "RESOURCE" if index == 0 else "NOTION"
            connection.execute("INSERT INTO object_registry VALUES (?, ?)", (ref, kind))
            if index:
                connection.execute("INSERT INTO notion VALUES (?, ?, ?)", (ref, TEXT, "CANONICAL"))
            else:
                connection.execute(
                    "INSERT INTO resource VALUES (?, ?, ?, ?)",
                    (ref, "COURSE", "Bilan fonctionnel synthétique", "ACTIVE"),
                )
            connection.execute(
                "INSERT INTO search_chunk VALUES (?, ?, ?, ?, ?, ?)",
                (f"chunk:r1-{index:03d}", ref, "BODY", f"version:{index}", TEXT, "CURRENT"),
            )
        connection.execute(
            "INSERT INTO search_chunk_fts(rowid, text) SELECT rowid, text FROM search_chunk"
        )
        connection.commit()
    finally:
        connection.close()
    return Read15RuntimeTarget(path, root, hashlib.sha256(path.read_bytes()).hexdigest())


def reader(target: Read15RuntimeTarget) -> sqlite3.Connection:
    target.validate()
    return connect_sqlite(target.runtime_path, readonly=True, allowed_root=target.data_root)


def test_lexical_readonly_snapshot_and_stable_window(tmp_path: Path) -> None:
    target = synthetic_search_target(tmp_path, count=101)
    before = target.runtime_path.read_bytes()
    connection = reader(target)
    bridge = SQLiteLocalSearchAdapter(connection)
    try:
        with pytest.raises(ValueError, match="SNAPSHOT"):
            bridge.admitted_window(text=SearchText("bilan"), result_limit=10)
        with bridge.read_snapshot():
            first = bridge.admitted_window(text=SearchText("bilan"), result_limit=20)
            second = bridge.admitted_window(text=SearchText("bilan"), result_limit=20)
            assert first == second
            assert first.window_full and first.more_admitted_in_window
            assert len(first.passages) == 20
            assert [p.passage_ref for p in first.passages] == [
                f"chunk:r1-{index:03d}" for index in range(20)
            ]
            with pytest.raises(sqlite3.OperationalError):
                connection.execute("UPDATE resource SET canonical_title = 'forbidden'")
            with pytest.raises(ValueError, match="ALREADY_ACTIVE"), bridge.read_snapshot():
                pass
        assert not connection.in_transaction
    finally:
        connection.close()
    assert target.runtime_path.read_bytes() == before
    assert not target.runtime_path.with_name("search.sqlite-wal").exists()
    assert not target.runtime_path.with_name("search.sqlite-shm").exists()


def test_admission_before_content_and_only_selected_materialization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = synthetic_search_target(tmp_path, count=4)
    connection = reader(target)
    bridge = SQLiteLocalSearchAdapter(connection)
    admitted_calls = []
    content_calls = []
    gate = bridge._evidence.is_admissible
    content = bridge._content.read_passage
    def admission(*, candidate, query):
        admitted_calls.append(candidate.locator)
        return candidate.locator != "chunk:r1-000" and gate(candidate=candidate, query=query)
    def read(ref):
        assert len(admitted_calls) == 4
        content_calls.append(ref)
        return content(ref)
    monkeypatch.setattr(bridge._evidence, "is_admissible", admission)
    monkeypatch.setattr(bridge._content, "read_passage", read)
    try:
        with bridge.read_snapshot():
            result = bridge.admitted_window(text=SearchText("bilan"), result_limit=1)
        assert len(admitted_calls) == 4
        assert content_calls == ["chunk:r1-001"]
        assert result.more_admitted_in_window and not result.window_full
    finally:
        connection.close()


def test_independent_f2a_rejects_checksum_and_policy_without_structured(
    tmp_path: Path,
) -> None:
    target = synthetic_search_target(tmp_path)
    connection = reader(target)
    bridge = SQLiteLocalSearchAdapter(connection)
    query = RetrievalQuery(
        search_goal=literal_fts(SearchText("bilan")), scope={},
        source_policy={"kinds": ("canonical",)}, filters={"active": True},
        required_authority={"basis": "canonical-registry"}, max_items=100,
    )
    try:
        with bridge.read_snapshot():
            candidate = bridge._evidence.search(query=query, channel=RetrievalChannel.LEXICAL).candidates[0]
            assert bridge._evidence.is_admissible(candidate=candidate, query=query)
            assert not bridge._evidence.is_admissible(
                candidate=replace(candidate, version_or_checksum="wrong"), query=query,
            )
            assert not bridge._evidence.is_admissible(
                candidate=candidate, query=replace(query, filters={"active": False}),
            )
    finally:
        connection.close()


def test_current_and_canonical_notions_only_and_literal_operator(tmp_path: Path) -> None:
    target = synthetic_search_target(tmp_path, count=3)
    connection = sqlite3.connect(target.runtime_path)
    try:
        connection.execute("UPDATE notion SET identity_status='ACTIVE' WHERE id='notion:r1-1'")
        connection.execute("UPDATE search_chunk SET status='OLD' WHERE id='chunk:r1-002'")
        connection.commit()
    finally:
        connection.close()
    target = replace(target, expected_sha256=hashlib.sha256(target.runtime_path.read_bytes()).hexdigest())
    connection = reader(target)
    try:
        bridge = SQLiteLocalSearchAdapter(connection)
        with bridge.read_snapshot():
            result = bridge.admitted_window(text=SearchText("bilan"), result_limit=10)
            assert len(result.passages) == 1
            assert result.passages[0].object_ref == RESOURCE
            assert bridge.admitted_window(
                text=SearchText("bilan OR absent"), result_limit=10,
            ).passages == ()
    finally:
        connection.close()


@pytest.mark.parametrize("fault", ["missing", "checksum", "source", "passage"])
def test_op13_provenance_failures_do_not_become_empty_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str,
) -> None:
    target = synthetic_search_target(tmp_path)
    connection = reader(target)
    bridge = SQLiteLocalSearchAdapter(connection)
    actual = DocumentContentAccessAdapter(connection).read_passage("chunk:r1-000")
    replacement = None if fault == "missing" else replace(actual, **{
        {"checksum": "version_or_checksum", "source": "source_ref", "passage": "passage_ref"}[fault]:
            "wrong"
    })
    monkeypatch.setattr(bridge._content, "read_passage", lambda _: replacement)
    try:
        with bridge.read_snapshot(), pytest.raises(ValueError, match="PROVENANCE"):
            bridge.admitted_window(text=SearchText("bilan"), result_limit=10)
    finally:
        connection.close()


def test_read_snapshot_rejects_mutable_connection(tmp_path: Path) -> None:
    target = synthetic_search_target(tmp_path)
    connection = sqlite3.connect(target.runtime_path)
    try:
        with pytest.raises(ValueError, match="QUERY_ONLY"), SQLiteLocalSearchAdapter(connection).read_snapshot():
            pass
    finally:
        connection.close()


def test_full_window_with_no_admission_has_no_materialization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = synthetic_search_target(tmp_path, count=100)
    connection = reader(target)
    bridge = SQLiteLocalSearchAdapter(connection)
    calls = []
    def deny(*, candidate, query):
        calls.append(candidate.locator)
        return False
    def forbidden(*args):
        pytest.fail("rejected content must not be read")
    monkeypatch.setattr(bridge._evidence, "is_admissible", deny)
    monkeypatch.setattr(bridge._content, "read_passage", forbidden)
    try:
        with bridge.read_snapshot():
            result = bridge.admitted_window(text=SearchText("bilan"), result_limit=10)
        assert len(calls) == 100
        assert result.passages == () and result.window_full and not result.more_admitted_in_window
    finally:
        connection.close()


def test_multiple_passages_of_same_object_are_not_merged(tmp_path: Path) -> None:
    target = synthetic_search_target(tmp_path, count=2)
    connection = sqlite3.connect(target.runtime_path)
    try:
        connection.execute("UPDATE search_chunk SET object_id=?", (RESOURCE,))
        connection.commit()
    finally:
        connection.close()
    target = replace(target, expected_sha256=hashlib.sha256(target.runtime_path.read_bytes()).hexdigest())
    connection = reader(target)
    try:
        bridge = SQLiteLocalSearchAdapter(connection)
        with bridge.read_snapshot():
            result = bridge.admitted_window(text=SearchText("bilan"), result_limit=10)
        assert [item.object_ref for item in result.passages] == [RESOURCE, RESOURCE]
        assert len({item.passage_ref for item in result.passages}) == 2
    finally:
        connection.close()
