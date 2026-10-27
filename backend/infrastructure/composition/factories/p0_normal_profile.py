"""Opt-in P1 composition; protected local artifacts, no implicit provider authority."""
from __future__ import annotations

import ctypes
import getpass
import io
import json
import os
import re
import subprocess
import sys
import threading
import warnings
import zipfile
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, cast

from backend.adapters.outbound.generation.openai.p0_content import build_p0_content_request
from backend.adapters.outbound.generation.openai.p0_normal_policy import canonical, closed, sha, utc
from backend.adapters.outbound.generation.openai.p0_normal_receipt import (
    P0NormalReceipt,
    pinned_receipt_root,
)
from backend.adapters.outbound.generation.openai.p0_product import P0ProductGenerationAdapter
from backend.adapters.outbound.generation.openai.p0_product_continuity_contract import (
    BoundChain,
    OriginProof,
    bind_chain,
)
from backend.adapters.outbound.generation.openai.p0_product_policy import (
    P1_HASHES,
    validate_permission,
)
from backend.adapters.outbound.openai import OpenAISDKResponsesTransportFactory
from backend.infrastructure.composition.factories.p0_normal_profile_contract import (
    absolute,
    bind_profile,
    descriptor,
)
from backend.infrastructure.composition.factories.p0_product_consent import bind_product_consent
from backend.infrastructure.config.secrets.provider import (
    ProviderCredentialRef,
    ProviderSecretValue,
)
from backend.infrastructure.filesystem import (
    capture_secure_path,
    hash_file_nofollow,
    read_file_nofollow,
)
from backend.modules.work_orchestration.application.queries.p0_local_reference_context import (
    ReadP0LocalReferenceContext,
)
from backend.modules.work_orchestration.application.queries.p0_source_admission import (
    ReadP0SourceAdmission,
)

if TYPE_CHECKING:
    from backend.adapters.inbound.api.p0_creation import P0CreationEndpoint
    from backend.infrastructure.composition.factories.local_browser import Read15RuntimeTarget
    from backend.modules.work_orchestration.application.services.p0_creation import (
        P0CreationService,
    )

_ROOT = Path(__file__).resolve().parents[4]
_CODE_ROOTS = {"backend", "frontend", "tools", "config"}
_CODE_SUFFIXES = {".py", ".js", ".css", ".html", ".ps1", ".json"}


def strict_document(raw: bytes, *, canonical_required: bool = True) -> dict[str, object]:
    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        if len(dict(pairs)) != len(pairs):
            raise ValueError("P0_NORMAL_DOCUMENT_DUPLICATE")
        return dict(pairs)
    value = json.loads(raw, object_pairs_hook=unique,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("P0_NORMAL_DOCUMENT_NONFINITE")))
    if not isinstance(value, dict) or (canonical_required and canonical(value) != raw):
        raise ValueError("P0_NORMAL_DOCUMENT_CANONICAL_REQUIRED")
    return cast(dict[str, object], value)


def read_descriptor(value: object, *, json_document: bool = True, canonical_required: bool = True) -> dict[str, object] | bytes:
    data = descriptor(value)
    path = Path(absolute(data["path"]))
    with pinned_receipt_root(path.parent):
        raw = read_file_nofollow(path, allowed_root=path.parent, maximum_bytes=64_000_000)
    if sha(raw) != data["sha256"]:
        raise ValueError("P0_NORMAL_ARTIFACT_CHANGED")
    return strict_document(raw, canonical_required=canonical_required) if json_document else raw


def windows_operator() -> dict[str, object]:
    """SID and profile of the process token; HTTP nonce is never a human identity."""
    if sys.platform != "win32":
        raise ValueError("P0_NORMAL_WINDOWS_REQUIRED")
    kernel, advapi, userenv = (ctypes.WinDLL(name, use_last_error=True) for name in ("kernel32", "advapi32", "userenv"))
    process = kernel.GetCurrentProcess
    process.restype = ctypes.c_void_p
    open_token = advapi.OpenProcessToken
    open_token.argtypes, open_token.restype = (ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p)), ctypes.c_int
    token = ctypes.c_void_p()
    if not open_token(process(), 8, ctypes.byref(token)):
        raise ValueError("P0_NORMAL_OPERATOR_TOKEN_REQUIRED")
    close = kernel.CloseHandle
    close.argtypes, close.restype = (ctypes.c_void_p,), ctypes.c_int
    try:
        information = advapi.GetTokenInformation
        information.argtypes, information.restype = (ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32)), ctypes.c_int
        size = ctypes.c_uint32()
        information(token, 1, None, 0, ctypes.byref(size))
        buffer = ctypes.create_string_buffer(size.value)
        if not information(token, 1, buffer, size.value, ctypes.byref(size)):
            raise ValueError("P0_NORMAL_OPERATOR_SID_REQUIRED")
        sid = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_void_p))[0]
        convert = advapi.ConvertSidToStringSidW
        convert.argtypes, convert.restype = (ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)), ctypes.c_int
        converted = ctypes.c_void_p()
        if not convert(sid, ctypes.byref(converted)):
            raise ValueError("P0_NORMAL_OPERATOR_SID_REQUIRED")
        free = kernel.LocalFree
        free.argtypes, free.restype = (ctypes.c_void_p,), ctypes.c_void_p
        try:
            sid_text = ctypes.wstring_at(converted)
        finally:
            free(converted)
        profile = userenv.GetUserProfileDirectoryW
        profile.argtypes, profile.restype = (ctypes.c_void_p, ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_uint32)), ctypes.c_int
        length = ctypes.c_uint32()
        profile(token, None, ctypes.byref(length))
        path = ctypes.create_unicode_buffer(length.value)
        if not profile(token, path, ctypes.byref(length)):
            raise ValueError("P0_NORMAL_OPERATOR_PROFILE_REQUIRED")
        return {"windows_sid": sid_text, "windows_profile": path.value}
    finally:
        close(token)


class MaskedLocalSecretResolver:
    """Explicit native masked prompt after preflight, retained only for this session."""
    def __init__(self, credential_ref: ProviderCredentialRef) -> None:
        self.ref = credential_ref
        self.lock = threading.Lock()
        self._value: ProviderSecretValue | None = None

    def resolve(self, credential_ref: ProviderCredentialRef) -> ProviderSecretValue:
        if credential_ref != self.ref:
            raise ValueError("P0_NORMAL_CREDENTIAL_REFERENCE_REJECTED")
        with self.lock:
            if self._value is None:
                if not sys.stdin.isatty():
                    raise ValueError("P0_NORMAL_MASKED_CONSOLE_REQUIRED")
                with warnings.catch_warnings():
                    warnings.simplefilter("error", getpass.GetPassWarning)
                    value = getpass.getpass("Credential OpenAI P0 (saisie masquée, mémoire de session) : ")
                self._value = ProviderSecretValue(value)
            return self._value

    def close(self) -> None:
        with self.lock:
            self._value = None


class LocalTokenizerHelper:
    def __init__(self, manifest: Mapping[str, object], manifest_sha256: str, *, application_root: Path = _ROOT) -> None:
        self.manifest, self.manifest_sha256, self.application_root = dict(manifest), manifest_sha256, application_root

    def __call__(self, body: bytes) -> Mapping[str, object]:
        manifest = self.manifest
        executable = Path(absolute(manifest.get("python_path")))
        if hash_file_nofollow(executable, allowed_root=executable.parent) != manifest.get("python_sha256"):
            raise ValueError("P0_NORMAL_TOKENIZER_INTERPRETER_CHANGED")
        environment = {key: os.environ[key] for key in ("SystemRoot", "WINDIR", "TEMP", "TMP") if key in os.environ}
        environment.update({"PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8"})
        envelope = canonical({"manifest": manifest, "manifest_sha256": self.manifest_sha256, "request_body_utf8": body.decode("utf-8")})
        completed = subprocess.run([str(executable), "-I", "-S", "-B", str(self.application_root / "tools/p0-tokenize-local.py")],
            input=envelope, capture_output=True, timeout=60, env=environment, cwd=self.application_root, check=False)
        if completed.returncode != 0 or len(completed.stdout) > 16_000:
            raise ValueError("P0_NORMAL_LOCAL_TOKENIZER_REFUSED")
        return strict_document(completed.stdout)


def _source_parts(name: object, *, directory: bool = False) -> tuple[str, ...]:
    if not isinstance(name, str) or not name or "\\" in name or ":" in name or "\x00" in name:
        raise ValueError("P0_NORMAL_SOURCE_PATH_REJECTED")
    rendered = name[:-1] if directory and name.endswith("/") else name
    parts = tuple(rendered.split("/"))
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("P0_NORMAL_SOURCE_PATH_REJECTED")
    return parts


def _source_case_unique(names: Mapping[str, object]) -> None:
    prefixes: dict[str, str] = {}
    for name in names:
        parts = _source_parts(name)
        for length in range(1, len(parts) + 1):
            exact = "/".join(parts[:length])
            folded = exact.casefold()
            if folded in prefixes and prefixes[folded] != exact:
                raise ValueError("P0_NORMAL_SOURCE_CASE_COLLISION")
            prefixes[folded] = exact


def verify_source_package(profile: Mapping[str, object], *, application_root: Path) -> None:
    manifest_raw = cast(bytes, read_descriptor(profile["source_manifest"], json_document=False))
    manifest = strict_document(manifest_raw)
    closed(manifest, {"schema", "source_commit", "source_tree", "files"}, "P0_NORMAL_SOURCE_MANIFEST_FIELDS")
    files = manifest["files"]
    if manifest["schema"] != "P0-NORMAL-SOURCE-MANIFEST-2.0" or not isinstance(files, dict) or not files:
        raise ValueError("P0_NORMAL_SOURCE_MANIFEST_REQUIRED")
    for key in ("source_commit", "source_tree"):
        value = manifest[key]
        if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{40}", value) is None:
            raise ValueError("P0_NORMAL_SOURCE_GIT_IDENTITY_REQUIRED")
    if manifest["source_commit"] != profile["baseline_commit"]:
        raise ValueError("P0_NORMAL_BASELINE_CHANGED")
    for name, value in files.items():
        parts = _source_parts(name)
        if (parts[0].casefold() not in _CODE_ROOTS or PurePosixPath(name).suffix.casefold() not in _CODE_SUFFIXES
                or any(p.casefold() == "__pycache__" for p in parts)
                or not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None):
            raise ValueError("P0_NORMAL_SOURCE_MANIFEST_ENTRY")
    _source_case_unique(files)
    # Enumerate actual names so a Backend directory is represented as Backend,
    # never reconstructed as backend on the case-insensitive Windows host.
    roots = [path for path in application_root.iterdir() if path.name.casefold() in _CODE_ROOTS]
    actual = {path.relative_to(application_root).as_posix(): path for root in roots
        for path in root.rglob("*") if path.is_file() and path.suffix.casefold() in _CODE_SUFFIXES
        and not any(p.casefold() == "__pycache__" for p in path.parts)}
    _source_case_unique(actual)
    if set(actual) != set(files):
        raise ValueError("P0_NORMAL_SOURCE_COVERAGE_CHANGED")
    for name, path in actual.items():
        if "\\" in name or ".." in PurePosixPath(name).parts or hash_file_nofollow(path, allowed_root=application_root) != files[name]:
            raise ValueError("P0_NORMAL_SOURCE_CHANGED")
    raw = cast(bytes, read_descriptor(profile["package"], json_document=False))
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        qualified: dict[str, str] = {}
        archive_names: dict[str, object] = {}
        qualified_folded: set[str] = set()
        prefixes: set[str] = set()
        embedded: list[tuple[str, bytes]] = []
        for entry in archive.infolist():
            # ZipInfo.filename normalizes Windows separators and truncates
            # NULs; orig_filename retains the raw header spelling to reject.
            parts = _source_parts(entry.orig_filename, directory=entry.is_dir())
            archive_names["/".join(parts)] = None
            if parts and parts[-1] == "P0_NORMAL_SOURCE_MANIFEST.json":
                if entry.is_dir() or entry.file_size > 4_000_000:
                    raise ValueError("P0_NORMAL_PACKAGE_MANIFEST_MISMATCH")
                embedded.append((entry.filename, archive.read(entry)))
                continue
            index = next((i for i, part in enumerate(parts) if part.casefold() in _CODE_ROOTS), None)
            if index is None or entry.is_dir() or PurePosixPath(entry.filename).suffix.casefold() not in _CODE_SUFFIXES:
                continue
            name = "/".join(parts[index:])
            if name.casefold() in qualified_folded or entry.file_size > 8_000_000:
                raise ValueError("P0_NORMAL_PACKAGE_DUPLICATE_OR_OVERSIZED")
            qualified_folded.add(name.casefold())
            prefixes.add("/".join(parts[:index]))
            qualified[name] = sha(archive.read(entry))
        _source_case_unique(archive_names)
        if qualified != files or len(prefixes) != 1:
            raise ValueError("P0_NORMAL_PACKAGE_SOURCE_MISMATCH")
        expected_name = "/".join(filter(None, (next(iter(prefixes)), "P0_NORMAL_SOURCE_MANIFEST.json")))
        if embedded != [(expected_name, manifest_raw)]:
            raise ValueError("P0_NORMAL_PACKAGE_MANIFEST_MISMATCH")
    # lexists/lstat through the security boundary rejects broken links too.
    # A parent repository is never consulted for a distribution without .git.
    git_marker = capture_secure_path(application_root / ".git", allowed_root=application_root)
    if git_marker.exists:
        with pinned_receipt_root(application_root):
            try:
                completed = subprocess.run(["git", "rev-parse", "HEAD", "HEAD^{tree}"], cwd=application_root,
                    capture_output=True, text=True, check=True, timeout=10)
            except (OSError, subprocess.SubprocessError) as error:
                raise ValueError("P0_NORMAL_CHECKOUT_IDENTITY_UNAVAILABLE") from error
            if (completed.stdout.splitlines() != [manifest["source_commit"], manifest["source_tree"]]
                    or not git_marker.same_identity(capture_secure_path(application_root / ".git", allowed_root=application_root))):
                raise ValueError("P0_NORMAL_CHECKOUT_IDENTITY_CHANGED")


class P0NormalProductComposition:
    def __init__(self, *, path: Path, target: Read15RuntimeTarget, saved_root: Path,
                 application_root: Path = _ROOT) -> None:
        self.path, self.target, self.saved_root, self.application_root = path, target, saved_root, application_root
        if not path.is_absolute():
            raise ValueError("P0_NORMAL_PROFILE_ABSOLUTE_REQUIRED")
        raw = read_file_nofollow(path, allowed_root=path.parent, maximum_bytes=128_000)
        self.envelope, self.envelope_sha256 = strict_document(raw), sha(raw)
        self.permission = cast(dict[str, object], read_descriptor(self.envelope["permission"]))
        self.decision = cast(dict[str, object], read_descriptor(self.envelope["decision"]))
        profile = cast(Mapping[str, object], self.envelope["profile"])
        delegation = cast(dict[str, object], read_descriptor(profile["operator_delegation"]))
        self.profile = dict(bind_profile(self.envelope, permission=self.permission, decision=self.decision,
            delegation=delegation, operator=windows_operator()))
        self.continuity = self.profile["schema"] == "P0-NORMAL-PROFILE-3.0"
        self.source_owner_sha256 = (str(descriptor(self.profile["source_admission_owner_decision"])["sha256"])
            if self.continuity else str(self.permission["owner_decision_sha256"]))
        runtime = cast(Mapping[str, object], self.profile["runtime"])
        if (Path(str(runtime["path"])) != target.runtime_path or Path(str(runtime["data_root"])) != target.data_root
                or runtime["sha256"] != target.expected_sha256 or Path(str(self.profile["saved_root"])) != saved_root):
            raise ValueError("P0_NORMAL_TARGET_AND_STORE_BINDING")
        self.root = Path(str(self.profile["receipt_root"]))
        application_identity = capture_secure_path(application_root, allowed_root=application_root)
        store_identities = []
        for root in (saved_root, self.root):
            before = capture_secure_path(root, allowed_root=root)
            if (not before.is_directory or before.same_identity(application_identity)
                    or before.path.is_relative_to(application_identity.path)):
                raise ValueError("P0_NORMAL_EXISTING_OUTSIDE_STORES_REQUIRED")
            store_identities.append(before)
        if store_identities[0].same_identity(store_identities[1]):
            raise ValueError("P0_NORMAL_DISTINCT_STORES_REQUIRED")
        self.store_identity = store_identities[0]
        self.receipt = P0NormalReceipt(self.root, str(self.permission["permission_namespace_sha256"]))
        self.tariff = cast(dict[str, object], read_descriptor(self.profile["tariff"]))
        self.tokenizer_manifest = cast(dict[str, object], read_descriptor(self.profile["tokenizer_manifest"]))
        source_manifest = cast(dict[str, object], read_descriptor(self.profile["source_admission_manifest"], canonical_required=False))
        self.admission = ReadP0SourceAdmission(source_manifest,
            manifest_sha256=str(descriptor(self.profile["source_admission_manifest"])["sha256"]),
            adopted_manifest_sha256=str(self.decision["source_admission_manifest_sha256"]), owner_admission_sha256=self.source_owner_sha256)
        self.local_context: ReadP0LocalReferenceContext | None = None
        self.local_context_adoption: dict[str, object] | None = None
        if self.profile["schema"] in {"P0-NORMAL-PROFILE-2.0", "P0-NORMAL-PROFILE-3.0"}:
            local_manifest = cast(dict[str, object], read_descriptor(self.profile["local_reference_context_manifest"]))
            self.local_context = ReadP0LocalReferenceContext(local_manifest,
                manifest_sha256=str(descriptor(self.profile["local_reference_context_manifest"])["sha256"]),
                adopted_manifest_sha256=str(self.decision["local_reference_context_manifest_sha256"]),
                owner_admission_sha256=self.source_owner_sha256, sources=self.admission,
                runtime_sha256=self.target.expected_sha256, institutional_catalogue_sha256=str(self.profile["institutional_catalog_sha256"]))
            self.local_context_adoption = {"profile_schema": self.profile["schema"], "owner_decision_schema": self.decision["schema"],
                "profile_sha256": self.permission["profile_sha256"], "owner_decision_sha256": self.permission["owner_decision_sha256"],
                "local_reference_context_manifest_sha256": self.local_context.manifest_sha256}
            if self.continuity:
                self.local_context_adoption.update(
                    continuity_manifest_sha256=descriptor(self.profile["continuity_manifest"])["sha256"],
                    continuity_anchor_sha256=descriptor(self.profile["continuity_anchor"])["sha256"],
                    source_admission_owner_decision_sha256=self.source_owner_sha256)
        self.resolver = MaskedLocalSecretResolver(ProviderCredentialRef(str(self.profile["credential_ref"])))
        self.tokenizer = LocalTokenizerHelper(self.tokenizer_manifest, str(self.permission["tokenizer_manifest_sha256"]), application_root=application_root)
        current = self.identities()
        families, levels = cast(list[str], self.permission["allowed_families"]), cast(list[str], self.permission["allowed_levels"])
        if not families or not levels:
            raise ValueError("P0_NORMAL_EMPTY_PERMISSION")
        # Expiry closes future previews, while immutable confirmed receipts may
        # still be recovered without a new grant, secret, tokenizer or transport.
        validation_time = min(datetime.now(UTC), utc(self.permission["expires_at_utc"]) - timedelta(microseconds=1))
        validate_permission(self.permission, identities=current, now=validation_time, family=families[0], level=levels[0])
        if self.continuity:
            self._continuity_chain()
        # The helper source/package and every adopted identity are verified
        # before this fixed local probe; no subject/reference/grant, provider
        # COUNT or credential is involved in readiness.
        self.tokenizer(canonical({"model": "gpt-5.6-terra", "input": "P0 LOCAL TOKENIZER READINESS PROBE"}))
        self.generation = P0ProductGenerationAdapter(permission=self.permission, permission_identities=self.identities,
            identity_source=self.grant_identities, tariff=self.tariff, tokenizer=self.tokenizer, receipt_root=self.root,
            resolver=self.resolver, credential_ref=self.resolver.ref, transport=OpenAISDKResponsesTransportFactory(r2_destination=True),
            local_context_adoption=self.local_context_adoption,
            continuity_chain=self._continuity_chain if self.continuity else None)

    def _continuity_chain(self) -> BoundChain:
        if not self.continuity:
            raise ValueError("P0_CONTINUITY_PROFILE_REQUIRED")
        # Exact protected descriptors supply all private campaign data. Nothing
        # in a request/agent command supplies an anchor, permission or grant.
        manifest = cast(dict[str, object], read_descriptor(self.profile["continuity_manifest"]))
        anchor = cast(dict[str, object], read_descriptor(self.profile["continuity_anchor"]))
        read_descriptor(anchor["implementation_decision"], canonical_required=False)
        read_descriptor(anchor["conditions"], json_document=False)
        for witness in cast(list[Mapping[str, object]], anchor["required_historical_reservations"]):
            read_descriptor(witness["metadata_evidence"], canonical_required=False)
        for witness in cast(list[Mapping[str, object]], manifest["historical_reservations"]):
            read_descriptor(witness["metadata_evidence"], canonical_required=False)
        source_owner = cast(dict[str, object], read_descriptor(self.profile["source_admission_owner_decision"]))
        if sha(canonical(source_owner)) != self.source_owner_sha256:
            raise ValueError("P0_CONTINUITY_SOURCE_OWNER_CHANGED")
        origins: list[OriginProof] = []
        prior_manifests: dict[str, Mapping[str, object]] = {}
        for node in cast(list[Mapping[str, object]], manifest["ancestors"]):
            envelope = cast(dict[str, object], read_descriptor(node["profile_envelope"]))
            permission = cast(dict[str, object], read_descriptor(node["permission"]))
            decision = cast(dict[str, object], read_descriptor(node["owner_decision"]))
            profile = cast(Mapping[str, object], envelope["profile"])
            delegation = cast(dict[str, object], read_descriptor(profile["operator_delegation"]))
            bind_profile(envelope, permission=permission, decision=decision, delegation=delegation, operator=windows_operator())
            # Historical bytes retain their own source/package identity; they
            # are not checked against or installed into the current checkout.
            for name in ("source_manifest", "source_admission_manifest", "operator_delegation", "tokenizer_manifest", "tariff"):
                read_descriptor(profile[name], canonical_required=name != "source_admission_manifest")
            for name in ("package", "tariff_evidence"):
                read_descriptor(profile[name], json_document=False)
            if profile["schema"] in {"P0-NORMAL-PROFILE-2.0", "P0-NORMAL-PROFILE-3.0"}:
                read_descriptor(profile["local_reference_context_manifest"])
            if profile["schema"] == "P0-NORMAL-PROFILE-3.0":
                prior_manifests[sha(canonical(permission))] = cast(dict[str, object], read_descriptor(profile["continuity_manifest"]))
                read_descriptor(profile["continuity_anchor"])
                read_descriptor(profile["source_admission_owner_decision"])
            saved = Path(str(profile["saved_root"]))
            identity = capture_secure_path(saved, allowed_root=saved)
            native = sha(canonical({"path": str(saved), "device": identity.device, "inode": identity.inode}))
            origins.append(OriginProof(permission, envelope, decision, delegation, windows_operator(), native))
        self.identities()
        delegation = cast(dict[str, object], read_descriptor(self.profile["operator_delegation"]))
        saved_identity = capture_secure_path(self.saved_root, allowed_root=self.saved_root)
        native = sha(canonical({"path": str(self.saved_root), "device": saved_identity.device, "inode": saved_identity.inode}))
        current = OriginProof(self.permission, self.envelope, self.decision, delegation, windows_operator(), native)
        return bind_chain(manifest, origins, current, ancestor_manifests=prior_manifests, anchor=anchor)

    def identities(self) -> Mapping[str, object]:
        from backend.infrastructure.composition.factories.conversation import (
            r2_environment_identity,
        )
        from backend.infrastructure.composition.factories.institutional_catalog import (
            inspect_institutional_catalog,
        )
        current = read_file_nofollow(self.path, allowed_root=self.path.parent, maximum_bytes=128_000)
        if sha(current) != self.envelope_sha256:
            raise ValueError("P0_NORMAL_PROFILE_CHANGED")
        permission = cast(dict[str, object], read_descriptor(self.envelope["permission"]))
        decision = cast(dict[str, object], read_descriptor(self.envelope["decision"]))
        delegation = cast(dict[str, object], read_descriptor(self.profile["operator_delegation"]))
        bind_profile(self.envelope, permission=permission, decision=decision, delegation=delegation, operator=windows_operator())
        r2_environment_identity()
        before = capture_secure_path(self.saved_root, allowed_root=self.saved_root)
        if not self.store_identity.same_identity(before):
            raise ValueError("P0_NORMAL_SAVED_ROOT_CHANGED")
        self.receipt._root_unchanged()
        self.target.validate()
        verify_source_package(self.profile, application_root=self.application_root)
        for name in ("source_admission_manifest", "tokenizer_manifest", "tariff"):
            read_descriptor(self.profile[name], canonical_required=name != "source_admission_manifest")
        if self.profile["schema"] in {"P0-NORMAL-PROFILE-2.0", "P0-NORMAL-PROFILE-3.0"}:
            read_descriptor(self.profile["local_reference_context_manifest"])
        if self.continuity:
            for name in ("continuity_manifest", "continuity_anchor", "source_admission_owner_decision"):
                read_descriptor(self.profile[name])
        if sha(cast(bytes, read_descriptor(self.profile["tariff_evidence"], json_document=False))) != self.tariff["evidence_sha256"]:
            raise ValueError("P0_NORMAL_TARIFF_EVIDENCE_CHANGED")
        # The exact current decision adopts the complete tariff artifact.
        # Its independently recorded admission cannot refer back to the same
        # decision hash: decision -> tariff -> decision would be a hash cycle.
        catalogue = sha(canonical(inspect_institutional_catalog(self.target, read=True)))
        if catalogue != self.profile["institutional_catalog_sha256"] or catalogue != self.permission["institutional_catalog_sha256"]:
            raise ValueError("P0_NORMAL_INSTITUTIONAL_CATALOG_CHANGED")
        identities = {key: self.permission[key] for key in P1_HASHES | {"baseline_commit"}}
        actual = {"profile_sha256": sha(canonical(self.profile)), "source_tree_sha256": descriptor(self.profile["source_manifest"])["sha256"],
            "package_sha256": descriptor(self.profile["package"])["sha256"], "runtime_sha256": self.target.expected_sha256,
            "receipt_root_sha256": self.receipt.root_sha256}
        for name in ("source_admission_manifest", "operator_delegation", "tokenizer_manifest", "tariff"):
            actual[name + "_sha256"] = descriptor(self.profile[name])["sha256"]
        if any(identities[k] != v for k,v in actual.items()):
            raise ValueError("P0_NORMAL_PROFILE_PERMISSION_IDENTITIES_CHANGED")
        return identities

    def grant_identities(self, request: Mapping[str, object], body: bytes) -> Mapping[str, object]:
        current = self.identities()
        wire = build_p0_content_request(request)
        fields = {key:value for key,value in current.items() if key in {
            "owner_decision_sha256", "baseline_commit", "source_tree_sha256", "package_sha256", "runtime_sha256",
            "profile_sha256", "output_schema_sha256", "tokenizer_manifest_sha256", "tariff_sha256", "receipt_root_sha256"}}
        return {**fields, "preparation_sha256": sha(canonical(request)), "context_sha256": request["context_sha256"],
            "reference_set_sha256": sha(canonical(request["references"])), "request_sha256": sha(body), "request_bytes": len(body),
            "output_schema_sha256": sha(canonical(wire.output_schema)), "namespace_sha256": str(self.permission["permission_namespace_sha256"])}

    def bind(self, service: P0CreationService, endpoint: P0CreationEndpoint) -> None:
        if self.continuity:
            # Available OFF as a read-only Application callback. The retained
            # original LOCK and full lifecycle are checked on every snapshot.
            endpoint.campaign_snapshot = self.generation.campaign_snapshot
        if self.local_context is None:
            bind_product_consent(service, endpoint, target=self.target, generation=self.generation, admission=self.admission)
            return
        from backend.infrastructure.composition.factories.p0_local_reference_context import (
            build_local_reference_resolver,
        )
        resolver = build_local_reference_resolver(self.target, self.local_context, revalidate=self.identities)
        service.institutional_resolver = resolver
        def metadata() -> list[dict[str, object]]:
            self.identities()
            assert self.local_context is not None
            return self.local_context.metadata()
        endpoint.local_reference_contexts = metadata
        if self.continuity and self.profile["continuity_enabled"] is not True:
            service.generation = None
            endpoint.generation_bound = False
            endpoint.consent_execute = None
            return
        bind_product_consent(service, endpoint, target=self.target, generation=self.generation, admission=self.local_context,
            institutional_resolver=resolver)

    def close(self) -> None:
        self.resolver.close()
