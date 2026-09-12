"""Exact contextual serializer successor; historical tables are never replaced."""
from __future__ import annotations

import ast
import hashlib
import subprocess
from pathlib import Path

BASELINE = "815274f85fcba7db96529fde57420a811042290a"
SELF = "tests/support/r3_serializer_8192_guard.py"
PRE = {
    "tests/support/r3_guard_oracle.py": "1f4523176b644aecd8c97c97b1a0270ad7e2fe1264de0c0a6bfd3dcfe19c414c",
    "tests/support/r3_prepare_contract_alignment_guard.py": "bad35e1e4135ac9b10abfeeff8a1717066c79d835b893af954053daf2f44ee84",
    "tests/support/r3_parse_observability_guard.py": "f1b9a3fa39acb533fe0160ccc949d212f0e5d05aa2f5ba2f8645abe16ee597ab"
}
SYMBOLS = {
    "tests/support/r3_guard_oracle.py": [
        "active_inventory"
    ],
    "tests/support/r3_prepare_contract_alignment_guard.py": [
        "successor_violations",
        "source_matches",
        "assert_successor_git_state"
    ],
    "tests/support/r3_parse_observability_guard.py": [
        "patch_violations"
    ]
}
CREATES = [
    "backend/infrastructure/composition/factories/r3_prepare_serialization.py",
    "tests/unit/test_r3_prepare_serialization.py",
    "tests/support/r3_serializer_8192_guard.py"
]
PATHS = tuple(PRE) + tuple(CREATES)
POST = {
    "tests/support/r3_guard_oracle.py": "8f2ad26eac2193746dbfb1c8eb80a1b58746bcd39d5e9132d651c4d2026a29d9",
    "tests/support/r3_prepare_contract_alignment_guard.py": "e5e1fe1c0619261c9c93c9752265953ba6cd2faefef129decba95222c1aceca5",
    "tests/support/r3_parse_observability_guard.py": "9e9596ace319b0d18b9c20fad5a59dca52dd4c7a0fc499b4d6a9e8bf39c2483a",
    "backend/infrastructure/composition/factories/r3_prepare_serialization.py": "df8452be7091017d19ac5a4e1abdadd1711f4300542e7c556a52325873660190",
    "tests/unit/test_r3_prepare_serialization.py": "3e218115a8202298cc14470dd71ae284fe073a423a075b9dddfeceb80f03f87a"
}
ORACLE_AST_SHA256 = "837dc202acde4fa9e7c9a05989d5396010f2011790f46bcea9ed4c6d89797ae2"
R2_SOURCE = "backend/infrastructure/composition/factories/conversation.py"
R2_SOURCE_SHA256 = "d3817b7f4186ea2eecbc01732c903471869e1f9710e11c2dc6a4c0ad8b5ed97e"


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def oracle_digest(raw: bytes) -> str:
    tree = ast.parse(raw)
    tree.body = [n for n in tree.body if not (isinstance(n, ast.Assign)
        and isinstance(n.targets[0], ast.Name) and n.targets[0].id == "ORACLE_AST_SHA256")]
    return hashlib.sha256(ast.dump(tree).encode()).hexdigest()


def source_matches(root: Path, path: str, historical: str) -> bool:
    """Authenticate one declared successor only; not a complete-inventory exemption."""
    from tests.support.r3_cap_a01_guard import PRE as CAP_PRE
    from tests.support.r3_cap_a01_guard import source_matches as cap_source_matches

    file = root / path
    return (path in PRE and historical == PRE[path]
            and (oracle_digest(Path(__file__).read_bytes()) == ORACLE_AST_SHA256
                 or cap_source_matches(Path(__file__).resolve().parents[2], SELF, CAP_PRE[SELF]))
            and file.is_file() and (digest(file.read_bytes()) == POST[path]
                 or cap_source_matches(root, path, POST[path])))


def violations(root: Path, *, changed: set[str] | None = None) -> list[str]:
    from tests.support.r3_cap_a01_guard import PRE as CAP_PRE
    from tests.support.r3_cap_a01_guard import source_matches as cap_source_matches

    assert len(PATHS) == len(set(PATHS)) == 6
    assert set(POST) == set(PATHS) - {SELF}
    errors = []
    for path, expected in POST.items():
        file = root / path
        if (not file.is_file() or digest(file.read_bytes()) != expected) and not cap_source_matches(root, path, expected):
            errors.append("SERIALIZER_IDENTITY:" + path)
    try:
        if (oracle_digest((root / SELF).read_bytes()) != ORACLE_AST_SHA256
                and not cap_source_matches(root, SELF, CAP_PRE[SELF])):
            errors.append("SERIALIZER_ORACLE_IDENTITY")
    except (OSError, SyntaxError, ValueError):
        errors.append("SERIALIZER_ORACLE_UNREADABLE")
    if changed is not None:
        errors += ["SERIALIZER_MISSING:" + p for p in sorted(set(PATHS) - changed)]
        errors += ["SERIALIZER_UNAPPROVED:" + p for p in sorted(changed - set(PATHS))]
    return errors


def assert_scope(root: Path, *, repository: Path | None = None) -> None:
    from tests.support.r3_locator_materialization_guard import prior_scope_bytes
    from tests.support.r3_prepare_contract_alignment_guard import outside_symbols

    repository = repository or Path(__file__).resolve().parents[2]
    assert violations(root) == []
    for path, expected in PRE.items():
        raw = subprocess.run(["git", "show", f"{BASELINE}:{path}"], cwd=repository,
                             check=True, capture_output=True).stdout
        assert digest(raw) == expected, path
        assert outside_symbols(raw, SYMBOLS[path]) == outside_symbols(
            prior_scope_bytes(root, path), SYMBOLS[path]), path
    assert hashlib.sha256((repository / R2_SOURCE).read_bytes()).hexdigest() == R2_SOURCE_SHA256


def assert_git_state(root: Path) -> None:
    from tests.support.r3_cap_a01_guard import PATHS as CAP_PATHS
    from tests.support.r3_cap_a01_guard import PRE as CAP_PRE
    from tests.support.r3_cap_a01_guard import assert_git_state as assert_cap_git_state
    from tests.support.r3_cap_a01_guard import source_matches as cap_source_matches
    from tests.support.r3_editorial_correction_guard import PATHS as EDITORIAL_PATHS
    from tests.support.r3_editorial_correction_guard import index_matches
    from tests.support.r3_guard_oracle import PREPARATION
    from tests.support.r3_locator_materialization_guard import PATHS as LOCATOR_PATHS
    from tests.support.r3_locator_materialization_guard import PRE as LOCATOR_PRE

    assert_cap_git_state(root)
    observed = set()
    for args in (["diff", "--name-only", BASELINE, "--"],
                 ["diff", "--cached", "--name-only", BASELINE, "--"],
                 ["ls-files", "--others", "--exclude-standard"]):
        result = subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)
        paths = set(result.stdout.splitlines())
        if "--cached" in args:
            assert not paths & set(PREPARATION)
        observed.update(paths)
    assert violations(root, changed=observed - set(PREPARATION) - (set(CAP_PATHS) - set(PATHS))
                      - (set(LOCATOR_PATHS) - set(PATHS))
                      - (set(EDITORIAL_PATHS) - set(PATHS))) == []
    assert_scope(root)
    for path in PATHS:
        staged = subprocess.run(["git", "show", ":" + path], cwd=root, capture_output=True)
        if staged.returncode:
            assert path in CREATES, path
        elif path in PRE and digest(staged.stdout) == PRE[path]:
            continue  # Only exact original index bytes before staging.
        elif path in LOCATOR_PRE and digest(staged.stdout) == LOCATOR_PRE[path]:
            continue
        elif index_matches(root, path, staged.stdout):
            continue
        elif path == SELF:
            assert (oracle_digest(staged.stdout) == ORACLE_AST_SHA256
                    or (cap_source_matches(root, path, CAP_PRE[path])
                        and digest(staged.stdout) == digest((root / path).read_bytes())))
        else:
            assert (digest(staged.stdout) == POST[path]
                    or (cap_source_matches(root, path, POST[path])
                        and digest(staged.stdout) == digest((root / path).read_bytes()))), path
