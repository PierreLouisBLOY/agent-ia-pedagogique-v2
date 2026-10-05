"""Active versioned STMG consumers remain exact and reject substitutions."""
import json
from pathlib import Path

import pytest

from tests.support import r6_scope_guard as guard

ROOT = Path(__file__).resolve().parents[2]
OWNER_PATHS = (
    "backend/modules/knowledge_reference/application/queries/stmg_alignment.py",
    "backend/modules/knowledge_reference/contracts/dto/stmg_frames.py",
    "backend/modules/knowledge_reference/ports/outbound/institutional_catalog.py",
    "backend/modules/knowledge_reference/application/queries/inspect_institutional_catalog.py",
    "backend/adapters/inbound/application/institutional_catalog.py",
    "backend/adapters/inbound/application/stmg_alignment.py",
    "backend/adapters/outbound/resource_library/institutional_sqlite.py",
    "backend/infrastructure/composition/factories/institutional_catalog.py",
    "backend/modules/pedagogical_context/contracts/dto/stmg_institutional.py",
    "backend/modules/pedagogical_context/contracts/dto/p0_context.py",
    "backend/modules/pedagogical_design/contracts/dto/course_policy.py",
    "backend/modules/pedagogical_design/application/commands/create_p0_candidate.py",
    "backend/modules/work_orchestration/application/services/p0_creation.py",
    "backend/modules/work_orchestration/application/services/p0_agentic.py",
    "backend/infrastructure/composition/factories/p0_creation.py",
    "backend/adapters/inbound/api/p0_creation.py",
    "backend/adapters/outbound/generation/openai/p0_content.py",
    "backend/adapters/outbound/review/p0_review.py",
    "backend/modules/materialization_export/application/commands/export_saved.py",
    "backend/modules/pedagogical_design/application/commands/reframe_course.py",
    "backend/adapters/inbound/application/reframe_course.py",
    "backend/modules/validation_control/application/commands/validate_p0.py",
    "frontend/app.js", "frontend/index.html",
)


DECLARED_OWNERS = tuple(json.loads((ROOT / guard.MANIFEST).read_text("utf-8"))["successors"][-1]["changed_owners"])


@pytest.mark.parametrize("path", DECLARED_OWNERS)
def test_stmg_active_owner_and_mutation(tmp_path, path):
    for protected in (*guard.PATHS, guard.SELF, guard.MANIFEST):
        target = tmp_path / protected
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / protected).read_bytes())
    assert guard.violations(tmp_path) == []
    raw = (ROOT / path).read_bytes()
    assert guard.index_matches(tmp_path, path, raw)
    assert not guard.index_matches(tmp_path, path, raw + b"\n# substitution\n")
    (tmp_path / path).write_bytes(raw + b"\n# substitution\n")
    assert guard.violations(tmp_path) == ["R6_IDENTITY:" + path]


def test_successor_keeps_historical_manifest_and_reviewed_entry():
    manifest = json.loads((ROOT / guard.MANIFEST).read_text("utf-8"))
    successor = manifest["successors"][-1]
    assert successor["entry"] == "7a54666567f3d11940cb6cb556439d986d487494"
    assert successor["purpose"] == "INSTITUTIONAL_AUTHORITY_628_FOUNDATION"
    assert successor["predecessor_manifest_sha256"] == "05eaba891801f3821021ab689d4d83bf40ed22aa361295a853ef719c15287e90"
    course = next(row for row in manifest["successors"] if row["purpose"] == "COURSE_BENCHMARK_PDF3")
    assert course["entry"] == "790230f7a9762e61ef22800b9fcbeb8f59e221af"
    assert course["predecessor_manifest_sha256"] == "79bf1a35640f0e1cacb244f139423d2ee46099f21009351434ad8363bf1e700d"
    historical = next(row for row in manifest["successors"] if row["purpose"] == "STMG_INSTITUTIONAL_ALIGNMENT")
    assert historical["entry"] == "cb0d6df2ebb4070ef0c89108e4005bf118e3e1f1"
    assert historical["predecessor_manifest_sha256"] == "f9f406104c24e415f6b9f862e1458571d1020283dac70c32fa8ac23201dce9dd"
    assert set(historical["changed_owners"]) <= set(successor["changed_owners"])
    assert set(OWNER_PATHS) <= set(successor["changed_owners"])
    assert successor["canonical_security_guards_changed"] is False
