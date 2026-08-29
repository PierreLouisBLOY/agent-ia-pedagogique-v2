"""Composition of the configured derived SQLite semantic search backend."""

from __future__ import annotations

from pathlib import Path

from backend.adapters.outbound.semantic import (
    SEMANTIC_INDEX_SCHEMA_VERSION,
    SEMANTIC_PROJECTION_VERSION,
    ConfiguredEmbeddingService,
    SemanticIndexManifest,
    SemanticPassage,
    SQLiteSemanticSearchBackend,
    read_semantic_index_manifest,
    source_corpus_sha256,
)


def build_sqlite_semantic_search_backend(
    *,
    index_path: Path,
    canonical_seed_sha256: str,
    passages: tuple[SemanticPassage, ...],
    embedding_service: ConfiguredEmbeddingService,
) -> SQLiteSemanticSearchBackend:
    actual = read_semantic_index_manifest(index_path)
    configured_dimension = (
        embedding_service.embedding_profile.requested_dimensions
    )
    expected = SemanticIndexManifest(
        schema_version=SEMANTIC_INDEX_SCHEMA_VERSION,
        canonical_seed_sha256=canonical_seed_sha256,
        embedding_provider_code=(
            embedding_service.provider_profile.provider_code.value
        ),
        embedding_model_code=(
            embedding_service.embedding_profile.model_code.value
        ),
        vector_dimension=(
            configured_dimension
            if configured_dimension is not None
            else actual.vector_dimension
        ),
        projection_version=SEMANTIC_PROJECTION_VERSION,
        indexed_chunk_count=len(passages),
        source_corpus_sha256=source_corpus_sha256(passages),
    )
    return SQLiteSemanticSearchBackend(
        index_path=index_path,
        expected_manifest=expected,
        embedding_service=embedding_service,
    )
