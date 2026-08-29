"""Derived local semantic retrieval adapters."""

from backend.adapters.outbound.semantic.contracts import (
    EmbeddingBatchRequest,
    EmbeddingBatchResponse,
    EmbeddingTransport,
    EmbeddingTransportError,
    EmbeddingTransportErrorCode,
    EmbeddingTransportFactory,
    SemanticBackendUnavailable,
    SemanticHit,
    SemanticPassage,
    SemanticSearchBackend,
)
from backend.adapters.outbound.semantic.index import (
    SEMANTIC_INDEX_SCHEMA_VERSION,
    SEMANTIC_PROJECTION_VERSION,
    SemanticIndexBuilder,
    SemanticIndexBuildReport,
    SemanticIndexManifest,
    SemanticQueryMetrics,
    SQLiteSemanticSearchBackend,
    project_semantic_passage,
    read_semantic_index_manifest,
    source_corpus_sha256,
)
from backend.adapters.outbound.semantic.openai import (
    OpenAISDKEmbeddingTransport,
    OpenAISDKEmbeddingTransportFactory,
)
from backend.adapters.outbound.semantic.service import ConfiguredEmbeddingService

__all__ = [
    "ConfiguredEmbeddingService",
    "EmbeddingBatchRequest",
    "EmbeddingBatchResponse",
    "EmbeddingTransport",
    "EmbeddingTransportError",
    "EmbeddingTransportErrorCode",
    "EmbeddingTransportFactory",
    "OpenAISDKEmbeddingTransport",
    "OpenAISDKEmbeddingTransportFactory",
    "SEMANTIC_INDEX_SCHEMA_VERSION",
    "SEMANTIC_PROJECTION_VERSION",
    "SemanticBackendUnavailable",
    "SemanticHit",
    "SemanticIndexBuildReport",
    "SemanticIndexBuilder",
    "SemanticIndexManifest",
    "SemanticPassage",
    "SemanticQueryMetrics",
    "SemanticSearchBackend",
    "SQLiteSemanticSearchBackend",
    "project_semantic_passage",
    "read_semantic_index_manifest",
    "source_corpus_sha256",
]
