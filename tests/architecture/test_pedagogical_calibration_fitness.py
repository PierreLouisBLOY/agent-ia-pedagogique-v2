from __future__ import annotations

import ast
import hashlib
from pathlib import Path

from tests.calibration.pedagogical.call_plan import RAW_OUTPUT_DIRECTORY

ROOT = Path(__file__).resolve().parents[2]
CALIBRATION = ROOT / "tests" / "calibration" / "pedagogical"
BACKEND = ROOT / "backend"
HARNESS = ROOT / "evaluation_harness"

_FROZEN_OWNER_HASHES = {
    "tests/e2e/core/catalog.py": "0f217a05bceb8dddb8a5b93b1f55738abaf65b62251138a10ad6653b2869dd06",
    "tests/e2e/core/expectations.py": "191c1d8c33353258dd959f5154efd8befa6c857cbddfd476c4cf2e6a1f56179d",
    "evaluation_harness/contracts/scoring.py": "706eaecd81f7fcbe2d7a851f00db4012f8932b9439e12386ba6688339d516bc1",
    "tests/providers/anthropic/mapping.py": "74f473ab60764978aa26b53309c89cf6588058d7ce3480f881798b5279057be7",
    "tests/providers/anthropic/scorer.py": "a604da2e6c1ca20850c87328046c9d9985e9b1a79442875b6e2a4c657086fbcf",
    "backend/adapters/outbound/generation/openai/adapter.py": "9357224fa7b4c77e4dd0cd7184491597138dd4247bbb5ad75f346c22fbb66be1",
    "backend/adapters/outbound/review/openai/adapter.py": "588111262f21075f8731e9d7513e5a93d4f1ed1bf37009f197922c5ccfabda9e",
    "backend/agent_runtime/registry/capabilities.py": "4467bc96d8e8df81ee8a5a66b24853d43b3ca569972fc55a3552c9dfea8bb5bf",
    "backend/agent_runtime/orchestration/workflows/catalog.py": "819c680e710896c72f0019d2f75481daed4abc60bbfe67696c65ea5012dbbcd7",
}


def _python_files(owner: Path) -> tuple[Path, ...]:
    return tuple(path for path in owner.rglob("*.py") if "__pycache__" not in path.parts)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def test_runtime_and_harness_cannot_import_test_only_calibration() -> None:
    violations = tuple(
        path.relative_to(ROOT).as_posix()
        for path in (*_python_files(BACKEND), *_python_files(HARNESS))
        if any(
            name == "tests.calibration" or name.startswith("tests.calibration.")
            for name in _imports(path)
        )
    )
    assert violations == ()


def test_golden_harness_adapters_and_registries_remain_byte_exact() -> None:
    actual = {
        relative: hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        for relative in _FROZEN_OWNER_HASHES
    }
    assert actual == _FROZEN_OWNER_HASHES


def test_calibration_owner_has_no_provider_sdk_or_runtime_recovery_import() -> None:
    forbidden = (
        "openai",
        "anthropic",
        "backend.agent_runtime.recovery",
        "backend.agent_runtime.registry",
        "backend.adapters.outbound.semantic",
    )
    violations = tuple(
        path.relative_to(ROOT).as_posix()
        for path in _python_files(CALIBRATION)
        if any(
            name == prefix or name.startswith(f"{prefix}.")
            for name in _imports(path)
            for prefix in forbidden
        )
    )
    assert violations == ()


def test_raw_live_outputs_are_outside_source_owners_and_git_ignored() -> None:
    assert RAW_OUTPUT_DIRECTORY.startswith("artifacts/")
    assert "/artifacts/" in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert (ROOT / "artifacts").resolve() in (ROOT / RAW_OUTPUT_DIRECTORY).resolve().parents


def test_calibration_contains_no_release_threshold_or_direct_provider_sdk_call() -> None:
    source = "\n".join(path.read_text(encoding="utf-8") for path in _python_files(CALIBRATION))
    assert '"release_threshold":' not in source
    assert "CAP-T04" not in source
    assert ".responses.create(" not in source
    assert ".messages.create(" not in source
    assert "embedding" not in source.casefold()


def test_r3a_preparation_constructs_no_provider_transport_or_live_executor() -> None:
    source = (CALIBRATION / "r3a_plan.py").read_text(encoding="utf-8")

    assert "RealCalibrationExecutor" not in source
    assert "EnvironmentProviderSecretResolver" not in source
    assert "TransportFactory" not in source
    assert "OPENAI_API_KEY" not in source
    assert "ANTHROPIC_API_KEY" not in source
    assert ".create(" not in source
    assert ".responses.create(" not in source
    assert ".messages.create(" not in source
