from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import pytest

from backend.adapters.outbound.persistence.sqlite import connect_sqlite
from backend.adapters.outbound.resource_library.exact_source_sqlite import (
    SQLiteExactResourceEvidenceAdapter,
)
from backend.infrastructure.composition.factories.local_browser import Read15RuntimeTarget
from backend.infrastructure.composition.factories.r6_p0 import (
    R6_EXACT_SOURCE_BINDINGS,
    load_p0_exact_reference,
)
from backend.modules.resource_library.application.dto.input.exact_resource_evidence import (
    ExactResourceEvidenceRequest,
)
from backend.modules.resource_library.application.queries.get_exact_resource_evidence import (
    GetExactResourceEvidenceQuery,
)
from backend.modules.resource_library.domain.value_objects import ResourceRef
from backend.modules.resource_library.ports.outbound.exact_resource_evidence import (
    ExactResourceEvidenceRecord,
    ExactResourceLookup,
    ExactResourceLookupStatus,
    ExactResourceQuestionRecord,
)

RESOURCE = "revmax260921g:exercise:d6ac1f74b244ef7c7911fc60"
VERSION = "revmax260921g:exercise_version:d6ac1f74b244ef7c7911fc60"
QUESTION = "revmax260921g:question:d6ac1f74b244ef7c7911fc60"
CORRECTION = "revmax260921g:correction:d6ac1f74b244ef7c7911fc60"
BODY = """{
  "notion_id": "notion:organisation",
  "prompt": "Analysez ce cas relatif à « Organisation » : Une association emploie des salariés, dispose d’un budget et coordonne des actions autour d’une mission sociale.",
  "correction": "Elle constitue une organisation car elle mobilise durablement acteurs et ressources autour d’une finalité avec coordination.",
  "points": 4,
  "controls": [
    "identifier finalité",
    "repérer ressources et acteurs",
    "observer coordination et règles"
  ],
  "case": "Une association emploie des salariés, dispose d’un budget et coordonne des actions autour d’une mission sociale."
}"""
PROMPT = "Analysez ce cas relatif à « Organisation » : Une association emploie des salariés, dispose d’un budget et coordonne des actions autour d’une mission sociale."
ANSWER = "Elle constitue une organisation car elle mobilise durablement acteurs et ressources autour d’une finalité avec coordination."


def _database(
    path: Path,
    *,
    body: str = BODY,
    prompt: str = PROMPT,
    correction: str = ANSWER,
    add_other: bool = True,
) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.executescript(
            """
            CREATE TABLE resource(
                id TEXT PRIMARY KEY, resource_type TEXT NOT NULL,
                canonical_title TEXT NOT NULL, identity_status TEXT NOT NULL
            );
            CREATE TABLE resource_version(
                id TEXT PRIMARY KEY, resource_id TEXT NOT NULL,
                lifecycle_status TEXT NOT NULL, validation_status TEXT NOT NULL,
                body TEXT NOT NULL
            );
            CREATE TABLE question(
                id TEXT PRIMARY KEY, question_type TEXT NOT NULL,
                prompt TEXT NOT NULL, lifecycle_status TEXT NOT NULL
            );
            CREATE TABLE correction(
                id TEXT PRIMARY KEY, correction_type TEXT NOT NULL,
                body TEXT NOT NULL, lifecycle_status TEXT NOT NULL
            );
            CREATE TABLE exercise_question(
                exercise_resource_id TEXT NOT NULL, question_id TEXT NOT NULL,
                position INTEGER NOT NULL, points_default REAL NOT NULL,
                required INTEGER NOT NULL
            );
            CREATE TABLE question_correction(
                question_id TEXT NOT NULL, correction_id TEXT NOT NULL
            );
            """
        )
        connection.execute(
            "INSERT INTO resource VALUES(?, 'EXERCISE', 'Cas — Organisation — 2', 'ACTIVE')",
            (RESOURCE,),
        )
        connection.execute(
            "INSERT INTO resource_version VALUES(?, ?, 'REVIEW', 'NEEDS_REVIEW', ?)",
            (VERSION, RESOURCE, body),
        )
        connection.execute(
            "INSERT INTO question VALUES(?, 'OPEN', ?, 'REVIEW')", (QUESTION, prompt)
        )
        connection.execute(
            "INSERT INTO correction VALUES(?, 'TEXT', ?, 'REVIEW')",
            (CORRECTION, correction),
        )
        connection.execute(
            "INSERT INTO exercise_question VALUES(?, ?, 1, 4.0, 1)",
            (RESOURCE, QUESTION),
        )
        connection.execute(
            "INSERT INTO question_correction VALUES(?, ?)", (QUESTION, CORRECTION)
        )
        if add_other:
            connection.execute(
                "INSERT INTO resource VALUES('resource:other', 'EXERCISE', 'Other', 'ACTIVE')"
            )
            connection.execute(
                "INSERT INTO resource_version VALUES('version:other', 'resource:other', 'REVIEW', 'PENDING', '{}')"
            )
        connection.commit()
    finally:
        connection.close()


def _query(path: Path) -> GetExactResourceEvidenceQuery:
    connection = connect_sqlite(path, readonly=True, immutable=True, allowed_root=path.parent)
    return GetExactResourceEvidenceQuery(SQLiteExactResourceEvidenceAdapter(connection))


def _target(path: Path) -> Read15RuntimeTarget:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return Read15RuntimeTarget(path, path.parent, digest)


def test_exact_reader_returns_typed_bounded_projection(tmp_path: Path) -> None:
    path = tmp_path / "exact.sqlite"
    _database(path)
    query = _query(path)
    view = query.execute(ExactResourceEvidenceRequest(ResourceRef(RESOURCE), VERSION))
    assert view.resource_ref.value == RESOURCE
    assert view.resource_version_ref == VERSION
    assert view.body_sha256 == hashlib.sha256(BODY.encode()).hexdigest()
    assert tuple(item.question_id for item in view.questions) == (QUESTION,)
    assert view.questions[0].correction_id == CORRECTION
    assert "path" not in view.as_dict() and "storage_uri" not in view.as_dict()


def test_six_pairs_are_closed_and_feed_seven_scenarios() -> None:
    assert len(R6_EXACT_SOURCE_BINDINGS) == 6
    assert {scenario for item in R6_EXACT_SOURCE_BINDINGS for scenario in item.scenarios} == {
        f"R6-S0{index}" for index in range(1, 8)
    }


@pytest.mark.parametrize(
    ("body", "prompt", "correction", "code"),
    [
        (BODY + " mutation", PROMPT, ANSWER, "R6_RESOURCE_BODY_HASH_MISMATCH"),
        (BODY, PROMPT + " mutation", ANSWER, "R6_QUESTION_HASH_MISMATCH"),
        (BODY, PROMPT, ANSWER + " mutation", "R6_CORRECTION_HASH_MISMATCH"),
    ],
)
def test_allowlist_hashes_fail_closed_on_copied_fixture_mutation(
    tmp_path: Path, body: str, prompt: str, correction: str, code: str
) -> None:
    path = tmp_path / "mutated.sqlite"
    _database(path, body=body, prompt=prompt, correction=correction)
    with pytest.raises(ValueError, match=code):
        load_p0_exact_reference(
            _target(path), resource_ref=RESOURCE, resource_version_ref=VERSION
        )


def test_seventh_existing_resource_is_refused_before_database_access(tmp_path: Path) -> None:
    path = tmp_path / "allowlist.sqlite"
    _database(path)
    with pytest.raises(ValueError, match="R6_SOURCE_NOT_ALLOWLISTED"):
        load_p0_exact_reference(
            _target(path),
            resource_ref="resource:other",
            resource_version_ref="version:other",
        )


def test_good_resource_with_version_owned_by_other_resource_is_mismatch(tmp_path: Path) -> None:
    path = tmp_path / "mismatch.sqlite"
    _database(path)
    with pytest.raises(ValueError, match="R6_RESOURCE_VERSION_MISMATCH"):
        _query(path).execute(
            ExactResourceEvidenceRequest(ResourceRef(RESOURCE), "version:other")
        )


def test_absent_version_is_refused_without_latest_fallback(tmp_path: Path) -> None:
    path = tmp_path / "missing-version.sqlite"
    _database(path)
    with pytest.raises(ValueError, match="R6_RESOURCE_VERSION_NOT_FOUND"):
        _query(path).execute(
            ExactResourceEvidenceRequest(ResourceRef(RESOURCE), "version:missing")
        )


def test_unknown_resource_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "missing-resource.sqlite"
    _database(path)
    with pytest.raises(ValueError, match="R6_RESOURCE_NOT_FOUND"):
        _query(path).execute(
            ExactResourceEvidenceRequest(ResourceRef("resource:missing"), VERSION)
        )


def test_title_only_never_falls_back_to_search(tmp_path: Path) -> None:
    path = tmp_path / "title.sqlite"
    _database(path)
    with pytest.raises(ValueError, match="R6_SOURCE_NOT_ALLOWLISTED"):
        load_p0_exact_reference(
            _target(path),
            resource_ref="Cas-Organisation-2",
            resource_version_ref=VERSION,
        )


class _OversizedSource:
    def load_exact_resource(
        self, resource_ref: ResourceRef, resource_version_ref: str
    ) -> ExactResourceLookup:
        question = ExactResourceQuestionRecord("question:one", 1, 1.0, "Q", "correction:one", "C")
        return ExactResourceLookup(
            ExactResourceLookupStatus.FOUND,
            ExactResourceEvidenceRecord(
                resource_ref, resource_version_ref, "EXERCISE", "Title", "ACTIVE",
                "REVIEW", "PENDING", "x" * 70_000, (question,),
            ),
        )


def test_projection_over_65536_bytes_is_refused() -> None:
    with pytest.raises(ValueError, match="R6_RESOURCE_PROJECTION_TOO_LARGE"):
        GetExactResourceEvidenceQuery(_OversizedSource()).execute(
            ExactResourceEvidenceRequest(ResourceRef(RESOURCE), VERSION)
        )


def test_adapter_requires_query_only_connection(tmp_path: Path) -> None:
    path = tmp_path / "mutable.sqlite"
    _database(path)
    connection = sqlite3.connect(path)
    try:
        with pytest.raises(ValueError, match="R6_READ_ONLY_REQUIRED"):
            SQLiteExactResourceEvidenceAdapter(connection)
    finally:
        connection.close()
