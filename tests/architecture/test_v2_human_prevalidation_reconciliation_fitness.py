from __future__ import annotations

import ast
import subprocess
from pathlib import Path

from tests.support.historical_hash_freeze import assert_current_historical_hashes

ROOT = Path(__file__).resolve().parents[2]
OWNER = (
    ROOT
    / "tests/calibration/pedagogical/v2_human_prevalidation_reconciliation.py"
)
REPORT = (
    ROOT
    / "docs/development/"
    "PHASE_12_16_G2_V2_HUMAN_PREVALIDATION_RECONCILIATION.md"
)
LOCAL_RESULT = (
    "artifacts/calibration/12.16-g2-anchor-corpus-v2/"
    "human_prevalidation_reconciliation_result.json"
)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def test_v2_reconciliation_is_test_only_offline_and_route_neutral() -> None:
    imports = _imports(OWNER)
    assert not any(name == "backend" or name.startswith("backend.") for name in imports)
    assert not any(name == "openai" or name.startswith("openai.") for name in imports)
    assert not any(name == "anthropic" or name.startswith("anthropic.") for name in imports)
    source = OWNER.read_text(encoding="utf-8")
    assert "EnvironmentProviderSecretResolver" not in source
    assert "TransportFactory" not in source
    assert "OPENAI_API_KEY" not in source
    assert "ANTHROPIC_API_KEY" not in source
    assert "os.environ" not in source
    assert ".responses.create(" not in source
    assert ".messages.create(" not in source
    assert '"openai_calls": 0' in source
    assert '"anthropic_calls": 0' in source
    assert '"PROVIDER_ROUTE_CHANGE": "NONE"' in source


def test_v2_reconciliation_artifacts_follow_tracking_policy() -> None:
    assert REPORT.is_file()
    report_ignore = subprocess.run(
        ["git", "check-ignore", "--quiet", REPORT.relative_to(ROOT).as_posix()],
        cwd=ROOT,
        check=False,
    )
    result_ignore = subprocess.run(
        ["git", "check-ignore", "--quiet", LOCAL_RESULT],
        cwd=ROOT,
        check=False,
    )
    assert report_ignore.returncode == 1
    assert result_ignore.returncode == 0


def test_v2_corpus_packet_and_v1_proofs_remain_byte_exact() -> None:
    assert_current_historical_hashes(
        ROOT,
        (
            "tests/calibration/pedagogical/catalog.py",
            "docs/development/PHASE_12_16_G2_FINAL_CALIBRATION_ANALYSIS_REPORT.json",
            "docs/development/PHASE_12_16_G2_HUMAN_REVIEW_RECONCILIATION_REPORT.json",
            "docs/development/PHASE_12_16_G2_V2_HUMAN_PREVALIDATION_PACKET.md",
            "tests/calibration/pedagogical/anchor_corpus_v2.py",
        ),
    )
