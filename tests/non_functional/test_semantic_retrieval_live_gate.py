from __future__ import annotations

import json
import math
import os
import statistics
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import pytest

from backend.adapters.outbound.persistence.migrations import inspect_database
from backend.adapters.outbound.semantic import (
    SemanticIndexBuilder,
    SemanticPassage,
    project_semantic_passage,
    source_corpus_sha256,
)
from backend.agent_runtime.agents.evidence import EvidenceAgent, RetrievalCoordinator
from backend.infrastructure.composition.factories.openai import (
    build_openai_embedding_service,
)
from backend.infrastructure.composition.factories.semantic import (
    build_sqlite_semantic_search_backend,
)
from backend.infrastructure.composition.factories.sqlite import build_sqlite_runtime
from backend.infrastructure.config.effective_config.provider import (
    EffectiveProviderConfiguration,
    build_effective_provider_configuration,
)
from backend.infrastructure.config.loaders.sqlite import SEED_PATH_ENV
from backend.infrastructure.config.schemas.provider import (
    EmbeddingProfileConfig,
    ModelCode,
    ModelProfileId,
    ProviderCode,
    ProviderConfiguration,
    ProviderConfigurationVersion,
    ProviderProfileConfig,
    ProviderProfileId,
    ProviderRouteConfig,
    ProviderWorkloadKind,
)
from backend.infrastructure.config.schemas.sqlite import SQLiteDatabasePaths
from backend.infrastructure.config.secrets.provider import (
    EnvironmentProviderSecretResolver,
    ProviderCredentialRef,
)
from backend.shared_kernel.time import Instant
from tests.support.retrieval_quality_cases import CORPUS_SHA256, corpus_sha256
from tests.support.semantic_retrieval_benchmark import (
    run_semantic_retrieval_benchmark,
)

EXPECTED_SEED_SIZE = 227_557_376
EXPECTED_SEED_SHA256 = "9d64d15e9c246924edeff16e7bbb5fb7a53791fc2ddf217541824771b34053e1"
MIGRATION = Path("database/migrations/001_document_sha256_check.sql")
LIVE_FLAG = "RUN_F2B_LIVE_SEMANTIC_BENCHMARK"
REPORT_PATH_ENV = "F2B_LIVE_REPORT_PATH"
MODEL_FILTER_ENV = "F2B_LIVE_MODEL"
TESTED_DIMENSION = 256
MODEL_FACTS = (
    ("text-embedding-3-small", 1_536, 0.02),
    ("text-embedding-3-large", 3_072, 0.13),
)


class _Clock:
    def now(self) -> Instant:
        return Instant(datetime(2026, 8, 29, 10, 0, tzinfo=UTC))


def test_live_selected_semantic_model(tmp_path: Path) -> None:
    if os.environ.get(LIVE_FLAG) != "1":
        pytest.skip(f"explicit live gate requires {LIVE_FLAG}=1")
    seed_value = os.environ.get(SEED_PATH_ENV)
    report_value = os.environ.get(REPORT_PATH_ENV)
    assert seed_value, f"live gate requires {SEED_PATH_ENV}"
    assert report_value, f"live gate requires {REPORT_PATH_ENV}"
    report_path = Path(report_value)
    assert report_path.is_absolute(), f"{REPORT_PATH_ENV} must be absolute"
    assert corpus_sha256() == CORPUS_SHA256
    model_filter = os.environ.get(MODEL_FILTER_ENV)
    selected_model_facts = tuple(
        facts
        for facts in MODEL_FACTS
        if model_filter is None or facts[0] == model_filter
    )
    assert selected_model_facts, f"{MODEL_FILTER_ENV} must select a known model"

    resolver = EnvironmentProviderSecretResolver(os.environ)
    resolver.resolve(ProviderCredentialRef("OPENAI_API_KEY"))
    seed_path = Path(seed_value)
    seed_before = inspect_database(seed_path, authenticate_seed=True)
    assert seed_before.size_bytes == EXPECTED_SEED_SIZE
    assert seed_before.sha256 == EXPECTED_SEED_SHA256
    assert seed_before.integrity == "ok"
    assert seed_before.quick == "ok"
    assert seed_before.foreign_key_violations == 0

    runtime_path = (tmp_path / "f2b-runtime.sqlite").resolve()
    composition = build_sqlite_runtime(
        SQLiteDatabasePaths(seed_path, runtime_path),
        MIGRATION,
    )
    passages = composition.semantic_passages()
    model_reports: dict[str, object] = {}
    index_paths: list[Path] = []
    try:
        for model_code, default_dimension, price_per_million in selected_model_facts:
            service = build_openai_embedding_service(
                configuration=_configuration(model_code),
                secret_resolver=resolver,
            )
            index_path = (tmp_path / f"{model_code}.semantic.sqlite").resolve()
            index_paths.append(index_path)
            request_interval_seconds = 10.0
            build = SemanticIndexBuilder().build(
                passages=passages,
                index_path=index_path,
                canonical_seed_sha256=seed_before.sha256,
                    embedding_provider_code="openai",
                    embedding_service=service,
                request_interval_seconds=request_interval_seconds,
                )
            semantic = build_sqlite_semantic_search_backend(
                index_path=index_path,
                canonical_seed_sha256=seed_before.sha256,
                passages=passages,
                embedding_service=service,
            )
            search = composition.evidence_search(semantic)
            content = composition.evidence_document_content(_Clock())
            started = time.perf_counter()
            try:
                quality = run_semantic_retrieval_benchmark(
                    EvidenceAgent(RetrievalCoordinator(search), content)
                )
            finally:
                duration_milliseconds = round(
                    (time.perf_counter() - started) * 1_000
                )
                search.close()
                content.close()
            query_metrics = semantic.metrics()
            provider_tokens = (
                build.provider_input_tokens
                + query_metrics.provider_input_tokens
            )
            model_reports[model_code] = {
                "build": {
                    "duration_milliseconds": build.build_duration_milliseconds,
                    "index_size_bytes": build.index_size_bytes,
                    "provider_call_count": build.provider_call_count,
                    "provider_input_tokens": build.provider_input_tokens,
                    "request_interval_seconds": request_interval_seconds,
                },
                "cost": {
                    "estimated_usd": round(
                        provider_tokens * price_per_million / 1_000_000,
                        8,
                    ),
                    "official_usd_per_million_input_tokens": price_per_million,
                },
                "default_dimension": default_dimension,
                "quality": quality,
                "query": {
                    "benchmark_duration_milliseconds": duration_milliseconds,
                    "latency_median_milliseconds": round(
                        statistics.median(query_metrics.latencies_milliseconds),
                        3,
                    ),
                    "latency_p95_milliseconds": round(
                        _percentile(query_metrics.latencies_milliseconds, 0.95),
                        3,
                    ),
                    "provider_input_tokens": query_metrics.provider_input_tokens,
                    "query_count": query_metrics.query_count,
                },
                "tested_dimension": build.manifest.vector_dimension,
                "total_provider_input_tokens": provider_tokens,
            }
            index_path.unlink()
            index_paths.remove(index_path)

        seed_after = inspect_database(seed_path, authenticate_seed=True)
        assert seed_after == seed_before
        report = {
            "benchmark": "PHASE_12_16_F2B_SEMANTIC_RETRIEVAL",
            "corpus": {
                "case_count": 60,
                "sha256": corpus_sha256(),
                "version": "12.16-f1-v1",
            },
            "dimensions": {
                "reduction_reason": (
                    "Default payload estimates make pure-standard-library cosine "
                    "scans 6x/12x larger; 256 dimensions are tested on all 60 cases."
                ),
                "tested": TESTED_DIMENSION,
            },
            "models": model_reports,
            "requested_models": tuple(item[0] for item in selected_model_facts),
            "seed": {
                "foreign_key_violations": seed_before.foreign_key_violations,
                "integrity": seed_before.integrity,
                "quick": seed_before.quick,
                "sha256": seed_before.sha256,
                "size_bytes": seed_before.size_bytes,
                "unchanged_after": seed_after == seed_before,
            },
            "sizing": _sizing(passages),
        }
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        for model_code, model_report in model_reports.items():
            assert isinstance(model_report, dict)
            query_report = model_report["query"]
            assert isinstance(query_report, dict)
            assert query_report["query_count"] == 60, model_code
            quality = model_report["quality"]
            assert isinstance(quality, dict)
            gates = quality["gates"]
            assert isinstance(gates, dict)
            assert gates["exact_label_combined_recall_at_5"] == 1.0, model_code
            assert gates["f2a_lexical_recovered_case_count"] == 16, model_code
            assert gates["f2a_lexical_recovered_preserved_count"] == 16, model_code
            assert gates["semantic_gap_recovered_by_semantic_count"] >= 3, model_code
            assert gates["semantic_gap_recovered_by_combined_count"] >= 3, model_code
    finally:
        for index_path in index_paths:
            index_path.unlink(missing_ok=True)
        _remove_runtime_files(runtime_path)
    assert all(not path.exists() for path in index_paths)
    assert inspect_database(seed_path, authenticate_seed=True) == seed_before


def _configuration(model_code: str) -> EffectiveProviderConfiguration:
    provider_id = ProviderProfileId("openai-semantic-provider")
    model_id = ModelProfileId(f"openai-{model_code}")
    return build_effective_provider_configuration(
        ProviderConfiguration(
            ProviderConfigurationVersion(1, 1),
            (
                ProviderProfileConfig(
                    provider_id,
                    ProviderCode("openai"),
                    ProviderCredentialRef("OPENAI_API_KEY"),
                ),
            ),
            (),
            (
                ProviderRouteConfig(
                    ProviderWorkloadKind.SEMANTIC_EMBEDDING,
                    model_id,
                ),
            ),
            (
                EmbeddingProfileConfig(
                    model_id,
                    provider_id,
                    ModelCode(model_code),
                    8_192,
                    300_000,
                    120_000,
                    TESTED_DIMENSION,
                    1,
                ),
            ),
        )
    )


def _sizing(passages: tuple[SemanticPassage, ...]) -> dict[str, object]:
    text_values = tuple(item.text for item in passages)
    projection_values = tuple(project_semantic_passage(item) for item in passages)
    char_lengths = tuple(sorted(len(value) for value in text_values))
    byte_lengths = tuple(sorted(len(value.encode("utf-8")) for value in text_values))
    count = len(passages)
    return {
        "chunk_count": count,
        "counts_by_chunk_type": dict(
            sorted(Counter(item.chunk_type for item in passages).items())
        ),
        "counts_by_object_type": dict(
            sorted(Counter(item.object_type for item in passages).items())
        ),
        "length_chars": _distribution(char_lengths),
        "length_utf8_bytes": _distribution(byte_lengths),
        "oversized_conservative_utf8_count": sum(
            length > 8_192 for length in byte_lengths
        ),
        "projection_utf8_bytes": _distribution(
            tuple(sorted(len(value.encode("utf-8")) for value in projection_values))
        ),
        "projection_over_8192_conservative_utf8_count": sum(
            len(value.encode("utf-8")) > 8_192 for value in projection_values
        ),
        "semantic_rollup_edge_count": sum(
            len(item.semantic_rollup_refs) for item in passages
        ),
        "source_corpus_sha256": source_corpus_sha256(passages),
        "total_chars": sum(char_lengths),
        "total_utf8_bytes": sum(byte_lengths),
        "unique_canonical_object_count": len(
            {item.canonical_object_ref for item in passages}
        ),
        "vector_payload_estimates_bytes": {
            "256": count * 256 * 4,
            "1536": count * 1_536 * 4,
            "3072": count * 3_072 * 4,
        },
    }


def _distribution(values: tuple[int, ...]) -> dict[str, int | float]:
    return {
        "max": values[-1],
        "median": statistics.median(values),
        "min": values[0],
        "p95": _percentile(values, 0.95),
    }


def _percentile(values: tuple[int | float, ...], percentile: float) -> int | float:
    ordered = tuple(sorted(values))
    index = max(0, math.ceil(len(ordered) * percentile) - 1)
    return ordered[index]


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
