"""Versioned portable source guard; private attestation is a separate operation."""
from __future__ import annotations

import ast
import hashlib
import re
import stat
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

BASELINE = "9474f8dbdf493d1bf56fee4ce8743deb424a47c6"
SELF = "tests/support/r3_portable_clone_guard.py"
EDITORIAL = "tests/support/r3_editorial_correction_guard.py"
PRE = {
    "tests/support/r3_guard_oracle.py": "5334562b585d6f3dc15de846a5df55e987052b62f9bd16b401cd583db83947fb",
    "tests/support/r3_editorial_correction_guard.py": "8bd8dfe911ad26da99371e47dbdbbb2966c593af0a65e59d57631ad5dce54229",
    "tests/support/r3_parse_observability_guard.py": "69c182f5b883b795c4dccda58db2d7dd9fd96e447e8612c39324e1984e622287",
    "tests/support/r3_prepare_contract_alignment_guard.py": "59db841b1ef88f1594e1404ee906ff66ba4ff979901b477e0d1c814120d5f5ad",
    "tests/support/r3_serializer_8192_guard.py": "0f9419e77c6d771d5e0b6463c90874a32ca61fb3fca1a1e0bdd93f8c24309a34",
    "tests/support/r3_cap_a01_guard.py": "f79025454ea7903043d6f249fc7c884911ca040a412c831f6406e34846ca2ddc",
    "tests/support/r3_locator_materialization_guard.py": "8435707018e817f2495a23d9b452c961d97b1f0f91786b05d89c1108dbdd0ea0",
    "tests/architecture/test_r3_editorial_correction_boundary.py": "5b425bdeca7680d5943a853989a582469c134698d60e4675d85696b5fc5becef",
    "tests/unit/test_r3_parse_observability.py": "cb649aee751ed222f2936df814410fa3f6630d00cbab8a8daec3cd8daacc918e",
    "tests/unit/test_r3_prepare_contract_alignment.py": "35d01d8bdfa6ff9495c868c0d9cb691e7bf67a386e34d0ccab48816abed93a12",
    "tests/unit/test_r3_prepare_serialization.py": "d09cdc1912b8b2e450d0e4256a163d07ccdf3a8fc39247dbd20442008cf0f90a",
    "tests/unit/test_r3_cap_a01_targeted.py": "2581379d2017472bb9ce83e0e9d0dc3dcb0749dc0e27303b596d3a8f03ca5616",
    "tests/unit/test_r3_locator_materialization.py": "f76701b1abf7ceb7112ec36b3f178c6d49b2b0fc36dadffb5db7fb2d109a2396"
}
CREATES = [
    "tests/support/r3_portable_clone_guard.py",
    "tests/unit/test_r3_portable_clone_guard.py",
    "architecture/adr/ADR-r3-portable-clone-private-preparations.md"
]
PATHS = tuple(PRE) + tuple(CREATES)
SYMBOLS = {
    "tests/support/r3_guard_oracle.py": [
        "active_inventory"
    ],
    "tests/support/r3_editorial_correction_guard.py": [
        "authenticated",
        "source_matches",
        "index_matches",
        "baseline_view",
        "violations",
        "assert_scope",
        "assert_git_state"
    ],
    "tests/support/r3_parse_observability_guard.py": [
        "patch_violations"
    ],
    "tests/support/r3_prepare_contract_alignment_guard.py": [
        "assert_successor_git_state"
    ],
    "tests/support/r3_serializer_8192_guard.py": [
        "assert_git_state"
    ],
    "tests/support/r3_cap_a01_guard.py": [
        "assert_git_state"
    ],
    "tests/support/r3_locator_materialization_guard.py": [
        "assert_git_state"
    ],
    "tests/architecture/test_r3_editorial_correction_boundary.py": [
        "test_exact_scope_history_working_index_and_predicates",
        "test_each_source_mutation_missing_or_replaced_is_rejected"
    ],
    "tests/unit/test_r3_parse_observability.py": [
        "test_every_patch_source_mutation_is_rejected"
    ],
    "tests/unit/test_r3_prepare_contract_alignment.py": [
        "copied_sources"
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
    "tests/support/r3_guard_oracle.py": "34c8b0f2330c863cc070167b3a0c4a9798caf5591e8ab0e03de787116b80172a",
    "tests/support/r3_editorial_correction_guard.py": "000e1438ae8800851589bf36f3557fb94c9083a9d393d5f5ec3e87b3b6322c8e",
    "tests/support/r3_parse_observability_guard.py": "920f31c96736a2c8c80ffd9e898c781752ed6ff83f5ace58dd3b730d4e228316",
    "tests/support/r3_prepare_contract_alignment_guard.py": "3d3d2de2e4946dc12ec1b1d4438ac64decaca16f2ba04a4e6946c78f84c721e5",
    "tests/support/r3_serializer_8192_guard.py": "52adce9e71a95695693dc5c89c2f9c0d69a17464861077aebc1772c933d57902",
    "tests/support/r3_cap_a01_guard.py": "1f2a17be26637258342cf107795d54a700bfb16b3f31c82a3399cbd956036e22",
    "tests/support/r3_locator_materialization_guard.py": "a547524602d677ef3f5133c7bc2cade8e64ab921ced965af62b7c7ebe4eb4766",
    "tests/architecture/test_r3_editorial_correction_boundary.py": "35aa4b37e08927e91ca29f45ce94ee55c187ff93eeed5235d3af083b1c377997",
    "tests/unit/test_r3_parse_observability.py": "b1289897fc165677730ea922433667057dcba075f739875f05a0bedd9e2c3f96",
    "tests/unit/test_r3_prepare_contract_alignment.py": "48b8359ac6618632a12faf4e98f51e53f93ab221b00f019bf4c5d07538efdf4c",
    "tests/unit/test_r3_prepare_serialization.py": "246ac04d79fb43d6421a7d621d28c076dd4c7886404fec497dea8e1a689c4a44",
    "tests/unit/test_r3_cap_a01_targeted.py": "96414f9921541cdbb9cf6c85e5e5a19bf1764ffcdc52351d22128d60ac5e018b",
    "tests/unit/test_r3_locator_materialization.py": "fb1b5990d5ae67ddd9448eb6d8bd6d7f2005f1fd7f5870e56bcf0663d0cd359e",
    "tests/unit/test_r3_portable_clone_guard.py": "890999df2339943cc6b3d4bec581cbeef25e6faacf7e838d29ee8a369568de78",
    "architecture/adr/ADR-r3-portable-clone-private-preparations.md": "77ce28c04b6bc830f64012228428811af5df431dab07d441022a4f630135b52b"
}
ORACLE_SHA256 = "2f1b74d19c7c2f1f18e3e700ba9b9a8ec6c848a94b2c741d4d2d3aa3263af115"


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def canonical_bytes(path: str, raw: bytes) -> bytes:
    raw = raw.replace(b"\r\n", b"\n")
    if path == SELF:
        pattern = rb'^ORACLE_SHA256 = "[0-9a-f]{64}"\n'
        raw, count = re.subn(pattern, b"", raw, flags=re.MULTILINE)
        if count != 1:
            raise ValueError("PORTABLE_SELF_DECLARATION")
    elif path == EDITORIAL:
        pattern = rb'^(    successor_sha256 = ")[0-9a-f]{64}("\n)'
        raw, count = re.subn(pattern, rb"\g<1>" + b"0" * 64 + rb"\g<2>", raw, flags=re.MULTILINE)
        if count != 1:
            raise ValueError("PORTABLE_BINDING_DECLARATION")
    return raw


def _plain_file(root: Path, path: str) -> Path | None:
    """Reject every reparse point before reading; errors are not absence."""
    relative = Path(path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("PORTABLE_PATH")
    current = root.absolute()
    for part in (None, *relative.parts):
        if part is not None:
            current = current / part
        try:
            info = current.lstat()
        except FileNotFoundError:
            return None
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("PORTABLE_REDIRECTION")
        if current != root / relative and not stat.S_ISDIR(info.st_mode):
            raise ValueError("PORTABLE_PARENT")
    if not stat.S_ISREG(info.st_mode):
        raise ValueError("PORTABLE_FILE_TYPE")
    return current


def source_bytes(root: Path, path: str) -> bytes:
    file = _plain_file(root, path)
    if file is None:
        raise FileNotFoundError("PORTABLE_MISSING")
    before = file.lstat()
    raw = file.read_bytes()
    after = file.lstat()
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
        after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns
    ) or getattr(after, "st_file_attributes", 0) & 0x400 or stat.S_ISLNK(after.st_mode):
        raise ValueError("PORTABLE_READ_RACE")
    return raw


def authenticated(root: Path, *, expected: str = ORACLE_SHA256) -> bool:
    """Trust the running guard's pin, never a candidate-declared digest."""
    from tests.support.r3_d3_scope_guard import PRE as D3_PRE
    from tests.support.r3_d3_scope_guard import authenticated as d3_authenticated
    from tests.support.r3_d3_scope_guard import source_matches as d3_matches

    d3_successor_sha256 = "f89b6688842c7badd43bc83007ef379df89e4da4ffa4f6484de3f356b96e0884"
    if expected == ORACLE_SHA256 and d3_authenticated(root, expected=d3_successor_sha256):
        return d3_matches(root, EDITORIAL, D3_PRE[EDITORIAL])
    try:
        raw = source_bytes(root, SELF)
        if expected != ORACLE_SHA256 or digest(canonical_bytes(SELF, raw)) != expected:
            return False
        if b'ORACLE_SHA256 = "' + expected.encode() + b'"\n' not in raw.replace(b"\r\n", b"\n"):
            return False
        editorial = source_bytes(root, EDITORIAL)
        pin = b'    successor_sha256 = "' + expected.encode() + b'"\n'
        return (pin in editorial.replace(b"\r\n", b"\n")
                and digest(canonical_bytes(EDITORIAL, editorial)) == POST.get(EDITORIAL))
    except (OSError, ValueError):
        return False


def source_matches(root: Path, path: str, historical: str) -> bool:
    from tests.support.r3_d3_scope_guard import PRE as D3_PRE
    from tests.support.r3_d3_scope_guard import baseline_view as d3_view
    from tests.support.r3_d3_scope_guard import source_matches as d3_matches

    try:
        if path in D3_PRE and d3_matches(root, path, D3_PRE[path]) and authenticated(root):
            raw = d3_view(root, path)
            return (digest(raw) == historical or (path in PRE and historical == PRE[path]
                    and digest(canonical_bytes(path, raw)) == POST.get(path)))
        return (path in PRE and historical == PRE[path] and authenticated(root)
                and digest(canonical_bytes(path, source_bytes(root, path))) == POST.get(path))
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


def baseline_view(root: Path, path: str) -> bytes:
    from tests.support.r3_d3_scope_guard import baseline_view as d3_view

    return (baseline_bytes(path) if path in PRE and source_matches(root, path, PRE[path])
            else d3_view(root, path))


def index_matches(root: Path, path: str, raw: bytes) -> bool:
    from tests.support.r4_scope_guard import index_matches as r4_index
    if r4_index(root, path, raw):
        return True
    from tests.support.r3_d3_scope_guard import index_matches as d3_index_matches

    if d3_index_matches(root, path, raw):
        return True
    if path not in PATHS or not authenticated(root):
        return False
    try:
        current = source_bytes(root, path)
        if path != SELF and digest(canonical_bytes(path, current)) != POST.get(path):
            return False
        # POST must be exact current bytes, including both binding declarations.
        return digest(raw) == digest(current) or (path in PRE and digest(raw) == PRE[path])
    except (OSError, ValueError):
        return False


def violations(root: Path, *, changed: set[str] | None = None) -> list[str]:
    from tests.support.r3_d3_scope_guard import PATHS as D3_PATHS
    from tests.support.r3_d3_scope_guard import baseline_view as d3_view
    from tests.support.r3_d3_scope_guard import violations as d3_violations
    from tests.support.r4_scope_guard import PATHS as R4_PATHS

    assert set(POST) == set(PATHS) - {SELF} and len(PATHS) == 16
    errors = d3_violations(root)
    if not authenticated(root):
        errors.append("PORTABLE_ORACLE_IDENTITY")
    for path, expected in POST.items():
        try:
            if digest(canonical_bytes(path, d3_view(root, path))) != expected:
                errors.append("PORTABLE_IDENTITY:" + path)
        except (OSError, ValueError):
            errors.append("PORTABLE_IDENTITY:" + path)
    if changed is not None:
        from tests.support.r5_scope_guard import PATHS as R5_PATHS
        from tests.support.r5_scope_guard import violations as r5_violations
        errors += r5_violations(root)
        errors += ["PORTABLE_MISSING:" + p for p in sorted(set(PATHS) - changed)]
        errors += ["PORTABLE_UNAPPROVED:" + p for p in sorted(changed - set(PATHS) - set(D3_PATHS) - set(R4_PATHS) - set(R5_PATHS))]
    return errors


def outside_scope(raw: bytes, path: str) -> str:
    tree = ast.parse(raw)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in SYMBOLS[path]:
            node.body = [ast.Pass()]
    return ast.dump(tree)


def assert_scope(root: Path) -> None:
    from tests.support.r3_d3_scope_guard import baseline_view as d3_view

    assert violations(root) == []
    for path in PRE:
        assert outside_scope(baseline_bytes(path), path) == outside_scope(d3_view(root, path), path), path


@dataclass(frozen=True)
class PrivatePreparationResult:
    status: str
    present_count: int
    errors: tuple[str, ...]


def _inspect_preparations(
    root: Path, expected: dict[str, str], *, require_complete: bool, git_paths: set[str]
) -> PrivatePreparationResult:
    """Pure checker; production entry below always supplies the canonical map."""
    errors = ["PROTECTED_DOCUMENT_INDEXED:" + p for p in sorted(git_paths & expected.keys())]
    present = 0
    for path, expected_hash in expected.items():
        try:
            file = _plain_file(root, path)
            if file is None:
                continue
            present += 1
            # Private documents retain the historical RAW-byte hash policy.
            if hashlib.sha256(source_bytes(root, path)).hexdigest() != expected_hash:
                errors.append("PROTECTED_DOCUMENT_CHANGED:" + path)
        except (OSError, ValueError):
            errors.append("PROTECTED_DOCUMENT_UNREADABLE_OR_REDIRECTED:" + path)
    if 0 < present < len(expected):
        errors.append("PRIVATE_PREPARATION_PARTIAL")
    if require_complete and present != len(expected):
        errors.append("PRIVATE_PREPARATION_ATTESTATION_INCOMPLETE")
    status = "FAIL" if errors else ("PASS" if present == len(expected) else "NOT_PERFORMED_ABSENT")
    return PrivatePreparationResult(status, present, tuple(errors))


def private_preparations(root: Path, *, require_complete: bool = False) -> PrivatePreparationResult:
    from tests.support.r3_guard_oracle import PREPARATION

    git_paths: set[str] = set()
    # HEAD catches a staged deletion; the index catches a new tracked private file.
    for args in (["ls-files", "-z"], ["ls-tree", "-r", "--name-only", "-z", "HEAD"]):
        result = subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)
        git_paths.update(result.stdout.split("\0"))
    return _inspect_preparations(root, PREPARATION, require_complete=require_complete, git_paths=git_paths)


def assert_git_state(root: Path) -> None:
    from tests.support.r3_d3_scope_guard import assert_git_state as assert_d3_git_state
    from tests.support.r3_guard_oracle import PREPARATION

    assert_d3_git_state(root)
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
