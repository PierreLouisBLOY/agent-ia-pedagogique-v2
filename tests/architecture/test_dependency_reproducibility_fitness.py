from __future__ import annotations

import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).parents[2]
LOCK_ROOT = ROOT / "requirements" / "lock"
PYPROJECT = ROOT / "pyproject.toml"
DEV_INPUT = ROOT / "requirements-dev.txt"
LOCK_NAMES = (
    "runtime-py312-win.txt",
    "calibration-py312-win.txt",
    "dev-py312-win.txt",
)
REQUIREMENT = re.compile(
    r"^(?P<name>[A-Za-z0-9_.-]+)==(?P<version>[A-Za-z0-9_.+-]+) "
    r"--hash=sha256:(?P<hash>[0-9a-f]{64})$"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _normalise(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _lock(name: str) -> tuple[str, dict[str, str]]:
    source = (LOCK_ROOT / name).read_text(encoding="utf-8")
    requirements: dict[str, str] = {}
    options: list[str] = []
    for line in source.splitlines():
        if not line or line.startswith("#"):
            continue
        if line.startswith("--"):
            options.append(line)
            continue
        match = REQUIREMENT.fullmatch(line)
        assert match is not None, f"unhashed or unpinned requirement in {name}"
        package = _normalise(match["name"])
        assert package not in requirements
        requirements[package] = match["version"]
    assert options == ["--only-binary=:all:"]
    assert "http://" not in source and "https://" not in source
    assert "git+" not in source and "@ file:" not in source
    return source, requirements


def test_exact_three_platform_locks_are_present_and_fully_hashed() -> None:
    assert tuple(sorted(path.name for path in LOCK_ROOT.glob("*.txt"))) == tuple(
        sorted(LOCK_NAMES)
    )
    for name in LOCK_NAMES:
        source, requirements = _lock(name)
        assert requirements
        for marker in (
            "# target-python: 3.12",
            "# target-platform: win_amd64",
            "# target-implementation: cp",
            "# target-abi: cp312",
            "# wheelhouse-manifest-sha256:",
        ):
            assert marker in source


def test_lock_inputs_and_declared_bounds_have_not_drifted() -> None:
    pyproject_hash = _sha256(PYPROJECT)
    dev_hash = _sha256(DEV_INPUT)
    assert pyproject_hash == "d3aaf2cc2abd2ad35a1112c3bebc998ffbe0925943adcaad46018c7282fcacbc"
    assert dev_hash == "a41e6dd0b460173f10812c1cebaf65d013ceac9c6893ebb242a5796ad7461123"

    pyproject = PYPROJECT.read_text(encoding="utf-8")
    assert 'dependencies = ["openai>=3.5,<4"]' in pyproject
    assert 'calibration = ["anthropic>=1.2,<2"]' in pyproject
    assert DEV_INPUT.read_text(encoding="utf-8").splitlines() == [
        "pytest==9.1.1",
        "ruff==0.16.4",
        "mypy==2.3.1",
    ]
    for name in LOCK_NAMES:
        source, _ = _lock(name)
        assert f"# source-pyproject-sha256: {pyproject_hash}" in source
    dev_source, _ = _lock("dev-py312-win.txt")
    assert f"# source-requirements-dev-sha256: {dev_hash}" in dev_source


def test_runtime_calibration_and_dev_sets_are_partitioned() -> None:
    _, runtime = _lock("runtime-py312-win.txt")
    _, calibration = _lock("calibration-py312-win.txt")
    _, dev = _lock("dev-py312-win.txt")

    assert len(runtime) == 14
    assert len(calibration) == 16
    assert len(dev) == 26
    assert set(runtime) < set(calibration)
    assert set(runtime) < set(dev)
    assert set(calibration) - set(runtime) == {"anthropic", "docstring-parser"}
    assert {"pytest", "ruff", "mypy"} <= set(dev)
    assert "anthropic" not in runtime and "anthropic" not in dev
    assert runtime["openai"].startswith("3.")
    assert calibration["anthropic"].startswith("1.")


def test_environment_documentation_matches_lock_and_alias_policy() -> None:
    environment = (ROOT / "docs" / "development" / "ENVIRONMENT.md").read_text(
        encoding="utf-8"
    )
    for name in LOCK_NAMES:
        assert f"requirements/lock/{name}" in environment
    assert "LEGACY_SETTING_FORBIDDEN" in environment
    assert "--require-hashes --no-deps" in environment
