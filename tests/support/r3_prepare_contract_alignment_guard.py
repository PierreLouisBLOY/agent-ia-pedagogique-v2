"""Separately approved twelve-file successor; historical identity tables stay immutable."""
from __future__ import annotations

import ast
import hashlib
import subprocess
from pathlib import Path

BASELINE = "81592e82aece8e41eb446e5701de3e83e86978c4"
PREINVENTORY_SHA256 = "9e80e8adcbf280ae5db4a6928458700f1ac4ef4e2086da227e3137b9a4406aeb"
SELF = "tests/support/r3_prepare_contract_alignment_guard.py"
PRE = {
    "backend/adapters/outbound/generation/openai/mapping.py": "ace7fe0d46f38dd03270160259e2858e86d9bfe98ba57c8492213c29f7f855b7",
    "backend/adapters/outbound/generation/openai/adapter.py": "d87da841360fe51fc23d1da32aa365bb10fdebeaf7bf0eb1dd4fce923776561e",
    "tests/integration/test_r3_parse_observability.py": "7f6528c7925c6f087a13c6a3b214a88f7c5026a712eceb3c7278a5aa85506be6",
    "tests/support/r3_parse_observability_guard.py": "124bfdcd22317193dcdbfa5b81e6c5786baea6f4cd34cd08fbe58177a869f424",
    "tests/support/r3_guard_oracle.py": "2183a65d907ed4f81d9f2a69c6d100633835dcfab93925d46b690e0e32d74c52",
    "tests/architecture/test_r3_product_boundary.py": "608841354864e3ce0285222167b06b9b68e57af302a1032d5f2584fba5eff341",
    "tests/unit/test_r3_parse_observability.py": "ef58b9a445b106c7ae89a72bc220538ab51bafd9c9e3b1a2bdeeb6d41350370f"
}
SYMBOLS = {
    "backend/adapters/outbound/generation/openai/mapping.py": [
        "build_openai_request"
    ],
    "backend/adapters/outbound/generation/openai/adapter.py": [
        "_map_response_body"
    ],
    "tests/integration/test_r3_parse_observability.py": [
        "SyntheticResponsePort.generate"
    ],
    "tests/support/r3_parse_observability_guard.py": [
        "active_source_matches",
        "assert_guard_extension",
        "patch_violations",
        "assert_patch_git_state"
    ],
    "tests/support/r3_guard_oracle.py": [
        "active_inventory"
    ],
    "tests/architecture/test_r3_product_boundary.py": [
        "test_exact_closed_inventory_owners_and_protected_identities"
    ],
    "tests/unit/test_r3_parse_observability.py": [
        "test_every_patch_source_mutation_is_rejected"
    ]
}
CREATES = [
    "backend/adapters/outbound/generation/openai/prepare_contract.py",
    "tests/unit/test_r3_prepare_contract_alignment.py",
    "tests/integration/test_r3_prepare_contract_alignment.py",
    "tests/support/r3_prepare_contract_alignment_guard.py",
    "architecture/adr/ADR-r3-prepare-contract-alignment.md"
]
PATHS = tuple(PRE) + tuple(CREATES)
PRODUCERS = (
    "backend/adapters/outbound/generation/openai/mapping.py",
    "backend/adapters/outbound/generation/openai/adapter.py",
)
POST = {
    "backend/adapters/outbound/generation/openai/mapping.py": "719627c198db268c2f503e9a8084c13b4992cd4957fb040858dc678b6c9f5e2a",
    "backend/adapters/outbound/generation/openai/adapter.py": "33be83bbbe85b79f3d6a2ef127a5ab467b8e80d33f49ded2cce3ad2d6b8862ea",
    "tests/integration/test_r3_parse_observability.py": "bede7031c1145ec7af44eba1f933faefbdd8c011c70d50de1fdabd2ed0c3a931",
    "tests/support/r3_parse_observability_guard.py": "f1b9a3fa39acb533fe0160ccc949d212f0e5d05aa2f5ba2f8645abe16ee597ab",
    "tests/support/r3_guard_oracle.py": "1f4523176b644aecd8c97c97b1a0270ad7e2fe1264de0c0a6bfd3dcfe19c414c",
    "tests/architecture/test_r3_product_boundary.py": "0bf3875818cb830d1333ae05f335ae265a943b4644fd8915c4f9e168eaa307cd",
    "tests/unit/test_r3_parse_observability.py": "0428a7a34364048c402f8ce2e37eded48fd448380d53294ff648cf647a236431",
    "backend/adapters/outbound/generation/openai/prepare_contract.py": "f8b5ac687f4655690986f37685d5b0039e6def4b2ada08e2e18309a88c76d0b2",
    "tests/unit/test_r3_prepare_contract_alignment.py": "923976d783a874c007a9cfed03aee87fd1fcbcbdefaa7b34c2d7e3069d2e862c",
    "tests/integration/test_r3_prepare_contract_alignment.py": "969d162cc397efb0aba7a1da92629cac9dc758cccdbab63039971246ef986de3",
    "architecture/adr/ADR-r3-prepare-contract-alignment.md": "7da2c2115812d0ff9f8c7edebea48a6c27508ece2110d80b134850ef4bbfbec5"
}
ORACLE_AST_SHA256 = "5acaa5c25c7284149e565df93f24003704e9da4ee604bae1c0a32b7b4f923083"


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def oracle_digest(raw: bytes) -> str:
    tree = ast.parse(raw)
    tree.body = [n for n in tree.body if not (isinstance(n, ast.Assign)
        and isinstance(n.targets[0], ast.Name) and n.targets[0].id == "ORACLE_AST_SHA256")]
    return hashlib.sha256(ast.dump(tree).encode()).hexdigest()


def successor_violations(root: Path, *, changed: set[str] | None = None) -> list[str]:
    from tests.support.r3_cap_a01_guard import source_matches as cap_source_matches
    from tests.support.r3_locator_materialization_guard import source_matches as locator_matches
    from tests.support.r3_serializer_8192_guard import PRE as SERIALIZER_PRE
    from tests.support.r3_serializer_8192_guard import source_matches as serializer_source_matches

    assert len(PATHS) == len(set(PATHS)) == 12
    assert set(POST) == set(PATHS) - {SELF}
    errors = []
    for path, expected in POST.items():
        file = root / path
        if (not file.is_file() or digest(file.read_bytes()) != expected) and not locator_matches(root, path, expected) and not cap_source_matches(root, path, expected) and not (
                path in SERIALIZER_PRE and expected == SERIALIZER_PRE[path]
                and serializer_source_matches(root, path, expected)):
            errors.append("PREPARE_SUCCESSOR_IDENTITY:" + path)
    oracle = root / SELF
    try:
        if (oracle_digest(oracle.read_bytes()) != ORACLE_AST_SHA256
                and not serializer_source_matches(root, SELF, SERIALIZER_PRE[SELF])):
            errors.append("PREPARE_SUCCESSOR_ORACLE_IDENTITY")
    except (OSError, SyntaxError, ValueError):
        errors.append("PREPARE_SUCCESSOR_ORACLE_UNREADABLE")
    if changed is not None:
        errors += ["PREPARE_SUCCESSOR_MISSING:" + p for p in sorted(set(PATHS) - changed)]
        errors += ["PREPARE_SUCCESSOR_UNAPPROVED:" + p for p in sorted(changed - set(PATHS))]
    return errors


def source_matches(root: Path, path: str, historical: str) -> bool:
    from tests.support.r3_locator_materialization_guard import source_matches as locator_matches

    # This exception is only for the two explicitly authorized producer successors.
    from tests.support.r3_parse_observability_guard import ADAPTER
    from tests.support.r3_parse_observability_guard import PRE as OLD_PRE
    from tests.support.r3_serializer_8192_guard import PRE as SERIALIZER_PRE
    from tests.support.r3_serializer_8192_guard import source_matches as serializer_source_matches

    identities = {PRODUCERS[0]: PRE[PRODUCERS[0]], ADAPTER: OLD_PRE[ADAPTER]}
    file = root / path
    # This is a per-source predicate, also used by isolated historical mutant fixtures.
    # Authenticate the expected table itself; complete inventories are separately checked
    # by successor_violations/assert_successor_git_state, never inferred from this helper.
    return (path in identities and historical == identities[path]
            and (oracle_digest(Path(__file__).read_bytes()) == ORACLE_AST_SHA256
                 or serializer_source_matches(Path(__file__).resolve().parents[2], SELF,
                                              SERIALIZER_PRE[SELF]))
            and file.is_file() and (digest(file.read_bytes()) == POST[path]
                                    or locator_matches(root, path, POST[path])))


def outside_symbols(raw: bytes, symbols: list[str]) -> str:
    tree = ast.parse(raw)
    def strip(nodes, prefix=""):
        for node in nodes:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if prefix + node.name in symbols:
                    node.body = [ast.Pass()]
            elif isinstance(node, ast.ClassDef):
                strip(node.body, prefix + node.name + ".")
    strip(tree.body)
    return ast.dump(tree)


def assert_successor_scope(root: Path, *, repository: Path | None = None) -> None:
    from tests.support.r3_locator_materialization_guard import prior_scope_bytes
    repository = repository or Path(__file__).resolve().parents[2]
    assert successor_violations(root) == []
    for path, expected in PRE.items():
        before = subprocess.run(["git", "show", f"{BASELINE}:{path}"], cwd=repository,
                                capture_output=True, check=True).stdout
        assert digest(before) == expected, path
        assert outside_symbols(before, SYMBOLS[path]) == outside_symbols(
            prior_scope_bytes(root, path), SYMBOLS[path]), path


def assert_successor_git_state(root: Path) -> None:
    from tests.support.r3_cap_a01_guard import PATHS as CAP_PATHS
    from tests.support.r3_cap_a01_guard import PRE as CAP_PRE
    from tests.support.r3_cap_a01_guard import source_matches as cap_source_matches
    from tests.support.r3_editorial_correction_guard import PATHS as EDITORIAL_PATHS
    from tests.support.r3_editorial_correction_guard import index_matches
    from tests.support.r3_guard_oracle import PREPARATION
    from tests.support.r3_locator_materialization_guard import PATHS as LOCATOR_PATHS
    from tests.support.r3_locator_materialization_guard import PRE as LOCATOR_PRE
    from tests.support.r3_locator_materialization_guard import source_matches as locator_matches
    from tests.support.r3_portable_clone_guard import PATHS as PORTABLE_PATHS
    from tests.support.r3_serializer_8192_guard import PATHS as SERIALIZER_PATHS
    from tests.support.r3_serializer_8192_guard import PRE as SERIALIZER_PRE
    from tests.support.r3_serializer_8192_guard import (
        assert_git_state as assert_serializer_git_state,
    )
    from tests.support.r3_serializer_8192_guard import source_matches as serializer_source_matches

    assert_serializer_git_state(root)
    observed = set()
    for args in (["diff", "--name-only", BASELINE, "--"],
                 ["diff", "--cached", "--name-only", BASELINE, "--"],
                 ["ls-files", "--others", "--exclude-standard"]):
        result = subprocess.run(["git", *args], cwd=root, capture_output=True, check=True, text=True)
        paths = set(result.stdout.splitlines())
        if "--cached" in args:
            assert not paths & set(PREPARATION)
        observed.update(paths)
    assert successor_violations(root, changed=(observed - set(PREPARATION))
                               - (set(SERIALIZER_PATHS) - set(PATHS))
                               - (set(CAP_PATHS) - set(PATHS))
                               - (set(LOCATOR_PATHS) - set(PATHS))
                      - (set(EDITORIAL_PATHS) - set(PATHS)) - (set(PORTABLE_PATHS) - set(PATHS))) == []
    assert_successor_scope(root)
    for path in PATHS:
        staged = subprocess.run(["git", "show", ":" + path], cwd=root, capture_output=True)
        if staged.returncode:
            assert path in CREATES, path
        elif path in PRE and digest(staged.stdout) == PRE[path]:
            continue  # Exact approved baseline bytes before staging, never arbitrary bytes.
        elif path in CAP_PRE and digest(staged.stdout) == CAP_PRE[path]:
            continue  # Exact preinventoried current baseline, independently checked above.
        elif path in LOCATOR_PRE and digest(staged.stdout) == LOCATOR_PRE[path]:
            continue
        elif index_matches(root, path, staged.stdout):
            continue
        elif path == SELF:
            assert (oracle_digest(staged.stdout) == ORACLE_AST_SHA256
                    or (serializer_source_matches(root, path, SERIALIZER_PRE[path])
                        and digest(staged.stdout) == digest((root / path).read_bytes()))), path
        else:
            assert (digest(staged.stdout) == POST[path]
                    or (locator_matches(root, path, POST[path])
                        and digest(staged.stdout) == digest((root / path).read_bytes()))
                    or (cap_source_matches(root, path, POST[path])
                        and digest(staged.stdout) == digest((root / path).read_bytes()))
                    or (path in SERIALIZER_PRE and POST[path] == SERIALIZER_PRE[path]
                        and serializer_source_matches(root, path, POST[path])
                        and digest(staged.stdout) == digest((root / path).read_bytes()))), path
