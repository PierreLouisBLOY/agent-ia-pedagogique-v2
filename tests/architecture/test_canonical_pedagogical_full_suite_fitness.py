from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parents[2]
FACADE = ROOT / "tests/e2e/core/full_suite_adapters.py"
INTEGRATION_GATE = ROOT / "tests/integration/test_canonical_pedagogical_full_suite_real_gate.py"
JSON_REPORT = ROOT / "docs/development/PHASE_12_15_G_CANONICAL_SUITE_REPORT.json"
MARKDOWN_REPORT = ROOT / "docs/development/PHASE_12_15_G_CANONICAL_SUITE_REPORT.md"


def test_full_suite_facade_is_test_only_and_contains_no_direct_sql_or_provider_access() -> None:
    source = FACADE.read_text(encoding="utf-8")
    assert "sqlite3" not in source
    assert "SELECT " not in source
    assert "INSERT " not in source
    assert "requests" not in source
    assert "http://" not in source and "https://" not in source
    assert "backend" not in str(FACADE.relative_to(ROOT / "tests"))


def test_backend_never_reads_committed_evaluation_reports_or_test_facade() -> None:
    forbidden = (
        JSON_REPORT.name,
        MARKDOWN_REPORT.name,
        "tests.e2e.core.full_suite_adapters",
    )
    for path in (ROOT / "backend").rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert not any(token in source for token in forbidden), path


def test_committed_reports_are_safe_complete_factory_outputs() -> None:
    payload = json.loads(JSON_REPORT.read_text(encoding="utf-8"))
    markdown = MARKDOWN_REPORT.read_text(encoding="utf-8")
    assert payload["report_schema"] == {"major": 1, "minor": 0}
    assert payload["evaluation_schema"] == {"major": 1, "minor": 0}
    assert payload["suite_id"] == "suite.pedagogical-canonical"
    assert payload["verdict"] == "PASS"
    assert len(payload["cases"]) == 8
    assert [case["case_code"] for case in payload["cases"]] == [
        f"SCN-{index:02d}" for index in range(1, 9)
    ]
    assert payload["summary"] == {
        "case_count": 8,
        "error_count": 0,
        "fail_count": 0,
        "inconclusive_count": 0,
        "pass_count": 8,
        "repetition_count": 8,
        "skipped_count": 0,
    }
    serialized = JSON_REPORT.read_bytes() + MARKDOWN_REPORT.read_bytes()
    for forbidden in (
        b".sqlite",
        b"PEDAGOGICAL_CANONICAL_SEED_PATH",
        b"G:\\",
        b"C:\\Users\\",
        b"http://",
        b"https://",
    ):
        assert forbidden not in serialized
    assert "Corpus pedagogique golden canonique" not in markdown


def test_real_gate_owns_two_run_and_committed_byte_reproducibility() -> None:
    source = INTEGRATION_GATE.read_text(encoding="utf-8")
    assert '"g-run-a.sqlite"' in source
    assert '"g-run-b.sqlite"' in source
    assert "run_a.json_artifact.content == run_b.json_artifact.content" in source
    assert "read_bytes() == run_a.json_artifact.content" in source
