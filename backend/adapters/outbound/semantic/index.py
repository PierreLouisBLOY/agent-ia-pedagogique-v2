"""Versioned rebuildable SQLite sidecar for canonical semantic vectors."""

from __future__ import annotations

import hashlib
import math
import sqlite3
import struct
import time
from dataclasses import dataclass
from pathlib import Path

from backend.adapters.outbound.semantic.contracts import (
    EmbeddingTransportError,
    EmbeddingTransportErrorCode,
    SemanticBackendUnavailable,
    SemanticHit,
    SemanticPassage,
)
from backend.adapters.outbound.semantic.service import ConfiguredEmbeddingService
from backend.infrastructure.filesystem import (
    LocalFileSecurityError,
    assert_local_data_root,
    atomic_replace_checked,
    capture_secure_path,
    ensure_private_directory,
    harden_private_file,
    private_temporary_file,
    resolve_secure_path,
)

SEMANTIC_INDEX_SCHEMA_VERSION = 2
SEMANTIC_PROJECTION_VERSION = "canonical-search-passage-v3"
SEMANTIC_CONTEXT_MAX_UTF8_BYTES = 6_000


@dataclass(frozen=True, slots=True)
class SemanticIndexManifest:
    schema_version: int
    canonical_seed_sha256: str
    embedding_provider_code: str
    embedding_model_code: str
    vector_dimension: int
    projection_version: str
    indexed_chunk_count: int
    source_corpus_sha256: str

    def __post_init__(self) -> None:
        if self.schema_version != SEMANTIC_INDEX_SCHEMA_VERSION:
            raise ValueError("unsupported semantic index schema version")
        for field_name in (
            "canonical_seed_sha256",
            "embedding_provider_code",
            "embedding_model_code",
            "projection_version",
            "source_corpus_sha256",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be a non-empty string")
        if type(self.vector_dimension) is not int or self.vector_dimension <= 0:
            raise ValueError("vector_dimension must be positive")
        if type(self.indexed_chunk_count) is not int or self.indexed_chunk_count <= 0:
            raise ValueError("indexed_chunk_count must be positive")


@dataclass(frozen=True, slots=True)
class SemanticIndexBuildReport:
    manifest: SemanticIndexManifest
    index_size_bytes: int
    build_duration_milliseconds: int
    provider_input_tokens: int
    provider_call_count: int


@dataclass(frozen=True, slots=True)
class SemanticQueryMetrics:
    query_count: int
    provider_input_tokens: int
    latencies_milliseconds: tuple[float, ...]


def project_semantic_passage(passage: SemanticPassage) -> str:
    if type(passage) is not SemanticPassage:
        raise TypeError("passage must be a SemanticPassage")
    projection = (
        f"canonical_object_ref: {passage.canonical_object_ref}\n"
        f"chunk_type: {passage.chunk_type}\n"
        f"content:\n{passage.text}"
    )
    if passage.semantic_aliases:
        projection += (
            "\nactive_canonical_aliases:\n"
            + "\n".join(passage.semantic_aliases)
        )
    if passage.semantic_context is not None:
        projection += (
            "\nlinked_canonical_context:\n"
            + _bounded_utf8(
                passage.semantic_context,
                SEMANTIC_CONTEXT_MAX_UTF8_BYTES,
            )
        )
    return projection


def source_corpus_sha256(passages: tuple[SemanticPassage, ...]) -> str:
    digest = hashlib.sha256()
    for passage in sorted(passages, key=lambda item: item.passage_ref):
        for value in (
            passage.canonical_object_ref,
            passage.passage_ref,
            passage.version_or_checksum,
            passage.object_type,
            passage.chunk_type,
            project_semantic_passage(passage),
            *passage.semantic_rollup_refs,
        ):
            digest.update(value.encode("utf-8"))
            digest.update(b"\0")
    return digest.hexdigest()


class SemanticIndexBuilder:
    def build(
        self,
        *,
        passages: tuple[SemanticPassage, ...],
        index_path: Path,
        canonical_seed_sha256: str,
        embedding_provider_code: str,
        embedding_service: ConfiguredEmbeddingService,
        request_interval_seconds: float = 0.0,
        data_root: Path | None = None,
    ) -> SemanticIndexBuildReport:
        if type(passages) is not tuple or not passages:
            raise ValueError("passages must be a non-empty tuple")
        if any(type(item) is not SemanticPassage for item in passages):
            raise TypeError("passages must contain SemanticPassage values")
        if len({item.passage_ref for item in passages}) != len(passages):
            raise ValueError("passage refs must be unique")
        if not isinstance(index_path, Path):
            raise TypeError("index_path must be a Path")
        if not index_path.is_absolute():
            raise ValueError("index_path must be absolute")
        if not canonical_seed_sha256 or not embedding_provider_code:
            raise ValueError("seed hash and provider code are required")
        if type(embedding_service) is not ConfiguredEmbeddingService:
            raise TypeError("embedding_service must be ConfiguredEmbeddingService")
        if (
            not isinstance(request_interval_seconds, (int, float))
            or isinstance(request_interval_seconds, bool)
            or not 0 <= request_interval_seconds <= 60
        ):
            raise ValueError("request_interval_seconds must be between 0 and 60")

        try:
            root = assert_local_data_root(
                index_path.parent if data_root is None else data_root
            )
            index_path = resolve_secure_path(index_path, allowed_root=root)
            ensure_private_directory(root, allowed_root=root)
            ensure_private_directory(index_path.parent, allowed_root=root)
            expected_destination = capture_secure_path(index_path, allowed_root=root)
        except LocalFileSecurityError as error:
            raise ValueError("semantic index path boundary rejected") from error

        ordered = tuple(sorted(passages, key=lambda item: item.passage_ref))
        projections = tuple(project_semantic_passage(item) for item in ordered)
        batches = embedding_service.batches(projections)
        try:
            temporary_path = private_temporary_file(
                index_path.parent,
                allowed_root=root,
                prefix=f".{index_path.name}.",
                suffix=".building",
            )
        except LocalFileSecurityError as error:
            raise ValueError("semantic index temp boundary rejected") from error
        started = time.perf_counter()
        input_tokens = 0
        dimension: int | None = None
        offset = 0
        connection: sqlite3.Connection | None = None
        try:
            connection = sqlite3.connect(temporary_path, isolation_level=None)
            _create_schema(connection)
            connection.execute("BEGIN IMMEDIATE")
            for batch_index, batch in enumerate(batches):
                if batch_index > 0 and request_interval_seconds > 0:
                    time.sleep(request_interval_seconds)
                response = embedding_service.embed(batch)
                input_tokens += response.input_tokens
                if dimension is None:
                    dimension = response.dimension
                elif response.dimension != dimension:
                    raise ValueError("embedding dimension changed during index build")
                batch_passages = ordered[offset : offset + len(batch)]
                for passage, vector in zip(
                    batch_passages, response.vectors, strict=True
                ):
                    payload, norm = _pack_vector(vector)
                    connection.execute(
                        """INSERT INTO semantic_vector(
                               row_key, canonical_object_ref, passage_ref,
                               version_or_checksum, object_type, chunk_type,
                               vector_payload, vector_norm
                           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            _row_key(passage),
                            passage.canonical_object_ref,
                            passage.passage_ref,
                            passage.version_or_checksum,
                            passage.object_type,
                            passage.chunk_type,
                            payload,
                            norm,
                        ),
                    )
                    for rollup_ref in passage.semantic_rollup_refs:
                        connection.execute(
                            """INSERT INTO semantic_rollup(
                                   row_key, canonical_object_ref
                               ) VALUES (?, ?)""",
                            (_row_key(passage), rollup_ref),
                        )
                offset += len(batch)
            if dimension is None or offset != len(ordered):
                raise ValueError("semantic index build did not cover every passage")
            manifest = SemanticIndexManifest(
                schema_version=SEMANTIC_INDEX_SCHEMA_VERSION,
                canonical_seed_sha256=canonical_seed_sha256,
                embedding_provider_code=embedding_provider_code,
                embedding_model_code=(
                    embedding_service.embedding_profile.model_code.value
                ),
                vector_dimension=dimension,
                projection_version=SEMANTIC_PROJECTION_VERSION,
                indexed_chunk_count=len(ordered),
                source_corpus_sha256=source_corpus_sha256(ordered),
            )
            _insert_manifest(connection, manifest)
            connection.execute("COMMIT")
            if connection.execute("PRAGMA quick_check").fetchone() != ("ok",):
                raise ValueError("semantic index quick_check failed")
            connection.close()
            connection = None
            harden_private_file(temporary_path, allowed_root=root)
            atomic_replace_checked(
                temporary_path,
                index_path,
                allowed_root=root,
                expected_destination=expected_destination,
            )
        except BaseException:
            if connection is not None:
                connection.close()
            temporary_path.unlink(missing_ok=True)
            raise
        duration = round((time.perf_counter() - started) * 1_000)
        verified = read_semantic_index_manifest(index_path, data_root=root)
        if verified != manifest:
            raise ValueError("semantic index manifest verification failed")
        return SemanticIndexBuildReport(
            manifest=manifest,
            index_size_bytes=index_path.stat().st_size,
            build_duration_milliseconds=duration,
            provider_input_tokens=input_tokens,
            provider_call_count=len(batches),
        )


class SQLiteSemanticSearchBackend:
    def __init__(
        self,
        *,
        index_path: Path,
        expected_manifest: SemanticIndexManifest,
        embedding_service: ConfiguredEmbeddingService,
        data_root: Path | None = None,
    ) -> None:
        if not isinstance(index_path, Path) or not index_path.is_absolute():
            raise ValueError("index_path must be an absolute Path")
        if type(expected_manifest) is not SemanticIndexManifest:
            raise TypeError("expected_manifest must be a SemanticIndexManifest")
        if type(embedding_service) is not ConfiguredEmbeddingService:
            raise TypeError("embedding_service must be ConfiguredEmbeddingService")
        try:
            self._data_root = assert_local_data_root(
                index_path.parent if data_root is None else data_root
            )
            self._index_path = resolve_secure_path(
                index_path, allowed_root=self._data_root
            )
        except LocalFileSecurityError as error:
            raise ValueError("semantic index path boundary rejected") from error
        self._expected_manifest = expected_manifest
        self._embedding_service = embedding_service
        self._query_input_tokens = 0
        self._latencies: list[float] = []

    def search(self, *, text: str, limit: int) -> tuple[SemanticHit, ...]:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("text must be a non-empty string")
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        started = time.perf_counter()
        manifest, rows, rollups = self._load_compatible_rows()
        try:
            response = self._embedding_service.embed((text,))
        except EmbeddingTransportError as error:
            raise SemanticBackendUnavailable(
                _provider_unavailable_reason(error.code)
            ) from None
        if response.dimension != manifest.vector_dimension:
            raise SemanticBackendUnavailable(
                "SEMANTIC_INDEX_STALE_OR_INCOMPATIBLE"
            )
        query = response.vectors[0]
        query_norm = math.sqrt(sum(value * value for value in query))
        scored: dict[tuple[str, str], SemanticHit] = {}
        notion_targets = {
            str(row[1]): row
            for row in rows
            if str(row[4]) == "NOTION" and str(row[5]) == "NOTION_LABEL"
        }
        for row in rows:
            vector = _unpack_vector(row[6], manifest.vector_dimension)
            stored_norm = row[7]
            if not isinstance(stored_norm, (int, float)):
                raise SemanticBackendUnavailable(
                    "SEMANTIC_INDEX_STALE_OR_INCOMPATIBLE"
                )
            score = sum(
                left * right for left, right in zip(query, vector, strict=True)
            ) / (query_norm * float(stored_norm))
            bounded = max(-1.0, min(1.0, score))
            direct = SemanticHit(
                canonical_object_ref=str(row[1]),
                passage_ref=str(row[2]),
                version_or_checksum=str(row[3]),
                object_type=str(row[4]),
                chunk_type=str(row[5]),
                score=float(f"{bounded:.12f}"),
            )
            _keep_best_hit(scored, direct)
            for rollup_ref in rollups.get(str(row[0]), ()):
                target = notion_targets.get(rollup_ref)
                if target is None:
                    continue
                _keep_best_hit(
                    scored,
                    SemanticHit(
                        canonical_object_ref=rollup_ref,
                        passage_ref=str(target[2]),
                        version_or_checksum=str(target[3]),
                        object_type=str(target[4]),
                        chunk_type=str(target[5]),
                        score=float(f"{bounded:.12f}"),
                        matched_passage_ref=str(row[2]),
                    ),
                )
        ordered_hits = sorted(
            scored.values(),
            key=lambda hit: (
                -hit.score,
                hit.canonical_object_ref,
                hit.passage_ref,
            )
        )
        self._query_input_tokens += response.input_tokens
        self._latencies.append((time.perf_counter() - started) * 1_000)
        return tuple(ordered_hits[:limit])

    def metrics(self) -> SemanticQueryMetrics:
        return SemanticQueryMetrics(
            query_count=len(self._latencies),
            provider_input_tokens=self._query_input_tokens,
            latencies_milliseconds=tuple(self._latencies),
        )

    def _load_compatible_rows(
        self,
    ) -> tuple[
        SemanticIndexManifest,
        tuple[tuple[object, ...], ...],
        dict[str, tuple[str, ...]],
    ]:
        try:
            before = capture_secure_path(
                self._index_path, allowed_root=self._data_root
            )
        except LocalFileSecurityError:
            raise SemanticBackendUnavailable(
                "SEMANTIC_INDEX_STALE_OR_INCOMPATIBLE"
            ) from None
        if not before.is_file:
            raise SemanticBackendUnavailable("SEMANTIC_INDEX_MISSING")
        try:
            connection = sqlite3.connect(
                f"file:{self._index_path.as_posix()}?mode=ro",
                uri=True,
            )
            opened = capture_secure_path(
                self._index_path, allowed_root=self._data_root
            )
            if not before.same_identity(opened):
                connection.close()
                raise SemanticBackendUnavailable(
                    "SEMANTIC_INDEX_STALE_OR_INCOMPATIBLE"
                )
            manifest = _read_manifest(connection)
            if manifest != self._expected_manifest:
                raise SemanticBackendUnavailable(
                    "SEMANTIC_INDEX_STALE_OR_INCOMPATIBLE"
                )
            rows = tuple(
                connection.execute(
                    """SELECT row_key, canonical_object_ref, passage_ref,
                              version_or_checksum, object_type, chunk_type,
                              vector_payload, vector_norm
                       FROM semantic_vector
                       ORDER BY row_key"""
                ).fetchall()
            )
            rollup_rows = tuple(
                connection.execute(
                    """SELECT row_key, canonical_object_ref
                       FROM semantic_rollup
                       ORDER BY row_key, canonical_object_ref"""
                ).fetchall()
            )
            connection.close()
            after = capture_secure_path(
                self._index_path, allowed_root=self._data_root
            )
            if not before.same_identity(after):
                raise SemanticBackendUnavailable(
                    "SEMANTIC_INDEX_STALE_OR_INCOMPATIBLE"
                )
        except SemanticBackendUnavailable:
            raise
        except (LocalFileSecurityError, OSError, sqlite3.Error, TypeError, ValueError):
            raise SemanticBackendUnavailable(
                "SEMANTIC_INDEX_STALE_OR_INCOMPATIBLE"
            ) from None
        if len(rows) != manifest.indexed_chunk_count:
            raise SemanticBackendUnavailable(
                "SEMANTIC_INDEX_STALE_OR_INCOMPATIBLE"
            )
        rollups: dict[str, list[str]] = {}
        for row_key, canonical_object_ref in rollup_rows:
            rollups.setdefault(str(row_key), []).append(str(canonical_object_ref))
        return (
            manifest,
            rows,
            {key: tuple(values) for key, values in rollups.items()},
        )


def read_semantic_index_manifest(
    index_path: Path, *, data_root: Path | None = None
) -> SemanticIndexManifest:
    if not isinstance(index_path, Path):
        raise ValueError("semantic index path must identify a file")
    try:
        root = assert_local_data_root(
            index_path.parent if data_root is None else data_root
        )
        index_path = resolve_secure_path(index_path, allowed_root=root)
        before = capture_secure_path(index_path, allowed_root=root)
    except LocalFileSecurityError as error:
        raise ValueError("semantic index path boundary rejected") from error
    if not before.is_file:
        raise ValueError("semantic index path must identify a file")
    connection = sqlite3.connect(
        f"file:{index_path.as_posix()}?mode=ro",
        uri=True,
    )
    try:
        opened = capture_secure_path(index_path, allowed_root=root)
        if not before.same_identity(opened):
            raise ValueError("semantic index path identity changed")
        result = _read_manifest(connection)
        after = capture_secure_path(index_path, allowed_root=root)
        if not before.same_identity(after):
            raise ValueError("semantic index path identity changed")
        return result
    finally:
        connection.close()


def _create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE semantic_index_metadata(
            singleton_id INTEGER PRIMARY KEY CHECK(singleton_id = 1),
            schema_version INTEGER NOT NULL,
            canonical_seed_sha256 TEXT NOT NULL,
            embedding_provider_code TEXT NOT NULL,
            embedding_model_code TEXT NOT NULL,
            vector_dimension INTEGER NOT NULL,
            projection_version TEXT NOT NULL,
            indexed_chunk_count INTEGER NOT NULL,
            source_corpus_sha256 TEXT NOT NULL
        );
        CREATE TABLE semantic_vector(
            row_key TEXT PRIMARY KEY,
            canonical_object_ref TEXT NOT NULL,
            passage_ref TEXT NOT NULL UNIQUE,
            version_or_checksum TEXT NOT NULL,
            object_type TEXT NOT NULL,
            chunk_type TEXT NOT NULL,
            vector_payload BLOB NOT NULL,
            vector_norm REAL NOT NULL CHECK(vector_norm > 0)
        );
        CREATE INDEX semantic_vector_identity_idx
            ON semantic_vector(canonical_object_ref, passage_ref);
        CREATE TABLE semantic_rollup(
            row_key TEXT NOT NULL REFERENCES semantic_vector(row_key)
                ON DELETE CASCADE,
            canonical_object_ref TEXT NOT NULL,
            PRIMARY KEY(row_key, canonical_object_ref)
        );
        CREATE INDEX semantic_rollup_identity_idx
            ON semantic_rollup(canonical_object_ref, row_key);
        """
    )


def _insert_manifest(
    connection: sqlite3.Connection,
    manifest: SemanticIndexManifest,
) -> None:
    connection.execute(
        """INSERT INTO semantic_index_metadata VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            1,
            manifest.schema_version,
            manifest.canonical_seed_sha256,
            manifest.embedding_provider_code,
            manifest.embedding_model_code,
            manifest.vector_dimension,
            manifest.projection_version,
            manifest.indexed_chunk_count,
            manifest.source_corpus_sha256,
        ),
    )


def _read_manifest(connection: sqlite3.Connection) -> SemanticIndexManifest:
    row = connection.execute(
        """SELECT schema_version, canonical_seed_sha256,
                  embedding_provider_code, embedding_model_code,
                  vector_dimension, projection_version, indexed_chunk_count,
                  source_corpus_sha256
           FROM semantic_index_metadata WHERE singleton_id = 1"""
    ).fetchone()
    if row is None:
        raise ValueError("semantic index manifest is missing")
    return SemanticIndexManifest(
        schema_version=int(row[0]),
        canonical_seed_sha256=str(row[1]),
        embedding_provider_code=str(row[2]),
        embedding_model_code=str(row[3]),
        vector_dimension=int(row[4]),
        projection_version=str(row[5]),
        indexed_chunk_count=int(row[6]),
        source_corpus_sha256=str(row[7]),
    )


def _row_key(passage: SemanticPassage) -> str:
    payload = "\0".join(
        (
            passage.canonical_object_ref,
            passage.passage_ref,
            passage.version_or_checksum,
        )
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _bounded_utf8(value: str, maximum_bytes: int) -> str:
    encoded = value.encode("utf-8")
    if len(encoded) <= maximum_bytes:
        return value
    return encoded[:maximum_bytes].decode("utf-8", errors="ignore")


def _pack_vector(vector: tuple[float, ...]) -> tuple[bytes, float]:
    if type(vector) is not tuple or not vector:
        raise ValueError("vector must be a non-empty tuple")
    payload = struct.pack(f"<{len(vector)}f", *vector)
    stored = struct.unpack(f"<{len(vector)}f", payload)
    if any(not math.isfinite(value) for value in stored):
        raise ValueError("stored vector contains non-finite values")
    norm = math.sqrt(sum(value * value for value in stored))
    if norm == 0:
        raise ValueError("stored vector has a zero norm")
    return payload, norm


def _unpack_vector(payload: object, dimension: int) -> tuple[float, ...]:
    if not isinstance(payload, bytes) or len(payload) != dimension * 4:
        raise SemanticBackendUnavailable(
            "SEMANTIC_INDEX_STALE_OR_INCOMPATIBLE"
        )
    values = struct.unpack(f"<{dimension}f", payload)
    if any(not math.isfinite(value) for value in values):
        raise SemanticBackendUnavailable(
            "SEMANTIC_INDEX_STALE_OR_INCOMPATIBLE"
        )
    return values


def _provider_unavailable_reason(code: EmbeddingTransportErrorCode) -> str:
    return {
        EmbeddingTransportErrorCode.AUTHENTICATION: (
            "SEMANTIC_PROVIDER_AUTHENTICATION_FAILED"
        ),
        EmbeddingTransportErrorCode.RATE_LIMIT: "SEMANTIC_PROVIDER_RATE_LIMITED",
        EmbeddingTransportErrorCode.TIMEOUT: "SEMANTIC_PROVIDER_TIMEOUT",
        EmbeddingTransportErrorCode.CONNECTION: "SEMANTIC_PROVIDER_UNAVAILABLE",
        EmbeddingTransportErrorCode.SERVER: "SEMANTIC_PROVIDER_UNAVAILABLE",
        EmbeddingTransportErrorCode.UNAVAILABLE: "SEMANTIC_PROVIDER_UNAVAILABLE",
    }[code]


def _keep_best_hit(
    hits: dict[tuple[str, str], SemanticHit],
    candidate: SemanticHit,
) -> None:
    key = (candidate.canonical_object_ref, candidate.passage_ref)
    current = hits.get(key)
    if current is None or candidate.score > current.score:
        hits[key] = candidate
