"""Closed LU source coverage; preparatory review never qualifies a code delta."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

from tests.support import r6_scope_guard as guard
from tests.unit.test_stabilisation_active_guard import active_clone

__all__ = ["active_clone"]
ROOT = Path(__file__).resolve().parents[2]
ENTRY = "89ef3edc5f9d09e5f769862833ffa2c1b175c8fb"
ENTRY_TREE = "93bdaa387815f6a6654496120b40e6853629f082"
PREDECESSOR = "3d1ac5b5b44e7b920f1a19d338dbd4903df73bb92444d68723d01fcf36ffe1ee"
REGISTRY = "tests/support/lu_product_guard_registry.json"
PURPOSE = "LU_PRODUIT_01_INTEGRATED_ACTIVE_1_0"


def _git(*args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                          check=True, timeout=20).stdout


def _registry() -> dict:
    assert guard.exact(ROOT, REGISTRY)
    result = json.loads((ROOT / REGISTRY).read_text("utf-8"))
    assert result["schema"] == "LU-PRODUCT-GUARD-REGISTRY-1.0"
    assert result["baseline"] == ENTRY
    assert result["baseline_tree"] == ENTRY_TREE
    assert result["predecessor_manifest_sha256"] == PREDECESSOR
    assert result["structural_review_status"] == "DISTINCT_REVIEW_COMPLETED"
    assert result["exact_delta_review_status"] == "DISTINCT_REVIEW_COMPLETED"
    return result


def _scanner(raw: bytes) -> bytes:
    return re.sub(rb'^MANIFEST_SHA256 = "[^"\n]+"\n', b"",
                  raw.replace(b"\r\n", b"\n"), flags=re.M)


def test_lu_entry_and_complete_predecessor_are_preserved():
    assert _git("rev-parse", ENTRY + "^{tree}").decode().strip() == ENTRY_TREE
    assert subprocess.run(["git", "merge-base", "--is-ancestor", ENTRY, "HEAD"],
                          cwd=ROOT, capture_output=True).returncode == 0
    previous_raw = _git("show", ENTRY + ":" + guard.MANIFEST)
    assert guard.digest(previous_raw) == PREDECESSOR
    previous = json.loads(previous_raw)
    current = json.loads((ROOT / guard.MANIFEST).read_text("utf-8"))
    registry = _registry()
    assert registry["received_owner_hashes"] == previous["sha256"]
    assert registry["private_exclusions"] == previous["private_source_exclusions"]
    for key in ("schema", "baseline", "cp645_paths", "cp645_pre_sha256",
                "private_source_exclusions"):
        assert current[key] == previous[key]
    assert current["successors"][:len(previous["successors"])] == previous["successors"]
    assert len(current["successors"]) == len(previous["successors"]) + 1
    successor = current["successors"][-1]
    assert successor["purpose"] == PURPOSE
    assert successor["baseline"] == ENTRY
    assert successor["parent_manifest_sha256"] == PREDECESSOR
    assert successor["guard_functions"] == "UNCHANGED"
    assert successor["private_exclusions_preserved"] == 27
    assert successor["registry_path"] == REGISTRY
    assert successor["registry_sha256"] == guard.digest((ROOT / REGISTRY).read_bytes())
    assert successor["changed_owners"] == registry["changed_owners"]
    assert _scanner((ROOT / guard.SELF).read_bytes()) == _scanner(
        _git("show", ENTRY + ":" + guard.SELF))
    assert set(previous["sha256"]) <= set(current["sha256"])
    assert not set(current["sha256"]) & set(guard.PRIVATE_PREPARATION_PATHS)


def test_lu_registry_equals_real_delta_and_only_admitted_owners_change():
    registry = _registry()
    changed = set(_git("diff", "--name-only", ENTRY, "--").decode().splitlines())
    changed.update(_git("ls-files", "--others", "--exclude-standard").decode().splitlines())
    assert len(registry["delta_paths"]) == len(set(registry["delta_paths"]))
    assert changed == set(registry["delta_paths"])
    controls = {guard.SELF, guard.MANIFEST, REGISTRY}
    assert set(registry["changed_owners"]) == changed - controls
    assert set(registry["owner_sha256"]) == set(registry["changed_owners"])
    previous = json.loads(_git("show", ENTRY + ":" + guard.MANIFEST))
    current = json.loads((ROOT / guard.MANIFEST).read_text("utf-8"))
    assert set(current["sha256"]) - set(previous["sha256"]) == (
        set(registry["changed_owners"]) | {REGISTRY}) - set(previous["sha256"])
    for path, before in previous["sha256"].items():
        if path not in registry["changed_owners"]:
            assert current["sha256"][path] == before
    for path, identities in registry["owner_sha256"].items():
        assert guard.exact(ROOT, path)
        assert current["sha256"][path] == identities["after"]
        assert guard.digest((ROOT / path).read_bytes()) == identities["after"]
        old = subprocess.run(["git", "show", ENTRY + ":" + path], cwd=ROOT,
                             capture_output=True, timeout=20)
        assert (guard.digest(old.stdout) if old.returncode == 0 else None) == identities["before"]


@pytest.mark.parametrize("fault", ("unknown", "omitted"))
def test_lu_closed_active_inventory_rejects_extra_and_missing_owner(fault):
    registry = _registry()
    declared = set(json.loads((ROOT / guard.MANIFEST).read_text("utf-8"))["active_delta_paths"])
    assert guard.active_delta_violations(ROOT, declared) == []
    if fault == "unknown":
        assert guard.active_delta_violations(ROOT, declared | {"backend/lu_unreviewed.py"}) == [
            "R6_ACTIVE_UNAPPROVED:backend/lu_unreviewed.py"]
    else:
        owner = registry["changed_owners"][0]
        assert guard.active_delta_violations(ROOT, declared - {owner}) == [
            "R6_ACTIVE_MISSING:" + owner]


@pytest.mark.parametrize("coordinated_manifest", (False, True))
def test_lu_registry_substitution_never_acquires_admission(active_clone, coordinated_manifest):
    target = active_clone / REGISTRY
    manifest = active_clone / guard.MANIFEST
    original = target.read_bytes()
    original_manifest = manifest.read_bytes()
    try:
        replacement = original + b"\n# unapproved registry replacement\n"
        target.write_bytes(replacement)
        assert guard.violations(active_clone) == ["R6_IDENTITY:" + REGISTRY]
        assert not guard.index_matches(active_clone, REGISTRY, replacement)
        if coordinated_manifest:
            forged = json.loads(original_manifest)
            forged["sha256"][REGISTRY] = guard.digest(replacement)
            manifest.write_text(json.dumps(forged, ensure_ascii=False, indent=2) + "\n", "utf-8")
            assert not guard.authenticated(active_clone)
            assert guard.violations(active_clone) == ["R6_GUARD_OR_MANIFEST_IDENTITY"]
    finally:
        target.write_bytes(original)
        manifest.write_bytes(original_manifest)
    assert guard.violations(active_clone) == []
