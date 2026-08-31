from __future__ import annotations

import ast
import hashlib
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OWNER = ROOT / "tests/calibration/pedagogical/anchor_corpus_v4.py"
ADR = (
    ROOT
    / "architecture/adr/"
    "ADR-P12-067-disposition-first-pairwise-human-calibration.md"
)
BASELINE = (
    ROOT
    / "docs/development/"
    "PHASE_12_16_G2_V4_DISPOSITION_FIRST_REMEDIATION_BASELINE.md"
)
LOCAL_KEY = (
    "artifacts/calibration/12.16-g2-anchor-corpus-v4/"
    "human_disposition_pairwise_reconciliation.json"
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


def test_v4_owner_is_test_only_offline_and_runtime_route_neutral() -> None:
    imports = _imports(OWNER)
    assert not any(name == "backend" or name.startswith("backend.") for name in imports)
    assert not any(name == "openai" or name.startswith("openai.") for name in imports)
    assert not any(name == "anthropic" or name.startswith("anthropic.") for name in imports)
    source = OWNER.read_text(encoding="utf-8")
    forbidden = (
        "EnvironmentProviderSecretResolver",
        "TransportFactory",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "os.environ",
        ".responses.create(",
        ".messages.create(",
    )
    assert all(marker not in source for marker in forbidden)
    baseline = BASELINE.read_text(encoding="utf-8")
    assert "PROVIDER_CALLS : `0`; PROVIDER_COST : `0`" in baseline
    assert "RUNTIME_ROUTE_CHANGE : `NONE`" in baseline
    assert "RELEASE_THRESHOLD_ADOPTION : `NOT_ALLOWED`" in baseline
    assert "GLOBAL_SUITE_RUN : `NO`" in baseline


def test_v4_local_key_is_ignored_and_owner_documents_are_not() -> None:
    ignored = subprocess.run(
        ["git", "check-ignore", "--quiet", LOCAL_KEY],
        cwd=ROOT,
        check=False,
    )
    assert ignored.returncode == 0
    tracked_outputs = (
        "architecture/adr/ADR-P12-067-disposition-first-pairwise-human-calibration.md",
        "docs/development/PHASE_12_16_G2_V4_NEGATIVE_CONTROL_REMEDIATION_MATRIX.md",
        "docs/development/PHASE_12_16_G2_V4_HUMAN_DISPOSITION_PAIRWISE_PACKET.md",
        "docs/development/PHASE_12_16_G2_V4_DISPOSITION_FIRST_REMEDIATION_BASELINE.md",
    )
    for relative_path in tracked_outputs:
        result = subprocess.run(
            ["git", "check-ignore", "--quiet", relative_path],
            cwd=ROOT,
            check=False,
        )
        assert result.returncode == 1


def test_v1_v2_v3_proofs_remain_byte_exact() -> None:
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
        "docs/development/PHASE_12_16_G2_V3_HUMAN_DELTA_PREVALIDATION_RECONCILIATION.md": (
            "4268c70543a8cf26274db6fc2c9b334ee71473a9ef8f960f0e3109c64b7dffc9"
        ),
        "docs/development/PHASE_12_16_G2_ANCHOR_CORPUS_V3_STRONG_ONLY_REMEDIATION_BASELINE.md": (
            "216a2f9f938557e116b8306604decdafbe51a9f0e2fab235e560a7e719ba876c"
        ),
        "architecture/adr/ADR-P12-066-strong-only-deliverability-calibration-semantics.md": (
            "aaba7d443ef17d8e557ccbceb87961758901b12591a6f368bc38ad05fda8d3ea"
        ),
    }
    actual = {
        relative: hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        for relative in frozen
    }
    assert actual == frozen


def test_adr_p12_067_records_durable_separation_and_non_authority() -> None:
    source = ADR.read_text(encoding="utf-8")
    assert "Statut : Accepté" in source
    assert "STRONG_ONLY" in source
    assert "DELIVERY_CANDIDATE" in source
    assert "NON_DELIVERABLE_NEGATIVE_CONTROL" in source
    assert "comparaison pairwise aveugle" in source
    assert "diagnostic secondaire" in source
    assert "secondaire et non bloquant" in source
    assert "n'obtient aucune autorité runtime" in source
    assert "aucune route fournisseur" in source
    assert "v1, v2 et v3 restent byte-exact immuables" in source
