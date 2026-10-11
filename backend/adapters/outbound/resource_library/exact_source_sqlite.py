from __future__ import annotations

import sqlite3

from backend.modules.resource_library.domain.value_objects import ResourceRef
from backend.modules.resource_library.ports.outbound.exact_resource_evidence import (
    ExactResourceEvidenceRecord,
    ExactResourceLookup,
    ExactResourceLookupStatus,
    ExactResourceQuestionRecord,
)


class SQLiteExactResourceEvidenceAdapter:
    """Read-only SQL mapper for the internal exact-source M03 boundary."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        if not isinstance(connection, sqlite3.Connection):
            raise TypeError("connection must be a sqlite3.Connection")
        query_only = connection.execute("PRAGMA query_only").fetchone()
        if query_only is None or int(query_only[0]) != 1:
            raise ValueError("R6_READ_ONLY_REQUIRED")
        self._connection = connection

    def load_exact_resource(
        self,
        resource_ref: ResourceRef,
        resource_version_ref: str,
    ) -> ExactResourceLookup:
        if type(resource_ref) is not ResourceRef:
            raise TypeError("resource_ref must be a ResourceRef")
        if not isinstance(resource_version_ref, str) or not resource_version_ref:
            raise ValueError("R6_RESOURCE_VERSION_REQUIRED")
        resource_row = self._connection.execute(
            """SELECT id, resource_type, canonical_title, identity_status
               FROM resource WHERE id = ?""",
            (resource_ref.value,),
        ).fetchone()
        if resource_row is None:
            return ExactResourceLookup(ExactResourceLookupStatus.RESOURCE_NOT_FOUND)
        version_row = self._connection.execute(
            """SELECT id, resource_id, lifecycle_status, validation_status, body
               FROM resource_version WHERE id = ?""",
            (resource_version_ref,),
        ).fetchone()
        if version_row is None:
            return ExactResourceLookup(ExactResourceLookupStatus.VERSION_NOT_FOUND)
        if str(version_row[1]) != resource_ref.value:
            return ExactResourceLookup(ExactResourceLookupStatus.VERSION_MISMATCH)
        rows = self._connection.execute(
            """SELECT q.id, eq.position, eq.points_default, q.prompt,
                      c.id, c.body
               FROM exercise_question AS eq
               JOIN question AS q ON q.id = eq.question_id
               JOIN question_correction AS qc ON qc.question_id = q.id
               JOIN correction AS c ON c.id = qc.correction_id
               WHERE eq.exercise_resource_id = ?
               ORDER BY eq.position, q.id, c.id""",
            (resource_ref.value,),
        ).fetchall()
        question_ids = [str(row[0]) for row in rows]
        if len(question_ids) != len(set(question_ids)):
            raise ValueError("R6_RESOURCE_SHAPE_INVALID")
        questions = tuple(
            ExactResourceQuestionRecord(
                question_id=str(row[0]),
                position=int(row[1]),
                points=float(row[2]),
                prompt=str(row[3]),
                correction_id=str(row[4]),
                correction=str(row[5]),
            )
            for row in rows
        )
        return ExactResourceLookup(
            ExactResourceLookupStatus.FOUND,
            ExactResourceEvidenceRecord(
                resource_ref=resource_ref,
                resource_version_ref=str(version_row[0]),
                resource_type=str(resource_row[1]),
                canonical_title=str(resource_row[2]),
                identity_status=str(resource_row[3]),
                resource_lifecycle_status=str(version_row[2]),
                resource_validation_status=str(version_row[3]),
                body=str(version_row[4]),
                questions=questions,
            ),
        )

    def close(self) -> None:
        self._connection.close()
