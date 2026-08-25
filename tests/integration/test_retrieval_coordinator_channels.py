from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from backend.agent_runtime.agents.evidence import (
    RetrievalCandidate,
    RetrievalChannel,
    RetrievalChannelUnavailable,
    RetrievalCoordinationError,
    RetrievalCoordinationErrorCode,
    RetrievalCoordinationMode,
    RetrievalCoordinator,
    RetrievalQuery,
    RetrievalSearchResult,
    RetrievalSignals,
)
from backend.agent_runtime.contracts import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    ActorKind,
    ActorRef,
    AgentId,
    ContractMeta,
    EvidenceRequest,
    InvocationStatus,
)
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant

NOW = Instant(datetime(2026, 8, 25, 10, 0, tzinfo=UTC))


class ScenarioSearchPort:
    def __init__(
        self,
        responses: dict[
            RetrievalChannel,
            RetrievalSearchResult | RetrievalChannelUnavailable,
        ],
    ) -> None:
        self.responses = responses
        self.calls: list[RetrievalChannel] = []

    def search(
        self,
        *,
        query: RetrievalQuery,
        channel: RetrievalChannel,
    ) -> RetrievalSearchResult:
        self.calls.append(channel)
        response = self.responses[channel]
        if isinstance(response, RetrievalChannelUnavailable):
            raise response
        return response


def _request() -> EvidenceRequest:
    return EvidenceRequest(
        meta=ContractMeta(
            schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
            run_id="run-integration",
            step_id="step-search",
            parent_step_id=None,
            correlation_id=CorrelationId("corr-integration"),
            created_at=NOW,
            actor=ActorRef(ActorKind.AGENT, AgentId.AG_02.value),
            status=InvocationStatus.RUNNING,
        ),
        search_goal="Retrieve admissible curriculum references",
        scope={"cycles": [1, 2, 3]},
        source_policy={"kinds": ["canonical"]},
        filters={"active": True},
        required_authority={"level": "official"},
        max_items=10,
    )


def _candidate(
    channel: RetrievalChannel,
    object_id: str,
    *,
    version: str = "v1",
    score: Decimal | None = None,
) -> RetrievalCandidate:
    return RetrievalCandidate(
        candidate_id=f"{channel.value}:{object_id}:{version}",
        channel=channel,
        source_ref=f"source:{channel.value}:{object_id}",
        source_kind="canonical_curriculum",
        locator=f"locator:{channel.value}:{object_id}",
        signals=RetrievalSignals(
            structured_rank=0 if channel is RetrievalChannel.STRUCTURED else None,
            lexical_score=score if channel is RetrievalChannel.LEXICAL else None,
            relational_score=score if channel is RetrievalChannel.RELATIONAL else None,
            semantic_score=score if channel is RetrievalChannel.SEMANTIC else None,
        ),
        canonical_object_ref=f"curriculum:{object_id}",
        version_or_checksum=version,
    )


def _result(
    channel: RetrievalChannel,
    object_ids: tuple[str, ...],
    *,
    version: str = "v1",
    score: Decimal | None = None,
) -> RetrievalSearchResult:
    return RetrievalSearchResult(
        channel=channel,
        candidates=tuple(
            _candidate(channel, object_id, version=version, score=score)
            for object_id in object_ids
        ),
    )


def _full_scenario() -> dict[
    RetrievalChannel,
    RetrievalSearchResult | RetrievalChannelUnavailable,
]:
    return {
        RetrievalChannel.STRUCTURED: _result(
            RetrievalChannel.STRUCTURED,
            ("a", "b", "c", "d", "e"),
        ),
        RetrievalChannel.LEXICAL: _result(
            RetrievalChannel.LEXICAL,
            ("b", "a", "d", "c"),
            score=Decimal("50"),
        ),
        RetrievalChannel.RELATIONAL: _result(
            RetrievalChannel.RELATIONAL,
            ("c", "b", "e"),
            score=Decimal("4"),
        ),
        RetrievalChannel.SEMANTIC: _result(
            RetrievalChannel.SEMANTIC,
            ("e", "c", "a"),
            score=Decimal("0.99"),
        ),
    }


def test_full_hybrid_fuses_overlapping_channels_deterministically() -> None:
    port = ScenarioSearchPort(_full_scenario())
    result = RetrievalCoordinator(port).coordinate(request=_request())
    assert result.mode is RetrievalCoordinationMode.FULL
    assert len(result.ranked_candidates) == 5
    assert port.calls == [
        RetrievalChannel.STRUCTURED,
        RetrievalChannel.LEXICAL,
        RetrievalChannel.RELATIONAL,
        RetrievalChannel.SEMANTIC,
    ]
    assert all(
        candidate.channel_ranks[RetrievalChannel.STRUCTURED] >= 1
        for candidate in result.ranked_candidates
    )
    assert [item.technical_rank for item in result.ranked_candidates] == [1, 2, 3, 4, 5]


def test_hard_filter_blocks_high_semantic_score_outside_structured() -> None:
    responses = _full_scenario()
    responses[RetrievalChannel.SEMANTIC] = RetrievalSearchResult(
        channel=RetrievalChannel.SEMANTIC,
        candidates=(
            _candidate(
                RetrievalChannel.SEMANTIC,
                "forbidden",
                score=Decimal("999999"),
            ),
            _candidate(RetrievalChannel.SEMANTIC, "a", score=Decimal("0.01")),
        ),
    )
    result = RetrievalCoordinator(ScenarioSearchPort(responses)).coordinate(
        request=_request()
    )
    assert all(
        item.identity.canonical_object_ref != "curriculum:forbidden"
        for item in result.ranked_candidates
    )
    assert "INADMISSIBLE_CANDIDATES_DROPPED:SEMANTIC" in result.limitations


def test_versions_of_the_same_object_remain_separate() -> None:
    responses: dict[
        RetrievalChannel,
        RetrievalSearchResult | RetrievalChannelUnavailable,
    ] = {}
    for channel in (
        RetrievalChannel.STRUCTURED,
        RetrievalChannel.LEXICAL,
        RetrievalChannel.RELATIONAL,
        RetrievalChannel.SEMANTIC,
    ):
        responses[channel] = RetrievalSearchResult(
            channel=channel,
            candidates=(
                _candidate(channel, "x", version="v1"),
                _candidate(channel, "x", version="v2"),
            ),
        )
    result = RetrievalCoordinator(ScenarioSearchPort(responses)).coordinate(
        request=_request()
    )
    assert len(result.ranked_candidates) == 2
    assert {item.identity.version_or_checksum for item in result.ranked_candidates} == {
        "v1",
        "v2",
    }


def test_empty_structured_result_cannot_be_repopulated_by_other_channels() -> None:
    responses = _full_scenario()
    responses[RetrievalChannel.STRUCTURED] = _result(
        RetrievalChannel.STRUCTURED,
        (),
    )
    result = RetrievalCoordinator(ScenarioSearchPort(responses)).coordinate(
        request=_request()
    )
    assert result.ranked_candidates == ()
    assert {item.channel for item in result.channel_results} == {
        RetrievalChannel.STRUCTURED,
        RetrievalChannel.LEXICAL,
        RetrievalChannel.RELATIONAL,
        RetrievalChannel.SEMANTIC,
    }


def test_semantic_unavailability_yields_stable_degraded_ranking() -> None:
    responses = _full_scenario()
    responses[RetrievalChannel.SEMANTIC] = RetrievalChannelUnavailable(
        RetrievalChannel.SEMANTIC,
        "INDEX_NOT_READY",
    )
    result = RetrievalCoordinator(ScenarioSearchPort(responses)).coordinate(
        request=_request()
    )
    assert result.mode is RetrievalCoordinationMode.DEGRADED
    assert result.unavailable_channels == (RetrievalChannel.SEMANTIC,)
    assert result.limitations == ("CHANNEL_UNAVAILABLE:SEMANTIC",)
    assert [item.identity.canonical_object_ref for item in result.ranked_candidates] == [
        "curriculum:b",
        "curriculum:c",
        "curriculum:a",
        "curriculum:d",
        "curriculum:e",
    ]


def test_required_lexical_failure_returns_no_partial_result() -> None:
    responses = _full_scenario()
    responses[RetrievalChannel.LEXICAL] = RetrievalChannelUnavailable(
        RetrievalChannel.LEXICAL,
        "FTS_UNAVAILABLE",
    )
    with pytest.raises(RetrievalCoordinationError) as raised:
        RetrievalCoordinator(ScenarioSearchPort(responses)).coordinate(request=_request())
    assert raised.value.code is RetrievalCoordinationErrorCode.REQUIRED_CHANNEL_UNAVAILABLE


def test_same_inputs_produce_strictly_equal_results() -> None:
    first = RetrievalCoordinator(ScenarioSearchPort(_full_scenario())).coordinate(
        request=_request()
    )
    second = RetrievalCoordinator(ScenarioSearchPort(_full_scenario())).coordinate(
        request=_request()
    )
    assert first == second
