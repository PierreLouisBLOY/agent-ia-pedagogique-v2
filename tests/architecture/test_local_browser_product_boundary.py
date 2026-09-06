from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BASELINE = "24b7a9850bc4644391dee2307c8a8a31036cd503"
SERVER_PATH = "backend/adapters/inbound/api/server.py"
ROUTES_PATH = "backend/adapters/inbound/api/routes.py"
_CONTRACT = "docs/development/phase_12_18_h2_r2_generation/CONVERSATION_HTTP_LOCAL_V1.json"
_R2_BASELINE = "19c42bc9f4b0b1a97b9bd2d6b880acd7378459f7"
EXPECTED_R2_INVENTORY = (
    "backend/adapters/inbound/api/routes.py",
    "backend/adapters/inbound/api/server.py",
    "backend/adapters/inbound/api/local_browser.py",
    "backend/adapters/inbound/api/conversation.py",
    "backend/adapters/inbound/api/production.py",
    "backend/adapters/inbound/application/conversation.py",
    "backend/adapters/inbound/application/production.py",
    "backend/modules/pedagogical_context/contracts/dto/conversation_context.py",
    "backend/modules/pedagogical_context/application/services/conversation_context.py",
    "backend/modules/pedagogical_design/contracts/dto/conversation_draft.py",
    "backend/modules/pedagogical_design/ports/inbound/create_conversation_draft.py",
    "backend/modules/pedagogical_design/ports/outbound/conversation_generation.py",
    "backend/modules/pedagogical_design/application/commands/create_conversation_draft.py",
    "backend/modules/work_orchestration/contracts/dto/conversation.py",
    "backend/modules/work_orchestration/contracts/dto/production_read_view.py",
    "backend/modules/work_orchestration/application/dto/input/read_production.py",
    "backend/modules/work_orchestration/ports/inbound/conversation.py",
    "backend/modules/work_orchestration/ports/inbound/production_read.py",
    "backend/modules/work_orchestration/ports/outbound/conversation_store.py",
    "backend/modules/work_orchestration/ports/outbound/production_store.py",
    "backend/modules/work_orchestration/ports/outbound/generation_job.py",
    "backend/modules/work_orchestration/application/services/conversation.py",
    "backend/modules/work_orchestration/application/queries/read_production.py",
    "backend/adapters/outbound/persistence/conversation_memory.py",
    "backend/adapters/outbound/generation/conversation.py",
    "backend/adapters/outbound/system/conversation_job.py",
    "backend/infrastructure/composition/bindings/conversation_agents.py",
    "backend/infrastructure/composition/bindings/conversation_routing.py",
    "backend/infrastructure/composition/bootstrap/conversation_worker.py",
    "backend/infrastructure/composition/factories/conversation.py",
    "backend/infrastructure/composition/factories/local_browser.py",
    "backend/adapters/outbound/generation/openai/mapping.py",
    "backend/adapters/outbound/generation/openai/adapter.py",
    "frontend/index.html",
    "frontend/app.js",
    "frontend/styles.css",
    "tests/architecture/test_local_browser_product_boundary.py",
    "tests/architecture/test_resource_ref_contract_fitness.py",
    "tests/architecture/test_security_recovery_observability_e2e_fitness.py",
    "tests/unit/test_local_browser_product_routes.py",
    "tests/architecture/test_local_search_product_boundary.py",
    "tests/unit/test_conversation_context.py",
    "tests/unit/test_conversation_application.py",
    "tests/unit/test_conversation_generation.py",
    "tests/unit/test_production_read.py",
    "tests/unit/test_conversation_routes_security.py",
    "tests/integration/test_conversation_http.py",
    "tests/integration/test_conversation_job_lifecycle.py",
    "tests/integration/test_conversation_product.py",
    "tests/unit/test_openai_conversation_mapping.py",
    "tests/unit/test_conversation_assets.py",
    "tests/architecture/test_conversation_product_boundary.py",
    "tests/support/conversation_fakes.py",
    "tests/support/conversation_synthetic.py",
    "architecture/adr/ADR-conversational-generation-product-boundary.md",
    "docs/development/phase_12_18_h2_r2_generation/CONVERSATION_HTTP_LOCAL_V1.json",
    "docs/development/phase_12_18_h2_r2_generation/IMPLEMENTATION_EVIDENCE.md",
    "docs/development/phase_12_18_h2_r2_generation/LIVE_GENERATION_SCOPE.json",
    "docs/development/phase_12_18_h2_r2_generation/MANIFEST_SHA256.txt",
    "backend/adapters/inbound/cli/local_browser.py",
    "backend/agent_runtime/contracts/planning/delegation.py",
    "tests/architecture/test_pedagogical_calibration_fitness.py",
    "tests/calibration/pedagogical/repair_tranche_v4_2.py",
    "tests/architecture/test_calibration_tooling_boundary.py",
    "tests/architecture/test_repository_hygiene_b06.py",
)
EXACT_R2_PREPARATION_PATHS = (
    "docs/development/phase_12_18_h2_r2_generation_preparation/01_CONTRAT_R2_GENERATION_CONVERSATIONNELLE.md",
    "docs/development/phase_12_18_h2_r2_generation_preparation/02_INVENTAIRE_GUARDS_TESTS_PERMISSIONS_R2.json",
    "docs/development/phase_12_18_h2_r2_generation_preparation/03_DECISION_ET_PLAN_EXECUTION_R2.md",
    "docs/development/phase_12_18_h2_r2_generation_preparation/MANIFEST_SHA256.txt",
)
PREPARATION_MANIFEST_SHA256 = "359b06ab34aa092831bd0d0eea909fc4b030776eef49414edbe7932f97eb9d6c"
_SEARCH_BASELINE = "3f724ca81843b5d45ac534e9654ff16281c55713"
EXPECTED_SEARCH_INVENTORY = (
    "architecture/adr/ADR-local-lexical-search-product-boundary.md",
    "backend/adapters/inbound/api/routes.py",
    "backend/adapters/inbound/api/search.py",
    "backend/adapters/inbound/api/server.py",
    "backend/adapters/inbound/application/local_search.py",
    "backend/adapters/outbound/search/local.py",
    "backend/infrastructure/composition/factories/local_browser.py",
    "backend/modules/resource_library/application/dto/input/search_local.py",
    "backend/modules/resource_library/application/dto/output/local_search_view.py",
    "backend/modules/resource_library/application/queries/search_local.py",
    "backend/modules/resource_library/domain/value_objects/search_text.py",
    "backend/modules/resource_library/ports/inbound/local_search.py",
    "backend/modules/resource_library/ports/outbound/local_search.py",
    "docs/development/phase_12_18_h2_local_search/IMPLEMENTATION_EVIDENCE.md",
    "docs/development/phase_12_18_h2_local_search/MANIFEST_SHA256.txt",
    "docs/development/phase_12_18_h2_local_search/SEARCH_HTTP_LOCAL_V1.json",
    "frontend/app.js",
    "frontend/index.html",
    "frontend/styles.css",
    "tests/architecture/test_local_browser_product_boundary.py",
    "tests/architecture/test_local_search_product_boundary.py",
    "tests/architecture/test_resource_ref_contract_fitness.py",
    "tests/architecture/test_security_recovery_observability_e2e_fitness.py",
    "tests/integration/test_local_search_http.py",
    "tests/integration/test_local_search_sqlite.py",
    "tests/unit/test_local_browser_product_routes.py",
    "tests/unit/test_local_search_application.py",
    "tests/unit/test_local_search_http_projection.py",
    "tests/unit/test_local_search_routes.py",
    "tests/unit/test_local_search_text.py",
)
EXPECTED_PROTECTED_DOCUMENTS = (
    ("docs/development/phase_12_18_h1_audit_cumulatif/01_BASELINE_ET_PERIMETRE.md", "1a220b89864c0b01634996b04b4784e38faee5fe7fea596f65c51ce8d0d9cecb"),
    ("docs/development/phase_12_18_h1_audit_cumulatif/02_MATRICE_CUMULATIVE_12_1_12_17.json", "3f1120df875476dc1f140ae394de27831d517c8b4d49ec07c8271075c42029b3"),
    ("docs/development/phase_12_18_h1_audit_cumulatif/03_ETAT_INTEGRATION_PRODUIT.md", "1d844c64b5e44dd798de3fb81807b1a8a7098f4cc7fa9d5eeeabf87432b8f811"),
    ("docs/development/phase_12_18_h1_audit_cumulatif/04_ECARTS_ET_PREPARATION_RECETTE.json", "af7e112116448cb076244349bf1de9cdd823ed2071ddeadda84bda4c7821d282"),
    ("docs/development/phase_12_18_h1_audit_cumulatif/LIVRABLE_12_18_H1_AUDIT_CUMULATIF.md", "c2723ab6f9d943397cc7eb8d36642f76ee555ea36d1ebe96bf31b28a84bfaefd"),
    ("docs/development/phase_12_18_h1_audit_cumulatif/MANIFEST_SHA256.txt", "259a50779d6c75231e3a3cad8f5d78dc69442b696613719c128fcb4320674ab3"),
    ("docs/development/phase_12_18_h1a_sources_et_evolution_guard/01_SOURCES_ET_ECARTS_RECONCILIES.json", "a8dd8edc13d505e504a3983bf5598a834f2fb57ba4fead0d3545f1d2848448d3"),
    ("docs/development/phase_12_18_h1a_sources_et_evolution_guard/02_PROPOSITION_EVOLUTION_GUARD.md", "f019d1e74e079ca2ecfc48f77da8ef3bee6904affa59346b48b59d8d9840a80c"),
    ("docs/development/phase_12_18_h1a_sources_et_evolution_guard/03_PAQUET_DECISION_ET_PLAN_H2.md", "2e90d55cd1600f71032f197c3aaa61c8aaebb291e792fea5d27a7b89e50a1dad"),
    ("docs/development/phase_12_18_h1a_sources_et_evolution_guard/LIVRABLE_H1A_SOURCES_ET_GUARD.md", "398a6e2b68e4deb0c720cb309d33ef41c12644c2b49951749739e3b224afc998"),
    ("docs/development/phase_12_18_h1a_sources_et_evolution_guard/MANIFEST_SHA256.txt", "2c7f3d2b93e4852f9243f6d6631492fc1d413bfb3ab0df4141672fa1ccd932a8"),
    ("docs/development/phase_12_18_h2_recherche_locale_preparation/01_BASELINE_ET_REUTILISATION.md", "86916ecaf2fbfc2f0d98d39ae18636264c2f02049e7e4dae8ff3d254a3f8c31e"),
    ("docs/development/phase_12_18_h2_recherche_locale_preparation/02_CONTRAT_RECHERCHE_LOCALE_PROPOSE.md", "664df97c350324af087597f7d17ec4e71ab837129a871959ee3305d61e7ebf0b"),
    ("docs/development/phase_12_18_h2_recherche_locale_preparation/03_INVENTAIRE_FICHIERS_ET_GUARDS.json", "856c7017b6f943c8575895a3844bfa62053c7574272422be3e8e1bbedb53606a"),
    ("docs/development/phase_12_18_h2_recherche_locale_preparation/04_DECISION_ET_PLAN_IMPLEMENTATION.md", "777e86b5584eebc59990568b4e82985e89901ea6a2e6b58cf4f032b4eda7df4b"),
    ("docs/development/phase_12_18_h2_recherche_locale_preparation/LIVRABLE_PROPOSITION_RECHERCHE_LOCALE.md", "b03bbb1be99b2698dff717b864ee59e968f3abe2d366e9e7c658aab60ac450d4"),
    ("docs/development/phase_12_18_h2_recherche_locale_preparation/MANIFEST_SHA256.txt", "7e210975e1c64ecc29aa73bbbaf48c2e4b099501625fd061f33f0ef13d8f15f4"),
)
_FORBIDDEN = ("aiohttp", "fastapi", "flask", "hypercorn", "starlette", "uvicorn")
_API_FORBIDDEN = (
    "anthropic", "backend.adapters.outbound", "backend.modules",
    "calibration_tooling", "openai", "sqlite3",
)
_EXPECTED_ROUTES = (
    (("GET",), "/api/v2/resources/{resource_ref}", None),
    (("GET",), "/api/v2/search", None),
    (("GET",), "/api/v2/conversation", None),
    (("POST",), "/api/v2/conversation/messages", None),
    (("POST",), "/api/v2/conversation/generations", None),
    (("GET",), "/api/v2/productions/{production_ref}/versions/{version_ref}", None),
    (("POST",), "/api/v2/conversation/assessment-preparations", None),
    (("POST",), "/api/v2/conversation/reviews", None),
    (("GET",), "/api/v2/conversation/reviews/{review_ref}", None),
    (("POST",), "/api/v2/conversation/validations", None),
    (("POST",), "/api/v2/conversation/modifications", None),
    (("GET",), "/api/v2/conversation/operations/{operation_ref}", None),
    (("GET",), "/api/v2/productions/{production_ref}/versions/{version_ref}/assessment", None),
    (("GET", "HEAD"), "/", "index.html"),
    (("GET", "HEAD"), "/assets/app.js", "app.js"),
    (("GET", "HEAD"), "/assets/styles.css", "styles.css"),
)


def _qualified(node: ast.expr, aliases: dict[str, str]) -> str:
    if isinstance(node, ast.Name):
        return aliases.get(node.id, node.id)
    if isinstance(node, ast.Attribute):
        return _qualified(node.value, aliases) + "." + node.attr
    if isinstance(node, ast.Subscript):
        return "DYNAMIC_UNRESOLVED"
    return ""


def imported_names(source: str, path: str) -> set[str]:
    tree = ast.parse(source)
    aliases: dict[str, str] = {}
    names: set[str] = set()
    package = ".".join(Path(path).parts[:-1])
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
                aliases[alias.asname or alias.name.split(".")[0]] = (
                    alias.name if alias.asname else alias.name.split(".")[0]
                )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level:
                try:
                    module = importlib.util.resolve_name("." * node.level + module, package)
                except (ImportError, ValueError):
                    names.add("DYNAMIC_UNRESOLVED")
            names.add(module)
            for alias in node.names:
                full = module + "." + alias.name
                names.add(full)
                aliases[alias.asname or alias.name] = full
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name):
                qualified = _qualified(node.value, aliases)
                if qualified:
                    aliases[target.id] = qualified
        if not isinstance(node, ast.Call):
            continue
        called = _qualified(node.func, aliases)
        if called in {"eval", "exec", "builtins.eval", "builtins.exec", "DYNAMIC_UNRESOLVED"}:
            names.add("DYNAMIC_UNRESOLVED")
        if called.endswith(("import_module", "__import__")):
            if node.args and isinstance(node.args[0], ast.Constant):
                module = node.args[0].value
                if isinstance(module, str) and not module.startswith("."):
                    names.add(module)
                else:
                    names.add("DYNAMIC_UNRESOLVED")
            else:
                names.add("DYNAMIC_UNRESOLVED")
    return names


def source_boundary_violations(source: str, path: str) -> list[str]:
    names = imported_names(source, path)
    violations = []
    for name in sorted(names):
        if name.startswith(_FORBIDDEN) or name == "DYNAMIC_UNRESOLVED":
            violations.append(name)
        if name.startswith("http.server") and path != SERVER_PATH:
            violations.append(name)
        if name.startswith("backend.adapters.inbound.api.server") and path != (
            "backend/infrastructure/composition/factories/local_browser.py"
        ):
            violations.append(name)
        if path.startswith("backend/adapters/inbound/api/") and name.startswith(_API_FORBIDDEN):
            violations.append(name)
        if "/domain/" in path or "/application/" in path and path.startswith("backend/modules/"):
            if name.startswith(("http", "urllib", "socket")):
                violations.append(name)
    if path.startswith("backend/adapters/inbound/api/") and re.search(
        r"\b(?:SELECT\s+.+\s+FROM|INSERT\s+INTO|CREATE\s+TABLE)\b", source
    ):
        violations.append("SQL_IN_HTTP")
    return violations


def server_import_violations(root: Path) -> list[str]:
    return [
        str(path.relative_to(root))
        for path in (root / "backend").rglob("*.py")
        if source_boundary_violations(
            path.read_text(encoding="utf-8"), path.relative_to(root).as_posix()
        )
    ]


def _literal(node: ast.expr, constants: dict[str, object]) -> object:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Tuple):
        return tuple(_literal(item, constants) for item in node.elts)
    if isinstance(node, ast.Name) and node.id in constants:
        return constants[node.id]
    raise ValueError("ROUTE_REGISTRY_MUST_BE_STATIC")


def route_contract_violations(root: Path) -> list[str]:
    from tests.support.r3_guard_oracle import R3_CONTRACT, R3_ROUTES
    constants: dict[str, object] = {}
    for node in ast.parse((root / ROUTES_PATH).read_text(encoding="utf-8")).body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value:
            if node.target.id in {"READ15_TEMPLATE", "SEARCH_TEMPLATE", "_RESOURCE_PREFIX", "ROUTE_SPECS",
                                  "CONVERSATION_TEMPLATE", "CONVERSATION_MESSAGES_TEMPLATE",
                                  "CONVERSATION_GENERATIONS_TEMPLATE", "PRODUCTION_VERSION_TEMPLATE",
                                  "R3_PREPARATION_TEMPLATE", "R3_REVIEWS_TEMPLATE", "R3_REVIEW_TEMPLATE",
                                  "R3_VALIDATIONS_TEMPLATE", "R3_MODIFICATIONS_TEMPLATE",
                                  "R3_OPERATION_TEMPLATE", "R3_ASSESSMENT_TEMPLATE"}:
                constants[node.target.id] = _literal(node.value, constants)
    from backend.adapters.inbound.api.routes import ROUTE_SPECS
    historical = json.loads((root / _CONTRACT).read_text(encoding="utf-8"))
    documented_r2 = tuple((tuple(r["methods"]), r["path"], r["asset"]) for r in historical["routes"])
    # Legacy mutation fixtures supply only their historical document. The active
    # contract remains independently checked against the literal oracle, never inferred.
    active_path = root / R3_CONTRACT
    contract = json.loads((active_path if active_path.is_file() else ROOT / R3_CONTRACT).read_text("utf-8"))
    documented = tuple((tuple(r["methods"]), r["path"], r["asset"]) for r in contract["routes"])
    violations = []
    if constants.get("ROUTE_SPECS") != R3_ROUTES:
        violations.append("AST_REGISTRY_DRIFT")
    if ROUTE_SPECS != R3_ROUTES or documented != R3_ROUTES or _EXPECTED_ROUTES != R3_ROUTES:
        violations.append("CONTRACT_REGISTRY_DRIFT")
    if documented_r2 != R3_ROUTES[:6] + R3_ROUTES[-3:]:
        violations.append("HISTORICAL_R2_REGISTRY_DRIFT")
    for path in (root / "backend/adapters/inbound/api").rglob("*.py"):
        if path.relative_to(root).as_posix() != ROUTES_PATH:
            if "/api/v2" in path.read_text(encoding="utf-8"):
                violations.append("ROUTE_DECLARED_OUTSIDE_REGISTRY")
    return violations


def frontend_violations(root: Path) -> list[str]:
    folder = root / "frontend"
    expected = {"index.html", "app.js", "styles.css"}
    actual = {path.relative_to(folder).as_posix() for path in folder.rglob("*") if path.is_file()}
    violations = [] if actual == expected else ["ASSET_INVENTORY"]
    for path in folder.rglob("*"):
        if path.is_file():
            source = path.read_text(encoding="utf-8")
            if re.search(r"https?://|//[a-zA-Z]|@import|\bimport\s*\(|WebSocket|innerHTML|eval\(",
                         source):
                violations.append("UNSAFE_OR_EXTERNAL_ASSET")
    return violations


def observability_server_violations(source: str) -> list[str]:
    path = "backend/infrastructure/composition/bootstrap/observability.py"
    imports = imported_names(source, path)
    bad = [name for name in imports if name.startswith(
        ("backend.adapters.inbound.api", "http.server", "socket", *_FORBIDDEN)
    ) or name == "DYNAMIC_UNRESOLVED"]
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call):
            name = _qualified(node.func, {})
            if name.endswith((".bind", "HTTPServer", "LocalRead15Server")):
                bad.append("SERVER_CONSTRUCTION_IN_OBSERVABILITY")
    return bad


def inventory_violations(root: Path, changed: set[str] | None = None) -> list[str]:
    from tests.architecture.test_conversation_product_boundary import CORRECTION_PATHS
    contract = json.loads((root / _CONTRACT).read_text(encoding="utf-8"))
    assert contract["baseline_commit"] == _R2_BASELINE
    assert contract["approved_inventory"] == list(EXPECTED_R2_INVENTORY)
    assert contract["corrective_inventory"] == list(CORRECTION_PATHS)
    assert contract["corrective_baseline_commit"] == "0c17d12eea1e1e6d4b04d943e756e0c8e35c41ba"
    indexed = set()
    active_errors = []
    if changed is None:
        from tests.support.r3_guard_oracle import R3_BASELINE, active_inventory
        # R2 is closed, not reauthorized by the active R3 delta.
        result = subprocess.run(["git", "diff", "--name-only", _R2_BASELINE, R3_BASELINE, "--"],
            cwd=root, capture_output=True, text=True, check=True)
        changed = set(result.stdout.splitlines())
        active_errors = active_inventory(root)
    protected = {item["path"]: item["sha256"] for item in contract["protected_documents"]}
    assert protected == dict(EXPECTED_PROTECTED_DOCUMENTS)
    allowed = set(EXPECTED_R2_INVENTORY) | set(CORRECTION_PATHS)
    preparation = set(EXACT_R2_PREPARATION_PATHS)
    violations = sorted(changed - allowed - set(protected) - preparation)
    violations.extend("MISSING_R2_PATH:" + path for path in sorted(allowed - changed))
    violations.extend("PROTECTED_DOCUMENT_INDEXED:" + path for path in sorted(
        indexed & (set(protected) | preparation)))
    from tests.architecture.test_conversation_product_boundary import preparation_violations
    violations.extend(preparation_violations(root))
    for name, digest in protected.items():
        path = root / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            violations.append("PROTECTED_DOCUMENT_CHANGED:" + name)
    return violations + active_errors


def test_server_framework_and_application_boundaries() -> None:
    assert server_import_violations(ROOT) == []


@pytest.mark.parametrize("source,path", [
    ("import http.server", "backend/modules/m/domain/x.py"),
    ("from http import server", "backend/modules/m/application/x.py"),
    ("import fastapi as f", SERVER_PATH),
    ("import http.server as h", "backend/adapters/inbound/api/extra.py"),
    ("from .server import LocalRead15Server", "backend/adapters/inbound/api/extra.py"),
    ("from ...outbound import persistence", "backend/adapters/inbound/api/extra.py"),
    ("import sqlite3", "backend/adapters/inbound/api/extra.py"),
    ("from ....modules import resource_library", "backend/adapters/inbound/api/extra.py"),
    ("import importlib as i\ni.import_module('http.server')", "backend/modules/m/domain/x.py"),
    ("from importlib import import_module as load\nload('sqlite3')",
     "backend/adapters/inbound/api/extra.py"),
    ("loader = __import__\nloader(name)", "backend/adapters/inbound/api/extra.py"),
    ("__import__('sqlite3')", "backend/adapters/inbound/api/extra.py"),
    ("eval(source)", "backend/adapters/inbound/api/extra.py"),
    ("connection.execute('SELECT * FROM resource')", "backend/adapters/inbound/api/extra.py"),
])
def test_ast_counterexamples_are_rejected(source: str, path: str) -> None:
    assert source_boundary_violations(source, path)


def test_only_exact_server_import_is_permitted() -> None:
    assert source_boundary_violations("from http.server import HTTPServer", SERVER_PATH) == []


def test_approved_registry_and_frontend() -> None:
    assert route_contract_violations(ROOT) == []
    assert frontend_violations(ROOT) == []


def test_a7_closed_registry_rejects_extra_routes_outside_or_inside_registry(
    tmp_path: Path,
) -> None:
    routes = tmp_path / ROUTES_PATH
    routes.parent.mkdir(parents=True)
    approved_source = (ROOT / ROUTES_PATH).read_text(encoding="utf-8")
    routes.write_text(approved_source, encoding="utf-8")
    contract = tmp_path / _CONTRACT
    contract.parent.mkdir(parents=True)
    contract.write_text((ROOT / _CONTRACT).read_text(encoding="utf-8"), encoding="utf-8")

    assert route_contract_violations(tmp_path) == []

    routes.write_text(
        approved_source.replace(
            "    ((\"GET\", \"HEAD\"), \"/assets/styles.css\", \"styles.css\"),\n)",
            "    ((\"GET\", \"HEAD\"), \"/assets/styles.css\", \"styles.css\"),\n"
            "    ((\"GET\",), \"/api/v2/extra\", None),\n)",
        ),
        encoding="utf-8",
    )
    assert "AST_REGISTRY_DRIFT" in route_contract_violations(tmp_path)

    routes.write_text(approved_source, encoding="utf-8")
    extra = routes.parent / "extra.py"
    extra.write_text('EXTRA_ROUTE = "/api/v2/extra"\n', encoding="utf-8")
    assert "ROUTE_DECLARED_OUTSIDE_REGISTRY" in route_contract_violations(tmp_path)


@pytest.mark.parametrize("source", [
    "from backend.adapters.inbound.api.server import LocalRead15Server",
    "host.bind(address)", "LocalRead15Server(service)",
    "import socket as network", "from http import server",
])
def test_observability_cannot_take_ownership_of_server(source: str) -> None:
    assert observability_server_violations(source)


def test_inventory_survives_staging_and_updated_head() -> None:
    assert inventory_violations(ROOT) == []
    for path in (
        "backend/adapters/inbound/api/extra.py", "frontend/extra.js",
        "backend/modules/resource_library/application/queries/get_resource.py",
        "requirements/lock/runtime-py312-win.txt",
    ):
        assert path in inventory_violations(ROOT, {path})


def test_existing_pure_contracts_and_original_guards_other_tests_preserved() -> None:
    expected = {
        "backend/adapters/inbound/api/local_browser.py":
            "cc7ee88ebbb41d17feb301c9707d1ab05efe3d1fa3118be8612c1b4c735d1148",
        "backend/infrastructure/config/schemas/http.py":
            "511336250f3a3274fe4f2f17f328771111250b0ec916a4e18723abc6b4ecf298",
    }
    for path, digest in expected.items():
        if path == "backend/adapters/inbound/api/local_browser.py":
            from tests.architecture.test_conversation_product_boundary import git_source, method_ast
            raw = git_source(BASELINE, path)
            assert digest in {hashlib.sha256(raw).hexdigest(),
                hashlib.sha256(raw.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")).hexdigest()}
            before = git_source(_R2_BASELINE, path).decode("utf-8")
            current = (ROOT / path).read_text("utf-8")
            assert method_ast(before, "authorize_request") == method_ast(current, "authorize_request")
            assert method_ast(current, "authorize_command")
        else:
            assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest
    permitted = {
        "tests/architecture/test_local_browser_http_boundary_fitness.py": {
            "test_b04_adds_no_http_server_framework_or_route",
            "test_b04_adds_no_frontend_public_url_or_drive_runtime_dependency",
        },
        "tests/architecture/test_minimal_local_observability_fitness.py": {
            "test_http_observability_adds_no_server_framework_or_route",
        },
        "tests/architecture/test_security_recovery_observability_e2e_fitness.py": {
            "test_later_provider_work_preserves_phase_f_backend_owners",
        },
        "tests/architecture/test_resource_ref_contract_fitness.py": {
            "test_read15_keeps_one_field_and_deprecations_without_http_implementation",
        },
    }
    for path, changed_tests in permitted.items():
        old = subprocess.run(["git", "show", f"{BASELINE}:{path}"], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout
        old_functions = {
            node.name: ast.dump(node, include_attributes=False)
            for node in ast.parse(old).body if isinstance(node, ast.FunctionDef)
            and node.name not in changed_tests
        }
        current = {
            node.name: ast.dump(node, include_attributes=False)
            for node in ast.parse((ROOT / path).read_text(encoding="utf-8")).body
            if isinstance(node, ast.FunctionDef) and node.name not in changed_tests
        }
        assert current == old_functions
