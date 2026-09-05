from __future__ import annotations

import ast
import json
from dataclasses import fields
from pathlib import Path

from backend.modules.resource_library.application.dto.input import GetResourceRequest
from backend.modules.resource_library.domain.value_objects import RESOURCE_REF_REGEX

ROOT = Path(__file__).resolve().parents[2]
RESOURCE_MODULE = ROOT / "backend" / "modules" / "resource_library"
CONTRACT = (
    RESOURCE_MODULE / "domain" / "value_objects" / "resource_ref.py"
)
HANDOFF = (
    ROOT
    / "docs"
    / "development"
    / "phase_12_17_04e_b09_legacy_review_api_handoff"
    / "API_HANDOFF.json"
)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    } | {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }


def test_resource_ref_contract_is_owned_by_the_resource_domain() -> None:
    assert CONTRACT.is_file()
    imports = _imports(CONTRACT)
    assert not any(name.startswith("backend.adapters") for name in imports)
    assert "sqlite3" not in imports
    assert RESOURCE_REF_REGEX == r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"


def test_resource_slice_contains_one_executable_copy_of_the_canonical_regex() -> None:
    paths = tuple(RESOURCE_MODULE.rglob("*.py")) + (
        ROOT / "backend" / "adapters" / "inbound" / "application" / "resource_library.py",
        ROOT / "backend" / "adapters" / "outbound" / "resource_library" / "sqlite.py",
    )
    occurrences = [
        path
        for path in paths
        if RESOURCE_REF_REGEX in path.read_text(encoding="utf-8")
    ]
    assert occurrences == [CONTRACT]


def test_application_and_sqlite_adapter_consume_the_domain_contract() -> None:
    paths = (
        RESOURCE_MODULE / "application" / "dto" / "input" / "get_resource.py",
        RESOURCE_MODULE / "application" / "dto" / "output" / "resource_view.py",
        RESOURCE_MODULE / "ports" / "outbound" / "resource_store.py",
        ROOT / "backend" / "adapters" / "inbound" / "application" / "resource_library.py",
        ROOT / "backend" / "adapters" / "outbound" / "resource_library" / "sqlite.py",
    )
    for path in paths:
        source = path.read_text(encoding="utf-8")
        assert "ResourceRef" in source
        assert "re.compile" not in source
        assert "fullmatch" not in source


def test_read15_keeps_one_field_and_deprecations_without_http_implementation() -> None:
    from backend.adapters.inbound.api.routes import ROUTE_SPECS

    handoff = json.loads(HANDOFF.read_text(encoding="utf-8"))
    http = handoff["http_handoff"]
    deprecation = handoff["read15_deprecation"]

    assert [field.name for field in fields(GetResourceRequest)] == ["resource_ref"]
    assert http["path_parameters"] == ["resource_ref"]
    assert http["query_parameters"] == []
    assert http["endpoint_implemented"] is False
    assert deprecation["version_ref"] == "DEPRECATED_FOR_ACTIVE_READ15"
    assert deprecation["include"] == "DEPRECATED_FOR_ACTIVE_READ15"
    assert ROUTE_SPECS == (
        (("GET",), "/api/v2/resources/{resource_ref}", None),
        (("GET",), "/api/v2/search", None),
        (("GET",), "/api/v2/conversation", None),
        (("POST",), "/api/v2/conversation/messages", None),
        (("POST",), "/api/v2/conversation/generations", None),
        (("GET",), "/api/v2/productions/{production_ref}/versions/{version_ref}", None),
        (("GET", "HEAD"), "/", "index.html"),
        (("GET", "HEAD"), "/assets/app.js", "app.js"),
        (("GET", "HEAD"), "/assets/styles.css", "styles.css"),
    )
