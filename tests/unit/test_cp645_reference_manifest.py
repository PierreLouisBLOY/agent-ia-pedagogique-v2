from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.adapters.outbound.persistence import migrations

MANIFEST = Path(__file__).resolve().parents[2] / "database/reference/CP645.json"
ROOT = MANIFEST.parents[2]


def test_reference_manifest_matches_unique_runtime_authentication_identity() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    inventory = manifest["sqlite_inventory"]
    assert manifest["size_bytes"] == migrations.CANONICAL_SEED_SIZE == 227_557_376
    assert manifest["sha256"] == migrations.CANONICAL_SEED_SHA256 == (
        "9d64d15e9c246924edeff16e7bbb5fb7a53791fc2ddf217541824771b34053e1"
    )
    assert (
        inventory["tables"], inventory["explicit_indexes"],
        inventory["triggers"], inventory["views"],
    ) == (
        migrations.CANONICAL_SEED_TABLES, migrations.CANONICAL_SEED_EXPLICIT_INDEXES,
        migrations.CANONICAL_SEED_TRIGGERS, migrations.CANONICAL_SEED_VIEWS,
    ) == (121, 23, 7, 11)
    assert manifest["schema_comparison"]["previous_seed_sha256"] != manifest["sha256"]
    assert manifest["policy"]["canonical_identity_count"] == 1


def test_cp645_reference_preserves_approval_and_seed_runtime_separation() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    content = manifest["content_status"]
    policy = manifest["policy"]
    assert content["canonical_notions"] == 628
    assert content["notion_rows_total"] == content["canonical_notions"] + content["merged_notions"]
    assert content["formula_approved"] == content["formula_rows_total"] == 210
    assert content["formula_owner_validation_events"] == 210
    assert policy["seed_immutable"] and policy["runtime_is_distinct_derived_copy"]
    assert not policy["binary_in_git"]
    assert not policy["method_approval_inferred_from_formula_approval"]
    assert policy["allowlisted_migrations"] == list(migrations.APPROVED_RUNTIME_MIGRATIONS)


def test_real_benchmark_identity_pins_follow_the_same_cp645_reference() -> None:
    import ast

    for name in (
        "test_retrieval_quality_real_gate.py",
        "test_semantic_retrieval_offline_r1_gate.py",
        "test_semantic_retrieval_live_gate.py",
    ):
        tree = ast.parse((ROOT / "tests/non_functional" / name).read_text("utf-8"))
        pins = {
            node.targets[0].id: ast.literal_eval(node.value)
            for node in tree.body
            if isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id in {"EXPECTED_SEED_SIZE", "EXPECTED_SEED_SHA256"}
        }
        assert pins == {
            "EXPECTED_SEED_SIZE": migrations.CANONICAL_SEED_SIZE,
            "EXPECTED_SEED_SHA256": migrations.CANONICAL_SEED_SHA256,
        }


def test_r6_scope_guard_covers_exact_current_baseline_delta() -> None:
    from tests.support import r6_scope_guard as guard

    assert set(guard.CP645_PATHS) == set(guard.CP645_POST)
    assert len(guard.CP645_PATHS) == len(set(guard.CP645_PATHS)) == 9
    assert set(guard.PATHS) == set(guard.CP645_PATHS) | set(guard.R6_PATHS)
    assert guard.violations(ROOT, changed=set(guard.PATHS)) == []
    assert guard.violations(ROOT, changed=set(guard.PATHS) | {"backend/r6_unapproved.py"}) == [
        "R6_UNAPPROVED:backend/r6_unapproved.py"
    ]


@pytest.mark.parametrize("path", [
    "database/reference/CP645.json",
    "backend/infrastructure/composition/factories/r6_p0.py",
])
def test_r6_scope_guard_rejects_mutated_exact_artifact(tmp_path: Path, path: str) -> None:
    from tests.support import r6_scope_guard as guard

    for allowed in guard.PATHS:
        source = ROOT / allowed
        if source.is_file():
            target = tmp_path / allowed
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
    for allowed in (guard.SELF, guard.MANIFEST):
        source = ROOT / allowed
        target = tmp_path / allowed
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    target = tmp_path / path
    target.write_bytes(target.read_bytes() + b"\n# unauthorized mutation\n")
    assert "R6_IDENTITY:" + path in guard.violations(tmp_path)


def test_cp645_index_substitution_is_rejected() -> None:
    from tests.support import r6_scope_guard as guard

    for path in guard.CP645_PATHS:
        raw = (ROOT / path).read_bytes()
        assert guard.index_matches(ROOT, path, raw)
        assert not guard.index_matches(ROOT, path, raw + b"\n# substituted index\n")
