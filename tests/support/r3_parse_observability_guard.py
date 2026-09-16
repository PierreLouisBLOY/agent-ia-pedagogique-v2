"""Versioned successor oracle, independent of immutable R2/R3 manifests."""
from __future__ import annotations

import ast
import hashlib
import subprocess
from pathlib import Path

BASELINE = "7e851503a78962cb04f0089bd0a01fdbafb29b70"
ADAPTER = "backend/adapters/outbound/generation/openai/adapter.py"
SELF = "tests/support/r3_parse_observability_guard.py"
PRE = {
    ADAPTER: "8854f9b5dea7d9ddb713d27211a77fe36dff4577ee080f63f5f71925fccc3088",
    "backend/adapters/outbound/generation/assessment_revision.py": "c9f4c65c6bdf2f033f24f379a9be5b9167894323ddb66a5242f9815f083a8ef3",
    "tests/support/r3_guard_oracle.py": "850328b50b8380264b60af0c3efc921e322f035aa18dd67e8bfa2f7b44a309de",
    "tests/architecture/test_conversation_product_boundary.py": "6476eb9684c235ffdd3b4931f8e40255882e0da3b7c4ff582e557b06896bdb1e",
    "tests/architecture/test_r3_product_boundary.py": "5c00d51cb4c6a0b78217b094fb8f1b7db52a471d0a0cd560f62fbc66f3b96838",
}
CREATES = (
    "backend/adapters/outbound/generation/parse_diagnostic.py",
    "tests/unit/test_r3_parse_observability.py",
    "tests/integration/test_r3_parse_observability.py",
    SELF,
    "architecture/adr/ADR-r3-parse-observability.md",
)
PATCH_PATHS = tuple(PRE) + CREATES
GUARD_SYMBOLS = {
    "tests/support/r3_guard_oracle.py": {"active_inventory", "assert_guard_scope"},
    "tests/architecture/test_conversation_product_boundary.py": {"assert_r2_generation_source_lineage"},
    "tests/architecture/test_r3_product_boundary.py": {
        "test_exact_closed_inventory_owners_and_protected_identities"},
}
# Frozen only after implementation and synthetic verification; historical PRE remains intact.
POST = {
    "backend/adapters/outbound/generation/openai/adapter.py": "d87da841360fe51fc23d1da32aa365bb10fdebeaf7bf0eb1dd4fce923776561e",
    "backend/adapters/outbound/generation/assessment_revision.py": "9d88137443e6e3235e04b50008e7e080d23657573ef19aa1b63f3b6856aeab6b",
    "tests/support/r3_guard_oracle.py": "2183a65d907ed4f81d9f2a69c6d100633835dcfab93925d46b690e0e32d74c52",
    "tests/architecture/test_conversation_product_boundary.py": "5f3432c9ebf52d948a49d996ee538796ca19e925c79b5a3028cd2863f0f9839b",
    "tests/architecture/test_r3_product_boundary.py": "608841354864e3ce0285222167b06b9b68e57af302a1032d5f2584fba5eff341",
    "backend/adapters/outbound/generation/parse_diagnostic.py": "89663dc7e83907463197ad319d23ca2dca7206912017e5bbd8810cd3eaa6771b",
    "tests/unit/test_r3_parse_observability.py": "ef58b9a445b106c7ae89a72bc220538ab51bafd9c9e3b1a2bdeeb6d41350370f",
    "tests/integration/test_r3_parse_observability.py": "7f6528c7925c6f087a13c6a3b214a88f7c5026a712eceb3c7278a5aa85506be6",
    "architecture/adr/ADR-r3-parse-observability.md": "5b8c063110320d4219d472bacbbe47d8d1700124433de62450a7fd3b7ab0f319",
}
ORACLE_AST_SHA256 = "ec9becd91a0227c449e9639a348514b0520a6a8a02a1138322601364e0defa1c"


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def oracle_digest(raw: bytes) -> str:
    tree = ast.parse(raw)
    tree.body = [n for n in tree.body if not (isinstance(n, ast.Assign)
        and isinstance(n.targets[0], ast.Name)
        and n.targets[0].id == "ORACLE_AST_SHA256")]
    return hashlib.sha256(ast.dump(tree).encode()).hexdigest()


def active_source_matches(root: Path, path: str, historical: str) -> bool:
    from tests.support.r3_prepare_contract_alignment_guard import PRODUCERS, source_matches

    if path in PRODUCERS:
        return source_matches(root, path, historical)
    file = root / path
    if not file.is_file():
        return False
    if path == ADAPTER:
        assert historical == PRE[ADAPTER]
        return digest(file.read_bytes()) == POST[ADAPTER]
    return hashlib.sha256(file.read_bytes()).hexdigest() == historical


def assert_guard_extension(root: Path, path: str, *, repository: Path | None = None) -> None:
    repository = repository or Path(__file__).resolve().parents[2]
    raw = subprocess.run(["git", "show", f"{BASELINE}:{path}"],
                         cwd=repository, capture_output=True, check=True).stdout
    assert PRE[path] in {hashlib.sha256(raw).hexdigest(),
        hashlib.sha256(raw.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")).hexdigest()}
    from tests.support.r4_scope_guard import baseline_view as r4_view
    current = r4_view(root, path)
    from tests.support.r3_prepare_contract_alignment_guard import (
        PRE as SUCCESSOR_PRE,
    )
    from tests.support.r3_prepare_contract_alignment_guard import assert_successor_scope

    if path in SUCCESSOR_PRE:
        assert_successor_scope(root, repository=repository)
        assert SUCCESSOR_PRE[path] == POST[path]
    else:
        assert digest(current) == POST[path], path
    def unchanged(source: bytes) -> list[str]:
        return [ast.dump(n) for n in ast.parse(source).body
                if not (isinstance(n, ast.FunctionDef) and n.name in GUARD_SYMBOLS[path])]
    assert unchanged(raw) == unchanged(current), path


def patch_violations(root: Path, *, changed: set[str] | None = None) -> list[str]:
    from tests.support.r3_cap_a01_guard import PATHS as CAP_PATHS
    from tests.support.r3_d3_scope_guard import PATHS as D3_PATHS
    from tests.support.r3_d3_scope_guard import violations as d3_violations
    from tests.support.r3_editorial_correction_guard import PATHS as EDITORIAL_PATHS
    from tests.support.r3_editorial_correction_guard import violations as editorial_violations
    from tests.support.r3_locator_materialization_guard import PATHS as LOCATOR_PATHS
    from tests.support.r3_locator_materialization_guard import source_matches as locator_matches
    from tests.support.r3_portable_clone_guard import PATHS as PORTABLE_PATHS
    from tests.support.r3_prepare_contract_alignment_guard import PATHS, successor_violations
    from tests.support.r3_serializer_8192_guard import PATHS as SERIALIZER_PATHS
    from tests.support.r3_serializer_8192_guard import source_matches as serializer_source_matches
    from tests.support.r4_scope_guard import PATHS as R4_PATHS
    from tests.support.r4_scope_guard import baseline_view as r4_view

    assert set(POST) == set(PATCH_PATHS) - {SELF}
    errors = d3_violations(root) + successor_violations(root) + editorial_violations(root)
    for path, expected in POST.items():
        if path in PATHS:
            continue  # The independent exact successor oracle checked these bytes above.
        file = root / path
        if (not file.is_file() or digest(r4_view(root, path)) != expected) and not locator_matches(root, path, expected):
            errors.append("PARSE_PATCH_IDENTITY:" + path)
    oracle = root / SELF
    from tests.support.r3_prepare_contract_alignment_guard import POST as SUCCESSOR_POST
    if (not oracle.is_file() or digest(oracle.read_bytes()) != SUCCESSOR_POST[SELF]) and not (
            serializer_source_matches(root, SELF, SUCCESSOR_POST[SELF])):
        errors.append("PARSE_PATCH_ORACLE_IDENTITY")
    if changed is not None:
        # Complete new successor working/index identities are checked by assert_patch_git_state.
        allowed = set(PATCH_PATHS) | set(PATHS) | (set(SERIALIZER_PATHS) & changed) | (set(CAP_PATHS) & changed) | (set(LOCATOR_PATHS) & changed) | (set(EDITORIAL_PATHS) & changed) | (set(PORTABLE_PATHS) & changed) | (set(D3_PATHS) & changed)
        errors += ["PARSE_PATCH_MISSING:" + p for p in sorted(allowed - changed)]
        errors += ["PARSE_PATCH_UNAPPROVED:" + p for p in sorted(changed - allowed - set(R4_PATHS))]
    return errors


def assert_patch_git_state(root: Path) -> None:
    """Authenticate working AND staged bytes; also valid after the bounded commit."""
    from tests.support.r3_editorial_correction_guard import index_matches
    from tests.support.r3_locator_materialization_guard import source_matches as locator_matches
    from tests.support.r3_prepare_contract_alignment_guard import PATHS, assert_successor_git_state

    assert_successor_git_state(root)
    observed = set()
    for args in (["diff", "--name-only", BASELINE, "--"],
                 ["diff", "--cached", "--name-only", BASELINE, "--"],
                 ["ls-files", "--others", "--exclude-standard"]):
        result = subprocess.run(["git", *args], cwd=root, capture_output=True, check=True, text=True)
        observed.update(result.stdout.splitlines())
    from tests.support.r3_guard_oracle import PREPARATION
    assert patch_violations(root, changed=observed - set(PREPARATION)) == []
    for path in PATCH_PATHS:
        if path in PATHS:
            continue  # Working and staged successor bytes were both authenticated above.
        staged = subprocess.run(["git", "show", ":" + path], cwd=root, capture_output=True)
        if staged.returncode:
            assert path in CREATES
        elif path in PRE and digest(staged.stdout) == digest(subprocess.run(
                ["git", "show", f"{BASELINE}:{path}"], cwd=root, capture_output=True,
                check=True).stdout):
            continue  # Not staged yet: the immutable PRE bytes are legitimate.
        elif index_matches(root, path, staged.stdout):
            continue
        elif path == SELF:
            assert oracle_digest(staged.stdout) == ORACLE_AST_SHA256
        else:
            assert (digest(staged.stdout) == POST[path]
                    or (locator_matches(root, path, POST[path])
                        and digest(staged.stdout) == digest((root / path).read_bytes()))), path
