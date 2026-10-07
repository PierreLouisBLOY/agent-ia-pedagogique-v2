"""Closed successor, exact mutation rejection and preserved architecture."""
import ast
import subprocess
from pathlib import Path

import pytest

from tests.support.r3_editorial_correction_guard import (
    BASELINE,
    CREATES,
    ORACLE_SHA256,
    PATHS,
    POST,
    PRE,
    SELF,
    assert_git_state,
    assert_predicates,
    assert_scope,
    authenticated,
    baseline_bytes,
    digest,
    oracle_digest,
    outside_scope,
    source_matches,
    violations,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.usefixtures("historical_guard_sources")
def test_exact_scope_history_working_index_and_predicates():
    assert_scope(ROOT)
    assert_git_state(ROOT)
    assert len(PRE) == 23 and len(CREATES) == 8 and len(PATHS) == 31
    assert authenticated(ROOT)
    from tests.support.r3_portable_clone_guard import baseline_view as portable_view

    assert oracle_digest(portable_view(ROOT, SELF)) == ORACLE_SHA256
    assert_predicates(ROOT)


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.usefixtures("historical_guard_sources")
def test_each_source_mutation_missing_or_replaced_is_rejected(tmp_path, path):
    from tests.support.r3_d3_scope_guard import PATHS as D3_PATHS
    from tests.support.r3_portable_clone_guard import PATHS as PORTABLE_PATHS

    for item in set(PATHS) | set(PORTABLE_PATHS) | set(D3_PATHS):
        destination = tmp_path / item
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((ROOT / item).read_bytes())
    assert violations(tmp_path) == []
    target = tmp_path / path
    original = target.read_bytes()
    target.write_bytes(original + b"\nUNAPPROVED_DRIFT = True\n")
    assert violations(tmp_path)
    if path in PRE:
        assert not source_matches(tmp_path, path, PRE[path])
    target.unlink()
    assert violations(tmp_path)


@pytest.mark.parametrize("path", PATHS)
def test_every_index_mutation_rejected_without_working_drift(monkeypatch, path):
    run = subprocess.run
    def tampered(args, **kwargs):
        if args == ["git", "show", ":" + path]:
            return subprocess.CompletedProcess(args, 0, stdout=(ROOT / path).read_bytes()+b"\nDRIFT\n")
        return run(args, **kwargs)
    monkeypatch.setattr(subprocess, "run", tampered)
    with pytest.raises(AssertionError):
        assert_git_state(ROOT)


def test_same_count_inventory_replacement_and_oracle_table_tampering(tmp_path):
    bad = set(PATHS)
    bad.remove(PATHS[0])
    bad.add("backend/unapproved.py")
    assert violations(ROOT, changed=bad)
    target = tmp_path / SELF
    target.parent.mkdir(parents=True)
    raw = (ROOT / SELF).read_bytes()
    target.write_bytes(raw.replace(next(iter(POST.values())).encode(), b"0"*64))
    assert not authenticated(tmp_path)


@pytest.mark.parametrize("path", tuple(PRE))
def test_outside_symbol_addition_cannot_be_hidden(path):
    old = baseline_bytes(path)
    assert outside_scope(old, path) != outside_scope(old+b"\nUNAPPROVED = True\n", path)


@pytest.mark.usefixtures("historical_guard_sources")
def test_m09_pure_contract_and_no_provider_editorial_route():
    path = "backend/modules/validation_control/contracts/dto/editorial_scope.py"
    tree = ast.parse((ROOT/path).read_bytes())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(n.name not in {"os", "socket", "sqlite3", "openai", "anthropic", "subprocess"} for n in node.names)
        if isinstance(node, ast.ImportFrom):
            assert not any(word in (node.module or "") for word in ("adapters", "infrastructure", "agent_runtime"))
    route = "backend/adapters/inbound/api/r3_review_modify.py"
    before = subprocess.run(["git", "show", f"{BASELINE}:{route}"], cwd=ROOT, check=True, capture_output=True).stdout
    assert before == (ROOT/route).read_bytes()
    policy = "backend/modules/pedagogical_design/domain/policies/assessment_revision.py"
    tree = ast.parse((ROOT/policy).read_bytes())
    local = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "assemble_editorial_corrections")
    assert all(not isinstance(n, (ast.Import, ast.ImportFrom)) for n in ast.walk(local))
    assert "open(" not in ast.unparse(local) and "_store" not in ast.unparse(local)
    service = "backend/modules/work_orchestration/application/services/r3_review_modify.py"
    old = ast.parse(baseline_bytes(service))
    from tests.support.r3_d3_scope_guard import assert_scope, baseline_view
    assert_scope(ROOT)
    new = ast.parse(baseline_view(ROOT, service))
    def method(tree, name):
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "R3ReviewModifyService")
        return next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name)
    assert ast.dump(method(old, "poll")) == ast.dump(method(new, "poll"))
    assert digest((ROOT/route).read_bytes()) == digest(before)
