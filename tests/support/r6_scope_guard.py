"""Exact R6 successor inventory pinned to the PRE-R6 candidate baseline."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

BASELINE = "5bdd49be35149a7134e866fa4473926b65a5ee69"
ROOT = Path(__file__).resolve().parents[2]
SELF = "tests/support/r6_scope_guard.py"
MANIFEST = "tests/support/r6_scope_manifest.json"
SELF_SHA256 = "f8c7baaebbf0315aa098eee6518a9a861a86c3c2e846aefd8ccb82cd337715e1"
MANIFEST_SHA256 = "aecc27a10365426145513353ba293a380b2501b2aa9ff69e8930368f12ea4b05"


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def _guard_digest(raw: bytes) -> str:
    self_pattern = rb"^SELF_" + rb"SHA256 = \"[^\"]+\"\r?\n"
    manifest_pattern = rb"^MANIFEST_" + rb"SHA256 = \"[^\"]+\"\r?\n"
    canonical = re.sub(self_pattern, b"", raw, flags=re.M)
    canonical = re.sub(manifest_pattern, b"", canonical, flags=re.M)
    return digest(canonical)


def _manifest(root: Path) -> dict[str, object]:
    path = root / MANIFEST
    raw = path.read_bytes()
    if digest(raw) != MANIFEST_SHA256:
        raise ValueError("R6_MANIFEST_IDENTITY")
    value = json.loads(raw)
    if value.get("schema") != "R6-SCOPE-MANIFEST-1.0" or value.get("baseline") != BASELINE:
        raise ValueError("R6_MANIFEST_SCHEMA")
    return value


def _authenticated(root: Path) -> bool:
    try:
        if _guard_digest((root / SELF).read_bytes()) != SELF_SHA256:
            return False
        _manifest(root)
        return True
    except (OSError, ValueError, json.JSONDecodeError):
        return False


def _paths(root: Path) -> tuple[tuple[str, ...], tuple[str, ...], dict[str, str]]:
    value = _manifest(root)
    cp645 = tuple(value["cp645_paths"])
    r6 = tuple(value["r6_paths"])
    expected = dict(value["sha256"])
    if len(cp645) != len(set(cp645)) or len(r6) != len(set(r6)):
        raise ValueError("R6_PATH_DUPLICATE")
    if set(cp645) & set(r6) or set(expected) != set(cp645) | set(r6):
        raise ValueError("R6_PATH_INVENTORY")
    return cp645, r6, expected


def authenticated(root: Path = ROOT) -> bool:
    return _authenticated(root)


def exact(root: Path, path: str) -> bool:
    try:
        if not _authenticated(root):
            return False
        _, _, expected = _paths(root)
        return path in expected and digest((root / path).read_bytes()) == expected[path]
    except (OSError, ValueError, json.JSONDecodeError):
        return False


def index_matches(root: Path, path: str, raw: bytes) -> bool:
    try:
        _, _, expected = _paths(root)
        return _authenticated(root) and path in expected and digest(raw) == expected[path]
    except (OSError, ValueError, json.JSONDecodeError):
        return False


def violations(root: Path = ROOT, *, changed: set[str] | None = None) -> list[str]:
    errors: list[str] = []
    if not _authenticated(root):
        return ["R6_GUARD_OR_MANIFEST_IDENTITY"]
    cp645, r6, expected = _paths(root)
    if set(expected) != set(cp645) | set(r6):
        errors.append("R6_INVENTORY_IDENTITY")
    errors.extend("R6_IDENTITY:" + path for path in expected if not exact(root, path))
    if changed is not None:
        allowed = set(cp645) | set(r6)
        errors.extend("R6_UNAPPROVED:" + path for path in sorted(changed - allowed))
        errors.extend("R6_MISSING:" + path for path in sorted(allowed - changed))
    return errors


def _load_constants() -> None:
    global CP645_PATHS, CP645_PRE, CP645_POST, R6_PATHS, PATHS
    value = _manifest(ROOT)
    CP645_PATHS = tuple(value["cp645_paths"])
    CP645_PRE = dict(value["cp645_pre_sha256"])
    CP645_POST = {path: value["sha256"][path] for path in CP645_PATHS}
    R6_PATHS = tuple(value["r6_paths"])
    PATHS = tuple((*CP645_PATHS, *R6_PATHS))


_load_constants()
