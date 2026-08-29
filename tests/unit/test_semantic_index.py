from __future__ import annotations

import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest

from backend.adapters.outbound.semantic import (
    ConfiguredEmbeddingService,
    EmbeddingBatchResponse,
    EmbeddingTransportError,
    EmbeddingTransportErrorCode,
    SemanticBackendUnavailable,
    SemanticIndexBuilder,
    SemanticIndexBuildReport,
    SemanticPassage,
    SQLiteSemanticSearchBackend,
    read_semantic_index_manifest,
    source_corpus_sha256,
)
from backend.infrastructure.config.schemas.provider import (
    EmbeddingProfileConfig,
    ModelCode,
    ModelProfileId,
    ProviderCode,
    ProviderProfileConfig,
    ProviderProfileId,
)
from backend.infrastructure.config.secrets.provider import (
    EnvironmentProviderSecretResolver,
    ProviderCredentialRef,
)
from tests.support.semantic_embedding_fakes import (
    RecordingEmbeddingTransport,
    RecordingEmbeddingTransportFactory,
)

SEED_SHA = "38ca8b3fe5c4fd14e9a4cc60a252e7eb03b1f8a8b5fc26ef62251d2b73e35134"


def _passages() -> tuple[SemanticPassage, ...]:
    return (
        SemanticPassage(
            "notion:b",
            "passage:b",
            "sha256:b",
            "NOTION",
            "NOTION_LABEL",
            "Beta",
        ),
        SemanticPassage(
            "notion:a",
            "passage:a",
            "sha256:a",
            "NOTION",
            "NOTION_LABEL",
            "Alpha",
        ),
    )


def _service(transport: RecordingEmbeddingTransport) -> ConfiguredEmbeddingService:
    return ConfiguredEmbeddingService(
        ProviderProfileConfig(
            ProviderProfileId("provider"),
            ProviderCode("openai"),
            ProviderCredentialRef("OPENAI_API_KEY"),
        ),
        EmbeddingProfileConfig(
            ModelProfileId("embedding"),
            ProviderProfileId("provider"),
            ModelCode("text-embedding-3-small"),
            8_192,
            300_000,
            30_000,
            2,
        ),
        EnvironmentProviderSecretResolver({"OPENAI_API_KEY": "synthetic"}),
        RecordingEmbeddingTransportFactory(transport),
    )


def _build(
    path: Path,
    transport: RecordingEmbeddingTransport,
) -> tuple[ConfiguredEmbeddingService, SemanticIndexBuildReport]:
    service = _service(transport)
    report = SemanticIndexBuilder().build(
        passages=_passages(),
        index_path=path,
        canonical_seed_sha256=SEED_SHA,
        embedding_provider_code="openai",
        embedding_service=service,
    )
    return service, report


def test_index_build_is_atomic_compact_and_manifested(tmp_path: Path) -> None:
    path = (tmp_path / "semantic.sqlite").resolve()
    transport = RecordingEmbeddingTransport(
        response=EmbeddingBatchResponse(
            "text-embedding-3-small",
            ((1.0, 0.0), (0.0, 1.0)),
            17,
        )
    )

    _, report = _build(path, transport)

    assert path.is_file()
    assert report.manifest == read_semantic_index_manifest(path)
    assert report.manifest.indexed_chunk_count == 2
    assert report.manifest.vector_dimension == 2
    assert report.manifest.source_corpus_sha256 == source_corpus_sha256(
        _passages()
    )
    with sqlite3.connect(path) as connection:
        lengths = tuple(
            row[0]
            for row in connection.execute(
                "SELECT length(vector_payload) FROM semantic_vector ORDER BY row_key"
            )
        )
        assert lengths == (8, 8)
        assert connection.execute("PRAGMA quick_check").fetchone() == ("ok",)
    assert tuple(tmp_path.glob("*.building")) == ()


def test_projection_includes_general_active_aliases_in_source_checksum() -> None:
    with_alias = replace(_passages()[0], semantic_aliases=("B", "Beta concept"))
    projection_passages = (with_alias, _passages()[1])

    assert source_corpus_sha256(projection_passages) != source_corpus_sha256(
        _passages()
    )


def test_similarity_and_ties_are_deterministic(tmp_path: Path) -> None:
    path = (tmp_path / "semantic.sqlite").resolve()
    transport = RecordingEmbeddingTransport(
        responses=[
            EmbeddingBatchResponse(
                "text-embedding-3-small",
                ((1.0, 0.0), (1.0, 0.0)),
                10,
            ),
            EmbeddingBatchResponse(
                "text-embedding-3-small",
                ((1.0, 0.0),),
                2,
            ),
        ]
    )
    service, report = _build(path, transport)
    backend = SQLiteSemanticSearchBackend(
        index_path=path,
        expected_manifest=report.manifest,
        embedding_service=service,
    )

    hits = backend.search(text="same direction", limit=2)

    assert tuple(hit.canonical_object_ref for hit in hits) == (
        "notion:a",
        "notion:b",
    )
    assert tuple(hit.score for hit in hits) == (1.0, 1.0)


def test_linked_content_score_rolls_up_to_current_notion_passage(
    tmp_path: Path,
) -> None:
    passages = (
        SemanticPassage(
            "content:definition",
            "passage:content",
            "sha256:content",
            "PEDAGOGICAL_CONTENT",
            "PEDAGOGICAL_CONTENT",
            "A coordinated group pursues one common objective.",
            semantic_rollup_refs=("notion:collective",),
        ),
        SemanticPassage(
            "notion:collective",
            "passage:notion",
            "sha256:notion",
            "NOTION",
            "NOTION_LABEL",
            "Collective action",
        ),
    )
    transport = RecordingEmbeddingTransport(
        responses=[
            EmbeddingBatchResponse(
                "text-embedding-3-small",
                ((1.0, 0.0), (0.0, 1.0)),
                8,
            ),
            EmbeddingBatchResponse(
                "text-embedding-3-small",
                ((1.0, 0.0),),
                2,
            ),
        ]
    )
    service = _service(transport)
    path = (tmp_path / "rollup.sqlite").resolve()
    report = SemanticIndexBuilder().build(
        passages=passages,
        index_path=path,
        canonical_seed_sha256=SEED_SHA,
        embedding_provider_code="openai",
        embedding_service=service,
    )
    backend = SQLiteSemanticSearchBackend(
        index_path=path,
        expected_manifest=report.manifest,
        embedding_service=service,
    )

    hits = backend.search(text="shared objective", limit=3)

    notion = next(hit for hit in hits if hit.canonical_object_ref == "notion:collective")
    assert notion.passage_ref == "passage:notion"
    assert notion.score == 1.0
    assert notion.matched_passage_ref == "passage:content"


@pytest.mark.parametrize(
    "field,value",
    [
        ("canonical_seed_sha256", "other-seed"),
        ("embedding_model_code", "text-embedding-3-large"),
        ("vector_dimension", 3),
    ],
)
def test_manifest_mismatch_closes_semantic_channel(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    path = (tmp_path / "semantic.sqlite").resolve()
    service, report = _build(
        path,
        RecordingEmbeddingTransport(
            response=EmbeddingBatchResponse(
                "text-embedding-3-small",
                ((1.0, 0.0), (0.0, 1.0)),
                4,
            )
        ),
    )
    expected = replace(report.manifest, **{field: value})
    backend = SQLiteSemanticSearchBackend(
        index_path=path,
        expected_manifest=expected,
        embedding_service=service,
    )

    with pytest.raises(SemanticBackendUnavailable) as raised:
        backend.search(text="query", limit=2)
    assert raised.value.reason_code == "SEMANTIC_INDEX_STALE_OR_INCOMPATIBLE"


def test_missing_index_and_provider_error_are_closed(tmp_path: Path) -> None:
    missing = (tmp_path / "missing.sqlite").resolve()
    service = _service(RecordingEmbeddingTransport())
    _, expected_report = _build(
        (tmp_path / "expected.sqlite").resolve(),
        RecordingEmbeddingTransport(
            response=EmbeddingBatchResponse(
                "text-embedding-3-small",
                ((1.0, 0.0), (0.0, 1.0)),
                4,
            )
        ),
    )
    backend = SQLiteSemanticSearchBackend(
        index_path=missing,
        expected_manifest=expected_report.manifest,
        embedding_service=service,
    )
    with pytest.raises(SemanticBackendUnavailable) as missing_error:
        backend.search(text="query", limit=2)
    assert missing_error.value.reason_code == "SEMANTIC_INDEX_MISSING"

    path = (tmp_path / "provider.sqlite").resolve()
    build_transport = RecordingEmbeddingTransport(
        response=EmbeddingBatchResponse(
            "text-embedding-3-small",
            ((1.0, 0.0), (0.0, 1.0)),
            4,
        )
    )
    _, report = _build(path, build_transport)
    unavailable_service = _service(
        RecordingEmbeddingTransport(
            error=EmbeddingTransportError(EmbeddingTransportErrorCode.TIMEOUT)
        )
    )
    unavailable = SQLiteSemanticSearchBackend(
        index_path=path,
        expected_manifest=report.manifest,
        embedding_service=unavailable_service,
    )
    with pytest.raises(SemanticBackendUnavailable) as provider_error:
        unavailable.search(text="query", limit=2)
    assert provider_error.value.reason_code == "SEMANTIC_PROVIDER_TIMEOUT"


def test_failed_build_leaves_no_partial_final_or_sidecar(tmp_path: Path) -> None:
    path = (tmp_path / "semantic.sqlite").resolve()
    service = _service(
        RecordingEmbeddingTransport(
            error=EmbeddingTransportError(EmbeddingTransportErrorCode.RATE_LIMIT)
        )
    )

    with pytest.raises(EmbeddingTransportError):
        SemanticIndexBuilder().build(
            passages=_passages(),
            index_path=path,
            canonical_seed_sha256=SEED_SHA,
            embedding_provider_code="openai",
            embedding_service=service,
        )

    assert not path.exists()
    assert tuple(tmp_path.glob("*.building")) == ()
