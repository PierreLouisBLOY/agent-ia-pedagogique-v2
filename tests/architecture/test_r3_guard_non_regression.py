import ast
import json
from pathlib import Path

import pytest

from tests.support.r3_guard_oracle import (
    GUARDS,
    PREPARATION,
    R3_CONTRACT,
    R3_PATHS,
    active_inventory,
    assert_guard_scope,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("path", tuple(GUARDS))
def test_each_guard_rejects_unapproved_function_mutation(tmp_path, path):
    target = tmp_path / path
    target.parent.mkdir(parents=True)
    source = (ROOT / path).read_text("utf-8")
    target.write_text(source, encoding="utf-8")
    assert_guard_scope(tmp_path, paths=(path,))
    tree = ast.parse(source)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name not in GUARDS[path])
    lines = source.splitlines()
    lines.insert(node.end_lineno, "    assert False")
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(AssertionError):
        assert_guard_scope(tmp_path, paths=(path,))


@pytest.mark.parametrize("mutation", ("extra", "omission", "same_count"))
def test_active_inventory_rejects_exact_set_mutants(mutation):
    changed = set(R3_PATHS)
    if mutation != "extra":
        changed.remove(R3_PATHS[0])
    if mutation != "omission":
        changed.add("backend/modules/unapproved_r3.py")
    assert active_inventory(ROOT, changed=changed)


def test_mutable_manifest_cannot_authorize_same_count_replacement(tmp_path):
    target = tmp_path / R3_CONTRACT
    target.parent.mkdir(parents=True)
    doc = json.loads((ROOT / R3_CONTRACT).read_text("utf-8"))
    doc["approved_inventory"][0] = "backend/modules/unapproved_r3.py"
    target.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(AssertionError):
        active_inventory(tmp_path, changed=set(doc["approved_inventory"]))


@pytest.mark.parametrize("path", (R3_PATHS[0], next(iter(PREPARATION)), "backend/hidden.py"))
def test_index_is_checked_independently_of_working_tree(monkeypatch, path):
    import subprocess

    from tests.support import r3_guard_oracle as oracle
    def git(args, **kwargs):
        result = {path} if "--cached" in args else set(R3_PATHS)
        return subprocess.CompletedProcess(args, 0, stdout="\n".join(sorted(result)))
    monkeypatch.setattr(oracle.subprocess, "run", git)
    errors = active_inventory(ROOT)
    if path in PREPARATION:
        assert "PROTECTED_DOCUMENT_INDEXED:" + path in errors
    elif path not in R3_PATHS:
        assert path in errors
    else:
        assert errors == []
