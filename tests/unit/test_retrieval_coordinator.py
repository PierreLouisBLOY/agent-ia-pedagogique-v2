from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from backend.agent_runtime.agents.evidence import (
    BASELINE_RETRIEVAL_COORDINATION_POLICY,
    FusedRetrievalCandidate,
    RetrievalCandidate,
    RetrievalChannel,
    RetrievalChannelUnavailable,
    RetrievalCoordinationError,
    RetrievalCoordinationErrorCode,
    RetrievalCoordinationMode,
    RetrievalCoordinationPolicy,
    RetrievalCoordinationResult,
    RetrievalCoordinator,
    RetrievalIdentity,
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
from backend.shared_kernel.identifiers import TypedEntityId
from backend.shared_kernel.references import ObjectVersionRef, TypedEntityRef, VersionRef
from backend.shared_kernel.time import Instant

NOW = Instant(datetime(2026, 8, 25, 9, 0, tzinfo=UTC))


class FakeSearchPort:
    def __init__(
        self,
        responses: dict[
            RetrievalChannel,
            RetrievalSearchResult | RetrievalChannelUnavailable,
        ],
    ) -> None:
        self.responses = responses
        self.calls: list[RetrievalChannel] = []
        self.queries: list[RetrievalQuery] = []

    def search(
        self,
        *,
        query: RetrievalQuery,
        channel: RetrievalChannel,
    ) -> RetrievalSearchResult:
        self.calls.append(channel)
        self.queries.append(query)
        response = self.responses[channel]
        if isinstance(response, RetrievalChannelUnavailable):
            raise response
        return response


def _meta() -> ContractMeta[InvocationStatus]:
    return ContractMeta(
        schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
        run_id="run-1",
        step_id="step-1",
        parent_step_id=None,
        correlation_id=CorrelationId("corr-1"),
        created_at=NOW,
        actor=ActorRef(ActorKind.AGENT, AgentId.AG_02.value),
        status=InvocationStatus.PLANNED,
    )


def _request(max_items: int | None = 10) -> EvidenceRequest:
    return EvidenceRequest(
        meta=_meta(),
        search_goal="Find the canonical progression",
        scope={"module": "M04", "cycles": [2, 3]},
        source_policy={"allowed_kinds": ["canonical"]},
        filters={"status": "active"},
        required_authority={"minimum": "official"},
        max_items=max_items,
    )


def _policy(**overrides: object) -> RetrievalCoordinationPolicy:
    values: dict[str, object] = {
        "enabled_channels": (
            RetrievalChannel.STRUCTURED,
            RetrievalChannel.LEXICAL,
            RetrievalChannel.RELATIONAL,
            RetrievalChannel.SEMANTIC,
        ),
        "required_channels": (
            RetrievalChannel.STRUCTURED,
            RetrievalChannel.LEXICAL,
        ),
        "channel_limit": 20,
        "final_limit": 10,
        "rrf_k": 60,
    }
    values.update(overrides)
    return RetrievalCoordinationPolicy(**values)  # type: ignore[arg-type]


def _candidate(
    channel: RetrievalChannel,
    *,
    object_id: str = "object-1",
    version: str | None = "v1",
    candidate_id: str | None = None,
    canonical: bool = True,
    source_ref: str | None = None,
    locator: str | None = None,
    lexical_score: Decimal | None = None,
    semantic_score: Decimal | None = None,
    relational_score: Decimal | None = None,
) -> RetrievalCandidate:
    return RetrievalCandidate(
        candidate_id=candidate_id or f"{channel.value.casefold()}-{object_id}-{version}",
        channel=channel,
        source_ref=source_ref or f"source:{channel.value.casefold()}:{object_id}",
        source_kind="canonical_record",
        locator=locator or f"record:{channel.value.casefold()}:{object_id}",
        signals=RetrievalSignals(
            structured_rank=0 if channel is RetrievalChannel.STRUCTURED else None,
            lexical_score=lexical_score,
            semantic_score=semantic_score,
            relational_score=relational_score,
        ),
        canonical_object_ref=f"canonical:{object_id}" if canonical else None,
        version_or_checksum=version,
    )


def _result(
    channel: RetrievalChannel,
    *candidates: RetrievalCandidate,
) -> RetrievalSearchResult:
    return RetrievalSearchResult(channel=channel, candidates=tuple(candidates))


def _full_responses(object_ids: tuple[str, ...] = ("object-1",)) -> dict[
    RetrievalChannel,
    RetrievalSearchResult | RetrievalChannelUnavailable,
]:
    return {
        channel: _result(
            channel,
            *(_candidate(channel, object_id=object_id) for object_id in object_ids),
        )
        for channel in (
            RetrievalChannel.STRUCTURED,
            RetrievalChannel.LEXICAL,
            RetrievalChannel.RELATIONAL,
            RetrievalChannel.SEMANTIC,
        )
    }


def _query(max_items: int = 5) -> RetrievalQuery:
    return RetrievalQuery(
        search_goal="Find canonical records",
        scope={},
        source_policy={},
        filters={},
        required_authority=None,
        max_items=max_items,
    )


def _fused(technical_rank: int = 1) -> FusedRetrievalCandidate:
    structured = _candidate(RetrievalChannel.STRUCTURED)
    identity = RetrievalIdentity.from_candidate(structured)
    return FusedRetrievalCandidate(
        identity=identity,
        representative=structured,
        occurrences=(structured,),
        channel_ranks={RetrievalChannel.STRUCTURED: 1},
        fusion_score=Decimal(1) / Decimal(61),
        technical_rank=technical_rank,
    )


def _coordination_result(**overrides: object) -> RetrievalCoordinationResult:
    values: dict[str, object] = {
        "query": _query(),
        "mode": RetrievalCoordinationMode.FULL,
        "ranked_candidates": (_fused(),),
        "channel_results": (
            _result(RetrievalChannel.STRUCTURED),
            _result(RetrievalChannel.LEXICAL),
        ),
        "unavailable_channels": (),
        "limitations": (),
    }
    values.update(overrides)
    return RetrievalCoordinationResult(**values)  # type: ignore[arg-type]


def test_coordination_mode_has_exact_values() -> None:
    assert tuple(RetrievalCoordinationMode) == (
        RetrievalCoordinationMode.FULL,
        RetrievalCoordinationMode.DEGRADED,
    )


def test_coordination_error_code_has_exact_values() -> None:
    assert [item.value for item in RetrievalCoordinationErrorCode] == [
        "REQUIRED_CHANNEL_UNAVAILABLE",
        "INVALID_CHANNEL_RESULT",
        "CHANNEL_RESULT_LIMIT_EXCEEDED",
        "STRUCTURED_ADMISSIBILITY_MISSING",
    ]


@pytest.mark.parametrize("field_name", ["enabled_channels", "required_channels"])
def test_policy_requires_real_channel_tuples(field_name: str) -> None:
    with pytest.raises(TypeError):
        _policy(**{field_name: [RetrievalChannel.STRUCTURED, RetrievalChannel.LEXICAL]})


def test_policy_requires_unique_channels() -> None:
    with pytest.raises(ValueError):
        _policy(
            enabled_channels=(
                RetrievalChannel.STRUCTURED,
                RetrievalChannel.LEXICAL,
                RetrievalChannel.LEXICAL,
            )
        )


def test_policy_requires_required_channels_to_be_enabled() -> None:
    with pytest.raises(ValueError):
        _policy(
            enabled_channels=(RetrievalChannel.STRUCTURED, RetrievalChannel.LEXICAL),
            required_channels=(
                RetrievalChannel.STRUCTURED,
                RetrievalChannel.LEXICAL,
                RetrievalChannel.SEMANTIC,
            ),
        )


@pytest.mark.parametrize(
    "enabled,required",
    [
        ((RetrievalChannel.LEXICAL,), (RetrievalChannel.LEXICAL,)),
        ((RetrievalChannel.STRUCTURED,), (RetrievalChannel.STRUCTURED,)),
        (
            (RetrievalChannel.STRUCTURED, RetrievalChannel.LEXICAL),
            (RetrievalChannel.STRUCTURED,),
        ),
        (
            (RetrievalChannel.STRUCTURED, RetrievalChannel.LEXICAL),
            (RetrievalChannel.LEXICAL,),
        ),
    ],
)
def test_policy_requires_structured_and_lexical_in_enabled_and_required(
    enabled: tuple[RetrievalChannel, ...],
    required: tuple[RetrievalChannel, ...],
) -> None:
    with pytest.raises(ValueError):
        _policy(enabled_channels=enabled, required_channels=required)


@pytest.mark.parametrize("field_name", ["enabled_channels", "required_channels"])
def test_policy_rejects_document_channel(field_name: str) -> None:
    channels = (
        RetrievalChannel.STRUCTURED,
        RetrievalChannel.LEXICAL,
        RetrievalChannel.DOCUMENT,
    )
    with pytest.raises(ValueError):
        _policy(**{field_name: channels})


@pytest.mark.parametrize("field_name", ["channel_limit", "final_limit", "rrf_k"])
@pytest.mark.parametrize("value", [0, -1])
def test_policy_requires_positive_limits(field_name: str, value: int) -> None:
    with pytest.raises(ValueError):
        _policy(**{field_name: value})


@pytest.mark.parametrize("field_name", ["channel_limit", "final_limit", "rrf_k"])
def test_policy_rejects_boolean_limits(field_name: str) -> None:
    with pytest.raises(TypeError):
        _policy(**{field_name: True})


def test_baseline_policy_has_exact_replaceable_defaults() -> None:
    assert BASELINE_RETRIEVAL_COORDINATION_POLICY == _policy()


def test_identity_uses_canonical_object_and_version_not_locator() -> None:
    first = RetrievalIdentity("canonical:1", "source:a", "locator:a", "v1")
    second = RetrievalIdentity("canonical:1", "source:b", "locator:b", "v1")
    assert first == second
    assert hash(first) == hash(second)


def test_identity_falls_back_to_source_locator_and_version() -> None:
    first = RetrievalIdentity(None, "source:1", "locator:1", "v1")
    same = RetrievalIdentity(None, "source:1", "locator:1", "v1")
    other_locator = RetrievalIdentity(None, "source:1", "locator:2", "v1")
    assert first == same
    assert first != other_locator


def test_identity_keeps_versions_isolated() -> None:
    assert RetrievalIdentity("canonical:1", "source:1", "locator:1", "v1") != (
        RetrievalIdentity("canonical:1", "source:1", "locator:1", "v2")
    )


def test_identity_normalizes_typed_references_deterministically() -> None:
    entity = TypedEntityRef(TypedEntityId("course", "course-1"))
    exact = ObjectVersionRef(entity, VersionRef("revision-2"))
    identity = RetrievalIdentity(exact, entity, "ignored", None)
    assert identity.deterministic_key() == (
        "canonical",
        "object-version-ref",
        "course",
        "course-1",
        "revision-2",
        "version-none",
    )


def test_fused_candidate_requires_structured_occurrence() -> None:
    lexical = _candidate(RetrievalChannel.LEXICAL)
    with pytest.raises(ValueError):
        FusedRetrievalCandidate(
            identity=RetrievalIdentity.from_candidate(lexical),
            representative=lexical,
            occurrences=(lexical,),
            channel_ranks={RetrievalChannel.LEXICAL: 1},
            fusion_score=Decimal("0.1"),
            technical_rank=1,
        )


@pytest.mark.parametrize("rank", [0, -1, True])
def test_fused_candidate_requires_positive_strict_channel_ranks(rank: object) -> None:
    structured = _candidate(RetrievalChannel.STRUCTURED)
    with pytest.raises((TypeError, ValueError)):
        FusedRetrievalCandidate(
            identity=RetrievalIdentity.from_candidate(structured),
            representative=structured,
            occurrences=(structured,),
            channel_ranks={RetrievalChannel.STRUCTURED: rank},  # type: ignore[dict-item]
            fusion_score=Decimal("0.1"),
            technical_rank=1,
        )


@pytest.mark.parametrize(
    "score",
    [Decimal("0"), Decimal("-1"), Decimal("NaN"), Decimal("Infinity")],
)
def test_fused_candidate_requires_finite_positive_fusion_score(score: Decimal) -> None:
    structured = _candidate(RetrievalChannel.STRUCTURED)
    with pytest.raises(ValueError):
        FusedRetrievalCandidate(
            identity=RetrievalIdentity.from_candidate(structured),
            representative=structured,
            occurrences=(structured,),
            channel_ranks={RetrievalChannel.STRUCTURED: 1},
            fusion_score=score,
            technical_rank=1,
        )


def test_coordination_result_requires_contiguous_technical_ranks() -> None:
    with pytest.raises(ValueError):
        _coordination_result(ranked_candidates=(_fused(technical_rank=2),))


def test_coordination_result_requires_unique_result_channels() -> None:
    structured = _result(RetrievalChannel.STRUCTURED)
    with pytest.raises(ValueError):
        _coordination_result(
            channel_results=(
                structured,
                structured,
                _result(RetrievalChannel.LEXICAL),
            )
        )


def test_zero_max_items_returns_without_port_calls() -> None:
    port = FakeSearchPort({})
    result = RetrievalCoordinator(port).coordinate(request=_request(max_items=0))
    assert result.mode is RetrievalCoordinationMode.FULL
    assert result.ranked_candidates == ()
    assert result.channel_results == ()
    assert port.calls == []


def test_channel_query_preserves_request_constraints_exactly() -> None:
    port = FakeSearchPort(_full_responses())
    request = _request()
    result = RetrievalCoordinator(port).coordinate(request=request)
    assert result.query.search_goal == request.search_goal
    assert result.query.scope == request.scope
    assert result.query.source_policy == request.source_policy
    assert result.query.filters == request.filters
    assert result.query.required_authority == request.required_authority


@pytest.mark.parametrize("request_limit,expected", [(None, 20), (50, 20), (7, 7)])
def test_channel_query_narrows_max_items(
    request_limit: int | None,
    expected: int,
) -> None:
    port = FakeSearchPort(_full_responses())
    result = RetrievalCoordinator(port).coordinate(request=_request(request_limit))
    assert result.query.max_items == expected
    assert {query.max_items for query in port.queries} == {expected}


def test_channels_are_called_in_canonical_order_not_policy_order() -> None:
    policy = _policy(
        enabled_channels=(
            RetrievalChannel.SEMANTIC,
            RetrievalChannel.RELATIONAL,
            RetrievalChannel.LEXICAL,
            RetrievalChannel.STRUCTURED,
        )
    )
    port = FakeSearchPort(_full_responses())
    RetrievalCoordinator(port, policy).coordinate(request=_request())
    assert port.calls == [
        RetrievalChannel.STRUCTURED,
        RetrievalChannel.LEXICAL,
        RetrievalChannel.RELATIONAL,
        RetrievalChannel.SEMANTIC,
    ]


@pytest.mark.parametrize(
    "channel",
    [RetrievalChannel.STRUCTURED, RetrievalChannel.LEXICAL],
)
def test_required_channel_unavailable_is_an_explicit_error(
    channel: RetrievalChannel,
) -> None:
    responses = _full_responses()
    responses[channel] = RetrievalChannelUnavailable(channel, "TEMPORARILY_UNAVAILABLE")
    with pytest.raises(RetrievalCoordinationError) as raised:
        RetrievalCoordinator(FakeSearchPort(responses)).coordinate(request=_request())
    assert raised.value.code is RetrievalCoordinationErrorCode.REQUIRED_CHANNEL_UNAVAILABLE


@pytest.mark.parametrize(
    "unavailable",
    [
        (RetrievalChannel.SEMANTIC,),
        (RetrievalChannel.RELATIONAL,),
        (RetrievalChannel.RELATIONAL, RetrievalChannel.SEMANTIC),
    ],
)
def test_optional_channel_unavailable_produces_degraded_mode(
    unavailable: tuple[RetrievalChannel, ...],
) -> None:
    responses = _full_responses()
    for channel in unavailable:
        responses[channel] = RetrievalChannelUnavailable(channel, "NOT_READY")
    result = RetrievalCoordinator(FakeSearchPort(responses)).coordinate(request=_request())
    assert result.mode is RetrievalCoordinationMode.DEGRADED
    assert result.unavailable_channels == unavailable
    assert result.limitations[: len(unavailable)] == tuple(
        f"CHANNEL_UNAVAILABLE:{channel.value}" for channel in unavailable
    )


def test_all_enabled_channels_available_produces_full_mode() -> None:
    result = RetrievalCoordinator(FakeSearchPort(_full_responses())).coordinate(
        request=_request()
    )
    assert result.mode is RetrievalCoordinationMode.FULL
    assert result.unavailable_channels == ()


def test_empty_structured_admissibility_produces_empty_final_result() -> None:
    responses = _full_responses()
    responses[RetrievalChannel.STRUCTURED] = _result(RetrievalChannel.STRUCTURED)
    result = RetrievalCoordinator(FakeSearchPort(responses)).coordinate(request=_request())
    assert result.ranked_candidates == ()


@pytest.mark.parametrize(
    "channel",
    [RetrievalChannel.LEXICAL, RetrievalChannel.RELATIONAL, RetrievalChannel.SEMANTIC],
)
def test_non_structured_inadmissible_candidates_are_dropped(
    channel: RetrievalChannel,
) -> None:
    responses = _full_responses()
    responses[channel] = _result(channel, _candidate(channel, object_id="outside"))
    result = RetrievalCoordinator(FakeSearchPort(responses)).coordinate(request=_request())
    assert all(
        occurrence.canonical_object_ref != "canonical:outside"
        for candidate in result.ranked_candidates
        for occurrence in candidate.occurrences
    )
    assert f"INADMISSIBLE_CANDIDATES_DROPPED:{channel.value}" in result.limitations


def test_wrong_channel_result_is_rejected() -> None:
    responses = _full_responses()
    responses[RetrievalChannel.STRUCTURED] = _result(RetrievalChannel.LEXICAL)
    with pytest.raises(RetrievalCoordinationError) as raised:
        RetrievalCoordinator(FakeSearchPort(responses)).coordinate(request=_request())
    assert raised.value.code is RetrievalCoordinationErrorCode.INVALID_CHANNEL_RESULT


def test_channel_result_exceeding_query_limit_is_rejected() -> None:
    responses = _full_responses(("one", "two"))
    with pytest.raises(RetrievalCoordinationError) as raised:
        RetrievalCoordinator(FakeSearchPort(responses)).coordinate(
            request=_request(max_items=1)
        )
    assert raised.value.code is RetrievalCoordinationErrorCode.CHANNEL_RESULT_LIMIT_EXCEEDED


def test_duplicate_identity_merges_every_occurrence() -> None:
    result = RetrievalCoordinator(FakeSearchPort(_full_responses())).coordinate(
        request=_request()
    )
    assert len(result.ranked_candidates) == 1
    assert tuple(item.channel for item in result.ranked_candidates[0].occurrences) == (
        RetrievalChannel.STRUCTURED,
        RetrievalChannel.LEXICAL,
        RetrievalChannel.RELATIONAL,
        RetrievalChannel.SEMANTIC,
    )


def test_different_versions_are_never_merged() -> None:
    responses = {
        channel: _result(
            channel,
            _candidate(channel, version="v1"),
            _candidate(channel, version="v2"),
        )
        for channel in (
            RetrievalChannel.STRUCTURED,
            RetrievalChannel.LEXICAL,
            RetrievalChannel.RELATIONAL,
            RetrievalChannel.SEMANTIC,
        )
    }
    result = RetrievalCoordinator(FakeSearchPort(responses)).coordinate(request=_request())
    assert {item.identity.version_or_checksum for item in result.ranked_candidates} == {
        "v1",
        "v2",
    }


def test_fallback_locator_differences_are_never_merged() -> None:
    responses = _full_responses()
    for channel in responses:
        responses[channel] = _result(
            channel,
            _candidate(
                channel,
                canonical=False,
                source_ref="source:shared",
                locator="section:a",
            ),
            _candidate(
                channel,
                canonical=False,
                source_ref="source:shared",
                locator="section:b",
                candidate_id=f"{channel.value}:section-b",
            ),
        )
    result = RetrievalCoordinator(FakeSearchPort(responses)).coordinate(request=_request())
    assert {item.identity.locator for item in result.ranked_candidates} == {
        "section:a",
        "section:b",
    }


def test_raw_channel_scores_are_preserved_in_occurrences() -> None:
    responses = _full_responses()
    responses[RetrievalChannel.LEXICAL] = _result(
        RetrievalChannel.LEXICAL,
        _candidate(RetrievalChannel.LEXICAL, lexical_score=Decimal("917.25")),
    )
    responses[RetrievalChannel.SEMANTIC] = _result(
        RetrievalChannel.SEMANTIC,
        _candidate(RetrievalChannel.SEMANTIC, semantic_score=Decimal("0.999")),
    )
    fused = RetrievalCoordinator(FakeSearchPort(responses)).coordinate(
        request=_request()
    ).ranked_candidates[0]
    assert any(item.signals.lexical_score == Decimal("917.25") for item in fused.occurrences)
    assert any(item.signals.semantic_score == Decimal("0.999") for item in fused.occurrences)


def test_representative_prefers_first_structured_occurrence() -> None:
    responses = _full_responses()
    first = _candidate(
        RetrievalChannel.STRUCTURED,
        candidate_id="structured-z",
    )
    second = _candidate(
        RetrievalChannel.STRUCTURED,
        candidate_id="structured-a",
        locator="other-locator",
    )
    responses[RetrievalChannel.STRUCTURED] = _result(
        RetrievalChannel.STRUCTURED,
        first,
        second,
    )
    fused = RetrievalCoordinator(FakeSearchPort(responses)).coordinate(
        request=_request()
    ).ranked_candidates[0]
    assert fused.representative is first
    assert len(fused.occurrences) == 5


def test_channel_rank_is_result_position_not_raw_score() -> None:
    responses = _full_responses(("a", "b"))
    responses[RetrievalChannel.LEXICAL] = _result(
        RetrievalChannel.LEXICAL,
        _candidate(
            RetrievalChannel.LEXICAL,
            object_id="a",
            lexical_score=Decimal("0.01"),
        ),
        _candidate(
            RetrievalChannel.LEXICAL,
            object_id="b",
            lexical_score=Decimal("999"),
        ),
    )
    result = RetrievalCoordinator(FakeSearchPort(responses)).coordinate(request=_request())
    ranks = {
        item.identity.canonical_object_ref: item.channel_ranks[RetrievalChannel.LEXICAL]
        for item in result.ranked_candidates
    }
    assert ranks == {"canonical:a": 1, "canonical:b": 2}


def test_rrf_uses_exact_decimal_rank_fusion() -> None:
    fused = RetrievalCoordinator(FakeSearchPort(_full_responses())).coordinate(
        request=_request()
    ).ranked_candidates[0]
    assert fused.fusion_score == Decimal(4) / Decimal(61)


def test_final_tie_break_prefers_lower_structured_rank() -> None:
    responses = _full_responses(("a", "b"))
    responses[RetrievalChannel.LEXICAL] = _result(
        RetrievalChannel.LEXICAL,
        _candidate(RetrievalChannel.LEXICAL, object_id="b"),
        _candidate(RetrievalChannel.LEXICAL, object_id="a"),
    )
    responses[RetrievalChannel.RELATIONAL] = _result(RetrievalChannel.RELATIONAL)
    responses[RetrievalChannel.SEMANTIC] = _result(RetrievalChannel.SEMANTIC)
    result = RetrievalCoordinator(FakeSearchPort(responses)).coordinate(request=_request())
    assert [item.identity.canonical_object_ref for item in result.ranked_candidates] == [
        "canonical:a",
        "canonical:b",
    ]


def test_final_limit_is_respected() -> None:
    policy = _policy(final_limit=2)
    result = RetrievalCoordinator(
        FakeSearchPort(_full_responses(("a", "b", "c", "d"))),
        policy,
    ).coordinate(request=_request(max_items=4))
    assert len(result.ranked_candidates) == 2


def test_coordinator_never_synthesizes_candidates_to_fill_top_k() -> None:
    result = RetrievalCoordinator(FakeSearchPort(_full_responses(("only",)))).coordinate(
        request=_request(max_items=10)
    )
    assert len(result.ranked_candidates) == 1
