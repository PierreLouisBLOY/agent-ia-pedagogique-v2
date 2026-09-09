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
    assert len(PATHS) == len(set(PATHS)) == 12
    assert set(POST) == set(PATHS) - {SELF}
    errors = []
    for path, expected in POST.items():
        file = root / path
        if not file.is_file() or digest(file.read_bytes()) != expected:
            errors.append("PREPARE_SUCCESSOR_IDENTITY:" + path)
    oracle = root / SELF
    try:
        if oracle_digest(oracle.read_bytes()) != ORACLE_AST_SHA256:
            errors.append("PREPARE_SUCCESSOR_ORACLE_IDENTITY")
    except (OSError, SyntaxError, ValueError):
        errors.append("PREPARE_SUCCESSOR_ORACLE_UNREADABLE")
    if changed is not None:
        errors += ["PREPARE_SUCCESSOR_MISSING:" + p for p in sorted(set(PATHS) - changed)]
        errors += ["PREPARE_SUCCESSOR_UNAPPROVED:" + p for p in sorted(changed - set(PATHS))]
    return errors


def source_matches(root: Path, path: str, historical: str) -> bool:
    # This exception is only for the two explicitly authorized producer successors.
    from tests.support.r3_parse_observability_guard import ADAPTER
    from tests.support.r3_parse_observability_guard import PRE as OLD_PRE

    identities = {PRODUCERS[0]: PRE[PRODUCERS[0]], ADAPTER: OLD_PRE[ADAPTER]}
    file = root / path
    # This is a per-source predicate, also used by isolated historical mutant fixtures.
    # Authenticate the expected table itself; complete inventories are separately checked
    # by successor_violations/assert_successor_git_state, never inferred from this helper.
    return (path in identities and historical == identities[path]
            and oracle_digest(Path(__file__).read_bytes()) == ORACLE_AST_SHA256
            and file.is_file() and digest(file.read_bytes()) == POST[path])


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
    repository = repository or Path(__file__).resolve().parents[2]
    assert successor_violations(root) == []
    for path, expected in PRE.items():
        before = subprocess.run(["git", "show", f"{BASELINE}:{path}"], cwd=repository,
                                capture_output=True, check=True).stdout
        assert digest(before) == expected, path
        assert outside_symbols(before, SYMBOLS[path]) == outside_symbols(
            (root / path).read_bytes(), SYMBOLS[path]), path


def assert_successor_git_state(root: Path) -> None:
    from tests.support.r3_guard_oracle import PREPARATION

    observed = set()
    for args in (["diff", "--name-only", BASELINE, "--"],
                 ["diff", "--cached", "--name-only", BASELINE, "--"],
                 ["ls-files", "--others", "--exclude-standard"]):
        result = subprocess.run(["git", *args], cwd=root, capture_output=True, check=True, text=True)
        paths = set(result.stdout.splitlines())
        if "--cached" in args:
            assert not paths & set(PREPARATION)
        observed.update(paths)
    assert successor_violations(root, changed=observed - set(PREPARATION)) == []
    assert_successor_scope(root)
    for path in PATHS:
        staged = subprocess.run(["git", "show", ":" + path], cwd=root, capture_output=True)
        if staged.returncode:
            assert path in CREATES, path
        elif path in PRE and digest(staged.stdout) == PRE[path]:
            continue  # Exact approved baseline bytes before staging, never arbitrary bytes.
        elif path == SELF:
            assert oracle_digest(staged.stdout) == ORACLE_AST_SHA256, path
        else:
            assert digest(staged.stdout) == POST[path], path
