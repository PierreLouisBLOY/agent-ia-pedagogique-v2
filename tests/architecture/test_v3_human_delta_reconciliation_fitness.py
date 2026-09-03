from __future__ import annotations

import ast
import subprocess
from pathlib import Path

from tests.support.historical_hash_freeze import assert_current_historical_hashes

ROOT = Path(__file__).resolve().parents[2]
OWNER = (
    ROOT
    / "tests/calibration/pedagogical/v3_human_delta_reconciliation.py"
)
LOCAL_INPUT = (
    "artifacts/calibration/12.16-g2-anchor-corpus-v3/"
    "completed_delta_prevalidation.md"
)
LOCAL_KEY = (
    "artifacts/calibration/12.16-g2-anchor-corpus-v3/"
    "human_delta_prevalidation_reconciliation.json"
)
LOCAL_RESULT = (
    "artifacts/calibration/12.16-g2-anchor-corpus-v3/"
    "human_delta_prevalidation_reconciliation_result.json"
)
TRACKED_REPORT = (
    "docs/development/"
    "PHASE_12_16_G2_V3_HUMAN_DELTA_PREVALIDATION_RECONCILIATION.md"
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


def test_v3_human_reconciliation_is_offline_and_runtime_route_neutral() -> None:
    imports = _imports(OWNER)
    assert not any(name == "backend" or name.startswith("backend.") for name in imports)
    assert not any(name == "openai" or name.startswith("openai.") for name in imports)
    assert not any(name == "anthropic" or name.startswith("anthropic.") for name in imports)
    source = OWNER.read_text(encoding="utf-8")
    for forbidden in (
        "EnvironmentProviderSecretResolver",
        "TransportFactory",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "os.environ",
        ".responses.create(",
        ".messages.create(",
    ):
        assert forbidden not in source
    assert '"openai_calls": 0' in source
    assert '"anthropic_calls": 0' in source
    assert '"RUNTIME_ROUTE_CHANGE": "NONE"' in source
    assert '"RELEASE_THRESHOLD_ADOPTION": "NOT_ALLOWED"' in source


def test_v3_human_inputs_and_result_are_ignored_but_report_is_tracked() -> None:
    for relative_path in (LOCAL_INPUT, LOCAL_KEY, LOCAL_RESULT):
        ignored = subprocess.run(
            ["git", "check-ignore", "--quiet", relative_path],
            cwd=ROOT,
            check=False,
        )
        assert ignored.returncode == 0
    report = subprocess.run(
        ["git", "check-ignore", "--quiet", TRACKED_REPORT],
        cwd=ROOT,
        check=False,
    )
    assert report.returncode == 1


def test_v1_v2_v3_corpora_and_historical_proofs_remain_byte_exact() -> None:
    assert_current_historical_hashes(
        ROOT,
        (
            "tests/calibration/pedagogical/catalog.py",
            "tests/calibration/pedagogical/anchor_corpus_v2.py",
            "tests/calibration/pedagogical/anchor_corpus_v3.py",
            "docs/development/PHASE_12_16_G2_V2_HUMAN_PREVALIDATION_PACKET.md",
            "docs/development/PHASE_12_16_G2_V2_HUMAN_PREVALIDATION_RECONCILIATION.md",
            "architecture/adr/ADR-P12-065-versioned-human-prevalidated-anchor-corpus.md",
            "architecture/adr/ADR-P12-066-strong-only-deliverability-calibration-semantics.md",
            "docs/development/PHASE_12_16_G2_ANCHOR_CORPUS_V3_STRONG_ONLY_REMEDIATION_BASELINE.md",
            "docs/development/PHASE_12_16_G2_ANCHOR_CORPUS_V3_CRITERION_DEFECT_ALIGNMENT_MATRIX.md",
            "docs/development/PHASE_12_16_G2_V3_HUMAN_DELTA_PREVALIDATION_PACKET.md",
        ),
    )
