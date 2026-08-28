from __future__ import annotations

from typing import Protocol, runtime_checkable

from backend.agent_runtime.agents.evidence.retrieval_model import (
    DocumentContentRequest,
    DocumentContentResult,
    RetrievalCandidate,
    RetrievalChannel,
    RetrievalQuery,
    RetrievalSearchResult,
)


@runtime_checkable
class EvidenceSearchPort(Protocol):
    def search(
        self,
        *,
        query: RetrievalQuery,
        channel: RetrievalChannel,
    ) -> RetrievalSearchResult:
        ...


@runtime_checkable
class EvidenceAdmissibilityPort(Protocol):
    """Independent canonical admission gate for retrieved candidates."""

    def is_admissible(
        self,
        *,
        candidate: RetrievalCandidate,
        query: RetrievalQuery,
    ) -> bool:
        ...


@runtime_checkable
class EvidenceDocumentContentPort(Protocol):
    def fetch(
        self,
        *,
        request: DocumentContentRequest,
    ) -> DocumentContentResult:
        ...
