from __future__ import annotations

import pytest

from backend.adapters.inbound.api.routes import (
    ASSET_NAMES,
    MAX_TARGET_BYTES,
    READ15_TEMPLATE,
    ROUTE_SPECS,
    RouteRejected,
    resolve_route,
)


@pytest.mark.parametrize("method,target,asset", [
    ("GET", "/", "index.html"), ("HEAD", "/", "index.html"),
    ("GET", "/assets/app.js", "app.js"), ("HEAD", "/assets/app.js", "app.js"),
    ("GET", "/assets/styles.css", "styles.css"),
    ("HEAD", "/assets/styles.css", "styles.css"),
])
def test_exact_assets(method: str, target: str, asset: str) -> None:
    assert resolve_route(method, target).asset_name == asset


def test_registry_has_one_business_operation_and_three_assets() -> None:
    assert len(ROUTE_SPECS) == 9
    assert ASSET_NAMES == {"index.html", "app.js", "styles.css"}
    match = resolve_route("GET", "/api/v2/resources/resource%3A1")
    assert match.template == READ15_TEMPLATE
    assert match.resource_ref == "resource:1"


@pytest.mark.parametrize("target", [
    "/api/v2/resources/", "/api/v2/resources/a/b", "/api/v2/resources/a%2fb",
    "/api/v2/resources/a%5cb", "/api/v2/resources/%252e%252e",
    "/api/v2/resources/a%", "/api/v2/resources/a?version_ref=x",
    "/api/v2/resources/a?include=x", "/api/v2/resources/a?unknown=x",
    "/api/v2/resources/a?", "/api/v2/resources/a#fragment", "/api/v2/resources/%ff",
    "/api/v2/resources/a%00", "http://localhost/", "//localhost/", "/a\\b",
    "/api/v2/resources/é", "/\x00", "/" + "a" * MAX_TARGET_BYTES,
])
def test_unsafe_or_extended_targets_are_closed(target: str) -> None:
    # NUL within a decoded ref reaches the Application owner, not a filesystem or query.
    if target == "/api/v2/resources/a%00":
        assert resolve_route("GET", target).resource_ref == "a\x00"
    else:
        with pytest.raises(RouteRejected) as rejected:
            resolve_route("GET", target)
        assert rejected.value.status == 400


@pytest.mark.parametrize("target", ["/health", "/docs", "/openapi", "/orchestrate",
                                   "/assets/extra.js", "/../private", "/assets/%61pp.js"])
def test_no_additional_route(target: str) -> None:
    with pytest.raises(RouteRejected) as rejected:
        resolve_route("GET", target)
    assert rejected.value.status == 404


@pytest.mark.parametrize("method,target", [
    ("HEAD", "/api/v2/resources/a"), ("POST", "/api/v2/resources/a"),
    ("POST", "/"), ("OPTIONS", "/"), ("get", "/"),
])
def test_closed_methods(method: str, target: str) -> None:
    with pytest.raises(RouteRejected) as rejected:
        resolve_route(method, target)
    assert rejected.value.status == 405
