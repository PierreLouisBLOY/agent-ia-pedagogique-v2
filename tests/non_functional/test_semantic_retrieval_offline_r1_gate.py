from __future__ import annotations

import json
import os
import time
import unicodedata
from datetime import UTC, datetime
from pathlib import Path

import pytest

from backend.adapters.outbound.persistence.migrations import inspect_database
from backend.adapters.outbound.semantic import SemanticHit, SemanticPassage
from backend.agent_runtime.agents.evidence import EvidenceAgent, RetrievalCoordinator
from backend.infrastructure.composition.factories.sqlite import build_sqlite_runtime
from backend.infrastructure.config.loaders.sqlite import SEED_PATH_ENV
from backend.infrastructure.config.schemas.sqlite import SQLiteDatabasePaths
from backend.shared_kernel.time import Instant
from tests.support.retrieval_quality_cases import CORPUS_SHA256, corpus_sha256
from tests.support.semantic_retrieval_benchmark import (
    run_semantic_retrieval_benchmark,
)

EXPECTED_SEED_SIZE = 105_553_920
EXPECTED_SEED_SHA256 = (
    "38ca8b3fe5c4fd14e9a4cc60a252e7eb03b1f8a8b5fc26ef62251d2b73e35134"
)
MIGRATION = Path("database/migrations/001_document_sha256_check.sql")
OFFLINE_FLAG = "RUN_F2B_OFFLINE_R1"
REPORT_PATH_ENV = "F2B_OFFLINE_R1_REPORT_PATH"
SI_TARGET = "notion:systeme-dinformation"


class _Clock:
    def now(self) -> Instant:
        return Instant(datetime(2026, 8, 29, 10, 0, tzinfo=UTC))


class _CanonicalAliasProbeBackend:
    """Test-only probe for canonical alias expansion before live embeddings."""

    def __init__(self, passages: tuple[SemanticPassage, ...]) -> None:
        labels: dict[str, list[SemanticPassage]] = {}
        for passage in passages:
            if passage.object_type == "NOTION" and passage.chunk_type == "NOTION_LABEL":
                labels.setdefault(_normalized(passage.text), []).append(passage)
        self._labels = {
            label: values[0]
            for label, values in labels.items()
            if len(values) == 1
        }

    def search(self, *, text: str, limit: int) -> tuple[SemanticHit, ...]:
        marker = "\nresolved_canonical_alias: "
        if marker not in text or limit <= 0:
            return ()
        passage = self._labels.get(_normalized(text.split(marker, 1)[1]))
        if passage is None:
            return ()
        return (
            SemanticHit(
                canonical_object_ref=passage.canonical_object_ref,
                passage_ref=passage.passage_ref,
                version_or_checksum=passage.version_or_checksum,
                object_type=passage.object_type,
                chunk_type=passage.chunk_type,
                score=1.0,
            ),
        )


def test_offline_r1_preserves_all_f2a_recoveries_with_canonical_aliases(
    tmp_path: Path,
) -> None:
    if os.environ.get(OFFLINE_FLAG) != "1":
        pytest.skip(f"explicit offline gate requires {OFFLINE_FLAG}=1")
    seed_value = os.environ.get(SEED_PATH_ENV)
    assert seed_value, f"offline gate requires {SEED_PATH_ENV}"
    seed_path = Path(seed_value)
    seed_before = inspect_database(seed_path, authenticate_seed=True)
    assert seed_before.size_bytes == EXPECTED_SEED_SIZE
    assert seed_before.sha256 == EXPECTED_SEED_SHA256
    assert seed_before.integrity == "ok"
    assert seed_before.quick == "ok"
    assert seed_before.foreign_key_violations == 0
    assert corpus_sha256() == CORPUS_SHA256

    runtime_path = (tmp_path / "f2b-r1-runtime.sqlite").resolve()
    composition = build_sqlite_runtime(
        SQLiteDatabasePaths(seed_path, runtime_path),
        MIGRATION,
    )
    passages = composition.semantic_passages()
    si_passage = next(
        passage
        for passage in passages
        if passage.canonical_object_ref == SI_TARGET
        and passage.chunk_type == "NOTION_LABEL"
    )
    assert "SI" in si_passage.semantic_aliases

    search = composition.evidence_search(_CanonicalAliasProbeBackend(passages))
    content = composition.evidence_document_content(_Clock())
    try:
        quality = run_semantic_retrieval_benchmark(
            EvidenceAgent(RetrievalCoordinator(search), content)
        )
    finally:
        search.close()
        content.close()
        _remove_runtime_files(runtime_path)

    gates = quality["gates"]
    assert gates["exact_label_combined_recall_at_5"] == 1.0
    assert gates["f2a_lexical_recovered_case_count"] == 16
    assert gates["f2a_lexical_recovered_preserved_count"] == 16
    si_outcome = next(
        item
        for item in quality["outcomes"]
        if item["case_id"] == "RQ-SYSTEME-INFORMATION-D"
    )
    assert si_outcome["lexical_rank"] == 5
    assert si_outcome["semantic_rank"] == 1
    assert si_outcome["combined_rank"] is not None
    assert si_outcome["combined_rank"] <= 5

    seed_after = inspect_database(seed_path, authenticate_seed=True)
    assert seed_after == seed_before
    report_value = os.environ.get(REPORT_PATH_ENV)
    if report_value:
        report_path = Path(report_value)
        assert report_path.is_absolute(), f"{REPORT_PATH_ENV} must be absolute"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(
                {
                    "benchmark": "PHASE_12_16_F2B_R1_OFFLINE",
                    "canonical_alias": {
                        "alias": "SI",
                        "canonical_object_ref": SI_TARGET,
                        "canonical_label": si_passage.text,
                        "status": "ACTIVE",
                    },
                    "corpus": quality["corpus"],
                    "gates": gates,
                    "si_outcome": si_outcome,
                    "seed": {
                        "sha256": seed_before.sha256,
                        "size_bytes": seed_before.size_bytes,
                        "unchanged_after": seed_after == seed_before,
                    },
                    "status": "PASS",
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )


def _normalized(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(
        character
        for character in decomposed
        if character.isalnum()
    ).casefold()


def _remove_runtime_files(runtime_path: Path) -> None:
    paths = (
        runtime_path.with_name(runtime_path.name + "-wal"),
        runtime_path.with_name(runtime_path.name + "-shm"),
        runtime_path,
    )
    for attempt in range(20):
        try:
            for path in paths:
                path.unlink(missing_ok=True)
            return
        except PermissionError:
            if attempt == 19:
                raise
            time.sleep(0.05)
