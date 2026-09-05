from __future__ import annotations

import pytest

from backend.adapters.inbound.api.routes import RouteRejected, resolve_route


@pytest.mark.parametrize("target,text,limit", [
    ("/api/v2/search?q=bilan", "bilan", 10),
    ("/api/v2/search?limit=20&q=bilan+fonctionnel", "bilan fonctionnel", 20),
    ("/api/v2/search?q=%C3%A9cole&limit=1", "école", 1),
    ("/api/v2/search?q=a%26b&limit=%31", "a&b", 1),
])
def test_exact_decoding(target: str, text: str, limit: int) -> None:
    match = resolve_route("GET", target)
    assert match.template == "/api/v2/search"
    assert match.search_text == text and match.search_limit == limit
    assert match.resource_ref is None


@pytest.mark.parametrize("query", [
    "", "limit=10", "q=a&q=b", "q=a&limit=1&limit=2", "%71=a",
    "q=a&unknown=x", "q=a&include=x", "q=a&version_ref=x", "q=a&", "&q=a",
    "q=a&limit=0", "q=a&limit=21", "q=a&limit=01", "q=a&limit=true",
    "q=a&limit=+1", "q=a&limit=", "q", "q=%ff", "q=%2520",
])
def test_closed_query(query: str) -> None:
    with pytest.raises(RouteRejected) as error:
        resolve_route("GET", "/api/v2/search?" + query)
    assert error.value.status == 400


@pytest.mark.parametrize("target", [
    "/api/v2/resources/search?q=x", "/api/v2/resources/a?", "/?q=a", "/assets/app.js?q=a",
    "/api/v2/search?q=%", "/api/v2/search?q=a#fragment",
])
def test_global_and_read15_rejections_preserved(target: str) -> None:
    with pytest.raises(RouteRejected) as error:
        resolve_route("GET", target)
    assert error.value.status == 400


def test_route_collision_and_unknown_path() -> None:
    assert resolve_route("GET", "/api/v2/resources/search").resource_ref == "search"
    with pytest.raises(RouteRejected) as error:
        resolve_route("GET", "/api/v2/search/")
    assert error.value.status == 404


@pytest.mark.parametrize("method", ["HEAD", "POST", "PUT", "DELETE", "OPTIONS"])
def test_method_rejection_precedes_bad_query(method: str) -> None:
    with pytest.raises(RouteRejected) as error:
        resolve_route(method, "/api/v2/search?q=%ff")
    assert error.value.status == 405
