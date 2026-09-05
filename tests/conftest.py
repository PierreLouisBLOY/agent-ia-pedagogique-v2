"""Keep pytest scratch databases and nested test repositories outside this checkout."""

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
