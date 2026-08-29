"""Metrics for the additive F2B semantic channel over the immutable F1 corpus."""

from __future__ import annotations

from collections.abc import Iterable

from backend.agent_runtime.agents.evidence import EvidenceAgent
from tests.support.retrieval_quality_cases import (
    BENCHMARK_K_VALUES,
    CORPUS_SHA256,
    CORPUS_VERSION,
    RETRIEVAL_QUALITY_CASES,
    PedagogicalLevel,
    RetrievalMissCause,
    RetrievalQueryClass,
    corpus_sha256,
    retrieval_quality_request,
)

_REPORTED_CHANNELS = ("SEMANTIC", "COMBINED")


def run_semantic_retrieval_benchmark(
    agent: EvidenceAgent,
) -> dict[str, object]:
    outcomes: list[dict[str, object]] = []
    for index, case in enumerate(RETRIEVAL_QUALITY_CASES, start=1):
        retrieval = agent.search_evidence(
            request=retrieval_quality_request(case, index)
        )
        channel_refs = {
            result.channel.value: tuple(
                str(candidate.canonical_object_ref or candidate.source_ref)
                for candidate in result.candidates
            )
            for result in retrieval.channel_results
        }
        channel_refs["COMBINED"] = tuple(
            str(
                candidate.representative.canonical_object_ref
                or candidate.representative.source_ref
            )
            for candidate in retrieval.ranked_candidates
        )
        outcomes.append(
            {
                "case": case,
                "ranks": {
                    channel: _first_expected_rank(
                        channel_refs.get(channel, ()),
                        case.expected_refs,
                    )
                    for channel in (
                        "STRUCTURED",
                        "LEXICAL",
                        "SEMANTIC",
                        "COMBINED",
                    )
                },
                "candidate_counts": {
                    channel: len(channel_refs.get(channel, ()))
                    for channel in _REPORTED_CHANNELS
                },
            }
        )

    lexical_recovered = tuple(
        item
        for item in outcomes
        if _rank(item, "LEXICAL") is not None
        and _rank(item, "LEXICAL") <= 5  # type: ignore[operator]
        and (
            _rank(item, "STRUCTURED") is None
            or _rank(item, "STRUCTURED") > 5  # type: ignore[operator]
        )
    )
    semantic_gap = tuple(
        item
        for item in outcomes
        if item["case"].miss_cause  # type: ignore[union-attr]
        is RetrievalMissCause.SEMANTIC_PARAPHRASE_GAP
    )
    return {
        "corpus": {
            "case_count": len(RETRIEVAL_QUALITY_CASES),
            "sha256": corpus_sha256(),
            "version": CORPUS_VERSION,
        },
        "gates": {
            "corpus_hash_matches": corpus_sha256() == CORPUS_SHA256,
            "exact_label_combined_recall_at_5": _metrics(
                tuple(
                    item
                    for item in outcomes
                    if item["case"].query_class  # type: ignore[union-attr]
                    is RetrievalQueryClass.EXACT_LABEL
                )
            )["COMBINED"]["recall_at_5"],
            "f2a_lexical_recovered_case_count": len(lexical_recovered),
            "f2a_lexical_recovered_preserved_count": sum(
                _rank(item, "COMBINED") is not None
                and _rank(item, "COMBINED") <= 5  # type: ignore[operator]
                for item in lexical_recovered
            ),
            "semantic_gap_case_count": len(semantic_gap),
            "semantic_gap_recovered_by_semantic_count": sum(
                _rank(item, "SEMANTIC") is not None
                and _rank(item, "SEMANTIC") <= 5  # type: ignore[operator]
                for item in semantic_gap
            ),
            "semantic_gap_recovered_by_combined_count": sum(
                _rank(item, "COMBINED") is not None
                and _rank(item, "COMBINED") <= 5  # type: ignore[operator]
                for item in semantic_gap
            ),
        },
        "k_values": BENCHMARK_K_VALUES,
        "metrics": {
            "global": _metrics(tuple(outcomes)),
            "by_query_class": {
                query_class.value: _metrics(
                    tuple(
                        item
                        for item in outcomes
                        if item["case"].query_class is query_class  # type: ignore[union-attr]
                    )
                )
                for query_class in RetrievalQueryClass
            },
            "by_level": {
                level.value: _metrics(
                    tuple(
                        item
                        for item in outcomes
                        if item["case"].level is level  # type: ignore[union-attr]
                    )
                )
                for level in PedagogicalLevel
            },
        },
        "outcomes": tuple(
            {
                "case_id": item["case"].case_id,  # type: ignore[union-attr]
                "combined_rank": _rank(item, "COMBINED"),
                "expected_refs": item["case"].expected_refs,  # type: ignore[union-attr]
                "level": item["case"].level.value,  # type: ignore[union-attr]
                "lexical_rank": _rank(item, "LEXICAL"),
                "query_class": item["case"].query_class.value,  # type: ignore[union-attr]
                "semantic_rank": _rank(item, "SEMANTIC"),
                "structured_rank": _rank(item, "STRUCTURED"),
            }
            for item in outcomes
        ),
    }


def _rank(item: dict[str, object], channel: str) -> int | None:
    return item["ranks"][channel]  # type: ignore[index,return-value]


def _first_expected_rank(
    refs: tuple[str, ...],
    expected_refs: tuple[str, ...],
) -> int | None:
    expected = frozenset(expected_refs)
    return next(
        (rank for rank, ref in enumerate(refs, start=1) if ref in expected),
        None,
    )


def _metrics(outcomes: Iterable[dict[str, object]]) -> dict[str, object]:
    materialized = tuple(outcomes)
    return {
        channel: _channel_metrics(materialized, channel)
        for channel in _REPORTED_CHANNELS
    }


def _channel_metrics(
    outcomes: tuple[dict[str, object], ...],
    channel: str,
) -> dict[str, object]:
    ranks = tuple(_rank(item, channel) for item in outcomes)
    return {
        "case_count": len(outcomes),
        "mrr_at_5": _rate(
            sum(1 / rank for rank in ranks if rank is not None and rank <= 5),
            len(outcomes),
        ),
        "recall_at_1": _rate(sum(rank == 1 for rank in ranks), len(outcomes)),
        "recall_at_3": _rate(
            sum(rank is not None and rank <= 3 for rank in ranks), len(outcomes)
        ),
        "recall_at_5": _rate(
            sum(rank is not None and rank <= 5 for rank in ranks), len(outcomes)
        ),
        "zero_hit_rate": _rate(
            sum(item["candidate_counts"][channel] == 0 for item in outcomes),  # type: ignore[index]
            len(outcomes),
        ),
    }


def _rate(numerator: int | float, denominator: int) -> float:
    return round(float(numerator) / denominator, 6) if denominator else 0.0
