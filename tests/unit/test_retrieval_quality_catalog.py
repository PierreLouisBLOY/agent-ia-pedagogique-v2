from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from tests.support.retrieval_quality_cases import (
    CORPUS_SHA256,
    RETRIEVAL_QUALITY_CASES,
    PedagogicalLevel,
    RetrievalMissCause,
    RetrievalQueryClass,
    corpus_sha256,
)


def test_retrieval_quality_catalog_is_frozen_and_balanced() -> None:
    assert len(RETRIEVAL_QUALITY_CASES) == 60
    assert corpus_sha256() == CORPUS_SHA256
    assert len({case.case_id for case in RETRIEVAL_QUALITY_CASES}) == 60
    assert {
        query_class: sum(
            case.query_class is query_class for case in RETRIEVAL_QUALITY_CASES
        )
        for query_class in RetrievalQueryClass
    } == {query_class: 10 for query_class in RetrievalQueryClass}
    assert {
        level: sum(case.level is level for case in RETRIEVAL_QUALITY_CASES)
        for level in PedagogicalLevel
    } == {
        PedagogicalLevel.PREMIERE_STMG: 18,
        PedagogicalLevel.TERMINALE_STMG: 18,
        PedagogicalLevel.BTS_CG_1: 12,
        PedagogicalLevel.BTS_CG_2: 12,
    }


def test_expected_references_are_static_and_semantic_cases_have_controls() -> None:
    controls = {
        case.case_id: case
        for case in RETRIEVAL_QUALITY_CASES
        if case.query_class is RetrievalQueryClass.EXACT_LABEL
    }
    semantic_classes = {
        RetrievalQueryClass.SYNONYM_BUSINESS,
        RetrievalQueryClass.PEDAGOGICAL_PARAPHRASE,
        RetrievalQueryClass.CONCEPT_DESCRIPTION,
    }
    for case in RETRIEVAL_QUALITY_CASES:
        assert case.expected_refs
        assert all(ref.startswith("notion:") for ref in case.expected_refs)
        if case.query_class in semantic_classes:
            assert case.control_ref in controls
            assert controls[case.control_ref].query_family == case.query_family
            assert controls[case.control_ref].expected_refs == case.expected_refs
            assert isinstance(case.miss_cause, RetrievalMissCause)
        else:
            assert case.miss_cause is None


def test_catalog_cases_are_immutable() -> None:
    with pytest.raises(FrozenInstanceError):
        RETRIEVAL_QUALITY_CASES[0].query_text = "mutated"  # type: ignore[misc]
