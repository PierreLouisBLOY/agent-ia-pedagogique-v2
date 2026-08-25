from __future__ import annotations

from collections.abc import Mapping

from backend.agent_runtime.agents.evidence import (
    DocumentContentRequest,
    DocumentContentResult,
    EvidenceContentUnavailable,
    RetrievalChannel,
    RetrievalChannelUnavailable,
    RetrievalQuery,
    RetrievalSearchResult,
)


class RecordingEvidenceSearchPort:
    """Deterministic, provider-free search boundary fake."""

    def __init__(
        self,
        responses: Mapping[
            RetrievalChannel,
            RetrievalSearchResult | RetrievalChannelUnavailable,
        ],
    ) -> None:
        self._responses = dict(responses)
        self.calls: list[tuple[RetrievalQuery, RetrievalChannel]] = []

    def search(
        self,
        *,
        query: RetrievalQuery,
        channel: RetrievalChannel,
    ) -> RetrievalSearchResult:
        self.calls.append((query, channel))
        response = self._responses[channel]
        if isinstance(response, RetrievalChannelUnavailable):
            raise response
        return response


class RecordingDocumentContentPort:
    """Deterministic content fake with one recorded call per explicit fetch."""

    def __init__(
        self,
        responses: Mapping[
            str,
            DocumentContentResult | EvidenceContentUnavailable,
        ],
    ) -> None:
        self._responses = dict(responses)
        self.calls: list[DocumentContentRequest] = []

    def fetch(self, *, request: DocumentContentRequest) -> DocumentContentResult:
        self.calls.append(request)
        response = self._responses[request.candidate_id]
        if isinstance(response, EvidenceContentUnavailable):
            raise response
        return response
