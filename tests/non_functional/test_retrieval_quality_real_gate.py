from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path

from backend.adapters.outbound.persistence.migrations import inspect_database
from backend.agent_runtime.agents.evidence import EvidenceAgent, RetrievalCoordinator
from backend.infrastructure.composition.factories.sqlite import build_sqlite_runtime
from backend.infrastructure.config.loaders.sqlite import SEED_PATH_ENV
from backend.infrastructure.config.schemas.sqlite import SQLiteDatabasePaths
from backend.shared_kernel.time import Instant
from tests.support.retrieval_quality_cases import (
    CORPUS_SHA256,
    render_benchmark_report,
    run_retrieval_benchmark,
)

EXPECTED_SEED_SIZE = 105_553_920
EXPECTED_SEED_SHA256 = "38ca8b3fe5c4fd14e9a4cc60a252e7eb03b1f8a8b5fc26ef62251d2b73e35134"
MIGRATION = Path("database/migrations/001_document_sha256_check.sql")
TRACKED_REPORT = Path(
    "docs/development/PHASE_12_16_F1_RETRIEVAL_BASELINE_REPORT.json"
)


class _Clock:
    def now(self) -> Instant:
        return Instant(datetime(2026, 8, 28, 10, 0, tzinfo=UTC))


def test_retrieval_quality_real_gate_is_reproducible_on_two_fresh_runtimes(
    tmp_path: Path,
) -> None:
    seed_value = os.environ.get(SEED_PATH_ENV)
    assert seed_value, f"mandatory real gate requires {SEED_PATH_ENV}"
    seed_path = Path(seed_value)
    seed_before = inspect_database(seed_path, authenticate_seed=True)
    assert seed_before.size_bytes == EXPECTED_SEED_SIZE
    assert seed_before.sha256 == EXPECTED_SEED_SHA256
    assert seed_before.integrity == "ok"
    assert seed_before.quick == "ok"
    assert seed_before.foreign_key_violations == 0

    rendered_runs = []
    for run_index in (1, 2):
        runtime_path = tmp_path / f"retrieval-quality-{run_index}.sqlite"
        composition = build_sqlite_runtime(
            SQLiteDatabasePaths(seed_path, runtime_path), MIGRATION
        )
        search = composition.evidence_search()
        content = composition.evidence_document_content(_Clock())
        try:
            report = run_retrieval_benchmark(
                EvidenceAgent(RetrievalCoordinator(search), content),
                seed_sha256=seed_before.sha256,
                seed_size_bytes=seed_before.size_bytes,
            )
            assert report["corpus"]["sha256"] == CORPUS_SHA256
            assert report["exact_label_misses"] == []
            assert report["decision"]["exact_label_gate"] == "PASS"
            rendered_runs.append(render_benchmark_report(report))
        finally:
            search.close()
            content.close()
            _remove_runtime_files(runtime_path)
        assert not runtime_path.exists()

    assert rendered_runs[0] == rendered_runs[1]
    assert json.loads(TRACKED_REPORT.read_text(encoding="utf-8")) == json.loads(
        rendered_runs[0]
    )
    assert inspect_database(seed_path, authenticate_seed=True) == seed_before


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
