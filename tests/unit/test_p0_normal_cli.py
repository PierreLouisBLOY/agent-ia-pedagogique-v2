"""CLI opt-in and lifecycle, with explicit composition doubles and zero provider."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.adapters.inbound.cli import local_browser
from backend.infrastructure.composition.factories import p0_normal_profile


def arguments():
    return ["--port", "9123", "--runtime", "SYNTHETIC_UNOPENED.sqlite", "--data-root",
            "SYNTHETIC_UNOPENED_ROOT", "--runtime-sha256", "a" * 64]


def normal_arguments():
    return [*arguments(), "--saved-root", "SYNTHETIC_UNOPENED_SAVED", "--word-profile",
            "product-v7", "--p0-normal-profile", "SYNTHETIC_UNOPENED_PROFILE.json"]


def test_default_cli_never_constructs_normal_profile_or_binds_provider(monkeypatch):
    def forbidden(**kwargs):
        pytest.fail("Default CLI must not load a normal profile")
    monkeypatch.setattr(p0_normal_profile, "P0NormalProductComposition", forbidden)
    calls = []
    composition = SimpleNamespace(url="http://127.0.0.1:9123/",
                                  serve_forever=lambda: None, close=lambda: calls.append("closed"))
    def build(*args, **kwargs):
        assert kwargs["p0_generation"] is None and kwargs["p0_product_binder"] is None
        calls.append("build-default")
        return composition
    monkeypatch.setattr(local_browser, "build_local_read15", build)
    assert local_browser.main(arguments()) == 0
    assert calls == ["build-default", "closed"]


@pytest.mark.parametrize("mutation", ["saved_root", "word_profile", "create_saved", "saved_only",
    "conversation", "review", "live", "r5_scope", "r5_authorization"])
def test_normal_profile_refuses_mixed_paths_before_loader_or_composition(monkeypatch, capsys, mutation):
    args = normal_arguments()
    if mutation in {"saved_root", "word_profile"}:
        option = "--saved-root" if mutation == "saved_root" else "--word-profile"
        index = args.index(option)
        del args[index:index + 2]
    else:
        args += {"create_saved": ["--create-saved"], "saved_only": ["--saved-only"],
                 "conversation": ["--enable-conversation"], "review": ["--enable-review-modify"],
                 "live": ["--live-authorization", "UNOPENED_GRANT"],
                 "r5_scope": ["--r5-scope", "UNOPENED_SCOPE"],
                 "r5_authorization": ["--r5-authorization", "UNOPENED_GRANT"]}[mutation]
    monkeypatch.setattr(p0_normal_profile, "P0NormalProductComposition",
                        lambda **kwargs: pytest.fail("Loader forbidden before argument validation"))
    monkeypatch.setattr(local_browser, "build_local_read15",
                        lambda *args, **kwargs: pytest.fail("Startup forbidden"))
    assert local_browser.main(args) == 1
    assert capsys.readouterr().out == "P0_NORMAL_EXPLICIT_PROFILE_AND_LIBRARY_REQUIRED\n"


def test_invalid_normal_profile_stops_without_startup_or_path_disclosure(monkeypatch, capsys):
    def invalid(**kwargs):
        raise ValueError("SYNTHETIC PRIVATE PATH DETAIL")
    monkeypatch.setattr(p0_normal_profile, "P0NormalProductComposition", invalid)
    monkeypatch.setattr(local_browser, "build_local_read15",
                        lambda *args, **kwargs: pytest.fail("Startup forbidden"))
    assert local_browser.main(normal_arguments()) == 1
    assert capsys.readouterr().out == "P0_NORMAL_PROFILE_NOT_ADOPTED_OR_INVALID\n"


@pytest.mark.parametrize("failure", [None, "startup", "serve", "interrupt"])
def test_explicit_profile_wiring_clears_resolver_on_all_completed_lifecycles(monkeypatch, failure):
    calls = []
    generation = object()
    def binder(*args):
        return None
    normal = SimpleNamespace(generation=generation, bind=binder,
                             close=lambda: calls.append("normal-closed"))
    def construct(**kwargs):
        assert kwargs["path"] == Path("SYNTHETIC_UNOPENED_PROFILE.json")
        assert kwargs["saved_root"] == Path("SYNTHETIC_UNOPENED_SAVED")
        assert kwargs["target"].expected_sha256 == "a" * 64
        calls.append("normal-constructed")
        return normal
    def serve():
        calls.append("serve")
        if failure == "serve":
            raise RuntimeError("SYNTHETIC server exception")
        if failure == "interrupt":
            raise KeyboardInterrupt
    composition = SimpleNamespace(url="http://127.0.0.1:9123/", serve_forever=serve,
                                  close=lambda: calls.append("composition-closed"))
    def build(*args, **kwargs):
        assert kwargs["p0_generation"] is generation and kwargs["p0_product_binder"] is binder
        assert kwargs["generation_jobs"] is None
        assert not kwargs["enable_conversation"] and not kwargs["enable_review_modify"]
        calls.append("build")
        if failure == "startup":
            raise RuntimeError("SYNTHETIC startup exception")
        return composition
    monkeypatch.setattr(p0_normal_profile, "P0NormalProductComposition", construct)
    monkeypatch.setattr(local_browser, "build_local_read15", build)
    assert local_browser.main(normal_arguments()) == (1 if failure in {"startup", "serve"} else 0)
    assert calls[-1] == "normal-closed"
    assert calls.count("normal-closed") == 1
    assert ("composition-closed" in calls) == (failure != "startup")
