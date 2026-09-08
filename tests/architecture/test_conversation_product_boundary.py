"""Independent immutable R2 oracles; no modified guard imported at module import."""
from __future__ import annotations

import ast
import hashlib
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
R3_BASELINE = "817ad474d93c78c602a22bd30cf77fe7621e68b1"
BASELINE_R2 = "19c42bc9f4b0b1a97b9bd2d6b880acd7378459f7"
CORRECTION_BASELINE = "0c17d12eea1e1e6d4b04d943e756e0c8e35c41ba"
CORRECTION_PATHS = (
    "backend/adapters/inbound/cli/local_browser.py",
    "backend/infrastructure/composition/factories/conversation.py",
    "backend/infrastructure/composition/bootstrap/conversation_worker.py",
    "backend/adapters/outbound/system/conversation_job.py",
    "backend/adapters/outbound/generation/openai/mapping.py",
    "backend/adapters/outbound/generation/openai/adapter.py",
    "backend/modules/work_orchestration/ports/outbound/generation_job.py",
    "backend/adapters/outbound/openai/transport.py",
    "backend/adapters/outbound/openai/contracts.py",
    "tests/unit/test_openai_conversation_mapping.py",
    "tests/integration/test_conversation_job_lifecycle.py",
    "tests/integration/test_conversation_product.py",
    "tests/integration/test_conversation_http.py",
    "tests/architecture/test_conversation_product_boundary.py",
    "tests/support/conversation_fakes.py",
    "tests/architecture/test_local_browser_product_boundary.py",
    "tests/architecture/test_local_search_product_boundary.py",
    "architecture/adr/ADR-conversational-generation-product-boundary.md",
    "docs/development/phase_12_18_h2_r2_generation/CONVERSATION_HTTP_LOCAL_V1.json",
    "docs/development/phase_12_18_h2_r2_generation/LIVE_GENERATION_SCOPE.json",
    "docs/development/phase_12_18_h2_r2_generation/IMPLEMENTATION_EVIDENCE.md",
    "docs/development/phase_12_18_h2_r2_generation/MANIFEST_SHA256.txt",
)
CORRECTED_GENERATION_HASHES = {
    "backend/adapters/outbound/generation/openai/adapter.py": "8854f9b5dea7d9ddb713d27211a77fe36dff4577ee080f63f5f71925fccc3088",
    "backend/adapters/outbound/generation/openai/mapping.py": "ace7fe0d46f38dd03270160259e2858e86d9bfe98ba57c8492213c29f7f855b7",
}
R2_HISTORY_PATH = "tests/calibration/pedagogical/repair_tranche_v4_2.py"
R2_HISTORY_BASELINE = "6d0d66380757d7502fd967cd0246c5b6ff91d5f8"
R2_HISTORY_ACTIVE_SHA256 = "9b85e5496ed9177bfd11fff896b7bd9bd87b4bf919216c6327172a784cf952d9"
HISTORICAL_R1_ROUTES = (
    (("GET",), "/api/v2/resources/{resource_ref}", None),
    (("GET",), "/api/v2/search", None),
    (("GET", "HEAD"), "/", "index.html"),
    (("GET", "HEAD"), "/assets/app.js", "app.js"),
    (("GET", "HEAD"), "/assets/styles.css", "styles.css"),
)
R2_PATHS = (
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
PREPARATION = {
    "docs/development/phase_12_18_h2_r2_generation_preparation/01_CONTRAT_R2_GENERATION_CONVERSATIONNELLE.md": "aac3f81f5a3a10017a305f5005dd373ccd598cdaee5815fcdb2c5606050df66f",
    "docs/development/phase_12_18_h2_r2_generation_preparation/02_INVENTAIRE_GUARDS_TESTS_PERMISSIONS_R2.json": "b5ed6c00d616b2f7319f2089637f9f0778c7e3eab601caf73a377de00fdd7699",
    "docs/development/phase_12_18_h2_r2_generation_preparation/03_DECISION_ET_PLAN_EXECUTION_R2.md": "f4dfa5de3ed8674c4ed24aeeeeee6bd3c72f214db427357447a3e7975df815ea",
    "docs/development/phase_12_18_h2_r2_generation_preparation/MANIFEST_SHA256.txt": "359b06ab34aa092831bd0d0eea909fc4b030776eef49414edbe7932f97eb9d6c",
}
PROTECTED = {
    "docs/development/phase_12_18_h1_audit_cumulatif/01_BASELINE_ET_PERIMETRE.md": "1a220b89864c0b01634996b04b4784e38faee5fe7fea596f65c51ce8d0d9cecb",
    "docs/development/phase_12_18_h1_audit_cumulatif/02_MATRICE_CUMULATIVE_12_1_12_17.json": "3f1120df875476dc1f140ae394de27831d517c8b4d49ec07c8271075c42029b3",
    "docs/development/phase_12_18_h1_audit_cumulatif/03_ETAT_INTEGRATION_PRODUIT.md": "1d844c64b5e44dd798de3fb81807b1a8a7098f4cc7fa9d5eeeabf87432b8f811",
    "docs/development/phase_12_18_h1_audit_cumulatif/04_ECARTS_ET_PREPARATION_RECETTE.json": "af7e112116448cb076244349bf1de9cdd823ed2071ddeadda84bda4c7821d282",
    "docs/development/phase_12_18_h1_audit_cumulatif/LIVRABLE_12_18_H1_AUDIT_CUMULATIF.md": "c2723ab6f9d943397cc7eb8d36642f76ee555ea36d1ebe96bf31b28a84bfaefd",
    "docs/development/phase_12_18_h1_audit_cumulatif/MANIFEST_SHA256.txt": "259a50779d6c75231e3a3cad8f5d78dc69442b696613719c128fcb4320674ab3",
    "docs/development/phase_12_18_h1a_sources_et_evolution_guard/01_SOURCES_ET_ECARTS_RECONCILIES.json": "a8dd8edc13d505e504a3983bf5598a834f2fb57ba4fead0d3545f1d2848448d3",
    "docs/development/phase_12_18_h1a_sources_et_evolution_guard/02_PROPOSITION_EVOLUTION_GUARD.md": "f019d1e74e079ca2ecfc48f77da8ef3bee6904affa59346b48b59d8d9840a80c",
    "docs/development/phase_12_18_h1a_sources_et_evolution_guard/03_PAQUET_DECISION_ET_PLAN_H2.md": "2e90d55cd1600f71032f197c3aaa61c8aaebb291e792fea5d27a7b89e50a1dad",
    "docs/development/phase_12_18_h1a_sources_et_evolution_guard/LIVRABLE_H1A_SOURCES_ET_GUARD.md": "398a6e2b68e4deb0c720cb309d33ef41c12644c2b49951749739e3b224afc998",
    "docs/development/phase_12_18_h1a_sources_et_evolution_guard/MANIFEST_SHA256.txt": "2c7f3d2b93e4852f9243f6d6631492fc1d413bfb3ab0df4141672fa1ccd932a8",
    "docs/development/phase_12_18_h2_recherche_locale_preparation/01_BASELINE_ET_REUTILISATION.md": "86916ecaf2fbfc2f0d98d39ae18636264c2f02049e7e4dae8ff3d254a3f8c31e",
    "docs/development/phase_12_18_h2_recherche_locale_preparation/02_CONTRAT_RECHERCHE_LOCALE_PROPOSE.md": "664df97c350324af087597f7d17ec4e71ab837129a871959ee3305d61e7ebf0b",
    "docs/development/phase_12_18_h2_recherche_locale_preparation/03_INVENTAIRE_FICHIERS_ET_GUARDS.json": "856c7017b6f943c8575895a3844bfa62053c7574272422be3e8e1bbedb53606a",
    "docs/development/phase_12_18_h2_recherche_locale_preparation/04_DECISION_ET_PLAN_IMPLEMENTATION.md": "777e86b5584eebc59990568b4e82985e89901ea6a2e6b58cf4f032b4eda7df4b",
    "docs/development/phase_12_18_h2_recherche_locale_preparation/LIVRABLE_PROPOSITION_RECHERCHE_LOCALE.md": "b03bbb1be99b2698dff717b864ee59e968f3abe2d366e9e7c658aab60ac450d4",
    "docs/development/phase_12_18_h2_recherche_locale_preparation/MANIFEST_SHA256.txt": "7e210975e1c64ecc29aa73bbbaf48c2e4b099501625fd061f33f0ef13d8f15f4",
}
GUARD_NODES = {
    "tests/architecture/test_calibration_tooling_boundary.py": {"test_all_40_historical_files_are_byte_exact_and_read_only"},
    "tests/architecture/test_repository_hygiene_b06.py": {"test_b01_evidence_stays_tracked_and_historical_freeze_stays_intact"},
    "tests/architecture/test_pedagogical_calibration_fitness.py": {"test_golden_harness_adapters_and_registries_remain_byte_exact"},
    "tests/architecture/test_local_browser_product_boundary.py": {"route_contract_violations", "inventory_violations", "test_existing_pure_contracts_and_original_guards_other_tests_preserved"} ,
    "tests/architecture/test_resource_ref_contract_fitness.py": {"test_read15_keeps_one_field_and_deprecations_without_http_implementation"} ,
    "tests/architecture/test_security_recovery_observability_e2e_fitness.py": {"test_later_provider_work_preserves_phase_f_backend_owners"} ,
    "tests/unit/test_local_browser_product_routes.py": {"test_registry_has_one_business_operation_and_three_assets"} ,
    "tests/architecture/test_local_search_product_boundary.py": {"test_exact_five_routes_preserve_read15", "test_exact_inventory_before_and_after_commit", "test_only_approved_guard_functions_change_and_old_assertions_remain", "test_reused_components_and_history_are_byte_identical"} ,
}
PRE_HASHES = {
    "tests/architecture/test_calibration_tooling_boundary.py": "43f91d0ea1d631588b76c9646edb8ddba16a771393694d4aa8cda95b2c2e2309",
    "tests/architecture/test_repository_hygiene_b06.py": "1d854e51559244b52c3b062bdfbde410653b8fdeff223deead9334eef5d9acfc",
    "tests/architecture/test_pedagogical_calibration_fitness.py": "a04792416e81c09724ba3750836dde9327e177e4535c9deb29917f5d3e8c3ad8",
    "tests/calibration/pedagogical/repair_tranche_v4_2.py": "d1e5b40dd1437aad38f5da0db4797e2670da953ee554f09f4aa1b1f078e9a6b6",
    "backend/adapters/inbound/api/routes.py": "4d2a22e38c9e6667007eec99fd8696bea1bc9a680c1a7c56c25afaecfff1b73e",
    "backend/adapters/inbound/api/server.py": "e1d71f396d4f3dffde4262075d528ae4797489ab7e0d65fb350796b5b3f50f66",
    "backend/adapters/inbound/api/local_browser.py": "cc7ee88ebbb41d17feb301c9707d1ab05efe3d1fa3118be8612c1b4c735d1148",
    "backend/infrastructure/composition/factories/local_browser.py": "29455fcb0703b33a24b531a146d757e8cc1d7dc054ef061084f4afeaee08acdd",
    "backend/adapters/outbound/generation/openai/mapping.py": "77b9419d94c3b5bc6b9317c33dc7fc13bd31d44e44d993d7a41d93b374eabc99",
    "backend/adapters/outbound/generation/openai/adapter.py": "9357224fa7b4c77e4dd0cd7184491597138dd4247bbb5ad75f346c22fbb66be1",
    "frontend/index.html": "a413bbdbe3bc34384d716404eab8c6fbc705469e350625190b0ce85426a8f882",
    "frontend/app.js": "1b5ca2e2a52d273712bd3d347511521a8f0556e8f57d749188d789477761a754",
    "frontend/styles.css": "a03e599ccb62cadef19f1dc8998371395e0337a5084dcd159fa645fc41daed7e",
    "tests/architecture/test_local_browser_product_boundary.py": "7873e130c4ffc52ba81feec9928572bb3658f14cd7c34c2f1460510ad2569d02",
    "tests/architecture/test_resource_ref_contract_fitness.py": "df2b1ca3c7088dee44a36c7542859261fba4de49a1c7840b61b63f39678e68be",
    "tests/architecture/test_security_recovery_observability_e2e_fitness.py": "6fc91a6245747d015afe0a197d9a21e3e33b6c9574cb9239d5d53285cc916584",
    "tests/unit/test_local_browser_product_routes.py": "b2a02bf760161a6a2954e401896cf73f63ba3d64a68cb14d219d89ad77d993ee",
    "tests/architecture/test_local_search_product_boundary.py": "82a70fd64ac1751ba5183ff1cc74ae1e25315341aa4e22a9513fa2e5f2df53d1",
    "backend/adapters/inbound/cli/local_browser.py": "f88bd7ea434fd821c1bbfc0c04c78f5514383b7886a7616cfa5d682b92b3f607",
    "backend/agent_runtime/contracts/planning/delegation.py": "72254e9a36aaf267593b880712cb68b8d3e6d978291d83515d0374c926e8af8f",
}


def git_source(ref: str, path: str) -> bytes:
    return subprocess.run(["git", "show", f"{ref}:{path}"], cwd=ROOT, capture_output=True, check=True).stdout


def git_diff_paths(before: str, after: str) -> list[str]:
    return subprocess.run(["git", "diff", "--name-only", before, after, "--"], cwd=ROOT,
        capture_output=True, check=True, text=True).stdout.splitlines()


def r2_historical_entry_sha256(root: Path, path: str) -> str:
    """HIST-020 only: authenticate fixed historical bytes AND approved active bytes."""
    assert path == R2_HISTORY_PATH
    assert R2_HISTORY_BASELINE == "6d0d66380757d7502fd967cd0246c5b6ff91d5f8"
    raw = git_source(R2_HISTORY_BASELINE, path)
    historical = hashlib.sha256(raw).hexdigest()
    assert historical == PRE_HASHES[path]
    assert hashlib.sha256((root / path).read_bytes()).hexdigest() == R2_HISTORY_ACTIVE_SHA256
    return historical


def preparation_violations(root: Path) -> list[str]:
    violations = []
    # Authenticate manifest first; no trust in a manifest supplied alongside modified documents.
    manifest = next(p for p in PREPARATION if p.endswith("MANIFEST_SHA256.txt"))
    for path in (manifest, *(p for p in PREPARATION if p != manifest)):
        file = root / path
        if not file.is_file() or hashlib.sha256(file.read_bytes()).hexdigest() != PREPARATION[path]:
            violations.append("PREPARATION_CHANGED:" + path)
    return violations


def corrective_inventory_violations(changed: set[str]) -> set[str]:
    return changed ^ set(CORRECTION_PATHS)


def test_correction_exact_delta_and_delivered_65_path_snapshot():
    assert len(CORRECTION_PATHS) == len(set(CORRECTION_PATHS)) == 22
    assert set(git_diff_paths(BASELINE_R2, CORRECTION_BASELINE)) == set(R2_PATHS)
    changed = set(git_diff_paths(CORRECTION_BASELINE, R3_BASELINE))
    from tests.support.r3_guard_oracle import active_inventory
    assert active_inventory(ROOT) == []
    assert corrective_inventory_violations(changed) == set()
    extras = set(CORRECTION_PATHS) - set(R2_PATHS)
    assert extras == {"backend/adapters/outbound/openai/contracts.py", "backend/adapters/outbound/openai/transport.py"}


@pytest.mark.parametrize("kind", ("unknown", "omission", "substitution"))
def test_corrective_inventory_rejects_every_unapproved_delta(kind):
    changed = set(CORRECTION_PATHS)
    if kind != "unknown":
        changed.remove(CORRECTION_PATHS[0])
    if kind != "omission":
        changed.add("backend/UNAPPROVED.py")
    assert corrective_inventory_violations(changed)


def assert_corrective_inventory_assertion_only(source: str) -> None:
    path = "tests/architecture/test_local_search_product_boundary.py"
    expected = ast.parse(git_source(CORRECTION_BASELINE, path))
    function = next(node for node in expected.body if isinstance(node, ast.FunctionDef)
                    and node.name == "test_exact_inventory_before_and_after_commit")
    old = ast.parse("assert inventory_violations(ROOT, set(EXPECTED_R2_INVENTORY)) == []").body[0]
    indexes = [index for index, node in enumerate(function.body) if ast.dump(node) == ast.dump(old)]
    assert len(indexes) == 1
    function.body[indexes[0]] = ast.parse('''assert inventory_violations(ROOT, set(EXPECTED_R2_INVENTORY) | {
        "backend/adapters/outbound/openai/contracts.py",
        "backend/adapters/outbound/openai/transport.py",
    }) == []''').body[0]
    assert ast.dump(ast.parse(source)) == ast.dump(expected)


@pytest.mark.parametrize("mutation", ("none", "historical_count", "shared_path", "extra_statement"))
def test_corrective_inventory_guard_has_exactly_one_approved_assertion_delta(mutation):
    source = git_source(R3_BASELINE, "tests/architecture/test_local_search_product_boundary.py").decode("utf-8")
    if mutation == "historical_count":
        source = source.replace("== 65", "== 64")
    elif mutation == "shared_path":
        source = source.replace('"backend/adapters/outbound/openai/contracts.py",', "")
    elif mutation == "extra_statement":
        source += "\nUNAPPROVED = True\n"
    if mutation == "none":
        assert_corrective_inventory_assertion_only(source)
    else:
        with pytest.raises(AssertionError):
            assert_corrective_inventory_assertion_only(source)


@pytest.mark.parametrize("missing", ("contracts.py", "transport.py", "both"))
def test_active_inventory_still_rejects_missing_shared_openai_modules(missing):
    from tests.architecture.test_local_browser_product_boundary import inventory_violations
    shared = {"backend/adapters/outbound/openai/" + name for name in ("contracts.py", "transport.py")}
    removed = shared if missing == "both" else {"backend/adapters/outbound/openai/" + missing}
    violations = inventory_violations(ROOT, (set(R2_PATHS) | set(CORRECTION_PATHS)) - removed)
    assert set(violations) == {"MISSING_R2_PATH:" + path for path in removed}


def method_ast(source: str, name: str) -> str:
    cls = next(n for n in ast.parse(source).body if isinstance(n, ast.ClassDef)
               and n.name == "LocalBrowserHttpSecurityContract")
    return ast.dump(next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name))


def function_map(source: str) -> dict[str, str]:
    return {n.name: ast.dump(n) for n in ast.parse(source).body if isinstance(n, ast.FunctionDef)}


def assert_r2_guard_nodes_preserved(root: Path) -> None:
    for path, allowed in GUARD_NODES.items():
        before = function_map(git_source(BASELINE_R2, path).decode("utf-8"))
        after = function_map(git_source(R3_BASELINE, path).decode("utf-8"))
        assert before.keys() == after.keys()
        assert {k: v for k, v in before.items() if k not in allowed} == {
            k: v for k, v in after.items() if k not in allowed
        }
    path = "tests/architecture/test_local_browser_product_boundary.py"
    name = "test_existing_pure_contracts_and_original_guards_other_tests_preserved"
    before = next(n for n in ast.parse(git_source(BASELINE_R2, path)).body
                  if isinstance(n, ast.FunctionDef) and n.name == name)
    after = next(n for n in ast.parse((root / path).read_text("utf-8")).body
                 if isinstance(n, ast.FunctionDef) and n.name == name)
    from tests.support.r3_guard_oracle import GUARDS, assert_guard_scope
    assert_guard_scope(root, paths=tuple(p for p in GUARD_NODES if p in GUARDS))
    # Original permitted table and entire historical loop are immutable.
    assert [ast.dump(n) for n in before.body[-2:]] == [ast.dump(n) for n in after.body[-2:]]


def assert_historical_manifest(folder: str, baseline: str, count: int) -> None:
    lines = (ROOT / folder / "MANIFEST_SHA256.txt").read_text("utf-8").splitlines()
    assert len(lines) == count
    for line in lines:
        sha, name = line.split("  ", 1)
        path = (ROOT / folder / name).resolve().relative_to(ROOT).as_posix()
        raw = git_source(baseline, path)
        assert sha in {hashlib.sha256(raw).hexdigest(),
            hashlib.sha256(raw.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")).hexdigest()}


def test_independent_inventory_source_and_pre_identities():
    from tests.architecture.test_local_browser_product_boundary import (
        EXACT_R2_PREPARATION_PATHS,
        EXPECTED_PROTECTED_DOCUMENTS,
        EXPECTED_R2_INVENTORY,
        inventory_violations,
    )
    assert len(R2_PATHS) == 65 and len(set(R2_PATHS)) == 65
    assert tuple(EXPECTED_R2_INVENTORY) == R2_PATHS
    assert dict(EXPECTED_PROTECTED_DOCUMENTS) == PROTECTED
    assert set(EXACT_R2_PREPARATION_PATHS) == set(PREPARATION)
    assert preparation_violations(ROOT) == []
    assert inventory_violations(ROOT) == []
    assert all((ROOT / p).is_file() for p in R2_PATHS)
    for path, sha in PRE_HASHES.items():
        raw = git_source(BASELINE_R2, path)
        assert sha in {hashlib.sha256(raw).hexdigest(),
            hashlib.sha256(raw.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")).hexdigest()}
    assert_r2_guard_nodes_preserved(ROOT)


@pytest.mark.parametrize("path", ["backend/adapters/outbound/generation/extra.py",
    "backend/modules/extra.py", "frontend/extra.js", "requirements/lock/runtime-py312-win.txt"])
def test_no_extra_file_even_under_historical_allowed_prefix(path):
    from tests.architecture.test_local_browser_product_boundary import inventory_violations
    assert path in inventory_violations(ROOT, {path})


def test_guard_oracle_rejects_unapproved_assertion_mutation(tmp_path):
    for path in GUARD_NODES:
        dest = tmp_path / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes((ROOT / path).read_bytes())
    path = tmp_path / "tests/unit/test_local_browser_product_routes.py"
    path.write_text(path.read_text("utf-8").replace('match.resource_ref == "resource:1"', "True"),
                    encoding="utf-8")
    # G06's approved body still preserves its remaining statements: independent check below.
    before = ast.parse(git_source(BASELINE_R2, path.relative_to(tmp_path).as_posix()))
    after = ast.parse(path.read_text("utf-8"))
    name = "test_registry_has_one_business_operation_and_three_assets"
    b = next(n for n in before.body if isinstance(n, ast.FunctionDef) and n.name == name)
    a = next(n for n in after.body if isinstance(n, ast.FunctionDef) and n.name == name)
    assert [ast.dump(n) for n in b.body[1:]] != [ast.dump(n) for n in a.body[1:]]
    other = tmp_path / "tests/architecture/test_local_search_product_boundary.py"
    other.write_text(other.read_text("utf-8").replace('assert frontend_violations(ROOT) == []',
                                                      'assert False'), encoding="utf-8")
    with pytest.raises(AssertionError):
        assert_r2_guard_nodes_preserved(tmp_path)


def test_only_closed_r2_routes_and_pure_security_evolution():
    from backend.adapters.inbound.api.routes import ROUTE_SPECS
    from tests.architecture.test_local_browser_product_boundary import _EXPECTED_ROUTES
    assert ROUTE_SPECS == _EXPECTED_ROUTES
    assert len(ROUTE_SPECS) == 16
    assert tuple(r for r in ROUTE_SPECS if r in HISTORICAL_R1_ROUTES) == HISTORICAL_R1_ROUTES
    path = "backend/adapters/inbound/api/local_browser.py"
    old, current = git_source(BASELINE_R2, path).decode("utf-8"), (ROOT / path).read_text("utf-8")
    old_cls = next(n for n in ast.parse(old).body if isinstance(n, ast.ClassDef)
                   and n.name == "LocalBrowserHttpSecurityContract")
    new_cls = next(n for n in ast.parse(current).body if isinstance(n, ast.ClassDef)
                   and n.name == old_cls.name)
    assert [ast.dump(n) for n in old_cls.body] == [
        ast.dump(n) for n in new_cls.body if not isinstance(n, ast.FunctionDef) or n.name != "authorize_command"
    ]

def assert_r2_generation_source_lineage(root: Path) -> None:
    from tests.support.r3_parse_observability_guard import active_source_matches

    for path, expected in CORRECTED_GENERATION_HASHES.items():
        assert active_source_matches(root, path, expected)
    changes = {
        "backend/adapters/outbound/generation/openai/adapter.py": (
            {"_map_response", "_parse_payload"}, {"_unique_object"}, set(),
            {("backend.adapters.outbound.generation.openai.mapping", "CONVERSATION_OUTPUT_CONTRACT_ID"),
             ("backend.adapters.outbound.generation.openai.mapping", "conversation_evidence_ids")}),
        "backend/adapters/outbound/generation/openai/mapping.py": (
            {"build_openai_request"}, {"conversation_evidence_ids"},
            {"CONVERSATION_OUTPUT_CONTRACT_ID"},
            {("backend.adapters.outbound.openai.contracts", "OpenAIReasoningEffort")}),
    }
    for path, (modified, added, new_constants, new_imports) in changes.items():
        before = ast.parse(git_source(BASELINE_R2, path))
        # Keep the initial R2/legacy AST proof on the immutable delivered snapshot;
        # active corrected sources are independently authenticated above.
        after = ast.parse(git_source(CORRECTION_BASELINE, path))
        old_functions = function_map(ast.unparse(before))
        new_functions = function_map(ast.unparse(after))
        assert new_functions.keys() == old_functions.keys() | added
        assert {k: v for k, v in old_functions.items() if k not in modified} == {
            k: v for k, v in new_functions.items() if k not in modified | added}
        def imports(tree):
            return {(n.module, a.name, a.asname) for n in tree.body
                    if isinstance(n, ast.ImportFrom) for a in n.names}
        assert imports(after) == imports(before) | {(m, n, None) for m, n in new_imports}
        def remainder(tree, ignored_constants=new_constants):
            return [ast.dump(n) for n in tree.body
                if not isinstance(n, (ast.FunctionDef, ast.ImportFrom))
                and not (isinstance(n, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id in ignored_constants for t in n.targets))]
        assert remainder(before) == remainder(after)
        if new_constants:
            assignment = next(n for n in after.body if isinstance(n, ast.Assign)
                and isinstance(n.targets[0], ast.Name) and n.targets[0].id in new_constants)
            assert ast.literal_eval(assignment.value) == "R2-ASSESSMENT-SECTIONS-1.0"


def test_historical_guard_amendment_preserves_other_functions_and_constants():
    path = "tests/calibration/pedagogical/repair_tranche_v4_2.py"
    before = ast.parse(git_source(BASELINE_R2, path))
    after = ast.parse((ROOT / path).read_text("utf-8"))
    old_functions, new_functions = function_map(ast.unparse(before)), function_map(ast.unparse(after))
    changed = {"_contract_sha256", "_bundle_sha256", "validate_live_authorization"}
    added = {"_historical_generation_source", "_assert_current_generation_sources"}
    assert new_functions.keys() == old_functions.keys() | added
    assert {k:v for k,v in old_functions.items() if k not in changed} == {
        k:v for k,v in new_functions.items() if k not in changed | added}
    def declarations(tree):
        return {n.targets[0].id: ast.dump(n) for n in tree.body
            if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)}
    old_constants, new_constants = declarations(before), declarations(after)
    assert new_constants.keys() == old_constants.keys() | {
        "_GENERATION_SOURCE_BASELINE", "_GENERATION_SOURCE_HASHES"}
    assert all(new_constants[k] == value for k, value in old_constants.items())
    old_classes = {n.name:n for n in before.body if isinstance(n, ast.ClassDef)}
    new_classes = {n.name:n for n in after.body if isinstance(n, ast.ClassDef)}
    assert old_classes.keys() == new_classes.keys()
    for name, old_class in old_classes.items():
        current = new_classes[name]
        if name == "RepairTrancheBudgetGuard":
            original = old_class.body[0].body
            amended = current.body[0].body
            assert ast.dump(amended[-2]) == ast.dump(ast.parse("_assert_current_generation_sources()").body[0])
            assert [ast.dump(n) for n in original] == [ast.dump(n) for n in amended[:-2] + amended[-1:]]
        else:
            assert ast.dump(current) == ast.dump(old_class)
    assert_r2_generation_source_lineage(ROOT)


def test_historical_identity_cannot_authorize_current_runtime(monkeypatch):
    from decimal import Decimal

    from tests.calibration.pedagogical import repair_tranche_v4_2 as historical
    assert historical.logical_matrix_sha256() == "605358444f1bc9052ca7b4e55057c9d5424b3ad3b4deecc17bdde83e23c18aa5"
    monkeypatch.setattr(historical, "LIVE_PROVIDER_RECALIBRATION_AUTHORIZED", True)
    monkeypatch.setattr(historical, "APPROVED_REPAIR_TRANCHE_CEILING_USD", Decimal("2.111240"))
    with pytest.raises(historical.RepairPlanError, match="MATRIX_MISMATCH"):
        historical.validate_live_authorization(historical.RepairRuntimeAuthorization(effective=True))


def test_historical_source_reader_fails_closed_on_unknown_corrupt_or_unavailable_blob(monkeypatch):
    import subprocess

    from tests.calibration.pedagogical import repair_tranche_v4_2 as historical
    reader = historical._historical_generation_source
    reader.cache_clear()
    with pytest.raises(historical.RepairPlanError):
        reader("../UNAUTHORIZED")
    with monkeypatch.context() as patch:
        patch.setattr(historical.subprocess, "run", lambda *args, **kwargs:
            subprocess.CompletedProcess(args, 0, stdout=b"CORRUPTED_SYNTHETIC_BLOB"))
        with pytest.raises(historical.RepairPlanError):
            reader(historical._GENERATION_CONTRACT_PATHS[0])
    with monkeypatch.context() as patch:
        def unavailable(*args, **kwargs):
            raise FileNotFoundError("SYNTHETIC_MISSING_GIT")
        patch.setattr(historical.subprocess, "run", unavailable)
        with pytest.raises(historical.RepairPlanError):
            reader(historical._GENERATION_CONTRACT_PATHS[0])
    reader.cache_clear()


def test_active_lineage_rejects_unapproved_class_or_constant_change(tmp_path):
    paths = ("backend/adapters/outbound/generation/openai/adapter.py",
             "backend/adapters/outbound/generation/openai/mapping.py")
    for relative in paths:
        dest = tmp_path / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes((ROOT / relative).read_bytes())
    assert_r2_generation_source_lineage(tmp_path)
    path = tmp_path / paths[1]
    path.write_text(path.read_text("utf-8").replace("_MAX_LIMITATIONS = 16", "_MAX_LIMITATIONS = 160"),
                    encoding="utf-8")
    with pytest.raises(AssertionError):
        assert_r2_generation_source_lineage(tmp_path)


def test_hist020_authenticates_both_sources_and_rejects_wrong_path(tmp_path):
    assert r2_historical_entry_sha256(ROOT, R2_HISTORY_PATH) == PRE_HASHES[R2_HISTORY_PATH]
    with pytest.raises(AssertionError):
        r2_historical_entry_sha256(tmp_path, "tests/calibration/pedagogical/UNAPPROVED.py")
    with pytest.raises(FileNotFoundError):
        r2_historical_entry_sha256(tmp_path, R2_HISTORY_PATH)
    target = tmp_path / R2_HISTORY_PATH
    target.parent.mkdir(parents=True)
    target.write_bytes((ROOT / R2_HISTORY_PATH).read_bytes())
    assert r2_historical_entry_sha256(tmp_path, R2_HISTORY_PATH) == PRE_HASHES[R2_HISTORY_PATH]
    target.write_bytes(target.read_bytes().replace(b"_assert_current_generation_sources()", b"_disabled_guard()"))
    with pytest.raises(AssertionError):
        r2_historical_entry_sha256(tmp_path, R2_HISTORY_PATH)


@pytest.mark.parametrize("mode", ("absent", "corrupted", "wrong_reference"))
def test_hist020_missing_corrupt_or_wrong_reference_never_falls_back(monkeypatch, mode):
    import sys
    module = sys.modules[__name__]
    calls = []
    original = git_source
    def read(ref, path):
        calls.append((ref, path))
        if mode == "absent":
            raise subprocess.CalledProcessError(128, ["git", "show"])
        if mode == "wrong_reference":
            return original("a560d6ca1989ba3dd13c9d02eeb97ef3fff6238b", path)
        return b"CORRUPTED_HISTORICAL_TEST_SOURCE"
    monkeypatch.setattr(module, "git_source", read)
    with pytest.raises((AssertionError, subprocess.CalledProcessError)):
        r2_historical_entry_sha256(ROOT, R2_HISTORY_PATH)
    assert calls == [(R2_HISTORY_BASELINE, R2_HISTORY_PATH)]


def test_hist020_wrong_baseline_even_with_equivalent_blob_is_rejected(monkeypatch):
    import sys
    monkeypatch.setattr(sys.modules[__name__], "R2_HISTORY_BASELINE", BASELINE_R2)
    with pytest.raises(AssertionError):
        r2_historical_entry_sha256(ROOT, R2_HISTORY_PATH)


@pytest.mark.parametrize("stage", ("untracked", "staged", "committed"))
@pytest.mark.parametrize("mutation", ("none", "extra", "substitution", "omission"))
def test_exact_65_path_inventory_at_all_git_states(monkeypatch, stage, mutation):
    from tests.architecture import test_local_browser_product_boundary as guard
    from tests.support.r3_guard_oracle import R3_PATHS
    expected = set(R2_PATHS) | set(CORRECTION_PATHS)
    actual = set(expected)
    extra = "backend/modules/unapproved_r2.py"
    removed = R2_PATHS[0]
    if mutation in {"extra", "substitution"}:
        actual.add(extra)
    if mutation in {"substitution", "omission"}:
        actual.remove(removed)
    if mutation == "substitution":
        assert len(actual) == 67
    calls = []
    def git(args, **kwargs):
        calls.append(args[1:])
        if args == ["git", "diff", "--name-only", BASELINE_R2, R3_BASELINE, "--"]:
            return subprocess.CompletedProcess(args, 0, stdout="\n".join(sorted(actual)))
        if "--cached" in args:
            assert args == ["git", "diff", "--cached", "--name-only", R3_BASELINE, "--"]
            result = set() if stage == "untracked" else set(R3_PATHS)
        elif args[1] == "diff":
            assert args == ["git", "diff", "--name-only", R3_BASELINE, "--"]
            result = set() if stage == "untracked" else set(R3_PATHS)
        else:
            assert args == ["git", "ls-files", "--others", "--exclude-standard"]
            result = set(R3_PATHS) if stage == "untracked" else set()
        return subprocess.CompletedProcess(args, 0, stdout="\n".join(sorted(result)))
    monkeypatch.setattr(guard.subprocess, "run", git)
    violations = guard.inventory_violations(ROOT)
    assert len(calls) == 4
    if mutation == "none":
        assert violations == []
    else:
        assert violations
    if mutation in {"extra", "substitution"}:
        assert extra in violations
    if mutation in {"substitution", "omission"}:
        assert "MISSING_R2_PATH:" + removed in violations


def test_changed_contract_alone_cannot_authorize_same_count_substitution(tmp_path):
    import json

    from tests.architecture.test_local_browser_product_boundary import (
        _CONTRACT,
        inventory_violations,
    )
    document = json.loads((ROOT / _CONTRACT).read_text("utf-8"))
    replacement = "backend/modules/unapproved_r2.py"
    document["approved_inventory"][0] = replacement
    assert len(document["approved_inventory"]) == 65
    target = tmp_path / _CONTRACT
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(AssertionError):
        inventory_violations(tmp_path, set(document["approved_inventory"]))


def test_two_history_guard_nodes_preserve_every_other_top_level_statement():
    cases = (
        ("tests/architecture/test_calibration_tooling_boundary.py",
         "test_all_40_historical_files_are_byte_exact_and_read_only"),
        ("tests/architecture/test_repository_hygiene_b06.py",
         "test_b01_evidence_stays_tracked_and_historical_freeze_stays_intact"),
    )
    for path, name in cases:
        before = ast.parse(git_source(BASELINE_R2, path))
        after = ast.parse((ROOT / path).read_text("utf-8"))
        rest_before = [ast.dump(n) for n in before.body if not (
            isinstance(n, ast.FunctionDef) and n.name == name)]
        rest_after = [ast.dump(n) for n in after.body if not (
            isinstance(n, ast.FunctionDef) and n.name == name)]
        assert rest_before == rest_after
        old = next(n for n in before.body if isinstance(n, ast.FunctionDef) and n.name == name)
        new = next(n for n in after.body if isinstance(n, ast.FunctionDef) and n.name == name)
        if "tooling" in path:
            new_loop = next(n for n in new.body if isinstance(n, ast.For))
            addition = next(n for n in new_loop.body if isinstance(n, ast.If))
            expected_test = ast.parse(
                'entry["path"] == "tests/calibration/pedagogical/repair_tranche_v4_2.py"',
                mode="eval").body
            assert ast.dump(addition.test) == ast.dump(expected_test)
            new_loop.body.remove(addition)
            assert ast.dump(old) == ast.dump(new)
        else:
            # The only removed statement is the all-current assertion. Everything else,
            # including tracked-evidence and exact freeze-manifest proof, is preserved.
            old_assert = next(n for n in old.body if isinstance(n, ast.Expr)
                and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Name)
                and n.value.func.id == "assert_current_historical_hashes")
            position = old.body.index(old_assert)
            replacement_start = next(i for i,n in enumerate(new.body)
                if isinstance(n, ast.ImportFrom)
                and n.module == "tests.architecture.test_conversation_product_boundary")
            replacement_end = next(i for i,n in enumerate(new.body)
                if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
                and isinstance(n.value.func, ast.Name)
                and n.value.func.id == "assert_current_historical_hashes")
            assert replacement_start == position
            new.body[replacement_start:replacement_end + 1] = [old_assert]
            assert ast.dump(old) == ast.dump(new)


@pytest.mark.parametrize("guard_name", ("tooling", "hygiene"))
@pytest.mark.parametrize("entry_index", range(39))
def test_each_other_frozen_source_still_requires_current_bytes(monkeypatch, guard_name, entry_index):
    from tests.architecture import test_calibration_tooling_boundary as tooling
    from tests.architecture import test_repository_hygiene_b06 as hygiene
    entries = [e for e in tooling._freeze()["entries"] if e["path"] != R2_HISTORY_PATH]
    assert len(entries) == 39
    source = ROOT / entries[entry_index]["path"]
    original = Path.read_bytes
    def corrupted_current(path):
        return b"CORRUPTED_CURRENT_TEST_SOURCE" if path == source else original(path)
    monkeypatch.setattr(Path, "read_bytes", corrupted_current)
    with pytest.raises(AssertionError):
        if guard_name == "tooling":
            tooling.test_all_40_historical_files_are_byte_exact_and_read_only()
        else:
            hygiene.test_b01_evidence_stays_tracked_and_historical_freeze_stays_intact()


@pytest.mark.parametrize("statement", (
    "import tests.calibration.pedagogical",
    "from tests.providers.anthropic import forbidden",
))
def test_tooling_import_boundary_still_rejects_historical_imports(tmp_path, monkeypatch, statement):
    from tests.architecture import test_calibration_tooling_boundary as guard
    source = tmp_path / "synthetic_forbidden_import.py"
    source.write_text(statement, encoding="utf-8")
    monkeypatch.setattr(guard, "ACTIVE_ROOTS", (tmp_path,))
    monkeypatch.setattr(guard, "ROOT", tmp_path)
    with pytest.raises(AssertionError):
        guard.test_active_graph_never_imports_historical_calibration_evidence()


@pytest.mark.parametrize("path", (
    "backend/modules/hidden_index_extra.py",
    next(iter(PROTECTED)),
    next(iter(PREPARATION)),
))
def test_index_cannot_be_hidden_by_clean_working_bytes(monkeypatch, path):
    from tests.architecture import test_local_browser_product_boundary as guard
    from tests.support.r3_guard_oracle import R3_PATHS
    def git(args, **kwargs):
        if args == ["git", "diff", "--name-only", BASELINE_R2, R3_BASELINE, "--"]:
            return subprocess.CompletedProcess(args, 0, stdout="\n".join(sorted(set(R2_PATHS) | set(CORRECTION_PATHS))))
        if "--cached" in args:
            assert args == ["git", "diff", "--cached", "--name-only", R3_BASELINE, "--"]
            # Index contains an additional file while worktree content cancels that delta.
            result = {path}
        elif args[1] == "diff":
            result = set(R3_PATHS)
        else:
            result = set()
        return subprocess.CompletedProcess(args, 0, stdout="\n".join(sorted(result)))
    monkeypatch.setattr(guard.subprocess, "run", git)
    violations = guard.inventory_violations(ROOT)
    if path in PROTECTED or path in PREPARATION:
        assert "PROTECTED_DOCUMENT_INDEXED:" + path in violations
    else:
        assert path in violations
