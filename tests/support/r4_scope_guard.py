"""Authenticated, exact R4 successor; no globally exempt directory or historical rewrite."""
from __future__ import annotations

import ast
import hashlib
import re
import subprocess
from functools import lru_cache
from pathlib import Path

BASELINE = "f4ba498ba001dfcae44d76d1a430405cbaf32b3f"
SELF = "tests/support/r4_scope_guard.py"
D3 = "tests/support/r3_d3_scope_guard.py"
ROOT = Path(__file__).resolve().parents[2]
PRE: dict[str, str] = {'tests/support/r3_prepare_contract_alignment_guard.py': '9f071d639a3ecacb28d67c69e0c5ff54dd134fb4f38a585bf75e327ff3f1aa57', 'tests/support/r3_parse_observability_guard.py': 'a54c84325c73b1cbdfd5ec0b8615b871ee8cdcee9ac86b155e7fac32424d9343', 'backend/adapters/inbound/api/routes.py': 'e57ee6575b03439bc3db4d578f982af3e9a135e2009db36b2c4656e819b72af4', 'backend/adapters/inbound/api/server.py': 'cdb8f592a9a831b7c8c648a99641922be137b0100c59bfec71b443d44b53ff57', 'backend/infrastructure/composition/factories/local_browser.py': '9e6d708e67aa96bdab7ad351c583e7b06d259d27e0e072b863a87f1ec1a36915', 'backend/adapters/inbound/cli/local_browser.py': '80fe207668149f2d584527a6c830db2b50bccc7979cd18bb766818abad1f0fab', 'frontend/index.html': '433a231173e7e75f44b25fc2b13b699b90853c8868baa06b86fa1c1489163750', 'frontend/app.js': '30dd09a50db482e59afef399a8dbf15d75a09a62fee60937821c0ff4687b046a', 'tests/support/r3_d3_scope_guard.py': 'a0a9839879146bdb3e4b1c85db39665ed8c2cc2c53906d10b16d3dc639967560', 'tests/support/r3_guard_oracle.py': '35c6495ee7e04060b5f4a7068beb681b7d9f51113ffcf599c2f56d09c5d07863', 'tests/architecture/test_r3_product_boundary.py': '0bf3875818cb830d1333ae05f335ae265a943b4644fd8915c4f9e168eaa307cd', 'tests/architecture/test_local_browser_product_boundary.py': '8b7200e415b018303fceb68c5b5f05d81730f8db029c198fdc5e3f2958e7cebb', 'tests/architecture/test_resource_ref_contract_fitness.py': '19bdca1b66374a0fb4fb2bd5f387059b6b6d7c74305f0b24a4d4993d9b4eda67', 'tests/unit/test_local_browser_product_routes.py': 'a73aadeaeb8bd79d1f1ffe680d3b8dc08ff8ca041696a52af2b0f2d8ecf33672', 'tests/support/r3_portable_clone_guard.py': 'b80b1b44e74329e97d641fbcbb3ea36c676a2b79913dd0861667ddc459038267', 'tests/architecture/test_conversation_product_boundary.py': '5f3432c9ebf52d948a49d996ee538796ca19e925c79b5a3028cd2863f0f9839b', 'tests/architecture/test_local_search_product_boundary.py': '0a06b09bb3953ef8aac416c5f09d31044e16d864737b0ba59fb846455610b65c', 'tests/architecture/test_security_recovery_observability_e2e_fitness.py': 'f7c2e7a8687e9adb76c3fcda8da1f11cc213ecc4306e06e2c5cf3bf9c68f2a44', 'tests/architecture/test_r3_d3_boundary.py': '4e2cfbbe3568628c027e20ce7c9e3d1ea4d49fbf1d1a7cd2c7a7ca825d744f1c', 'tests/support/r3_editorial_correction_guard.py': '5cdc6cc9251b952b03d8000ef8f5db3b778797b90db868e9106baf0b08c93fcf'}
POST: dict[str, str] = {'tests/support/r3_prepare_contract_alignment_guard.py': '1b697453ac24082947f443518ebe15e17ae7d34a2d63a426eb450985b75f6e3e', 'tests/support/r3_parse_observability_guard.py': '50fc58dc1b1065572e410ae04dc823f305d1b7839be31d7bdd1266fc266696b1', 'architecture/adr/ADR-r4-save-reopen-word.md': '5075e453702d1a11906a350dec6f21107ac8df3de163cadf85c2ef8466a81a41', 'docs/development/R4_SAVE_REOPEN_WORD.md': '3de5f813d2539baf2d85605c51c0312c5acc5e8c71985203cd610a1df7ad8ebb', 'backend/modules/work_orchestration/contracts/dto/saved_production.py': '2852c44b2e301bfea9032cb028b3d4a7fa91ba61174ae1bf758116932b97d247', 'backend/modules/work_orchestration/ports/outbound/saved_production.py': '65ecfcfd2e5af1fdd343acae4ea0fe8a5814f61edb5639288f4330369039f08d', 'backend/modules/work_orchestration/application/services/saved_production.py': '142fa4735b678f3cbb43c2fa04caa9fb807aabde271cb7e2823567da1bdbfcd9', 'backend/modules/lifecycle_promotion/contracts/dto/promotion.py': '0dea3c711172198f8a82016cd74060089f49c44ecd080227804465f23290a956', 'backend/modules/lifecycle_promotion/application/commands/promote_saved.py': 'c143ac42c8022eb3e7ac99ee840819b4c942789dba146d3cec415f992f19a27d', 'backend/modules/materialization_export/contracts/dto/word_document.py': '673161d118dc379dd2f85cbb37439a5ddaef93804d45b44828e1edd2127760ac', 'backend/modules/materialization_export/ports/outbound/word_writer.py': 'dbcf14cf1088e4dce78bf7a00ae7b45bafba916c5354e2f4502cc5b4a11a2004', 'backend/modules/materialization_export/application/commands/export_saved.py': '01454095a0eb0ee5c601dd2a479e41ac4ca7ea0752b6eea0764a40375888d23a', 'backend/adapters/outbound/persistence/saved_production.py': '670eb3d26dd156c80e58a74f55780d5926c716c1d26bb5d46d4722c276e4a53f', 'backend/adapters/outbound/export/word.py': '9e52dc031aa0751c01fdfb62899ef417bf4c2497156c4d6b8e3b7611757cf67d', 'backend/adapters/outbound/export/__init__.py': '86b0ad4f981190ecf4ad628106735e93164e6e9c673c3aed44b756788e65ec65', 'backend/adapters/inbound/application/saved_production.py': '064110fd181c122878f715565569f9ef8219b3cdf325362e0b1ce9910dd17d15', 'backend/adapters/inbound/api/saved_production.py': '04c4dcbd885862566ce652b8d4fce669c1017c49027427fe081f3d405dd42396', 'backend/adapters/inbound/api/routes.py': '5e485c21ba750d07bd3ad968f13eb0f9cbf66c4e425b9a6e72e312179ff7eb50', 'backend/adapters/inbound/api/server.py': 'eae7b08f346484196beb006f43a29e0f7ed6d92a934b4cac637cbec231cfe381', 'backend/infrastructure/composition/factories/local_browser.py': 'd707396048f61ea00febfb52bd83b394ab3c29c8344f4e7e3f9d6e97ee8a7a6a', 'backend/adapters/inbound/cli/local_browser.py': '078851614b0c40f1647d14555f1b0928caa9e4ff84155ac2a42f760c8bcbf17a', 'frontend/index.html': '1be77f30ab7af0b7e3f3b8169dd58dd2981b920878367d29a6f19d0d992b84d9', 'frontend/app.js': '15c18c2e5f5fdb5bc3e2e64f683a98b100b0de53e20654d1e716e23bcbbd1a95', 'tests/support/r4_synthetic.py': 'f8a348d528cf5372840fe02cf10baaf093137d1ba2931fbb1a69d886b663e55b', 'tests/support/r3_d3_scope_guard.py': 'e457fc39fba4cf7a9f9c949097a2fb9f77662fec1cf48fd07eda04538f29abeb', 'tests/support/r3_guard_oracle.py': '9a190ac8acbf2d4a6dbfb2995cb6ab030a6814c43312656a6e8961cf90ea8924', 'tests/architecture/test_r4_product_boundary.py': 'c443f6fd98f29b6fe3f463f7b618971c6ee4cd3661d0dd1ef490f0ccfbc9ff68', 'tests/architecture/test_r3_product_boundary.py': 'eb87c89427cca05cc320a61c5fe73d0e8ff978566670c3bb8976415ec5a93bbb', 'tests/architecture/test_local_browser_product_boundary.py': '58f43bf3b393d160c1dd51f5b1d9886f8c0add4d8d1451db31cf8ab622a0e520', 'tests/architecture/test_resource_ref_contract_fitness.py': '52c6f1630472511da6d691fd35ec75cc5bb71a795ccd3b5d860625b1ab91edc8', 'tests/unit/test_local_browser_product_routes.py': '9c9732646c37ac0af91078bb86d6e6fddd62383013c75d1035721ceba3f3e892', 'tests/unit/test_r4_saved_production.py': '7c1d6511cde8e055dca9e15683d17efc8df7925a352d7b2d1a6d253c53b4a919', 'tests/unit/test_r4_promotion.py': 'ee7384693ea5dfc7f6b26e183cb3b98e132be7488ee247996439d478a9621eb2', 'tests/unit/test_r4_word.py': '3b18777320a0fb78658cd1b4d4ed0b57c21d3a1a672fa5c79ca24845bc10c37b', 'tests/integration/test_r4_local_http.py': '66bff6e0a4c72cae0742b9a37de23fa6daa69305aefdf44e7e0730df4e980d8e', 'tests/unit/test_r4_scope_guard.py': '75beb67839ff2f5fc19b38b41ea33c6f30408d854be1445fbb8538cf3fce4347', 'tests/support/r3_portable_clone_guard.py': '7be3f790ab9c83308cee6d0128c8bb726e5638bd6aa2be68863c986490adfab5', 'tests/architecture/test_conversation_product_boundary.py': 'fc8a1bf532bf675f3d8417e9e5190c83aa0e41ecb994a46519c9ac0577f53d9d', 'tests/architecture/test_local_search_product_boundary.py': '7943869796f279ebabf662c0c3885ad3654812c62b7538038e6ce84abc181d74', 'tests/architecture/test_security_recovery_observability_e2e_fitness.py': '466c11aa8098629adc23705748c4668fe34f29031863b9dc0dd9ac66023b51f7', 'tests/architecture/test_r3_d3_boundary.py': 'bd48434cc848c98c7ae2a4132e6766f95f3f5d984378732b7f748318475a4a7c', 'tests/support/r3_editorial_correction_guard.py': '8ee1609f594a9ba3a217589d160c4a3d121c76bc8773a535c141ba362af58c3e'}
SYMBOLS: dict[str, list[str]] = {'tests/support/r3_editorial_correction_guard.py': ['violations'], 'tests/support/r3_prepare_contract_alignment_guard.py': ['successor_violations'], 'tests/support/r3_parse_observability_guard.py': ['assert_guard_extension', 'patch_violations'], 'frontend/app.js': [], 'frontend/index.html': [], 'backend/adapters/inbound/api/routes.py': ['ROUTE_SPECS', 'RouteMatch.r4_operation', 'RouteMatch.document_kind', 'resolve_route'], 'backend/adapters/inbound/api/server.py': ['LocalRead15Service.__init__', 'LocalRead15Service._conversation'], 'backend/infrastructure/composition/factories/local_browser.py': ['LocalRead15Composition.saved', 'build_local_read15', 'build_saved_application', 'build_local_saved'], 'backend/adapters/inbound/cli/local_browser.py': ['main'], 'tests/support/r3_guard_oracle.py': ['active_inventory', 'assert_guard_scope'], 'tests/support/r3_d3_scope_guard.py': ['source_bytes', 'index_matches', 'violations'], 'tests/support/r3_portable_clone_guard.py': ['index_matches', 'violations'], 'tests/architecture/test_r3_product_boundary.py': ['test_exact_closed_inventory_owners_and_protected_identities', 'test_no_r3_live_grant_route_export_promotion_or_credential_discovery'], 'tests/architecture/test_local_browser_product_boundary.py': ['_EXPECTED_ROUTES', 'route_contract_violations', 'test_a7_closed_registry_rejects_extra_routes_outside_or_inside_registry'], 'tests/architecture/test_resource_ref_contract_fitness.py': ['test_read15_keeps_one_field_and_deprecations_without_http_implementation'], 'tests/unit/test_local_browser_product_routes.py': ['test_registry_has_one_business_operation_and_three_assets'], 'tests/architecture/test_conversation_product_boundary.py': ['test_only_closed_r2_routes_and_pure_security_evolution', 'test_exact_65_path_inventory_at_all_git_states', 'test_active_lineage_rejects_unapproved_class_or_constant_change'], 'tests/architecture/test_local_search_product_boundary.py': ['test_exact_five_routes_preserve_read15'], 'tests/architecture/test_security_recovery_observability_e2e_fitness.py': ['test_later_provider_work_preserves_phase_f_backend_owners'], 'tests/architecture/test_r3_d3_boundary.py': ['test_exact_scope_and_protected_contracts']}
PATHS: tuple[str, ...] = ('tests/support/r3_prepare_contract_alignment_guard.py', 'tests/support/r3_parse_observability_guard.py', 'architecture/adr/ADR-r4-save-reopen-word.md', 'docs/development/R4_SAVE_REOPEN_WORD.md', 'backend/modules/work_orchestration/contracts/dto/saved_production.py', 'backend/modules/work_orchestration/ports/outbound/saved_production.py', 'backend/modules/work_orchestration/application/services/saved_production.py', 'backend/modules/lifecycle_promotion/contracts/dto/promotion.py', 'backend/modules/lifecycle_promotion/application/commands/promote_saved.py', 'backend/modules/materialization_export/contracts/dto/word_document.py', 'backend/modules/materialization_export/ports/outbound/word_writer.py', 'backend/modules/materialization_export/application/commands/export_saved.py', 'backend/adapters/outbound/persistence/saved_production.py', 'backend/adapters/outbound/export/word.py', 'backend/adapters/outbound/export/__init__.py', 'backend/adapters/inbound/application/saved_production.py', 'backend/adapters/inbound/api/saved_production.py', 'backend/adapters/inbound/api/routes.py', 'backend/adapters/inbound/api/server.py', 'backend/infrastructure/composition/factories/local_browser.py', 'backend/adapters/inbound/cli/local_browser.py', 'frontend/index.html', 'frontend/app.js', 'tests/support/r4_synthetic.py', 'tests/support/r4_scope_guard.py', 'tests/support/r3_d3_scope_guard.py', 'tests/support/r3_guard_oracle.py', 'tests/architecture/test_r4_product_boundary.py', 'tests/architecture/test_r3_product_boundary.py', 'tests/architecture/test_local_browser_product_boundary.py', 'tests/architecture/test_resource_ref_contract_fitness.py', 'tests/unit/test_local_browser_product_routes.py', 'tests/unit/test_r4_saved_production.py', 'tests/unit/test_r4_promotion.py', 'tests/unit/test_r4_word.py', 'tests/integration/test_r4_local_http.py', 'tests/unit/test_r4_scope_guard.py', 'tests/support/r3_portable_clone_guard.py', 'tests/architecture/test_conversation_product_boundary.py', 'tests/architecture/test_local_search_product_boundary.py', 'tests/architecture/test_security_recovery_observability_e2e_fitness.py', 'tests/architecture/test_r3_d3_boundary.py', 'tests/support/r3_editorial_correction_guard.py')
SELF_SHA256 = "82088bbc687b3aa1b781a65cbdf0f4dd2388f154a80de3c63e17733519b71364"


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def canonical(path: str, raw: bytes) -> bytes:
    raw = raw.replace(b"\r\n", b"\n")
    if path == SELF:
        raw = re.sub(rb'^SELF_SHA256 = "[^"\n]+"\n', b"", raw, flags=re.M)
    if path == D3:
        raw = re.sub(rb'^(    r4_successor_sha256 = ")[^"\n]+("\n)', rb'\g<1>PIN\g<2>', raw, flags=re.M)
    return raw


def read(root: Path, path: str) -> bytes:
    from tests.support.r5_scope_guard import baseline_view
    r5_successor_sha256 = "aee6c0dc70529120635149acf0dd053eac832f1c74db5278307fcab650c04e68"
    return baseline_view(root, path, expected=r5_successor_sha256)


@lru_cache(maxsize=64)
def baseline(path: str) -> bytes:
    assert path in PRE
    raw = subprocess.run(["git", "show", f"{BASELINE}:{path}"], cwd=ROOT,
                         check=True, capture_output=True).stdout
    assert digest(raw) == PRE[path], path
    return raw


def outside_scope(path: str, raw: bytes) -> str:
    text = raw.decode("utf-8").replace("\r\n", "\n")
    if path == "frontend/app.js":
        return text.split("\n// R4: a saved document", 1)[0].rstrip()
    if path == "frontend/index.html":
        # Exactly one added section and the two explicitly corrected retention notices.
        text = re.sub(r'    <section class="workspace" aria-labelledby="r4-heading">.*?    </section>\n', "", text, flags=re.S)
        return text.replace("Tout est perdu à l’arrêt sans sauvegarde explicite des versions.", "Tout est perdu à l’arrêt.").replace(
            "Sauvegardez explicitement les versions à conserver.", "Session volatile : tout est perdu à l’arrêt.")
    tree = ast.parse(raw)
    allowed = set(SYMBOLS.get(path, []))
    def strip(nodes, prefix=""):
        result = []
        for node in nodes:
            name = prefix + getattr(node, "name", "")
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                continue  # Exact imported module additions are pinned by POST, checked by boundaries.
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and name in allowed:
                continue
            if isinstance(node, ast.ClassDef):
                node.body = strip(node.body, name + ".")
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                target = node.target if isinstance(node, ast.AnnAssign) else node.targets[0]
                if isinstance(target, ast.Name) and (prefix + target.id in allowed or target.id.startswith("R4_")):
                    continue
            result.append(node)
        return result
    tree.body = strip(tree.body)
    return ast.dump(tree)


def authenticated(*, expected: str = SELF_SHA256) -> bool:
    try:
        return expected == SELF_SHA256 and len(expected) == 64 and digest(canonical(SELF, read(ROOT, SELF))) == expected
    except (OSError, ValueError):
        return False


def exact(root: Path, path: str) -> bool:
    try:
        raw = read(root, path)
        if path == SELF:
            return digest(canonical(path, raw)) == SELF_SHA256
        return (digest(canonical(path, raw)) == POST.get(path)
                and (path not in PRE or outside_scope(path, raw) == outside_scope(path, baseline(path))))
    except (OSError, ValueError, SyntaxError, AssertionError):
        return False


def baseline_view(root: Path, path: str, *, expected: str = SELF_SHA256) -> bytes:
    if path in PRE and authenticated(expected=expected) and exact(root, path):
        return baseline(path)
    return read(root, path)


def index_matches(root: Path, path: str, raw: bytes) -> bool:
    from tests.support.r5_scope_guard import index_matches as r5_index
    if r5_index(root, path, raw):
        return True
    return (path in PATHS and authenticated() and exact(root, path)
            and (digest(raw) == digest(read(root, path)) or digest(raw) == PRE.get(path)))


def violations(root: Path, *, changed: set[str] | None = None) -> list[str]:
    from tests.support.r5_scope_guard import PATHS as R5_PATHS
    from tests.support.r5_scope_guard import violations as r5_violations
    errors = [] if authenticated() else ["R4_ORACLE_IDENTITY"]
    errors += r5_violations(root)
    if set(POST) != set(PATHS) - {SELF}:
        errors.append("R4_INVENTORY_IDENTITY")
    errors += ["R4_IDENTITY:" + path for path in PATHS if not exact(root, path)]
    if changed is not None:
        errors += ["R4_UNAPPROVED:" + p for p in sorted(changed - set(PATHS) - set(R5_PATHS))]
        errors += ["R4_MISSING:" + p for p in sorted(set(PATHS) - changed)]
    return errors


R4_ROUTES = (
    (("GET", "POST"), "/api/v2/conversation/saved", None),
    (("GET",), "/api/v2/productions/{production_ref}/versions/{version_ref}/saved", None),
    (("POST",), "/api/v2/productions/{production_ref}/versions/{version_ref}/saved-validation", None),
    (("GET", "POST"), "/api/v2/productions/{production_ref}/versions/{version_ref}/promotion", None),
    (("GET",), "/api/v2/productions/{production_ref}/versions/{version_ref}/preview/{document_kind}", None),
    (("GET",), "/api/v2/productions/{production_ref}/versions/{version_ref}/word/{document_kind}", None),
)
