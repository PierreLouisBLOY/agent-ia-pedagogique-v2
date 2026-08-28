from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from backend.agent_runtime.agents.evidence.retrieval_coordination_model import (
    BASELINE_RETRIEVAL_COORDINATION_POLICY,
    FusedRetrievalCandidate,
    RetrievalChannelUnavailable,
    RetrievalCoordinationError,
    RetrievalCoordinationErrorCode,
    RetrievalCoordinationMode,
    RetrievalCoordinationPolicy,
    RetrievalCoordinationResult,
    RetrievalIdentity,
)
from backend.agent_runtime.agents.evidence.retrieval_model import (
    RetrievalCandidate,
    RetrievalChannel,
    RetrievalQuery,
    RetrievalSearchResult,
)
from backend.agent_runtime.agents.evidence.retrieval_ports import (
    EvidenceAdmissibilityPort,
    EvidenceSearchPort,
)
from backend.agent_runtime.contracts.evidence import EvidenceRequest

_CHANNEL_EXECUTION_ORDER = (
    RetrievalChannel.STRUCTURED,
    RetrievalChannel.LEXICAL,
    RetrievalChannel.RELATIONAL,
    RetrievalChannel.SEMANTIC,
)


@dataclass(frozen=True, slots=True)
class RetrievalCoordinator:
    search_port: EvidenceSearchPort
    policy: RetrievalCoordinationPolicy = BASELINE_RETRIEVAL_COORDINATION_POLICY
    admissibility_port: EvidenceAdmissibilityPort | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.search_port, EvidenceSearchPort):
            raise TypeError("search_port must implement EvidenceSearchPort")
        if not isinstance(self.policy, RetrievalCoordinationPolicy):
            raise TypeError("policy must be a RetrievalCoordinationPolicy")
        if self.admissibility_port is not None and not isinstance(
            self.admissibility_port, EvidenceAdmissibilityPort
        ):
            raise TypeError(
                "admissibility_port must implement EvidenceAdmissibilityPort"
            )

    def coordinate(self, *, request: EvidenceRequest) -> RetrievalCoordinationResult:
        if type(request) is not EvidenceRequest:
            raise TypeError("request must be an EvidenceRequest")
        base_query = RetrievalQuery.from_evidence_request(request)
        if request.max_items == 0:
            return RetrievalCoordinationResult(
                query=base_query,
                mode=RetrievalCoordinationMode.FULL,
                ranked_candidates=(),
                channel_results=(),
                unavailable_channels=(),
                limitations=(),
            )

        channel_max = min(
            self.policy.channel_limit,
            request.max_items
            if request.max_items is not None
            else self.policy.channel_limit,
        )
        query = RetrievalQuery(
            search_goal=base_query.search_goal,
            scope=base_query.scope,
            source_policy=base_query.source_policy,
            filters=base_query.filters,
            required_authority=base_query.required_authority,
            max_items=channel_max,
        )
        channel_results, unavailable_channels, limitations = self._search_channels(query)
        ranked_candidates, dropped_limitations = self._fuse_and_rank(
            request=request,
            query=query,
            channel_results=channel_results,
        )
        limitations.extend(dropped_limitations)
        return RetrievalCoordinationResult(
            query=query,
            mode=(
                RetrievalCoordinationMode.DEGRADED
                if unavailable_channels
                else RetrievalCoordinationMode.FULL
            ),
            ranked_candidates=ranked_candidates,
            channel_results=tuple(channel_results),
            unavailable_channels=tuple(unavailable_channels),
            limitations=tuple(limitations),
        )

    def _search_channels(
        self,
        query: RetrievalQuery,
    ) -> tuple[
        list[RetrievalSearchResult],
        list[RetrievalChannel],
        list[str],
    ]:
        results: list[RetrievalSearchResult] = []
        unavailable: list[RetrievalChannel] = []
        limitations: list[str] = []
        enabled = frozenset(self.policy.enabled_channels)
        required = frozenset(self.policy.required_channels)

        for channel in _CHANNEL_EXECUTION_ORDER:
            if channel not in enabled:
                continue
            try:
                result = self.search_port.search(query=query, channel=channel)
            except RetrievalChannelUnavailable as error:
                if error.channel is not channel:
                    raise RetrievalCoordinationError(
                        RetrievalCoordinationErrorCode.INVALID_CHANNEL_RESULT,
                        f"channel {channel.value} reported mismatched unavailability",
                    ) from None
                if channel in required:
                    raise RetrievalCoordinationError(
                        RetrievalCoordinationErrorCode.REQUIRED_CHANNEL_UNAVAILABLE,
                        f"required channel unavailable: {channel.value}",
                    ) from None
                unavailable.append(channel)
                limitations.append(f"CHANNEL_UNAVAILABLE:{channel.value}")
                continue
            self._validate_result(result, channel, query)
            results.append(result)

        return results, unavailable, limitations

    def _validate_result(
        self,
        result: RetrievalSearchResult,
        requested_channel: RetrievalChannel,
        query: RetrievalQuery,
    ) -> None:
        if type(result) is not RetrievalSearchResult or result.channel is not requested_channel:
            raise RetrievalCoordinationError(
                RetrievalCoordinationErrorCode.INVALID_CHANNEL_RESULT,
                f"invalid result for channel: {requested_channel.value}",
            )
        if query.max_items is None:
            raise RetrievalCoordinationError(
                RetrievalCoordinationErrorCode.INVALID_CHANNEL_RESULT,
                "bounded retrieval query is required",
            )
        if len(result.candidates) > query.max_items:
            raise RetrievalCoordinationError(
                RetrievalCoordinationErrorCode.CHANNEL_RESULT_LIMIT_EXCEEDED,
                f"channel result exceeds limit: {requested_channel.value}",
            )

    def _fuse_and_rank(
        self,
        *,
        request: EvidenceRequest,
        query: RetrievalQuery,
        channel_results: list[RetrievalSearchResult],
    ) -> tuple[tuple[FusedRetrievalCandidate, ...], list[str]]:
        results_by_channel = {result.channel: result for result in channel_results}
        structured = results_by_channel.get(RetrievalChannel.STRUCTURED)
        if structured is None:
            raise RetrievalCoordinationError(
                RetrievalCoordinationErrorCode.STRUCTURED_ADMISSIBILITY_MISSING,
                "STRUCTURED admissibility result is missing",
            )

        occurrences_by_identity: dict[RetrievalIdentity, list[RetrievalCandidate]] = {}
        ranks_by_identity: dict[RetrievalIdentity, dict[RetrievalChannel, int]] = {}
        dropped_channels: list[RetrievalChannel] = []
        admissibility_port = self._resolved_admissibility_port()
        fallback_admissible_identities = frozenset(
            RetrievalIdentity.from_candidate(candidate)
            for candidate in structured.candidates
        )
        for channel in _CHANNEL_EXECUTION_ORDER:
            result = results_by_channel.get(channel)
            if result is None:
                continue
            dropped = False
            for rank, candidate in enumerate(result.candidates, start=1):
                if not self._is_admissible(
                    candidate=candidate,
                    query=query,
                    port=admissibility_port,
                    fallback_admissible_identities=fallback_admissible_identities,
                ):
                    dropped = True
                    continue
                identity = RetrievalIdentity.from_candidate(candidate)
                occurrences_by_identity.setdefault(identity, []).append(candidate)
                ranks_by_identity.setdefault(identity, {}).setdefault(channel, rank)
            if dropped:
                dropped_channels.append(channel)

        sortable: list[
            tuple[
                RetrievalIdentity,
                tuple[RetrievalCandidate, ...],
                dict[RetrievalChannel, int],
                RetrievalCandidate,
                Decimal,
            ]
        ] = []
        for identity, occurrence_list in occurrences_by_identity.items():
            occurrences = tuple(occurrence_list)
            channel_ranks = ranks_by_identity[identity]
            representative = min(
                enumerate(occurrences),
                key=lambda indexed_candidate: (
                    _CHANNEL_EXECUTION_ORDER.index(indexed_candidate[1].channel),
                    indexed_candidate[0],
                    indexed_candidate[1].candidate_id,
                ),
            )[1]
            fusion_score = sum(
                (
                    Decimal(1) / Decimal(self.policy.rrf_k + rank)
                    for rank in channel_ranks.values()
                ),
                start=Decimal(0),
            )
            sortable.append(
                (identity, occurrences, channel_ranks, representative, fusion_score)
            )

        missing_rank = self.policy.channel_limit + 1
        sortable.sort(
            key=lambda item: (
                -item[4],
                item[2].get(RetrievalChannel.STRUCTURED, missing_rank),
                item[2].get(RetrievalChannel.LEXICAL, missing_rank),
                item[2].get(RetrievalChannel.RELATIONAL, missing_rank),
                item[2].get(RetrievalChannel.SEMANTIC, missing_rank),
                item[0].deterministic_key(),
            )
        )
        final_limit = (
            min(self.policy.final_limit, request.max_items)
            if request.max_items is not None
            else self.policy.final_limit
        )
        ranked = tuple(
            FusedRetrievalCandidate(
                identity=identity,
                representative=representative,
                occurrences=occurrences,
                channel_ranks=channel_ranks,
                fusion_score=fusion_score,
                technical_rank=technical_rank,
            )
            for technical_rank, (
                identity,
                occurrences,
                channel_ranks,
                representative,
                fusion_score,
            ) in enumerate(sortable[:final_limit], start=1)
        )
        limitations = [
            f"INADMISSIBLE_CANDIDATES_DROPPED:{channel.value}"
            for channel in dropped_channels
        ]
        return ranked, limitations

    def _resolved_admissibility_port(self) -> EvidenceAdmissibilityPort | None:
        if self.admissibility_port is not None:
            return self.admissibility_port
        if isinstance(self.search_port, EvidenceAdmissibilityPort):
            return self.search_port
        return None

    @staticmethod
    def _is_admissible(
        *,
        candidate: RetrievalCandidate,
        query: RetrievalQuery,
        port: EvidenceAdmissibilityPort | None,
        fallback_admissible_identities: frozenset[RetrievalIdentity],
    ) -> bool:
        if port is None:
            return (
                RetrievalIdentity.from_candidate(candidate)
                in fallback_admissible_identities
            )
        return port.is_admissible(candidate=candidate, query=query)
