"""Closed D3 successor: exact bytes, scoped AST, independent index and private-source rules."""
from __future__ import annotations

import ast
import hashlib
import re
import subprocess
from functools import lru_cache
from pathlib import Path

BASELINE = "6e43ca5a58cb50a71de87d099812ec340e8be686"
SELF = "tests/support/r3_d3_scope_guard.py"
PORTABLE = "tests/support/r3_portable_clone_guard.py"
PRE = {
    "backend/modules/work_orchestration/application/services/r3_review_modify.py": "98a2368e21617978f3b2be67fdc4d8155c6dac7781dd2b14a98066bd4a776d3e",
    "backend/adapters/outbound/persistence/conversation_memory.py": "9eaae7f7f2b72278014f028cf19cada94b213988c3147be64f96c41909481c08",
    "backend/infrastructure/composition/bindings/r3_agents.py": "19f64b4b745ec81103312aaf8f879b9ef030fdea56898689eec9fbc91af233ca",
    "backend/adapters/outbound/generation/assessment_revision.py": "9d88137443e6e3235e04b50008e7e080d23657573ef19aa1b63f3b6856aeab6b",
    "backend/adapters/outbound/generation/openai/mapping.py": "86e6e51830cf5ea70fc25507d643fcb63da144a6a0f1dcc42fa65b933d671438",
    "backend/adapters/outbound/generation/openai/adapter.py": "409adc317691285eb03bbbba672c5ecaae2a80ca83158d486d3234c6f291c384",
    "frontend/app.js": "e453430c2a0a1a0800fb0a8e05c9d20465b23140fc7f24048229951f16648d8a",
    "tests/support/r3_guard_oracle.py": "34c8b0f2330c863cc070167b3a0c4a9798caf5591e8ab0e03de787116b80172a",
    "tests/support/r3_parse_observability_guard.py": "920f31c96736a2c8c80ffd9e898c781752ed6ff83f5ace58dd3b730d4e228316",
    "tests/support/r3_prepare_contract_alignment_guard.py": "3d3d2de2e4946dc12ec1b1d4438ac64decaca16f2ba04a4e6946c78f84c721e5",
    "tests/support/r3_serializer_8192_guard.py": "52adce9e71a95695693dc5c89c2f9c0d69a17464861077aebc1772c933d57902",
    "tests/support/r3_cap_a01_guard.py": "1f2a17be26637258342cf107795d54a700bfb16b3f31c82a3399cbd956036e22",
    "tests/support/r3_locator_materialization_guard.py": "a547524602d677ef3f5133c7bc2cade8e64ab921ced965af62b7c7ebe4eb4766",
    "tests/support/r3_editorial_correction_guard.py": "b31950522adc29909c7dd017d4b16ffa1a8da15f641c36d3733170bc0df0aecd",
    "tests/support/r3_portable_clone_guard.py": "72ceadc15196b34b29e84c70f50b25095cc5ad6e0e96761a7d5653bcd85a6808",
    "tests/architecture/test_r3_editorial_correction_boundary.py": "35aa4b37e08927e91ca29f45ce94ee55c187ff93eeed5235d3af083b1c377997",
    "tests/unit/test_r3_portable_clone_guard.py": "890999df2339943cc6b3d4bec581cbeef25e6faacf7e838d29ee8a369568de78",
    "tests/unit/test_r3_parse_observability.py": "b1289897fc165677730ea922433667057dcba075f739875f05a0bedd9e2c3f96",
    "tests/unit/test_r3_prepare_contract_alignment.py": "48b8359ac6618632a12faf4e98f51e53f93ab221b00f019bf4c5d07538efdf4c",
    "tests/unit/test_r3_prepare_serialization.py": "246ac04d79fb43d6421a7d621d28c076dd4c7886404fec497dea8e1a689c4a44",
    "tests/unit/test_r3_cap_a01_targeted.py": "96414f9921541cdbb9cf6c85e5e5a19bf1764ffcdc52351d22128d60ac5e018b",
    "tests/unit/test_r3_locator_materialization.py": "fb1b5990d5ae67ddd9448eb6d8bd6d7f2005f1fd7f5870e56bcf0663d0cd359e"
}
CREATES = [
    "backend/modules/work_orchestration/contracts/dto/r3_restoration.py",
    "backend/infrastructure/composition/factories/r3_d3_recovery.py",
    "backend/infrastructure/composition/bindings/r3_harden_projection.py",
    "backend/adapters/outbound/generation/openai/harden_contract.py",
    "backend/adapters/outbound/generation/openai/harden_materialization.py",
    "backend/infrastructure/composition/factories/r3_harden_serialization.py",
    "backend/infrastructure/composition/factories/r3_harden_profile.py",
    "backend/infrastructure/composition/factories/r3_harden_execution.py",
    "tests/support/r3_d3_scope_guard.py",
    "tests/support/r3_d3_fixtures.py",
    "tests/unit/test_r3_restoration.py",
    "tests/integration/test_r3_d3_recovery.py",
    "tests/unit/test_r3_dependency_refusal.py",
    "tests/integration/test_r3_d3_product.py",
    "tests/integration/test_r3_d3_http.py",
    "tests/unit/test_r3_harden_wire.py",
    "tests/unit/test_r3_harden_execution.py",
    "tests/architecture/test_r3_d3_boundary.py",
    "tests/unit/test_r3_d3_scope_guard.py",
    "architecture/adr/ADR-r3-d3-restoration-harden-boundary.md",
    "docs/development/phase_12_18_h2_r3_d3/README.md",
    "docs/development/phase_12_18_h2_r3_d3/RESTORATION_CONTRACT.json",
    "docs/development/phase_12_18_h2_r3_d3/HARDEN_CONTRACT.json",
    "docs/development/phase_12_18_h2_r3_d3/IMPLEMENTATION_SCOPE.json"
]
PATHS = tuple(PRE) + tuple(CREATES)
SYMBOLS = {
    "backend/modules/work_orchestration/application/services/r3_review_modify.py": [
        "DIAGNOSTIC_CODES",
        "R3ReviewModifyService.__init__",
        "R3ReviewModifyService._validation",
        "R3ReviewModifyService.poll",
        "R3ReviewModifyService.close"
    ],
    "backend/adapters/outbound/persistence/conversation_memory.py": [
        "ConversationMemoryStore.from_r3_restoration"
    ],
    "backend/infrastructure/composition/bindings/r3_agents.py": [
        "transform"
    ],
    "backend/adapters/outbound/generation/assessment_revision.py": [
        "AssessmentRevisionAdapter.propose"
    ],
    "backend/adapters/outbound/generation/openai/mapping.py": [
        "build_openai_request"
    ],
    "backend/adapters/outbound/generation/openai/adapter.py": [
        "OpenAIGenerationAdapter.generate",
        "_map_response_body"
    ],
    "frontend/app.js": [
        "r3Command"
    ],
    "tests/support/r3_guard_oracle.py": [
        "active_inventory"
    ],
    "tests/support/r3_parse_observability_guard.py": [
        "patch_violations"
    ],
    "tests/support/r3_prepare_contract_alignment_guard.py": [
        "successor_violations",
        "assert_successor_git_state"
    ],
    "tests/support/r3_serializer_8192_guard.py": [
        "violations",
        "assert_git_state"
    ],
    "tests/support/r3_cap_a01_guard.py": [
        "violations",
        "assert_git_state"
    ],
    "tests/support/r3_locator_materialization_guard.py": [
        "violations",
        "assert_git_state"
    ],
    "tests/support/r3_editorial_correction_guard.py": [
        "violations",
        "assert_git_state"
    ],
    "tests/support/r3_portable_clone_guard.py": [
        "authenticated",
        "source_matches",
        "baseline_view",
        "index_matches",
        "violations",
        "assert_scope",
        "assert_git_state"
    ],
    "tests/architecture/test_r3_editorial_correction_boundary.py": [
        "test_each_source_mutation_missing_or_replaced_is_rejected",
        "test_m09_pure_contract_and_no_provider_editorial_route"
    ],
    "tests/unit/test_r3_portable_clone_guard.py": [
        "copy_successor",
        "test_signatures_and_outside_scope_nodes_remain_protected"
    ],
    "tests/unit/test_r3_parse_observability.py": [
        "test_every_patch_source_mutation_is_rejected"
    ],
    "tests/unit/test_r3_prepare_contract_alignment.py": [
        "copied_sources",
        "test_selection_is_exact_and_other_requests_byte_equivalent"
    ],
    "tests/unit/test_r3_prepare_serialization.py": [
        "test_each_successor_source_mutation_is_rejected"
    ],
    "tests/unit/test_r3_cap_a01_targeted.py": [
        "test_each_targeted_successor_identity_is_closed"
    ],
    "tests/unit/test_r3_locator_materialization.py": [
        "test_every_successor_file_mutation_is_rejected"
    ]
}
POST: dict[str, str] = {
    "backend/modules/work_orchestration/application/services/r3_review_modify.py": "69cfb192fb672deaa9caa915c4aa57c01607fa326b2752792093081698af0558",
    "backend/adapters/outbound/persistence/conversation_memory.py": "67f7610d0daa3bd45ee9b746aad4e4bcb53d7ab12916626f39f6c805ba45d77d",
    "backend/infrastructure/composition/bindings/r3_agents.py": "af6450df990ab8b211a48bb00d1be32c87681bd4877e3da21c5b6361962a7208",
    "backend/adapters/outbound/generation/assessment_revision.py": "4b1fc2e4ff46484f3a4e28426a2adc37812676920d68644dbbe42c64cb88b27d",
    "backend/adapters/outbound/generation/openai/mapping.py": "3d48f9538a6c7fe39b8992342c33350431946a2870bed085615c8f54365da3ed",
    "backend/adapters/outbound/generation/openai/adapter.py": "747bb1d21843c4da57f62bd248e9b762fa99351627d98996eb55c8e848f342a4",
    "frontend/app.js": "30dd09a50db482e59afef399a8dbf15d75a09a62fee60937821c0ff4687b046a",
    "tests/support/r3_guard_oracle.py": "35c6495ee7e04060b5f4a7068beb681b7d9f51113ffcf599c2f56d09c5d07863",
    "tests/support/r3_parse_observability_guard.py": "a54c84325c73b1cbdfd5ec0b8615b871ee8cdcee9ac86b155e7fac32424d9343",
    "tests/support/r3_prepare_contract_alignment_guard.py": "9f071d639a3ecacb28d67c69e0c5ff54dd134fb4f38a585bf75e327ff3f1aa57",
    "tests/support/r3_serializer_8192_guard.py": "73f616ac465a836cdbcf5838b76c84639ad0d9e15158d51afef507259dbd036d",
    "tests/support/r3_cap_a01_guard.py": "bf9de68f53e3227a05a09bda089972a2f1785f74f16d593fff495fda5a63a752",
    "tests/support/r3_locator_materialization_guard.py": "777a36976277cee25cefe9b59e31d3708a4a7f40626d1c7a35e56891f043b74e",
    "tests/support/r3_editorial_correction_guard.py": "5cdc6cc9251b952b03d8000ef8f5db3b778797b90db868e9106baf0b08c93fcf",
    "tests/support/r3_portable_clone_guard.py": "e27ad7f499cb23e65de1c38401be69b799c26cc58311dd10ae7cb21655c911af",
    "tests/architecture/test_r3_editorial_correction_boundary.py": "c875207bed120f8738263a959b965f260dc6e205a806f8031dc6e15967dc31c4",
    "tests/unit/test_r3_portable_clone_guard.py": "b66885b0518b2611dca6bf4e80f5c7e74cb1b52e5e230e472a672aa1d3f23db5",
    "tests/unit/test_r3_parse_observability.py": "1100d8c5e3a522b94b869c2375940c4054a607be236767be5e13e1f6f31c28d0",
    "tests/unit/test_r3_prepare_contract_alignment.py": "14c991fdf2a46725fe35ebf65ba780e876d7fb2f655cf0f2afbdf413b7bfc37a",
    "tests/unit/test_r3_prepare_serialization.py": "0cc99d2811eef67ea5b0f24d060c32ddd4c7c3645bebacfe909fad16bb7d3cbb",
    "tests/unit/test_r3_cap_a01_targeted.py": "863853ccc430e2605f3ef546a5512a1e8d8a86f134f2b1c68ae92d48ae37ae0a",
    "tests/unit/test_r3_locator_materialization.py": "0563f2288ce587b1bed44995c380b889ea07835b39c762e741e598a02814c306",
    "backend/modules/work_orchestration/contracts/dto/r3_restoration.py": "0112a107983bd52a59e6b8f0a717cc2cfce3e7ee58e60b49a3ab1210884fd966",
    "backend/infrastructure/composition/factories/r3_d3_recovery.py": "56054d2c2f02ad356e650df1792bbcc42483e7bf5cc3377fcfceeff7cb40cceb",
    "backend/infrastructure/composition/bindings/r3_harden_projection.py": "21e9fb0078e259b528f16bb8c337fff07600bba524d95b2026f0babd55af928c",
    "backend/adapters/outbound/generation/openai/harden_contract.py": "d18cbf1a8289d618e779b55345b861a0173c48bd875eaedf13967807da2c7ebd",
    "backend/adapters/outbound/generation/openai/harden_materialization.py": "2ed6e6c336ba7061c7da445eacb782d20ac7c4a3796dbec65307bbaa06f7b2e1",
    "backend/infrastructure/composition/factories/r3_harden_serialization.py": "7475ea2b84d080fd9f8e853042720a06401e0c624a48dadc855656a38ebd69a7",
    "backend/infrastructure/composition/factories/r3_harden_profile.py": "b6774f36d97c331f1ad42b4a744bda34d198378996a8fc32c18662407120a42a",
    "backend/infrastructure/composition/factories/r3_harden_execution.py": "60f11dd1f30587bca5e16e532f7f7e622268858ed06a46a7792aa5b9f7697531",
    "tests/support/r3_d3_fixtures.py": "fbd63ad54822fd9a36da54644d52fad95a708f79349f37a2a50db040822763f4",
    "tests/unit/test_r3_restoration.py": "3b7207b16a8ddf1520e8a08d608196d80a514a46cfa9c061aed727b8a702dde6",
    "tests/integration/test_r3_d3_recovery.py": "03b82d72b6fba7902253b57b2992b0995517cf30f3ae69b05352567a57c19d5c",
    "tests/unit/test_r3_dependency_refusal.py": "f7d3ef21d9fc52a56f06213e97f49cccfee203f6b7ccb250215591bf835a031b",
    "tests/integration/test_r3_d3_product.py": "8b8c6bbf5222de2b2f9ad0adef5bee3537a392f6b5f0631c6616a250f36bc33e",
    "tests/integration/test_r3_d3_http.py": "f5c291a68c75246018c38dd6051ee5e1322c47d63134918ddbd3a6446fc3b1b7",
    "tests/unit/test_r3_harden_wire.py": "26185aeb28722a4cb3b21f2a9e5037b6ddfdea3689614fcc8ca84438fa85be9c",
    "tests/unit/test_r3_harden_execution.py": "dcac97eb098a1af746147184903af0f5de8bc5f95230f364cd4f7b9d3e82a2e3",
    "tests/architecture/test_r3_d3_boundary.py": "4e2cfbbe3568628c027e20ce7c9e3d1ea4d49fbf1d1a7cd2c7a7ca825d744f1c",
    "tests/unit/test_r3_d3_scope_guard.py": "ec28285ad7400019fda9f5a63f37fcbaef893986ac3078632b0cc1df3346c768",
    "architecture/adr/ADR-r3-d3-restoration-harden-boundary.md": "61a9297306fb887e2b54f7ec6a3423330f91b61afe6614f99d6431154da495f4",
    "docs/development/phase_12_18_h2_r3_d3/README.md": "8573bedc4b47a1358c9f68595a456bc6e3b381bc5060940b8dc75d4c3a365281",
    "docs/development/phase_12_18_h2_r3_d3/RESTORATION_CONTRACT.json": "03c52ca355d280ca09c7d243778d133429e4304fe6abd0b7b5b4caa5c3149cc7",
    "docs/development/phase_12_18_h2_r3_d3/HARDEN_CONTRACT.json": "78f438f0898bfa7a0ec09acf7fd027214e7905915c8239a751645d9688666b61",
    "docs/development/phase_12_18_h2_r3_d3/IMPLEMENTATION_SCOPE.json": "c6942cce8eedcd7380f2834b6496dc0c3fe258641c0f0396a8c70ddbe886d193"
}
ORACLE_SHA256 = "f89b6688842c7badd43bc83007ef379df89e4da4ffa4f6484de3f356b96e0884"


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def source_bytes(root: Path, path: str) -> bytes:
    from tests.support.r3_portable_clone_guard import source_bytes as read
    return read(root, path)


def canonical_bytes(path: str, raw: bytes) -> bytes:
    raw = raw.replace(b"\r\n", b"\n")
    if path == SELF:
        raw, count = re.subn(rb'^ORACLE_SHA256 = "[0-9a-f]{64}"\n', b"", raw, flags=re.MULTILINE)
        if count != 1:
            raise ValueError("D3_SELF_DECLARATION")
    elif path == PORTABLE:
        raw, count = re.subn(rb'^(    d3_successor_sha256 = ")[0-9a-f]{64}("\n)',
            rb"\g<1>" + b"0" * 64 + rb"\g<2>", raw, flags=re.MULTILINE)
        if count != 1:
            raise ValueError("D3_BINDING_DECLARATION")
    return raw


def authenticated(root: Path, *, expected: str = ORACLE_SHA256) -> bool:
    try:
        raw, portable = source_bytes(root, SELF), source_bytes(root, PORTABLE)
        return (expected == ORACLE_SHA256 and expected != "0" * 64
            and digest(canonical_bytes(SELF, raw)) == expected
            and b'ORACLE_SHA256 = "' + expected.encode() + b'"\n' in raw.replace(b"\r\n", b"\n")
            and b'    d3_successor_sha256 = "' + expected.encode() + b'"\n' in portable.replace(b"\r\n", b"\n")
            and digest(canonical_bytes(PORTABLE, portable)) == POST.get(PORTABLE))
    except (OSError, ValueError):
        return False


@lru_cache(maxsize=64)
def baseline_bytes(path: str) -> bytes:
    assert path in PRE
    repository = Path(__file__).resolve().parents[2]
    raw = subprocess.run(["git", "show", f"{BASELINE}:{path}"], cwd=repository,
                         check=True, capture_output=True).stdout
    assert digest(raw) == PRE[path], path
    return raw


@lru_cache(maxsize=256)
def outside_scope(raw: bytes, path: str) -> str:
    if path == "frontend/app.js":
        text = raw.decode("utf-8").replace("\r\n", "\n")
        start = text.index("async function r3Command(operation) {")
        end = text.index('\nfor (const [name, operation]', start)
        return text[:start] + "R3_COMMAND_BODY" + text[end:]
    tree = ast.parse(raw)
    allowed = SYMBOLS[path]
    guards = path.startswith("tests/support/")
    def strip(nodes: list[ast.stmt], prefix: str = "") -> list[ast.stmt]:
        kept: list[ast.stmt] = []
        for node in nodes:
            name = prefix + getattr(node, "name", "")
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and name in allowed:
                if guards or path.startswith("tests/"):
                    node.body = [ast.Pass()]
                else:
                    continue
            elif isinstance(node, ast.ClassDef):
                node.body = strip(node.body, name + ".")
            elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                if node.targets[0].id in allowed:
                    node.value = ast.Constant(None)
            kept.append(node)
        return kept
    tree.body = strip(tree.body)
    return ast.dump(tree)


def _exact(root: Path, path: str) -> bool:
    try:
        if path == SELF:
            return authenticated(root)
        raw = source_bytes(root, path)
        if digest(canonical_bytes(path, raw)) != POST.get(path):
            return False
        return path not in PRE or outside_scope(raw, path) == outside_scope(baseline_bytes(path), path)
    except (OSError, ValueError, SyntaxError, AssertionError):
        return False


def source_matches(root: Path, path: str, historical: str) -> bool:
    return path in PRE and historical == PRE[path] and authenticated(root) and _exact(root, path)


def baseline_view(root: Path, path: str) -> bytes:
    return baseline_bytes(path) if path in PRE and source_matches(root, path, PRE[path]) else source_bytes(root, path)


def index_matches(root: Path, path: str, raw: bytes) -> bool:
    if path not in PATHS or not authenticated(root) or not _exact(root, path):
        return False
    return digest(raw) == digest(source_bytes(root, path)) or (path in PRE and digest(raw) == PRE[path])


def violations(root: Path, *, changed: set[str] | None = None) -> list[str]:
    errors = []
    if set(POST) != set(PATHS) - {SELF} or len(PATHS) != 46 or not authenticated(root):
        errors.append("D3_ORACLE_IDENTITY")
    for path in PATHS:
        if not _exact(root, path):
            errors.append("D3_IDENTITY:" + path)
    if changed is not None:
        errors += ["D3_MISSING:" + path for path in sorted(set(PATHS) - changed)]
        errors += ["D3_UNAPPROVED:" + path for path in sorted(changed - set(PATHS))]
    return errors


def assert_scope(root: Path) -> None:
    assert violations(root) == []


def assert_git_state(root: Path) -> None:
    from tests.support.r3_guard_oracle import PREPARATION
    from tests.support.r3_portable_clone_guard import private_preparations
    assert_scope(root)
    assert not private_preparations(root).errors
    observed: set[str] = set()
    for args in (["diff", "--name-only", BASELINE, "--"],
                 ["diff", "--cached", "--name-only", BASELINE, "--"],
                 ["ls-files", "--others", "--exclude-standard"]):
        result = subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)
        observed.update(result.stdout.splitlines())
    assert violations(root, changed=observed - set(PREPARATION)) == []
    for path in PATHS:
        staged = subprocess.run(["git", "show", ":" + path], cwd=root, capture_output=True)
        if staged.returncode:
            assert path in CREATES, path
        else:
            assert index_matches(root, path, staged.stdout), path
