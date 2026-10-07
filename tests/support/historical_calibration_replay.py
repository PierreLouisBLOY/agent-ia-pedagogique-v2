"""Execute the original report assertions on authenticated historical Git code."""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

from tests.support.historical_guard_fixture import materialize_historical_guard_sources


def replay_historical_report(root: Path, temporary: Path) -> subprocess.CompletedProcess[bytes]:
    source = root / "artifacts/calibration"
    files = sorted(p for p in source.rglob("*") if p.is_file())
    if len(files) != 321:
        raise ValueError("HISTORICAL_CALIBRATION_321_PRIVATE_FILES_REQUIRED")
    historical = materialize_historical_guard_sources(temporary / "historical")
    for path in files:
        if path.is_symlink() or path.is_junction():
            raise ValueError("HISTORICAL_CALIBRATION_LINK_REJECTED")
        target = historical / path.relative_to(root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        if hashlib.sha256(path.read_bytes()).digest() != hashlib.sha256(target.read_bytes()).digest():
            raise ValueError("HISTORICAL_CALIBRATION_COPY_MISMATCH")
    env = dict(os.environ)
    for key in tuple(env):
        if key.upper().startswith(("OPENAI_", "AZURE_OPENAI_", "RUN_")) or key.upper() in {
            "ANTHROPIC_API_KEY", "PROJET_V2_CANONICAL_DB", "PROJET_V2_RUNTIME_DB",
            "PROJET_V2_DATA_DIR", "PEDAGOGICAL_CANONICAL_SEED_PATH",
            "PEDAGOGICAL_RUNTIME_DATABASE_PATH",
        }:
            del env[key]
    env.update(PYTHONDONTWRITEBYTECODE="1", TEMP=str(temporary), TMP=str(temporary))
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
         "--basetemp=" + str(temporary / "pytest"),
         "tests/unit/test_pedagogical_calibration_r4_r3_r3.py::"
         "test_reports_are_safe_float_free_and_byte_reproducible"],
        cwd=historical, env=env, capture_output=True, timeout=180,
    )
