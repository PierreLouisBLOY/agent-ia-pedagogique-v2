"""Real CP645 acceptance: no synthetic seed or provider substitutes."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

import pytest

from backend.adapters.outbound.persistence.migrations import (
    CANONICAL_SEED_SHA256,
    CANONICAL_SEED_SIZE,
    snapshot_sqlite_files,
)
from backend.adapters.outbound.persistence.sqlite import connect_sqlite
from backend.agent_runtime.agents.evidence import (
    DocumentContentRequest,
    RetrievalChannel,
    RetrievalQuery,
)
from backend.infrastructure.composition.factories.sqlite import (
    SQLiteRuntimeComposition,
    build_sqlite_runtime,
)
from backend.infrastructure.config.loaders.sqlite import SEED_PATH_ENV
from backend.infrastructure.config.schemas.sqlite import SQLiteDatabasePaths
from backend.shared_kernel.time import Instant

MIGRATION = Path("database/migrations/001_document_sha256_check.sql")
NOTIONS = (
    ("Besoin en fonds de roulement (BFR)", "notion:besoin-en-fonds-de-roulement-bfr"),
    ("Fonds de roulement net global (FRNG)", "notion:fonds-de-roulement-net-global-frng"),
    ("Bilan fonctionnel", "notion:bilan-fonctionnel"),
    ("Productivité", "notion:productivite"),
    ("Système d’information", "notion:systeme-dinformation"),
    ("Besoins de recrutement", "notion:besoins-de-recrutement"),
    ("Contrat", "notion:contrat"),
    ("Démarche marketing", "notion:demarche-marketing"),
)


class _Clock:
    def now(self) -> Instant:
        return Instant(datetime(2026, 9, 21, tzinfo=UTC))


@pytest.fixture(scope="module")
def cp645_runtime(
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[SQLiteRuntimeComposition]:
    value = os.environ.get(SEED_PATH_ENV)
    assert value, "CANONICAL_SEED_REQUIRED"
    seed = Path(value)
    before = snapshot_sqlite_files(seed)
    # Authenticate before any SQLite open, not only after inventory inspection.
    assert before.main.size_bytes == CANONICAL_SEED_SIZE
    assert before.main.sha256 == CANONICAL_SEED_SHA256
    runtime = tmp_path_factory.mktemp("cp645-evidence") / "runtime.sqlite"
    composition = build_sqlite_runtime(SQLiteDatabasePaths(seed, runtime), MIGRATION)
    assert composition.readiness.migration_versions == ("001", "002")
    try:
        yield composition
    finally:
        assert snapshot_sqlite_files(seed) == before


@pytest.mark.parametrize(("label", "reference"), NOTIONS)
@pytest.mark.parametrize("channel", (RetrievalChannel.STRUCTURED, RetrievalChannel.LEXICAL))
def test_cp645_notion_is_retrieved_admitted_and_materialized(
    cp645_runtime: SQLiteRuntimeComposition,
    label: str,
    reference: str,
    channel: RetrievalChannel,
) -> None:
    # OP-11 accepts FTS5 expressions on the lexical channel. Parentheses in
    # canonical labels must remain literal, not become query operators.
    text = '"' + label.replace('"', '""') + '"' if channel == RetrievalChannel.LEXICAL else label
    query = RetrievalQuery(text, {}, {"kinds": ("canonical",)}, {"active": True}, None, 20)
    search = cp645_runtime.evidence_search()
    content = cp645_runtime.evidence_document_content(_Clock())
    try:
        result = search.search(query=query, channel=channel)
        candidates = [item for item in result.candidates if item.source_ref == reference]
        assert candidates, (channel, reference)
        candidate = candidates[0]
        assert search.is_admissible(candidate=candidate, query=query)
        assert candidate.version_or_checksum
        assert candidate.authority["absolute"] is False
        fragment = content.fetch(
            request=DocumentContentRequest(
                candidate_id=candidate.candidate_id,
                source_ref=reference,
                locator=candidate.locator,
                source_policy=query.source_policy,
            )
        )
        assert fragment.source_ref == reference
        assert fragment.locator == candidate.locator
        assert fragment.version_or_checksum == candidate.version_or_checksum
        assert fragment.content
        assert fragment.metadata["trust"] == "UNTRUSTED_CONTENT"
        assert "path" not in fragment.provenance
    finally:
        search.close()
        content.close()


def test_cp645_real_content_counts_and_formula_validations_survive_migrations(
    cp645_runtime: SQLiteRuntimeComposition,
) -> None:
    with closing(
        connect_sqlite(cp645_runtime.paths.runtime_database_path, readonly=True)
    ) as connection:
        assert connection.execute(
            "SELECT count(*) FROM notion WHERE identity_status = 'CANONICAL'"
        ).fetchone()[0] == 628
        assert connection.execute("SELECT count(*) FROM document").fetchone()[0] == 67
        assert connection.execute("SELECT count(*) FROM formula").fetchone()[0] == 210
        assert connection.execute(
            "SELECT count(*) FROM formula WHERE lifecycle_status = 'APPROVED'"
        ).fetchone()[0] == 210
        assert connection.execute(
            "SELECT count(DISTINCT v.object_id) FROM validation_event v "
            "JOIN formula f ON f.id = v.object_id "
            "WHERE v.validation_type = 'PEDAGOGICAL_OWNER_APPROVAL' AND v.result = 'APPROVED'"
        ).fetchone()[0] == 210
        assert connection.execute(
            "SELECT count(*) FROM formula_v1_validation_event"
        ).fetchone()[0] == 3
