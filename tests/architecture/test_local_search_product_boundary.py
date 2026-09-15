from __future__ import annotations

import ast
import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from backend.adapters.inbound.api import routes
from tests.architecture import test_resource_ref_contract_fitness as resource_guard
from tests.architecture import test_security_recovery_observability_e2e_fitness as owner_guard
from tests.architecture.test_conversation_product_boundary import (
    HISTORICAL_R1_ROUTES,
    assert_historical_manifest,
    assert_r2_guard_nodes_preserved,
    git_diff_paths,
    git_source,
)
from tests.architecture.test_local_browser_product_boundary import (
    _CONTRACT,
    _EXPECTED_ROUTES,
    _R2_BASELINE,
    _SEARCH_BASELINE,
    EXPECTED_PROTECTED_DOCUMENTS,
    EXPECTED_R2_INVENTORY,
    EXPECTED_SEARCH_INVENTORY,
    ROOT,
    frontend_violations,
    inventory_violations,
    route_contract_violations,
    source_boundary_violations,
)


def test_exact_five_routes_preserve_read15() -> None:
    assert routes.ROUTE_SPECS == _EXPECTED_ROUTES
    assert len(_EXPECTED_ROUTES) == 22
    assert tuple(r for r in _EXPECTED_ROUTES if r in HISTORICAL_R1_ROUTES) == HISTORICAL_R1_ROUTES
    assert route_contract_violations(ROOT) == []
    assert frontend_violations(ROOT) == []


def registry_copy(tmp_path: Path) -> Path:
    for name in ("backend/adapters/inbound/api/routes.py", _CONTRACT):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((ROOT / name).read_bytes())
    return tmp_path


@pytest.mark.parametrize("mutation", ["extra", "method", "off_registry"])
def test_extra_route_method_or_off_registry_declaration_rejected(
    tmp_path: Path, mutation: str,
) -> None:
    root = registry_copy(tmp_path)
    path = root / "backend/adapters/inbound/api/routes.py"
    source = path.read_text(encoding="utf-8")
    if mutation == "extra":
        source = source.replace('    (("GET",), SEARCH_TEMPLATE, None),',
                                '    (("GET",), SEARCH_TEMPLATE, None),\n'
                                '    (("GET",), "/api/v2/extra", None),')
    elif mutation == "method":
        source = source.replace('(("GET",), SEARCH_TEMPLATE', '(("GET", "POST"), SEARCH_TEMPLATE')
    else:
        (path.parent / "extra.py").write_text('PATH = "/api/v2/extra"', encoding="utf-8")
    path.write_text(source, encoding="utf-8")
    assert route_contract_violations(root)


def test_exact_inventory_before_and_after_commit() -> None:
    assert len(EXPECTED_SEARCH_INVENTORY) == 30
    assert inventory_violations(ROOT) == []
    assert set(git_diff_paths(_SEARCH_BASELINE, _R2_BASELINE)) == set(EXPECTED_SEARCH_INVENTORY)
    assert inventory_violations(ROOT, set(EXPECTED_R2_INVENTORY) | {
        "backend/adapters/outbound/openai/contracts.py",
        "backend/adapters/outbound/openai/transport.py",
    }) == []
    assert len(EXPECTED_R2_INVENTORY) == 65
    assert _SEARCH_BASELINE == "3f724ca81843b5d45ac534e9654ff16281c55713"
    source = (ROOT / "tests/architecture/test_local_browser_product_boundary.py").read_text("utf-8")
    assert '["git", "diff", "--name-only", _R2_BASELINE, R3_BASELINE, "--"]' in source
    from tests.support.r3_guard_oracle import R3_PATHS, active_inventory
    assert len(R3_PATHS) == 59
    assert active_inventory(ROOT) == []


@pytest.mark.parametrize("name", [
    "backend/modules/resource_library/application/queries/extra.py",
    "backend/adapters/inbound/api/extra.py", "frontend/extra.js",
    "backend/modules/resource_library/application/queries/get_resource.py",
    "requirements/lock/runtime-py312-win.txt",
])
def test_unlisted_staged_untracked_or_protected_file_rejected(name: str) -> None:
    assert name in inventory_violations(ROOT, {name})


def test_protected_document_mutation_is_rejected(tmp_path: Path) -> None:
    contract = tmp_path / _CONTRACT
    contract.parent.mkdir(parents=True)
    contract.write_bytes((ROOT / _CONTRACT).read_bytes())
    for name, _ in EXPECTED_PROTECTED_DOCUMENTS:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / name).read_bytes())
    name = EXPECTED_PROTECTED_DOCUMENTS[0][0]
    (tmp_path / name).write_text("changed", encoding="utf-8")
    assert "PROTECTED_DOCUMENT_CHANGED:" + name in inventory_violations(tmp_path, set())


def test_a7_accepts_only_approved_five_routes() -> None:
    resource_guard.test_read15_keeps_one_field_and_deprecations_without_http_implementation()


def test_a7_rejects_sixth_route_and_read15_parameter_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(routes, "ROUTE_SPECS", (*routes.ROUTE_SPECS, (("GET",), "/extra", None)))
    with pytest.raises(AssertionError):
        resource_guard.test_read15_keeps_one_field_and_deprecations_without_http_implementation()


def test_phase_f_exact_search_owners_accepted() -> None:
    owner_guard.test_later_provider_work_preserves_phase_f_backend_owners()


def test_phase_f_unlisted_module_and_backend_owner_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    def changed(*args, **kwargs):
        return subprocess.CompletedProcess(args, 0, "backend/modules/extra.py\n", "")
    monkeypatch.setattr(owner_guard.subprocess, "run", changed)
    with pytest.raises(AssertionError):
        owner_guard.test_later_provider_work_preserves_phase_f_backend_owners()


def test_route_count_and_three_assets() -> None:
    from tests.unit.test_local_browser_product_routes import (
        test_registry_has_one_business_operation_and_three_assets,
    )
    test_registry_has_one_business_operation_and_three_assets()


@pytest.mark.parametrize("mutated", [
    _EXPECTED_ROUTES[:-1], (*_EXPECTED_ROUTES, _EXPECTED_ROUTES[0]),
    (*_EXPECTED_ROUTES[:-1], _EXPECTED_ROUTES[0]),
])
def test_duplicate_missing_or_sixth_route_rejected(
    monkeypatch: pytest.MonkeyPatch, mutated: tuple,
) -> None:
    monkeypatch.setattr(routes, "ROUTE_SPECS", mutated)
    assert route_contract_violations(ROOT)


def functions(source: str) -> dict[str, str]:
    return {node.name: ast.dump(node, include_attributes=False) for node in ast.parse(source).body
            if isinstance(node, ast.FunctionDef)}


def baseline_source(path: str) -> str:
    return subprocess.run(
        ["git", "show", f"{_SEARCH_BASELINE}:{path}"], cwd=ROOT,
        check=True, capture_output=True, text=True, encoding="utf-8",
    ).stdout


def test_only_approved_guard_functions_change_and_old_assertions_remain() -> None:
    scopes = {
        "tests/architecture/test_local_browser_product_boundary.py":
            {"route_contract_violations", "inventory_violations"},
        "tests/architecture/test_resource_ref_contract_fitness.py":
            {"test_read15_keeps_one_field_and_deprecations_without_http_implementation"},
        "tests/architecture/test_security_recovery_observability_e2e_fitness.py":
            {"test_later_provider_work_preserves_phase_f_backend_owners"},
        "tests/unit/test_local_browser_product_routes.py":
            {"test_registry_has_one_business_operation_and_three_assets"},
    }
    for path, allowed in scopes.items():
        old = functions(baseline_source(path))
        current = functions(git_source(_R2_BASELINE, path).decode("utf-8"))
        assert old.keys() == current.keys()
        assert {k: v for k, v in old.items() if k not in allowed} == {
            k: v for k, v in current.items() if k not in allowed
        }
    assert_r2_guard_nodes_preserved(ROOT)
    ref_path = "tests/architecture/test_resource_ref_contract_fitness.py"
    name = "test_read15_keeps_one_field_and_deprecations_without_http_implementation"
    old = next(n for n in ast.parse(baseline_source(ref_path)).body
               if isinstance(n, ast.FunctionDef) and n.name == name)
    current = next(n for n in ast.parse((ROOT / ref_path).read_text("utf-8")).body
                   if isinstance(n, ast.FunctionDef) and n.name == name)
    assert [ast.dump(n) for n in old.body[:-1]] == [ast.dump(n) for n in current.body[:-1]]
    unit_path = "tests/unit/test_local_browser_product_routes.py"
    name = "test_registry_has_one_business_operation_and_three_assets"
    old = next(n for n in ast.parse(baseline_source(unit_path)).body
               if isinstance(n, ast.FunctionDef) and n.name == name)
    current = next(n for n in ast.parse((ROOT / unit_path).read_text("utf-8")).body
                   if isinstance(n, ast.FunctionDef) and n.name == name)
    assert [ast.dump(n) for n in old.body[1:]] == [ast.dump(n) for n in current.body[1:]]


def test_reused_components_and_history_are_byte_identical() -> None:
    prep = ROOT / "docs/development/phase_12_18_h2_recherche_locale_preparation"
    inventory = json.loads((prep / "03_INVENTAIRE_FICHIERS_ET_GUARDS.json").read_text("utf-8"))
    for item in inventory["read_only_dependencies"]:
        if item["path"] in {"backend/adapters/inbound/api/local_browser.py",
                            "backend/adapters/inbound/cli/local_browser.py"}:
            for baseline in (_SEARCH_BASELINE, _R2_BASELINE):
                raw = git_source(baseline, item["path"])
                assert item["sha256"] in {hashlib.sha256(raw).hexdigest(),
                    hashlib.sha256(raw.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")).hexdigest()}
        else:
            assert hashlib.sha256((ROOT / item["path"]).read_bytes()).hexdigest() == item["sha256"]
    assert_historical_manifest("docs/development/phase_12_18_h2_local_search", _R2_BASELINE, 29)
    for name, digest in EXPECTED_PROTECTED_DOCUMENTS:
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
    # The old manifest is a historical working-tree snapshot. Check baseline Git blobs,
    # accepting only the Git EOL representation documented at entry.
    manifest_dir = ROOT / "docs/development/phase_12_18_h2_local_read15"
    for line in (manifest_dir / "MANIFEST_SHA256.txt").read_text("utf-8").splitlines():
        digest, name = line.split("  ", 1)
        relative = (manifest_dir / name).resolve().relative_to(ROOT).as_posix()
        raw = subprocess.run(
            ["git", "show", f"{_SEARCH_BASELINE}:{relative}"], cwd=ROOT,
            check=True, capture_output=True,
        ).stdout
        assert digest in {
            hashlib.sha256(raw).hexdigest(),
            hashlib.sha256(raw.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")).hexdigest(),
        }


@pytest.mark.parametrize("source,path", [
    ("import sqlite3", "backend/adapters/inbound/api/search.py"),
    ("from backend.modules import resource_library", "backend/adapters/inbound/api/search.py"),
    ("import http.server", "backend/modules/resource_library/application/queries/search_local.py"),
])
def test_storage_or_http_boundary_shortcuts_rejected(source: str, path: str) -> None:
    assert source_boundary_violations(source, path)


def test_bridge_is_lexical_and_does_not_bypass_independent_admission() -> None:
    source = (ROOT / "backend/adapters/outbound/search/local.py").read_text("utf-8")
    assert "self._evidence.is_admissible(" in source
    assert "channel=RetrievalChannel.LEXICAL" in source
    assert "RetrievalChannel.SEMANTIC" not in source
    assert "RetrievalChannel.STRUCTURED" not in source
    assert "self._content.read_passage(" in source
    assert "sqlite3.connect" not in source
    assert "SELECT " not in source and "INSERT " not in source
    assert "self._connection.rollback()" in source


def test_search_assets_are_static_safe_and_keep_existing_read15() -> None:
    script = (ROOT / "frontend/app.js").read_text("utf-8")
    html = (ROOT / "frontend/index.html").read_text("utf-8")
    assert 'form.requestSubmit()' in script
    assert "AbortController" in script and "searchSequence" in script
    assert "textContent" in script and "replaceChildren" in script
    for forbidden in ("innerHTML", "localStorage", "sessionStorage", "console.", "history."):
        assert forbidden not in script
    assert 'id="resource-form"' in html and 'id="search-form"' in html
    assert 'aria-live="polite"' in html
    assert frontend_violations(ROOT) == []
