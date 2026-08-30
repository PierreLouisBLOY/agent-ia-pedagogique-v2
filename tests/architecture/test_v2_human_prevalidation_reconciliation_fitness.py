from __future__ import annotations

import ast
import hashlib
import subprocess
from pathlib import Path

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
    frozen = {
        "tests/calibration/pedagogical/catalog.py": (
            "53da2068fa6585086fe955b633a1d8e173cf770c8b5cb5e71f6cc8cc474e7317"
        ),
        "docs/development/PHASE_12_16_G2_FINAL_CALIBRATION_ANALYSIS_REPORT.json": (
            "f08fad954918f82e690a539b35f02a88ce3d08818a95f6c18df982f4c3d7c272"
        ),
        "docs/development/PHASE_12_16_G2_HUMAN_REVIEW_RECONCILIATION_REPORT.json": (
            "568e810af5a3cee9e46a56696300066db421d2dfc330f721718318be85a8b6cd"
        ),
        "docs/development/PHASE_12_16_G2_V2_HUMAN_PREVALIDATION_PACKET.md": (
            "81bca8cc998e866c7b08f22af65c009714b5e4d5068fb0c19b2ba6598a7d48c9"
        ),
        "tests/calibration/pedagogical/anchor_corpus_v2.py": (
            "bd0c5eff43be20b4f578b99321e076471804f8a3e0e197858b08a3701800be76"
        ),
    }
    actual = {
        relative: hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        for relative in frozen
    }
    assert actual == frozen
