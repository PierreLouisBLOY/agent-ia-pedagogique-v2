"""Protected profile artifacts with declared synthetic composition; zero provider."""

import importlib.util
import json
import os
import stat
import subprocess
import sys
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.adapters.outbound.generation.openai.p0_normal_policy import canonical, sha
from backend.infrastructure.composition.factories.p0_normal_profile import (
    MaskedLocalSecretResolver,
    P0NormalProductComposition,
    read_descriptor,
    verify_source_package,
    windows_operator,
)
from backend.infrastructure.composition.factories.p0_normal_profile_contract import absolute
from backend.infrastructure.config.secrets.provider import ProviderCredentialRef
from tests.unit.test_p0_product_permission import configured_product
from tests.unit.test_p0_source_admission import admitted_fixture

APPLICATION_ROOT = Path(__file__).resolve().parents[2]


def artifact(tmp_path, name, raw):
    path = tmp_path / name
    path.write_bytes(raw)
    return {"path": str(path), "sha256": sha(raw)}


@pytest.mark.parametrize(
    "mutation", ["bytes", "hash", "pretty", "duplicate", "nonfinite", "fields"]
)
def test_protected_binary_document_binding_is_actual_not_merely_declared(tmp_path, mutation):
    desc = artifact(tmp_path, "synthetic-profile.json", canonical({"safe": True}))
    if mutation == "bytes":
        Path(desc["path"]).write_bytes(canonical({"safe": False}))
    elif mutation == "hash":
        desc["sha256"] = "0" * 64
    elif mutation == "pretty":
        desc = artifact(tmp_path, "synthetic-profile.json", b'{ "safe": true }')
    elif mutation == "duplicate":
        desc = artifact(tmp_path, "synthetic-profile.json", b'{"a":1,"a":2}')
    elif mutation == "nonfinite":
        desc = artifact(tmp_path, "synthetic-profile.json", b'{"a":NaN}')
    else:
        desc["key"] = "SYNTHETIC_NOT_A_SECRET"
    with pytest.raises(ValueError):
        read_descriptor(desc)


def test_source_admission_can_preserve_exact_original_pretty_bytes(tmp_path):
    raw = b'{\n  "status": "NON_ADOPTE"\n}'
    desc = artifact(tmp_path, "source-identity.json", raw)
    assert read_descriptor(desc, canonical_required=False) == {"status": "NON_ADOPTE"}
    assert Path(desc["path"]).read_bytes() == raw


@pytest.mark.parametrize(
    "path", ["relative.json", "https://example.invalid/profile", "\\\\network\\share\\profile.json"]
)
def test_normal_profile_accepts_only_explicit_local_absolute_paths(path):
    with pytest.raises(ValueError):
        absolute(path)


def source_package_fixture(tmp_path):
    code = tmp_path / "application"
    (code / "backend").mkdir(parents=True)
    (code / "backend" / "synthetic.py").write_text("VALUE = 'synthetic'\n", encoding="utf-8")
    files = {"backend/synthetic.py": sha((code / "backend/synthetic.py").read_bytes())}
    manifest = artifact(
        tmp_path,
        "source.json",
        canonical({"schema": "P0-NORMAL-SOURCE-MANIFEST-2.0", "source_commit": "1" * 40,
                   "source_tree": "2" * 40, "files": files}),
    )
    package = tmp_path / "synthetic-package.zip"
    with zipfile.ZipFile(package, "w") as archive:
        archive.write(code / "backend/synthetic.py", "distribution/backend/synthetic.py")
        archive.writestr("distribution/P0_NORMAL_SOURCE_MANIFEST.json", Path(manifest["path"]).read_bytes())
    return code, {
        "baseline_commit": "1" * 40,
        "source_manifest": manifest,
        "package": {"path": str(package), "sha256": sha(package.read_bytes())},
    }


@pytest.mark.parametrize(
    "mutation", [None, "source", "new_source", "package", "duplicate", "extra", "traversal"]
)
def test_complete_source_inventory_and_zip_tree_equivalence(tmp_path, mutation):
    code, profile = source_package_fixture(tmp_path)
    package = Path(profile["package"]["path"])
    if mutation == "source":
        (code / "backend/synthetic.py").write_text("CHANGED = True\n")
    elif mutation == "new_source":
        (code / "backend/new.py").write_text("ADDED = True\n")
    elif mutation in {"package", "duplicate", "extra", "traversal"}:
        with zipfile.ZipFile(package, "a") as archive:
            name = {
                "package": "backend/synthetic.py",
                "duplicate": "distribution/backend/synthetic.py",
                "extra": "distribution/backend/extra.py",
                "traversal": "../backend/extra.py",
            }[mutation]
            archive.writestr(name, "CHANGED = True\n")
        profile["package"]["sha256"] = sha(package.read_bytes())
    if mutation is None:
        verify_source_package(profile, application_root=code)
    else:
        with pytest.raises(ValueError):
            verify_source_package(profile, application_root=code)


def rewrite_source_fixture(tmp_path, code, profile, files):
    manifest = {"schema": "P0-NORMAL-SOURCE-MANIFEST-2.0", "source_commit": "1" * 40,
                "source_tree": "2" * 40, "files": files}
    raw = canonical(manifest)
    profile["source_manifest"] = artifact(tmp_path, "source.json", raw)
    package = Path(profile["package"]["path"])
    with zipfile.ZipFile(package, "w") as archive:
        for name in files:
            archive.write(code / name, "distribution/" + name)
        archive.writestr("distribution/P0_NORMAL_SOURCE_MANIFEST.json", raw)
    profile["package"]["sha256"] = sha(package.read_bytes())


@pytest.mark.parametrize("name", ["backend/new.PY", "backend/new.JS", "backend/new.JSON",
                                  "Frontend/new.JS"])
def test_unmanifested_windows_case_source_is_rejected(tmp_path, name):
    code, profile = source_package_fixture(tmp_path)
    extra = code / name
    extra.parent.mkdir(exist_ok=True)
    extra.write_text("VALUE = 'SYNTHETIC OUTSIDE MAPPING'\n", encoding="utf-8")
    with pytest.raises(ValueError, match="SOURCE_COVERAGE_CHANGED"):
        verify_source_package(profile, application_root=code)


@pytest.mark.parametrize("suffix", [".PY", ".JS", ".JSON"])
def test_adopted_case_variant_preserves_real_root_and_suffix_names(tmp_path, suffix):
    code, profile = source_package_fixture(tmp_path)
    (code / "backend").rename(code / "temporary-root")
    (code / "temporary-root").rename(code / "Backend")
    extra = code / "Backend" / ("extra" + suffix)
    extra.write_text("SYNTHETIC QUALIFIED VARIANT\n", encoding="utf-8")
    actual_root = next(path for path in code.iterdir() if path.name.casefold() == "backend")
    assert actual_root.name == "Backend"
    files = {path.relative_to(code).as_posix(): sha(path.read_bytes())
             for path in actual_root.iterdir()}
    rewrite_source_fixture(tmp_path, code, profile, files)
    verify_source_package(profile, application_root=code)
    assert all(name.startswith("Backend/") for name in files)


@pytest.mark.parametrize("extra", ["Backend/SYNTHETIC.PY", "Backend/other.py"])
def test_mapping_rejects_case_collision_of_file_or_directory_prefix(tmp_path, extra):
    code, profile = source_package_fixture(tmp_path)
    manifest = json.loads(Path(profile["source_manifest"]["path"]).read_bytes())
    manifest["files"][extra] = "f" * 64
    profile["source_manifest"] = artifact(tmp_path, "source.json", canonical(manifest))
    with pytest.raises(ValueError, match="SOURCE_CASE_COLLISION"):
        verify_source_package(profile, application_root=code)


@pytest.mark.parametrize("extra", ["distribution/Backend/SYNTHETIC.PY", "distribution/Backend/other.py"])
def test_archive_rejects_case_collision_of_file_or_directory_prefix(tmp_path, extra):
    code, profile = source_package_fixture(tmp_path)
    package = Path(profile["package"]["path"])
    with zipfile.ZipFile(package, "a") as archive:
        archive.writestr(extra, "SYNTHETIC COLLIDING VARIANT")
    profile["package"]["sha256"] = sha(package.read_bytes())
    with pytest.raises(ValueError, match="CASE_COLLISION|PACKAGE_DUPLICATE"):
        verify_source_package(profile, application_root=code)


@pytest.mark.parametrize("name", ["backend/./synthetic.py", "backend//synthetic.py",
                                  "/backend/synthetic.py", "backend/../synthetic.py",
                                  "backend\\synthetic.py", "backend/synthetic.py:alias"])
@pytest.mark.parametrize("where", ["mapping", "archive"])
def test_raw_source_paths_refuse_aliases_before_normalization(tmp_path, name, where):
    code, profile = source_package_fixture(tmp_path)
    if where == "mapping":
        manifest = json.loads(Path(profile["source_manifest"]["path"]).read_bytes())
        manifest["files"] = {name: "f" * 64}
        profile["source_manifest"] = artifact(tmp_path, "source.json", canonical(manifest))
    else:
        package = Path(profile["package"]["path"])
        with zipfile.ZipFile(package, "a") as archive:
            entry = zipfile.ZipInfo("placeholder")
            # ZipInfo's Windows constructor normalizes a backslash. Preserve
            # the actual malformed header spelling for this raw-path mutation.
            entry.filename = name
            archive.writestr(entry, "SYNTHETIC INVALID PATH")
        profile["package"]["sha256"] = sha(package.read_bytes())
    with pytest.raises(ValueError, match="SOURCE_PATH_REJECTED"):
        verify_source_package(profile, application_root=code)


def test_native_operator_comes_from_windows_process_token():
    value = windows_operator()
    assert set(value) == {"windows_sid", "windows_profile"}
    assert value["windows_sid"].startswith("S-1-") and Path(value["windows_profile"]).is_absolute()
    assert value == windows_operator()


def test_noninteractive_secret_refuses_unmasked_fallback_and_never_uses_environment(monkeypatch):
    ref = ProviderCredentialRef("openai.p0.normal")
    resolver = MaskedLocalSecretResolver(ref)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    monkeypatch.setenv("OPENAI_API_KEY", "SYNTHETIC-NOT-A-KEY")
    with pytest.raises(ValueError, match="MASKED_CONSOLE_REQUIRED"):
        resolver.resolve(ref)
    with pytest.raises(ValueError, match="REFERENCE_REJECTED"):
        resolver.resolve(ProviderCredentialRef("other"))
    resolver.close()
    assert resolver._value is None


def test_helper_retains_file_and_parent_against_write_and_substitution(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "synthetic_tokenizer_module", APPLICATION_ROOT / "tools/p0-tokenize-local.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    parent = tmp_path / "synthetic-encoding"
    parent.mkdir()
    data = parent / "cache-entry"
    data.write_bytes(b"SYNTHETIC ENCODING PLACEHOLDER, NOT USED TO TOKENIZE")
    held = module.RetainedPaths()
    try:
        held.retain(str(data), file=True)
        with pytest.raises(PermissionError):
            data.write_bytes(b"SUBSTITUTED")
        with pytest.raises(PermissionError):
            parent.rename(tmp_path / "moved")
    finally:
        held.close()
    assert data.read_bytes().startswith(b"SYNTHETIC")


def test_verified_helper_ignores_timestamp_valid_unverified_bytecode(tmp_path, monkeypatch):
    from importlib._bootstrap_external import _code_to_timestamp_pyc
    spec = importlib.util.spec_from_file_location(
        "synthetic_tokenizer_cache_module", APPLICATION_ROOT / "tools/p0-tokenize-local.py")
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    source = tmp_path / "synthetic_verified_source.py"
    source.write_text("VALUE = 'VERIFIED_SOURCE'\n", encoding="utf-8")
    cache = Path(importlib.util.cache_from_source(str(source)))
    cache.parent.mkdir()
    before = source.stat()
    cache.write_bytes(_code_to_timestamp_pyc(compile("VALUE = 'UNVERIFIED_BYTECODE'\n", str(source), "exec"),
        int(before.st_mtime), before.st_size))
    raw = cache.read_bytes()
    def load(name):
        module_spec = importlib.util.spec_from_file_location(name, source)
        module = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(module)
        return module.VALUE
    assert load("synthetic_before") == "UNVERIFIED_BYTECODE"
    monkeypatch.setattr(sys, "pycache_prefix", sys.pycache_prefix)
    monkeypatch.setattr(sys, "dont_write_bytecode", sys.dont_write_bytecode)
    helper.disable_unverified_bytecode_cache()
    assert not os.path.lexists(sys.pycache_prefix)
    assert load("synthetic_after") == "VERIFIED_SOURCE"
    assert cache.read_bytes() == raw and not os.path.lexists(sys.pycache_prefix)


@pytest.fixture
def synthetic_tokenizer_manifest():
    return {"schema": "DECLARED_SYNTHETIC_TOKENIZER_BINDING_FIXTURE"}


def complete_profile_fixture(tmp_path, monkeypatch, tokenizer_manifest):
    settings, *_ = configured_product(tmp_path)
    code = tmp_path / "synthetic-application"
    (code / "tools").mkdir(parents=True)
    (code / "tools/p0-tokenize-local.py").write_bytes(
        (APPLICATION_ROOT / "tools/p0-tokenize-local.py").read_bytes()
    )
    source_files = {
        "tools/p0-tokenize-local.py": sha((code / "tools/p0-tokenize-local.py").read_bytes())
    }
    source = artifact(
        tmp_path,
        "synthetic-source.json",
        canonical({"schema": "P0-NORMAL-SOURCE-MANIFEST-2.0", "source_commit": "1" * 40,
                   "source_tree": "2" * 40, "files": source_files}),
    )
    package = tmp_path / "synthetic-qualified.zip"
    with zipfile.ZipFile(package, "w") as archive:
        archive.write(code / "tools/p0-tokenize-local.py", "tools/p0-tokenize-local.py")
        archive.writestr("P0_NORMAL_SOURCE_MANIFEST.json", Path(source["path"]).read_bytes())
    runtime = tmp_path / "synthetic-runtime.bin"
    runtime.write_bytes(b"SYNTHETIC IDENTITY ONLY, NOT A DATABASE")
    target = SimpleNamespace(
        runtime_path=runtime, data_root=tmp_path, expected_sha256=sha(runtime.read_bytes())
    )

    def validate():
        if sha(runtime.read_bytes()) != target.expected_sha256:
            raise ValueError("P0_SYNTHETIC_RUNTIME_CHANGED")

    target.validate = validate
    saved = tmp_path / "synthetic-library"
    saved.mkdir()
    delegation = {
        "schema": "P0-LOCAL-OPERATOR-DELEGATION-1.0",
        **windows_operator(),
        "credential_ref": "openai.p0.normal",
        "local_operator_delegation_accepted": True,
    }
    native_manifest, *_ = admitted_fixture()
    now = datetime.now(UTC)
    tariff = {
        **settings["tariff"],
        "retrieved_at_utc": (now - timedelta(days=1)).isoformat(),
        "evidence_sha256": sha(b"SYNTHETIC PRICE EVIDENCE ONLY"),
    }
    catalogue = {"status": "SYNTHETIC_CATALOGUE_NOT_OFFICIAL"}
    profile = {
        "schema": "P0-NORMAL-PROFILE-1.0",
        "baseline_commit": "1" * 40,
        "source_manifest": source,
        "package": {"path": str(package), "sha256": sha(package.read_bytes())},
        "runtime": {
            "path": str(runtime),
            "data_root": str(tmp_path),
            "sha256": target.expected_sha256,
        },
        "saved_root": str(saved),
        "receipt_root": str(settings["receipt_root"]),
        "source_admission_manifest": artifact(
            tmp_path, "synthetic-source-admission.json", canonical(native_manifest)
        ),
        "operator_delegation": artifact(
            tmp_path, "synthetic-delegation.json", canonical(delegation)
        ),
        "tokenizer_manifest": artifact(
            tmp_path, "tokenizer-identity.json", canonical(tokenizer_manifest)
        ),
        "tariff": artifact(tmp_path, "synthetic-tariff.json", canonical(tariff)),
        "tariff_evidence": artifact(
            tmp_path, "synthetic-price-evidence.txt", b"SYNTHETIC PRICE EVIDENCE ONLY"
        ),
        "institutional_catalog_sha256": sha(canonical(catalogue)),
        "credential_ref": "openai.p0.normal",
    }
    permission = {
        **settings["permission"],
        "baseline_commit": profile["baseline_commit"],
        "issued_at_utc": (now - timedelta(minutes=1)).isoformat(),
        "expires_at_utc": (now + timedelta(days=1)).isoformat(),
        "profile_sha256": sha(canonical(profile)),
        "source_tree_sha256": source["sha256"],
        "package_sha256": profile["package"]["sha256"],
        "runtime_sha256": target.expected_sha256,
        "institutional_catalog_sha256": profile["institutional_catalog_sha256"],
    }
    for name in (
        "source_admission_manifest",
        "operator_delegation",
        "tokenizer_manifest",
        "tariff",
    ):
        permission[name + "_sha256"] = profile[name]["sha256"]
    decision = {
        "schema": "P0-NORMAL-OWNER-DECISION-1.0",
        "status": "ADOPTED",
        "profile_sha256": permission["profile_sha256"],
        "permission_policy_sha256": sha(
            canonical({k: v for k, v in permission.items() if k != "owner_decision_sha256"})
        ),
        "excluded_oracles_and_private_evidence": True,
        "source_authority_unknown_preserved": True,
        "local_operator_delegation_accepted": True,
    }
    for name in (
        "source_admission_manifest",
        "operator_delegation",
        "tokenizer_manifest",
        "tariff",
    ):
        decision[name + "_sha256"] = profile[name]["sha256"]
    owner = artifact(
        tmp_path, "synthetic-decision-NOT-A-REAL-OWNER-ACCORD.json", canonical(decision)
    )
    permission["owner_decision_sha256"] = owner["sha256"]
    env = {
        "schema": "P0-NORMAL-PROFILE-ENVELOPE-1.0",
        "profile": profile,
        "permission": artifact(
            tmp_path, "synthetic-permission-NOT-LIVE.json", canonical(permission)
        ),
        "decision": owner,
    }
    path = Path(artifact(tmp_path, "synthetic-envelope.json", canonical(env))["path"])
    from backend.infrastructure.composition.factories import (
        institutional_catalog,
        p0_normal_profile,
    )

    # The synthetic package has no .git: no parent repository may be consulted.
    actual_run = subprocess.run
    monkeypatch.setattr(
        institutional_catalog, "inspect_institutional_catalog", lambda *args, **kwargs: catalogue
    )

    def selective_run(args, **kwargs):
        if args[0] == "git":
            raise AssertionError("NO_GIT_IN_EXTRACTED_DISTRIBUTION")
        return actual_run(args, **kwargs)

    # actual_run must be the unpatched implementation.
    monkeypatch.setattr(p0_normal_profile.subprocess, "run", selective_run)

    class DeclaredSyntheticTokenizer:
        def __init__(self, *args, **kwargs):
            pass

        def __call__(self, body):
            return {"provider_calls": 0, "recognition": "DECLARED_SYNTHETIC_DOUBLE_NOT_OFFICIAL"}

    monkeypatch.setattr(p0_normal_profile, "LocalTokenizerHelper", DeclaredSyntheticTokenizer)
    built = []

    class ForbiddenTransport:
        def build(self, **kwargs):
            built.append(kwargs)
            raise AssertionError("NO_REAL_TRANSPORT_IN_QUALIFICATION")

    monkeypatch.setattr(
        p0_normal_profile,
        "OpenAISDKResponsesTransportFactory",
        lambda **kwargs: ForbiddenTransport(),
    )
    return path, target, saved, code, env, built


def test_complete_synthetic_profile_binds_only_after_adoption_and_starts_with_zero_effects(
    tmp_path, monkeypatch, synthetic_tokenizer_manifest
):
    path, target, saved, code, env, built = complete_profile_fixture(
        tmp_path, monkeypatch, synthetic_tokenizer_manifest
    )
    composition = P0NormalProductComposition(
        path=path, target=target, saved_root=saved, application_root=code
    )
    assert (
        composition.generation.ledger.slots() == []
        and composition.resolver._value is None
        and built == []
    )
    assert composition.identities()["profile_sha256"] == sha(canonical(env["profile"]))
    composition.close()


@pytest.mark.parametrize("mutation", ["same_physical_store", "application_alias"])
def test_normal_store_native_alias_identity_refuses_before_helper_or_provider(tmp_path, monkeypatch,
        synthetic_tokenizer_manifest, mutation):
    from backend.infrastructure.composition.factories import p0_normal_profile
    path, target, saved, code, env, built = complete_profile_fixture(tmp_path, monkeypatch, synthetic_tokenizer_manifest)
    receipt = Path(env["profile"]["receipt_root"])
    actual_capture = p0_normal_profile.capture_secure_path
    def capture(value, *, allowed_root):
        # Declared synthetic native-ID mutation: two lexical aliases report the
        # same actual ID, or one store resolves to the application directory.
        if mutation == "same_physical_store" and value == receipt:
            return actual_capture(saved, allowed_root=saved)
        if mutation == "application_alias" and value == saved:
            return actual_capture(code, allowed_root=code)
        return actual_capture(value, allowed_root=allowed_root)
    monkeypatch.setattr(p0_normal_profile, "capture_secure_path", capture)
    monkeypatch.setattr(p0_normal_profile, "LocalTokenizerHelper",
                        lambda *a, **k: pytest.fail("Alias refusal must precede tokenizer or resolver"))
    with pytest.raises(ValueError, match="DISTINCT_STORES|OUTSIDE_STORES"):
        P0NormalProductComposition(path=path, target=target, saved_root=saved, application_root=code)
    assert built == []


def test_startup_rejects_changed_helper_source_before_executing_readiness(tmp_path, monkeypatch,
        synthetic_tokenizer_manifest):
    from backend.infrastructure.composition.factories import p0_normal_profile
    path, target, saved, code, env, built = complete_profile_fixture(tmp_path, monkeypatch, synthetic_tokenizer_manifest)
    (code / "tools/p0-tokenize-local.py").write_bytes(b"SYNTHETIC MUTATED HELPER MUST NEVER EXECUTE")
    class ForbiddenProbe:
        def __init__(self, *args, **kwargs):
            pass
        def __call__(self, body):
            pytest.fail("Source/package identity must be checked before helper execution")
    monkeypatch.setattr(p0_normal_profile, "LocalTokenizerHelper", ForbiddenProbe)
    with pytest.raises(ValueError, match="SOURCE_CHANGED"):
        P0NormalProductComposition(path=path, target=target, saved_root=saved, application_root=code)
    assert built == []


@pytest.mark.parametrize("mutation", [None, "commit", "tree", "profile", "old", "missing", "duplicate", "bytes", "prefix"])
def test_package_embeds_exact_adopted_identity_without_git(tmp_path, monkeypatch, mutation):
    code, profile = source_package_fixture(tmp_path)
    raw = Path(profile["source_manifest"]["path"]).read_bytes()
    manifest = json.loads(raw)
    if mutation in {"commit", "tree", "old"}:
        if mutation == "old":
            manifest["schema"] = "P0-NORMAL-SOURCE-MANIFEST-1.0"
        else:
            manifest["source_" + mutation] = "9" * 40 if mutation == "commit" else "MALFORMED"
        raw = canonical(manifest)
        profile["source_manifest"] = artifact(tmp_path, "source.json", raw)
    if mutation == "profile":
        profile["baseline_commit"] = "9" * 40
    package = Path(profile["package"]["path"])
    with zipfile.ZipFile(package, "w") as archive:
        archive.write(code / "backend/synthetic.py", "distribution/backend/synthetic.py")
        if mutation != "missing":
            name = ("other" if mutation == "prefix" else "distribution") + "/P0_NORMAL_SOURCE_MANIFEST.json"
            archive.writestr(name, b"CHANGED" if mutation == "bytes" else raw)
            if mutation == "duplicate":
                archive.writestr(name, raw)
    profile["package"]["sha256"] = sha(package.read_bytes())
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: pytest.fail("No Git or subprocess for source/package verification"))
    if mutation is None:
        verify_source_package(profile, application_root=code)
    else:
        with pytest.raises(ValueError):
            verify_source_package(profile, application_root=code)


@pytest.mark.parametrize("mutation", [None, "head", "tree", "error"])
def test_present_checkout_requires_exact_git_identity_without_fallback(tmp_path, monkeypatch, mutation):
    code, profile = source_package_fixture(tmp_path)
    (code / ".git").mkdir()
    called = []
    def git(args, **kwargs):
        assert args == ["git", "rev-parse", "HEAD", "HEAD^{tree}"] and kwargs["cwd"] == code
        called.append(args)
        if mutation == "error":
            raise subprocess.CalledProcessError(128, args)
        return subprocess.CompletedProcess(args, 0, stdout=("9" * 40 if mutation == "head" else "1" * 40)
            + "\n" + ("9" * 40 if mutation == "tree" else "2" * 40) + "\n")
    monkeypatch.setattr(subprocess, "run", git)
    if mutation is None:
        verify_source_package(profile, application_root=code)
    else:
        with pytest.raises(ValueError, match="CHECKOUT_IDENTITY"):
            verify_source_package(profile, application_root=code)
    assert len(called) == 1


def test_broken_git_symlink_probe_is_rejected_before_any_git_invocation(tmp_path, monkeypatch):
    from backend.infrastructure.filesystem import LocalFileSecurityError
    code, profile = source_package_fixture(tmp_path)
    marker = code / ".git"
    real_lstat, real_lexists = os.lstat, os.path.lexists
    # Declared synthetic lstat of a broken link; no privilege/configuration change.
    monkeypatch.setattr(os.path, "lexists", lambda p: True if Path(p) == marker else real_lexists(p))
    monkeypatch.setattr(os, "lstat", lambda p, *a, **k: SimpleNamespace(st_mode=stat.S_IFLNK, st_file_attributes=0)
                        if Path(p) == marker else real_lstat(p, *a, **k))
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("Broken link must refuse before Git"))
    with pytest.raises(LocalFileSecurityError, match="PATH_REDIRECTION_FORBIDDEN"):
        verify_source_package(profile, application_root=code)


@pytest.mark.parametrize(
    "mutation", ["profile", "source", "runtime", "price", "delegate", "package"]
)
def test_normal_profile_revalidates_artifacts_before_any_secret_or_effect(
    tmp_path, monkeypatch, synthetic_tokenizer_manifest, mutation
):
    path, target, saved, code, env, built = complete_profile_fixture(
        tmp_path, monkeypatch, synthetic_tokenizer_manifest
    )
    composition = P0NormalProductComposition(
        path=path, target=target, saved_root=saved, application_root=code
    )
    if mutation == "profile":
        path.write_bytes(canonical({**env, "extra": True}))
    elif mutation == "source":
        (code / "tools/p0-tokenize-local.py").write_bytes(b"CHANGED")
    elif mutation == "runtime":
        target.runtime_path.write_bytes(b"CHANGED")
    else:
        name = {"price": "tariff", "delegate": "operator_delegation", "package": "package"}[
            mutation
        ]
        Path(env["profile"][name]["path"]).write_bytes(b"CHANGED")
    with pytest.raises(ValueError):
        composition.identities()
    assert (
        composition.resolver._value is None
        and built == []
        and composition.generation.ledger.slots() == []
    )
    composition.close()
