from __future__ import annotations

import pytest

from backend.adapters.outbound.search.local import literal_fts, minimized_excerpt
from backend.modules.resource_library.application.dto.input.search_local import SearchLocalRequest
from backend.modules.resource_library.domain.value_objects.search_text import (
    InvalidSearchTextError,
    SearchText,
)


@pytest.mark.parametrize("text,tokens", [
    ("  bilan\u00a0fonctionnel  ", ("bilan", "fonctionnel")),
    ("e\u0301cole d'abord", ("école", "d", "abord")),
    ("alpha OR beta", ("alpha", "OR", "beta")),
    ('"alpha"* (beta) -- NOT', ("alpha", "beta", "NOT")),
    ("\u0301isolée", ("isolée",)),
    ("中文 12", ("中文", "12")),
    ("un\u2028deux", ("un", "deux")),
])
def test_normalization_and_literal_tokens(text: str, tokens: tuple[str, ...]) -> None:
    value = SearchText(text)
    assert value.tokens == tokens
    assert SearchText(value.value) == value
    assert literal_fts(value) == " AND ".join('"' + token + '"' for token in tokens)


@pytest.mark.parametrize("text", [
    "", "   ", "...", "\u0301", "x" * 65, "x" * 257, "a " * 13,
    "a\x00b", "a\tb", "a\nb", "a\u202eb", "a\ud800b", None, 42, True,
])
def test_invalid_text_rejected(text: object) -> None:
    with pytest.raises(InvalidSearchTextError):
        SearchText(text)


def test_exact_text_and_token_budgets() -> None:
    assert len(SearchText("x" * 64).tokens[0]) == 64
    assert len(SearchText(" ".join(["a"] * 12)).tokens) == 12
    maximum = " ".join(["x" * 64] * 3 + ["y" * 61])
    assert len(maximum) == 256
    assert len(SearchText(maximum).value) == 256
    with pytest.raises(InvalidSearchTextError):
        SearchText(maximum + " ")


@pytest.mark.parametrize("limit", [0, 21, True, False, "10", 1.0, None])
def test_request_limit_is_a_strict_integer(limit: object) -> None:
    with pytest.raises(InvalidSearchTextError):
        SearchLocalRequest(SearchText("bilan"), limit)


@pytest.mark.parametrize("limit", [1, 10, 20])
def test_request_limits(limit: int) -> None:
    assert SearchLocalRequest(SearchText("bilan"), limit).limit == limit


def test_excerpt_sanitization_and_boundary() -> None:
    assert minimized_excerpt("  a\n\tb\u202e\u2028c  ") == ("a b c", False)
    assert minimized_excerpt("x" * 320) == ("x" * 320, False)
    assert minimized_excerpt("x" * 321) == ("x" * 320, True)
    assert minimized_excerpt("<script>not executable</script>")[0].startswith("<script>")
