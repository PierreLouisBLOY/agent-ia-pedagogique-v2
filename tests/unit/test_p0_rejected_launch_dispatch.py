"""Explicit normal launcher selection; doubles qualify routing only."""

import json
import socket
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.adapters.inbound.cli import local_browser
from backend.infrastructure.composition.factories import p0_rejected_profile as F
from tests.unit.test_p0_normal_cli import arguments


def selected(kind="profile", mode=None):
    args = [
        *arguments(),
        "--saved-root",
        r"C:\SYNTHETIC_UNOPENED_SAVED",
        "--word-profile",
        "product-v7",
        "--p0-rejected-" + ("profile" if kind == "profile" else "inspection-plan"),
        r"C:\SYNTHETIC_UNOPENED_SELECTOR.json",
        "--p0-rejected-adoption",
        r"C:\SYNTHETIC_UNOPENED_ADOPTION.json",
    ]
    if mode is not None:
        args += ["--p0-rejected-mode", mode]
    return args


@pytest.mark.parametrize(
    "mutation",
    [
        "adoption_orphan",
        "mode_orphan",
        "profile_orphan",
        "plan_orphan",
        "both",
        "legacy",
        "relative",
        "unc",
        "env",
        "plan_default",
        "plan_off",
        "profile_inspect",
        "saved_only",
        "create_saved",
        "conversation",
        "review",
        "live",
        "r5_scope",
        "r5_authorization",
        "missing_runtime",
        "missing_library",
        "wrong_word",
    ],
)
def test_cli_refuses_before_business_loader(monkeypatch, capsys, mutation):
    args = selected()
    if mutation.endswith("_orphan"):
        args = (
            arguments()
            + {
                "adoption_orphan": ["--p0-rejected-adoption", r"C:\UNOPENED.json"],
                "mode_orphan": ["--p0-rejected-mode", "off"],
                "profile_orphan": ["--p0-rejected-profile", r"C:\UNOPENED.json"],
                "plan_orphan": ["--p0-rejected-inspection-plan", r"C:\UNOPENED.json"],
            }[mutation]
        )
    elif mutation in {"relative", "unc", "env"}:
        args[args.index("--p0-rejected-profile") + 1] = {
            "relative": "relative.json",
            "unc": r"\\host\share\profile.json",
            "env": r"C:\%TEMP%\profile.json",
        }[mutation]
    elif mutation in {"plan_default", "plan_off"}:
        args = selected("plan", None if mutation == "plan_default" else "off")
    elif mutation == "profile_inspect":
        args = selected(mode="inspect-only")
    elif mutation.startswith("missing_"):
        key = "--runtime" if mutation == "missing_runtime" else "--saved-root"
        index = args.index(key)
        del args[index : index + 2]
    elif mutation == "wrong_word":
        args[args.index("--word-profile") + 1] = "diffusion-v5"
    else:
        args += {
            "both": ["--p0-rejected-inspection-plan", r"C:\UNOPENED.json"],
            "legacy": ["--p0-normal-profile", r"C:\UNOPENED.json"],
            "saved_only": ["--saved-only"],
            "create_saved": ["--create-saved"],
            "conversation": ["--enable-conversation"],
            "review": ["--enable-review-modify"],
            "live": ["--live-authorization", "UNOPENED"],
            "r5_scope": ["--r5-scope", "UNOPENED"],
            "r5_authorization": ["--r5-authorization", "UNOPENED"],
        }[mutation]

    def forbidden(*args, **kwargs):
        pytest.fail("No profile, runtime, SDK or server before selection validation")

    monkeypatch.setattr(F, "P0RejectedProductComposition", forbidden)
    monkeypatch.setattr(F, "P0RejectedInspectionComposition", forbidden)
    monkeypatch.setattr(local_browser, "build_local_read15", forbidden)
    assert local_browser.main(args) == 1
    assert capsys.readouterr().out == "P0_REJECTED_EXPLICIT_SELECTION_REQUIRED\n"


@pytest.mark.parametrize(
    "kind,mode",
    [("profile", None), ("profile", "off"), ("profile", "on"), ("plan", "inspect-only")],
)
@pytest.mark.parametrize("failure", [None, "startup", "serve", "interrupt"])
def test_cli_explicit_routing_and_lifecycle(monkeypatch, kind, mode, failure):
    calls = []
    composition = SimpleNamespace(
        generation=None, bind=lambda *args: None, close=lambda: calls.append("product-close")
    )

    def construct(**kwargs):
        assert kwargs["adoption_path"] == Path(r"C:\SYNTHETIC_UNOPENED_ADOPTION.json")
        if kind == "profile":
            assert kwargs["mode"] == (mode or "off")
        else:
            assert "mode" not in kwargs and "plan_path" in kwargs
        calls.append("product-create")
        return composition

    monkeypatch.setattr(
        F,
        "P0RejectedProductComposition" if kind == "profile" else "P0RejectedInspectionComposition",
        construct,
    )

    def serve():
        if failure == "serve":
            raise RuntimeError("Synthetic server failure")
        if failure == "interrupt":
            raise KeyboardInterrupt

    def build(*args, **kwargs):
        assert kwargs["p0_generation"] is None and kwargs["p0_product_binder"] is composition.bind
        if failure == "startup":
            raise RuntimeError("Synthetic startup failure")
        return SimpleNamespace(
            url="http://127.0.0.1:9123/",
            serve_forever=serve,
            close=lambda: calls.append("server-close"),
        )

    monkeypatch.setattr(local_browser, "build_local_read15", build)
    assert local_browser.main(selected(kind, mode)) == (1 if failure in {"startup", "serve"} else 0)
    assert calls.count("product-close") == 1
    assert ("server-close" in calls) == (failure != "startup")


def test_bad_enum_is_argparse_refusal():
    with pytest.raises(SystemExit) as error:
        local_browser.main(selected(mode="ON"))
    assert error.value.code == 2


def run_launcher(config, tmp_path):
    path = tmp_path / "SYNTHETIC-launcher.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-File",
            str(Path(__file__).resolve().parents[2] / "tools/launch-local.ps1"),
            "-ConfigPath",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def launcher_config(tmp_path):
    return {
        "runtime_path": str(tmp_path / "UNOPENED-runtime"),
        "data_root": str(tmp_path),
        "runtime_sha256": "a" * 64,
        "port": 9123,
        "saved_root": str(tmp_path / "UNOPENED-saved"),
        "word_profile": "product-v7",
        "p0_rejected_profile": str(tmp_path / "UNOPENED-profile.json"),
        "p0_rejected_adoption": str(tmp_path / "UNOPENED-adoption.json"),
    }


@pytest.mark.parametrize(
    "mutation",
    [
        "adoption_orphan",
        "mode_orphan",
        "profile_orphan",
        "plan_orphan",
        "both",
        "legacy",
        "relative",
        "unc",
        "env",
        "wrong_case",
        "mode_case",
        "mode_type",
        "plan_default",
        "profile_inspect",
        "saved_only",
        "create_saved",
        "conversation",
        "review",
        "live",
        "r5_scope",
        "r5_authorization",
        "missing_saved",
        "word",
    ],
)
def test_actual_powershell_selection_refuses_before_port_or_python(tmp_path, mutation):
    config = launcher_config(tmp_path)
    config["python_path"] = str(tmp_path / "MUST_NOT_EXECUTE.exe")
    if mutation.endswith("_orphan"):
        for key in ("p0_rejected_profile", "p0_rejected_adoption"):
            config.pop(key)
        key = {
            "adoption_orphan": "p0_rejected_adoption",
            "mode_orphan": "p0_rejected_mode",
            "profile_orphan": "p0_rejected_profile",
            "plan_orphan": "p0_rejected_inspection_plan",
        }[mutation]
        config[key] = "off" if key.endswith("mode") else str(tmp_path / "UNOPENED.json")
    elif mutation in {"relative", "unc", "env"}:
        config["p0_rejected_profile"] = {
            "relative": "relative.json",
            "unc": r"\\host\share\file.json",
            "env": r"C:\%TEMP%\file.json",
        }[mutation]
    elif mutation == "wrong_case":
        config["P0_REJECTED_PROFILE"] = config.pop("p0_rejected_profile")
    elif mutation in {"mode_case", "mode_type", "profile_inspect"}:
        config["p0_rejected_mode"] = {
            "mode_case": "ON",
            "mode_type": True,
            "profile_inspect": "inspect-only",
        }[mutation]
    elif mutation == "plan_default":
        config["p0_rejected_inspection_plan"] = config.pop("p0_rejected_profile")
    elif mutation == "missing_saved":
        config.pop("saved_root")
    elif mutation == "word":
        config["word_profile"] = "diffusion-v5"
    else:
        key = {
            "both": "p0_rejected_inspection_plan",
            "legacy": "p0_normal_profile",
            "conversation": "enable_conversation",
            "review": "enable_review_modify",
            "live": "live_authorization",
        }.get(mutation, mutation)
        config[key] = (
            True
            if mutation in {"saved_only", "create_saved", "conversation", "review"}
            else str(tmp_path / "UNOPENED.json")
        )
    with socket.socket() as blocker:
        blocker.bind(("127.0.0.1", 0))
        blocker.listen()
        config["port"] = blocker.getsockname()[1]
        result = run_launcher(config, tmp_path)
    assert result.returncode == 2, result.stderr
    assert "CONFIG_INVALID" in result.stderr and "PORT_IN_USE" not in result.stderr


@pytest.mark.parametrize(
    "kind,mode",
    [("profile", None), ("profile", "off"), ("profile", "on"), ("plan", "inspect-only")],
)
def test_actual_powershell_serializes_closed_selector(tmp_path, kind, mode):
    config = launcher_config(tmp_path)
    capture = tmp_path / "SYNTHETIC-args.cmd"
    capture.write_text("@echo %*\n@exit /b 0\n", encoding="ascii")
    config["python_path"] = str(capture)
    if kind == "plan":
        config["p0_rejected_inspection_plan"] = config.pop("p0_rejected_profile")
    if mode is not None:
        config["p0_rejected_mode"] = mode
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        config["port"] = probe.getsockname()[1]
    result = run_launcher(config, tmp_path)
    assert result.returncode == 0, result.stderr
    option = "--p0-rejected-profile" if kind == "profile" else "--p0-rejected-inspection-plan"
    assert option in result.stdout and "--p0-rejected-adoption" in result.stdout
    assert "--p0-normal-profile" not in result.stdout
    assert ("--p0-rejected-mode" in result.stdout) == (mode is not None)
