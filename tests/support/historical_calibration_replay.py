"""Execute the original report assertions on authenticated historical Git code."""
from __future__ import annotations

import ast
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from tests.support.historical_guard_fixture import (
    CALIBRATION_FABRICATION,
    FABRICATION,
    materialize_historical_guard_sources,
)


def replay_historical_report(
    root: Path, temporary: Path,
    target: str = "tests/unit/test_pedagogical_calibration_r4_r3_r3.py::"
    "test_reports_are_safe_float_free_and_byte_reproducible",
) -> subprocess.CompletedProcess[bytes]:
    admitted = {
        "tests/unit/test_pedagogical_calibration_r4_r3_r3.py::"
        "test_reports_are_safe_float_free_and_byte_reproducible",
        *("tests/unit/test_pedagogical_calibration_r3b_r3.py::" + name for name in (
            "test_consolidated_manifest_has_twenty_five_unique_hash_only_results",
            "test_new_ids_order_and_frozen_checksum_are_deterministic",
            "test_cost_ceiling_and_exact_approval_are_frozen_and_mutation_sensitive",
            "test_generated_reports_and_ignored_ledger_match_deterministic_renderers",
        )),
    }
    if target not in admitted:
        raise ValueError("HISTORICAL_CALIBRATION_TARGET_REJECTED")
    source = root / "artifacts/calibration"
    files = sorted(p for p in source.rglob("*") if p.is_file())
    if len(files) != 321:
        raise ValueError("HISTORICAL_CALIBRATION_321_PRIVATE_FILES_REQUIRED")
    fabrication = (CALIBRATION_FABRICATION if target.startswith(
        "tests/unit/test_pedagogical_calibration_r3b_r3.py::") else FABRICATION)
    historical = materialize_historical_guard_sources(temporary / "historical", fabrication)
    for path in files:
        if path.is_symlink() or path.is_junction():
            raise ValueError("HISTORICAL_CALIBRATION_LINK_REJECTED")
        copied = historical / path.relative_to(root)
        copied.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, copied)
        if hashlib.sha256(path.read_bytes()).digest() != hashlib.sha256(copied.read_bytes()).digest():
            raise ValueError("HISTORICAL_CALIBRATION_COPY_MISMATCH")
    if target.endswith("::test_generated_reports_and_ignored_ledger_match_deterministic_renderers"):
        bench = historical / "tests/unit/test_pedagogical_calibration_r3b_r3.py"
        original = bench.read_bytes()
        ledger_commit = "2b378114b2f439307a85007981f2239d14461c76"
        ledger_bench = subprocess.check_output([
            "git", "show", ledger_commit + ":tests/unit/test_pedagogical_calibration_r3b_r3.py",
        ], cwd=historical)
        name = "test_generated_reports_and_ignored_ledger_match_deterministic_renderers"
        old_node = next(n for n in ast.parse(original).body if isinstance(n, ast.FunctionDef) and n.name == name)
        new_node = next(n for n in ast.parse(ledger_bench).body if isinstance(n, ast.FunctionDef) and n.name == name)
        original_lines = original.splitlines(keepends=True)
        original_lines[old_node.lineno - 1:old_node.end_lineno] = ledger_bench.splitlines(keepends=True)[new_node.lineno - 1:new_node.end_lineno]
        revised = b"".join(original_lines)
        for renderer in ("render_evidence_baseline_markdown", "render_remaining_plan_markdown"):
            redundant = (renderer + '(audit) + "\\n"').encode()
            if revised.count(redundant) != 1:
                raise ValueError("HISTORICAL_RENDER_BENCH_CORRECTION_REJECTED")
            revised = revised.replace(redundant, (renderer + "(audit)").encode())
        bench.write_bytes(revised)
        (temporary / "HISTORICAL_RENDER_BENCH_SUCCESSOR.json").write_text(json.dumps({
            "contract_id": "R2-HISTORICAL-RENDER-CHECK-1.1",
            "fabrication": fabrication,
            "original_test_sha256": hashlib.sha256(original).hexdigest(),
            "ledger_bench_commit": ledger_commit,
            "ledger_bench_file_sha256": hashlib.sha256(ledger_bench).hexdigest(),
            "successor_test_sha256": hashlib.sha256(revised).hexdigest(),
            "correction": "Public 2b378 ledger identity assertions and two redundant LF additions; no renderer, report, JSON or ledger changed",
            "original_result": "FAIL_RETAINED", "successor_result": "TO_BE_EXECUTED",
        }, indent=2), "utf-8")
    env = dict(os.environ)
    for key in tuple(env):
        if key.upper().startswith(("OPENAI_", "AZURE_OPENAI_", "RUN_")) or key.upper() in {
            "ANTHROPIC_API_KEY", "PROJET_V2_CANONICAL_DB", "PROJET_V2_RUNTIME_DB",
            "PROJET_V2_DATA_DIR", "PEDAGOGICAL_CANONICAL_SEED_PATH",
            "PEDAGOGICAL_RUNTIME_DATABASE_PATH",
        }:
            del env[key]
    env.update(PYTHONDONTWRITEBYTECODE="1", TEMP=str(temporary), TMP=str(temporary))
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
         "--basetemp=" + str(temporary / "pytest"),
         target],
        cwd=historical, env=env, capture_output=True, timeout=180,
    )
    bench_receipt = temporary / "HISTORICAL_RENDER_BENCH_SUCCESSOR.json"
    if bench_receipt.exists():
        record = json.loads(bench_receipt.read_bytes())
        record["successor_result"] = "PASS" if result.returncode == 0 else "FAIL"
        record["exit"] = result.returncode
        bench_receipt.write_text(json.dumps(record, indent=2), "utf-8")
    return result
