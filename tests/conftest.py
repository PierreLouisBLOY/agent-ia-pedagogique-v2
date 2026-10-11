"""Keep pytest scratch databases and nested test repositories outside this checkout."""

import sys
import tempfile
from pathlib import Path

import pytest

from tests.support.repository_hygiene import require_external_temp_root


def pytest_configure(config: pytest.Config) -> None:
    candidate = config.option.basetemp or tempfile.gettempdir()
    try:
        require_external_temp_root(Path(candidate), Path(__file__).resolve().parents[1])
    except ValueError as error:
        raise pytest.UsageError(str(error)) from None


@pytest.fixture(scope="session")
def historical_r5_sources(tmp_path_factory: pytest.TempPathFactory) -> Path:
    from tests.support.historical_guard_fixture import materialize_historical_guard_sources

    return materialize_historical_guard_sources(tmp_path_factory.mktemp("historical-r5") / "source")


@pytest.fixture
def historical_guard_sources(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch,
                             historical_r5_sources: Path) -> None:
    """Explicitly selected archival assertions only; behaviour tests remain current."""
    _bind_historical_sources(request, monkeypatch, historical_r5_sources)


def _bind_historical_sources(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch,
                             root: Path) -> None:
    from types import FunctionType

    from tests.support.historical_git_successor import assert_historical_git_state

    if hasattr(request.module, "ROOT"):
        monkeypatch.setattr(request.module, "ROOT", root)
    for name, module in tuple(sys.modules.items()):
        if name.startswith("tests.support.r") and module is not None and hasattr(module, "ROOT"):
            monkeypatch.setattr(module, "ROOT", root)
        if name.startswith("tests.support.r") and module is not None and hasattr(module, "assert_git_state"):
            monkeypatch.setattr(module, "assert_git_state", assert_historical_git_state)
    for name, value in tuple(vars(request.module).items()):
        if (isinstance(value, FunctionType) and value.__name__ == "assert_git_state"
                and value.__module__.startswith("tests.support.r3_")):
            monkeypatch.setattr(request.module, name, assert_historical_git_state)
