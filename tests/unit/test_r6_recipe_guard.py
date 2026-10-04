from pathlib import Path

import pytest

from tests.support import r6_scope_guard as guard

ROOT = Path(__file__).resolve().parents[2]
ADDITIONS = (
    "backend/adapters/inbound/application/lot2_saved_production.py",
    "backend/adapters/outbound/export/lot1_word.py",
    "backend/adapters/outbound/export/r6_readable_word.py",
    "backend/modules/materialization_export/contracts/dto/lot1_word_table.py",
    "backend/infrastructure/composition/factories/local_browser.py",
    "backend/infrastructure/composition/factories/saved_p0_documentary.py",
    "tests/integration/test_r6_p0_matrix_application.py",
    "backend/modules/pedagogical_design/application/commands/reassemble_p0_candidate.py",
    "backend/modules/materialization_export/application/commands/export_saved.py",
    "tests/unit/test_r6_p0_reassembly.py",
)


@pytest.mark.parametrize("path", ADDITIONS)
def test_recipe_reuse_and_composition_are_pinned_and_mutation_rejected(tmp_path, path):
    for allowed in (*guard.PATHS, guard.SELF, guard.MANIFEST):
        target = tmp_path / allowed
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / allowed).read_bytes())
    raw = (ROOT / path).read_bytes()
    assert guard.violations(tmp_path) == []
    assert guard.index_matches(tmp_path, path, raw)
    assert not guard.index_matches(tmp_path, path, raw + b"\n# substitution\n")
    (tmp_path / path).write_bytes(raw + b"\n# substitution\n")
    assert guard.violations(tmp_path) == ["R6_IDENTITY:" + path]
    (tmp_path / path).unlink()
    assert not guard.exact(tmp_path, path)
