from __future__ import annotations

import json
import shutil
import socket
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "tools/launch-local.ps1"
POWERSHELL = shutil.which("powershell.exe") or shutil.which("powershell")


def _run(config: Path) -> subprocess.CompletedProcess[str]:
    if POWERSHELL is None:
        pytest.fail("WINDOWS_POWERSHELL_REQUIRED")
    return subprocess.run(
        [
            POWERSHELL,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(LAUNCHER),
            "-ConfigPath",
            str(config),
        ],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )


def _config(path: Path, port: int) -> Path:
    value = {
        "runtime_path": str(path / "runtime.sqlite"),
        "data_root": str(path),
        "runtime_sha256": "0" * 64,
        "port": port,
        "python_path": sys.executable,
    }
    config = path / "launcher.json"
    config.write_text(json.dumps(value), encoding="utf-8")
    return config


def test_missing_config_fails_with_copy_instruction(tmp_path: Path) -> None:
    result = _run(tmp_path / "missing.json")
    assert result.returncode == 2
    assert "CONFIG_NOT_FOUND" in result.stderr


def test_invalid_config_fails_before_startup(tmp_path: Path) -> None:
    config = tmp_path / "launcher.json"
    config.write_text("{}", encoding="utf-8")
    result = _run(config)
    assert result.returncode == 2
    assert "CONFIG_INVALID" in result.stderr


def test_occupied_loopback_port_fails_before_runtime_startup(tmp_path: Path) -> None:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = int(listener.getsockname()[1])
        result = _run(_config(tmp_path, port))
    assert result.returncode == 3
    assert "PORT_IN_USE" in result.stderr


@pytest.mark.parametrize("runtime_exists", [False, True])
def test_unavailable_or_mismatched_runtime_fails_closed(
    tmp_path: Path, runtime_exists: bool
) -> None:
    config = _config(tmp_path, 18765)
    value = json.loads(config.read_text(encoding="utf-8"))
    if runtime_exists:
        Path(value["runtime_path"]).write_bytes(b"test-only runtime identity mismatch")
    config.write_text(json.dumps(value), encoding="utf-8")

    result = _run(config)

    assert result.returncode == 1
    assert "LOCAL_READ15_STARTUP_REJECTED" in result.stdout
    assert "provider" not in result.stdout.casefold()
