from __future__ import annotations

import ast
import hashlib
import subprocess
from pathlib import Path

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
    frozen = {
        "tests/calibration/pedagogical/catalog.py": (
            "53da2068fa6585086fe955b633a1d8e173cf770c8b5cb5e71f6cc8cc474e7317"
        ),
        "tests/calibration/pedagogical/anchor_corpus_v2.py": (
            "bd0c5eff43be20b4f578b99321e076471804f8a3e0e197858b08a3701800be76"
        ),
        "tests/calibration/pedagogical/anchor_corpus_v3.py": (
            "cf90457393b02dca233cd4bc5d5c73e4a63a091591cb448d19b30b68e6bdc241"
        ),
        "docs/development/PHASE_12_16_G2_V2_HUMAN_PREVALIDATION_PACKET.md": (
            "81bca8cc998e866c7b08f22af65c009714b5e4d5068fb0c19b2ba6598a7d48c9"
        ),
        "docs/development/PHASE_12_16_G2_V2_HUMAN_PREVALIDATION_RECONCILIATION.md": (
            "3ae6d71e47da917bcb904e5534ea4ec893d37887f4eba1b98c37c4ab4b0392fd"
        ),
        "architecture/adr/ADR-P12-065-versioned-human-prevalidated-anchor-corpus.md": (
            "9541f927ff631bed44d382812ef3a0ed9e83f520c73b320f0494f2aaadd6d872"
        ),
        "architecture/adr/ADR-P12-066-strong-only-deliverability-calibration-semantics.md": (
            "aaba7d443ef17d8e557ccbceb87961758901b12591a6f368bc38ad05fda8d3ea"
        ),
        "docs/development/PHASE_12_16_G2_ANCHOR_CORPUS_V3_STRONG_ONLY_REMEDIATION_BASELINE.md": (
            "216a2f9f938557e116b8306604decdafbe51a9f0e2fab235e560a7e719ba876c"
        ),
        "docs/development/PHASE_12_16_G2_ANCHOR_CORPUS_V3_CRITERION_DEFECT_ALIGNMENT_MATRIX.md": (
            "cc50a5295d2447f00805c88f25223c02bbc0fbe9328eaccc9e69217f93eefa72"
        ),
        "docs/development/PHASE_12_16_G2_V3_HUMAN_DELTA_PREVALIDATION_PACKET.md": (
            "0cd536bdbdca68cead009bad9ae09a1d11c514ff0774c34fbe4f14f5ae4d6477"
        ),
    }
    actual = {
        relative: hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        for relative in frozen
    }
    assert actual == frozen
